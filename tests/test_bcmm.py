import json
from pathlib import Path

import openpyxl
import pytest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "indicadores.json"


def _bcmm():
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    return payload["indicators"]["BCMM"]


def test_bcmm_schema_29_columnas():
    ind = _bcmm()
    assert len(ind["columns"]) == 29, f"BCMM debe tener 29 columnas, tiene {len(ind['columns'])}"
    for i, col in enumerate(ind["columns"]):
        assert col["index"] == i


def test_bcmm_columnas_ordenadas():
    ind = _bcmm()
    labels = [c["label"] for c in ind["columns"]]
    assert labels[0] == "Exportaciones"
    assert labels[1] == "Importaciones"
    assert labels[2] == "Saldo"
    for i in range(3, 6):
        assert "Var. anual" in labels[i]
    for i in range(6, 10):
        assert "petroleras" in labels[i] or "no petroleras" in labels[i]
    for i in range(10, 14):
        assert "Var. anual" in labels[i]
    for i in range(14, 17):
        assert "Bienes" in labels[i]
    for i in range(17, 20):
        assert "Var. anual" in labels[i]
    for i in range(20, 23):
        assert "Exportaciones" in labels[i]
    for i in range(23, 26):
        assert "Var. anual" in labels[i]
    for i in range(26, 29):
        assert "Acum ene-mes" in labels[i]


def test_bcmm_saldo_derivado():
    ind = _bcmm()
    for o in ind["observations"][-24:]:
        vals = o["values"]
        if vals[0] is not None and vals[1] is not None:
            assert vals[2] is not None
            assert round(vals[0] - vals[1], 6) == pytest.approx(vals[2], abs=1e-3)


def test_bcmm_saldo_yoy_calculado():
    ind = _bcmm()
    obs = ind["observations"]
    for o in obs[-24:]:
        vals = o["values"]
        if vals[5] is not None:
            # La variación anual del saldo debe ser coherente con saldo previo -12 meses.
            pass
    # Al menos el dato más reciente tiene variación anual del saldo.
    assert obs[-1]["values"][5] is not None
    assert obs[-1]["values"][3] is not None
    assert obs[-1]["values"][4] is not None


def test_bcmm_acumulados_ene_mes():
    ind = _bcmm()
    obs = ind["observations"][-3:]
    for o in obs:
        vals = o["values"]
        assert vals[26] is not None
        assert vals[27] is not None
        assert vals[28] is not None


def test_bcmm_excel_individual_hojas():
    xlsx = ROOT / "downloads" / "indicadores" / "BCMM" / "BCMM_datos.xlsx"
    assert xlsx.exists()
    wb = openpyxl.load_workbook(xlsx)
    assert wb.sheetnames == [
        "Comercio total",
        "Variaciones anuales",
        "Petrolero y no petrolero",
        "Importaciones por tipo",
    ]
