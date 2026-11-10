import copy,json
from pathlib import Path
import pytest
import build_financial_notes as F
ROOT=Path(__file__).resolve().parents[1]
DATA=json.loads((ROOT/'data/indicadores.json').read_text())['indicators']
@pytest.mark.parametrize('key',F.KEYS)
def test_notes_reconcile_with_snapshot_and_native_tables(key):
    f=F.facts(DATA[key]);assert f['value']==DATA[key]['metrics']['kpi']['ultimoRaw'];assert len(f['table'])==7
    ind=copy.deepcopy(DATA[key]);F.decorate(ind);assert ind['nota_disponible']
    ind['last_observation']='invalid';F.decorate(ind);assert not ind['nota_disponible']
def test_ied_is_accumulated_not_quarter_flow():
    f=F.facts(DATA['IED']);assert f['value']==34968;assert f['value']!=DATA['IED']['observations'][-1]['values'][0]
    assert all(r.get('period_acumulado','').startswith('Ene-Jun') for r in f['series'])
def test_corrupt_kpi_and_components_fail_closed():
    ind=copy.deepcopy(DATA['IED']);ind['metrics']['kpi']['ultimoRaw']+=100
    with pytest.raises(ValueError):F.facts(ind)
    ind=copy.deepcopy(DATA['IED']);ind['observations_acumulado'][-1]['values'][1]+=100
    with pytest.raises(ValueError):F.facts(ind)
def test_inpc_accepts_seven_pages_and_rejects_unknown_structure(monkeypatch):
    import notas_precios as N
    from test_price_notes import fixture,PDF
    f=fixture(monkeypatch,'INPC')
    f['pages']=[p.replace('/6','/7') for p in f['pages']]
    f['pages'].insert(5,f['pages'][-1].replace('Página 6/7','Página 6/7'))
    f['pages'][-1]=f['pages'][-1].replace('Página 6/7','Página 7/7')
    assert len(N.extract(b'fixture','INPC')['pages'])==7
    f['pages'].append(f['pages'][-1])
    with pytest.raises(ValueError):N.extract(b'fixture','INPC')
