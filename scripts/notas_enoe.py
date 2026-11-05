"""ENOE mensual: personas, denominadores y series separados por edición."""
import hashlib,io,re
from datetime import date
import pdfplumber
from sources import inegi_bulletin as B,inegi
NAMES={'DESOCUP':'ENOE'}
PRODUCTS={'DESOCUP':('iooe','IOE')}
ACTIVITY=['Total','Población económicamente activa (PEA)','Ocupada','Desocupada','Población no económicamente activa (PNEA)','Disponible','No disponible']
ACT_IDS=['population','pea','occupied','unemployed','pnea','available','unavailable']
RATES=['Tasa de participación económica','Tasa de desocupación (TD)','TD mujeres','TD hombres','Tasa de ocupación parcial y desocupación','Tasa de presión general','Tasa de trabajo asalariado','Tasa de subocupación','Tasa de condiciones críticas de ocupación','Tasa de informalidad laboral 1','Tasa de ocupación en el sector informal 1']
RATE_IDS=['participation','unemployment','unemployment_women','unemployment_men','partial','pressure','salary','underemployment','critical','informality','informal_sector']
DENOMS=['15 años y más']+['PEA']*5+['Población ocupada']*5
ADJUSTED=[RATES[0],'Tasa de ocupación',RATES[7],RATES[1],RATES[2],RATES[3],RATES[9],RATES[10]]
ADJ_IDS=['participation','occupation','underemployment','unemployment','unemployment_women','unemployment_men','informality','informal_sector']
SECTOR_LABELS=['Posición en la ocupación','Trabajadores subordinados y remunerados','Empleadores','Trabajadores por cuenta propia','Trabajadores no remunerados','Sector de actividad económica','Primario','Agricultura, ganadería, silvicultura, caza y pesca','Secundario','Industria extractiva y de la electricidad','Industria manufacturera','Construcción','Terciario','Comercio','Restaurantes y servicios de alojamiento','Transportes, comunicaciones, correo y almacenamiento','Servicios profesionales, financieros y corporativos','Servicios sociales','Servicios diversos','Gobierno y organismos internacionales','No especificado','Nivel de ingresos','Hasta un salario mínimo','Más de 1 hasta 2 salarios mínimos','Más de 2 hasta 3 salarios mínimos','Más de 3 hasta 5 salarios mínimos','Más de 5 salarios mínimos','No recibe ingresos','No especificado']
SECTOR_IDS=['position_total','salaried','employers','self','unpaid','sector_total','primary','agriculture','secondary','extractive','manufacturing','construction','tertiary','commerce','hospitality','transport','professional','social','other_services','government','sector_unspecified','income_total','income_1','income_2','income_3','income_5','income_over5','income_none','income_unspecified']

def flat(s):return re.sub(r'\s+',' ',s).strip()
def clean(s):return re.sub(r'\d+/','',s).strip()
def integers(text):
    # Buscar límites de los tres enteros, conservando espacios de millares.
    # Una partición sólo se acepta si la diferencia coincide exactamente.
    tokens=text.split();found=[]
    for i in range(1,len(tokens)-1):
        for j in range(i+1,len(tokens)):
            parts=[' '.join(tokens[:i]),' '.join(tokens[i:j]),' '.join(tokens[j:])]
            if not all(re.fullmatch(r'-?\d{1,3}(?: \d{3})*',p) for p in parts):continue
            vals=[int(p.replace(' ','')) for p in parts]
            if vals[0]>=0 and vals[1]>=0 and vals[1]-vals[0]==vals[2]:found.append(vals)
    if len(found)!=1:raise ValueError('Enteros ambiguos o diferencia poblacional incompatible')
    return found[0]

