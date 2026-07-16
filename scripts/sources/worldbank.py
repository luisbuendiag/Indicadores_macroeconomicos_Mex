"""Conector Banco Mundial (World Bank Open Data). NO requiere token.

Sirve como fuente de contexto anual (PIB real, inflación, desempleo) y como
prueba de que el pipeline funciona con fuentes sin token. Escribe
data/worldbank.json; no reemplaza las series oficiales de INEGI/Banxico.
"""
from __future__ import annotations

from .base import SourceResult, http_get_json

BASE = "https://api.worldbank.org/v2/country/MEX/indicator/{id}?format=json&per_page=500"


def fetch(config: dict, start_year=2015) -> SourceResult:
    wb = config.get("worldbank", {})
    series = {k: v for k, v in wb.items() if not k.startswith("_")}
    out, warns = {}, []
    for name, wb_id in series.items():
        try:
            raw = http_get_json(BASE.format(id=wb_id))
        except Exception as e:  # noqa: BLE001
            warns.append(f"World Bank {name} ({wb_id}) falló: {e}.")
            continue
        if not isinstance(raw, list) or len(raw) < 2 or not raw[1]:
            warns.append(f"World Bank {name}: respuesta vacía.")
            continue
        obs = []
        for row in reversed(raw[1]):
            yr = int(row["date"])
            if yr < start_year or row["value"] is None:
                continue
            obs.append({"year": yr, "value": row["value"]})
        out[name] = {"indicator_id": wb_id, "observations": obs}
    return SourceResult(bool(out), out, warns)
