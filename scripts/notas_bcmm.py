"""BCMM oportuna íntegra: flujos nominales, saldos y series separadas."""
import hashlib,io,re
from datetime import date
import pdfplumber
from sources import inegi_bulletin as B,inegi
NAMES={'BCMM':'Balanza Comercial de Mercancías de México'}
PRODUCTS={'BCMM':('comext_o','balcom_o')}
LABELS=['Exportaciones totales','Petroleras','No petroleras','Agropecuarias','Extractivas','Manufactureras','Automotrices','No automotrices','Importaciones totales','Petroleras','No petroleras','Bienes de consumo','Petroleras','No petroleras','Bienes intermedios','Petroleras','No petroleras','Bienes de capital','Saldo de la balanza comercial']
IDS=['exports','exports_oil','exports_non_oil','agriculture','extractive','manufacturing','automotive','non_automotive','imports','imports_oil','imports_non_oil','consumption','consumption_oil','consumption_non_oil','intermediate','intermediate_oil','intermediate_non_oil','capital','balance']
HISTORY_LABELS=['Exportaciones totales','Petroleras','No petroleras','Importaciones totales','Petroleras','No petroleras','Balanza comercial total','Petrolera','No petrolera']
HISTORY_IDS=['exports','exports_oil','exports_non_oil','imports','imports_oil','imports_non_oil','balance','balance_oil','balance_non_oil']
MARKET_LABELS=['Total','Estados Unidos','Automotriz','Otras','Resto del mundo','Automotriz','Otras']
MARKET_IDS=['total','usa','usa_auto','usa_other','rest','rest_auto','rest_other']
NUM=r'-?\d{1,3}(?: \d{3})*\.\d'
PCT=r'(?:-?\d+\.\d|S\.S\.)'
DIRS={'descenso':-1,'retroceso':-1,'caída':-1,'disminución':-1,'aumento':1,'avance':1,'alza':1,'crecimiento':1,'incremento':1}
D='('+'|'.join(DIRS)+')'
def flat(s):return re.sub(r'\s+',' ',s).strip()
def value(s):return None if s=='S.S.' else float(s.replace(' ',''))
def row(f,i):return next(r for r in f['rows'] if r['id']==i)
def history(f,i):return next(r for r in f['history'] if r['id']==i)
def close(a,b,tolerance=.21):return abs(a-b)<=tolerance

def history_rows(words,year):
    def header(text):
        found=[w for w in words if w['text']==text]
        if len(found)!=1:raise ValueError('Encabezado histórico BCMM ambiguo: '+text)
        return found[0]
    columns=[header(str(year-2)),header(str(year-1))]
    # Meses publicados en el encabezado, sin derivar posiciones de las curvas.
    tail=[w for w in words if re.fullmatch(r'(?:ene\.-)?[a-z]{3}\.1/|[a-z]{3}\.',w['text']) and w['top']>columns[0]['top']-2 and w['top']<columns[0]['top']+20]
    tail=sorted(tail,key=lambda w:w['x0'])
    if len(tail)!=4:raise ValueError('Cambió el encabezado de cuatro periodos recientes')
    columns+=tail;centers=[(w['x0']+w['x1'])/2 for w in columns]
    boundaries=[centers[0]-32]+[(a+b)/2 for a,b in zip(centers,centers[1:])]+[centers[-1]+40]
    top=max(w['top'] for w in columns)+6
    foot=[w['top'] for w in words if w['text']=='1/' and w['top']>top]
    if not foot:raise ValueError('Falta pie de cifras oportunas del cuadro 2')
    bottom=min(foot);lines={}
    for w in words:
        if top<w['top']<bottom:lines.setdefault(round(w['top']),[]).append(w)
    lines=[sorted(ws,key=lambda w:w['x0']) for _,ws in sorted(lines.items()) if any(w['x0']>boundaries[0] and re.search(r'\d',w['text']) for w in ws)]
    if len(lines)!=9:raise ValueError('Número de filas históricas distinto')
    out=[]
    for ws,label,ident in zip(lines,HISTORY_LABELS,HISTORY_IDS):
        actual=' '.join(w['text'] for w in ws if w['x1']<boundaries[0])
        if actual!=label:raise ValueError('Cambió el orden de filas históricas')
        vals=[]
        for a,b in zip(boundaries,boundaries[1:]):
            text=' '.join(w['text'] for w in ws if a<=(w['x0']+w['x1'])/2<b)
            if not re.fullmatch(r'-?\d{1,3}(?: \d{3})*',text):raise ValueError('Columna histórica no legible')
            vals.append(int(text.replace(' ','')))
        out.append(dict(id=ident,label=label,values=vals,location='p. 2, cuadro 2',series='original'))
    return out,[w['text'] for w in tail]

