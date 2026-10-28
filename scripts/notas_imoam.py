"""IMOAM: hechos, trazabilidad y redacción controlada para Word institucional."""
from __future__ import annotations
import csv
import hashlib
import io
import json
import re
from datetime import date
from decimal import Decimal
from pathlib import Path

import pdfplumber
from sources import imoam, inegi, inegi_bulletin as B

LABELS = ['Índice estimado', 'IC95 inferior del índice', 'IC95 superior del índice',
          'Variación anual estimada', 'IC95 inferior anual', 'IC95 superior anual']


def extract(pdf: bytes) -> dict:
    rows, first, pub = imoam.parse_pdf(pdf)
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        pages = [page.extract_text() or '' for page in doc.pages]
    if not 1 <= len(pages) <= 12 or any(not p.strip() for p in pages):
        raise ValueError('Boletín incompleto o páginas sin texto; requiere revisión')
    whole = '\n\n'.join(pages)
    if not re.search(r'cifras originales', first, re.I) or not re.search(r'estadística\s+experimental', whole, re.I):
        raise ValueError('Cambio de metodología o tipo de serie: revisar el módulo IMOAM')
    pub_date = date(*pub)
    if pub_date > date.today():
        raise ValueError('La publicación tiene fecha futura')
    # La edición puede no especificar base en texto: no se presume 2018.
    match = re.search(r'(?:base\s*)?((?:19|20)\d{2})\s*=\s*100', whole, re.I)
    vals = [r['value'] for r in rows]
    table_pattern = r'Índice\s+(-?\d+[.,]\d+)\s+(-?\d+[.,]\d+)\s+(-?\d+[.,]\d+)'
    annual_pattern = r'Variación anual\s+(-?\d+[.,]\d+)\s*%?\s+(-?\d+[.,]\d+)\s*%?\s+(-?\d+[.,]\d+)'
    matches = [re.search(table_pattern, first, re.I), re.search(annual_pattern, first, re.I)]
    quotes = [m.group() for m in matches]
    raw_values = [v.replace(',', '.') for m in matches for v in m.groups()]
    return dict(indicator='IMOAM', ym=rows[0]['ym'], period=rows[0]['period'],
                publication_date=pub_date.isoformat(), bulletin=B._extract_bulletin_meta(first, pub).get('numero_boletin'),
                values=vals, base=match.group(1) if match else None, pages=pages,
                source_sha256=hashlib.sha256(pdf).hexdigest(), evidence=quotes, raw_values=raw_values,
                series='original', statistical_status='estimado')


def align(facts: dict, indicator: dict) -> None:
    if inegi.label_to_ym(indicator.get('last_observation', '')) != facts['ym']:
        raise ValueError('Periodo del boletín distinto al periodo de la ficha')
    observed = next((o for o in indicator.get('observations', []) if inegi.label_to_ym(o['period']) == facts['ym']), None)
    if not observed or len(observed['values']) != 6:
        raise ValueError('Falta la observación completa del IMOAM')
    for expected, actual in zip(facts['values'], observed['values']):
        if actual is None or abs(expected - actual) > 0.000001:
            raise ValueError('Discrepancia entre boletín y dashboard; no publicar nota')


def number(value: float, percent=False) -> str:
    return f'{value * (100 if percent else 1):.1f}' + ('%' if percent else '')


def period_text(ym: str) -> str:
    year, month = map(int, ym.split('-'))
    return f'{B.MESES_NOMBRE[month-1]} de {year}'


def paragraphs(facts: dict) -> list[tuple[str, str]]:
    v = facts['values']; annual = v[3]
    movement = 'un aumento' if annual > 0 else 'una disminución' if annual < 0 else 'una variación nula'
    # Solo el piloto: redacción controlada, sin inferencias sobre históricos.
    lead = (f'En {period_text(facts["ym"])}, el IMOAM estima {movement} de '
            f'{number(abs(annual), True)} respecto al mismo mes del año anterior. '
            f'El índice estimado se ubicó en {number(v[0])} puntos, a partir de cifras originales.')
    if v[4] <= 0 <= v[5]:
        uncertainty = ('El intervalo de confianza al 95% de la variación anual incluye cero'
                       + (' y valores negativos' if v[4] < 0 else '')
                       + '. La estimación puntual debe leerse junto con esta incertidumbre; no implica certeza sobre el signo del cambio.')
    elif v[5] < 0:
        uncertainty = 'El intervalo de confianza al 95% de la variación anual se mantiene en terreno negativo. El resultado es una estimación sujeta a incertidumbre.'
    else:
        uncertainty = 'El intervalo de confianza al 95% de la variación anual se mantiene en terreno positivo. El resultado es una estimación sujeta a incertidumbre.'
    index_ci = f'Para el índice estimado, el intervalo de confianza al 95% va de {number(v[1])} a {number(v[2])} puntos.'
    method = ('El IMOAM es una estadística experimental del INEGI que anticipa el IMAI del sector manufacturero. '
              'Corresponde a una estimación con cifras originales, sin ajuste estacional; no es un resultado observado del IMAI ni de la EMIM, ni una variación mensual desestacionalizada.')
    return [('Resultados', lead), ('Incertidumbre de la estimación', uncertainty + ' ' + index_ci), ('Alcance metodológico', method)]


def trace(facts: dict, url: str) -> list[dict]:
    return [dict(variable=label, valor=(str(Decimal(facts['raw_values'][i]) / (100 if i>=3 else 1)) if facts.get('raw_values') else str(v)), unidad='fracción' if i >= 3 else 'puntos',
                 periodo=facts['ym'], comparacion='mismo mes del año anterior' if i>=3 else 'nivel del índice',
                 serie='original', estatus='estimado', fuente=url, ubicacion='página 1, cuadro 1',
                 calculo='valor porcentual / 100' if i>=3 else 'lectura directa', evidencia=facts['evidence'][i//3])
            for i,(label,v) in enumerate(zip(LABELS,facts['values']))]


def write_evidence(directory: Path, facts: dict, pdf: bytes, url: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory/'boletin.pdf').write_bytes(pdf)
    (directory/'boletin.txt').write_text('\n\n'.join(f'PÁGINA {i+1}\n{p}' for i,p in enumerate(facts['pages'])),encoding='utf-8')
    (directory/'hechos.json').write_text(json.dumps({**facts,'source_url':url},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    rows=trace(facts,url)
    with (directory/'trazabilidad.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