def population_rows(block,spec,ids,location,groups=False):
    matches=list(re.finditer(r'^(.+?)\s+((?:-?\d+\s+)+)(\d+\.\d)\s+(\d+\.\d)(?:\s+(-?\d+\.\d))?\s*$',block,re.M))
    expected=spec if not groups else [label if n==0 else ('Mujeres' if n==1 else 'Hombres') if i==0 else label for n in range(3) for i,label in enumerate(spec)]
    if len(matches)!=len(expected):raise ValueError('Número de filas poblacionales cambió')
    rows=[]
    for i,(m,label) in enumerate(zip(matches,expected)):
        if clean(m[1])!=label:raise ValueError('Orden o identidad poblacional cambió: '+label)
        vals=integers(m[2]);relative=[float(m[3]),float(m[4]),float(m[5]) if m[5] else None]
        if not all(0<=v<=100 for v in relative[:2]):raise ValueError('Porcentaje poblacional inválido')
        rows.append(dict(id=ids[i%len(ids)],group=['total','women','men'][i//len(ids)] if groups else 'total',label=label,previous=vals[0],current=vals[1],difference=vals[2],relative_previous=relative[0],relative_current=relative[1],relative_difference=relative[2],series='original',location=location,evidence=m[0]))
    return rows

def rate_rows(block,spec,ids,location,series):
    matches=list(re.finditer(r'^(.+?)\s+(\d+\.\d)\s+(-?\d+\.\d)\s+(-?\d+\.\d)\s*$',block,re.M))
    if len(matches)!=len(spec):raise ValueError('Número de tasas cambió')
    rows=[]
    for m,label,ident in zip(matches,spec,ids):
        if not re.fullmatch(re.escape(label)+r'(?:\s*\d+/)*\s*',m[1]):raise ValueError('Identidad o orden de tasas cambió: '+ident)
        vals=list(map(float,m.group(2,3,4)))
        if not 0<=vals[0]<=100 or (series=='original' and not 0<=vals[1]<=100):raise ValueError('Tasa fuera de dominio')
        rows.append(dict(id=ident,label=label,**dict(zip(['previous','current','difference'] if series=='original' else ['current','mom','yoy'],vals)),series=series,location=location,evidence=m[0]))
    return rows

def get(f,ident,group='total'):return next(r for r in f['population'] if r['id']==ident and r['group']==group)
def rate(f,ident,adjusted=False):return next(r for r in f['adjusted' if adjusted else 'rates'] if r['id']==ident)

def extract(pdf,key='DESOCUP'):
    if key!='DESOCUP':raise ValueError('Indicador no soportado')
    with pdfplumber.open(io.BytesIO(pdf)) as d:pages=[p.extract_text() or '' for p in d.pages]
    if len(pages)!=15 or any(not p.strip() for p in pages):raise ValueError('Cambió la estructura mensual ENOE de quince páginas')
    pub=B._extract_pub_date(pages[0]);bulletin=B._extract_bulletin_number(pages[0]);ref=B._extract_data_month(pages[0])
    if not pub or not bulletin or not ref or date(*pub)>date.today() or tuple(ref)>=tuple(pub[:2]):raise ValueError('Fechas o edición inválidas')
    for i,p in enumerate(pages,1):
        if 'OCUPACIÓN Y EMPLEO (ENOE)' not in p or 'INDICADORES DE OCUPACIÓN Y EMPLEO' not in p or f'Página {i}/15' not in p or B._extract_pub_date(p)!=pub or B._extract_bulletin_number(p)!=bulletin:raise ValueError('Páginas de distinto producto o edición')
    year,month=ref;period=B.MESES_NOMBRE[month-1]+f' de {year-1} y {year}'
    blocks=[pages[3].split('Cuadro 1',1)[1].split('1/ Valor',1)[0],pages[5].split('Cuadro 2',1)[1].split('1/ Porcentaje',1)[0],pages[8].split('Cuadro 4',1)[1].split('1/ Población',1)[0]]
    for b in blocks:
        if period not in flat(b) or f'{year} {year}-{year-1}' not in flat(b):raise ValueError('Periodo o columnas originales distintos')
    population=population_rows(blocks[0],ACTIVITY,ACT_IDS,'p. 4, cuadro 1',True)
    sectors=population_rows(blocks[1],SECTOR_LABELS,SECTOR_IDS,'p. 6, cuadro 2')
    for r in population:
        r['denominator']=('PEA' if r['id'] in ['occupied','unemployed'] else 'PNEA' if r['id'] in ['available','unavailable'] else 'Población de 15 años y más')+'; grupo '+r['group']
    for r in sectors:r['denominator']='Población ocupada'
    rates=rate_rows(blocks[2],RATES,RATE_IDS,'p. 9, cuadro 4','original')
    for r,denom in zip(rates,DENOMS):r['denominator']=denom
    b=pages[11].split('Cuadro 7',1)[1].split('Nota:',1)[0]
    if f'{B.MESES_NOMBRE[month-1]} de {year}' not in b or 'cifras desestacionalizadas' not in b or 'puntos' not in b or 'porcentuales' not in b:raise ValueError('Periodo, serie o unidad ajustada incompatible')
    prev_month=12 if month==1 else month-1;prev_year=year-1 if month==1 else year
    if B.MESES_NOMBRE[prev_month-1] not in b or f'de {prev_year}' not in b or f'de {year-1}' not in b:raise ValueError('Comparaciones ajustadas cambiaron')
    national=b.split('\nNacional\n',1)[1].split('Agregado urbano de 32 ciudades',1)[0];urban=b.split('Agregado urbano de 32 ciudades',1)[1]
    adjusted=rate_rows(national,ADJUSTED,ADJ_IDS,'p. 12, cuadro 7, nacional','desestacionalizada')
    urbanrows=rate_rows(urban,ADJUSTED,ADJ_IDS,'p. 12, cuadro 7, 32 ciudades','desestacionalizada')
    for rows in [adjusted,urbanrows]:
        for r in rows:r['denominator']='15 años y más' if r['id']=='participation' else 'PEA' if r['id'] in ['occupation','unemployment','unemployment_women','unemployment_men'] else 'Población ocupada'
    method=flat(pages[14]);foot=flat(pages[8])
    base=re.search(r'base enero de (\d{4})',foot)
    if not base or 'X-13ARIMA-SEATS' not in method or 'Probabilístico, bietápico, estratificado y por conglomerados' not in method or '15 años y más' not in pages[3] or 'todos sus decimales' not in flat(pages[11]):raise ValueError('Revisar metodología, población o precisión')
    if not all(t in foot for t in ['Porcentaje respecto a la PEA','Porcentaje respecto a la población ocupada','salarios mínimos equivalentes']):raise ValueError('Denominadores o base salarial ausentes')
    f=dict(indicator=key,ym=f'{year}-{month:02d}',period=inegi.ym_to_label(f'{year}-{month:02d}',8),publication_date='%04d-%02d-%02d'%tuple(pub),bulletin=bulletin,wage_base=base[1],population=population,sectors=sectors,rates=rates,adjusted=adjusted,urban=urbanrows,pages=pages,source_sha256=hashlib.sha256(pdf).hexdigest())
    for g in ['total','women','men']:
        for col in ['previous','current']:
            if get(f,'pea',g)[col]!=get(f,'occupied',g)[col]+get(f,'unemployed',g)[col] or get(f,'population',g)[col]!=get(f,'pea',g)[col]+get(f,'pnea',g)[col]:raise ValueError('Identidad poblacional incompatible')
    for ident in ACT_IDS:
        for col in ['previous','current','difference']:
            if get(f,ident)[col]!=get(f,ident,'women')[col]+get(f,ident,'men')[col]:raise ValueError('Desglose por sexo incompatible')
    for col in ['previous','current','difference']:
        for ident in ['position_total','sector_total','income_total']:
            if next(r for r in sectors if r['id']==ident)[col]!=get(f,'occupied')[col]:raise ValueError('Totales de ocupación incompatibles')
    for ident,rateid in [('pea','participation'),('unemployed','unemployment')]:
        r=get(f,ident);t=rate(f,rateid)
        if any(r['relative_'+c]!=t[c] for c in ['previous','current','difference']):raise ValueError('Tasas originales y población incompatibles')
    cover=pages[0].split('Sumó ',1)[0]
    nums=[float(v) for v in re.findall(r'(\d+\.\d)\s*%',cover)]
    if nums!=[rate(f,i)['current'] for i in ['participation','unemployment','underemployment','informality']]:raise ValueError('Portada y cuadro original incompatibles')
    million=re.search(r'(\d+\.\d) millones',cover)
    if not million or abs(float(million[1])-get(f,'pea')['current']/1e6)>.051:raise ValueError('PEA de portada incompatible')
    return f
