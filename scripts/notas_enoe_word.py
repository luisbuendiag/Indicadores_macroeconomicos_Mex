"""Nota ENOE con población, calidad laboral y ajuste estacional separados."""
from notas_layout import Layout
from notas_enoe import get,rate
from notas_imoam import period_text
POPS=[('pea','PEA'),('occupied','Población ocupada'),('unemployed','Población desocupada'),('pnea','PNEA'),('available','PNEA disponible')]
RATES=[('participation','Participación¹'),('unemployment','Desocupación²'),('underemployment','Subocupación³'),('informality','Informalidad laboral (TIL1)³'),('informal_sector','Sector informal (TOSI1)³'),('critical','Condiciones críticas³')]
ADJUSTED=RATES[:4]
def num(v):return f'{v:,}'.replace(',',' ')
def tables(f):
    y=int(f['ym'][:4]);u=rate(f,'unemployment');adj=rate(f,'unemployment',True)
    hero=[['ENOE · '+f['period'],'Publicación '+f['publication_date']],[f'Desocupación original {u["current"]:.1f}%',f'Desocupación ajustada {adj["current"]:.1f}%']]
    population=[['Población (personas)',str(y-1),str(y),'Cambio anual']]+[[label,num(get(f,i)['previous']),num(get(f,i)['current']),num(get(f,i)['difference'])] for i,label in POPS]
    original=[['Tasa original',str(y-1)+' (%)',str(y)+' (%)','Cambio (pp)']]+[[label,f'{rate(f,i)["previous"]:.1f}',f'{rate(f,i)["current"]:.1f}',f'{rate(f,i)["difference"]:+.1f}'] for i,label in RATES]
    adjusted=[['Tasa ajustada','Nivel (%)','Mensual (pp)','Anual (pp)']]+[[label,f'{rate(f,i,True)["current"]:.1f}',f'{rate(f,i,True)["mom"]:+.1f}',f'{rate(f,i,True)["yoy"]:+.1f}'] for i,label in ADJUSTED]
    return [hero,population,original,adjusted]

def build(f,url,template,out):
    x=Layout(template,out);data=tables(f);u=rate(f,'unemployment');p=rate(f,'participation');occ=get(f,'occupied');pea=get(f,'pea')
    x.table(data[0],True);x.p('Encuesta nacional de ocupación y empleo',bold=True,color='10312B')
    x.h('Resumen ejecutivo')
    x.p(f'En {period_text(f["ym"])}, la desocupación fue de {u["current"]:.1f}% de la PEA, con una diferencia anual oficial de {u["difference"]:+.1f} puntos porcentuales en cifras originales.',gray=True)
    x.bullet(f'La población ocupada fue de {num(occ["current"])} personas ({num(occ["difference"])} frente al mismo mes del año anterior). La PEA cambió en {num(pea["difference"])} personas y la participación, en {p["difference"]:+.1f} puntos porcentuales.',True)
    sub,inf=rate(f,'underemployment'),rate(f,'informality')
    x.bullet(f'La subocupación se situó en {sub["current"]:.1f}% y la informalidad laboral, en {inf["current"]:.1f}% de la población ocupada. Sus diferencias anuales fueron {sub["difference"]:+.1f} y {inf["difference"]:+.1f} puntos porcentuales, respectivamente.',True)
    x.h('Población y participación en el mercado laboral');x.table(data[1]);x.note('Cuadro 1, p. 4. Cifras originales para el mismo mes de ambos años. PEA: población económicamente activa; PNEA: no económicamente activa. La PNEA disponible no busca trabajo activamente y no forma parte de la desocupación.')
    x.bars('sexo',['Mujeres','Hombres'],[get(f,'occupied',g)['difference']/1000 for g in ['women','men']],'Cambio anual de la población ocupada por sexo','Miles de personas · cifras originales')
    x.p('La baja de la desocupación debe leerse junto con los cambios en ocupación y participación; por sí sola no acredita creación neta de empleo.')
    manuf=next(r for r in f['sectors'] if r['id']=='manufacturing');construction=next(r for r in f['sectors'] if r['id']=='construction')
    x.note(f'En el desglose sectorial original, manufacturas registró un cambio anual de {num(manuf["difference"])} personas ocupadas y construcción, de {num(construction["difference"])}. Fuente: cuadro 2, p. 6. La ENOE mide personas, no puestos afiliados al IMSS.')
    x.doc.add_page_break();x.h('Condiciones laborales en cifras originales');x.table(data[2]);x.note('Cuadro 4, p. 9. Denominadores: ¹ población de 15 años y más; ² PEA; ³ población ocupada. pp: puntos porcentuales. Se conservan las diferencias oficiales calculadas con todos los decimales, no por resta de las tasas redondeadas.')
    c,s=rate(f,'critical'),rate(f,'informal_sector')
    x.p(f'Las condiciones críticas de ocupación registraron {c["current"]:.1f}% ({c["difference"]:+.1f} pp anual). La ocupación en el sector informal fue {s["current"]:.1f}% ({s["difference"]:+.1f} pp); este concepto es distinto de la informalidad laboral total.')
    x.h('Cambios de corto plazo con ajuste estacional');x.table(data[3]);x.note('Cuadro 7, p. 12. Cobertura nacional. Mensual frente al mes previo; anual frente al mismo mes del año anterior. Los denominadores son los indicados arriba. No comparar estos niveles con los originales para inferir un cambio temporal.')
    x.bars('mensual',['Participación','Desocupación','Subocupación','Informalidad laboral'],[rate(f,i,True)['mom'] for i,_ in ADJUSTED],'Diferencias mensuales de las tasas ajustadas','Puntos porcentuales · cifras desestacionalizadas')
    x.h('Notas y fuente')
    x.note(f'Población de 15 años y más. ENOE mensual, nacional; cifras originales y ajustadas por separado. Las tasas no se suman ni comparten siempre denominador. Condiciones críticas e ingresos: salarios mínimos equivalentes, base enero de {f["wage_base"]}. Ajuste estacional: X-13ARIMA-SEATS. No se empalman series ENOE, ENOEN o ETOE ni se reconstruyen cifras históricas desde gráficas.')
    x.note(f'INEGI, boletín {f["bulletin"]}, {f["publication_date"]}. Población: cuadro 1; ocupación sectorial: cuadro 2; tasas: cuadros 4 y 7; metodología: p. 15.');x.note(url)
    x.save('ENOE '+f['period'])

def validate(f,doc):
    if len(doc.tables)!=4 or len(doc.inline_shapes)!=2:raise ValueError('Faltan tablas o gráficas ENOE')
    for actual,wanted in zip(doc.tables,tables(f)):
        if [[c.text for c in r.cells] for r in actual.rows]!=wanted:raise ValueError('Cuadro Word distinto al boletín ENOE')
