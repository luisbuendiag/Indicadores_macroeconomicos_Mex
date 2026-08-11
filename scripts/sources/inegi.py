"""Conector INEGI (BIE). Requiere INEGI_TOKEN.

Consulta la API de Indicadores del INEGI (Banco de Información Económica, BIE)
para las series cuyo ID esté confirmado en config/series.json. Cada indicador
puede tener una o varias series (por columnas del dashboard). Soporta:
  - multi-columna: el valor de config/series.json puede ser un dict o una lista
    de dicts con 'serie' y 'columna_objetivo'.
  - factor: multiplica el valor de la API (p. ej. 0.01 para pasar de % a fracción).
  - transform: 'yoy' (variación anual %), 'mom' (variación mensual %),
    'qoq' (variación trimestral %), 'diff_yoy_pp' (cambio de la inflación anual
    respecto al mes previo, en puntos porcentuales),
    'mom_abs' (diferencia absoluta respecto al mes previo, p. ej. puntos).

El pipeline (build_data.py) fusiona cada serie sobre la columna objetivo del
indicador existente, conservando el resto de columnas/desgloses de respaldo.
"""
from __future__ import annotations

import os
from datetime import datetime

from .base import SourceResult, http_get_json

ENDPOINT = ("https://www.inegi.org.mx/app/api/indicadores/desarrolladores/jsonxml/"
            "INDICATOR/{ids}/es/{geo}/false/{db}/2.0/{token}?type=json")

DEFAULT_DB = "BIE-BISE"
DEFAULT_GEO = "00"

MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
         "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
_MES_IDX = {m: i + 1 for i, m in enumerate(MESES)}


def _two_digit_year(yy: int) -> str:
    return f"{yy:02d}"[-2:]


def ym_to_label(ym: str, freq: int | str | None = None) -> str:
    """Convierte 'AAAA-MM' a la etiqueta del tablero.

    Frecuencia 4 = trimestral ('1T-26'), 8/9 = mensual ('May 26').
    """
    year, month = ym.split("-")
    mi = int(month)
    yy = int(year)
    if str(freq) == "4":
        q = (mi - 1) // 3 + 1
        return f"{q}T-{_two_digit_year(yy)}"
    return f"{MESES[mi - 1]} {_two_digit_year(yy)}"


def label_to_ym(period: str) -> str | None:
    """Convierte una etiqueta del tablero ('Abr 26 P', '1T-25 R') a 'AAAA-MM'.

    Devuelve None si no reconoce el formato.
    """
    per = (period or "").strip()
    # Trimestral: "1T-25 R" -> 2025-01, "2T-26" -> 2026-04 (mes inicial)
    m_trim = per.split()
    if m_trim and m_trim[0] and "T-" in m_trim[0]:
        q_part, yy = m_trim[0].split("T-")
        try:
            q = int(q_part)
            y = int(yy)
            if 1 <= q <= 4:
                month = (q - 1) * 3 + 1
                return f"{2000 + y:04d}-{month:02d}"
        except ValueError:
            pass
    # Mensual: "Abr 26 P"
    parts = per.split()
    if len(parts) < 2:
        return None
    mi = _MES_IDX.get(parts[0][:3].capitalize())
    if mi is None:
        return None
    try:
        yy = int(parts[1])
    except ValueError:
        return None
    return f"{2000 + yy:04d}-{mi:02d}"


def _tp_to_ym(time_period: str) -> str | None:
    """Convierte 'AAAA/MM' del BIE a 'AAAA-MM'."""
    tp = (time_period or "").strip()
    if "/" not in tp:
        return None
    y, m = tp.split("/", 1)
    try:
        mi = int(m)
    except ValueError:
        return None
    if not (1 <= mi <= 12) or len(y) != 4 or not y.isdigit():
        return None
    return f"{y}-{mi:02d}"


def _ym_minus_months(ym: str, months: int) -> str | None:
    """Resta meses a un 'AAAA-MM'."""
    y, m = map(int, ym.split("-"))
    total = y * 12 + (m - 1) - months
    if total < 0:
        return None
    ny, nm = divmod(total, 12)
    return f"{ny:04d}-{nm + 1:02d}"


def _transform_observations(obs: list[dict], transform: str | None) -> list[dict]:
    """Aplica transformaciones derivadas (yoy, mom, qoq, diff_yoy_pp)."""
    if not transform:
        return obs

    by_ym = {o["ym"]: o["value"] for o in obs}
    out = []
    for o in obs:
        val = None
        if transform == "yoy":
            prev = _ym_minus_months(o["ym"], 12)
            if prev and prev in by_ym and by_ym[prev]:
                val = (o["value"] / by_ym[prev] - 1) * 100
        elif transform == "mom":
            prev = _ym_minus_months(o["ym"], 1)
            if prev and prev in by_ym and by_ym[prev]:
                val = (o["value"] / by_ym[prev] - 1) * 100
        elif transform == "qoq":
            prev = _ym_minus_months(o["ym"], 3)
            if prev and prev in by_ym and by_ym[prev]:
                val = (o["value"] / by_ym[prev] - 1) * 100
        elif transform == "mom_abs":
            prev = _ym_minus_months(o["ym"], 1)
            if prev and prev in by_ym and by_ym[prev] is not None:
                val = o["value"] - by_ym[prev]
        elif transform == "diff_yoy_pp":
            # Primero calcular yoy
            prev_y = _ym_minus_months(o["ym"], 12)
            if prev_y and prev_y in by_ym and by_ym[prev_y]:
                yoy = (o["value"] / by_ym[prev_y] - 1) * 100
                # Mes previo
                prev_m = _ym_minus_months(o["ym"], 1)
                if prev_m and prev_m in by_ym:
                    prev_y_ym = _ym_minus_months(prev_m, 12)
                    if prev_y_ym and prev_y_ym in by_ym and by_ym[prev_y_ym]:
                        yoy_prev = (by_ym[prev_m] / by_ym[prev_y_ym] - 1) * 100
                        val = yoy - yoy_prev
        if val is not None and not (val != val):  # evitar NaN
            out.append({"ym": o["ym"], "value": val, "period": o.get("period", o["ym"])})
    return out


