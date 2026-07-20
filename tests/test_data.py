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
    # Feb-26 de IMAI y CONSUMO debe estar anulado y marcado como revisión.
    for key in ("IMAI", "CONSUMO"):
        ind = payload["indicators"][key]
        assert ind.get("data_quality"), f"{key} debe tener marca de calidad"
        feb = [o for o in ind["observations"] if o["period"].startswith("Feb 26")][0]
        assert feb["values"][0] is None, f"{key} Feb-26 debe estar anulado (en revisión)"
