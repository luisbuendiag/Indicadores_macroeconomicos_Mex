"""Notas de SIC desde boletines completos; sin servicios de IA."""
import argparse,csv,hashlib,json,os,re,urllib.request
from pathlib import Path
from urllib.parse import urlparse
from docx import Document
import notas_sic as N
import notas_sic_word as V
import notas_word as W
import build_auto_notes as A
import lib_notes_state as S
from sources import inegi_sic as P

ROOT=Path(__file__).resolve().parents[1]
VERSION='sic-python-1'

def allowed(url,key):
    try:
        u=urlparse(url);product=N.PRODUCTS.get(key)
        if not product:return False
        directory,filename=product
        return u.scheme=='https' and u.hostname=='www.inegi.org.mx' and not u.username and not u.password and u.port in (None,443) and not u.query and not u.fragment and re.fullmatch(r'/contenidos/saladeprensa/boletines/\d{4}/'+directory+'/'+filename+r'\d{4}_\d{2}\.pdf',u.path) is not None
    except ValueError:return False

def download(url,key):
    if not allowed(url,key):raise ValueError('Fuente no permitida')
    class Redirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,req,fp,code,msg,headers,newurl):
            if not allowed(newurl,key):raise ValueError('Redirección no permitida')
            return super().redirect_request(req,fp,code,msg,headers,newurl)
    with urllib.request.build_opener(Redirect()).open(url,timeout=45) as r:
        if not allowed(r.url,key):raise ValueError('Destino no permitido')
        data=r.read(20_000_001)
    if len(data)>20_000_000 or not data.startswith(b'%PDF'):raise ValueError('PDF inválido')
    return data


def publish(root,work,f,fp,url,result,previous,old_url,old_date):
    path=root/'data/indicadores.json';before=path.read_bytes();payload=json.loads(before)
    ind=payload['indicators']['SIC']
    current_date=ind.get('fecha_publicacion_oficial') or ind.get('fecha_ultima_publicacion')
    if ind.get('url_boletin_oficial')!=old_url or ind['last_observation']!=f['period'] or current_date!=old_date:raise ValueError('La ficha SIC cambió durante la revisión')
    ind.update(url_boletin_oficial=url,fecha_publicacion=f['publication_date'],periodo_boletin=f['period'],numero_boletin=f['bulletin'],boletin_validado=True,producto_boletin='Sistema de Indicadores Cíclicos')
    try:
        A.write_json(path,payload)
        return A.publish(root,work,f,fp,url,result,previous)
    except Exception:
        A.atomic(path,before)
        raise


