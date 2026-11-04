"""Notas de PIB oportuno y trimestral desde boletines completos; sin servicios de IA."""
import argparse,csv,hashlib,json,os,re,urllib.request
from pathlib import Path
from urllib.parse import urlparse
from docx import Document
import notas_pib as N
import notas_pib_word as V
import notas_word as W
import build_auto_notes as A
import lib_notes_state as S

ROOT=Path(__file__).resolve().parents[1]
VERSION='pib-python-1'

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


def run(key,root=ROOT,publish_requested=False,pdf_path=None):
    payload=json.loads((root/'data/indicadores.json').read_text());ind=payload['indicators'][key]
    states=S.load_state(root/'data/notas/estado.json');previous=states.get(key,{})
    state=dict(status='pendiente',target_period=ind['last_observation'],published=previous.get('published',{}),message='')
    work=None
    try:
        cfg=json.loads((root/'config/notas_automaticas.json').read_text())
        if cfg.get('enabled') is False or os.environ.get('NOTES_PILOT_ENABLED')=='false':return {**state,'status':'deshabilitada'}
        if pdf_path and publish_requested:raise ValueError('No publicar desde un PDF local')
        url=ind['url_boletin_oficial']
        if not allowed(url,key):raise ValueError('Boletín no oficial')
        pdf=pdf_path.read_bytes() if pdf_path else download(url,key)
        f=N.extract(pdf,key)
        if f['period']!=ind['last_observation']:raise ValueError('Periodo distinto al de la ficha')
        if int(f['publication_date'][:4])!=cfg['template_year']:raise ValueError('Actualizar el membrete institucional')
        h=hashlib.sha256(pdf+(root/cfg['template']).read_bytes()+VERSION.encode())
        h.update(json.dumps(cfg,sort_keys=True).encode())
        for name in ('build_gdp_notes.py','notas_pib.py','notas_pib_word.py','notas_layout.py','notas_word.py','build_auto_notes.py'):h.update((root/'scripts'/name).read_bytes())
        fp=h.hexdigest();state['candidate_fingerprint']=fp
        dest=root/f'downloads/indicadores/{key}/nota/{key}_nota.docx';pub=previous.get('published',{})
        if pub.get('fingerprint')==fp and dest.exists() and S.digest(dest)==pub.get('docx_sha256'):return {**previous,'unchanged':True}
        work=Path(os.environ.get('NOTES_WORK_DIR',str(root/'.notes-work')))/key/fp
        work.mkdir(parents=True,exist_ok=True)
        (work/'boletin.pdf').write_bytes(pdf);(work/'boletin.txt').write_text('\n\n'.join(f['pages']))
        A.write_json(work/'hechos.json',{**f,'source_url':url})
        evidence=[]
        q,y=f['quarter'],f['year']
        for row in f['rows']:
            for field in ('mom','yoy','ytd'):
                comparison=('trimestre previo' if field=='mom' else 'enero al trimestre' if field=='ytd' else 'mismo trimestre de un año antes')
                evidence.append(dict(variable=row['id']+' '+row['label']+' '+field,valor=row[field],unidad='porcentaje',periodo=f['period'],serie=row['series'],ubicacion=row['location']+'; '+comparison,fuente=url))
        periods=[str(i)+'T-'+str(y-1) for i in range(q,5)]+['año '+str(y-1)]+[str(i)+'T-'+str(y) for i in range(1,q+1)]+['enero a '+str(q)+'T-'+str(y)]
        for row in f['originals']:
            for period,value in zip(periods,row['values']):
                evidence.append(dict(variable=row['id']+' '+row['label']+' variación anual',valor=value,unidad='porcentaje',periodo=period,serie=row['series'],ubicacion=row['location']+'; respecto al mismo intervalo de un año antes',fuente=url))
        with (work/'trazabilidad.csv').open('w',encoding='utf-8-sig',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=['variable','valor','unidad','periodo','serie','ubicacion','fuente']);writer.writeheader();writer.writerows(evidence)
        out=work/f'{key}_nota.docx';V.build(f,url,root/cfg['template'],out)
        _,pages=W.render(out,2)
        if len(pages)!=2:raise ValueError('La nota no tiene dos páginas')
        V.validate(N.extract((work/'boletin.pdf').read_bytes(),key),Document(out))
        result=dict(passed=True,kind='reglas_python',model=VERSION,result=dict(datos=True,logica=True,estructura=True,render=True,issues=[]),limits=['Controles locales; no equivalen a revisión visual humana.'])
        A.write_json(work/'revision.json',result)
        if publish_requested and cfg.get('auto_publish') is True and os.environ.get('NOTES_AUTO_PUBLISH','true')=='true':return A.publish(root,work,f,fp,url,result,previous)
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
