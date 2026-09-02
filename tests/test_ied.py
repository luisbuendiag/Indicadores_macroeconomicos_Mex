"""Tests para el conector IED de la Secretaría de Economía."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from sources import ied

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def _sample_manual() -> dict:
    return json.loads((DATA_DIR / "ied_manual_2026_2t.json").read_text(encoding="utf-8"))


def test_period_to_quarter():
    assert ied._period_to_quarter("Enero - marzo") == (1, 3)
    assert ied._period_to_quarter("Enero-marzo") == (1, 3)
    assert ied._period_to_quarter("Enero - junio") == (4, 6)
    assert ied._period_to_quarter("Enero - septiembre") == (7, 9)
    assert ied._period_to_quarter("Enero - diciembre") == (10, 12)
    assert ied._period_to_quarter("Agosto") is None


def test_clean_converts_values():
    assert ied._clean(1234.5) == 1234.5
    assert ied._clean("34967.55") == 34967.55
    assert ied._clean("-") is None
    assert ied._clean("C") is None
    assert ied._clean(None) is None


def test_pct_to_frac():
    items = [{"concepto": "A", "participacion_pct": 88.5}]
    out = ied._pct_to_frac(items)
    assert out[0]["participacion_pct"] == 0.885


def test_historical_flows():
    acum = [
        {"year": 2025, "end_month": 3, "acumulado": 21373.19, "period_acum": "Ene-Mar 25", "quarter": "1T-25"},
        {"year": 2025, "end_month": 6, "acumulado": 34264.57, "period_acum": "Ene-Jun 25", "quarter": "2T-25"},
        {"year": 2026, "end_month": 3, "acumulado": 24503.05, "period_acum": "Ene-Mar 26", "quarter": "1T-26"},
        {"year": 2026, "end_month": 6, "acumulado": 34968, "period_acum": "Ene-Jun 26", "quarter": "2T-26"},
    ]
    flows = ied._historical_flows(acum)
    by_ym = {(f["year"], f["end_month"]): f["flujo"] for f in flows}
    assert by_ym[(2025, 3)] == 21373.19
    assert round(by_ym[(2025, 6)], 2) == 12891.38
    assert by_ym[(2026, 3)] == 24503.05
    assert round(by_ym[(2026, 6)], 2) == 10464.95


def test_componentes_flujo_from_manual():
    manual = _sample_manual()
    # Simular componentes 1T de un XLS
    ti_1t = {"nuevas": 2071.63, "reinversion": 24086.04, "cuentas": -1654.62}
    comp = ied._componentes_flujo_from_manual(manual, ti_1t)
    assert comp["Nuevas inversiones"] == round(2726 - 2071.63 * (24503.05 / (2071.63 + 24086.04 - 1654.62)), 2)
    assert comp["Reinversión de utilidades"] > 0
    assert comp["Cuentas entre compañías"] > 0


@pytest.mark.skipif(not (DATA_DIR / "ied_manual_2026_2t.json").exists(), reason="manual 2T no presente")
def test_build_indicator_shape():
    res = ied.fetch()
    assert res.ok, res.warnings
    ind = res.data["IED"]
    assert ind["key"] == "IED"
    assert ind["last_observation"] == "2T-26"
    assert ind["columns"][0]["label"] == "Flujo trimestral"
    assert ind["columns"][4]["fmt"] == "pct-frac"

    # La serie principal (observations) debe ser flujo trimestral, no acumulado.
    last = ind["observations"][-1]
    assert last["period"] == "2T-26"
    assert last.get("period_acumulado") == "Ene-Jun 26"
    assert last["values"][0] == 10464.95
    assert round(last["values"][4], 2) == -0.04

    # Serie de acumulado comparable: mismo corte para todos los puntos.
    acum = ind["observations_acumulado"]
    assert acum, "observations_acumulado no puede estar vacío"
    cortes = {o["period_acumulado"].split(" ")[0] for o in acum}
    assert len(cortes) == 1, f"se mezclan cortes en acumulado comparable: {cortes}"
    last_ac = acum[-1]
    assert last_ac["period"] == "2026"
    assert last_ac["period_acumulado"] == "Ene-Jun 26"
    assert last_ac["values"][0] == 34968
    assert round(last_ac["values"][4], 3) == 0.02

    # Métricas
    assert ind["metrics"]["acumulado"]["valor"] == 34968
    assert round(ind["metrics"]["acumulado"]["variacion_anual_pct"], 3) == 0.021
    assert round(ind["metrics"]["flujo_trimestral"]["valor"], 2) == 10464.95
    assert round(ind["metrics"]["flujo_trimestral"]["variacion_anual_pct"], 3) == -0.035
    assert ind["metrics"]["corte_referencia"] == "Ene-Jun"
    assert ind["source_mode"] in ("structured", "manual_fallback")
    assert "source_mode" in ind["metrics"]


@pytest.mark.skipif(not (DATA_DIR / "ied_manual_2026_2t.json").exists(), reason="manual 2T no presente")
def test_source_mode_priority():
    res = ied.fetch()
    assert res.ok, res.warnings
    ind = res.data["IED"]
    # Si el XLS estructurado contiene el corte actual, source_mode debe ser structured.
    # En este entorno el resumen histórico ya contiene 2026 2T, por lo que se espera structured.
    assert ind["source_mode"] == "structured"
    assert ind["metrics"]["source_mode"] == "structured"


def test_ied_integration_final_output():
    """Construye IED y verifica la SALIDA FINAL que persistiría en data/indicadores.json."""
    res = ied.fetch()
    assert res.ok, res.warnings
    raw = res.data["IED"]

    from build_data import merge_indicator
    import lib_data as L
    payload = L.load_data()
    merge_indicator(payload, "IED", raw)

    # Reproducir el merge de métricas de lib_metrics
    import lib_metrics
    kpicfg, _ = lib_metrics._kpicfg_and_colors()
    ied_metrics = lib_metrics._ied_metrics(payload["indicators"]["IED"], kpicfg)
    payload["indicators"]["IED"].setdefault("metrics", {})
    payload["indicators"]["IED"]["metrics"].update(ied_metrics or {})

    ind = payload["indicators"]["IED"]

    # El periodo final no puede ser 1T-26
    assert ind["last_observation"] == "2T-26", f"last_observation={ind['last_observation']}"
    assert ind["periodo_referencia"] == "Ene-Jun 26", f"periodo_referencia={ind['periodo_referencia']}"

    # Acumulado y flujo
    assert ind["metrics"]["acumulado"]["valor"] == 34968
    assert round(ind["metrics"]["acumulado"]["variacion_anual_pct"], 3) == 0.021
    assert round(ind["metrics"]["flujo_trimestral"]["valor"], 2) == 10464.95
    assert round(ind["metrics"]["flujo_trimestral"]["variacion_anual_pct"], 2) == -0.04

    # Series
    assert len(ind["observations"]) > 0
    assert len(ind["observations_acumulado"]) > 0
    assert ind["observations"][-1]["period"] == "2T-26"
    assert ind["observations_acumulado"][-1]["period"] == "2026"

    # Componentes no vacíos
    assert ind["metrics"]["componentes_acumulado"]
    assert ind["metrics"]["composicion_tipo"]
    assert ind["metrics"]["composicion_sector"]

    # Metadata
    assert ind["fecha_publicacion"] == "24 de agosto de 2026"
    assert "source_mode" in ind

    # Mapeo de KPIs: acumulado es principal, flujo es secundario
    kpi = ind["metrics"]["kpi"]
    assert kpi["ultimoRaw"] == 34968, f"kpi.ultimoRaw={kpi['ultimoRaw']}"
    assert kpi["ultimoP"] == "Ene-Jun 26", f"kpi.ultimoP={kpi['ultimoP']}"
    assert kpi["varText"] == "+2.1%", f"kpi.varText={kpi['varText']}"
    assert kpi["flujoRaw"] == 10464.95, f"kpi.flujoRaw={kpi['flujoRaw']}"
    assert kpi["flujoP"] == "2T-26", f"kpi.flujoP={kpi['flujoP']}"
    assert ind["metrics"]["yoy"]["text"] == "-3.5%", f"yoy.text={ind['metrics']['yoy']['text']}"

    # Resumen/lectura sin genéricos de max/min/adverso
    resumen = " ".join(ind["metrics"].get("resumen", []))
    assert "máximo" not in resumen.lower()
    assert "mínimo" not in resumen.lower()
    assert "adverso" not in resumen.lower()
    assert "favorable" not in resumen.lower()
    assert "34,968" in resumen
    assert "10,465" in resumen


@pytest.mark.skipif(not (DATA_DIR / "ied_manual_2026_2t.json").exists(), reason="manual 2T no presente")
def test_labels_and_separation():
    res = ied.fetch()
    assert res.ok, res.warnings
    ind = res.data["IED"]
    assert ind["metrics"]["acumulado"]["valor"] == 34968
    assert ind["metrics"]["flujo_trimestral"]["valor"] == 10464.95
    assert ind["metrics"]["acumulado"]["valor"] != ind["metrics"]["flujo_trimestral"]["valor"]
    assert round(ind["metrics"]["acumulado"]["variacion_anual_pct"], 3) == 0.021
    assert round(ind["metrics"]["flujo_trimestral"]["variacion_anual_pct"], 3) == -0.035
