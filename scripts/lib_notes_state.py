"""Metadatos de notas automáticas; sin importar generadores ni hacer llamadas."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / 'data/notas/estado.json'


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_state(path: Path = STATE) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding='utf-8'))


def decorate(ind: dict, root: Path = ROOT) -> None:
    """Conserva la identidad de la nota publicada, aun si falla una candidata."""
    state = load_state(root / 'data/notas/estado.json').get(ind['key'])
    if not state:
        return
    note = ind.setdefault('nota', {})
    published = state.get('published', {})
    path = root / note.get('path', '__sin_nota__')
    if published and path.is_file() and digest(path) == published.get('docx_sha256'):
        note.update({k: published[k] for k in ('periodo', 'generated_at', 'source_sha256', 'fingerprint')})
        note.update(automatic=True, generated_from='boletin_validado')
    note['status'] = state.get('status', 'pendiente')
    note['target_period'] = state.get('target_period')
    note['message'] = state.get('message', '')
    if published and not (path.is_file() and digest(path) == published.get('docx_sha256')):
        note.update(automatic=False, status='error', message='El Word disponible no coincide con la versión validada')
    elif note['status'] == 'vigente' and published.get('periodo') != ind.get('last_observation'):
        note.update(status='pendiente', message='La nota corresponde a un periodo anterior a la ficha')


def validate_published(ind: dict, root: Path = ROOT) -> list[str]:
    """Una bandera automatic:true requiere un historial y QA verificables."""
    note=ind.get('nota',{})
    if not note.get('automatic'):
        return []
    try:
        state=load_state(root/'data/notas/estado.json').get(ind['key'],{})
        pub=state.get('published',{})
        if ind['key']!='IMOAM' or not pub or pub.get('fingerprint')!=note.get('fingerprint'):
            raise ValueError('Falta identidad de la publicación automática')
        archive=(root/pub['archive']).resolve()
        if not archive.is_relative_to((root/'data/notas/IMOAM').resolve()):
            raise ValueError('Historial de nota fuera de la ruta permitida')
        doc=root/note['path']
        if digest(doc)!=pub['docx_sha256'] or digest(archive/'IMOAM_nota.docx')!=pub['docx_sha256']:
            raise ValueError('Word distinto a la versión validada')
        if digest(archive/'boletin.pdf')!=pub['source_sha256'] or note.get('source_sha256')!=pub['source_sha256']:
            raise ValueError('Boletín distinto a la evidencia validada')
        qa=load_state(archive/'revision.json')
        if qa.get('passed') is not True or qa.get('model')!=pub.get('review_model'):
            raise ValueError('Falta revisión aprobada de la nota')
        result=qa.get('result',{})
        if any(result.get(k) is not True for k in ('datos','logica','editorial','visual')) or result.get('issues')!=[]:
            raise ValueError('La nota no supera las cuatro capas de QA')
        facts=load_state(archive/'hechos.json')
        if facts['period']!=pub['periodo'] or facts['period']!=note.get('periodo'):
            raise ValueError('Periodo de nota incompatible con el boletín archivado')
    except (OSError,ValueError,KeyError,TypeError) as exc:
        return [f'[{ind["key"]}] nota automática sin validación reproducible: {exc}']
    return []
