"""Base para conectores de fuentes oficiales.

Cada conector implementa fetch() y devuelve un dict {clave_indicador: {...}}
compatible con el esquema de data/indicadores.json, o None si no puede operar
(por ejemplo, falta de token). El pipeline NUNCA borra datos cuando un conector
devuelve None: conserva la última versión válida.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

USER_AGENT = "IndicadoresMacroMX/2.0 (+https://github.com/luisbuendiag/Indicadores_macroeconomicos_Mex)"


def http_get_json(url: str, timeout: int = 30) -> dict | list:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


class SourceResult:
    def __init__(self, ok: bool, data: dict | None = None, warnings: list[str] | None = None):
        self.ok = ok
        self.data = data or {}
        self.warnings = warnings or []
