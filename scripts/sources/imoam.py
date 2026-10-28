"""IMOAM: estimaciones publicadas por INEGI, sin token ni series inventadas.

Conserva cada vintage mensual publicado, no reconstruye un IMAI observado.
Ante errores el pipeline conserva las últimas observaciones válidas.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from io import BytesIO
import re
import urllib.request

from .base import SourceResult, USER_AGENT
from . import inegi_bulletin as B


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


def fetch(config=None, start_year=2024, max_bulletins=36):
    if B.pdfplumber is None:
        return SourceResult(False, warnings=['IMOAM: falta pdfplumber'])
    today = date.today()
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
    items = [B._build_item('IMOAM', col, [r[0][col] for r in found], 'IMOAM_pdf', latest[3], url_meta={latest[3]:(latest[1],latest[2])}, kind='IMOAM') for col in range(6)]
    warnings = []
    if latest[2][:2] < (today.year, today.month):
        warnings.append('IMOAM: aún no se recuperó un boletín válido del mes corriente; comprobar calendario de difusión')
    return SourceResult(True, data={'IMOAM': items}, warnings=warnings)
