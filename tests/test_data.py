import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "indicadores.json"
PERIOD_RE = re.compile(r"^([1-4]T-\d{2}|[A-Za-zÁÉÍÓÚáéíóú]{3}\s*\d{2})")


@pytest.fixture(scope="module")
def payload():
    return json.loads(DATA.read_text(encoding="utf-8"))


def test_file_exists():
    assert DATA.exists(), "data/indicadores.json debe existir"


def test_meta_and_order(payload):
    assert "meta" in payload and "indicators" in payload
    assert payload["meta"]["base_year"] == 2018
    assert isinstance(payload.get("order"), list) and payload["order"]


PENDING_STATES = {"pendiente de token", "pendiente de confirmar serie",
                  "no disponible", "error de fuente"}


def test_indicators_shape(payload):
    for key, ind in payload["indicators"].items():
        assert ind["columns"], f"{key} sin columnas"
        # Los scaffolds (indicadores a la espera de token/serie) pueden no tener
        # observaciones todavía; no deben inventarse cifras.
        if not ind["observations"]:
            assert ind.get("estado") in PENDING_STATES or ind.get("origen_dato") == "pendiente", \
                f"{key} sin observaciones y sin estado pendiente declarado"
            continue
        for o in ind["observations"]:
            assert PERIOD_RE.match(o["period"]), f"{key}: periodo inválido {o['period']}"
            assert len(o["values"]) == len(ind["columns"]), f"{key}: columnas/valores desalineados"


def test_desocup_source_is_inegi(payload):
    # Regla del usuario: la fuente principal de desocupación debe ser INEGI/ENOE.
    fuente = payload["indicators"]["DESOCUP"]["fuente"]["nombre"].lower()
    assert "inegi" in fuente and "enoe" in fuente


def test_no_critical_validation_errors(payload):
    import validate as V
    errors, _ = V.validate(payload)
    assert not errors, f"No debe haber errores críticos tras overrides: {errors}"


def test_duplicate_flagged_as_revision(payload):
    # Feb-26 de IMAI y CONSUMO ya no son duplicados sospechosos y tienen valores reales.
    for key in ("IMAI", "CONSUMO"):
        ind = payload["indicators"][key]
        feb = [o for o in ind["observations"] if o["period"].startswith("Feb 26")][0]
        assert feb["values"][0] is not None, f"{key} Feb-26 debe tener valor real"
    # Los dos índices son distintos (IMAI ~100.8, CONSUMO ~111.4).
    imai_feb = next(o for o in payload["indicators"]["IMAI"]["observations"] if o["period"].startswith("Feb 26"))
    cons_feb = next(o for o in payload["indicators"]["CONSUMO"]["observations"] if o["period"].startswith("Feb 26"))
    assert imai_feb["values"][0] != cons_feb["values"][0]


# Regresión: variaciones oficiales del boletín INEGI.
# Se comparan con los valores públicados en los boletines más recientes.
@pytest.mark.parametrize("key,monthly_col,annual_col,expected_monthly,expected_annual", [
    ("CONSUMO", 1, 2, 0.001, 0.021),
    ("IMFBCF", 1, 2, 0.04, 0.051),
    ("IGAE", 3, 4, -0.003, 0.02),
])
def test_bulletin_variations_monthly_and_annual(payload, key, monthly_col, annual_col, expected_monthly, expected_annual):
    ind = payload["indicators"][key]
    last = ind["observations"][-1]
    assert last["values"][monthly_col] == pytest.approx(expected_monthly, abs=1e-4)
    assert last["values"][annual_col] == pytest.approx(expected_annual, abs=1e-4)


def test_pib_bulletin_variations(payload):
    pib = payload["indicators"]["PIB"]
    last = pib["observations"][-1]
    # Trimestral desestacionalizada y anual desestacionalizada del PIBT.
    assert last["values"][2] == pytest.approx(-0.006, abs=1e-4)
    assert last["values"][3] == pytest.approx(0.004, abs=1e-4)
    # El nivel debe conservarse de la serie BIE.
    assert last["values"][0] == pytest.approx(24973976.071, abs=1e-3)


def test_pibsec_terciarias_bulletin_variations(payload):
    pibsec = payload["indicators"]["PIBSEC"]
    last = pibsec["observations"][-1]
    assert last["values"][3] == pytest.approx(-0.004, abs=1e-4)
    assert last["values"][4] == pytest.approx(0.011, abs=1e-4)
