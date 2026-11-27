"""Valida que lib_metrics coincida con el motor JS del dashboard."""
from __future__ import annotations

import json
import copy
import pytest

import lib_data as L
import lib_format as F
import lib_metrics as M


def _payload():
    payload=copy.deepcopy(L.load_data())
    i=payload['indicators']['IGAE']
    i['observations']=[{'period':'Abr 25','values':[100,None,None]+[None]*6},
                       {'period':'Abr 26','values':[53.9,None,None]+[None]*6},
                       {'period':'May 26','values':[108.5,None,None]+[None]*6},
                       {'period':'Jun 26','values':[107.4,-.001,.028191]+[None]*6}]
    i['last_observation']='Jun 26'
    return payload


def test_igae_kpi():
    payload = _payload()
    metrics = M.compute_all_metrics(payload)
    kpi = metrics["IGAE"]["kpi"]
    assert kpi["ultimoP"] == "Jun 26"
    assert kpi["ultimoFmt"] == "107.4"
    assert kpi["varText"] == "-0.1%"
    assert kpi["varMag"] == -0.1
    assert kpi["yoyText"] == "+2.8%"
    assert kpi["yoyLabel"] == "Var. anual original"
    assert kpi["assessment"] == "adverso"
    assert kpi["semaforo"] == "malo"


def test_igae_analysis():
    payload = _payload()
    metrics = M.compute_all_metrics(payload)
    a = metrics["IGAE"]["analysis"]
    assert len(a) == 2
    assert "107.4 puntos" in a[0]
    assert "-0.10%" in a[0]
    assert "108.5 puntos (mayo de 2026)" in a[1]
    assert "53.9 puntos (abril de 2026)" in a[1]


def test_inpc_kpi():
    payload = _payload()
    metrics = M.compute_all_metrics(payload)
    kpi = metrics["INPC"]["kpi"]
    inpc = payload["indicators"]["INPC"]
    vals = inpc["observations"][-1]["values"]
    prev = inpc["observations"][-2]["values"]
    d = vals[2] - prev[2]
    expected_var = ("+" if d >= 0 else "") + F._to_fixed(d, 1, 1) + " puntos porcentuales"
    assert kpi["ultimoP"] == inpc["observations"][-1]["period"]
    assert kpi["ultimoFmt"] == F.fmt_val(vals[2], "pct-rate")
    assert kpi["varText"] == expected_var
    assert round(kpi["varMag"], 4) == round(d, 4)
    assert kpi["yoyText"] == "—"
    assert kpi["assessment"] == "neutral"
    assert kpi["semaforo"] == "estable"


def test_inpc_uses_official_two_decimal_precision():
    ind = {"key": "INPC", "observations": [
        {"period": "Sep 26", "values": [None, None, 3.64]},
        {"period": "Oct 26", "values": [None, None, 3.75]},
    ]}
    assert M.compute_kpi(ind)["ultimoFmt"] == "3.75%"
    assert F.fmt_val(3.80, "pct-rate") == "3.80%"
    assert F.fmt_val(3.59, "pct-rate") == "3.59%"


def test_inpc_analysis():
    payload = _payload()
    metrics = M.compute_all_metrics(payload)
    a = metrics["INPC"]["analysis"]
    inpc = payload["indicators"]["INPC"]
    vals = inpc["observations"][-1]["values"]
    prev = inpc["observations"][-2]["values"]
    d = vals[2] - prev[2]
    expected_var = ("+" if d >= 0 else "") + F._to_fixed(d, 1, 1) + " puntos porcentuales"
    assert len(a) == 2
    assert "inflación general anual" in a[0]
    assert expected_var in a[0]
    assert "Banco de México" in a[1]


