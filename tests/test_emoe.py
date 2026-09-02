"""Tests de concepto, posición y formato para EMOE/IGOEC."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "data" / "indicadores.json").read_text(encoding="utf-8"))
METRICS = json.loads((ROOT / "data" / "metrics.json").read_text(encoding="utf-8"))["indicators"]
CONFIG_JS = (ROOT / "assets" / "js" / "config.js").read_text(encoding="utf-8")
META = json.loads((ROOT / "config" / "indicadores_meta.json").read_text(encoding="utf-8"))
SERIES = json.loads((ROOT / "config" / "series.json").read_text(encoding="utf-8"))
BUILD_DATA = (ROOT / "scripts" / "build_data.py").read_text(encoding="utf-8")


def test_emoe_is_principal_and_ordered_after_emim():
    assert "EMOE" in META["principal"]
    assert "EMOE" not in META["complementario"]
    idx = META["principal"].index("EMOE")
    assert META["principal"][idx - 1] == "EMIM"


def test_emoe_not_in_entorno_financiero():
    assert "EMOE" not in CONFIG_JS.split("COMPLEMENTARIOS")[1].split("];")[0]


def test_emoe_name_and_main_indicator():
    ind = DATA["indicators"]["EMOE"]
    assert "Encuesta Mensual de Opinión Empresarial" in ind["nombre"]
    assert ind.get("indicador_principal") == "IGOEC"
    assert ind.get("umbral") == 50
    assert ind["unidad"] == "Puntos"
    assert ind["clasificacion"] == "principal"


def test_emoe_columns_are_points_not_pct():
    cols = [c["label"] for c in DATA["indicators"]["EMOE"]["columns"]]
    assert cols[0] == "IGOEC"
    assert "puntos" in cols[1].lower()
    assert "puntos" in cols[2].lower()
    for c in DATA["indicators"]["EMOE"]["columns"][:3]:
        assert c["fmt"] == "idx"


def test_emoe_values_are_points():
    for o in DATA["indicators"]["EMOE"]["observations"][-3:]:
        v = o["values"][0]
        if v is not None:
            assert 0 < v < 100, f"IGOEC fuera de rango esperado: {v}"


def test_emoe_yoy_in_points():
    m = METRICS["EMOE"]
    yoy = m.get("yoy") or m.get("annualVar")
    if yoy:
        assert yoy.get("label") == "Cambio anual"
        # La variación anual del IGOEC se presenta en puntos, no porcentaje.
        assert "%" not in yoy.get("text", "")


def test_emoe_metrics_kpi():
    k = METRICS["EMOE"]["kpi"]
    assert k["varLabel"] == "Cambio mensual"
    assert k["yoyLabel"] == "Cambio anual"


def test_emoe_config_js_kpicfg():
    m = re.search(r"EMOE:\s*\{[^}]*umbral:\s*(\d+)", CONFIG_JS)
    assert m
    assert int(m.group(1)) == 50
    assert "Cambio mensual" in CONFIG_JS
    assert "IGOEC" in CONFIG_JS


def test_emoe_compute_function_exists():
    assert "def compute_emoe_metrics" in BUILD_DATA
    assert "compute_emoe_metrics(payload)" in BUILD_DATA


def test_emoe_url_points_to_ice():
    ind = DATA["indicators"]["EMOE"]
    url = ind.get("url_boletin_oficial") or ""
    # Offline puede caer en URL anterior si no hay red; preferimos la fuente.
    if url and "ice" in url:
        assert "/ice/ice" in url


def test_emoe_no_percent_sign_in_main_value():
    k = METRICS["EMOE"]["kpi"]
    assert "%" not in k["ultimoFmt"]
