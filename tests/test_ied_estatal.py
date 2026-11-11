import copy,json
from pathlib import Path
import openpyxl,pytest
import ied_estatal as E
ROOT=Path(__file__).resolve().parents[1]
DATA=json.loads((ROOT/'data/ied_estatal.json').read_text())
def test_complete_history_actual_header_not_filename():
 assert len(DATA['periods'])>=34
 assert DATA['periods'][0]['year']==2018
 last=DATA['periods'][-1]
 assert DATA['ranking']['period']==f"{last['quarter']}T-{last['year']}"
 for p in DATA['periods']:
  assert set(p['values'])==set(E.STATES)
  assert abs(sum(p['values'].values())-p['total'])<.05
 assert DATA['ranking']['comparison'].endswith(str(last['year']-1))
def test_ranking_ties_and_year_comparison():
 x=copy.deepcopy(DATA);last=x['periods'][-1];last['values'][E.STATES[0]]=last['values'][E.STATES[1]]
 r=E.ranking(x);rows={v['state']:v for v in r['rows']}
 assert rows[E.STATES[0]]['rank']==rows[E.STATES[1]]['rank']
 assert all(v['change']==v['previous_rank']-v['rank'] for v in r['rows'])
def test_official_discovery_and_no_external_redirect():
 p=E.Links();p.feed('<a href="/cms/uploads/attachment/file/123/2027_1T_Flujos_TI_OR_2.xlsx">Datos</a>')
 assert len(p.urls)==1
 assert not E.allowed('https://evil.example/2027_Flujos_EF_AC.xlsx')
 assert not E.allowed(E.URL+'?evil=1')
def test_source_failure_keeps_validated_history(tmp_path,monkeypatch):
 p=tmp_path/'data/ied_estatal.json';p.parent.mkdir();p.write_text(json.dumps(DATA))
 monkeypatch.setattr(E,'get',lambda _:(_ for _ in ()).throw(ValueError('network')))
 E.refresh(tmp_path);after=json.loads(p.read_text());assert after['periods']==DATA['periods'];assert after['download_status']=='conservado'
def test_excel_native_formulas_and_history_grow():
 w=openpyxl.Workbook();E.add_excel_sheets(w,DATA)
 h=w['Historia estatal'];r=w['Ranking estatal'];assert h.max_row==len(DATA['periods'])+3 and h.max_column==34
 assert r['D4'].value.startswith('=COUNTIF(') and r['F4'].value=='=E4-D4'
 assert len(r._charts)==1
 more=copy.deepcopy(DATA);new=copy.deepcopy(more['periods'][-1]);new.update(quarter=2,period='2T-2026',label='Ene-Jun 2026');more['periods'].append(new);more['ranking']=E.ranking(more)
 w2=openpyxl.Workbook();E.add_excel_sheets(w2,more);assert w2['Historia estatal'].max_row==len(DATA['periods'])+4
 assert str(len(DATA['periods'])+4) in w2['Ranking estatal']['B4'].value

def test_original_versions_reconcile_national_components_and_state_rank():
 assert DATA['variant']=='originalmente_publicadas'
 assert 'originalmente publicadas' in DATA['basis']
 current=next(p for p in DATA['periods'] if p['period']=='2T-2026')
 previous=next(p for p in DATA['periods'] if p['period']=='2T-2025')
 assert current['total']==pytest.approx(34967.54664001)
 assert previous['total']==pytest.approx(34264.56746297)
 assert current['total']/previous['total']-1==pytest.approx(.020516,abs=.000001)
 for p in DATA['periods']:assert sum(p['components'].values())==pytest.approx(p['total'],abs=.05)
 revised=json.loads((ROOT/'data/ied_estatal_actualizada.json').read_text())
 assert revised['periods'][0]['year']==2006
 assert not E.allowed(revised['source_url'])
