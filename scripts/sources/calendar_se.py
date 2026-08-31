"""Conector de la Secretaría de Economía (IED).

No hay endpoint automatizado identificado. Usa el respaldo anual en
``data/calendar_sources/<año>_se.json``.
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}


def _parse_fecha(txt: str) -> date | None:
    """'30 de julio de 2026' -> date(2026, 7, 30)."""
    if not txt:
        return None
    try:
        parts = txt.replace(" de ", " ").split()
        day = int(parts[0])
        month = MESES[parts[1].lower()]
        year = int(parts[2])
        return date(year, month, day)
    except (ValueError, KeyError, IndexError, TypeError):
        return None


def _normalize_period(periodo: str | None) -> str:
    if not periodo:
        return "Próximo periodo"
    # Normaliza "4T 2025" -> "4° trimestre 2025"
    m = re.match(r"(\d)T\s+(\d{4})", (periodo or "").strip())
    if m:
        return f"{m.group(1)}° trimestre {m.group(2)}"
    return periodo.strip()


def fetch(year: int, src_dir: Path) -> tuple[list[dict], dict]:
    """Carga el calendario manual de la Secretaría de Economía."""
    events: list[dict] = []
    status = {
        "status": "ok",
        "count": 0,
        "message": "",
        "consulted_at": None,
        "url": "https://www.gob.mx/se",
    }
    path = src_dir / f"{year}_se.json"
    if not path.exists():
        status["status"] = "missing"
        status["message"] = f"No existe {path.name}; se usará regla manual de IED."
        return events, status
    try:
        src = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        status["status"] = "error"
        status["message"] = f"Error leyendo {path.name}: {e}"
        return events, status

    for entry in src.get("entries", []):
        clave = entry.get("clave", "IED")
        producto = entry.get("producto", "Inversión Extranjera Directa")
        for pub in entry.get("publicaciones", []):
            d = _parse_fecha(pub.get("fecha"))
            if not d:
                continue
            events.append({
                "source": "Secretaría de Economía (manual)",
                "institution": "Secretaría de Economía",
                "program": producto,
                "period": _normalize_period(pub.get("periodo")),
                "date": d,
                "url": pub.get("url") or "https://www.gob.mx/se",
                "deliverables": [{"type": "comunicado", "format": "pdf", "url": pub.get("url") or "", "label": "Comunicado", "size": None}] if pub.get("url") else [],
                "comentario": None,
                "indicator": clave,
            })
        if entry.get("proxima_no_anunciada"):
            events.append({
                "source": "Secretaría de Economía (manual)",
                "institution": "Secretaría de Economía",
                "program": producto,
                "period": _normalize_period(entry.get("proxima_periodo")),
                "date": None,
                "url": "",
                "deliverables": [],
                "comentario": entry.get("proxima_comentario", "Próxima fecha oficial no anunciada"),
                "indicator": clave,
                "no_anunciada": True,
            })
    status["count"] = len(events)
    status["consulted_at"] = src.get("actualizado") or date.today().isoformat()
    status["message"] = f"{len(events)} eventos cargados desde {path.name}"
    return events, status
