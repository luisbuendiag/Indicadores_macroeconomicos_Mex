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

import calendar
import json
import re
from datetime import date, datetime, timedelta
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

        # Trimestral corto: '2T 2026', '4T-2025'
        qm2 = re.match(r"^(\d)T[-\s]?(\d{4})$", p, re.IGNORECASE)
        if qm2:
            q = int(qm2.group(1))
            y = int(qm2.group(2))
            if 1 <= q <= 4:
                month = (q - 1) * 3 + 1
                return f"{y}-{month:02d}"

    # Formatos del dashboard: 'May 26', 'May 26 P', '1T-26', '1T-26 R'
    return inegi.label_to_ym(p)


def _period_to_ym_flexible(period: str | None) -> str | None:
    """Versión permisiva que también entiende fechas ISO o españolas."""
    ym = _period_to_ym(period)
    if ym:
        return ym
    p = (period or "").strip()
    # ISO
    try:
        d = date.fromisoformat(p)
        return f"{d.year}-{d.month:02d}"
    except (ValueError, TypeError):
        pass
    # '7 de agosto de 2026'
    m = re.match(r"^(\d{1,2})\s+de\s+([A-Za-zÁÉÍÓÚáéíóúñÑ]+)\s+de\s+(\d{4})$", p, re.IGNORECASE)
    if m:
        mi = _month_from_name(m.group(2))
        if mi:
            return f"{int(m.group(3))}-{mi:02d}"
    return None


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


