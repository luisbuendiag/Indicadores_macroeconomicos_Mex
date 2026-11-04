"""PIB oportuno y trimestral: cuadros completos de una misma edición."""
import hashlib,io,re
from datetime import date
import pdfplumber
from sources import inegi_bulletin as B
NAMES={'PIB':'PIB oportuno','PIBSEC':'PIB trimestral'}
PRODUCTS={'PIB':('pibo','pib_eo'),'PIBSEC':('pibt','pib_Pconst')}
QUARTERS=['primer','segundo','tercer','cuarto']
CORE=['PIB','Actividades primarias','Actividades secundarias','Actividades terciarias']
CODES=['11','21','22','23','31-33','43','46','48-49','51','52','53','54','55','56','61','62','71','72','81','93']
SHORT=['Agropecuario','Minería','Energía, agua y gas','Construcción','Manufacturas','Comercio al por mayor','Comercio al por menor','Transportes y almacenamiento','Información','Financieros y seguros','Inmobiliarios y alquiler','Profesionales y técnicos','Corporativos','Apoyo a negocios y residuos','Educación','Salud y asistencia social','Esparcimiento','Alojamiento y alimentos','Otros servicios','Gobierno y organismos']

def read_original(text,key):
    # Las etiquetas multilínea rodean a veces el vector numérico. Cada fila inicia
    # con su identificador SCIAN o agregado; acotar antes de la siguiente fila.
    if key=='PIB':spec=[('total',r'PIB'),('primarias',r'Actividades primarias'),('secundarias',r'Actividades secundarias'),('terciarias',r'Actividades terciarias')]
    else:
        spec=[('total',r'PIB total a precios de mercado'),('primarias',r'Actividades primarias'),('11',r'11 '),('secundarias',r'Actividades secundarias')]
        spec += [(c,re.escape(c)+' ') for c in CODES[1:5]]
        spec += [('terciarias',r'Actividades terciarias')]+[(c,re.escape(c)+' ') for c in CODES[5:]]
    starts=[]
    for ident,pat in spec:
        m=re.search('^'+pat,text,re.M)
        if not m:raise ValueError('Falta fila original '+ident)
        starts.append((ident,m.start()))
    if [s for _,s in starts]!=sorted(s for _,s in starts):raise ValueError('Orden de filas originales cambió')
    vectors=list(re.finditer(r'(?<![\d.])(-?\d+\.\d+)(?:\s+-?\d+\.\d+){6}(?![\d.])',text))
    if len(vectors)!=len(spec):raise ValueError('Número de filas originales cambió')
    rows=[]
    for i,(ident,start) in enumerate(starts):
        end=starts[i+1][1] if i+1<len(starts) else len(text)
        block=text[start:end];vals=re.findall(r'(?<![\d.])-?\d+\.\d+(?![\d.])',block)
        if len(vals)!=7:raise ValueError('Columnas originales ambiguas '+ident)
        label=SHORT[CODES.index(ident)] if ident in CODES else CORE[['total','primarias','secundarias','terciarias'].index(ident)]
        rows.append(dict(id=ident,label=label,values=list(map(float,vals)),original=float(vals[5]),ytd=float(vals[6]),previous=float(vals[4]),series='original',location='cuadro 2',evidence=block.strip()))
    return rows

