"""URL SIC por fecha oficial de publicación; el PDF confirma los periodos."""
import re
from datetime import date
from sources import inegi_bulletin as B, inegi

def publication_date(ind):
    text=ind.get('fecha_publicacion_oficial') or ind.get('fecha_ultima_publicacion')
    if not text:raise ValueError('Falta fecha oficial del SIC')
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}',text):d=date.fromisoformat(text)
    else:
        m=re.fullmatch(r'(\d{1,2}) de ([a-z]+) de (\d{4})',text.strip().lower())
        if not m or m[2] not in B.MESES_NOMBRE:raise ValueError('Fecha oficial SIC no reconocida')
        d=date(int(m[3]),B.MESES_NOMBRE.index(m[2])+1,int(m[1]))
    if d>date.today():raise ValueError('Publicación SIC futura')
    ref=inegi.label_to_ym(ind.get('last_observation') or '')
    if ref is None:
        raise ValueError('Falta periodo mensual verificable del SIC')
    if (d.year,d.month) <= tuple(map(int,ref.split('-'))):
        raise ValueError('La fecha oficial del calendario SIC no es posterior al mes de referencia; conservar la nota anterior')
    return d.isoformat()

def expected_bulletin_url(ind):
    d=publication_date(ind);return f'https://www.inegi.org.mx/contenidos/saladeprensa/boletines/{d[:4]}/sic_cya/sic{d[:4]}_{d[5:7]}.pdf'
