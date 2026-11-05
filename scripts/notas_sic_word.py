"""Nota SIC de dos páginas; cifras en puntos, sin reconstruir niveles históricos."""
from docx.shared import Inches
from notas_layout import Layout
from notas_imoam import period_text

def tables(f):
    c,a=f['groups']
    hero=[['Sistema de Indicadores Cíclicos','Publicación '+f['publication_date']]]
    for g in [c,a]:hero.append([g['name']+' · '+g['period'],f'{g["level"]:.1f} puntos | {g["delta"]:+.2f} mensual'])
    return [hero]+[[['Componente cíclico','Cambio mensual (puntos)','Relación con actividad']]+[[r['label'],f'{r["delta"]:+.2f}','Inversa' if r['inverse'] else 'Directa'] for r in g['components']] for g in f['groups']]

def position(g):
    return 'por arriba de la tendencia de largo plazo' if g['level']>100 else 'por debajo de la tendencia de largo plazo' if g['level']<100 else 'en torno a la referencia de tendencia, al redondeo publicado'

def chart(x,g):
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FormatStrFormatter
    h=g['history'];ys=[r['values'][0] for r in h];labels=[r['ym'][5:]+'/'+r['ym'][2:4] for r in h]
    with plt.rc_context({'font.family':'Noto Sans','font.size':9,'axes.unicode_minus':False}):
        fig,ax=plt.subplots(figsize=(6.1,1.75));ax.plot(range(12),ys,color='#235B4C',marker='o',markersize=3,lw=1.7);ax.axhline(0,color='#777',lw=.7)
        ax.annotate(f'{ys[-1]:+.2f}',(11,ys[-1]),xytext=(-8,10),textcoords='offset points',ha='right',color='#10312B',fontsize=9)
        ax.set_xticks([0,2,4,6,8,11],[labels[i] for i in [0,2,4,6,8,11]]);ax.yaxis.set_major_formatter(FormatStrFormatter('%.2f'));ax.margins(y=.30)
        ax.set_title('Cambios mensuales del Indicador '+g['name'],fontsize=11,color='#10312B');ax.set_ylabel('Puntos');ax.spines[['top','right']].set_visible(False)
        fig.tight_layout();path=x.out.parent/(g['name']+'.png');fig.savefig(path,dpi=300);plt.close(fig)
    x.doc.add_picture(str(path),width=Inches(6.05));x.note('Fuente: '+h[-1]['location']+'. Cada observación es una diferencia frente al mes previo; la línea cero representa ausencia de cambio, no la tendencia de 100 puntos.')

def build(f,url,template,out):
    x=Layout(template,out);c,a=f['groups'];data=tables(f)
    x.table(data[0],True);x.p('Sistema de indicadores cíclicos',bold=True,color='10312B')
    x.h('Resumen ejecutivo')
    x.p(f'En {period_text(c["ym"])}, el Indicador Coincidente se situó en {c["level"]:.1f} puntos, {position(c)}, y registró un cambio mensual de {c["delta"]:+.2f} puntos.',gray=True)
    x.bullet(f'El Indicador Adelantado registró {a["level"]:.1f} puntos en {period_text(a["ym"])}, {position(a)}, con un cambio mensual de {a["delta"]:+.2f} puntos.',True)
    x.bullet('El Coincidente refleja el estado general de la economía; el Adelantado busca anticipar sus puntos de giro. Sus meses de referencia son distintos y sus cambios no son tasas de crecimiento del PIB.',True)
    x.h('Componentes del Coincidente en '+c['period']);x.table(data[1]);x.note('Cuadro 1, p. 3. Cambios de los componentes cíclicos, no de las variables originales. En la desocupación urbana, la relación con la actividad es inversa.')
    chart(x,c)
    pos=sum(r['delta']>0 for r in c['components']);neg=sum(r['delta']<0 for r in c['components'])
    x.p(f'Entre sus seis componentes cíclicos, {pos} aumentaron, {neg} disminuyeron y {6-pos-neg} no registraron cambio al redondeo publicado. Este conteo describe signos; no mide contribuciones al indicador compuesto.')
    x.doc.add_page_break();x.h('Componentes del Adelantado en '+a['period']);x.table(data[2]);x.note('Cuadro 2, p. 6. Momento adecuado para invertir: sector manufacturero. IPC en términos reales. Tipo de cambio real y TIIE: relación inversa con la actividad económica.')
    chart(x,a)
    x.h('Contrastes en los componentes')
    direct=[r for r in a['components'] if not r['inverse']];best=max(direct,key=lambda r:r['delta']);worst=min(direct,key=lambda r:r['delta'])
    x.p(f'Entre los componentes de relación directa, {best["label"].lower()} registró el mayor cambio ({best["delta"]:+.2f} puntos) y {worst["label"]}, el menor ({worst["delta"]:+.2f} puntos). Son diferencias de componentes cíclicos, no rendimientos financieros.')
    x.h('Lectura de la posición cíclica')
    x.bullet('La referencia de 100 puntos representa la tendencia de largo plazo. La posición respecto a esa línea y el cambio mensual se analizan conjuntamente.')
    x.bullet('El cruce de 100 no determina por sí solo una recesión. El ciclo clásico identifica periodos entre picos y valles y se distingue del ciclo de crecimiento.')
    x.h('Notas y fuente')
    x.note('Series desestacionalizadas corregidas por atípicos, filtro Hodrick-Prescott aplicado dos veces y estandarización. Los cuadros conservan el signo publicado; la relación inversa se considera al interpretarlo. Las trayectorias pueden revisarse con nueva información.')
    x.note(f'INEGI, boletín {f["bulletin"]}, publicado el {f["publication_date"]}. Cuadros: pp. 3 y 6; interpretación: pp. 9–12; metodología: p. 13. Niveles a un decimal; cambios a dos.');x.note(url)
    x.save('SIC '+c['period']+' y '+a['period'])

def validate(f,doc):
    expected=tables(f)
    if len(doc.tables)!=3 or len(doc.inline_shapes)!=2:raise ValueError('Faltan tablas o gráficas SIC')
    for actual,wanted in zip(doc.tables,expected):
        if [[c.text for c in r.cells] for r in actual.rows]!=wanted:raise ValueError('Cuadro Word distinto al SIC publicado')
