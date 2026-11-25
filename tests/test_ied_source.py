import json
from pathlib import Path
import ied_estatal
from sources import ied

ROOT=Path(__file__).resolve().parents[1]

def setup_source(tmp_path,monkeypatch,status):
    original=json.loads((ROOT/'data/ied_estatal.json').read_text())
    original['download_status']=status
    (tmp_path/'data').mkdir()
    path=tmp_path/'data/indicadores.json'
    path.write_text(json.dumps({'indicators':{'IED':{'last_checked':'2026-11-12'}}}))
    (tmp_path/'data/ied_estatal.json').write_text(json.dumps(original))
    monkeypatch.setattr(ied,'ROOT',tmp_path)
    monkeypatch.setattr(ied,'DATA_DIR',tmp_path/'data')
    monkeypatch.setattr(ied_estatal,'refresh',lambda root:None)
    return original,path

def test_cached_edition_does_not_count_as_new_successful_query(tmp_path,monkeypatch):
    _,path=setup_source(tmp_path,monkeypatch,'conservado');before=path.read_bytes()
    result=ied.fetch()
    assert not result.ok
    assert result.data=={}
    assert path.read_bytes()==before
    assert any('sin adelantar' in w for w in result.warnings)

def test_successful_original_download_is_queryable(tmp_path,monkeypatch):
    original,_=setup_source(tmp_path,monkeypatch,'ok')
    result=ied.fetch()
    assert result.ok
    assert result.data['IED']['data_variant']=='originalmente_publicadas'
    assert result.data['IED']['metrics']['kpi']['ultimoRaw']==original['periods'][-1]['total']
