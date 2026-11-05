"""IOAE íntegro: estimaciones, observados e intervalos sin mezclarlos."""
import hashlib,io,re
from datetime import date
import pdfplumber
from sources import inegi_bulletin as B,inegi
NAMES={'IOAE':'Indicador Oportuno de la Actividad Económica'}
PRODUCTS={'IOAE':('ioae','ioae')}
LABELS=['IGAE','Actividades secundarias','Actividades terciarias']
IDS=['total','secundarias','terciarias']

def flat(s):return re.sub(r'\s+',' ',s).strip()
def read_table(text,n):
    b=text.split('Cuadro '+str(n),1)[1].split('Nota:',1)[0]
    ref=re.search(r'\n([a-z]+) y ([a-z]+) de (\d{4})\n',b)
    if not ref or any(m not in B.MESES_NOMBRE for m in ref.group(1,2)):raise ValueError('Periodo ausente en cuadro IOAE')
    months=[B.MESES_NOMBRE.index(ref[i])+1 for i in (1,2)]
    if months[1]!=months[0]+1:raise ValueError('Meses no consecutivos')
    unit=['variación porcentual anual','variación porcentual mensual','índice base'][n-1]
    if unit not in b or 'cifras desestacionalizadas' not in b or 'Intervalo de confianza a 95.0 %' not in b or 'Inferior Superior' not in b:raise ValueError('Serie, unidad o confianza distintas')
    pat=r'^('+ref[1]+'|'+ref[2]+r')\s+(-?\d+\.\d)(?:(2/)|\s+(-?\d+\.\d)\s+(-?\d+\.\d))\s*$'
    matches=list(re.finditer(pat,b,re.M))
    if len(matches)!=6:raise ValueError('Cuadro IOAE debe tener seis filas completas')
    rows=[]
    for i,m in enumerate(matches):
        g=i//2;observed=bool(m[3]);expected_month=ref[1 if i%2==0 else 2]
        if m[1]!=expected_month or observed!=(i==2):raise ValueError('Cambió mes o condición observado/estimado')
        if i%2==0:
            end=matches[i+2].start() if i+2<len(matches) else len(b)
            if LABELS[g] not in b[m.start():end]:raise ValueError('Etiqueta de actividad incompatible')
        point=float(m[2]);lo=float(m[4]) if m[4] else None;hi=float(m[5]) if m[5] else None
        if not observed and not lo<=point<=hi:raise ValueError('Intervalo desordenado o sin estimación')
        if n==3 and (point<=0 or (lo is not None and lo<=0)):raise ValueError('Nivel de índice inválido')
        rows.append(dict(id=IDS[g],label=LABELS[g],ym=f'{ref[3]}-{months[i%2]:02d}',status='observado IMAI' if observed else 'estimación IOAE',point=point,low=lo,high=hi,location=f'p. {1 if n==1 else 2}, cuadro {n}',evidence=m[0]))
    return rows

def extract(pdf,key='IOAE'):
    if key!='IOAE':raise ValueError('Indicador no soportado')
    with pdfplumber.open(io.BytesIO(pdf)) as d:pages=[p.extract_text() or '' for p in d.pages]
    if len(pages)!=6 or any(not p.strip() for p in pages):raise ValueError('Cambió la estructura de seis páginas IOAE')
    pub=B._extract_pub_date(pages[0]);bulletin=B._extract_bulletin_number(pages[0])
    if not pub or not bulletin or date(*pub)>date.today():raise ValueError('Fecha o boletín inválidos')
    for i,p in enumerate(pages,1):
        if 'DE LA ACTIVIDAD ECONÓMICA (IOAE)' not in p or f'Página {i}/6' not in p or B._extract_pub_date(p)!=pub or B._extract_bulletin_number(p)!=bulletin:raise ValueError('Páginas de distinta edición')
    groups=[read_table(pages[0],1),read_table(pages[1],2),read_table(pages[1],3)]
    for page in pages[:2]:
        if 'Se considera como valor observado' not in page or 'Indicador Mensual de la Actividad Industrial (IMAI)' not in page or 'independiente' not in page:raise ValueError('Cambió condición observada o ajuste independiente')
    if any([(r['id'],r['ym'],r['status']) for r in g]!=[(r['id'],r['ym'],r['status']) for r in groups[0]] for g in groups):raise ValueError('Cuadros de distintas actividades o meses')
    ym=groups[0][1]['ym']
    if ym>=f'{pub[0]:04d}-{pub[1]:02d}':raise ValueError('Referencia incompatible con publicación')
    cover=pages[0].split('El IOAE anticipa',1)[0]
    vals=[float(v) for v in re.findall(r'(-?\d+\.\d)\s*%',cover)]
    if vals!=[groups[0][1]['point'],groups[1][1]['point']]:raise ValueError('Portada no coincide con cuadros')
    if B.MESES_NOMBRE[int(ym[5:])-1] not in cover:raise ValueError('Mes de portada incompatible')
    base=re.search(r'índice base (\d{4})=100',pages[1]);method=flat(pages[5])
    if not base or f'base {base[1]}=100' not in method or 'Factores Dinámicos' not in method or 'validación cruzada' not in method or 'no reemplaza el cálculo tradicional del IGAE' not in method or '95.0 %' not in method:raise ValueError('Revisar base, metodología y alcance IOAE')
    rows=[]
    for i,r in enumerate(groups[0]):
        rows.append({k:r[k] for k in ['id','label','ym','status']}|{field:groups[n][i] for n,field in enumerate(['yoy','mom','index'])})
    return dict(indicator=key,ym=ym,period=inegi.ym_to_label(ym,8),base=base[1],publication_date='%04d-%02d-%02d'%tuple(pub),bulletin=bulletin,rows=rows,pages=pages,source_sha256=hashlib.sha256(pdf).hexdigest())
