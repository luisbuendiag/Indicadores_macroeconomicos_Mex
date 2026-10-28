"""Piloto IMOAM: generar, auditar y publicar solo cuando se habilita explícitamente.

Sin --publish se prepara una candidata local. Sin clave/modelo o con QA rechazado
nunca se reemplaza el Word publicado. No escribe en los machotes.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import shutil
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import lib_data as L
import lib_notas
import lib_notes_state as S
import notas_imoam as I
import notas_word as W
import notas_review as R

ROOT=Path(__file__).resolve().parents[1]
CONFIG=ROOT/'config/notas_automaticas.json'
VERSION='imoam-pilot-1'


def atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent,delete=False) as f:
        f.write(data);temp=Path(f.name)
    try:os.replace(temp,path)
    finally:temp.unlink(missing_ok=True)


def write_json(path: Path, obj: dict) -> None:
    atomic(path,(json.dumps(obj,ensure_ascii=False,indent=2)+'\n').encode())


def official_url(url: str) -> bool:
    u=urlparse(url)
    return (u.scheme=='https' and u.hostname in ('www.inegi.org.mx','en.www.inegi.org.mx')
            and not u.username and not u.password and u.port in (None,443)
            and re.fullmatch(r'/contenidos/saladeprensa/boletines/\d{4}/imoam/imoam\d{4}_\d{2}\.pdf',u.path) is not None)


def download(url: str) -> bytes:
    if not official_url(url):raise ValueError('URL del boletín IMOAM no oficial o producto incorrecto')
    class OfficialRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,req,fp,code,msg,headers,newurl):
            if not official_url(newurl):raise ValueError('Redirección a una fuente no permitida')
            return super().redirect_request(req,fp,code,msg,headers,newurl)
    req=urllib.request.Request(url,headers={'User-Agent':'IndicadoresMacroMX/NotasIMOAM/1'})
    with urllib.request.build_opener(OfficialRedirect()).open(req,timeout=45) as r:
        if not official_url(r.url):raise ValueError('Destino de boletín no oficial')
        pdf=r.read(20_000_001)
    if len(pdf)>20_000_000 or not pdf.startswith(b'%PDF'):raise ValueError('Boletín no válido o demasiado grande')
    return pdf


def fingerprint(pdf: bytes, template: Path, rules: Path, model: str, root: Path=ROOT) -> str:
    h=hashlib.sha256()
    for data in (pdf,template.read_bytes(),rules.read_bytes(),VERSION.encode(),model.encode()):h.update(hashlib.sha256(data).digest())
    for name in ('build_auto_notes.py','notas_imoam.py','notas_word.py','notas_review.py'):
        h.update(hashlib.sha256((root/'scripts'/name).read_bytes()).digest())
    h.update(hashlib.sha256((root/'config/notas_automaticas.json').read_bytes()).digest())
    return h.hexdigest()


def publish(root: Path, work: Path, facts: dict, fp: str, url: str, review: dict, previous: dict) -> dict:
    """Un solo snapshot Git publica Word, evidencias y metadatos coherentes.

    Antes de Git, los archivos de servicio se reemplazan con rollback en caso de error.
    El historial de fuentes usa una ruta inmutable por fingerprint.
    """
    payload_path=root/'data/indicadores.json'
    payload=json.loads(payload_path.read_text(encoding='utf-8'))
    I.align(facts,payload['indicators']['IMOAM'])
    if payload['indicators']['IMOAM'].get('url_boletin_oficial') != url:
        raise ValueError('El boletín de la ficha cambió durante la revisión')
    dest=root/'downloads/indicadores/IMOAM/nota/IMOAM_nota.docx'
    if not lib_notas.is_valid_docx(work/'IMOAM_nota.docx'):raise ValueError('Candidata Word inválida')
    archive=root/'data/notas/IMOAM'/(fp+'-'+S.digest(work/'IMOAM_nota.docx')[:12])
    archive.mkdir(parents=True,exist_ok=True)
    for name in ('boletin.pdf','boletin.txt','hechos.json','trazabilidad.csv','revision.json','IMOAM_nota.docx'):
        src=work/name;target=archive/name
        if target.exists() and S.digest(target)!=S.digest(src):raise ValueError('Intento de sobrescribir historial inmutable')
        if not target.exists():atomic(target,src.read_bytes())
    stamp=datetime.now(timezone.utc).isoformat(timespec='seconds')
    published=dict(periodo=facts['period'],generated_at=stamp,source_sha256=facts['source_sha256'],fingerprint=fp,
                   docx_sha256=S.digest(work/'IMOAM_nota.docx'),source_url=url,review_model=review['model'],archive=str(archive.relative_to(root)))
    state=dict(status='vigente',message='Nota generada y validada automáticamente',target_period=facts['period'],published=published)
    states=S.load_state(root/'data/notas/estado.json');states['IMOAM']=state
    ind=payload['indicators']['IMOAM']
    ind['nota']={**ind.get('nota',{}),**{k:published[k] for k in ('periodo','generated_at','source_sha256','fingerprint')},
                 'available':True,'format':'docx','path':str(dest.relative_to(root)),'automatic':True,'generated_from':'boletin_validado',
                 'status':'vigente','target_period':facts['period'],'message':state['message']}
    ind.update(nota_disponible=True,url_nota_individual=str(dest.relative_to(root)),nota_causa=None)
    paths=[dest,root/'data/notas/estado.json',payload_path]
    backups={p:p.read_bytes() if p.exists() else None for p in paths}
    try:
        atomic(dest,(work/'IMOAM_nota.docx').read_bytes());write_json(paths[1],states);write_json(payload_path,payload)
    except Exception:
        for path,data in backups.items():
            if data is None:path.unlink(missing_ok=True)
            else:atomic(path,data)
        raise
    return state


def run(root: Path=ROOT, publish_requested=False, record_status=False, pdf_path: Path|None=None, reviewer=None, retry_review=False) -> dict:
    cfg=json.loads((root/'config/notas_automaticas.json').read_text())
    payload=json.loads((root/'data/indicadores.json').read_text())
    ind=payload['indicators']['IMOAM'];states=S.load_state(root/'data/notas/estado.json');previous=states.get('IMOAM',{})
    state=dict(status='pendiente',target_period=ind['last_observation'],published=previous.get('published',{}),message='')
    work=None
    try:
        if pdf_path and publish_requested:
            raise ValueError('No se permite publicar desde un PDF local')
        url=ind.get('url_boletin_oficial','')
        if not official_url(url):raise ValueError('La ficha no identifica un boletín IMOAM oficial')
        pdf=pdf_path.read_bytes() if pdf_path else download(url)
        facts=I.extract(pdf);I.align(facts,ind)
        if cfg.get('template_year') and int(facts['publication_date'][:4]) != cfg['template_year']:
            raise ValueError('Actualizar el membrete y su año antes de publicar esta edición')
        if len(facts['pages'])>cfg['max_source_pages']:raise ValueError('El boletín excede la cobertura del piloto')
        fp=fingerprint(pdf,root/cfg['template'],root/cfg['rules'],os.environ.get('NOTES_REVIEW_MODEL',''),root)
        state['candidate_fingerprint']=fp
        dest=root/'downloads/indicadores/IMOAM/nota/IMOAM_nota.docx'
        pub=previous.get('published',{})
        if pub.get('fingerprint')==fp and dest.exists() and S.digest(dest)==pub.get('docx_sha256'):
            return {**previous,'unchanged':True}
        same = previous.get('candidate_fingerprint') == fp
        attempts = previous.get('review_attempts', 0) if same and not retry_review else 0
        if same and not retry_review and previous.get('status') == 'rechazada':
            return {**previous, 'unchanged': True}
        if attempts >= 3:
            return {**previous, 'unchanged': True, 'message': 'Se agotaron los tres intentos de revisión; requiere intervención'}
        state['review_attempts'] = attempts
        work=Path(os.environ.get('NOTES_WORK_DIR', str(root/'.notes-work')))/'IMOAM'/fp;work.mkdir(parents=True,exist_ok=True)
        # No se reutilizan renders de intentos incompletos.
        for name in ('nota-pagina-*.png','fuente-pagina-*.png'):
            for p in work.glob(name):p.unlink()
        I.write_evidence(work,facts,pdf,url)
        draft=W.build(facts,url,root/cfg['template'],work/'IMOAM_nota.docx')
        (work/'nota.txt').write_text(draft,encoding='utf-8')
        _,note_pages=W.render(work/'IMOAM_nota.docx',cfg['max_note_pages'])
        source_pages=W.raster(work/'boletin.pdf',work/'fuente-pagina')
        if not reviewer and not (os.environ.get('OPENAI_API_KEY') and os.environ.get('NOTES_REVIEW_MODEL')):
            state.update(status='pendiente_configuracion',message='Candidata preparada; falta configurar la revisión automática por API')
        else:
            images=[(f'Boletín oficial página {i+1}',p) for i,p in enumerate(source_pages)]+[(f'Nota Word página {i+1}',p) for i,p in enumerate(note_pages)]
            state['review_attempts'] += 1
            result=(reviewer or R.review)(facts,draft,(root/cfg['rules']).read_text(),images,cfg['max_output_tokens'])
            write_json(work/'revision.json',result)
            if not isinstance(result.get('passed'),bool) or not R.validate(result['result']):
                state.update(status='rechazada',message='La revisión A–D detectó incidencias; se conserva la última nota')
            elif result['passed'] is not True:
                state.update(status='rechazada',message='La revisión no aprobó la publicación')
            else:
                write_json(work/'revision.json',result)
                if publish_requested and os.environ.get('NOTES_AUTO_PUBLISH')=='true':
                    return publish(root,work,facts,fp,url,result,previous)
                state.update(status='validada_sin_publicar',message='Candidata validada; publicación automática deshabilitada')
    except Exception as exc:
        # No se guarda cuerpo de respuestas HTTP ni credenciales en archivos públicos.
        detail = str(exc)[:220] if type(exc) in (ValueError, RuntimeError) else type(exc).__name__
        state.update(status='error',message='No se publicó la candidata: '+detail)
        if work:(work/'error.txt').write_text(type(exc).__name__,encoding='utf-8')
    if work:
        write_json(work/'estado.json',state)
    if record_status:
        states['IMOAM']=state;write_json(root/'data/notas/estado.json',states)
        # Usa root explícito para pruebas y para no mezclar otra copia de trabajo.
        S.decorate(payload['indicators']['IMOAM'],root)
        write_json(root/'data/indicadores.json',payload)
    return state


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--publish',action='store_true');p.add_argument('--record-status',action='store_true')
    p.add_argument('--retry-review', action='store_true', help='Reintentar explícitamente una revisión rechazada o agotada')
    p.add_argument('--pdf',type=Path,help='PDF local para preparación/revisión; nunca publicar desde un archivo local')
    args=p.parse_args()
    if args.pdf and args.publish:p.error('--pdf no se permite con --publish')
    state=run(publish_requested=args.publish,record_status=args.record_status,pdf_path=args.pdf,retry_review=args.retry_review)
    print(json.dumps({k:v for k,v in state.items() if k!='published'},ensure_ascii=False))
    # Fallos de una nota no bloquean los demás indicadores; el estado es explícito.
    return 0

if __name__=='__main__':raise SystemExit(main())
