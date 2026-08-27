"""Tests de integridad para el indicador INPP."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "indicadores.json"


@pytest.fixture(scope="module")
def payload():
    return json.loads(DATA.read_text(encoding="utf-8"))


def test_inpp_in_principal_and_order(payload):
    assert "INPP" in payload["order"], "INPP debe estar en el orden"
    pos = payload["order"].index("INPP")
    inpc_pos = payload["order"].index("INPC")
    assert pos == inpc_pos + 1, "INPP debe ir inmediatamente después de INPC"


def test_inpp_has_columns_and_observations(payload):
    ind = payload["indicators"].get("INPP")
    assert ind, "INPP debe existir en indicadores"
    assert ind["columns"], "INPP debe tener columnas"
    assert ind["observations"], "INPP debe tener observaciones"
    assert len(ind["observations"][0]["values"]) == len(ind["columns"])


def test_inpp_main_variations_are_pct_raw(payload):
    ind = payload["indicators"]["INPP"]
    cols = ind["columns"]
    # Las columnas 1-3 y 5-7 son variaciones (pct-raw).
    for i in range(8):
        assert cols[i]["fmt"] in ("idx", "pct-raw")


def test_inpp_last_observation_consistent(payload):
    ind = payload["indicators"]["INPP"]
    last = ind["observations"][-1]
    assert last["period"]
    assert last["values"][0] is not None, "índice con petróleo presente"
    assert last["values"][2] is not None, "variación anual con petróleo presente"
    assert last["values"][4] is not None, "índice sin petróleo presente"
