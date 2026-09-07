"""Tests del Sistema de Indicadores Cíclicos (SIC) y la reclasificación IED.

Verifica la clasificación oficial (SIC principal / IED complementario),
los IDs de series BIE del SIC, el esquema de columnas y la calidad de los datos.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "indicadores.json"
META_FILE = ROOT / "config" / "indicadores_meta.json"
SERIES_FILE = ROOT / "config" / "series.json"
CONFIG_JS = ROOT / "assets" / "js" / "config.js"

# IDs oficiales BIE-BISE del SIC (verificados contra el Reloj de los ciclos
# económicos del INEGI y el boletín oficial).
SIC_COINCIDENTE = "214293"
SIC_ADELANTADO = "214307"
SIC_COMP_COINCIDENTE = {"214295", "214297", "214299", "214301", "214303", "214305"}
SIC_COMP_ADELANTADO = {"214309", "214311", "214313", "214315", "214317", "214319"}
SIC_ALL_IDS = {SIC_COINCIDENTE, SIC_ADELANTADO} | SIC_COMP_COINCIDENTE | SIC_COMP_ADELANTADO


@pytest.fixture(scope="module")
def meta():
    return json.loads(META_FILE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def payload():
    return json.loads(DATA.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def sic(payload):
    ind = payload["indicators"].get("SIC")
    assert ind is not None, "SIC no existe en data/indicadores.json"
    return ind


def _parse_js_array(name: str) -> list[str]:
    src = CONFIG_JS.read_text(encoding="utf-8")
    m = re.search(rf"{re.escape(name)}\s*=\s*\[(.*?)\]", src, re.S)
    assert m, f"no se encontró {name} en config.js"
    return re.findall(r'"([^"]+)"', m.group(1))


# ---------------- Clasificación ----------------

def test_sic_es_principal_y_posicion(meta):
    """SIC es indicador principal, va después de PIBSEC y aparece una sola vez."""
    assert meta["principal"].count("SIC") == 1
    idx = meta["principal"].index("SIC")
    assert meta["principal"][idx - 1] == "PIBSEC"
    assert meta["principal"][idx + 1] == "IOAE"
    assert "SIC" not in meta["complementario"]
    assert meta["profile"]["SIC"]["clasificacion"] == "principal"
    assert meta["profile"]["SIC"]["serie_confirmada"] is True


def test_ied_es_complementario(meta):
    """IED pasa a Entorno financiero: una sola vez, no es principal."""
    assert meta["complementario"].count("IED") == 1
    assert "IED" not in meta["principal"]
    assert meta["profile"]["IED"]["clasificacion"] == "complementario"


def test_sic_en_config_js():
    """PRINCIPAL de config.js contiene SIC tras PIBSEC; COMPLEMENTARIOS inicia con IED."""
    principal = _parse_js_array("PRINCIPAL")
    complementarios = _parse_js_array("COMPLEMENTARIOS")
    assert principal.count("SIC") == 1
    assert principal.index("SIC") == 2
    assert "IED" not in principal
    assert complementarios[0] == "IED"
    assert "SIC" not in complementarios


# ---------------- Series oficiales ----------------

def test_sic_series_oficiales_bie():
    """Las series del SIC usan los IDs oficiales del BIE, ya confirmados."""
    series = json.loads(SERIES_FILE.read_text(encoding="utf-8"))
    specs = series["inegi"].get("SIC")
    assert specs, "No hay sección SIC en config/series.json (inegi)"
    assert len(specs) == 18
    ids = {s["serie"] for s in specs}
    assert SIC_ALL_IDS <= ids, f"Faltan series SIC: {SIC_ALL_IDS - ids}"
    for s in specs:
        assert s["serie"] is not None
        assert s.get("confirmar") is False, f"SIC {s.get('nombre')} marcado para confirmar"
        assert s.get("db") == "BIE-BISE"
        assert s.get("geo") == "00"
        assert s.get("unidad") == "Puntos"
        assert s.get("frecuencia") == "Mensual"
    # Columnas objetivo: 0-1 compuestos, 2-5 diferencias, 6-17 componentes.
    cols = sorted(s["columna_objetivo"] for s in specs)
    assert cols == list(range(18))


# ---------------- Esquema y datos ----------------

def test_sic_columnas(sic):
    """SIC tiene 18 columnas: 2 compuestos + 4 diferencias + 12 componentes."""
    cols = sic.get("columns", [])
    assert len(cols) == 18
    labels = [c["label"] for c in cols]
    assert "Coincidente" in labels[0]
    assert "Adelantado" in labels[1]
    # Las diferencias se expresan en puntos.
    for c in cols[2:6]:
        assert "puntos" in c["label"].lower(), c["label"]


def test_sic_observaciones_mensuales(sic):
    """Observaciones mensuales, sin duplicados, con valores en puntos plausibles."""
    obs = sic.get("observations", [])
    assert len(obs) > 400, f"SIC debería tener historia desde 1980 ({len(obs)})"
    periods = [o["period"] for o in obs]
    assert len(periods) == len(set(periods)), "periodos duplicados en SIC"
    coinc = [o["values"][0] for o in obs if o["values"] and o["values"][0] is not None]
    adel = [o["values"][1] for o in obs if o["values"] and len(o["values"]) > 1 and o["values"][1] is not None]
    assert coinc and adel
    # Componentes cíclicos: oscilan alrededor de 100.
    assert all(60 <= v <= 140 for v in coinc), "Coincidente fuera de rango plausible"
    assert all(60 <= v <= 140 for v in adel), "Adelantado fuera de rango plausible"


def test_sic_diferencias_en_puntos(sic):
    """La columna 2 es la diferencia mensual del Coincidente (puntos, no %)."""
    obs = [o for o in sic["observations"] if o["values"] and o["values"][0] is not None]
    assert len(obs) > 24
    last = obs[-1]
    prev = obs[-2]
    if last["values"][2] is not None and prev["values"][0] is not None:
        esperado = last["values"][0] - prev["values"][0]
        assert abs(last["values"][2] - esperado) < 1e-6, (
            f"Dif. mensual Coincidente {last['values'][2]} != {esperado}"
        )
    # Las diferencias mensuales deben ser magnitudes pequeñas (puntos, no %).
    diffs = [o["values"][2] for o in obs if len(o["values"]) > 2 and o["values"][2] is not None]
    assert diffs and max(abs(d) for d in diffs) < 10, "diferencias mensuales fuera de escala de puntos"


def test_sic_componentes_presentes(sic):
    """Las 12 componentes oficiales tienen historia en las columnas 6-17."""
    obs = sic["observations"]
    for col in range(6, 18):
        vals = [o["values"][col] for o in obs if len(o["values"]) > col and o["values"][col] is not None]
        assert len(vals) > 200, f"Componente col {col} con historia insuficiente"


def test_sic_periodo_referencia(sic):
    """`last_observation` corresponde al último mes con cifra del Coincidente
    (el periodo de referencia del boletín oficial). El Adelantado puede tener
    un mes adicional, que se conserva en las observaciones."""
    obs = sic["observations"]
    last = obs[-1]
    vals = last["values"]
    assert vals[0] is not None or vals[1] is not None, (
        "El último periodo del SIC no tiene cifra de Coincidente ni Adelantado"
    )
    coinc_periods = [o["period"] for o in obs if o["values"] and o["values"][0] is not None]
    assert coinc_periods, "SIC sin observaciones del Coincidente"
    assert sic.get("last_observation") == coinc_periods[-1]
    # El último periodo del vector puede ser más reciente si el Adelantado va adelante.
    assert obs[-1]["period"] >= sic["last_observation"] or obs[-1]["values"][1] is not None


def test_sic_fuente_y_unidad(sic):
    assert sic.get("unidad") == "Puntos"
    assert sic.get("frecuencia") == "Mensual"
    fuente = sic.get("fuente") or {}
    assert "inegi" in (fuente.get("nombre") or "").lower()


# ---------------- Métricas ----------------

def test_sic_metrics():
    metrics_path = ROOT / "data" / "metrics.json"
    if not metrics_path.exists():
        pytest.skip("metrics.json no generado")
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    sic = metrics["indicators"].get("SIC")
    assert sic, "SIC sin métricas"
    kpi = sic.get("kpi") or {}
    assert kpi.get("ultimoRaw") is not None
    assert "puntos" in (kpi.get("varText") or "")
    assert (kpi.get("coincidente") or {}).get("valor") is not None
    assert (kpi.get("adelantado") or {}).get("valor") is not None
    assert sic.get("resumen"), "SIC sin resumen"


# ---------------- Transformación yoy_abs ----------------

def test_yoy_abs_transform():
    """yoy_abs calcula la diferencia absoluta respecto a 12 meses atrás."""
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    from sources import inegi
    obs = [{"ym": f"2025-{m:02d}", "value": 100.0 + m, "period": f"2025-{m:02d}"} for m in range(1, 13)]
    obs += [{"ym": f"2026-{m:02d}", "value": 100.0 + m + 2, "period": f"2026-{m:02d}"} for m in range(1, 13)]
    out = inegi._transform_observations(obs, "yoy_abs")
    by_ym = {o["ym"]: o["value"] for o in out}
    # 2025 no tiene año base: sólo 2026 tiene diferencia.
    assert all(ym.startswith("2026") for ym in by_ym)
    assert abs(by_ym["2026-03"] - 2.0) < 1e-9
