"""Regression: original IGAE rates must never enter IOAE error or RMSE."""
import copy
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from ioae_comparison import align_igae_observed
from lib_metrics import compute_kpi
from sources import inegi_bulletin as bulletin

URL = 'https://www.inegi.org.mx/contenidos/saladeprensa/boletines/2026/igae/igae2026_10.pdf'


def pair():
    ioae = {'key': 'IOAE', 'frecuencia': 'Mensual', 'observations': [
        {'period': 'Jun 26', 'values': [.02, .01, .03, .001] + [None] * 8 + [.08]},
        {'period': 'Ago 26', 'values': [.025, .013, .037, .001] + [None] * 8 + [.033335]},
        {'period': 'Sep 26', 'values': [.037, .026, .049, .001] + [None] * 9}]}
    igae = {'columns': [{'index': 9, 'label': 'Var. anual desest. (%)'}],
            'observations': [{'period': 'Ago 26', 'values': [100, .006, .033335] + [None] * 6 + [.035]}],
            'boletin_cifras': {'2026-08': {'9': {'value': .035, 'url': URL,
                                               'publication_date': '2026-10-23'}}}}
    return ioae, igae


def js_kpi(ind):
    script = "import {computeKPI} from './assets/js/metrics.js'; console.log(JSON.stringify(computeKPI(" + json.dumps(ind) + ")));"
    result = subprocess.run(['node', '--input-type=module'], input=script, text=True,
                            cwd=ROOT, check=True, capture_output=True)
    return json.loads(result.stdout)


def test_exact_month_adjustment_and_python_javascript_agree():
    ioae, igae = pair()
    original = copy.deepcopy(igae)
    assert align_igae_observed(ioae, igae) == 1
    assert igae == original  # Original rates stay intact.
    assert [o['values'][12] for o in ioae['observations']] == [None, .035, None]
    py, js = compute_kpi(ioae), js_kpi(ioae)
    for k in (py, js):
        assert k['latestObservedP'] == 'Ago 26'
        assert k['latestErrorPP'] == pytest.approx(1.0)
        assert k['rmseN'] == 1
        assert 'observedRaw' not in k  # Latest nowcast is September, observed is August.
    assert py['rmseText'].replace('p.p.', 'pp') == js['rmseText']


@pytest.mark.parametrize('problem', ['missing', 'wrong_label', 'no_evidence', 'wrong_value', 'foreign_url', 'nan'])
def test_no_original_fallback_and_stale_values_are_removed(problem):
    ioae, igae = pair()
    if problem == 'missing': igae = None
    elif problem == 'wrong_label': igae['columns'][0]['label'] = 'Anual original'
    elif problem == 'no_evidence': igae.pop('boletin_cifras')
    elif problem == 'wrong_value': igae['boletin_cifras']['2026-08']['9']['value'] = .1
    elif problem == 'foreign_url': igae['boletin_cifras']['2026-08']['9']['url'] = 'https://evil.example/boletines/igae.pdf'
    elif problem == 'nan': igae['observations'][0]['values'][9] = float('nan')
    assert align_igae_observed(ioae, igae) == 0
    assert all(o['values'][12] is None for o in ioae['observations'])
    k = compute_kpi(ioae)
    assert 'rmseText' not in k and 'latestErrorPP' not in k


def test_legacy_unmarked_data_cannot_generate_error_metrics():
    ioae, _ = pair()
    for k in (compute_kpi(ioae), js_kpi(ioae)):
        assert 'rmseText' not in k and 'latestErrorPP' not in k


def test_zero_observed_is_valid():
    ioae, igae = pair()
    igae['observations'][0]['values'][9] = 0.0
    igae['boletin_cifras']['2026-08']['9']['value'] = 0.0
    assert align_igae_observed(ioae, igae) == 1
    assert compute_kpi(ioae)['latestErrorPP'] == pytest.approx(-2.5)


def test_rounding_does_not_discard_documented_rates():
    ioae, igae = pair()
    igae['observations'][0]['values'][9] = .007
    igae['boletin_cifras']['2026-08']['9']['value'] = .7 / 100
    assert align_igae_observed(ioae, igae) == 1


def test_pipeline_migrates_without_changing_originals_and_tracks_per_row_source():
    from build_data import prepare_igae_for_v3, apply_inegi_total, compute_ioae_metrics
    ioae, igae = pair()
    igae['columns'] = [{'index': i, 'label': str(i)} for i in range(9)]
    igae['observations'][0]['values'] = igae['observations'][0]['values'][:9]
    igae.pop('boletin_cifras')
    payload = {'indicators': {'IGAE': igae, 'IOAE': ioae}}
    original_values = igae['observations'][0]['values'][:]
    prepare_igae_for_v3(payload)
    assert len(igae['columns']) == 10
    assert igae['observations'][0]['values'][:9] == original_values
    source = {'target_column': 9, 'api_total': [{'ym': '2026-08', 'period': 'Ago 26',
               'value': .035, 'source_url': URL, 'source_publication_date': '2026-10-23'}],
              'link': URL.replace('_10.pdf', '_11.pdf'), 'freq': 8, 'serie': 'IGAE_pdf',
              'metodo': 'INEGI boletín PDF', 'fecha_publicacion': '2026-11-23'}
    apply_inegi_total(payload, 'IGAE', source, None)
    compute_ioae_metrics(payload)
    assert ioae['observations'][1]['values'][12] == .035
    assert ioae['observed_sources']['2026-08']['url'] == URL
    assert ioae['observed_sources']['2026-08']['publication_date'] == '2026-10-23'
    assert igae['observations'][0]['values'][:9] == original_values


def test_bulletin_connector_keeps_adjusted_annual_separate(monkeypatch):
    monkeypatch.setattr(bulletin, '_available_issues', lambda *a, **kw: [(2026, 10, URL)])
    monkeypatch.setattr(bulletin, '_req', lambda _: b'fixture')
    monkeypatch.setattr(bulletin, '_pdf_text_first_page', lambda _: ('23 de octubre de 2026', []))
    row = {'ym': '2026-08', 'period': 'Ago 26', 'value': .035}
    monkeypatch.setattr(bulletin, '_parse_imcp_imfbcf', lambda *a: {'mensual': [dict(row, value=.006)], 'anual': [row]})
    items = bulletin._fetch_kind('IGAE', 2026, 1)
    assert [i['target_column'] for i in items] == [1, 9]
    observed = items[1]['api_total'][0]
    assert observed['value'] == .035
    assert observed['source_url'] == URL
    assert observed['source_publication_date'] == '2026-10-23'


def test_excel_preserves_new_adjusted_rate_separately():
    from build_data import prepare_igae_for_v3
    from build_excel import build_workbook
    _, igae = pair()
    igae.update(key='IGAE', nombre='IGAE', frecuencia='Mensual', unidad='Índice base 2018=100')
    prepare_igae_for_v3({'indicators': {'IGAE': igae}})
    model = build_workbook([igae])
    from datetime import date
    for column, expected in ((2, .033335), (9, .035)):
        sheet, address = model.coords['IGAE', column, date(2026, 8, 1)]
        assert model.wb[sheet][address].value == expected
