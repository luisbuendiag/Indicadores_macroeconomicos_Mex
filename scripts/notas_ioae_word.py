"""IOAE en dos páginas con intervalos explícitos y observados diferenciados."""
from docx.shared import Inches
from notas_layout import Layout
from notas_imoam import period_text

def current(f):return [r for r in f['rows'] if r['ym']==f['ym']]
def interval(v):return f'[{v["low"]:.1f}, {v["high"]:.1f}]' if v['low'] is not None else 'No publicado'
def tables(f):
    rows=current(f);t=rows[0]
    data=[[[f'IOAE · {f["period"]}','Publicación '+f['publication_date']],[f'Anual estimada {t["yoy"]["point"]:.1f}%',f'Mensual estimada {t["mom"]["point"]:.1f}%']]]
    for field,label in [('yoy','Anual'),('mom','Mensual')]:
        data.append([['Actividad',label+' estimada (%)','IC 95% (%)']]+[[r['label'],f'{r[field]["point"]:.1f}',interval(r[field])] for r in rows])
    data.append([['Actividad','Índice estimado','IC 95% (puntos)']]+[[r['label'],f'{r["index"]["point"]:.1f}',interval(r['index'])] for r in rows])
    prior=[r for r in f['rows'] if r['ym']!=f['ym']]
    data.append([['Mes previo y condición','Anual (%)','Mensual (%)']]+[[r['label']+' · '+('observado IMAI' if r['status']=='observado IMAI' else 'estimación'),f'{r["yoy"]["point"]:.1f}',f'{r["mom"]["point"]:.1f}'] for r in prior])
    return data

def range_text(v):
    if v['low']<0<v['high']:return 'incluye tanto disminuciones como aumentos'
    if v['low']<=0<=v['high']:return 'incluye la ausencia de cambio'
    return 'se mantiene por encima de cero' if v['low']>0 else 'se mantiene por debajo de cero'

def chart(x,f,field):
    import matplotlib.pyplot as plt
    rows=current(f);values=[r[field] for r in rows];ys=list(range(3))
    with plt.rc_context({'font.family':'Noto Sans','font.size':9,'axes.unicode_minus':False}):
        fig,ax=plt.subplots(figsize=(6.1,1.75))
        for y,v in zip(ys,values):
            ax.errorbar(v['point'],y,xerr=[[v['point']-v['low']],[v['high']-v['point']]],fmt='o',color='#235B4C',ecolor='#A57F2C',capsize=5,linewidth=2)
            ax.annotate(f'{v["point"]:.1f}%',(v['point'],y),xytext=(0,8),textcoords='offset points',ha='center',fontsize=8)
        ax.axvline(0,color='#777',lw=.8,ls='--');ax.set_yticks(ys,[('IGAE' if r['id']=='total' else r['label'].replace('Actividades ','').capitalize()) for r in rows]);ax.invert_yaxis();ax.set_ylim(2.5,-.6)
        lo=min(0,min(v['low'] for v in values));hi=max(0,max(v['high'] for v in values));pad=max(hi-lo,1)*.12;ax.set_xlim(lo-pad,hi+pad)
        ax.set_title(('Variación anual' if field=='yoy' else 'Variación mensual')+' estimada e IC al 95%',fontsize=11,color='#10312B');ax.set_xlabel('Variación real (%) · cifras desestacionalizadas');ax.spines[['top','right']].set_visible(False)
        fig.tight_layout();path=x.out.parent/(field+'.png');fig.savefig(path,dpi=300);plt.close(fig)
    x.doc.add_picture(str(path),width=Inches(6.05));x.note('Punto: estimación. Segmento: intervalo de confianza del 95%. Fuente: cuadro '+('1, p. 1.' if field=='yoy' else '2, p. 2.'))

def build(f,url,template,out):
    x=Layout(template,out);data=tables(f);rows=current(f);t=rows[0];prior=[r for r in f['rows'] if r['ym']!=f['ym']]
    x.table(data[0],True);x.p('Indicador oportuno de la actividad económica',bold=True,color='10312B')
    x.h('Resumen ejecutivo')
    x.p(f'Para {period_text(f["ym"])}, el IOAE estima una variación real del IGAE de {t["yoy"]["point"]:.1f}% anual y {t["mom"]["point"]:.1f}% mensual, con cifras desestacionalizadas. Son estimaciones anticipadas del IGAE.',gray=True)
    x.bullet(f'El intervalo anual del total es {interval(t["yoy"])}% y {range_text(t["yoy"])}. El mensual es {interval(t["mom"])}% y {range_text(t["mom"])}.',True)
    x.bullet(f'Las actividades secundarias registran una estimación anual de {rows[1]["yoy"]["point"]:.1f}% y las terciarias, de {rows[2]["yoy"]["point"]:.1f}%. Cada resultado conserva su intervalo; no se infieren aportaciones al total.',True)
    x.h('Comparación anual del mes estimado');x.table(data[1]);chart(x,f,'yoy')
    x.h('Comparación mensual del mes estimado');x.table(data[2]);x.note('Cuadros 1 y 2. Anual: frente al mismo mes de un año antes. Mensual: frente al mes inmediato anterior. Los rangos corresponden al mismo mes y actividad que cada estimación.')
    x.doc.add_page_break();x.h('Incertidumbre en el cambio mensual');chart(x,f,'mom')
    x.p(f'El intervalo mensual del IGAE {range_text(t["mom"])}. La estimación puntual debe leerse junto con ese rango y no como un cambio observado o garantizado.')
    x.h('Nivel estimado de actividad');x.table(data[3]);x.note(f'Cuadro 3, p. 2. Índice base {f["base"]}=100, desestacionalizado. Intervalos en puntos del índice; no son porcentajes ni tasas acumuladas.')
    x.h('Mes previo en la misma edición');x.table(data[4]);x.note(f'Referencia: {period_text(prior[0]["ym"])}. Cuadros 1 y 2. El dato de secundarias es observado según el IMAI, como indica el pie 2; no presenta intervalo de confianza. Los otros dos son estimaciones IOAE.')
    x.h('Alcance y fuente')
    x.p('El IOAE anticipa el comportamiento del IGAE mediante modelos econométricos y no reemplaza su cálculo tradicional. El total se estima de manera independiente de sus componentes; las tasas sectoriales no se suman ni se promedian para obtenerlo.')
    x.note('Modelo de factor dinámico, mínimos cuadrados parciales, regresiones con errores autocorrelacionados y validación cruzada, según la ficha metodológica. Los intervalos no asignan una probabilidad a cada punto ni prueban por sí solos diferencias significativas entre sectores. No se reconstruyen series desde gráficas ni se atribuyen causas.')
    x.note(f'INEGI, boletín {f["bulletin"]}, {f["publication_date"]}. Cuadros: pp. 1–2; gráficas: pp. 3–5; metodología: p. 6. IC al 95%; cifras de la edición publicada, sujetas a actualización.');x.note(url)
    x.save('IOAE '+f['period'])

def validate(f,doc):
    expected=tables(f)
    if len(doc.tables)!=5 or len(doc.inline_shapes)!=2:raise ValueError('Faltan tablas o gráficas IOAE')
    for actual,wanted in zip(doc.tables,expected):
        if [[c.text for c in r.cells] for r in actual.rows]!=wanted:raise ValueError('Cuadro Word distinto al boletín IOAE')
