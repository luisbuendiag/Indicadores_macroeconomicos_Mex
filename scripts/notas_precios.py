"""Precios publicados: variaciones e incidencias conservan sus unidades."""
import hashlib,io,re
from datetime import date
import pdfplumber
from sources import inegi_bulletin as B,inegi
NAMES={'INPC':6,'INPP':8}
CP=[('total','INPC','General'),('subyacente','Subyacente','Subyacente'),('mercancias','Mercancías','Mercancías'),('alimentos','Alimentos, bebidas y tabaco','Alimentos procesados'),('no_alimentos','Mercancías no alimenticias','Mercancías no alimenticias'),('servicios','Servicios','Servicios'),('vivienda','Vivienda','Vivienda'),('educacion','Educación (colegiaturas)','Educación'),('otros_servicios','Otros servicios','Otros servicios'),('no_subyacente','No subyacente','No subyacente'),('agro','Agropecuarios','Agropecuarios'),('frutas','Frutas y verduras','Frutas y verduras'),('pecuarios','Pecuarios','Pecuarios'),('energia_tarifas','Energéticos y tarifas autorizadas por','Energéticos y tarifas'),('energia','Energéticos','Energéticos'),('tarifas','Tarifas autorizadas por el gobierno','Tarifas autorizadas')]
PP=[('total','Índice Nacional de Precios Productor','Total'),('primarias','Actividades primarias','Primarias'),('secundarias','Actividades secundarias','Secundarias'),('mineria','Minería','Minería'),('energia','energía eléctrica, suministro de agua y de gas natural por','Energía, agua y gas'),('construccion','Construcción','Construcción'),('manufacturas','Industrias manufactureras','Manufacturas'),('terciarias','Actividades terciarias','Terciarias')]
NUM=r'-?\d+\.\d+'

def vectors(text,count):
    pat=r'(?<![\d.])'+r'\s+'.join(['('+NUM+r')']*count)+r'(?![\d.])'
    return list(re.finditer(pat,text))

def rows(text,spec,count,fields,location):
    matches=vectors(text,count)
    if len(matches)!=len(spec):raise ValueError('Cambió el número de filas o columnas')
    result=[];last=0
    for m,(ident,prefix,label) in zip(matches,spec):
        before=re.sub(r'\s+',' ',text[last:m.start()]).strip()
        if not re.search(re.escape(prefix)+r'(?:\d+/)?$',before):raise ValueError('Fila fuera de orden: '+ident)
        vals=[float(v) for v in m.groups()]
        result.append(dict(id=ident,label=label,**{field:vals[i] for field,i in fields.items()},values=vals,location=location,evidence=before+' '+m[0]))
        last=m.end()
    return result

def generics(page,key):
    result=[];expected=10 if key=='INPC' else 15
    foot=[w['top'] for w in page.extract_words() if w['text']=='1/']
    for side,(left,right) in enumerate([(0,page.width/2),(page.width/2,page.width)]):
        words=page.crop((left,0,right,page.height)).extract_words()
        if not foot:raise ValueError('Falta nota de incidencia')
        words=[w for w in words if w['top']<min(foot)]
        nums=[w for w in words if re.fullmatch(NUM,w['text'])]
        if len(nums)!=expected*2:raise ValueError('Cambió el cuadro de genéricos')
        pairs=[nums[i:i+2] for i in range(0,len(nums),2)]
        for i,(a,b) in enumerate(pairs):
            if abs(a['top']-b['top'])>3:raise ValueError('Genérico ambiguo')
            y=a['top'];lo=(pairs[i-1][0]['top']+y)/2 if i else y-8;hi=(pairs[i+1][0]['top']+y)/2 if i+1<len(pairs) else y+9
            label=' '.join(w['text'] for w in words if lo<=w['top']<hi and w['x1']<a['x0']-2)
            v,inc=float(a['text']),float(b['text'])
            if not label or 'mensual' in label.lower() or (side==0 and (v<0 or inc<0)) or (side==1 and (v>0 or inc>0)):raise ValueError('Etiqueta o signo de genérico incompatible')
            result.append(dict(id=f'generico_{side}_{i}',label=label,mom=v,incidence=inc,location='p. 4, cuadro 2' if key=='INPC' else 'p. 5, cuadro 3'))
    return result

