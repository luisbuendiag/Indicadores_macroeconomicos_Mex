"""Ediciones completas de consumo e inversión: tasas reales y series separadas."""
import hashlib,io,re
from datetime import date
import pdfplumber
from sources import inegi_bulletin as B,inegi

NAMES={'CONSUMO':'IMCP','IMFBCF':'IMFBCF'}
PRODUCTS={'CONSUMO':('imcp','imcpmi'),'IMFBCF':('ifb','imfbcf')}
# IDs jerárquicos: nunca confundir filas repetidas de bienes u origen.
CONSUMO=[('total','Consumo privado','Consumo privado'),('nacional','Nacional','Nacional'),('nacional_bienes','Bienes','Bienes nacionales'),('nacional_servicios','Servicios','Servicios nacionales'),('importado','Importado','Bienes importados'),('importado_bienes','Bienes','Bienes importados (detalle)')]
INV=[('total','Formación bruta de capital fijo','Inversión fija total'),('construccion','Construcción','Construcción'),('residencial','Residencial','Residencial'),('no_residencial','No residencial','No residencial'),('maquinaria','Maquinaria y equipo','Maquinaria y equipo'),('nacional','Nacional','Maquinaria y equipo nacional'),('nacional_transporte','Equipo de transporte','Transporte nacional'),('nacional_otros','Maquinaria, equipo y otros bienes','Otra maquinaria nacional'),('importado','Importado','Maquinaria y equipo importado'),('importado_transporte','Equipo de transporte','Transporte importado'),('importado_otros','Maquinaria, equipo y otros bienes','Otra maquinaria importada')]
ORIG_CONSUMO=CONSUMO[:3]+[('nacional_duradero','Duradero','Duraderos nacionales'),('nacional_semi','Semi duradero','Semiduraderos nacionales'),('nacional_no','No duradero','No duraderos nacionales')]+CONSUMO[3:]+[('importado_duradero','Duradero','Duraderos importados'),('importado_semi','Semi duradero','Semiduraderos importados'),('importado_no','No duradero','No duraderos importados')]
BUYERS=[]
for ident,name,short in [INV[0],INV[1],INV[4]]:
    BUYERS.extend([(ident+'_comprador',name,short),(ident+'_privada','Privada',short+' privada'),(ident+'_publica','Pública',short+' pública')])


def read_rows(text,spec,fields,page):
    matches=list(re.finditer(r'^([^\n]+?)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s*$',text,re.M))
    if len(matches)!=len(spec):raise ValueError('Cambió el número de filas del cuadro')
    rows=[]
    for m,(ident,label,display) in zip(matches,spec):
        actual=re.sub(r'\d+/\s*$','',m[1]).strip()
        if actual!=label:raise ValueError('Cambió el orden o identidad de la fila: '+ident)
        vals=[float(m[2]),float(m[3])]
        if any(v < -100 for v in vals):raise ValueError('Variación real imposible')
        rows.append(dict(id=ident,label=display,**dict(zip(fields,vals)),series='desestacionalizada' if fields[0]=='mom' else 'original',location=f'p. {page}, cuadro {page-1}',evidence=m[0]))
    return rows


def extract(pdf,key):
    if key not in NAMES:raise ValueError('Indicador no soportado')
    alias=NAMES[key]
    with pdfplumber.open(io.BytesIO(pdf)) as doc:pages=[p.extract_text() or '' for p in doc.pages]
    if len(pages)!=4 or any(not p.strip() for p in pages):raise ValueError('Cambió la estructura del boletín')
    pub=B._extract_pub_date(pages[0]);ref=B._extract_data_month(pages[0]);bulletin=B._extract_bulletin_number(pages[0])
    if not pub or not ref or not bulletin or date(*pub)>date.today() or tuple(ref)>=tuple(pub[:2]):raise ValueError('Fechas incompatibles')
    for i,p in enumerate(pages):
        if '('+alias+')' not in p or f'Página {i+1}/4' not in p or B._extract_bulletin_number(p)!=bulletin or B._extract_pub_date(p)!=pub:raise ValueError('Páginas de distinta edición o producto')
    if 'FICHA METODOLÓGICA' not in pages[3] or 'volumen' not in pages[3] or 'X-13ARIMA-SEATS' not in pages[3]:raise ValueError('Revisar la metodología de la nueva edición')
    base=re.search(r'índice\s+(\d{4})=100',pages[0])
    if not base:raise ValueError('Base ausente')
    methodbase=re.search(r'base fija (?:en el año|en)\s+(\d{4})',pages[3])
    if not methodbase or methodbase[1]!=base[1]:raise ValueError('Base incompatible con metodología')
    adjusted=pages[1].split('Cuadro 1',1)[1].split('Nota:',1)[0]
    original=pages[2].split('Cuadro 2',1)[1].split('1/ Cifras',1)[0]
    period=f'{B.MESES_NOMBRE[ref[1]-1]} de {ref[0]}'
    for block in [adjusted,original]:
        if period not in re.sub(r'\s+',' ',block):raise ValueError('Periodo distinto entre cuadros')
    if 'cifras desestacionalizadas' not in adjusted or 'CIFRAS ORIGINALES' not in pages[2] or 'Cifras preliminares' not in pages[2] or 'independiente' not in pages[1]:raise ValueError('Cambió serie, estatus o ajuste independiente')
    rows=read_rows(adjusted,CONSUMO if key=='CONSUMO' else INV,('mom','yoy'),2)
    originals=read_rows(original,ORIG_CONSUMO if key=='CONSUMO' else INV+BUYERS,('original','ytd'),3)
    if key=='CONSUMO':
        if 'Compras netas de residentes' not in original or not re.search(r'NA\s+NA',original):raise ValueError('Revisar las compras netas de residentes')
        for group,ids,fields in [(rows,['importado','importado_bienes'],['mom','yoy']),(originals,['importado','importado_bienes'],['original','ytd'])]:
            pair=[next(r for r in group if r['id']==i) for i in ids]
            if any(pair[0][field]!=pair[1][field] for field in fields):raise ValueError('Desglose importado incompatible')
    else:
        for ident in ['total','construccion','maquinaria']:
            a=next(r for r in originals if r['id']==ident);b=next(r for r in originals if r['id']==ident+'_comprador')
            if (a['original'],a['ytd'])!=(b['original'],b['ytd']):raise ValueError('Totales incompatibles entre cuadros de inversión')
    cover=re.search(r'\n(\d+\.\d+)\s*[▲▼]?\s*(-?\d+\.\d+)\s*%\s*[▲▼]?\s*(-?\d+\.\d+)\s*%',pages[0])
    if not cover or (float(cover[2]),float(cover[3]))!=(rows[0]['mom'],rows[0]['yoy']):raise ValueError('Portada y cuadro ajustado incompatibles')
    ym=f'{ref[0]:04d}-{ref[1]:02d}'
    return dict(indicator=key,ym=ym,period=inegi.ym_to_label(ym,8),publication_date=f'{pub[0]:04d}-{pub[1]:02d}-{pub[2]:02d}',bulletin=bulletin,base=base[1],index=float(cover[1]),rows=rows,originals=originals,pages=pages,source_sha256=hashlib.sha256(pdf).hexdigest(),cover_evidence=cover[0])
