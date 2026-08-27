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


def http_get_json(url: str, timeout: int = 60) -> dict | list:
    """Obtiene JSON de una URL con timeout extendido y un reintento."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.URLError as e:
            if attempt == 0 and "timed out" in str(e).lower():
                continue
            raise
    raise urllib.error.URLError("timed out after retry")


class SourceResult:
    def __init__(self, ok: bool, data: dict | None = None, warnings: list[str] | None = None):
        self.ok = ok
        self.data = data or {}
        self.warnings = warnings or []
