"""Notas IMCP e IMFBCF: originales, ajustadas y acumulados sin mezclar."""
from notas_layout import Layout
from notas_imoam import period_text

CORE={'CONSUMO':['total','nacional','nacional_bienes','nacional_servicios','importado'],
      'IMFBCF':['total','construccion','residencial','no_residencial','maquinaria','nacional','importado']}
SHORT={'nacional':'Nacional','importado':'Importado'}
def row(f,ident,original=False):return next(r for r in f['originals' if original else 'rows'] if r['id']==ident)
def label(f,r):
    if f['indicator']=='IMFBCF' and r['id'] in ('nacional','importado'):return 'Equipo '+SHORT[r['id']].lower()
    return r['label']

def hero(f):
    r=f['rows'][0];alias='IMCP' if f['indicator']=='CONSUMO' else 'IMFBCF'
    return [[alias+' · '+period_text(f['ym']).capitalize(),'Publicación '+f['publication_date']],
            [f'Índice ajustado {f["index"]:.1f}',f'Mensual {r["mom"]:.1f}% | Anual {r["yoy"]:.1f}%']]

def tables(f):
    key=f['indicator'];parts=[row(f,i) for i in CORE[key]]
    adjusted=[['Componente','Mensual (%)','Anual (%)']]+[[label(f,r),f'{r["mom"]:.1f}',f'{r["yoy"]:.1f}'] for r in parts]
    originals=[r for r in f['originals'] if r['id']!='importado_bienes'] if key=='CONSUMO' else [row(f,i,True) for i in CORE[key]]
    original=[['Componente','Anual original (%)','Enero–mes (%)']]+[[label(f,r),f'{r["original"]:.1f}',f'{r["ytd"]:.1f}'] for r in originals]
    data=[hero(f),adjusted,original]
    if key=='IMFBCF':
        data.append([['Comprador del total','Anual original (%)','Enero–mes (%)']]+[[t,f'{row(f,"total_"+i,True)["original"]:.1f}',f'{row(f,"total_"+i,True)["ytd"]:.1f}'] for i,t in [('privada','Privado'),('publica','Público')]])
    return data

