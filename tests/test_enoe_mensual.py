import pytest

from enoe_mensual import RATE_IDS, refresh


URL = 'https://www.inegi.org.mx/contenidos/saladeprensa/boletines/2026/iooe/IOE2026_10.pdf'


def facts(period):
    return {'period': period, 'bulletin': '634/26', 'publication_date': '2026-10-22',
            'population': [{'id': 'occupied', 'group': 'total', 'current': 59977049,
                            'previous': 60244382, 'difference': -267333}],
            'rates': [{'id': key, 'difference': -0.1} for key in RATE_IDS],
            'adjusted': [{'id': key, 'current': 2.6, 'mom': -0.2} for key in RATE_IDS]}


def test_refresh_keeps_series_distinct_and_skips_repeat(monkeypatch):
    indicator = {'last_observation': 'Sep 26', 'url_boletin_oficial': URL}
    monkeypatch.setattr('enoe_mensual.notas_enoe.extract', lambda _pdf: facts('Sep 26'))
    assert refresh(indicator, fetch=lambda *_a, **_k: b'%PDF')
    actual = indicator['enoe_mensual']
    assert actual['ocupados'] == 59977049
    assert actual['cambio_ocupados_anual'] == -267333
    assert actual['tasas']['unemployment'] == {
        'anual_original_pp': -0.1, 'nivel_desest': 2.6, 'mensual_desest_pp': -0.2}
    assert refresh(indicator, fetch=lambda *_a, **_k: pytest.fail('repeat query')) is False


def test_invalid_reference_cannot_replace_monthly_values(monkeypatch):
    previous = {'periodo': 'Ago 26', 'ocupados': 60000000}
    indicator = {'last_observation': 'Sep 26', 'url_boletin_oficial': URL, 'enoe_mensual': previous}
    monkeypatch.setattr('enoe_mensual.notas_enoe.extract', lambda _pdf: facts('Ago 26'))
    with pytest.raises(ValueError, match='contiene Ago 26'):
        refresh(indicator, fetch=lambda *_a, **_k: b'%PDF')
    assert indicator['enoe_mensual'] == previous


def test_card_never_substitutes_quarterly_occupation_for_missing_month():
    from lib_metrics import _desocup_metrics

    indicator = {
        'key': 'DESOCUP',
        'observations': [
            {'period': 'Sep 25', 'values': [3.0]},
            {'period': 'Abr 26', 'values': [2.9, None, None, None, 60.0, 60000000]},
            {'period': 'Sep 26', 'values': [2.8]},
        ],
        'enoe_mensual': {'periodo': 'Ago 26', 'ocupados': 59800000},
    }
    stale = _desocup_metrics(indicator, {})['kpi']
    assert stale['poblacion'] is None
    assert stale['cards'][0]['momRaw'] is None

    indicator['enoe_mensual'] = {
        'periodo': 'Sep 26', 'ocupados': 59977049,
        'tasas': {'unemployment': {'nivel_desest': 2.6, 'mensual_desest_pp': -0.1}},
    }
    matched = _desocup_metrics(indicator, {})['kpi']
    assert matched['poblacion']['personas'] == 59977049
    assert matched['poblacion']['frecuencia'] == 'mensual'
    assert matched['cards'][0]['momRaw'] == -0.1
