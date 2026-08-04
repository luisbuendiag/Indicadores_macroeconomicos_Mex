"""Conector Banco de México (SIE). Requiere BANXICO_TOKEN.

Descarga series diarias/semanales (tipo de cambio FIX, tasa objetivo, reservas
internacionales) y las agrega a frecuencia mensual (último dato del mes) para el
dashboard. Si no hay token, devuelve SourceResult(ok=False) y el pipeline conserva
los datos existentes.
"""
from __future__ import annotations

import os
from collections import OrderedDict
from datetime import datetime

from .base import SourceResult, http_get_json

BASE = ("https://www.banxico.org.mx/SieAPIRest/service/v1/series/{series}/"
        "datos/{start}/{end}?token={token}")
MESES_ABBR = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
              "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

FMT = {
    "TIPOCAMBIO": "fx",
    "TASA": "pct-raw",
    "RESERVAS": "usd",
}


def _monthly_last(datos, factor: float = 1.0) -> list[dict]:
    """Agrega observaciones diarias/semanales al último valor de cada mes."""
    by_month: OrderedDict[tuple[int, int], float] = OrderedDict()
    for d in datos:
        try:
            dt = datetime.strptime(d["fecha"], "%d/%m/%Y")
            val = float(d["dato"].replace(",", "")) * factor
        except (ValueError, KeyError, TypeError):
            continue
        key = (dt.year, dt.month)
        by_month[key] = val  # el último recorrido gana (datos vienen ordenados asc)
    obs = []
    for (y, m), v in by_month.items():
        period = f"{MESES_ABBR[m - 1]} {str(y)[2:]}"
        obs.append({"period": period, "values": [round(v, 6)]})
    return obs


def fetch(config: dict, start: str = "2018-01-01", end: str | None = None) -> SourceResult:
    token = os.environ.get("BANXICO_TOKEN")
    if not token:
        return SourceResult(False, warnings=[
            "BANXICO_TOKEN ausente: se omiten tipo de cambio, tasa objetivo y reservas; "
            "se conservan datos previos."])
    end = end or datetime.today().strftime("%Y-%m-%d")
    out, warns = {}, []
    for key, meta in config.get("banxico", {}).items():
        if key.startswith("_"):
            continue
        serie = meta.get("serie")
        if not serie:
            continue
        url = BASE.format(series=serie, start=start, end=end, token=token)
        try:
            raw = http_get_json(url)
            datos = raw.get("bmx", {}).get("series", [{}])[0].get("datos", [])
        except Exception as e:  # noqa: BLE001 - resiliencia de red
            warns.append(f"Banxico {key} ({serie}) falló: {e}. Se conservan datos previos.")
            continue
        if not datos:
            warns.append(f"Banxico {key} ({serie}): respuesta sin observaciones.")
            continue

        factor = float(meta.get("factor", 1.0))
        obs = _monthly_last(datos, factor)
        if not obs:
            warns.append(f"Banxico {key}: sin observaciones mensuales.")
            continue

        last = obs[-1]
        out[key] = {
            "key": key,
            "nombre": meta.get("nombre"),
            "frecuencia": meta.get("frecuencia", "Mensual"),
            "unidad": meta.get("unidad"),
            "columns": [{"label": meta.get("nombre"), "index": 0, "fmt": FMT.get(key, "num")}],
            "observations": obs,
            "last_observation": last["period"],
            "fuente": {
                "nombre": "Banco de México (SIE)",
                "serie": serie,
                "link": meta.get("link", "https://www.banxico.org.mx/SieAPIRest/"),
                "metodo": "Banxico SIE API",
            },
            "api_meta": {
                "serie": serie,
                "n_obs": len(obs),
                "ultimo_valor": last["values"][0],
                "ultima_observacion": last["period"],
                "ultima_ym": None,
            },
        }
    return SourceResult(bool(out), out, warns)
