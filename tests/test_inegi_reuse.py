import json
from pathlib import Path

from sources import inegi


def raw_series(*values):
    return {"Series": [{"FREQ": 8, "OBSERVATIONS": [
        {"TIME_PERIOD": f"2025/{month:02d}", "OBS_VALUE": str(value)}
        for month, value in enumerate(values, 1)
    ]}]}


def test_same_response_used_for_distinct_transformations(monkeypatch):
    monkeypatch.setenv("INEGI_TOKEN", "test")
    calls = []

    def request(url):
        calls.append(url)
        return raw_series(100, 110, 121)

    monkeypatch.setattr(inegi, "http_get_json", request)
    level = {"serie": "100", "columna_objetivo": 0, "factor": 10}
    monthly = {"serie": "100", "columna_objetivo": 1, "transform": "mom"}
    different_endpoint = {"serie": "100", "geo": "01", "columna_objetivo": 2}
    config = {"inegi": {"A": level, "B": [monthly, different_endpoint]}}

    fetched = inegi.fetch(config, start_year=2025)
    assert len(calls) == 2
    assert fetched.data == {
        "A": inegi._fetch_one(level, "test", 2025),
        "B": [inegi._fetch_one(monthly, "test", 2025),
              inegi._fetch_one(different_endpoint, "test", 2025)],
    }
    calls.clear()
    inegi.fetch(config, start_year=2025)
    assert len(calls) == 2  # La siguiente corrida consulta de nuevo.


def test_empty_response_and_failed_request_are_not_reused(monkeypatch):
    monkeypatch.setenv("INEGI_TOKEN", "test")
    results = iter((OSError("error simulado"), {}, raw_series(100, 110)))
    calls = []

    def request(url):
        calls.append(url)
        result = next(results)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(inegi, "http_get_json", request)
    result = inegi.fetch({"inegi": {
        key: {"serie": "100"} for key in ("FALLA", "VACIA", "VALIDA", "REUTILIZADA")
    }}, start_year=2025)
    assert len(calls) == 3
    assert set(result.data) == {"VALIDA", "REUTILIZADA"}


def test_configured_duplicate_requests_are_eliminated(monkeypatch):
    monkeypatch.setenv("INEGI_TOKEN", "test")
    config = json.loads((Path(__file__).resolve().parents[1] / "config/series.json").read_text())
    calls = []

    def request(url):
        calls.append(url)
        return raw_series(100, 110)

    monkeypatch.setattr(inegi, "http_get_json", request)
    inegi.fetch(config)
    optimized = len(calls)
    calls.clear()
    original = inegi._fetch_one

    def uncached(spec, token, start_year, **kwargs):
        return original(spec, token, start_year)

    monkeypatch.setattr(inegi, "_fetch_one", uncached)
    inegi.fetch(config)
    assert len(calls) > optimized
    assert len(set(calls)) == optimized
