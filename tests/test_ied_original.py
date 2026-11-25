import copy,json
from pathlib import Path
import pytest
from ied_original import build_indicator,verify,preserve_legacy,original_transition

ROOT=Path(__file__).resolve().parents[1]
def original():
    return json.loads((ROOT/'data/ied_estatal.json').read_text())

def test_all_products_share_original_comparable_amounts():
    source=original(); before=copy.deepcopy(source); ind=build_indicator(source)
    verify(ind,source)
    rows=ind['observations_acumulado']; latest=source['periods'][-1]
    assert all(r['quarter']==latest['quarter'] for r in rows)
    for row in ind['observations']:
        published=next(p for p in source['periods'] if p['year']==row['year'] and p['quarter']==row['quarter'])
        assert row['values'][0]==published['total']
        assert row['values'][1:4]==list(published['components'].values())
        assert row['variant']=='originalmente_publicadas'
    assert ind['metrics']['kpi']['ultimoRaw']==latest['total']
    assert ind['metrics']['kpi']['varMag']==pytest.approx((rows[-1]['values'][0]/rows[-2]['values'][0]-1)*100)
    assert source==before

def test_dated_2026_edition_regression_and_no_inferred_quarter_flow():
    source=original(); source['periods']=[p for p in source['periods'] if (p['year'],p['quarter'])<=(2026,2)]
    ind=build_indicator(source)
    assert ind['observations_acumulado'][-2]['values'][0]==pytest.approx(34264.56746297)
    assert ind['metrics']['kpi']['ultimoRaw']==pytest.approx(34967.54664001)
    assert ind['metrics']['kpi']['varText']=='+2.1%'
    assert 'flujo_trimestral' not in ind['metrics']
    assert not any(k.startswith('flujo') for k in ind['metrics']['kpi'])

def test_mixed_edition_or_corrupt_kpi_blocks_release():
    source=original();ind=build_indicator(source)
    ind['observations_acumulado'][-2]['values'][0]=38019.72
    with pytest.raises(ValueError,match='mezcla'):verify(ind,source)
    ind=build_indicator(source);ind['metrics']['kpi']['varMag']+=1
    with pytest.raises(ValueError,match='KPI'):verify(ind,source)

def test_wrong_variant_and_unreconciled_components_rejected():
    source=original();source['variant']='actualizadas'
    with pytest.raises(ValueError):build_indicator(source)
    source=original();source['periods'][-1]['components']['Nuevas inversiones']+=100
    with pytest.raises(ValueError,match='componentes'):build_indicator(source)

def test_missing_same_cut_is_null_not_another_quarter():
    source=original();last=source['periods'][-1]
    source['periods']=[p for p in source['periods'] if (p['year'],p['quarter'])!=(last['year']-1,last['quarter'])]
    ind=build_indicator(source)
    assert ind['metrics']['kpi']['varMag'] is None
    assert ind['metrics']['kpi']['varText']=='—'

def test_original_migration_preserves_legacy_and_does_not_allow_further_shrinkage(tmp_path):
    source=original();ind=build_indicator(source)
    (tmp_path/'data').mkdir();(tmp_path/'data/ied_estatal.json').write_text(json.dumps(source))
    legacy={'observations':[{'period':'1T-00','values':[100]},{'period':'2T-26','values':[200]}]}
    report={'coverage':[{'sheet':'Flujo trimestral','column':0,'first':'2000-01-01','last':'2026-04-01','count':2}]}
    assert not original_transition(ind,report,tmp_path)
    preserve_legacy(tmp_path,legacy)
    assert original_transition(ind,report,tmp_path)
    assert not original_transition(ind,dict(report,data_variant='originalmente_publicadas'),tmp_path)
    path=tmp_path/'data/ied_nacional_legado.json';archived=json.loads(path.read_text())
    archived['indicator']['observations']=archived['indicator']['observations'][-1:]
    path.write_text(json.dumps(archived))
    with pytest.raises(ValueError,match='legado'):original_transition(ind,report,tmp_path)