def rate(text,pattern,ident,label,page):
    m=re.search(pattern,text)
    if not m:raise ValueError('Falta tasa ajustada '+ident)
    return dict(id=ident,label=label,value=DIRS[m[1]]*float(m[2]),location=f'p. {page}, texto',series='desestacionalizada',evidence=m[0])

def adjusted(pages):
    e=flat(pages[4]);i=flat(pages[6]);out=[]
    for ident,label,pat in [
      ('exports','Exportaciones totales',r'exportaciones totales registraron un '+D+r' mensual de (\d+\.\d+) por ciento'),
      ('exports_non_oil','Exportaciones no petroleras',r'un '+D+r' de (\d+\.\d+) % en las exportaciones no petroleras'),
      ('exports_oil','Exportaciones petroleras',r'un '+D+r' de (\d+\.\d+) % en las petroleras'),
      ('manufacturing','Exportaciones manufactureras',r'las manufactureras presentaron una '+D+r' mensual de (\d+\.\d+) por ciento'),
      ('non_automotive','Exportaciones no automotrices',r'una '+D+r' de (\d+\.\d+) % en las exportaciones manufactureras no automotrices'),
      ('automotive','Exportaciones automotrices',r'un '+D+r' de (\d+\.\d+) % en las automotrices')]:out.append(rate(e,pat,ident,label,5))
    for ident,label,pat in [
      ('imports','Importaciones totales',r'importaciones totales de mercancías mostraron un '+D+r' mensual de (\d+\.\d+) %'),
      ('imports_non_oil','Importaciones no petroleras',r'un '+D+r' de (\d+\.\d+) % en las importaciones no petroleras'),
      ('imports_oil','Importaciones petroleras',r'una '+D+r' de (\d+\.\d+) % en las petroleras')]:out.append(rate(i,pat,ident,label,7))
    pat=r'se observaron (incrementos|descensos) mensuales de (\d+\.\d+) % en las importaciones de bienes de consumo \('+D+r' de (\d+\.\d+) % en las de bienes de consumo no petroleros\), de (\d+\.\d+) % en las de bienes de uso intermedio \('+D+r' de (\d+\.\d+) % en las de bienes de uso intermedio no petroleros\) y de (\d+\.\d+) % en las de bienes de capital'
    m=re.search(pat,i)
    if not m:raise ValueError('Cambió la narrativa de importaciones por uso')
    sign=1 if m[1]=='incrementos' else -1
    for ident,label,v in [('consumption','Importaciones de consumo',sign*float(m[2])),('consumption_non_oil','Consumo no petrolero',DIRS[m[3]]*float(m[4])),('intermediate','Importaciones intermedias',sign*float(m[5])),('intermediate_non_oil','Intermedios no petroleros',DIRS[m[6]]*float(m[7])),('capital','Importaciones de capital',sign*float(m[8]))]:out.append(dict(id=ident,label=label,value=v,location='p. 7, texto',series='desestacionalizada',evidence=m[0]))
    total=re.search(r'balanza comercial registró un (superávit|déficit) de ([\d ]+) mdd, monto que se compara con el de ([\d ]+) mdd de ([a-z]+)',e)
    if not total:raise ValueError('Falta saldo ajustado o comparación')
    sign=1 if total[1]=='superávit' else -1
    balances=[dict(id='balance',current=sign*int(total[2].replace(' ','')),previous=sign*int(total[3].replace(' ','')),location='p. 5, texto')]
    for ident,kind in [('balance_non_oil','no petroleros'),('balance_oil','petroleros')]:
        m=re.search(r'un (?:menor|mayor) (superávit|déficit) de la balanza de productos '+kind+r'.*?pasó de ([\d ]+) mdd.*?a ([\d ]+) mdd',e)
        if not m:raise ValueError('Falta saldo ajustado '+ident)
        sign=1 if m[1]=='superávit' else -1
        balances.append(dict(id=ident,previous=sign*int(m[2].replace(' ','')),current=sign*int(m[3].replace(' ','')),location='p. 5, texto'))
    for col in ['previous','current']:
        if not close(balances[0][col],balances[1][col]+balances[2][col],2):raise ValueError('Saldos ajustados incompatibles')
    return out,balances,total[4]

