"""Notas de Banxico e IED desde el snapshot oficial, sin inferencias causales."""
import argparse
import hashlib,json,math,os
from pathlib import Path
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx import Document
from docx.shared import Inches
from lib_format import per_long
from notas_layout import Layout
import notas_word as W
import build_auto_notes as A
from sources.inegi import label_to_ym
ROOT=Path(__file__).resolve().parents[1]
KEYS=('TIPOCAMBIO','TASA','RESERVAS','IED','REMESAS')
TITLES={'TIPOCAMBIO':'Tipo de cambio FIX','TASA':'Tasa objetivo','RESERVAS':'Reservas internacionales','IED':'Inversión extranjera directa','REMESAS':'Ingresos por remesas'}
UNITS={'TIPOCAMBIO':'Pesos por dólar','TASA':'Porcentaje','RESERVAS':'Millones de dólares','IED':'Millones de dólares','REMESAS':'Millones de dólares'}
def valid(v):return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)
def facts(ind):
    key=ind['key'];k=ind['metrics']['kpi']
    series=ind.get('observations_acumulado') if key=='IED' else ind['observations']
    today=datetime.now(ZoneInfo('America/Mexico_City')).date().isoformat()
    if key == 'REMESAS':
        series = [r for r in series if valid(r['values'][0])
                  and (ym := label_to_ym(r['period'])) and ym <= today[:7]]
    else:
        series=[r for r in series if valid(r['values'][0]) and (key=='IED' or r['period']<=today)]
    if key=='IED':
        span=series[-1]['period_acumulado'].rsplit(' ',1)[0]
        series=[r for r in series if r['period_acumulado'].rsplit(' ',1)[0]==span]
    if not series or not valid(k['ultimoRaw']):raise ValueError('Serie o KPI incompleto')
    last=series[-1];v=last['values'][0]
    if key=='IED' and ind.get('data_variant')=='originalmente_publicadas':
        if len(series)>1 and series[-2]['values'][0]>0:
            expected=(v/series[-2]['values'][0]-1)*100
            if abs(expected-k['varMag'])>1e-8:raise ValueError('IED: variación y acumulados originales no concilian')

    if abs(v-k['ultimoRaw'])>0.005:raise ValueError('El último dato no concilia con la ficha')
    fmt=lambda n:f'{n:,.4f}' if key=='TIPOCAMBIO' else f'{n:,.2f}'
    reading=f'{TITLES[key]}: {fmt(v)} {"%" if key=="TASA" else UNITS[key].lower()}. Referencia: {k["ultimoP"]}.'
    label = 'Corte ' + k['ultimoP']
    extra=[]
    if key=='TIPOCAMBIO':
        delta=(v/series[-2]['values'][0]-1)*100
        extra=[f'El FIX varió {delta:+.2f}% respecto a la observación hábil anterior. '+('El aumento representa una depreciación del peso frente al dólar.' if delta>0 else 'La disminución representa una apreciación del peso frente al dólar.' if delta<0 else 'El tipo de cambio se mantuvo sin cambio.'),'El FIX es un tipo de cambio de referencia; no equivale a una cotización de compra o venta al público.']
    elif key=='TASA':
        effective_date = k.get('vigenteDesdeP')
        label = (f'Vigente desde el {per_long(effective_date)}' if effective_date
                 else f'Corte al {per_long(last["period"])}')
        reading = f'Tasa objetivo: {fmt(v)} %.'
        extra=[f'Último ajuste registrado: {k["varText"]}.','La serie registra el nivel de la tasa objetivo. Una observación diaria repetida no constituye una nueva decisión de política monetaria.']
    elif key=='RESERVAS':
        if len(last['values'])>1 and valid(last['values'][1]):extra.append(f'El cambio semanal publicado fue {last["values"][1]:+,.1f} millones de dólares.')
        extra.append('El saldo de reservas es una variable de balance. Su cambio no identifica por sí solo operaciones de intervención cambiaria.')
    elif key=='REMESAS':
        if last['period'] != k['ultimoP'] or last['period'] != ind['last_observation']:
            raise ValueError('Remesas: el último periodo no concilia con la ficha')
        _, annual, accumulated, accumulated_annual = last['values']
        if valid(annual):
            extra.append(f'La variación anual del ingreso mensual fue de {annual:+.2%}, con cifras originales.')
        if valid(accumulated):
            text = f'El acumulado de enero al mes de referencia fue de {fmt(accumulated)} millones de dólares'
            if valid(accumulated_annual):
                text += f', una variación de {accumulated_annual:+.2%} frente al mismo lapso del año previo'
            extra.append(text + '.')
    else:
        extra=[f'El dato principal corresponde al acumulado {last["period_acumulado"]}.']
        if ind.get('corte_de_comunicado'):
            extra.append('Cifra preliminar del comunicado 114 de la Secretaría de Economía, publicado el 24 de noviembre de 2026.')
        if len(last['values'])>=4 and all(valid(x) for x in last['values'][1:4]):
            amounts=last['values'][1:4]
            if abs(sum(amounts)-v)>2:raise ValueError('Los componentes de IED no concilian')
            extra.append('Del total acumulado, '+', '.join(f'{name}: {n:,.0f} millones de dólares ({n/v*100:.1f}%)' for name,n in zip(['nuevas inversiones','reinversión de utilidades','cuentas entre compañías'],amounts))+'.')
        extra.append('Los flujos registrados son revisables. La IED no representa anuncios de inversión ni el total de la formación bruta de capital fijo.')
    recent=series[-6:]
    return dict(key=key,period=ind['last_observation'],label=k['ultimoP'],value=v,reading=reading,extra=extra,series=series,table=[['Periodo',UNITS[key]]]+[[r.get('period_acumulado',r['period']),fmt(r['values'][0])] for r in recent],source=ind['url_boletin_oficial'] if ind.get('corte_de_comunicado') else ind['fuente']['link'],source_name=ind['fuente']['nombre'])
