"""Lógica de frescura de datos del dashboard.

Compara, por indicador, el último periodo cargado contra el calendario oficial
(``data/calendario_publicaciones.json``) y devuelve uno de cuatro estados:

- ACTUALIZADO
- PUBLICACIÓN PENDIENTE
- REZAGADO
- ERROR DE FUENTE

No emite juicios sin fuente: el estado refleja la relación entre el dato
almacenado, el calendario y el resultado del pipeline (``update_log``).
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sources import inegi

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
CAL_FILE = DATA_DIR / "calendario_publicaciones.json"
UPDATE_LOG_FILE = DATA_DIR / "update_log.json"

ESTADOS = {
    "ACTUALIZADO": "ACTUALIZADO",
    "PUBLICACION_PENDIENTE": "PUBLICACIÓN PENDIENTE",
    "REZAGADO": "REZAGADO",
    "ERROR_FUENTE": "ERROR DE FUENTE",
}


def _load_json(path: Path) -> Any:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


MESES_FULL = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}


def _month_from_name(name: str) -> int | None:
    n = name.lower()
    if n in inegi.MESES:
        return inegi.MESES.index(n) + 1
    if n in MESES_FULL:
        return MESES_FULL[n]
    return None


def _period_to_ym(period: str | None) -> str | None:
    p = (period or "").strip()
    if not p:
        return None

    # Si el periodo incluye año de 4 dígitos, parsear formato completo del calendario
    # antes de delegar a inegi.label_to_ym, que asume año de 2 dígitos.
    if re.search(r"\b\d{4}\b", p):
        # Mensual completo: 'Mayo 2026', 'mayo de 2026'
        m = re.match(r"^([A-Za-zÁÉÍÓÚáéíóú]+)\s+(?:de\s+)?(\d{4})$", p)
        if m:
            mi = _month_from_name(m.group(1))
            if mi:
                return f"{m.group(2)}-{mi:02d}"

        # Trimestral completo: '2° trimestre de 2026', '2° trimestre 2026'
        qm = re.match(r"^(\d)\s*°?\s*trimestre\s+(?:de\s+)?(\d{4})", p, re.IGNORECASE)
        if qm:
            q = int(qm.group(1))
            y = int(qm.group(2))
            if 1 <= q <= 4:
                month = (q - 1) * 3 + 1
                return f"{y}-{month:02d}"

    # Formatos del dashboard: 'May 26', 'May 26 P', '1T-26', '1T-26 R'
    return inegi.label_to_ym(p)


def _clean_period(period: str | None) -> str:
    """Normaliza periodos tipo 'May 26 P' o '1T-26 P' a 'May 26' / '1T-26'."""
    p = (period or "").strip()
    if p and p[-1] in "PpRr" and p[-2] == " ":
        # revisar: si termina en letra sola precedida de espacio
        return p[:-2].strip()
    # También puede ser 'Abr 26 P' sin espacio? no, usa split
    return p


def load_calendar() -> list[dict]:
    cal = _load_json(CAL_FILE)
    return list(cal.get("items", []))


def latest_published(calendar: list[dict], key: str, as_of: date | None = None) -> dict | None:
    """Última publicación marcada como 'publicado' para la clave."""
    items = [
        i for i in calendar
        if i.get("clave") == key and i.get("estatus") == "publicado"
    ]
    if as_of is not None:
        items = [i for i in items if date.fromisoformat(i["fecha_iso"]) <= as_of]
    if not items:
        return None
    return max(items, key=lambda i: i["fecha_iso"])


def latest_expected(calendar: list[dict], key: str, as_of: date | None = None) -> dict | None:
    """Próxima publicación futura para la clave."""
    items = [
        i for i in calendar
        if i.get("clave") == key and i.get("estatus") == "próximo"
    ]
    if as_of is not None:
        items = [i for i in items if date.fromisoformat(i["fecha_iso"]) >= as_of]
    if not items:
        return None
    return min(items, key=lambda i: i["fecha_iso"])


def source_had_error(key: str, update_log: dict | None = None, manifest_row: dict | None = None) -> bool:
    """Revisa si el pipeline reportó un error real para el indicador.

    No marca como error los mensajes informativos de consulta (p. ej.
    'INEGI IGAE: 101 observaciones...'), solo aquellos con palabras clave de
    fallo o mensajes críticos.
    """
    if update_log is None:
        update_log = _load_json(UPDATE_LOG_FILE)
    warnings = [w for w in update_log.get("warnings", []) if isinstance(w, str)]
    critical = [c for c in update_log.get("critical", []) if isinstance(c, str)]
    all_msgs = warnings + critical

    error_kw = ("error", "excepción", "falló", "sin observaciones", "sin indicador base", "sin indicador")
    source_name = (manifest_row.get("fuente") or "").lower().replace(" ", "") if manifest_row else ""

    for msg in all_msgs:
        lower = msg.lower()
        # Advertencias explícitas del indicador.
        if msg.startswith(f"{key}:") and any(k in lower for k in error_kw):
            return True
        # Advertencias de INEGI por indicador.
        if msg.startswith(f"INEGI {key}:") and any(k in lower for k in error_kw):
            return True
        # Fallos a nivel de módulo/fuente que afectan al indicador.
        if any(k in lower for k in ("excepción", "falló")):
            for token in (source_name, "inegi", "banxico", "worldbank"):
                if token and token in lower:
                    return True
    return bool(critical)


def compute_state(
    key: str,
    dashboard_period: str | None,
    manifest_row: dict | None = None,
    update_log: dict | None = None,
    calendar: list[dict] | None = None,
    as_of: date | None = None,
) -> dict[str, Any]:
    """Determina el estado de frescura de un indicador.

    Devuelve un dict con:
      - estado
      - periodo_dashboard
      - periodo_oficial
      - fecha_publicacion_oficial
      - url_boletin (cuando aplique)
      - proxima_publicacion
      - periodo_proximo
      - motivo
    """
    if as_of is None:
        as_of = date.today()
    if calendar is None:
        calendar = load_calendar()
    if update_log is None:
        update_log = _load_json(UPDATE_LOG_FILE)

    row = manifest_row or {}
    dashboard_period_clean = _clean_period(dashboard_period)
    dashboard_ym = _period_to_ym(dashboard_period_clean)

    pub = latest_published(calendar, key, as_of=as_of)
    prox = latest_expected(calendar, key, as_of=as_of)

    official_period = pub.get("periodo_referencia") if pub else None
    official_ym = _period_to_ym(official_period) if official_period else None

    # Error de fuente si el pipeline falló explícitamente para este indicador.
    had_error = source_had_error(key, update_log, manifest_row)

    # Calcular comparación cuando tenemos ambos periodos.
    compara = None
    if dashboard_ym and official_ym:
        compara = (dashboard_ym > official_ym) - (dashboard_ym < official_ym)
        # equivalente a cmp: -1, 0, 1

    if had_error:
        estado = ESTADOS["ERROR_FUENTE"]
        motivo = f"El pipeline reportó un error para {key} y el dato podría no estar actualizado."
    elif not dashboard_ym and not official_ym:
        estado = ESTADOS["ERROR_FUENTE"]
        motivo = "No se pudo determinar ni el periodo del dashboard ni el periodo oficial."
    elif not official_ym:
        estado = ESTADOS["PUBLICACION_PENDIENTE"]
        motivo = "No hay publicación oficial registrada en el calendario aún."
    elif not dashboard_ym:
        estado = ESTADOS["ERROR_FUENTE"]
        motivo = "El dashboard no tiene periodo de referencia."
    elif compara == -1:
        estado = ESTADOS["REZAGADO"]
        motivo = (
            f"El calendario indica que ya se publicó {official_period}, "
            f"pero el dashboard aún muestra {dashboard_period_clean}."
        )
    elif compara == 0:
        estado = ESTADOS["ACTUALIZADO"]
        motivo = (
            f"El periodo cargado ({dashboard_period_clean}) coincide con el último "
            f"periodo oficial publicado ({official_period})."
        )
    else:  # compara == 1: el dashboard está más adelantado que el calendario
        estado = ESTADOS["ACTUALIZADO"]
        motivo = (
            f"El dashboard tiene {dashboard_period_clean}, que está adelantado "
            f"al calendario ({official_period}); se recomienda revisar el calendario."
        )

    # Si está actualizado pero no hay datos (observations vacío), pasa a pendiente/error.
    if estado == ESTADOS["ACTUALIZADO"] and not dashboard_period_clean:
        estado = ESTADOS["PUBLICACION_PENDIENTE"]
        motivo = "No hay datos cargados; la publicación está pendiente."

    return {
        "estado": estado,
        "periodo_dashboard": dashboard_period_clean,
        "periodo_oficial": official_period,
        "fecha_publicacion_oficial": pub.get("fecha_publicacion") if pub else None,
        "fecha_iso_publicacion": pub.get("fecha_iso") if pub else None,
        "proxima_publicacion": prox.get("fecha_publicacion") if prox else None,
        "periodo_proximo": prox.get("periodo_referencia") if prox else None,
        "motivo": motivo,
    }


def diagnose_all(
    indicators: dict[str, dict],
    manifest_rows: dict[str, dict] | None = None,
    update_log: dict | None = None,
    calendar: list[dict] | None = None,
    as_of: date | None = None,
) -> dict[str, dict[str, Any]]:
    """Diagnostica la frescura de todos los indicadores del payload."""
    if calendar is None:
        calendar = load_calendar()
    if update_log is None:
        update_log = _load_json(UPDATE_LOG_FILE)
    rows = manifest_rows or {}
    result: dict[str, dict[str, Any]] = {}
    for key, ind in indicators.items():
        result[key] = compute_state(
            key,
            ind.get("last_observation") or ind.get("periodo_referencia"),
            manifest_row=rows.get(key),
            update_log=update_log,
            calendar=calendar,
            as_of=as_of,
        )
    return result


if __name__ == "__main__":
    payload = json.loads((DATA_DIR / "indicadores.json").read_text("utf-8"))
    manifest = _load_json(DATA_DIR / "manifest.json")
    rows = {m["clave"]: m for m in manifest.get("indicadores", [])}
    diag = diagnose_all(payload["indicators"], rows)
    for k, v in diag.items():
        print(f"{k:12s} {v['estado']:22s} {v['periodo_dashboard'] or '-':8s} vs {v['periodo_oficial'] or '-':8s} | {v['motivo']}")
