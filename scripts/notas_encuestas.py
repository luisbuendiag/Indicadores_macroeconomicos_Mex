"""Cuadros completos de EMIM y confianza EMOE; sin inferir series históricas."""
import hashlib,io,re
from datetime import date
import pdfplumber
from sources import inegi_bulletin as B,inegi
NAMES={'EMIM':'Encuesta Mensual de la Industria Manufacturera','EMOE':'Indicadores de Confianza Empresarial'}
PRODUCTS={'EMIM':'emim','EMOE':'ice'}
NUM=r'-?\d+\.\d+'
METRICS=['Producción','Personal ocupado','Horas trabajadas','Remuneraciones medias reales']
SECTORS={'311':'Alimentos','312':'Bebidas y tabaco','313':'Insumos textiles','314':'Productos textiles','315':'Prendas de vestir','316':'Cuero y piel','321':'Madera','322':'Papel','323':'Impresión','324':'Petróleo y carbón','325':'Química','326':'Plástico y hule','327':'Minerales no metálicos','331':'Metálicas básicas','332':'Productos metálicos','333':'Maquinaria y equipo','334':'Computación y electrónica','335':'Equipo eléctrico','336':'Equipo de transporte','337':'Muebles','339':'Otras manufacturas'}
COMPONENTS=['Momento para invertir','Situación presente del país','Situación futura del país','Situación presente de la empresa','Situación futura de la empresa']
def numbers(text,count):
    vals=[float(v) for v in re.findall(NUM,text)]
    if len(vals)!=count:raise ValueError('Cambió el número de columnas del cuadro')
    return vals

def extract(pdf,key):
    if key not in NAMES:raise ValueError('Producto no soportado')
    with pdfplumber.open(io.BytesIO(pdf)) as doc:pages=[p.extract_text() or '' for p in doc.pages]
    if len(pages)!=(5 if key=='EMIM' else 7) or any(not p.strip() for p in pages):raise ValueError('Cambió la estructura del boletín')
    if '('+key+')' not in pages[0]:raise ValueError('Producto incorrecto')
    pub=B._extract_pub_date(pages[0]);ref=B._extract_data_month(pages[0])
    if not pub or not ref or date(*pub)>date.today() or tuple(ref)>=tuple(pub[:2]):raise ValueError('Fechas incompatibles')
    ym=f'{ref[0]:04d}-{ref[1]:02d}'
    f=dict(indicator=key,ym=ym,period=inegi.ym_to_label(ym,8),publication_date=f'{pub[0]:04d}-{pub[1]:02d}-{pub[2]:02d}',bulletin=B._extract_bulletin_number(pages[0]),pages=pages,source_sha256=hashlib.sha256(pdf).hexdigest())
    if key=='EMIM':
        if 'CIFRAS ORIGINALES' not in pages[3] or 'Cifras preliminares' not in pages[3] or 'independiente' not in pages[2]:raise ValueError('Cambió el tipo de serie o estatus')
        table=pages[2].split('Cuadro 1',1)[1].split('Nota:',1)[0]
        if 'cifras desestacionalizadas' not in table:raise ValueError('Falta serie ajustada')
        labels=['Volumen físico de la producción','Personal ocupado total','Horas trabajadas por el personal ocupado total','Remuneraciones medias reales pagadas']
        rows=[]
        for label,short in zip(labels,METRICS):
            m=re.search(re.escape(label)+r'\s+('+NUM+r')\s+('+NUM+r')',table)
            if not m:raise ValueError('Fila EMIM ausente: '+label)
            rows.append(dict(label=short,mom=float(m[1]),yoy=float(m[2]),series='desestacionalizada',evidence=m[0],location='p. 3, cuadro 1'))
        text=pages[3].split('31-33 Industrias manufactureras',1)[1].split('1/ Cifras',1)[0]
        starts=list(re.finditer(r'(?m)^(3\d{2})\s',text));total=text[:starts[0].start()]
        vals=numbers(total,8)
        for i,r in enumerate(rows):r.update(index=vals[i*2],original=vals[i*2+1])
        sectors=[]
        for i,m in enumerate(starts):
            code=m[1];block=text[m.end():starts[i+1].start() if i+1<len(starts) else len(text)]
            vals=numbers(block,8)
            if code not in SECTORS:raise ValueError('Cambió el universo de subsectores')
            sectors.append(dict(code=code,label=SECTORS[code],production=vals[1],employment=vals[3],hours=vals[5],pay=vals[7],evidence=block,series='original',location='p. 4, cuadro 2'))
        if [r['code'] for r in sectors]!=list(SECTORS):raise ValueError('Universo sectorial incompleto o duplicado')
        base=re.search(r'índice\s+(\d{4})=100',pages[3])
        if not base:raise ValueError('Base ausente')
        f.update(rows=rows,sectors=sectors,base=base[1],total_evidence=total)
    else:
        if 'centrado en 50' not in pages[6] or 'promedio ponderado' not in re.sub(r'\s+',' ',pages[0]):raise ValueError('Cambió la metodología de confianza')
        m=re.search('('+NUM+r')\s*puntos\s*[▲▼]?\s*('+NUM+r')\s*puntos\s*[▲▼]?\s*('+NUM+r')\s*puntos',pages[0])
        if not m:raise ValueError('IGOEC ausente')
        globalrow=dict(label='IGOEC',level=float(m[1]),mom=float(m[2]),yoy=float(m[3]),series='desestacionalizada',location='p. 1',evidence=m[0])
        rows=[];components=[]
        for page,tableid,label,series in [(1,1,'Manufacturas','desestacionalizada'),(2,2,'Construcción','original'),(3,3,'Comercio','original'),(3,4,'Servicios no financieros','original')]:
            block=pages[page].split('Cuadro '+str(tableid),1)[1]
            # Cada cuadro tiene exactamente seis filas: ICE y cinco componentes.
            block=block.split('Fuente:',1)[0]
            if 'cifras '+('desestacionalizadas' if series=='desestacionalizada' else 'originales') not in block:raise ValueError('Cambió el ajuste estacional sectorial')
            if tableid==1 and 'Componente no sujeto a desestacionalización' not in block:raise ValueError('Revisar ajuste de componentes manufactureros')
            if tableid==2 and 'Componente ajustado por efecto estacional' not in block:raise ValueError('Revisar ajuste del componente de inversión')
            if re.findall(r'(?m)^([a-e])\)',block)!=list('abcde'):raise ValueError('Cambió el orden de componentes de confianza')
            matches=list(re.finditer('('+NUM+r')\s+('+NUM+r')\s+('+NUM+r')\s+(\d+)\s+por\s+(arriba|debajo)',block))
            if len(matches)!=6:raise ValueError('Cuadro de confianza incompleto')
            for i,m in enumerate(matches):
                row=dict(label=label if i==0 else COMPONENTS[i-1],sector=label,level=float(m[1]),mom=float(m[2]),yoy=float(m[3]),months=int(m[4]),side=m[5],series=series,location=f'p. {page+1}, cuadro {tableid}',evidence=m[0])
                if i and tableid==1 and i>=3:row['series']='original'
                if i==1 and tableid==2:row['series']='desestacionalizada'
                if not 0<=row['level']<=100 or (row['level']>50)!=(row['side']=='arriba'):raise ValueError('Umbral incompatible')
                (rows if i==0 else components).append(row)
        f.update(rows=rows,components=components,globalrow=globalrow)
    return f
