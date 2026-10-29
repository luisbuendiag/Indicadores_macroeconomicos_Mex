"""Extracción de cuadros oficiales IMAI e IGAE, sin mezclar versiones BIE."""
import hashlib,io,re
from datetime import date
import pdfplumber
from sources import inegi_bulletin as B
from sources import inegi

NAMES={'IMAI':['Actividad industrial','Minería','Generación, transmisión','Construcción','Industrias manufactureras'],
       'IGAE':['Indicador Global de la Actividad Económica','Actividades primarias','Actividades secundarias','Actividades terciarias']}

def extract(pdf,key):
    if key not in NAMES:raise ValueError('Indicador no soportado')
    with pdfplumber.open(io.BytesIO(pdf)) as d:pages=[p.extract_text() or '' for p in d.pages]
    if len(pages)!=5 or any(not p.strip() for p in pages):raise ValueError('Cambió la estructura del boletín')
    if not re.search(r'\('+key+r'\)',pages[0]):raise ValueError('Producto incorrecto')
    pub=B._extract_pub_date(pages[0]);ref=B._extract_data_month(pages[0])
    if not pub or not ref:raise ValueError('Fechas ausentes')
    if date(*pub)>date.today():raise ValueError('Publicación futura')
    if 'independiente' not in pages[1] or 'Cifras preliminares' not in pages[3]:raise ValueError('Cambió la metodología o el estatus estadístico')
    ym=f'{ref[0]:04d}-{ref[1]:02d}'
    if tuple(ref)>=tuple(pub[:2]):raise ValueError('Periodo incompatible')
    adjusted=pages[1].split('Cuadro 1',1)[1].split('Nota:',1)[0]
    original=pages[3].split('Cuadro 2',1)[1]
    if 'desestacionalizadas' not in adjusted or 'CIFRAS ORIGINALES' not in pages[3]:raise ValueError('Tipo de serie cambió')
    rows=[]
    for label in NAMES[key]:
        # La fila de energía tiene una etiqueta multilínea; acotar hasta el siguiente sector.
        if label.startswith('Generación'):
            pattern=r'Generación, transmisión.{0,400}?(-?\d+\.\d+)\s+(-?\d+\.\d+)'
        else:
            pattern=re.escape(label)+r'\s+'+(r'(\d+\.\d+)\s+' if key=='IGAE' else '')+r'(-?\d+\.\d+)\s+(-?\d+\.\d+)'
        m=re.search(pattern,adjusted,re.S)
        if not m:raise ValueError('No se pudo leer la fila ajustada: '+label)
        vals=[float(x) for x in m.groups()]
        mo,yr=vals[-2:]
        # Cifras originales: fila completa con anual y acumulado.
        if label.startswith('Generación'):
            pat=r'Generación, transmisión.{0,400}?(-?\d+\.\d+)\s+(-?\d+\.\d+)'
        else:pat=re.escape(label)+r'\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)'
        o=re.search(pat,original,re.S)
        if not o:raise ValueError('No se pudo leer la fila original: '+label)
        rows.append(dict(label=label,index=vals[0] if key=='IGAE' else None,mom=mo,yoy=yr,original=float(o[1]),ytd=float(o[2]),evidence_adjusted=m[0],evidence_original=o[0]))
    base=re.search(r'índice\s+(\d{4})=100',pages[0])
    if not base:raise ValueError('Base del índice no identificada')
    if key=='IMAI':
        m=re.search(r'\n(\d+\.\d+)\s*[▲▼]?\s*(-?\d+\.\d+)\s*%\s*[▲▼]?\s*(-?\d+\.\d+)\s*%',pages[0])
        if not m:raise ValueError('Índice de portada no legible')
        rows[0]['index']=float(m[1])
    return dict(indicator=key,ym=ym,period=inegi.ym_to_label(ym,8),publication_date=f'{pub[0]:04d}-{pub[1]:02d}-{pub[2]:02d}',bulletin=B._extract_bulletin_number(pages[0]),base=base[1],rows=rows,pages=pages,source_sha256=hashlib.sha256(pdf).hexdigest())