def extract(pdf,key='BCMM'):
    if key!='BCMM':raise ValueError('Indicador no soportado')
    with pdfplumber.open(io.BytesIO(pdf)) as d:
        pages=[p.extract_text() or '' for p in d.pages]
        words=d.pages[1].extract_words() if len(pages)==9 else []
    if len(pages)!=9 or any(not p.strip() for p in pages):raise ValueError('Cambió la estructura de nueve páginas BCMM')
    pub=B._extract_pub_date(pages[0]);ref=B._extract_data_month(pages[0]);bulletin=B._extract_bulletin_number(pages[0])
    if not pub or not ref or not bulletin or date(*pub)>date.today() or tuple(ref)>=tuple(pub[:2]):raise ValueError('Fechas o edición inválidas')
    for n,p in enumerate(pages,1):
        if 'MERCANCÍAS DE MÉXICO (BCMM)' not in p or f'Página {n}/9' not in p or B._extract_pub_date(p)!=pub or B._extract_bulletin_number(p)!=bulletin:raise ValueError('Páginas de distinta edición')
    y,mo=ref;month=B.MESES_NOMBRE[mo-1];ym=f'{y}-{mo:02d}'
    block=pages[0].split('Cuadro 1',1)[1].split('Nota:',1)[0]
    if f'a {month} de {y}1/' not in block or f'Enero-{month} de {y}' not in block or 'I. CIFRAS ORIGINALES' not in pages[0] or '1/ Cifras oportunas' not in pages[0] or 'S.S. Sin significado' not in pages[0]:raise ValueError('Cambió referencia, acumulado o estatus')
    pattern=r'^(.+?)\s+('+NUM+r')\s+('+PCT+r')\s+('+NUM+r')\s+('+PCT+r')\s*$'
    ms=list(re.finditer(pattern,block,re.M))
    if len(ms)!=len(IDS):raise ValueError('Número de filas originales cambió')
    rows=[]
    for m,label,ident in zip(ms,LABELS,IDS):
        if m[1]!=label:raise ValueError('Identidad o jerarquía original incompatible')
        rows.append(dict(id=ident,label=label,amount=value(m[2]),yoy=value(m[3]),ytd=value(m[4]),ytd_yoy=value(m[5]),location='p. 1, cuadro 1',series='original',evidence=m[0]))
    if any(r['amount']<0 or r['ytd']<0 or r['yoy'] is None or r['ytd_yoy'] is None for r in rows if r['id']!='balance'):raise ValueError('Flujo nominal o tasa inválidos')
    h,head=history_rows(words,y)
    if any(v<0 for r in h if not r['id'].startswith('balance') for v in r['values']):raise ValueError('Flujo histórico negativo')
    expected_head=[B.MESES_NOMBRE[(mo-3+k)%12][:3]+'.'+('1/' if k==2 else '') for k in range(3)]
    if head[:3]!=expected_head:raise ValueError('Orden de meses históricos cambió')
    if head[-1]!='ene.-'+month[:3]+'.1/' or head[-2]!=month[:3]+'.1/':raise ValueError('Referencia histórica distinta del cuadro 1')
    market=pages[2].split('Cuadro 3',1)[1].split('1/ Cifras',1)[0]
    if f'a {month} de {y}' not in market or 'Exportaciones no petroleras' not in market or f'{y-1} {y}' not in flat(market):raise ValueError('Cobertura o periodo de mercados cambió')
    ms=list(re.finditer(r'^(.+?)\s+(\d+\.\d{2})\s+(-?\d+\.\d)\s+(-?\d+\.\d)\s+(-?\d+\.\d)\s+(-?\d+\.\d)\s+(-?\d+\.\d)\s*$',market,re.M))
    if len(ms)!=7:raise ValueError('Número de mercados distinto')
    markets=[]
    for m,label,ident in zip(ms,MARKET_LABELS,MARKET_IDS):
        if m[1]!=label:raise ValueError('Orden de mercados cambió')
        markets.append(dict(id=ident,label=label,share=float(m[2]),values=list(map(float,m.group(3,4,5,6,7))),location='p. 3, cuadro 3',series='original',evidence=m[0]))
    if markets[0]['share']!=100 or any(not 0<=r['share']<=100 for r in markets):raise ValueError('Participaciones fuera de dominio')
    rates,balances,prevmonth=adjusted(pages)
    if prevmonth!=B.MESES_NOMBRE[(mo-2)%12] or 'II. CIFRAS DESESTACIONALIZADAS' not in pages[4]:raise ValueError('Comparación ajustada o serie incompatibles')
    method=flat(pages[8])
    if 'X-13ARIMA-SEATS' not in method or 'Pedimento aduanal' not in method or 'registros administrativos' not in method or 'Periodicidad Mensual' not in method:raise ValueError('Revisar metodología BCMM')
    f=dict(indicator=key,ym=ym,period=inegi.ym_to_label(ym,8),publication_date='%04d-%02d-%02d'%tuple(pub),bulletin=bulletin,rows=rows,history=h,markets=markets,adjusted=rates,balances=balances,pages=pages,source_sha256=hashlib.sha256(pdf).hexdigest())
    for field in ['amount','ytd']:
        if not close(row(f,'exports')[field]-row(f,'imports')[field],row(f,'balance')[field]):raise ValueError('Saldo distinto de exportaciones menos importaciones')
        for total,children in [('exports',['exports_oil','exports_non_oil']),('exports_non_oil',['agriculture','extractive','manufacturing']),('manufacturing',['automotive','non_automotive']),('imports',['imports_oil','imports_non_oil']),('imports',['consumption','intermediate','capital']),('consumption',['consumption_oil','consumption_non_oil']),('intermediate',['intermediate_oil','intermediate_non_oil'])]:
            if not close(row(f,total)[field],sum(row(f,c)[field] for c in children)):raise ValueError('Desglose incompatible: '+total)
    for ident in HISTORY_IDS[:7]:
        r=row(f,ident);hh=history(f,ident)
        if not close(r['amount'],hh['values'][4],.51) or not close(r['ytd'],hh['values'][5],.51):raise ValueError('Cuadros 1 y 2 incompatibles')
    for k in range(6):
        for suffix in ['', '_oil','_non_oil']:
            if not close(history(f,'exports'+suffix)['values'][k]-history(f,'imports'+suffix)['values'][k],history(f,'balance'+suffix)['values'][k],2):raise ValueError('Saldo histórico incompatible')
    for total,children in [('total',['usa','rest']),('usa',['usa_auto','usa_other']),('rest',['rest_auto','rest_other'])]:
        if not close(next(r for r in markets if r['id']==total)['share'],sum(r['share'] for r in markets if r['id'] in children),.02):raise ValueError('Participaciones de mercados incompatibles')
    if markets[0]['values'][-2:]!=[row(f,'exports_non_oil')['yoy'],row(f,'exports_non_oil')['ytd_yoy']]:raise ValueError('Mercados y exportaciones no petroleras no coinciden')
    cover=pages[0].split('Aumentaron las exportaciones',1)[0].split('Disminuyeron las exportaciones',1)[0]
    m=re.search(r'\n(-?\d{1,3}(?: \d{3})*)\s+(\d{1,3}(?: \d{3})*)\s+[▲▼]?\s*(-?\d+\.\d) %\s+(\d{1,3}(?: \d{3})*)\s+[▲▼]?\s*(-?\d+\.\d) %',cover)
    if not m or not close(int(m[1].replace(' ','')),row(f,'balance')['amount'],.51) or not close(int(m[2].replace(' ','')),row(f,'exports')['amount'],.51) or not close(int(m[4].replace(' ','')),row(f,'imports')['amount'],.51) or [float(m[3]),float(m[5])]!=[row(f,'exports')['yoy'],row(f,'imports')['yoy']]:raise ValueError('Portada y cuadro 1 incompatibles')
    return f
