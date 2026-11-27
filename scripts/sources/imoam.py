"""IMOAM: estimaciones publicadas por INEGI, sin token ni series inventadas.

Conserva cada vintage mensual publicado, no reconstruye un IMAI observado.
Ante errores el pipeline conserva las últimas observaciones válidas.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from zoneinfo import ZoneInfo
import json
from pathlib import Path
from io import BytesIO
import re
import urllib.request

from .base import SourceResult, USER_AGENT
from . import inegi_bulletin as B


HISTORY_FILE = Path(__file__).resolve().parents[2] / 'config/imoam_history.json'


def _archived_rows():
    """Convierte las estimaciones archivadas de base 2018 al esquema del conector."""
    archive = json.loads(HISTORY_FILE.read_text(encoding='utf-8'))['observaciones']
    if any(len(entry['values']) != 6 for entry in archive.values()):
        raise ValueError('cada boletín debe tener seis valores')
    return {
        ym: [
            dict(ym=ym, period=B.inegi.ym_to_label(ym, 8), value=value,
                 pub_date=entry['publicado'], caracter='estimado')
            for value in entry['values']
        ]
        for ym, entry in archive.items()
    }


def parse_pdf(pdf: bytes) -> tuple[list[dict], str, tuple[int, int, int]]:
    with B.pdfplumber.open(BytesIO(pdf)) as doc:
        text = doc.pages[0].extract_text() or ''
    if 'IMOAM' not in text or 'MANUFACTURERA' not in text.upper():
        raise ValueError('PDF ajeno al IMOAM')
    ref, pub = B._extract_ref_period(text), B._extract_pub_date(text)
    if not ref or not pub:
        raise ValueError('Periodo o publicación ausentes')
    def numbers(label):
        m = re.search(r'^' + label + r'\s+(-?\d+[.,]\d+)\s*%?\s+(-?\d+[.,]\d+)\s*%?\s+(-?\d+[.,]\d+)\s*%?\s*$', text, re.M | re.I)
        if not m:
            raise ValueError('No se encontró el cuadro de estimaciones: ' + label)
        return [float(v.replace(',', '.')) for v in m.groups()]
    idx, annual = numbers('Índice'), numbers('Variación anual')
    if not (0 < idx[1] <= idx[0] <= idx[2] < 500 and -100 < annual[1] <= annual[0] <= annual[2] < 100):
        raise ValueError('Estimación o intervalos inválidos')
    ym = f'{ref[0]:04d}-{ref[1]:02d}'
    if (ref[0], ref[1]) >= (pub[0], pub[1]):
        raise ValueError('El periodo estimado debe preceder a la publicación')
    period = B.inegi.ym_to_label(ym, 8)
    values = idx + [x / 100 for x in annual]
    rows = [dict(ym=ym, period=period, value=v, pub_date=f'{pub[0]:04d}-{pub[1]:02d}-{pub[2]:02d}', caracter='estimado') for v in values]
    return rows, text, pub


def publication_warnings(latest_pub, today, calendar):
    """Only warn for an official release date already due, never a month change."""
    due = []
    for row in calendar.get('items', []):
        if row.get('clave') != 'IMOAM' or row.get('usar_para_frescura') is False:
            continue
        try:
            scheduled = date.fromisoformat(row.get('fecha_iso', ''))
        except (TypeError, ValueError):
            continue
        if scheduled <= today:
            due.append(scheduled)
    if not due:
        return ['IMOAM: calendario sin fechas verificables; no se puede confirmar vigencia']
    published = date(*latest_pub)
    expected = max(due)
    if expected > published:
        return [f'IMOAM: publicación prevista para {expected.isoformat()} no recuperada; '
                'se conserva el último boletín válido']
    return []


def load_release_calendar():
    path = Path(__file__).resolve().parents[2] / 'data/calendario_publicaciones.json'
    try:
        calendar = json.loads(path.read_text(encoding='utf-8'))
        return calendar if isinstance(calendar, dict) else {}
    except (OSError, ValueError):
        return {}


def fetch(config=None, start_year=2025, max_bulletins=36):
    if B.pdfplumber is None:
        return SourceResult(False, warnings=['IMOAM: falta pdfplumber'])
    today = datetime.now(ZoneInfo('America/Mexico_City')).date()
    # Ventana acotada; incluye mes corriente para capturar la publicación nueva.
    end = today.year * 12 + today.month - 1
    months = range(end, max(start_year * 12 - 1, end - max_bulletins), -1)
    def load(n):
        year, zero_month = divmod(n, 12)
        url = B.BULLETIN_URLS['IMOAM'].format(year=year, mm=f'{zero_month+1:02d}')
        try:
            req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
            with urllib.request.urlopen(req, timeout=20) as r:
                pdf = r.read()
            rows, text, pub = parse_pdf(pdf)
            return rows, text, pub, url
        except Exception:
            return None
    with ThreadPoolExecutor(max_workers=4) as pool:
        found = [r for r in pool.map(load, months) if r]
    if not found:
        return SourceResult(False, warnings=['IMOAM: no se pudo validar ningún boletín; se conserva el último dato válido'])
    found.sort(key=lambda r:r[0][0]['ym'])
    latest = found[-1]
    warnings = publication_warnings(latest[2], today, load_release_calendar())
    try:
        by_period = {ym: rows for ym, rows in _archived_rows().items() if ym < latest[0][0]['ym']}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        by_period = {}
        warnings.append(f'IMOAM: no se pudo leer el histórico de boletines: {exc}')
    for rows, _, _, _ in found:
        by_period[rows[0]['ym']] = rows
    history = [rows for _, rows in sorted(by_period.items())]
    items = [
        B._build_item('IMOAM', col, [rows[col] for rows in history], 'IMOAM_pdf', latest[3],
                      url_meta={latest[3]: (latest[1], latest[2])}, kind='IMOAM')
        for col in range(6)
    ]
    return SourceResult(True, data={'IMOAM': items}, warnings=warnings)
