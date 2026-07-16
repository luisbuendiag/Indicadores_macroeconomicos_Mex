"""Conector Banco de México (SIE). Requiere BANXICO_TOKEN.

Descarga series diarias (tipo de cambio FIX, tasa objetivo) y las agrega a
frecuencia mensual (último dato del mes) para el dashboard. Si no hay token,
devuelve SourceResult(ok=False) y el pipeline conserva los datos existentes.
"""
from __future__ import annotations

import os
from collections import OrderedDict
from datetime import datetime

from .base import SourceResult, http_get_json

BASE = "https://www.banxico.org.mx/SieAPIRest/service/v1/series/{series}/datos/{start}/{end}?token={token}"
MESES_ABBR = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def _monthly_last(datos, is_pct):
    """Agrega observaciones diarias al último valor de cada mes."""
    by_month = OrderedDict()
    for d in datos:
        try:
            dt = datetime.strptime(d["fecha"], "%d/%m/%Y")
            val = float(d["dato"].replace(",", ""))
        except (ValueError, KeyError):
            continue
        key = (dt.year, dt.month)
        by_month[key] = val  # el último recorrido gana (datos vienen ordenados asc)
    obs = []
    for (y, m), v in by_month.items():
        period = f"{MESES_ABBR[m - 1]} {str(y)[2:]}"
        obs.append({"period": period, "values": [v]})
    return obs


def fetch(config: dict, start="2018-01-01", end=None) -> SourceResult:
    token = os.environ.get("BANXICO_TOKEN")
    if not token:
        return SourceResult(False, warnings=["BANXICO_TOKEN ausente: se omiten tipo de cambio y tasa objetivo; se conservan datos previos."])
    end = end or datetime.today().strftime("%Y-%m-%d")
    out, warns = {}, []
    for key, meta in config.get("banxico", {}).items():
        serie = meta.get("serie")
        if not serie:
            continue
        url = BASE.format(series=serie, start=start, end=end, token=token)
        try:
            raw = http_get_json(url)
            datos = raw["bmx"]["series"][0].get("datos", [])
        except Exception as e:  # noqa: BLE001 - resiliencia de red
            warns.append(f"Banxico {key} ({serie}) falló: {e}. Se conservan datos previos.")
            continue
        is_pct = key == "TASA"
        obs = _monthly_last(datos, is_pct)
        if not obs:
            warns.append(f"Banxico {key}: sin observaciones.")
            continue
        out[key] = {
            "key": key, "nombre": meta.get("nombre"), "frecuencia": "Mensual",
            "unidad": meta.get("unidad"), "columns": [{"label": meta.get("nombre"), "index": 0, "fmt": "idx" if key == "TIPOCAMBIO" else "pct-raw"}],
            "observations": obs, "last_observation": obs[-1]["period"],
            "fuente": {"nombre": "Banco de México (SIE)", "serie": serie, "link": "https://www.banxico.org.mx/SieAPIRest/", "metodo": "Banxico SIE API"},
        }
    return SourceResult(bool(out), out, warns)