def extract(pdf,key):
    if key not in NAMES:raise ValueError('Producto no soportado')
    with pdfplumber.open(io.BytesIO(pdf)) as d:
        pages=[p.extract_text() or '' for p in d.pages]
        if len(pages)!=NAMES[key] or any(not p.strip() for p in pages):raise ValueError('Cambió la estructura del boletín')
        products=generics(d.pages[3 if key=='INPC' else 4],key)
    pub=B._extract_pub_date(pages[0]);ref=B._extract_data_month(pages[0]);number=B._extract_bulletin_number(pages[0])
    if not pub or not ref or not number or date(*pub)>date.today() or tuple(ref)>=tuple(pub[:2]):raise ValueError('Fechas incompatibles')
    for i,p in enumerate(pages):
        if '('+key+')' not in p or f'Página {i+1}/{len(pages)}' not in p or B._extract_bulletin_number(p)!=number or B._extract_pub_date(p)!=pub:raise ValueError('Páginas de distinta edición')
    month=B.MESES_NOMBRE[ref[1]-1];y=ref[0]
    if 'FICHA METODOLÓGICA' not in pages[-1] or 'Laspeyres' not in pages[-1]:raise ValueError('Revisar metodología')
    cover=re.search(r'\n[▲▼]?\s*('+NUM+r')\s*%\s*[▲▼]?\s*('+NUM+r')\s*%\s*[▲▼]?\s*('+NUM+r')\s*%\s*[▲▼]?\s*('+NUM+r')\s*%\s*[▲▼]?\s*('+NUM+r')\s*%\s*[▲▼]?\s*('+NUM+r')\s*%',pages[0])
    if not cover:raise ValueError('Portada no legible')
    covervals=[float(v) for v in cover.groups()]
    if key=='INPC':
        block=pages[1].split('Cuadro 1',1)[1].split('1/ La incidencia',1)[0]
        if month+' de los años' not in block:raise ValueError('Periodo del cuadro incompatible')
        years=[int(v) for v in re.findall(r'\b20\d{2}\b',block)]
        if years!=[y-2,y-1,y]*3+[y-1,y] or 'mensual anual mensual anual' not in re.sub(r'\s+',' ',block):raise ValueError('Revisar columnas del cuadro INPC')
        data=rows(block,CP,11,dict(mom=2,yoy=5,prior_yoy=4,incidence=8,annual_incidence=10),'p. 2, cuadro 1')
        index=re.search(r'nivel de\s+('+NUM+r')\s+puntos',pages[0])
        base=re.search(r'(Segunda quincena de julio de \d{4}=100)',pages[-1])
        if not index or not base or 'Próxima publicación mensual' not in pages[0]:raise ValueError('No es el boletín mensual del INPC')
        headline=[next(r for r in data if r['id']==i) for i in ['total','subyacente','no_subyacente']]
        groups=[];destinations=[];index=float(index[1]);base=base[1]
    else:
        if 'incluido petróleo' not in pages[0] or 'preliminares' not in pages[-1] or 'cinco meses' not in pages[-1]:raise ValueError('Cambió cobertura o estatus del INPP')
        base=re.search(r'Periodo base de comparación\s+([A-Za-záéíóú]+ de \d{4}=100)',pages[-1])
        if not base:raise ValueError('Base del INPP ausente')
        base=base[1];index=None;groups=[]
        for page,num,spec in [(1,1,PP),(4,4,[('total','Mercancías y servicios de uso intermedio','Uso intermedio')]+[r for r in PP[1:] if r[0]!='construccion']),(5,5,[('total','Mercancías y servicios finales','Finales')]+PP[1:])]:
            block=pages[page].split('Cuadro '+str(num),1)[1].split('Fuente:',1)[0]
            if month+' de los años' not in block:raise ValueError('Periodo del cuadro incompatible')
            years=[int(v) for v in re.findall(r'\b20\d{2}\b',block)]
            if years!=[y-2,y-1,y]*2 or 'incluido petróleo' not in block:raise ValueError('Revisar cobertura o columnas')
            rr=rows(block,spec,6,dict(mom=2,yoy=5,prior_yoy=4),f'p. {page+1}, cuadro {num}')
            groups.append(rr)
        data=groups[0];headline=[g[0] for g in groups]
        block=pages[6].split('Cuadro 6',1)[1].split('1/ La incidencia',1)[0]
        destinations=rows(block,[('finales','Mercancías y servicios finales','Finales'),('interna','Demanda interna','Demanda interna'),('consumo','Consumo','Consumo'),('capital','Formación de capital','Formación de capital'),('exportacion','Exportaciones','Exportaciones')],7,dict(mom=2,incidence=3,yoy=6),'p. 7, cuadro 6')
        if (destinations[0]['mom'],destinations[0]['yoy'])!=(headline[2]['mom'],headline[2]['yoy']):raise ValueError('Finales incompatibles entre cuadros')
    if covervals!=[v for r in headline for v in (r['mom'],r['yoy'])]:raise ValueError('Portada y cuadros incompatibles')
    ym=f'{y:04d}-{ref[1]:02d}'
    return dict(indicator=key,ym=ym,period=inegi.ym_to_label(ym,8),publication_date=f'{pub[0]:04d}-{pub[1]:02d}-{pub[2]:02d}',bulletin=number,base=base,index=index,rows=data,groups=groups,destinations=destinations,generics=products,pages=pages,source_sha256=hashlib.sha256(pdf).hexdigest())