def build(f,url,template,out):
    x=Layout(template,out);key=f['indicator'];data=tables(f);total=f['rows'][0];orig=row(f,'total',True)
    title='Consumo privado' if key=='CONSUMO' else 'Formación bruta de capital fijo'
    x.table(data[0],True);x.p(title,bold=True,color='10312B');x.note('Índice '+f['base']+'=100. Variaciones reales; edición del boletín, sujeta a revisión.')
    x.h('Resumen ejecutivo')
    if key=='CONSUMO':
        verb='no cambió respecto al mes previo' if total['mom']==0 else f'varió {total["mom"]:.1f}% respecto al mes previo'
        x.p(f'En {period_text(f["ym"])}, el consumo privado {verb}; en la comparación anual registró {total["yoy"]:.1f}%, con cifras desestacionalizadas.',gray=True)
        leaves=[row(f,i) for i in ['nacional_bienes','nacional_servicios','importado']]
        best=max(leaves,key=lambda r:r['mom']);worst=min(leaves,key=lambda r:r['mom'])
        x.bullet(f'Mayor variación mensual entre bienes nacionales, servicios nacionales y bienes importados: {best["label"].lower()}, con {best["mom"]:.1f}%.',True)
        x.bullet(f'Menor variación mensual en esos tres componentes: {worst["label"].lower()}, con {worst["mom"]:.1f}%. El conjunto nacional varió {row(f,"nacional")["mom"]:.1f}%.',True)
    else:
        x.p(f'En {period_text(f["ym"])}, la inversión fija registró {total["mom"]:.1f}% mensual y {total["yoy"]:.1f}% anual, en términos reales y con cifras desestacionalizadas.',gray=True)
        x.bullet(f'Maquinaria y equipo varió {row(f,"maquinaria")["mom"]:.1f}% mensual: el componente importado registró {row(f,"importado")["mom"]:.1f}% y el nacional, {row(f,"nacional")["mom"]:.1f}%.',True)
        x.bullet(f'Construcción varió {row(f,"construccion")["mom"]:.1f}% mensual; residencial, {row(f,"residencial")["mom"]:.1f}%, y no residencial, {row(f,"no_residencial")["mom"]:.1f}%.',True)
    x.h('Comparación mensual y anual ajustada');x.table(data[1]);x.note('Fuente: INEGI, cuadro 1, p. 2. Ambas tasas desestacionalizadas. Las filas son agregados y desgloses, no sumandos de tasas.')
    if key=='CONSUMO':ids=['nacional_bienes','nacional_servicios','importado'];labels=['Bienes nacionales','Servicios nacionales','Bienes importados']
    else:ids=['residencial','no_residencial','nacional','importado'];labels=['Construcción residencial','Construcción no residencial','Equipo nacional','Equipo importado']
    x.bars('mensual',labels,[row(f,i)['mom'] for i in ids],'Contrastes en la variación mensual','Variación real mensual (%) · cifras desestacionalizadas')
    x.h('Balance del año')
    x.p(f'En cifras originales, el total registró {orig["original"]:.1f}% anual y {orig["ytd"]:.1f}% en enero al mes de referencia respecto al mismo intervalo del año anterior.')
    x.note('El acumulado es una tasa publicada por el INEGI; no se obtiene promediando tasas mensuales. Las tasas originales y ajustadas pueden diferir.')
    x.doc.add_page_break();x.h('Cifras originales y acumulado');x.table(data[2]);x.note('Fuente: INEGI, cuadro 2, p. 3. Cifras preliminares; anual contra el mismo mes del año anterior y acumulado contra enero al mismo mes del año anterior.')
    if key=='CONSUMO':
        x.h('Durabilidad y origen de los bienes')
        ids=['duradero','semi','no']
        x.bars('acumulado',['Duraderos','Semiduraderos','No duraderos'],[row(f,'nacional_'+i,True)['ytd'] for i in ids],
               'Acumulado por durabilidad de los bienes','Variación real enero–mes (%) · cifras originales',
               [row(f,'importado_'+i,True)['ytd'] for i in ids],
               'Verde: nacionales. Dorado: importados. Fuente: cuadro 2. Las categorías de durabilidad desglosan bienes; no incluyen servicios.')
        x.h('Notas metodológicas')
        x.p('El IMCP mide el gasto de los hogares en bienes y servicios nacionales e importados. El consumo de bienes importados no equivale a producción nacional ni a ventas minoristas.')
        x.note('El total incluye compras netas de residentes y no residentes. En el cuadro original estas compras presentan NA: no aplica; no se sustituyen por cero. Los agregados ajustados se calculan de forma independiente a sus componentes. No se infieren causas ni cambios en bienestar.')
    else:
        x.h('Inversión por comprador');x.table(data[3]);x.note('Fuente: cuadro 2, tipo de bien y comprador. Cifras originales preliminares. El comprador público o privado se identifica explícitamente en el boletín.')
        ids=['total','construccion','maquinaria']
        x.bars('comprador',['Total','Construcción','Maquinaria y equipo'],[row(f,i+'_privada',True)['ytd'] for i in ids],
               'Acumulado según tipo de comprador','Variación real enero–mes (%) · cifras originales',
               [row(f,i+'_publica',True)['ytd'] for i in ids],
               'Verde: privado. Dorado: público. Fuente: cuadro 2. Tasas de cada agregado; no son participaciones ni contribuciones al total.')
        x.h('Notas metodológicas')
        x.p('El IMFBCF mide inversión en activos fijos utilizados continuamente durante más de un año. No representa IED, anuncios de inversión ni ejecución presupuestaria.')
        x.note('Equipo nacional e importado se refieren a maquinaria y equipo. Los agregados ajustados se calculan de manera independiente a sus componentes. Los cuadros originales también desglosan transporte y otra maquinaria; la evidencia conserva todas sus filas. No se atribuyen causas sin evidencia.')
    x.p('',6.5);x.note(f'INEGI, boletín {f["bulletin"]}, publicado el {f["publication_date"]}. Resultados y cuadros: pp. 1–3; metodología: p. 4. Cifras sujetas a revisión.');x.note(url)
    x.save(title+' · '+f['period'])

def validate(f,doc):
    expected=tables(f)
    if len(doc.tables)!=len(expected) or len(doc.inline_shapes)!=2:raise ValueError('Faltan tablas o visuales')
    for actual,wanted in zip(doc.tables,expected):
        if [[c.text for c in r.cells] for r in actual.rows]!=wanted:raise ValueError('Cuadro Word incompatible con el boletín')
