"""Edición íntegra del SIC: componentes cíclicos y cambios en puntos."""
import hashlib,io,re
from datetime import date
import pdfplumber
from sources import inegi_bulletin as B,inegi
NAMES={'SIC':'Sistema de Indicadores Cíclicos'}
PRODUCTS={'SIC':('sic_cya','sic')}
MONTHS=['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']
LABELS=[['IGAE','Actividad industrial','Ingresos al por menor','Asegurados permanentes IMSS','Desocupación urbana','Importaciones totales'],['Tendencia del empleo manufacturero','Momento adecuado para invertir','IPC de la BMV real','Tipo de cambio real México-EUA','TIIE','S&P 500 de EUA']]
INVERSE=[[False,False,False,False,True,False],[False,False,False,True,True,False]]
HEADERS=[
'Índice de Indicador ingresos por Asegurados Indicador de Tasa de Indicador global de la suministro de trabajadores Importaciones Año Mes la actividad desocupación Coincidente actividad bienes y permanentes totales industrial1/ urbana económica1/ servicios al por en el IMSS menor1/',
'Indicador de Índice de precios Índice confianza y cotizaciones Tasa de Standard & Tendencia del Tipo de cambio Indicador empresarial: de la Bolsa interés Poor’s 500 Año Mes empleo en las real bilateral Adelantado momento Mexicana de interbancaria (índice manufacturas México-EUA adecuado para Valores en de equilibrio bursátil de invertir1/ términos reales EUA)']
def flat(s):return re.sub(r'\s+',' ',s).strip()
def add_month(ym,delta):
    y,m=map(int,ym.split('-'));v=y*12+m-1+delta;return f'{v//12:04d}-{v%12+1:02d}'
def table(text,n):
    block=text.split('Cuadro '+str(n),1)[1].split('Nota:',1)[0]
    name='Coincidente' if n==1 else 'Adelantado'
    m=re.search(r'Diferencias del Indicador '+name+r' y de sus componentes\s+([a-z]+) de (\d{4})[–-]([a-z]+) de (\d{4})',block)
    if not m:raise ValueError('Faltan periodos del cuadro '+str(n))
    start=f'{m[2]}-{B.MESES_NOMBRE.index(m[1])+1:02d}';end=f'{m[4]}-{B.MESES_NOMBRE.index(m[3])+1:02d}'
    if add_month(start,11)!=end:raise ValueError('Historia mensual incompleta')
    if '(diferencia en puntos respecto al mes inmediato anterior)' not in block:raise ValueError('Unidad o comparación del cuadro cambió')
    pat=r'^(?:(\d{4})\s+)?('+ '|'.join(MONTHS)+r')\.\s+((?:-?\d+\.\d{2}\s+){6}-?\d+\.\d{2})\s*$'
    matches=list(re.finditer(pat,block,re.M))
    if len(matches)!=12:raise ValueError('El cuadro no contiene doce filas de siete valores')
    head=block.split('(diferencia en puntos respecto al mes inmediato anterior)',1)[1][:block.split('(diferencia en puntos respecto al mes inmediato anterior)',1)[1].index(matches[0][0])]
    if flat(head)!=HEADERS[n-1]:raise ValueError('Cambió identidad u orden de columnas SIC')
    rows=[];year=None
    for i,r in enumerate(matches):
        if r[1]:year=int(r[1])
        if year is None:raise ValueError('Año de fila ausente')
        ym=f'{year}-{MONTHS.index(r[2])+1:02d}'
        if ym!=add_month(start,i):raise ValueError('Fechas de filas fuera de secuencia')
        values=list(map(float,r[3].split()))
        rows.append(dict(ym=ym,values=values,location=f'p. {3 if n==1 else 6}, cuadro {n}',evidence=r[0]))
    return rows

