import copy,json
from datetime import datetime
from pathlib import Path
import pytest
import build_financial_notes as F
ROOT=Path(__file__).resolve().parents[1]
DATA=json.loads((ROOT/'data/indicadores.json').read_text())['indicators']
from ied_original import build_indicator
ORIGINAL=json.loads((ROOT/'data/ied_estatal.json').read_text())
DATA['IED']=build_indicator(ORIGINAL,DATA['IED'])
@pytest.mark.parametrize('key',F.KEYS)
def test_notes_reconcile_with_snapshot_and_native_tables(key):
    if key == 'REMESAS' and key not in DATA:
        pytest.skip('Remesas todavía no forma parte de la edición guardada')
    f = F.facts(DATA[key])
    assert f['value'] == DATA[key]['metrics']['kpi']['ultimoRaw']
    assert len(f['table']) == 1 + min(6, len(f['series']))
    ind=copy.deepcopy(DATA[key]);F.decorate(ind);assert ind['nota_disponible']
    ind['last_observation']='invalid';F.decorate(ind);assert not ind['nota_disponible']
def test_ied_is_accumulated_not_quarter_flow():
    f=F.facts(DATA['IED']);assert f['value']==ORIGINAL['periods'][-1]['total'];assert f['value']==DATA['IED']['observations'][-1]['values'][0]
    assert all(r['quarter']==ORIGINAL['periods'][-1]['quarter'] for r in f['series'])
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


@pytest.mark.parametrize('accumulated, growth', [(45914.1, -.054), (None, None)])
def test_remesas_note_reads_monthly_level_and_complete_cut(accumulated, growth, monkeypatch):
    class ReleaseClock(datetime):
        @classmethod
        def now(cls, tz):
            return datetime(2026, 11, 18, tzinfo=tz)

    monkeypatch.setattr(F, 'datetime', ReleaseClock)
    ind = {
        'key': 'REMESAS',
        'last_observation': 'Sep 26',
        'metrics': {'kpi': {'ultimoRaw': 5362.191882, 'ultimoP': 'Sep 26'}},
        'observations': [
            {'period': 'Ago 26', 'values': [5452.34, None, None, None]},
            {'period': 'Sep 26', 'values': [5362.191882, .0196, accumulated, growth]},
            {'period': 'Ene 30', 'values': [999, None, None, None]},
        ],
        'fuente': {'nombre': 'Banco de México (SIE)', 'link': 'https://www.banxico.org.mx/'},
    }
    facts = F.facts(ind)
    assert facts['table'][-1] == ['Sep 26', '5,362.19']
    assert '5,362.19 millones de dólares' in facts['reading']
    assert '+1.96%' in facts['extra'][0]
    if accumulated is not None:
        assert '45,914.10 millones' in facts['extra'][1]
        assert '-5.40%' in facts['extra'][1]
    else:
        assert len(facts['extra']) == 1
    ind['metrics']['kpi']['ultimoP'] = 'Ago 26'
    with pytest.raises(ValueError, match='periodo'):
        F.facts(ind)
