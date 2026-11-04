"""Notas ejecutivas trimestrales con tasas de la edición, sin ponderaciones inventadas."""
from notas_layout import Layout
from notas_pib import NAMES

def originals(f):return [next(r for r in f['originals'] if r['id']==i) for i in ['total','primarias','secundarias','terciarias']]
def selected(f):
    rows=[r for r in f['originals'] if r['id'] not in ['total','primarias','secundarias','terciarias']]
    return sorted(rows,key=lambda r:(-r['original'],r['id']))[:3]+sorted(rows,key=lambda r:(r['original'],r['id']))[:3]
def tables(f):
    t=f['rows'][0]
    return [
      [[NAMES[f['indicator']]+' · '+f['period'],'Publicación '+f['publication_date']],
       [f'Trimestral ajustada {t["mom"]:.1f}%',f'Anual ajustada {t["yoy"]:.1f}%']],
      [['Actividad','Trimestral (%)','Anual (%)','Acumulado (%)']]+[[r['label'],f'{r["mom"]:.1f}',f'{r["yoy"]:.1f}',f'{r["ytd"]:.1f}'] for r in f['rows']],
      [['Actividad','Anual original (%)','Enero–trimestre (%)']]+[[r['label'],f'{r["original"]:.1f}',f'{r["ytd"]:.1f}'] for r in originals(f)],
    ]

def build(f,url,template,out):
    x=Layout(template,out);t=f['rows'][0];o=originals(f)[0];data=tables(f);op=f['indicator']=='PIB'
    x.table(data[0],True);x.p('Estimación oportuna del PIB' if op else 'Producto interno bruto trimestral',bold=True,color='10312B')
    x.note('Variaciones reales. Base '+f['base']+'. Edición del boletín '+f['bulletin']+'.')
    x.h('Resumen ejecutivo')
    x.p(f'En el {f["reference"]}, el PIB registró {t["mom"]:.1f}% respecto al trimestre previo y {t["yoy"]:.1f}% frente al mismo trimestre del año anterior, con cifras desestacionalizadas.',gray=True)
    sectors=f['rows'][1:];up=sum(r['mom']>0 for r in sectors);down=sum(r['mom']<0 for r in sectors)
    x.bullet(f'De las tres grandes actividades, {up} crecieron y {down} disminuyeron frente al trimestre previo; {3-up-down} no registraron cambio. Esta comparación no pondera su tamaño.',True)
    best=max(sectors,key=lambda r:r['mom']);worst=min(sectors,key=lambda r:r['mom'])
    x.bullet(f'Las {best["label"].lower()} presentaron la mayor tasa trimestral ({best["mom"]:.1f}%); las {worst["label"].lower()}, la menor ({worst["mom"]:.1f}%). Las tasas no son aportaciones al PIB.',True)
    x.h('Actividad económica con ajuste estacional');x.table(data[1]);x.note('Cuadro 1, p. 2. Trimestral frente al trimestre previo; anual frente al mismo trimestre de un año antes. Acumulado desde enero hasta el trimestre de referencia frente al mismo lapso previo.')
    x.bars('trimestral',[r['label'].replace('Actividades ','').capitalize() for r in sectors],[r['mom'] for r in sectors],'Variación trimestral por actividad','Variación real trimestral (%) · cifras desestacionalizadas')
    x.h('Balance de lo que va del año')
    x.p(f'El PIB acumuló una variación de {t["ytd"]:.1f}% con ajuste estacional y de {o["ytd"]:.1f}% con cifras originales. Son resultados de series distintas para el mismo intervalo; no se promedian tasas trimestrales.')
    x.note('La estimación oportuna está sujeta a cambios al incorporarse información y no reemplaza al cálculo trimestral.' if op else 'El cálculo trimestral incorpora información más reciente y conserva cifras preliminares y revisadas según los pies del boletín.')
    x.doc.add_page_break();x.h('Resultados con cifras originales');x.table(data[2]);x.note('Cuadro 2, p. '+('3' if op else '4')+'. Anual: mismo trimestre del año anterior. Acumulado: enero al trimestre de referencia. No equivale a tasa anualizada.')
    if op:
        rows=originals(f)[1:]
        x.bars('original',[r['label'].replace('Actividades ','').capitalize() for r in rows],[r['original'] for r in rows],'Variación anual por actividad','Variación real anual (%) · cifras originales')
        x.h('Lectura de la estimación')
        x.p(f'Con cifras originales, el total registró {o["original"]:.1f}% anual. Las tres actividades se comparan con el mismo trimestre del año previo; las diferencias respecto a las tasas ajustadas reflejan tratamientos estadísticos distintos.')
        x.bullet('La estimación oportuna utiliza información disponible y modelos econométricos para completar el trimestre. No se presenta como resultado definitivo.')
        x.bullet('La edición conserva información histórica preliminar y resultados oportunos para el trimestre actual. No se infiere una revisión frente a otro boletín sin cotejar ambas ediciones del mismo periodo.')
    else:
        selected_rows=selected(f)
        x.h('Contrastes sectoriales')
        x.bars('sectores',[r['label'] for r in selected_rows],[r['original'] for r in selected_rows],'Mayores y menores tasas sectoriales','Variación real anual (%) · cifras originales')
        n=sum(r['original']>0 for r in f['originals'] if r['id'].isdigit() or r['id'] in ['31-33','48-49'])
        x.p(f'De los 20 sectores publicados, {n} registraron crecimiento anual en cifras originales. La gráfica muestra los tres con mayores y los tres con menores tasas; esta selección no mide sus contribuciones al crecimiento.')
        manuf=next(r for r in f['originals'] if r['id']=='31-33')
        x.bullet(f'Las manufacturas registraron {manuf["original"]:.1f}% anual y {manuf["ytd"]:.1f}% en el acumulado, con cifras originales. Su desempeño debe distinguirse del agregado de actividades secundarias.')
    x.h('Notas metodológicas')
    x.p('El PIB mide la actividad productiva en términos reales. Las tasas ajustadas y originales se conservan por separado; no son variaciones nominales ni medidas directas de bienestar.')
    x.note('El ajuste estacional utiliza X-13ARIMA-SEATS. El total ajustado se calcula de manera independiente a sus componentes: no se suman ni se promedian sus tasas. No se estiman contribuciones sin ponderaciones compatibles ni se reconstruyen niveles desde gráficas PDF.')
    x.note(f'Fuente: INEGI, boletín {f["bulletin"]}, {f["publication_date"]}. Cuadros 1 y 2; ficha metodológica p. {len(f["pages"])}. Cifras sujetas a revisión.');x.note(url)
    x.save(NAMES[f['indicator']]+' '+f['period'])

def validate(f,doc):
    expected=tables(f)
    if len(doc.tables)!=len(expected) or len(doc.inline_shapes)!=2:raise ValueError('Faltan cuadros o gráficas')
    for actual,wanted in zip(doc.tables,expected):
        if [[c.text for c in r.cells] for r in actual.rows]!=wanted:raise ValueError('Cuadro Word distinto al boletín')
