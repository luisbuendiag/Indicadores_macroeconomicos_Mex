"""Conector del calendario de Sala de Prensa del INEGI.

Consulta el endpoint de fechas de publicación, guarda la respuesta en caché
anual y devuelve eventos normalizados listos para mapear a claves del
dashboard.

Modo offline: sólo lee los archivos de caché ya descargados; no realiza
llamadas de red.
"""
from __future__ import annotations

import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

from .base import USER_AGENT

INEGI_URL = "https://www.inegi.org.mx/app/api/saladeprensa/api/saladeprensa/ObtenerFechasTabla/v3"
INEGI_FORM = {
    "titulo": "",
    "idPrograma": "0",
    "ordenarPor": "fecha",
    "ordenarAsc": "1",
    "desde": "0",
    "tomar": "5000",
    "ingles": "0",
    "ambito": "-1",
    "tipoNoticia": "1,2,3,4,5,6,7,8",
}


def _parse_ddmmyyyy(txt: str) -> date | None:
    """Convierte 'dd/mm/yyyy' en date."""
    if not txt:
        return None
    try:
        d, m, y = txt.split("/")
        return date(int(y), int(m), int(d))
    except (ValueError, TypeError):
        return None


def _abs_inegi_url(path: str) -> str:
    """Prefija rutas relativas de INEGI con el dominio adecuado."""
    if not path:
        return ""
    path = path.strip()
    if path.startswith("http"):
        return path
    if path.startswith("/saladeprensa/"):
        return f"https://www.inegi.org.mx/contenidos{path}"
    if path.startswith("/"):
        return f"https://www.inegi.org.mx{path}"
    return path


def _clean_notas(notas: str) -> str | None:
    """Limpia HTML de las notas y devuelve texto plano o None."""
    if not notas:
        return None
    txt = re.sub(r"<[^>]+>", " ", notas)
    txt = html.unescape(txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt or None


def _size_text(val) -> str | None:
    """Convierte el peso en megabytes a cadena legible."""
    if val in (None, "", "0"):
        return None
    try:
        mb = float(str(val).replace(",", "."))
    except (ValueError, TypeError):
        return None
    if mb <= 0:
        return None
    return f"{mb:.2f} MB".replace(".00 MB", " MB").replace(".0 MB", " MB")


def _build_deliverables(item: dict) -> list[dict]:
    """Extrae comunicados y reportes del evento de Sala de Prensa."""
    deliverables: list[dict] = []
    mappings = [
        ("Boletín PDF", "comunicadoEsUrlPdf", "comunicadoEsUrlPdfPeso", "comunicado", "pdf"),
        ("Boletín Word", "comunicadoEsUrlWord", "comunicadoEsUrlWordPeso", "comunicado", "word"),
        ("Boletín Excel", "comunicadoEsUrlExcel", "comunicadoEsUrlExcelPeso", "comunicado", "excel"),
        ("Reporte PDF", "reporteEsUrlPdf", "reporteEsUrlPdfPeso", "reporte", "pdf"),
        ("Reporte Word", "reporteEsUrlWord", "reporteEsUrlWordPeso", "reporte", "word"),
    ]
    for label, url_field, size_field, kind, fmt in mappings:
        url = _abs_inegi_url(item.get(url_field) or "")
        if not url:
            continue
        size = _size_text(item.get(size_field))
        deliverables.append({
            "type": kind,
            "format": fmt,
            "url": url,
            "label": label,
            "size": size,
        })
    return deliverables


def _main_url(item: dict, deliverables: list[dict]) -> str:
    """Elige la URL principal del evento: primer entregable, urlConsulta o Sala de Prensa."""
    for d in deliverables:
        if d.get("url"):
            return d["url"]
    u = _abs_inegi_url(item.get("urlConsulta") or "")
    if u:
        return u
    return "https://www.inegi.org.mx/app/saladeprensa/calendario/"


def _post_json(url: str, fields: dict, timeout: int = 60) -> list:
    """Envía una petición POST y devuelve el JSON parseado."""
    data = urllib.parse.urlencode(fields).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.URLError as e:
            if attempt == 0 and "timed out" in str(e).lower():
                continue
            raise
    raise urllib.error.URLError("timed out after retry")


def _read_cache(year: int, cache_dir: Path) -> list | None:
    path = cache_dir / f"inegi_{year}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def _save_cache(year: int, data: list, cache_dir: Path) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / f"inegi_{year}.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _normalize_item(item: dict) -> dict | None:
    """Convierte un registro crudo del INEGI en un evento normalizado."""
    fecha = item.get("fecha")
    d = _parse_ddmmyyyy(fecha)
    if d is None:
        return None
    period = (item.get("periodo") or "").strip()
    program = (item.get("programa") or "").strip()
    if not program or not period:
        return None
    deliverables = _build_deliverables(item)
    return {
        "source": "INEGI Sala de Prensa",
        "institution": "INEGI",
        "program": program,
        "period": period,
        "date": d,
        "url_consulta": _abs_inegi_url(item.get("urlConsulta") or ""),
        "url": _main_url(item, deliverables),
        "deliverables": deliverables,
        "comentario": _clean_notas(item.get("notas")),
        "raw": item,
    }


def fetch(years: list[int], cache_dir: Path, offline: bool = False) -> tuple[list[dict], dict]:
    """Descarga o lee de caché las fechas de publicación del INEGI.

    Devuelve (eventos, info_status).
    """
    events: list[dict] = []
    status = {"status": "ok", "count": 0, "message": "", "consulted_at": None, "url": INEGI_URL}
    if offline:
        for year in years:
            cached = _read_cache(year, cache_dir)
            if cached:
                for item in cached:
                    ev = _normalize_item(item)
                    if ev:
                        events.append(ev)
        status["count"] = len(events)
        status["message"] = f"Modo offline: {len(events)} eventos leídos de caché"
        return events, status

    for year in years:
        fields = {**INEGI_FORM, "fechaDesde": f"{year}-01-01", "fechaHasta": f"{year}-12-31"}
        try:
            raw = _post_json(INEGI_URL, fields)
        except Exception as e:  # noqa: BLE001
            cached = _read_cache(year, cache_dir)
            if cached:
                for item in cached:
                    ev = _normalize_item(item)
                    if ev:
                        events.append(ev)
                status["message"] += f" {year} falló ({e}); usado caché."
            else:
                status["message"] += f" {year} falló ({e}); sin caché."
            continue
        _save_cache(year, raw, cache_dir)
        for item in raw:
            ev = _normalize_item(item)
            if ev:
                events.append(ev)
    status["count"] = len(events)
    status["consulted_at"] = date.today().isoformat()
    if "falló" not in status["message"]:
        status["message"] = f"{len(events)} eventos consultados del INEGI"
    return events, status
