"""Conector INPP: consulta niveles, variaciones y componentes del BIE de INEGI.

Fuentes:
  - Nivel total con/sin petróleo y variaciones: BIE-BISE 910492, 910491,
    1800002/1801002/1802002 (con) y 1800001/1801001/1802001 (sin).
  - Bienes intermedios y actividades primarias: BIE-BISE 910493, 1700003.
  - Subsectores: variaciones anuales del BIE 1801003-1801009.

Las variaciones porcentuales vienen de INEGI como números en porcentaje
(p. ej. 3.12) y se almacenan con fmt pct-raw. Los niveles son índices.
"""
from __future__ import annotations

import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime

from .base import SourceResult, USER_AGENT
from . import inegi

INPP_LINK = "https://www.inegi.org.mx/programas/inpp/2019a/"

# Especificaciones BIE. Los porcentajes se leen tal cual (pct-raw).
SPECS = [
    # Total con petróleo
    {"serie": "910492", "columna_objetivo": 0, "nombre": "INPP con petróleo (índice)", "link": INPP_LINK},
    {"serie": "1800002", "columna_objetivo": 1, "nombre": "INPP con petróleo var. mensual (%)", "link": INPP_LINK},
    {"serie": "1801002", "columna_objetivo": 2, "nombre": "INPP con petróleo var. anual (%)", "link": INPP_LINK},
    {"serie": "1802002", "columna_objetivo": 3, "nombre": "INPP con petróleo var. acumulada (%)", "link": INPP_LINK},
    # Total sin petróleo (bienes y servicios finales)
    {"serie": "910491", "columna_objetivo": 4, "nombre": "INPP sin petróleo (índice)", "link": INPP_LINK},
    {"serie": "1800001", "columna_objetivo": 5, "nombre": "INPP sin petróleo var. mensual (%)", "link": INPP_LINK},
    {"serie": "1801001", "columna_objetivo": 6, "nombre": "INPP sin petróleo var. anual (%)", "link": INPP_LINK},
    {"serie": "1802001", "columna_objetivo": 7, "nombre": "INPP sin petróleo var. acumulada (%)", "link": INPP_LINK},
    # Bienes intermedios y actividades primarias (se computa yoy desde nivel)
    {"serie": "910493", "columna_objetivo": 8, "transform": "yoy", "factor": 1, "nombre": "Bienes intermedios var. anual (%)", "link": INPP_LINK},
    {"serie": "1700003", "columna_objetivo": 9, "transform": "yoy", "factor": 1, "nombre": "Actividades primarias var. anual (%)", "link": INPP_LINK},
    # Subsectores: variación anual oficial del BIE
    {"serie": "1801003", "columna_objetivo": 10, "nombre": "Agricultura var. anual (%)", "link": INPP_LINK},
    {"serie": "1801005", "columna_objetivo": 11, "nombre": "Minería con petróleo var. anual (%)", "link": INPP_LINK},
    {"serie": "1801007", "columna_objetivo": 12, "nombre": "Construcción var. anual (%)", "link": INPP_LINK},
    {"serie": "1801008", "columna_objetivo": 13, "nombre": "Manufacturas var. anual (%)", "link": INPP_LINK},
    {"serie": "1801009", "columna_objetivo": 14, "nombre": "Transportes var. anual (%)", "link": INPP_LINK},
]


def _head_ok(url: str, timeout: int = 15) -> bool:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT}, method="HEAD")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": USER_AGENT}), timeout=timeout) as r:
                ctype = r.headers.get("Content-Type", "")
                return "pdf" in ctype.lower() or r.headers.get("Content-Length") is not None
        except Exception:
            return False


def _discover_bulletin(period: str | None) -> dict | None:
    """Descubre la URL del boletín oficial del INPP para el periodo dado."""
    ym = inegi.label_to_ym(period) if period else None
    if not ym:
        return None
    year, month = int(ym.split("-")[0]), int(ym.split("-")[1])
    # Busca el PDF del mes de referencia; si no, el inmediato anterior.
    for m in range(month, 0, -1):
        url = f"https://www.inegi.org.mx/contenidos/saladeprensa/boletines/{year}/inpp/inpp{year}_{m:02d}.pdf"
        if _head_ok(url):
            return {
                "url": url,
                "periodo_boletin": period,
                "tipo_documento": "PDF",
                "producto_boletin": "Índice Nacional de Precios Productor",
                "metodo": "INEGI boletín PDF",
            }
        time.sleep(0.3)
    return None


def fetch(config: dict | None = None, start_year: int = 2018) -> SourceResult:
    """Consulta el BIE para el INPP y devuelve un SourceResult."""
    token = os.environ.get("INEGI_TOKEN")
    if not token:
        return SourceResult(False, warnings=["inegi_inpp: INEGI_TOKEN ausente; se omite"])

    # Usa el motor genérico del conector inegi con las especificaciones propias.
    res = inegi.fetch({"inegi": {"INPP": SPECS}}, start_year=start_year)
    if not res.ok or "INPP" not in res.data:
        return res

    items = res.data["INPP"]
    if not isinstance(items, list):
        items = [items]

    # Cambiar metodo para que build_data no sobrescriba la serie principal del
    # perfil y para identificar el origen específico del INPP.
    for it in items:
        it["metodo"] = "INEGI BIE API (INPP)"

    # Descubrir boletín oficial para el último periodo con datos.
    last_item = items[0]
    last_period = last_item.get("api_meta", {}).get("ultima_observacion")
    if last_period:
        bulletin = _discover_bulletin(last_period)
        if bulletin:
            items.append({
                "target_column": -1,
                "api_total": [],
                "serie": "inpp_boletin",
                "metodo": "INEGI BIE API (INPP)",
                "link": bulletin["url"],
                "periodo_boletin": bulletin["periodo_boletin"],
                "tipo_documento": bulletin["tipo_documento"],
                "producto_boletin": bulletin["producto_boletin"],
            })

    res.data["INPP"] = items
    return res
