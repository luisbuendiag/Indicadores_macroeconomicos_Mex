"""Calendar regression: month rollover must not imply a late release."""
from datetime import date
from sources.imoam import publication_warnings

def calendar(*days):
    return {'items': [{'clave': 'IMOAM', 'fecha_iso': d} for d in days]}

def test_before_next_official_release():
    assert publication_warnings((2026, 10, 28), date(2026, 11, 13),
        calendar('2026-10-28', '2026-11-25')) == []

def test_due_but_missing_keeps_warning():
    warnings = publication_warnings((2026, 10, 28), date(2026, 11, 26),
        calendar('2026-10-28', '2026-11-25'))
    assert len(warnings) == 1 and '2026-11-25' in warnings[0]

def test_due_release_recovered():
    assert publication_warnings((2026, 11, 25), date(2026, 11, 26),
        calendar('2026-11-25')) == []

def test_missing_or_invalid_calendar_cannot_certify_freshness():
    for value in ({}, calendar('invalid')):
        assert 'no se puede confirmar' in publication_warnings(
            (2026, 10, 28), date(2026, 11, 13), value)[0]

def test_other_indicators_and_disabled_rows_are_ignored():
    data = calendar('2026-10-28')
    data['items'] += [
        {'clave': 'IMAI', 'fecha_iso': '2026-11-11'},
        {'clave': 'IMOAM', 'fecha_iso': '2026-11-10', 'usar_para_frescura': False}]
    assert publication_warnings((2026, 10, 28), date(2026, 11, 13), data) == []
