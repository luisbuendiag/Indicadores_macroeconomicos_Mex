"""Conector Banco de México (SIE). Requiere BANXICO_TOKEN.

Descarga series diarias/semanales (tipo de cambio FIX, tasa objetivo, reservas
internacionales) y las agrega a frecuencia mensual (último dato del mes) para el
dashboard. Si no hay token, devuelve SourceResult(ok=False) y el pipeline conserva
los datos existentes.
"""
from __future__ import annotations

import os
from collections import OrderedDict
import calendar
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


def _raw_observations(datos, factor: float = 1.0) -> list[dict]:
    """Conserva observaciones diarias/semanales originales con periodo ISO."""
    obs = []
    for d in datos:
        try:
            dt = datetime.strptime(d["fecha"], "%d/%m/%Y")
            val = float(d["dato"].replace(",", "")) * factor
        except (ValueError, KeyError, TypeError):
            continue
        obs.append({"period": dt.strftime("%Y-%m-%d"), "values": [round(val, 6)]})
    return obs


def _monthly_last(datos, factor: float = 1.0, end: str | None = None) -> list[dict]:
    """Agrega observaciones diarias/semanales al último valor de cada mes.

    Si la consulta termina antes del último día del mes en curso, se omite ese
    mes incompleto; de esa forma el dashboard no muestra un "último dato mensual"
    parcial basado en la semana/día más reciente.
    """
    by_month: OrderedDict[tuple[int, int], float] = OrderedDict()
    for d in datos:
        try:
            dt = datetime.strptime(d["fecha"], "%d/%m/%Y")
            val = float(d["dato"].replace(",", "")) * factor
        except (ValueError, KeyError, TypeError):
            continue
        key = (dt.year, dt.month)
        by_month[key] = val  # el último recorrido gana (datos vienen ordenados asc)

    # Descartar el mes en curso si la consulta no llega a su último día.
    if end and by_month:
        try:
            end_dt = datetime.strptime(end, "%Y-%m-%d").date()
            last_year, last_month = next(reversed(by_month))
            if (last_year, last_month) == (end_dt.year, end_dt.month):
                last_day = calendar.monthrange(end_dt.year, end_dt.month)[1]
                if end_dt.day < last_day:
                    by_month.popitem(last=True)
        except (ValueError, TypeError):
            pass

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
        obs = _monthly_last(datos, factor, end)
        if not obs:
            warns.append(f"Banxico {key}: sin observaciones mensuales.")
            continue

        raw = _raw_observations(datos, factor)
        if not raw:
            warns.append(f"Banxico {key}: sin observaciones originales.")
            continue

        last = obs[-1]
        last_raw = raw[-1]
        frecuencia_meta = (meta.get("frecuencia") or "").lower()
        frecuencia_original = "Diaria"
        if "semanal" in frecuencia_meta:
            frecuencia_original = "Semanal"
        elif "diaria" in frecuencia_meta or key in ("TIPOCAMBIO", "TASA"):
            frecuencia_original = "Diaria"

        out[key] = {
            "key": key,
            "nombre": meta.get("nombre"),
            "frecuencia": meta.get("frecuencia", "Mensual"),
            "frecuencia_original": frecuencia_original,
            "unidad": meta.get("unidad"),
            "columns": [{"label": meta.get("nombre"), "index": 0, "fmt": FMT.get(key, "num")}],
            "observations": obs,
            "observations_original": raw,
            "last_observation": last["period"],
            "fecha_ultima_observacion": last_raw["period"],
            "fuente": {
                "nombre": "Banco de México (SIE)",
                "serie": serie,
                "link": meta.get("link", "https://www.banxico.org.mx/SieAPIRest/"),
                "metodo": "Banxico SIE API",
            },
            "api_meta": {
                "serie": serie,
                "n_obs_mensual": len(obs),
                "n_obs_original": len(raw),
                "ultimo_valor": last["values"][0],
                "ultimo_valor_original": last_raw["values"][0],
                "ultima_observacion": last["period"],
                "ultima_observacion_original": last_raw["period"],
                "ultima_ym": None,
            },
        }
    return SourceResult(bool(out), out, warns)
