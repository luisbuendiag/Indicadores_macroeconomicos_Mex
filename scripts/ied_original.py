"""One canonical originally-published IED edition for all public products."""
from copy import deepcopy
import json
import math
import re
from datetime import date
from pathlib import Path

VARIANT = 'originalmente_publicadas'
COMPONENTS = ('Nuevas inversiones', 'Reinversión de utilidades', 'Cuentas entre compañías')

def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)

def metrics(ind):
    rows = ind['observations_acumulado']
    last = rows[-1]
    total, change = last['values'][0], last['values'][4]
    direction = 'flat' if change is None or abs(change * 100) <= .05 else 'up' if change > 0 else 'down'
    assessment = {'up': 'favorable', 'down': 'adverso', 'flat': 'neutral'}[direction]
    text = '—' if change is None else f'{change * 100:+.1f}%'
    maximum = max(rows, key=lambda r: r['values'][0])
    minimum = min(rows, key=lambda r: r['values'][0])
    kpi = dict(assessment=assessment, dir=direction, ultimoFmt=f'{total:,.0f}',
        ultimoRaw=total, ultimoP=last['period_acumulado'], varText=text,
        varMag=None if change is None else change * 100, pos=change is None or change >= 0,
        varColor='#1E8F5F' if change is None or change >= 0 else '#9B2247',
        varLabel='Var. anual del acumulado', maxFmt=f'{maximum["values"][0]:,.0f}',
        maxRaw=maximum['values'][0], maxP=maximum['period_acumulado'],
        minFmt=f'{minimum["values"][0]:,.0f}', minRaw=minimum['values'][0],
        minP=minimum['period_acumulado'], lastI=len(rows)-1,
        series=[r['values'][0] for r in rows], periods=[r['period_acumulado'] for r in rows],
        semaforo={'favorable': 'bueno', 'adverso': 'malo'}.get(assessment, 'estable'))
    bullets = [f'La IED acumulada en {last["period_acumulado"]} fue de {total:,.0f} millones de dólares.']
    if change is not None:
        bullets.append(f'La variación respecto al mismo acumulado del año anterior fue de {text}, con cifras originalmente publicadas en ambos años.')
    bullets.append('Los cortes son acumulados desde enero; no representan flujos exclusivos de cada trimestre.')
    return dict(kpi=kpi, yoy=None, annualVar=None, resumen=bullets, analysis=bullets)

def build_indicator(data, previous=None):
    if data.get('variant') != VARIANT or not data.get('source_sha256'):
        raise ValueError('IED requiere TI_OR validado y trazable')
    periods = data.get('periods') or []
    if not periods:
        raise ValueError('IED sin historia original')
    keys = [(p['year'], p['quarter']) for p in periods]
    if keys != sorted(set(keys)):
        raise ValueError('IED con cortes duplicados o desordenados')
    by_cut = {(p['year'], p['quarter']): p for p in periods}
    rows = []
    for p in periods:
        total = p['total']; amounts = [p['components'][name] for name in COMPONENTS]
        if not all(finite(v) for v in [total, *amounts]) or abs(sum(amounts)-total) > .05:
            raise ValueError('IED original: componentes no concilian')
        prior = by_cut.get((p['year']-1, p['quarter']))
        change = total / prior['total'] - 1 if prior and prior['total'] > 0 else None
        rows.append(dict(period=f'{p["quarter"]}T-{p["year"]%100:02d}',
            period_acumulado=p['label'], year=p['year'], quarter=p['quarter'],
            variant=VARIANT, values=[total, *amounts, change]))
    last = periods[-1]; comparable = [dict(r, period=str(r['year'])) for r in rows if r['quarter'] == last['quarter']]
    ind = deepcopy(previous or {})
    ind.update(key='IED', nombre='Inversión Extranjera Directa (IED)',
        descripcion='IED acumulada desde enero, con cifras originalmente publicadas. Comparación anual al mismo corte.',
        frecuencia='Trimestral', unidad='Millones de dólares', ajuste_estacional='No aplica',
        grupo='inversion', clasificacion='complementario', data_variant=VARIANT,
        source_mode='structured_original', source_sha256=data['source_sha256'],
        source_url=data['source_url'], observations=rows, observations_acumulado=comparable,
        last_observation=rows[-1]['period'], periodo_referencia=last['label'],
        fuente=dict(nombre='Secretaría de Economía / RNIE', metodo='Archivo TI_OR, cifras originalmente publicadas',
                    link=data['source_url'], serie=None),
        columns=[dict(label=label,index=i,fmt='pct-frac' if i==4 else 'usd') for i,label in enumerate(
            ['IED acumulada desde enero',*COMPONENTS,'Var. anual del acumulado'])],
        notas=['Cifras originalmente publicadas; cada corte conserva su edición inicial.',
               'Acumulados desde enero. No restar cortes de diferentes ediciones para inferir flujos trimestrales.'])
    ind['metrics'] = metrics(ind)
    ind['metrics']['acumulado'] = dict(periodo=last['label'],valor=last['total'],unidad='mdd',
        variacion_anual_pct=comparable[-1]['values'][4],corte=last['label'].rsplit(' ',1)[0])
    ind['api_meta'] = dict(n_obs=len(rows),n_obs_acumulado=len(comparable),
        ultima_observacion=rows[-1]['period'],ultimo_valor=last['total'],variant=VARIANT)
    return ind