def _first_business_day(year: int, month: int) -> date:
    """Primer día hábil (lunes-viernes) del mes, ignorando días festivos."""
    d = date(year, month, 1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def _first_friday(year: int, month: int) -> date:
    d = date(year, month, 1)
    while d.weekday() != 4:
        d += timedelta(days=1)
    return d


def _prev_month(d: date) -> date:
    if d.month == 1:
        return date(d.year - 1, 12, 1)
    return date(d.year, d.month - 1, 1)


def _prev_quarter(d: date, offset_months: int = 3) -> date:
    """Resta `offset_months` meses y devuelve el primer mes de ese trimestre."""
    year = d.year
    month = d.month - offset_months
    while month <= 0:
        month += 12
        year -= 1
    q = (month - 1) // 3
    month = q * 3 + 1
    return date(year, month, 1)


def _quarter_after(d: date, months_after: int = 2) -> date:
    """Devuelve el trimestre de `d + months_after` meses."""
    year = d.year
    month = d.month + months_after
    while month > 12:
        month -= 12
        year += 1
    q = (month - 1) // 3
    month = q * 3 + 1
    return date(year, month, 1)


def _ym_to_period(ym: str, frecuencia: str | None = None) -> str | None:
    """Convierte '2026-07' al periodo del dashboard ('Jul 26' o '1T-26')."""
    if not ym:
        return None
    try:
        y, m = map(int, ym.split("-"))
    except Exception:
        return None
    if frecuencia and "trimest" in frecuencia.lower():
        q = (m - 1) // 3 + 1
        return f"{q}T-{y % 100}"
    return f"{inegi.MESES[m - 1].capitalize()} {y % 100}"


def expected_period_from_frequency(
    frecuencia: str | None, as_of: date
) -> tuple[str | None, str | None]:
    """Periodo esperado para series sin calendario oficial.

    Devuelve (periodo_ym, periodo_label) o (None, None) si no se puede inferir.
    """
    f = (frecuencia or "").lower().replace(" ", "").replace("->mensual", "")
    if not f:
        return None, None

    # Si la serie se agrega y muestra como mensual (Diaria->mensual,
    # Semanal->mensual), el valor del mes en curso sólo estará disponible
    # cuando el mes termine; mientras tanto el mes esperado es el anterior.
    if (frecuencia or "").lower().replace(" ", "").endswith("->mensual"):
        prev = _prev_month(as_of)
        ym = f"{prev.year}-{prev.month:02d}"
        return ym, _ym_to_period(ym, frecuencia)

    if "diaria" in f:
        # Series diarias: se espera el mes actual desde el primer día hábil.
        first_biz = _first_business_day(as_of.year, as_of.month)
        if as_of >= first_biz:
            ym = f"{as_of.year}-{as_of.month:02d}"
        else:
            prev = _prev_month(as_of)
            ym = f"{prev.year}-{prev.month:02d}"
        return ym, _ym_to_period(ym, frecuencia)

    if "semanal" in f:
        # Series semanales: se espera el mes actual desde el primer viernes.
        first_fri = _first_friday(as_of.year, as_of.month)
        if as_of >= first_fri:
            ym = f"{as_of.year}-{as_of.month:02d}"
        else:
            prev = _prev_month(as_of)
            ym = f"{prev.year}-{prev.month:02d}"
        return ym, _ym_to_period(ym, frecuencia)

    if "mensual" in f:
        # Sin calendario mensual, se espera el mes anterior (publicación con lag).
        prev = _prev_month(as_of)
        ym = f"{prev.year}-{prev.month:02d}"
        return ym, _ym_to_period(ym, frecuencia)

    if "trimest" in f:
        # Sin calendario trimestral, se espera el trimestre recién cerrado
        # ~60 días después de su último día. Ej. Q2 (termina 30 de junio):
        # antes de ~finales de agosto se espera Q1; después se espera Q2.
        q_end = _prev_quarter(as_of, 3)  # trimestre que acaba de cerrar
        last_q_month = q_end.month + 2
        last_q_day = calendar.monthrange(q_end.year, last_q_month)[1]
        q_end_date = date(q_end.year, last_q_month, last_q_day)
        days_since_q_end = (as_of - q_end_date).days
        if days_since_q_end >= 60:
            ym = f"{q_end.year}-{q_end.month:02d}"
        else:
            prev = _prev_quarter(q_end, 3)
            ym = f"{prev.year}-{prev.month:02d}"
        return ym, _ym_to_period(ym, frecuencia)

    return None, None


def _prev_period(ym: str, frecuencia: str | None) -> str | None:
    """Devuelve el periodo inmediatamente anterior a `ym` según la frecuencia."""
    try:
        y, m = map(int, ym.split("-"))
    except Exception:
        return None
    f = (frecuencia or "").lower().replace(" ", "")
    if "trimest" in f:
        q = (m - 1) // 3
        if q == 0:
            return f"{y - 1}-10"  # Q4 del año anterior
        return f"{y}-{(q - 1) * 3 + 1:02d}"  # mes de inicio del trimestre anterior
    # Mensual, diaria o semanal -> mes anterior.
    if m == 1:
        return f"{y - 1}-12"
    return f"{y}-{m - 1:02d}"


def _mexico_city_today() -> date:
    """Fecha de hoy en America/Mexico_City."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/Mexico_City")).date()
    except Exception:
        return date.today()


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


def _obs_ym_set(ind: dict | None) -> set[str]:
    """Conjunto de periodos presentes en las observaciones del indicador."""
    out: set[str] = set()
    if not ind:
        return out
    for o in ind.get("observations", []) or []:
        p = _clean_period(o.get("period"))
        ym = _period_to_ym_flexible(p)
        if ym:
            out.add(ym)
    # También considera la granularidad original si existe.
    for o in ind.get("observations_original", []) or []:
        p = _clean_period(o.get("period"))
        ym = _period_to_ym_flexible(p)
        if ym:
            out.add(ym)
    return out


def _resolve_pub_prox(
    calendar: list[dict],
    key: str,
    ind: dict | None,
    as_of: date,
) -> tuple[dict | None, dict | None]:
    """Determina la última publicación confirmada por los datos y la siguiente
    publicación pendiente, sin depender únicamente de la fecha del calendario.

    - `pub` es el ítem del calendario con fecha <= as_of cuyo periodo de
      referencia efectivamente está en las observaciones del indicador.
    - `prox` es el siguiente ítem del calendario (por fecha) cuyo periodo no
      esté en los datos. Puede ser futuro o vencido (si la publicación aún no
      ocurre).
    """
    obs_yms = _obs_ym_set(ind)
    items = [i for i in calendar if i.get("clave") == key]
    if not items:
        return None, None
    items.sort(key=lambda i: i.get("fecha_iso") or "")

    # Estados con semántica de publicación real (no decisiones/eventos/reglas).
    data_statuses = {"publicado", "próximo", "no_anunciada"}

    items = [i for i in items if i.get("usar_para_frescura", True)]

    pub = None
    if obs_yms:
        for it in reversed(items):
            if it.get("estatus") not in data_statuses:
                continue
            if not it.get("fecha_iso"):
                continue
            if date.fromisoformat(it["fecha_iso"]) <= as_of:
                if _period_to_ym_flexible(it.get("periodo_referencia")) in obs_yms:
                    pub = it
                    break

    prox = None
    start_idx = items.index(pub) + 1 if pub else 0
    for it in items[start_idx:]:
        if it.get("estatus") not in data_statuses:
            continue
        if _period_to_ym_flexible(it.get("periodo_referencia")) not in obs_yms:
            prox = it
            break
    return pub, prox


def compute_state(
    key: str,
    dashboard_period: str | None,
    manifest_row: dict | None = None,
    update_log: dict | None = None,
    calendar: list[dict] | None = None,
    as_of: date | None = None,
    ind: dict | None = None,
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
        as_of = _mexico_city_today()
    if calendar is None:
        calendar = load_calendar()
    if update_log is None:
        update_log = _load_json(UPDATE_LOG_FILE)

    row = manifest_row or {}
    dashboard_period_clean = _clean_period(dashboard_period)
    dashboard_ym = _period_to_ym_flexible(dashboard_period_clean)

    pub, prox = _resolve_pub_prox(calendar, key, ind, as_of)

    official_period = pub.get("periodo_referencia") if pub else None
    official_ym = _period_to_ym_flexible(official_period) if official_period else None

    # Error de fuente si el pipeline falló explícitamente para este indicador.
    had_error = source_had_error(key, update_log, manifest_row)

    freq = (row or {}).get("frecuencia") or (manifest_row or {}).get("frecuencia")

    # Si no hay publicado en el calendario pero hay una próxima publicación:
    #  - Si el dashboard ya alcanzó la próxima publicación, es ACTUALIZADO.
    #  - Si aún no llega su fecha y el dashboard está exactamente un periodo
    #    antes, es ACTUALIZADO (la próxima publicación aún no se espera).
    #  - Si aún no llega su fecha pero el dashboard está más atrasado, es
    #    PENDIENTE (se espera una publicación intermedia no registrada).
    #  - Si la fecha ya pasó y el dashboard no alcanzó el periodo, es REZAGADO.
    if not pub and prox:
        prox_ym = _period_to_ym_flexible(prox.get("periodo_referencia"))
        prox_date = date.fromisoformat(prox["fecha_iso"]) if prox.get("fecha_iso") else None
        prox_due = prox_date and as_of >= prox_date
        if prox_ym and dashboard_ym:
            if dashboard_ym == prox_ym:
                official_period = prox.get("periodo_referencia")
                official_ym = prox_ym
                pub = prox  # tratar como publicado para metadata
            elif dashboard_ym > prox_ym and prox_due:
                # El dashboard está más adelantado que el calendario próximo.
                official_period = dashboard_period_clean
                official_ym = dashboard_ym
            elif not prox_due and dashboard_ym == _prev_period(prox_ym, freq):
                # La próxima publicación no vence aún; el dashboard está un
                # periodo atrás, que es el último disponible.
                official_period = dashboard_period_clean
                official_ym = dashboard_ym

    # Si sigue sin haber periodo oficial, inferirlo de la frecuencia (Banxico,
    # series sin calendario, etc.).
    fallback_ym = None
    fallback_label = None
    used_fallback = False
    if not official_ym and freq:
        fallback_ym, fallback_label = expected_period_from_frequency(freq, as_of)
        if fallback_ym:
            official_ym = fallback_ym
            official_period = fallback_label
            used_fallback = True

    # Calcular comparación cuando tenemos ambos periodos.
    compara = None
    if dashboard_ym and official_ym:
        compara = (dashboard_ym > official_ym) - (dashboard_ym < official_ym)

    if had_error:
        estado = ESTADOS["ERROR_FUENTE"]
        motivo = f"El pipeline reportó un error para {key} y el dato podría no estar actualizado."
    elif not dashboard_ym and not official_ym:
        estado = ESTADOS["ERROR_FUENTE"]
        motivo = "No se pudo determinar ni el periodo del dashboard ni el periodo oficial."
    elif not official_ym:
        estado = ESTADOS["PUBLICACION_PENDIENTE"]
        motivo = "No hay publicación oficial registrada en el calendario aún."
    elif not dashboard_ym and not (manifest_row or {}).get("serie") and (manifest_row or {}).get("fuente"):
        estado = ESTADOS["PUBLICACION_PENDIENTE"]
        motivo = "No hay datos cargados; falta confirmar el ID de serie oficial."
    elif not dashboard_ym:
        estado = ESTADOS["ERROR_FUENTE"]
        motivo = "El dashboard no tiene periodo de referencia."
    elif compara == -1:
        estado = ESTADOS["REZAGADO"]
        motivo = (
            f"El periodo esperado es {official_period}, "
            f"pero el dashboard aún muestra {dashboard_period_clean}."
        )
    elif compara == 0:
        estado = ESTADOS["ACTUALIZADO"]
        motivo = (
            f"El periodo cargado ({dashboard_period_clean}) coincide con el último "
            f"periodo esperado ({official_period})."
        )
    else:  # compara == 1: el dashboard está más adelantado que el esperado
        estado = ESTADOS["ACTUALIZADO"]
        motivo = (
            f"El dashboard tiene {dashboard_period_clean}, que está adelantado "
            f"al periodo esperado ({official_period}); se recomienda revisar el calendario."
        )

    # Si está actualizado pero no hay datos (observations vacío), pasa a pendiente/error.
    if estado == ESTADOS["ACTUALIZADO"] and not dashboard_period_clean:
        estado = ESTADOS["PUBLICACION_PENDIENTE"]
        motivo = "No hay datos cargados; la publicación está pendiente."

    if prox and prox.get("estatus") == "no_anunciada":
        prox_tipo = "no_anunciada"
    elif used_fallback:
        prox_tipo = "calculada"
    elif prox:
        prox_tipo = "oficial"
    else:
        prox_tipo = None

    return {
        "estado": estado,
        "periodo_dashboard": dashboard_period_clean,
        "periodo_oficial": official_period,
        "fecha_publicacion_oficial": pub.get("fecha_publicacion") if pub else None,
        "fecha_iso_publicacion": pub.get("fecha_iso") if pub else None,
        "proxima_publicacion": prox.get("fecha_publicacion") if prox else None,
        "periodo_proximo": prox.get("periodo_referencia") if prox else None,
        "proxima_publicacion_tipo": prox_tipo,
        "url_boletin": pub.get("url_boletin") if pub else None,
        "regla_publicacion": (prox or pub or {}).get("regla_publicacion"),
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
            ind=ind,
        )
    return result


if __name__ == "__main__":
    payload = json.loads((DATA_DIR / "indicadores.json").read_text("utf-8"))
    manifest = _load_json(DATA_DIR / "manifest.json")
    rows = {m["clave"]: m for m in manifest.get("indicadores", [])}
    diag = diagnose_all(payload["indicators"], rows)
    for k, v in diag.items():
        print(f"{k:12s} {v['estado']:22s} {v['periodo_dashboard'] or '-':8s} vs {v['periodo_oficial'] or '-':8s} | {v['motivo']}")
