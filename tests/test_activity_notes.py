import json,copy
from pathlib import Path
from types import SimpleNamespace
import pytest
import notas_actividad as N
from build_activity_notes import allowed
ROOT=Path(__file__).resolve().parents[1]

class PDF:
    def __init__(self,pages):self.pages=[SimpleNamespace(extract_text=lambda p=p:p) for p in pages]
    def __enter__(self):return self
    def __exit__(self,*a):pass

@pytest.mark.parametrize('key,index,annual,original',[('IMAI',103.4,3.6,3.5),('IGAE',108.4,3.5,3.3)])
def test_official_edition_separates_series(monkeypatch,key,index,annual,original):
    pages=json.loads((ROOT/f'tests/fixtures/{key.lower()}2026_10_pages.json').read_text())
    monkeypatch.setattr(N.pdfplumber,'open',lambda _:PDF(pages))
    f=N.extract(b'fixture',key);r=f['rows'][0]
    assert f['period']=='Ago 26' and r['index']==index
    assert r['mom']==.6 and r['yoy']==annual and r['original']==original
    assert all(r['evidence_adjusted'] and r['evidence_original'] for r in f['rows'])
    pages[1]=pages[1].replace('Cuadro 1','Otro cuadro')
    with pytest.raises((ValueError,IndexError)):N.extract(b'fixture',key)

@pytest.mark.parametrize('key',['IMAI','IGAE'])
def test_wrong_product_and_source_rejected(monkeypatch,key):
    other='IGAE' if key=='IMAI' else 'IMAI'
    pages=json.loads((ROOT/f'tests/fixtures/{other.lower()}2026_10_pages.json').read_text())
    monkeypatch.setattr(N.pdfplumber,'open',lambda _:PDF(pages))
    with pytest.raises(ValueError):N.extract(b'fixture',key)
    assert not allowed('https://evil.example/imai2026_10.pdf',key)
    assert not allowed('https://www.inegi.org.mx/contenidos/saladeprensa/boletines/2026/'+other.lower()+'/'+other.lower()+'2026_10.pdf',key)
