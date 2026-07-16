"""Conector INEGI (BIE). Requiere INEGI_TOKEN.

Los IDs de serie de INEGI deben confirmarse contra el catálogo oficial del BIE
antes de usarse (config/series.json los deja en null hasta confirmarlos) para
evitar publicar una serie equivocada. Cuando falta el token o los IDs no están
confirmados, devuelve SourceResult(ok=False) y el pipeline conserva los datos.
"""
from __future__ import annotations

import os

from .base import SourceResult, http_get_json

ENDPOINT = ("https://www.inegi.org.mx/app/api/indicadores/desarrolladores/jsonxml/"
            "INDICATOR/{ids}/es/0700/false/BIE/2.0/{token}?type=json")


def fetch(config: dict, start_year=2018) -> SourceResult:
    token = os.environ.get("INEGI_TOKEN")
    if not token:
        return SourceResult(False, warnings=["INEGI_TOKEN ausente: se omite la actualización desde INEGI; se conservan datos previos."])
    inegi = config.get("inegi", {})
    confirmed = {k: v.get("serie") for k, v in inegi.items()
                 if isinstance(v, dict) and v.get("serie")}
    if not confirmed:
        return SourceResult(False, warnings=[
            "INEGI: no hay IDs de serie confirmados en config/series.json. "
            "Confírmalos contra el catálogo del BIE antes de activar la descarga; "
            "se conservan los datos previos."])
    # Estructura preparada; la normalización específica por indicador se añade
    # al confirmar los IDs. Devuelve vacío con advertencia hasta entonces.
    return SourceResult(False, warnings=[
        f"INEGI: {len(confirmed)} serie(s) configurada(s) pero la normalización "
        "por indicador está pendiente de validar con datos reales del token."])
