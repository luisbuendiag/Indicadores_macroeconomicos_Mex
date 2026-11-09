"""Conectores oficiales: conservar la última versión válida ante fallos de fuente."""
from __future__ import annotations

import http.client
import json
import socket
import time
import urllib.error
import urllib.request

USER_AGENT = "IndicadoresMacroMX/2.0 (+https://github.com/luisbuendiag/Indicadores_macroeconomicos_Mex)"
RETRY_STATUS = {408, 429, 500, 502, 503, 504}


def http_get_bytes(url: str, timeout: int = 60, *, accept: str = '*/*') -> bytes:
    """Tres intentos solo ante fallos transitorios; 404 y errores de contenido no se repiten."""
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT, 'Accept': accept})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError, socket.timeout,
                ConnectionError, http.client.IncompleteRead) as error:
            if isinstance(error, urllib.error.HTTPError) and error.code not in RETRY_STATUS:
                raise
            if attempt == 2:
                raise
            delay = 2 ** (attempt + 1)
            if isinstance(error, urllib.error.HTTPError):
                retry_after = error.headers.get('Retry-After', '') if error.headers else ''
                if retry_after.isdigit():
                    delay = max(delay, min(int(retry_after), 60))
            time.sleep(delay)
    raise RuntimeError('No se pudo completar la consulta')


def http_get_json(url: str, timeout: int = 60) -> dict | list:
    return json.loads(http_get_bytes(url, timeout, accept='application/json').decode('utf-8'))


class SourceResult:
    def __init__(self, ok: bool, data: dict | None = None, warnings: list[str] | None = None):
        self.ok = ok
        self.data = data or {}
        self.warnings = warnings or []
