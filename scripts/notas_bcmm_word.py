"""BCMM ejecutiva: valores nominales, originales y ajustados sin confundir saldos."""
from docx.shared import Inches
from notas_layout import Layout
from notas_bcmm import row
from notas_imoam import period_text
FLOW=[('exports','Exportaciones totales'),('manufacturing','Exp. manufactureras'),('automotive','Exp. automotrices'),('non_automotive','Exp. no automotrices'),('imports','Importaciones totales'),('intermediate','Imp. intermedias'),('capital','Imp. de capital'),('balance','Saldo comercial')]
def number(v):return f'{v:,.1f}'.replace(',',' ')
def rate(f,i):return next(r for r in f['adjusted'] if r['id']==i)['value']
def tables(f):
    balance=row(f,'balance');c=f['balances'][0];prev=(int(f['ym'][5:])-2)%12
    from sources.inegi_bulletin import MESES_NOMBRE
    hero=[['BCMM · '+f['period'],'Publicación '+f['publication_date']],[f'Saldo original {number(balance["amount"])} mdd',f'Acumulado {number(balance["ytd"])} mdd']]
    flows=[['Concepto','Mes (mdd)','Anual (%)','Enero–mes (mdd)']]+[[label,number(row(f,i)['amount']),'—' if i=='balance' else f'{row(f,i)["yoy"]:.1f}',number(row(f,i)['ytd'])] for i,label in FLOW]
    balances=[['Saldo ajustado (mdd)',MESES_NOMBRE[prev].capitalize(),period_text(f['ym']).capitalize()]]+[[{'balance':'Total','balance_oil':'Petrolero','balance_non_oil':'No petrolero'}[r['id']],f'{r["previous"]:,}'.replace(',',' '),f'{r["current"]:,}'.replace(',',' ')] for r in f['balances']]
    markets=[['Destino no petrolero','Cuota enero–mes (%)','Anual mes (%)','Anual enero–mes (%)']]+[[r['label'],f'{r["share"]:.2f}',f'{r["values"][-2]:.1f}',f'{r["values"][-1]:.1f}'] for r in f['markets'] if r['id'] in ['usa','rest']]
    return [hero,flows,balances,markets]

def bars(x,name,labels,values,title,unit,precision):
    import matplotlib.pyplot as plt
    with plt.rc_context({'font.family':'Noto Sans','font.size':9,'axes.unicode_minus':False}):
        fig,ax=plt.subplots(figsize=(6.1,1.75));ys=list(range(len(values)));ax.barh(ys,values,color=['#235B4C' if v>=0 else '#611232' for v in values]);pad=max(1,max(abs(v) for v in values))*.24
        ax.set_xlim(min(0,min(values))-pad,max(0,max(values))+pad)
        for y,v in zip(ys,values):ax.text(v,y,(' ' if v>=0 else '')+f'{v:.{precision}f}'+(' ' if v<0 else ''),ha='left' if v>=0 else 'right',va='center',fontsize=8)
        ax.set_yticks(ys,labels);ax.invert_yaxis();ax.axvline(0,color='#777',lw=.7);ax.spines[['top','right']].set_visible(False);ax.set_title(title,fontsize=11,color='#10312B');ax.set_xlabel(unit,fontsize=9);fig.tight_layout();path=x.out.parent/(name+'.png');fig.savefig(path,dpi=300);plt.close(fig)
    x.doc.add_picture(str(path),width=Inches(6.05))