def build(f,template,out):
    x=Layout(template,out);key=f['key'];x.p(TITLES[key],bold=True,size=14);x.p(f['label'],size=10)
    x.h('Lectura del indicador');x.p(f['reading'])
    for line in f['extra']:x.bullet(line)
    x.h('Evolución reciente');
    import matplotlib.pyplot as plt
    history_size = {'IED': 8, 'RESERVAS': 52, 'REMESAS': 24}.get(key, 260)
    rows = f['series'][-history_size:]
    with plt.rc_context({'font.family':'Noto Sans','font.size':9,'axes.unicode_minus':False}):
        fig,ax=plt.subplots(figsize=(6.1,2));ys=[r['values'][0] for r in rows];xs=list(range(len(rows)))
        if key=='TASA':ax.step(xs,ys,where='post',color='#1E5B4F')
        else:ax.plot(xs,ys,color='#1E5B4F',linewidth=1.6)
        ticks=sorted(set([0,len(rows)//2,len(rows)-1]));ax.set_xticks(ticks,[rows[i].get('period_acumulado',rows[i]['period']) for i in ticks]);ax.set_ylabel(UNITS[key]);ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',alpha=.2);fig.tight_layout();p=out.parent/'historia.png';fig.savefig(p,dpi=200);plt.close(fig)
    x.doc.add_picture(str(p),width=Inches(6.05));x.note('Serie del mismo concepto y unidad. '+('Mismo acumulado de cada año.' if key=='IED' else 'Observaciones disponibles en sus fechas de referencia.'))
    x.h('Últimas observaciones');x.table(f['table']);x.note('Fuente: '+f['source_name']+'. '+f['source']);
    for p in x.doc.paragraphs:
        if p.runs and p.runs[0].font.size and p.runs[0].font.size.pt==8:p.alignment=WD_ALIGN_PARAGRAPH.LEFT
    x.save(TITLES[key])
    d=Document(out)
    if len(d.inline_shapes)!=1 or len(d.tables)!=1 or [[c.text for c in r.cells] for r in d.tables[0].rows]!=f['table']:raise ValueError('El Word no concilia con la serie')
def decorate(ind,root=ROOT):
    state_path=root/'data/notas/financieras.json'
    states=json.loads(state_path.read_text()) if state_path.exists() else {};s=states.get(ind['key'],{});path=f'downloads/indicadores/{ind["key"]}/nota/{ind["key"]}_nota.docx'
    pdfpath=path.removesuffix('.docx')+'.pdf'
    pdfok=s.get('period')==ind.get('last_observation') and (root/pdfpath).exists() and hashlib.sha256((root/pdfpath).read_bytes()).hexdigest()==s.get('pdf_sha256')
    docxok=s.get('period')==ind.get('last_observation') and (root/path).exists() and hashlib.sha256((root/path).read_bytes()).hexdigest()==s.get('docx_sha256')
    ok=pdfok or docxok
    selected=pdfpath if pdfok else path
    ind.update(nota_disponible=ok,nota_causa=None if ok else 'Nota pendiente de actualizar',url_nota_individual=selected if ok else None,nota=dict(available=ok,format='pdf' if pdfok else 'docx',automatic=False,generated_from='snapshot_oficial',periodo=s.get('period'),path=selected,status='vigente' if ok else 'pendiente'))

def run(root=ROOT, keys=None):
    keys = KEYS if keys is None else tuple(dict.fromkeys(keys))
    payload=json.loads((root/'data/indicadores.json').read_text())
    state_path = root/'data/notas/financieras.json'
    states = json.loads(state_path.read_text()) if keys != KEYS and state_path.exists() else {}
    cfg=json.loads((root/'config/notas_automaticas.json').read_text())
    for key in keys:
        f=facts(payload['indicators'][key]);work=Path(os.environ.get('NOTES_WORK_DIR',str(root/'.notes-work')))/key;work.mkdir(parents=True,exist_ok=True);out=work/f'{key}_nota.docx';build(f,root/cfg['template'],out)
        _,pages=W.render(out,2)
        if not 1<=len(pages)<=2:raise ValueError('Extensión inválida')
        dest=root/f'downloads/indicadores/{key}/nota/{key}_nota.docx';dest.parent.mkdir(parents=True,exist_ok=True);A.atomic(dest,out.read_bytes())
        states[key]=dict(period=f['period'],docx_sha256=hashlib.sha256(out.read_bytes()).hexdigest(),source=f['source'],generated_at=datetime.now(timezone.utc).isoformat())
    A.write_json(root/'data/notas/financieras.json',states)
    for key in keys:decorate(payload['indicators'][key],root)
    A.write_json(root/'data/indicadores.json',payload)
    print('Notas financieras validadas:',', '.join(keys))

if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--key', action='append', choices=KEYS)
    args = parser.parse_args()
    run(keys=args.key)
