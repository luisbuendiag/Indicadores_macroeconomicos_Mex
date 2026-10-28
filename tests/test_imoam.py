"""Regresión de IMOAM: escala, incertidumbre y recuperación defensiva."""
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from sources import imoam
import lib_metrics

ROOT = Path(__file__).resolve().parents[1]
TEXT = (ROOT / 'tests/fixtures/imoam2026_10.txt').read_text()

class PDF:
    def __init__(self, text): self.pages = [SimpleNamespace(extract_text=lambda: text)]
    def __enter__(self): return self
    def __exit__(self, *args): pass

def test_official_table_scaling_and_reference(monkeypatch):
    monkeypatch.setattr(imoam.B.pdfplumber, 'open', lambda b: PDF(TEXT))
    rows, _, pub = imoam.parse_pdf(b'fixture')
    assert [r['value'] for r in rows] == pytest.approx([108, 105.1, 111.1, .019, -.009, .047])
    assert rows[0]['ym'] == '2026-09'
    assert pub == (2026, 10, 28)

@pytest.mark.parametrize('text', [TEXT.replace('105.1', '115.1'), TEXT.replace('IMOAM', 'OTRO').replace('MANUFACTURERA', 'OTRA'), TEXT.replace('septiembre', 'noviembre')])
def test_reject_wrong_product_intervals_or_future_period(monkeypatch, text):
    monkeypatch.setattr(imoam.B.pdfplumber, 'open', lambda b: PDF(text))
    with pytest.raises(ValueError): imoam.parse_pdf(b'fixture')

def test_network_failure_preserves_existing_data(monkeypatch):
    def fail(*a, **kw): raise OSError('offline')
    monkeypatch.setattr(imoam.urllib.request, 'urlopen', fail)
    result = imoam.fetch(max_bulletins=1)
    assert not result.ok and result.warnings and not result.data

def test_published_metrics_and_products():
    p = json.loads((ROOT/'data/indicadores.json').read_text())
    ind = p['indicators']['IMOAM']
    assert len(ind['columns']) == 6
    assert p['order'].index('IMOAM') == p['order'].index('IMAI') + 1
    assert all(len(o['values']) == 6 for o in ind['observations'])
    assert ind['nota_disponible'] and ind['xlsx_disponible']
    assert (ROOT / ind['url_nota_individual']).exists()
    metrics = lib_metrics.compute_all_metrics(p)['IMOAM']
    assert metrics['kpi']['varMag'] == pytest.approx(1.9)
    assert metrics['annualVar'] is None
    assert any('experimental' in line for line in metrics['analysis'])
