"""Valida que lib_metrics coincida con el motor JS del dashboard."""
from __future__ import annotations

import json

import lib_data as L
import lib_metrics as M


def _payload():
    return L.load_data()


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
    assert "53.9 puntos (abril de 1995)" in a[1]


def test_inpc_kpi():
    payload = _payload()
    metrics = M.compute_all_metrics(payload)
    kpi = metrics["INPC"]["kpi"]
    assert kpi["ultimoP"] == "Jul 26"
    assert kpi["ultimoFmt"] == "3.1%"
    assert kpi["varText"] == "-0.2 puntos porcentuales"
    assert round(kpi["varMag"], 4) == -0.2483
    assert kpi["yoyText"] == "—"
    assert kpi["assessment"] == "neutral"
    assert kpi["semaforo"] == "estable"


def test_inpc_analysis():
    payload = _payload()
    metrics = M.compute_all_metrics(payload)
    a = metrics["INPC"]["analysis"]
    assert len(a) == 2
    assert "inflación general anual" in a[0]
    assert "-0.2 puntos porcentuales" in a[0]
    assert "Banco de México" in a[1]


def test_desocup_kpi():
    payload = _payload()
    metrics = M.compute_all_metrics(payload)
    kpi = metrics["DESOCUP"]["kpi"]
    assert kpi["ultimoFmt"] == "2.9%"
    assert kpi["varText"] == "+0.1 p.p."
    assert kpi["yoyText"] == "+0.2 p.p."
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


def test_pib_yoy_trimestral():
    payload = _payload()
    metrics = M.compute_all_metrics(payload)
    kpi = metrics["PIB"]["kpi"]
    assert kpi["ultimoFmt"] == "+1.5%"
    assert kpi["varText"] == "+2.1%"
    assert kpi["varLabel"] == "Var. anual desest."
    assert kpi["yoyText"] == "+2.2%"
    assert kpi["yoyLabel"] == "Var. anual original"
    assert kpi["ytdText"] == "+1.2%"