def test_desocup_kpi():
    payload = _payload()
    indicator = payload["indicators"]["DESOCUP"]
    indicator["observations"] = [
        {"period": "Sep 25", "values": [3.0]},
        {"period": "Ago 26", "values": [3.1]},
        {"period": "Sep 26", "values": [2.8]},
    ]
    indicator["last_observation"] = "Sep 26"
    indicator["enoe_mensual"] = {
        "periodo": "Sep 26",
        "tasas": {"unemployment": {"anual_original_pp": -0.1, "mensual_desest_pp": -0.1}},
    }
    metrics = M.compute_all_metrics(payload)
    kpi = metrics["DESOCUP"]["kpi"]
    assert kpi["ultimoFmt"] == "2.8%"
    assert kpi["varLabel"] == "Cambio anual original"
    assert kpi["varMag"] == pytest.approx(-0.1)

    indicator.pop("enoe_mensual")
    kpi = M.compute_all_metrics(payload)["DESOCUP"]["kpi"]
    assert kpi["varMag"] == pytest.approx(-0.2)
    assert kpi["cards"][0]["momRaw"] is None
    assert kpi["assessment"] in ("favorable", "adverso", "neutral")
    assert kpi["semaforo"] in ("bueno", "malo", "estable")


def test_desocup_analysis():
    payload = _payload()
    metrics = M.compute_all_metrics(payload)
    a = metrics["DESOCUP"]["resumen"]
    assert len(a) >= 1
    assert "tasa de desocupación" in a[0]
    assert "p.p." in a[0]
    assert "INEGI/ENOE" not in a[0]


def test_format_val():
    from lib_format import fmt_val, per_long, en_frase, period_to_date
    assert fmt_val(108.595752, "idx") == "108.6"
    assert fmt_val(-0.003, "pct-frac") == "-0.3%"
    assert fmt_val(3.365977, "pct-raw") == "3.4%"
    assert fmt_val(24973976.071, "bill") == "24.97 billones de pesos de 2018"
    assert per_long("May 26 O") == "mayo de 2026"
    assert per_long("1T-26 P") == "primer trimestre de 2026"
    assert en_frase("1T-26 P") == "el primer trimestre de 2026"
    assert period_to_date("Jun 26").month == 6
    assert period_to_date("2T-25").month == 4


@pytest.mark.parametrize("accumulated_original", [None, 0.018])
def test_pib_yoy_trimestral(accumulated_original):
    payload = _payload()
    values = [0.009, 0.031, 0.032, 0.019]
    if accumulated_original is not None:
        values.append(accumulated_original)
    pib = payload["indicators"]["PIB"]
    pib["last_observation"] = "3T-26 P"
    pib["observations"] = [{"period": "3T-26 P", "values": values}]
    kpi = M.compute_all_metrics(payload, offline=True)["PIB"]["kpi"]
    assert kpi["ultimoFmt"] == "+0.9%"
    assert kpi["varText"] == "+3.2%"
    assert kpi["varLabel"] == "Var. anual original"
    assert kpi["yoyText"] == "+3.1%"
    assert kpi["yoyLabel"] == "Var. anual desest."
    assert kpi["qoqLabel"] == "Var. trimestral desest."
    assert kpi["ytdRaw"] == accumulated_original
    assert kpi["ytdText"] == ("+1.8%" if accumulated_original is not None else "—")
    assert kpi["ytdLabel"] == "Acumulado enero–septiembre"
    assert kpi["ytdBasis"] == "Cifras originales"


def test_profile_annual_rates_use_original_series():
    payload = _payload()
    metrics = M.compute_all_metrics(payload, offline=True)
    for key, monthly, annual in (
        ("IMAI", 1, 4), ("CONSUMO", 1, 3), ("IMFBCF", 1, 26), ("EMIM", 3, 2)
    ):
        item = metrics[key]
        kpi = item["kpi"]
        values = payload["indicators"][key]["observations"][kpi["lastI"]]["values"]
        assert item["annualVar"]["label"] == "Var. anual original"
        assert item["annualVar"]["mag"] == values[annual] * 100
        assert kpi["varMag"] == values[monthly] * 100