def verify(ind, original):
    canonical = build_indicator(original)
    if ind.get('data_variant') != VARIANT or ind['observations_acumulado'] != canonical['observations_acumulado'] or ind['observations'] != canonical['observations']:
        raise ValueError('IED: mezcla de ediciones o acumulados inconsistentes')
    expected = canonical['metrics']['kpi']; actual = ind['metrics']['kpi']
    for field in ('ultimoRaw','varMag'):
        if expected[field] is None:
            if actual.get(field) is not None: raise ValueError('IED: comparación inexistente')
        elif not finite(actual.get(field)) or abs(actual[field]-expected[field]) > 1e-8:
            raise ValueError('IED: KPI no concilia con acumulados originales')
    if any(field in actual for field in ('flujoRaw','flujoText','flujoP')):
        raise ValueError('IED: no inferir flujos trimestrales desde ediciones originales')

def sync(root):
    root = Path(root); path = root/'data/indicadores.json'
    payload=json.loads(path.read_text()); original=json.loads((root/'data/ied_estatal.json').read_text())
    previous=payload['indicators']['IED']
    archive=root/'data/ied_nacional_legado.json'
    if previous.get('data_variant') != VARIANT and not archive.exists():
        archive.write_text(json.dumps(dict(variant='legado_con_ediciones_mixtas_no_comparable',indicator=previous),ensure_ascii=False,indent=2)+'\n')
    ind=build_indicator(original,previous); verify(ind,original)
    payload['indicators']['IED']=ind
    path.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    metric_path=root/'data/metrics.json'
    if metric_path.exists():
        shared=json.loads(metric_path.read_text());shared['indicators']['IED']=metrics(ind)
        metric_path.write_text(json.dumps(shared,ensure_ascii=False,indent=2)+'\n')
    return ind

def preserve_legacy(root, ind):
    """Retain the full previous edition before moving to a different variant."""
    archive=Path(root)/'data/ied_nacional_legado.json'
    if ind.get('data_variant') != VARIANT and not archive.exists():
        archive.write_text(json.dumps(dict(variant='legado_con_ediciones_mixtas_no_comparable',indicator=ind),ensure_ascii=False,indent=2)+'\n')

def original_transition(ind, old_report, root):
    """Allow only the explicit, archived legacy-to-TI_OR migration once."""
    if ind.get('data_variant') != VARIANT or old_report.get('data_variant') == VARIANT:
        return False
    root=Path(root); archive=root/'data/ied_nacional_legado.json'
    if not archive.exists():
        return False
    old=json.loads(archive.read_text()).get('indicator',{})
    if old.get('data_variant') == VARIANT or not old.get('observations'):
        return False
    def period_date(text):
        if str(text).isdigit() and len(str(text))==4:
            return date(int(text),1,1).isoformat()
        found=re.fullmatch(r'([1-4])T-(\d{2}|\d{4})',str(text))
        if not found:raise ValueError('IED: periodo legado no reconocido')
        year=int(found[2]);year=year+(1900 if year>=80 else 2000) if year<100 else year
        return date(year,1+(int(found[1])-1)*3,1).isoformat()
    for covered in old_report.get('coverage',[]):
        rows=old.get('observations_acumulado',[]) if 'comparable' in covered.get('sheet','').lower() else old['observations']
        values=[r for r in rows if len(r.get('values',[]))>covered['column'] and finite(r['values'][covered['column']])]
        dates=sorted(period_date(r['period']) for r in values)
        if not dates or len(values)<covered['count'] or dates[0]>covered['first'] or dates[-1]<covered['last']:
            raise ValueError('IED: el archivo legado no preserva la cobertura anterior')
    verify(ind,json.loads((root/'data/ied_estatal.json').read_text()))
    # Legacy and original editions remain separate; neither is shortened in place.
    return True
