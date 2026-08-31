"""Conector del calendario de publicaciones del Banco de México.

Descarga los archivos mensules canal_1_{MM}{YYYY}_es.json, extrae los
anuncios de política monetaria (TASA) y los estados de cuenta semanales
(RESERVAS) y los normaliza.

Modo offline: lee la caché mensual si existe.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

from .base import USER_AGENT, http_get_json

BASE_URL = "https://www.banxico.org.mx/canales/canal_1_{MM}{YYYY}_es.json"
BANXICO_PREFIX = "https://www.banxico.org.mx"

MESES_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def _format_date(d: date) -> str:
    return f"{d.day} de {MESES_ES[d.month - 1]} de {d.year}"


def _parse_ddmmyyyy(txt: str) -> date | None:
    if not txt:
        return None
    try:
        d, m, y = txt.split("/")
        return date(int(y), int(m), int(d))
    except (ValueError, TypeError):
        return None


def _previous_friday(d: date) -> date:
    """Devuelve el viernes anterior más cercano."""
    while d.weekday() != 4:
        d -= timedelta(days=1)
    return d


def _extract_period_date(title: str, pub_date: date) -> date:
    """Intenta extraer la fecha de cierre de la semana del título."""
    if not title:
        return _previous_friday(pub_date)
    # Busca patrones: "al 21 de agosto de 2026", "al 31 de julio y del mes de julio de 2026"
    m = re.search(r"al\s+(\d{1,2})\s+de\s+([a-zA-ZáéíóúÁÉÍÓÚñÑ]+)\s+(?:y\s+.*\s+)?(?:de\s+)?(\d{4})", title, re.IGNORECASE)
    if not m:
        m = re.search(r"al\s+(\d{1,2})\s+de\s+([a-zA-ZáéíóúÁÉÍÓÚñÑ]+)\s+de\s+(\d{4})", title, re.IGNORECASE)
    if m:
        try:
            mes = MESES_ES.index(m.group(2).lower()) + 1
            return date(int(m.group(3)), mes, int(m.group(1)))
        except (ValueError, IndexError):
            pass
    return _previous_friday(pub_date)


def _full_url(path: str | None) -> str:
    if not path:
        return ""
    path = path.strip()
    if path.startswith("http"):
        return path
    return BANXICO_PREFIX + path


def _deliverable_for(res: dict) -> dict | None:
    url = _full_url(res.get("url"))
    if not url:
        return None
    dtype = (res.get("documentType") or "").lower()
    if dtype == "minuta":
        label, kind = "Minuta de la reunión", "minuta"
    else:
        label, kind = (res.get("linkText") or res.get("title") or "Comunicado"), "comunicado"
    ext = (res.get("content") or {}).get("extension") or "pdf"
    return {
        "type": kind,
        "format": ext,
        "url": url,
        "label": label,
        "size": None,
    }


def _flatten(section, parent_id: str, category_id: str) -> list[dict]:
    """Recorre una sección (webResources o webFutureResources) del JSON de Banxico."""
    if not isinstance(section, dict):
        return []
    results: list[dict] = []
    for entries in section.values():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if str(entry.get("parentId")) != str(parent_id):
                continue
            if str(entry.get("categoryId")) != str(category_id):
                continue
            if "resources" in entry and isinstance(entry["resources"], list):
                for res in entry["resources"]:
                    res.setdefault("categoryId", entry.get("categoryId"))
                    res.setdefault("parentId", entry.get("parentId"))
                    results.append(res)
            if "futureResources" in entry and isinstance(entry["futureResources"], list):
                for res in entry["futureResources"]:
                    res.setdefault("categoryId", entry.get("categoryId"))
                    res.setdefault("parentId", entry.get("parentId"))
                    results.append(res)
    return results


def _normalize_tasa(res: dict) -> dict | None:
    d = _parse_ddmmyyyy(res.get("referenceDate") or res.get("firstPublishingDate"))
    if not d:
        return None
    deliverables: list[dict] = []
    dev = _deliverable_for(res)
    if dev:
        deliverables.append(dev)
    return {
        "source": "Banco de México calendario",
        "institution": "Banco de México",
        "program": res.get("title") or res.get("linkText") or "Anuncio de decisión de política monetaria",
        "period": _format_date(d),
        "date": d,
        "url": deliverables[0]["url"] if deliverables else "https://www.banxico.org.mx/mercados/tasas-de-referencia.html",
        "deliverables": deliverables,
        "comentario": None,
        "is_evento": True,
        "indicator": "TASA",
    }


def _normalize_reservas(res: dict) -> dict | None:
    d = _parse_ddmmyyyy(res.get("referenceDate") or res.get("firstPublishingDate"))
    if not d:
        return None
    title = res.get("title") or res.get("linkText") or ""
    period_date = _extract_period_date(title, d)
    deliverables: list[dict] = []
    dev = _deliverable_for(res)
    if dev:
        deliverables.append(dev)
    return {
        "source": "Banco de México calendario",
        "institution": "Banco de México",
        "program": res.get("linkText") or res.get("title") or "Estado de cuenta del Banco de México",
        "period": _format_date(period_date),
        "date": d,
        "url": deliverables[0]["url"] if deliverables else "https://www.banxico.org.mx/publicaciones-y-prensa/reservas-internacionales/",
        "deliverables": deliverables,
        "comentario": None,
        "is_evento": False,
        "indicator": "RESERVAS",
    }


def _cache_path(year: int, month: int, cache_dir: Path) -> Path:
    return cache_dir / f"banxico_{year}_{month:02d}.json"


def _fetch_month(year: int, month: int, cache_dir: Path, offline: bool) -> dict | None:
    path = _cache_path(year, month, cache_dir)
    if offline:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return None
    url = BASE_URL.format(MM=f"{month:02d}", YYYY=year)
    try:
        data = http_get_json(url)
    except Exception as e:  # noqa: BLE001
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        raise urllib.error.URLError(f"Banxico {year}-{month:02d} falló: {e}")
    cache_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def fetch(years: list[int], cache_dir: Path, offline: bool = False) -> tuple[list[dict], dict]:
    """Consulta el calendario mensual de Banxico para TASA y RESERVAS.

    Devuelve (eventos, info_status).
    """
    events: list[dict] = []
    status = {
        "status": "ok",
        "count": 0,
        "message": "",
        "consulted_at": None,
        "url": BASE_URL,
    }
    if offline:
        for year in years:
            for month in range(1, 13):
                data = _fetch_month(year, month, cache_dir, offline=True)
                if data:
                    for res in _flatten(data.get("webResources", {}), "1", "3"):
                        ev = _normalize_tasa(res)
                        if ev:
                            events.append(ev)
                    for res in _flatten(data.get("webResources", {}), "11", "13"):
                        ev = _normalize_reservas(res)
                        if ev:
                            events.append(ev)
                    for res in _flatten(data.get("webFutureResources", {}), "1", "3"):
                        ev = _normalize_tasa(res)
                        if ev:
                            events.append(ev)
                    for res in _flatten(data.get("webFutureResources", {}), "11", "13"):
                        ev = _normalize_reservas(res)
                        if ev:
                            events.append(ev)
        status["count"] = len(events)
        status["message"] = f"Modo offline: {len(events)} eventos leídos de caché"
        return events, status

    missing: list[str] = []
    for year in years:
        for month in range(1, 13):
            try:
                data = _fetch_month(year, month, cache_dir, offline=False)
            except Exception as e:  # noqa: BLE001
                missing.append(f"{year}-{month:02d}")
                continue
            if not data:
                continue
            for res in _flatten(data.get("webResources", {}), "1", "3"):
                ev = _normalize_tasa(res)
                if ev:
                    events.append(ev)
            for res in _flatten(data.get("webResources", {}), "11", "13"):
                ev = _normalize_reservas(res)
                if ev:
                    events.append(ev)
            for res in _flatten(data.get("webFutureResources", {}), "1", "3"):
                ev = _normalize_tasa(res)
                if ev:
                    events.append(ev)
            for res in _flatten(data.get("webFutureResources", {}), "11", "13"):
                ev = _normalize_reservas(res)
                if ev:
                    events.append(ev)
    status["count"] = len(events)
    status["consulted_at"] = date.today().isoformat()
    if missing:
        status["message"] = f"Faltaron {len(missing)} meses: {', '.join(missing[:5])}."
    else:
        status["message"] = f"{len(events)} eventos consultados de Banxico"
    return events, status