def _parse_series(raw: dict) -> tuple[list[dict], dict] | None:
    """Extrae observaciones ordenadas, metadatos y etiqueta de periodo."""
    series = (raw or {}).get("Series") or []
    if not series:
        return None
    s = series[0]
    freq = s.get("FREQ")
    meta = {
        "indicador": s.get("INDICADOR"),
        "freq": freq,
        "unit": s.get("UNIT"),
        "lastupdate": s.get("LASTUPDATE"),
        "source": s.get("SOURCE"),
    }
    obs = []
    for o in s.get("OBSERVATIONS") or []:
        ym = _tp_to_ym(o.get("TIME_PERIOD"))
        val = o.get("OBS_VALUE")
        if ym is None or val in (None, ""):
            continue
        try:
            num = float(val)
        except (TypeError, ValueError):
            continue
        if num != num:  # NaN
            continue
        obs.append({"ym": ym, "value": num,
                    "period": ym_to_label(ym, freq)})
    obs.sort(key=lambda x: x["ym"])
    return obs, meta


def _fetch_one(spec: dict, token: str, start_year: int) -> dict | None:
    """Consulta y transforma una serie individual."""
    serie_id = str(spec["serie"])
    url = ENDPOINT.format(ids=serie_id, token=token,
                          db=spec.get("db", DEFAULT_DB),
                          geo=spec.get("geo", DEFAULT_GEO))
    raw = http_get_json(url)
    parsed = _parse_series(raw)
    if not parsed or not parsed[0]:
        return None
    obs, meta = parsed

    # Para transformaciones yoy/mom/qoq/mom_abs necesitamos observaciones previas.
    transform = spec.get("transform")
    if transform in ("yoy", "qoq", "mom", "mom_abs"):
        # extendemos el inicio un año atrás para tener el periodo previo
        start = max(1, start_year - 1)
    else:
        start = start_year
    obs = [o for o in obs if int(o["ym"][:4]) >= start]

    obs = _transform_observations(obs, transform)
    # filtrar al rango solicitado después de transformar
    obs = [o for o in obs if int(o["ym"][:4]) >= start_year]
    if not obs:
        return None

    factor = spec.get("factor", 1.0)
    for o in obs:
        o["value"] = o["value"] * factor

    last = obs[-1]
    return {
        "target_column": int(spec.get("columna_objetivo", 0)),
        "api_total": obs,
        "serie": serie_id,
        "link": spec.get("link"),
        "freq": meta.get("freq"),
        "api_meta": {
            "serie": serie_id, "freq": meta.get("freq"), "unit": meta.get("unit"),
            "lastupdate": meta.get("lastupdate"), "n_obs": len(obs),
            "ultimo_valor": round(last["value"], 6),
            "ultima_ym": last["ym"], "ultima_observacion": last.get("period", ym_to_label(last["ym"], meta.get("freq"))),
        },
    }


def _specs_for(key: str, value) -> list[dict]:
    """Normaliza la configuración de un indicador a una lista de especificaciones."""
    if isinstance(value, list):
        return [s for s in value if isinstance(s, dict) and s.get("serie")]
    if isinstance(value, dict) and value.get("serie"):
        return [value]
    return []


def fetch(config: dict, start_year: int = 2018) -> SourceResult:
    token = os.environ.get("INEGI_TOKEN")
    if not token:
        return SourceResult(False, warnings=[
            "INEGI_TOKEN ausente: se omite la actualización desde INEGI; se conservan datos previos."])
    inegi = config.get("inegi", {})
    confirmed: dict[str, list[dict]] = {}
    for key, value in inegi.items():
        if key.startswith("_"):
            continue
        specs = _specs_for(key, value)
        if specs:
            confirmed[key] = specs

    if not confirmed:
        return SourceResult(False, warnings=[
            "INEGI: no hay IDs de serie confirmados en config/series.json. "
            "Confírmalos contra el catálogo del BIE antes de activar la descarga; "
            "se conservan los datos previos."])

    data: dict = {}
    warnings: list[str] = []
    for key, specs in confirmed.items():
        items: list[dict] = []
        for spec in specs:
            serie_id = str(spec["serie"])
            try:
                item = _fetch_one(spec, token, start_year)
            except Exception as e:  # noqa: BLE001 - resiliencia del pipeline
                warnings.append(f"INEGI {key}: error de consulta (serie {serie_id}): {e}")
                continue
            if not item or not item["api_total"]:
                warnings.append(f"INEGI {key}: respuesta sin observaciones (serie {serie_id}).")
                continue
            items.append(item)
            meta = item.get("api_meta", {})
            warnings.append(
                f"INEGI {key}: {meta.get('n_obs')} observaciones (serie {serie_id}, base "
                f"{spec.get('db', DEFAULT_DB)}); última {meta.get('ultima_observacion')} = "
                f"{meta.get('ultimo_valor')}; actualización BIE {meta.get('lastupdate')}.")
        if items:
            data[key] = items if len(items) > 1 else items[0]

    return SourceResult(bool(data), data=data, warnings=warnings)


def today_iso() -> str:
    return datetime.now().astimezone().isoformat()