def extract(pdf,key):
    if key not in NAMES:raise ValueError('Indicador no soportado')
    with pdfplumber.open(io.BytesIO(pdf)) as d:pages=[p.extract_text() or '' for p in d.pages]
    expected=4 if key=='PIB' else 5
    if len(pages)!=expected or any(not p.strip() for p in pages):raise ValueError('Cambió la estructura del boletín')
    pub=B._extract_pub_date(pages[0]);bulletin=B._extract_bulletin_number(pages[0])
    if not pub or not bulletin or date(*pub)>date.today():raise ValueError('Fecha o boletín inválidos')
    identity='ESTIMACIÓN OPORTUNA DEL PRODUCTO' if key=='PIB' else 'A PRECIOS CONSTANTES'
    for n,p in enumerate(pages,1):
        if identity not in p or f'Página {n}/{expected}' not in p or B._extract_pub_date(p)!=pub or B._extract_bulletin_number(p)!=bulletin:raise ValueError('Páginas de distinta edición')
    adjusted=pages[1].split('Cuadro 1',1)[1].split('Nota:',1)[0]
    ref=re.search(r'al (primer|segundo|tercer|cuarto) trimestre de (\d{4})',adjusted)
    if not ref:raise ValueError('Periodo trimestral ausente')
    q=QUARTERS.index(ref[1])+1;year=int(ref[2]);end=date(year,q*3,1)
    if end>=date(*pub):raise ValueError('Periodo incompatible')
    if 'cifras desestacionalizadas' not in adjusted or 'independiente' not in pages[1]:raise ValueError('Cambió el ajuste estacional')
    # Los tres encabezados de comparación se validan antes de leer tasas.
    prevq=4 if q==1 else q-1;prevyear=year-1 if q==1 else year
    if not re.search(r'\b'+str(prevq)+r'\.\S* trimestre',adjusted) or not re.search(r'\b'+str(q)+r'\.\S* trimestre',adjusted) or f'{q*3} meses' not in adjusted or f'de {prevyear}' not in adjusted or f'de {year-1}' not in adjusted:raise ValueError('Cambió el encabezado de comparaciones')
    matches=list(re.finditer(r'^(Producto Interno Bruto Oportuno|PIB|Actividades primarias|Actividades secundarias|Actividades terciarias)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s*$',adjusted,re.M))
    if len(matches)!=4:raise ValueError('Faltan filas ajustadas')
    rows=[]
    for m,ident,label in zip(matches,['total','primarias','secundarias','terciarias'],CORE):
        if ident!='total' and m[1]!=label:raise ValueError('Orden ajustado distinto')
        rows.append(dict(id=ident,label=label,mom=float(m[2]),yoy=float(m[3]),ytd=float(m[4]),series='desestacionalizada',location='p. 2, cuadro 1',evidence=m[0]))
    original=pages[2 if key=='PIB' else 3]
    if 'CIFRAS ORIGINALES' not in original or 'Cifras preliminares' not in original or f'al {ref[1]} trimestre de {year}' not in original:raise ValueError('Cambió serie, periodo o estatus original')
    if key=='PIB' and 'Cifras oportunas' not in original:raise ValueError('Falta estatus oportuno')
    if key=='PIBSEC' and 'Cifras revisadas' not in original:raise ValueError('Revisar las revisiones de edición')
    block=original.split('Cuadro 2',1)[1].split('1/ Cifras',1)[0]
    if f'{year-1}1/' not in block or f'{year}1/' not in block or not re.search(r'\b'+str(q*3)+r'(?:2/)?\s*\n?Anual|\b'+str(q*3)+r'\s*\nAnual',block):raise ValueError('Cambió encabezado histórico original')
    header=re.split(r'\nPIB (?:total a precios de mercado|(?=-?\d+\.\d+))',block,maxsplit=1)[0]
    quarters=[int(v) for v in re.findall(r'\b([1-4])\.(?:er|o|°)',header)]
    if quarters!=list(range(q,5))+list(range(1,q+1)):raise ValueError('Orden histórico de trimestres distinto')
    originals=read_original(block,key)
    cover=pages[0].split('Aumentó el PIB',1)[0].split('Disminuyó el PIB',1)[0]
    vals=[float(x) for x in re.findall(r'(-?\d+\.\d+)\s*%',cover)]
    if vals!=[v for r in rows for v in (r['mom'],r['yoy'])]:raise ValueError('Portada no coincide con cuadro 1')
    method=pages[-1];base=re.search(r'precios constantes de (\d{4})',method)
    if not base or 'X-13ARIMA-SEATS' not in method or 'Denton' not in method or 'FICHA METODOLÓGICA' not in method:raise ValueError('Revisar metodología')
    if key=='PIB' and 'no reemplaza' not in original:raise ValueError('Cambió alcance oportuno')
    if key=='PIBSEC':
        a=next(r for r in originals if r['id']=='primarias');b=next(r for r in originals if r['id']=='11')
        if a['values']!=b['values']:raise ValueError('Agregado primario incompatible')
    if any(v < -100 for r in originals for v in r['values']) or any(r[f]<-100 for r in rows for f in ['mom','yoy','ytd']):raise ValueError('Variación real imposible')
    return dict(indicator=key,period=f'{q}T-{str(year)[2:]}'+(' P' if key=='PIB' else ''),quarter=q,year=year,reference=f'{ref[1]} trimestre de {year}',publication_date='%04d-%02d-%02d'%tuple(pub),bulletin=bulletin,base=base[1],rows=rows,originals=originals,pages=pages,source_sha256=hashlib.sha256(pdf).hexdigest())
