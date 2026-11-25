"""Conector Banco de México (SIE). Requiere BANXICO_TOKEN.

Descarga series diarias/semanales (tipo de cambio FIX, tasa objetivo, reservas
internacionales) y las conserva en su frecuencia oficial original. No fuerza una
agregación mensual como serie principal.

- FIX: diaria, días hábiles bancarios.
- TASA: diaria, con cambios discretos en fechas de decisión.
- RESERVAS: semanal.
- REMESAS: flujos mensuales en millones de dólares.

Si no hay token, devuelve SourceResult(ok=False) y el pipeline conserva los datos
existentes.
"""
from __future__ import annotations

import os
from datetime import datetime
from math import isfinite

from .base import SourceResult, http_get_json
from .inegi import ym_to_label

BASE = ("https://www.banxico.org.mx/SieAPIRest/service/v1/series/{series}/"
        "datos/{start}/{end}?token={token}")

MESES_ABBR = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
              "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

FMT = {
    "TIPOCAMBIO": "fx",
    "TASA": "pct-raw",
    "RESERVAS": "usd",
    "REMESAS": "mdd",
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


def _monthly_last(datos, factor: float = 1.0) -> list[dict]:
    """Serie auxiliar mensual: último valor de cada mes.

    Se conserva como FIX_MENSUAL / TASA_MENSUAL / RESERVAS_MENSUAL en
    observaciones_mensual, pero NO es la serie principal del dashboard.
    """
    by_month: dict[tuple[int, int], float] = {}
    for d in datos:
        try:
            dt = datetime.strptime(d["fecha"], "%d/%m/%Y")
            val = float(d["dato"].replace(",", "")) * factor
        except (ValueError, KeyError, TypeError):
            continue
        by_month[(dt.year, dt.month)] = val

    obs = []
    for (y, m), v in sorted(by_month.items()):
        period = f"{MESES_ABBR[m - 1]} {str(y)[2:]}"
        obs.append({"period": period, "values": [round(v, 6)]})
    return obs


def _remesas_monthly(obs: list[dict]) -> list[dict]:
    """Compara el mismo mes y acumula únicamente tramos completos desde enero."""
    by_month = {row["period"][:7]: row["values"][0] for row in obs
                if isfinite(row["values"][0]) and row["values"][0] >= 0}
    rows = []
    for ym, value in sorted(by_month.items()):
        year, month = map(int, ym.split("-"))
        previous = by_month.get(f"{year - 1}-{month:02d}")
        months = [by_month.get(f"{year}-{m:02d}") for m in range(1, month + 1)]
        prior_months = [by_month.get(f"{year - 1}-{m:02d}") for m in range(1, month + 1)]
        total = sum(months) if None not in months else None
        prior_total = sum(prior_months) if None not in prior_months else None
        rows.append({
            "period": ym_to_label(ym),
            "values": [value, round(value / previous - 1, 6) if previous else None,
                       round(total, 6) if total is not None else None,
                       round(total / prior_total - 1, 6) if total is not None and prior_total else None],
        })
    return rows


def _infer_frecuencia(meta: dict, key: str) -> str:
    frec = (meta.get("frecuencia") or "").lower().replace("-", " ")
    if "semanal" in frec:
        return "Semanal"
    if "diaria" in frec:
        return "Diaria"
    if key in ("TIPOCAMBIO", "TASA"):
        return "Diaria"
    return meta.get("frecuencia") or "Diaria"


def fetch(config: dict, start: str | None = None, end: str | None = None) -> SourceResult:
    token = os.environ.get("BANXICO_TOKEN")
    if not token:
        return SourceResult(False, warnings=[
            "BANXICO_TOKEN ausente: se omiten las series del SIE; "
            "se conservan datos previos."])
    end = end or datetime.today().strftime("%Y-%m-%d")
    out, warns = {}, []
    for key, meta in config.get("banxico", {}).items():
        if key.startswith("_"):
            continue
        serie = meta.get("serie")
        if not serie:
            continue
        # Sin corte inicial artificial: la misma clave oficial define su historia.
        url = (BASE.format(series=serie,start=start,end=end,token=token) if start else
               f"https://www.banxico.org.mx/SieAPIRest/service/v1/series/{serie}/datos?token={token}")
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
        obs = _raw_observations(datos, factor)
        if key == "REMESAS":
            obs = _remesas_monthly(obs)
        if not obs:
            warns.append(f"Banxico {key}: sin observaciones originales.")
            continue

        # Serie auxiliar mensual, claramente diferenciada.
        mensual = _monthly_last(datos, factor) if key != "REMESAS" else []

        frecuencia = _infer_frecuencia(meta, key)
        last = obs[-1]

        out[key] = {
            "key": key,
            "nombre": meta.get("nombre"),
            "frecuencia": frecuencia,
            "unidad": meta.get("unidad"),
            "columns": [{"label": meta.get("nombre"), "index": 0, "fmt": FMT.get(key, "num")}],
            "observations": obs,
            "observations_mensual": mensual,
            "last_observation": last["period"],
            "fecha_ultima_observacion": last["period"],
            "fuente": {
                "nombre": "Banco de México (SIE)",
                "serie": serie,
                "link": meta.get("link", "https://www.banxico.org.mx/SieAPIRest/"),
                "metodo": "Banxico SIE API",
            },
            "api_meta": {
                "serie": serie,
                "n_obs": len(obs),
                "n_obs_mensual": len(mensual),
                "ultimo_valor": last["values"][0],
                "ultima_observacion": last["period"],
                "ultima_ym": None,
            },
        }
    return SourceResult(bool(out), out, warns)