def build(f,url,template,out):
    x=Layout(template,out);data=tables(f);b=row(f,'balance');e=row(f,'exports');i=row(f,'imports')
    balance_word='superávit' if b['amount']>0 else 'déficit' if b['amount']<0 else 'saldo nulo';acc_word='superávit' if b['ytd']>0 else 'déficit' if b['ytd']<0 else 'saldo nulo'
    x.table(data[0],True);x.p('Balanza comercial de mercancías de México',bold=True,color='10312B')
    x.h('Resumen ejecutivo')
    x.p(f'En {period_text(f["ym"])}, la balanza comercial registró un {balance_word} de {number(abs(b["amount"]))} millones de dólares, con cifras originales. Las exportaciones variaron {e["yoy"]:.1f}% anual y las importaciones, {i["yoy"]:.1f}%.',gray=True)
    x.bullet(f'En enero al mes de referencia, el saldo fue un {acc_word} de {number(abs(b["ytd"]))} mdd. Las exportaciones acumularon {e["ytd_yoy"]:.1f}% anual y las importaciones, {i["ytd_yoy"]:.1f}%, frente al mismo lapso del año anterior.',True)
    x.bullet(f'Con ajuste estacional, las exportaciones cambiaron {rate(f,"exports"):.2f}% mensual y las importaciones, {rate(f,"imports"):.2f}%. Esta comparación de corto plazo se distingue de la anual en cifras originales.',True)
    x.h('Flujos y saldo con cifras originales');x.table(data[1]);x.note('Cuadro 1, p. 1. mdd: millones de dólares corrientes. Cifras oportunas; las filas incluyen agregados y desgloses. No se expresan cambios del saldo como crecimiento porcentual.')
    ids=['agriculture','extractive','automotive','non_automotive']
    bars(x,'anual',['Agropecuarias','Extractivas','Automotrices','No automotrices'],[row(f,i)['yoy'] for i in ids],'Exportaciones no petroleras por rubro','Variación nominal anual (%) · cifras originales',1)
    x.note('Fuente: cuadro 1. Automotrices y no automotrices desglosan las manufactureras; las tasas no se suman para obtener el agregado.')
    x.doc.add_page_break();x.h('Saldo con ajuste estacional');x.table(data[2]);x.note('Texto de la p. 5. Saldos en mdd redondeados a enteros. Los originales y ajustados son series distintas; no se compara su diferencia como si fuera un cambio en el tiempo.')
    bars(x,'mensual',['Exportaciones','Importaciones'],[rate(f,'exports'),rate(f,'imports')],'Cambios mensuales de los flujos ajustados','Variación nominal mensual (%) · cifras desestacionalizadas',2)
    x.p(f'Las exportaciones manufactureras variaron {rate(f,"manufacturing"):.2f}% mensual: automotrices, {rate(f,"automotive"):.2f}%, y no automotrices, {rate(f,"non_automotive"):.2f}%. Las importaciones de capital registraron {rate(f,"capital"):.2f}%.')
    x.h('Mercados de las exportaciones no petroleras');x.table(data[3]);x.note('Cuadro 3, p. 3. La cuota corresponde al acumulado enero al mes de referencia, exclusivamente de exportaciones no petroleras. No es participación mensual ni de exportaciones totales. Las tasas anuales comparan el mismo mes o acumulado del año anterior.')
    x.h('Alcance y fuente')
    x.p('La BCMM mide flujos nominales de mercancías en dólares corrientes. No mide volúmenes reales ni incluye comercio de servicios. Un superávit no acredita por sí solo mayor fortaleza económica; se analiza junto con exportaciones e importaciones.')
    x.note('Información oportuna, sujeta a revisión. Fuente principal: pedimentos aduanales. Ajuste estacional: X-13ARIMA-SEATS. Las sumas pueden diferir por redondeo. No se infieren causas, récords, destinos adicionales ni aportaciones a partir de tasas o de gráficas.')
    x.note(f'Fuente: SAT, Secretaría de Economía, Banco de México e INEGI. Boletín {f["bulletin"]}, {f["publication_date"]}. Cuadros 1–3: pp. 1–3; cifras ajustadas: pp. 5–8; metodología: p. 9.');x.note(url)
    x.save('BCMM '+f['period'])

def validate(f,doc):
    if len(doc.tables)!=4 or len(doc.inline_shapes)!=2:raise ValueError('Faltan tablas o gráficas BCMM')
    for actual,wanted in zip(doc.tables,tables(f)):
        if [[c.text for c in r.cells] for r in actual.rows]!=wanted:raise ValueError('Cuadro Word distinto al boletín BCMM')