def run(key,root=ROOT,publish_requested=False,pdf_path=None):
    payload=json.loads((root/'data/indicadores.json').read_text());ind=payload['indicators'][key]
    states=S.load_state(root/'data/notas/estado.json');previous=states.get(key,{})
    state=dict(status='pendiente',target_period=ind['last_observation'],published=previous.get('published',{}),message='')
    work=None
    try:
        cfg=json.loads((root/'config/notas_automaticas.json').read_text())
        if cfg.get('enabled') is False or os.environ.get('NOTES_PILOT_ENABLED')=='false':return {**state,'status':'deshabilitada'}
        if pdf_path and publish_requested:raise ValueError('No publicar desde un PDF local')
        old_url=ind['url_boletin_oficial']
        url=P.expected_bulletin_url(ind)
        if not allowed(url,key):raise ValueError('Boletín no oficial')
        pdf=pdf_path.read_bytes() if pdf_path else download(url,key)
        f=N.extract(pdf,key)
        if f['publication_date']!=P.publication_date(ind):raise ValueError('Fecha del boletín distinta al calendario oficial')
        if f['period']!=ind['last_observation']:raise ValueError('Periodo distinto al de la ficha')
        if int(f['publication_date'][:4])!=cfg['template_year']:raise ValueError('Actualizar el membrete institucional')
        h=hashlib.sha256(pdf+(root/cfg['template']).read_bytes()+VERSION.encode())
        h.update(json.dumps(cfg,sort_keys=True).encode())
        for name in ('build_cycle_notes.py','notas_sic.py','notas_sic_word.py','notas_layout.py','notas_word.py','build_auto_notes.py','sources/inegi_sic.py'):h.update((root/'scripts'/name).read_bytes())
        fp=h.hexdigest();state['candidate_fingerprint']=fp
        dest=root/f'downloads/indicadores/{key}/nota/{key}_nota.docx';pub=previous.get('published',{})
        if ind.get('url_boletin_oficial')==url and pub.get('source_url')==url and pub.get('fingerprint')==fp and dest.exists() and S.digest(dest)==pub.get('docx_sha256'):return {**previous,'unchanged':True}
        work=Path(os.environ.get('NOTES_WORK_DIR',str(root/'.notes-work')))/key/fp
        work.mkdir(parents=True,exist_ok=True)
        (work/'boletin.pdf').write_bytes(pdf);(work/'boletin.txt').write_text('\n\n'.join(f['pages']))
        A.write_json(work/'hechos.json',{**f,'source_url':url})
        evidence=[]
        for g in f['groups']:
            evidence.append(dict(variable=g['name']+' nivel',valor=g['level'],unidad='puntos',periodo=g['ym'],serie='componente cíclico; tendencia=100',ubicacion='p. 1, portada',fuente=url))
            labels=[g['name']]+[r['label']+(' (inversa)' if r['inverse'] else '') for r in g['components']]
            for row in g['history']:
                for label,value in zip(labels,row['values']):
                    evidence.append(dict(variable=label+' diferencia mensual',valor=value,unidad='puntos',periodo=row['ym'],serie='ciclo de crecimiento; cambio frente al mes previo',ubicacion=row['location'],fuente=url))
        with (work/'trazabilidad.csv').open('w',encoding='utf-8-sig',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=['variable','valor','unidad','periodo','serie','ubicacion','fuente']);writer.writeheader();writer.writerows(evidence)
        out=work/f'{key}_nota.docx';V.build(f,url,root/cfg['template'],out)
        _,pages=W.render(out,2)
        if len(pages)!=2:raise ValueError('La nota no tiene dos páginas')
        V.validate(N.extract((work/'boletin.pdf').read_bytes(),key),Document(out))
        result=dict(passed=True,kind='reglas_python',model=VERSION,result=dict(datos=True,logica=True,estructura=True,render=True,issues=[]),limits=['Controles locales; no equivalen a revisión visual humana.'])
        A.write_json(work/'revision.json',result)
        if publish_requested and cfg.get('auto_publish') is True and os.environ.get('NOTES_AUTO_PUBLISH','true')=='true':return publish(root,work,f,fp,url,result,previous,old_url,ind['fecha_publicacion_oficial'] if 'fecha_publicacion_oficial' in ind else ind.get('fecha_ultima_publicacion'))
        state.update(status='validada_sin_publicar',message='Nota validada por reglas Python; publicación deshabilitada')
    except Exception as e:state.update(status='error',message='No se publicó la candidata: '+(str(e)[:180] if isinstance(e,(ValueError,RuntimeError)) else type(e).__name__))
    if work:A.write_json(work/'estado.json',state)
    if publish_requested:
        states[key]=state;A.write_json(root/'data/notas/estado.json',states);S.decorate(ind,root);A.write_json(root/'data/indicadores.json',payload)
    return state

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--publish',action='store_true');p.add_argument('--key',choices=list(N.NAMES));p.add_argument('--pdf',type=Path);args=p.parse_args()
    if args.pdf and (args.publish or not args.key):p.error('--pdf requiere --key y no permite --publish')
    for key in [args.key] if args.key else N.NAMES:print(json.dumps({'indicator':key,**run(key,publish_requested=args.publish,pdf_path=args.pdf)},ensure_ascii=False))