def extract(pdf,key='SIC'):
    if key!='SIC':raise ValueError('Indicador no soportado')
    with pdfplumber.open(io.BytesIO(pdf)) as d:pages=[p.extract_text() or '' for p in d.pages]
    if len(pages)!=13 or any(not p.strip() for p in pages):raise ValueError('Cambió la estructura de trece páginas del SIC')
    pub=B._extract_pub_date(pages[0]);number=B._extract_bulletin_number(pages[0])
    if not pub or not number or date(*pub)>date.today():raise ValueError('Fecha o boletín inválidos')
    for i,p in enumerate(pages,1):
        if 'CÍCLICOS (SIC)' not in p or f'Página {i}/13' not in p or B._extract_pub_date(p)!=pub or B._extract_bulletin_number(p)!=number:raise ValueError('Páginas de distinta edición o producto')
    histories=[table(pages[2],1),table(pages[5],2)];cy,ay=[h[-1]['ym'] for h in histories]
    if add_month(cy,1)!=ay or ay>=f'{pub[0]:04d}-{pub[1]:02d}':raise ValueError('Periodos incompatibles entre indicadores')
    intro=pages[0].split('puntos dif. mensual puntos dif. mensual',1)
    if len(intro)!=2:raise ValueError('Portada sin unidades esperadas')
    pairs=re.search(r'(\d+\.\d)\s+[▲▼]?\s*(-?\d+\.\d{2})\s+(\d+\.\d)\s+[▲▼]?\s*(-?\d+\.\d{2})',intro[1])
    if not pairs:raise ValueError('Portada no legible')
    c,a=float(pairs[1]),float(pairs[3]);deltas=[float(pairs[2]),float(pairs[4])]
    if deltas!=[h[-1]['values'][0] for h in histories]:raise ValueError('Portada y cuadros no coinciden')
    covermonths=intro[0].split('Indicador Coincidente Indicador Adelantado',1)[1]
    if flat(covermonths)!=B.MESES_NOMBRE[int(cy[5:])-1]+' '+B.MESES_NOMBRE[int(ay[5:])-1]:raise ValueError('Meses de portada distintos de cuadros')
    if 'línea ubicada en 100' not in pages[1] or 'Hodrick-Prescott' not in pages[12] or 'estandarizan' not in pages[12] or 'FICHA METODOLÓGICA' not in pages[12]:raise ValueError('Revisar metodología, referencia o estandarización')
    if 'Tasa de desocupación urbana1/' not in flat(pages[3]) or 'México-EUA2/' not in flat(pages[7]) or 'equilibrio2/' not in flat(pages[7]):raise ValueError('Cambió identidad de componentes inversos')
    if 'Serie cuyo comportamiento es inverso' not in pages[3] or 'Serie cuyo comportamiento es inverso' not in pages[7]:raise ValueError('Revisar componentes inversos')
    if 'no se establece la magnitud del cambio' not in flat(pages[9]) or 'caída significativa y generalizada' not in flat(pages[9]):raise ValueError('Cambió interpretación de ciclos')
    # Cotejo de posición declarada en la portada, sin dar precisión adicional al nivel redondeado.
    for name,level in [('Coincidente',c),('Adelantado',a)]:
        direction='por arriba' if level>100 else 'por debajo' if level<100 else None
        if direction:
            sentence=re.search(r'El Indicador '+name+r'.{0,180}?tendencia de largo',flat(pages[0]),re.I)
            if not sentence or direction not in sentence[0]:raise ValueError('Posición cíclica incompatible con portada')
    groups=[]
    for n,(level,h) in enumerate(zip([c,a],histories)):
        groups.append(dict(name=['Coincidente','Adelantado'][n],ym=h[-1]['ym'],period=inegi.ym_to_label(h[-1]['ym'],8),level=level,delta=h[-1]['values'][0],history=h,
          components=[dict(label=label,delta=value,inverse=inv,location=h[-1]['location']) for label,value,inv in zip(LABELS[n],h[-1]['values'][1:],INVERSE[n])]))
    return dict(indicator='SIC',ym=cy,period=inegi.ym_to_label(cy,8),publication_date='%04d-%02d-%02d'%tuple(pub),bulletin=number,groups=groups,pages=pages,source_sha256=hashlib.sha256(pdf).hexdigest(),cover_evidence=pairs[0])
