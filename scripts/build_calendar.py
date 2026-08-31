#!/usr/bin/env python3
"""Construye los calendarios de publicaciones del dashboard.

Genera dos archivos:
  - data/calendario.json               (nuevo esquema enriquecido)
  - data/calendario_publicaciones.json (esquema legacy, usado por el frontend
    y build_excel.py)

Fuentes:
  - INEGI Sala de Prensa (POST /ObtenerFechasTabla/v3)
  - Banco de México (calendario mensual canal_1_{MM}{YYYY}_es.json)
  - Secretaría de Economía (respaldo manual en data/calendar_sources/)

En modo offline o bajo pytest usa caché y, si falta, los respaldos anuales.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import lib_data as L
from sources import calendar_banxico, calendar_inegi, calendar_se

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
CACHE_DIR = DATA_DIR / "cache" / "saladeprensa"
SRC_DIR = DATA_DIR / "calendar_sources"
CONFIG_DIR = ROOT / "config"
MAP_FILE = CONFIG_DIR / "calendar_map.json"
NEW_OUT = DATA_DIR / "calendario.json"
LEGACY_OUT = DATA_DIR / "calendario_publicaciones.json"

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}
MESES_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def _under_pytest() -> bool:
    return "pytest" in sys.modules


def parse_fecha(txt: str) -> date:
    """'30 de julio de 2026' -> date(2026, 7, 30)."""
    parts = txt.replace(" de ", " ").split()
    day = int(parts[0])
    month = MESES[parts[1].lower()]
    year = int(parts[2])
    return date(year, month, day)


def data_as_of() -> date:
    """Fecha de referencia: última actualización de los datos publicados."""
    try:
        payload = json.loads((DATA_DIR / "indicadores.json").read_text("utf-8"))
        dates = [
            ind.get("last_updated")
            for ind in payload.get("indicators", {}).values()
            if ind.get("last_updated")
        ]
        if dates:
            return date.fromisoformat(max(dates))
    except Exception:
        pass
    return date.today()


def _load_map() -> dict:
    if MAP_FILE.exists():
        return json.loads(MAP_FILE.read_text(encoding="utf-8"))
    return {}


def _load_meta() -> dict:
    try:
        return json.loads(L.META_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _display_date(d: date | None) -> str:
    if d is None:
        return "Por anunciar"
    return f"{d.day} de {MESES_ES[d.month - 1]} de {d.year}"


def _extract_acronyms(text: str) -> list[str]:
    return re.findall(r"\(([A-Z]+)\)", text)


def _program_excluded(program: str, patterns: list[str]) -> bool:
    low = program.lower()
    return any(p.lower() in low for p in patterns)


def _program_includes(program: str, patterns: list[str]) -> bool:
    low = program.lower()
    return any(p.lower() in low for p in patterns)


def _score_program(program: str, preferred: list[str]) -> int:
    if not preferred:
        return 0
    low = program.lower()
    return sum(1 for p in preferred if p.lower() in low)


def _match_inegi_indicator(program: str, cfg: dict) -> str | None:
    """Mapea un programa del INEGI a una clave del dashboard."""
    ind_cfg = cfg.get("inegi", {}).get("indicators", {})
    acronyms = _extract_acronyms(program)
    # 1) por acrónimo
    for key, meta in ind_cfg.items():
        for ac in acronyms:
            if ac.upper() in [a.upper() for a in meta.get("acronyms", [])] or ac.upper() == key:
                if not _program_excluded(program, meta.get("program_exclude", [])):
                    return key
    # 2) por subcadena
    for key, meta in ind_cfg.items():
        if _program_excluded(program, meta.get("program_exclude", [])):
            continue
        if _program_includes(program, meta.get("program_contains", [])):
            return key
    return None


def _map_inegi_events(raw_events: list[dict], cfg: dict, warnings: list[str]) -> list[dict]:
    """Mapea y desduplica eventos del INEGI."""
    ind_cfg = cfg.get("inegi", {}).get("indicators", {})
    groups: dict[tuple[str, date], list[dict]] = {}
    for ev in raw_events:
        key = _match_inegi_indicator(ev["program"], cfg)
        if not key:
            continue
        meta = ind_cfg.get(key, {})
        if _program_excluded(ev["program"], meta.get("program_exclude", [])):
            continue
        if _program_excluded(ev["program"], cfg.get("inegi", {}).get("exclude_substrings", [])):
            continue
        d = ev["date"]
        if (key, d) not in groups:
            groups[(key, d)] = []
        groups[(key, d)].append(ev)

    events: list[dict] = []
    for (key, d), items in groups.items():
        meta = ind_cfg.get(key, {})
        preferred = meta.get("preferred_program_contains", [])
        best = max(items, key=lambda x: _score_program(x["program"], preferred))
        events.append({
            **best,
            "indicator": key,
            "product": meta.get("product", best["program"]),
            "frequency": meta.get("frequency", "Mensual"),
            "category": meta.get("category", "Actividad económica"),
            "institution": meta.get("institution", "INEGI"),
            "sigla": meta.get("sigla", key),
            "usar_para_frescura": meta.get("usar_para_frescura", True),
            "is_evento": False,
            "no_anunciada": False,
        })
    return events


def _map_banxico_events(raw_events: list[dict], cfg: dict) -> list[dict]:
    """Enriquece eventos de Banxico con metadatos del mapa."""
    bx_cfg = cfg.get("banxico", {}).get("indicators", {})
    events: list[dict] = []
    for ev in raw_events:
        key = ev.get("indicator")
        if not key:
            continue
        meta = bx_cfg.get(key, {})
        events.append({
            **ev,
            "product": meta.get("product", ev.get("program", key)),
            "frequency": meta.get("frequency", "Semanal"),
            "category": meta.get("category", "Financiero"),
            "institution": meta.get("institution", "Banco de México"),
            "sigla": meta.get("sigla", key),
            "usar_para_frescura": meta.get("usar_para_frescura", False),
            "is_evento": meta.get("is_evento", False) or ev.get("is_evento", False),
            "no_anunciada": False,
        })
    return events


def _map_se_events(raw_events: list[dict], cfg: dict) -> list[dict]:
    """Enriquece eventos de la Secretaría de Economía."""
    se_cfg = cfg.get("se", {}).get("indicators", {})
    events: list[dict] = []
    for ev in raw_events:
        key = ev.get("indicator", "IED")
        meta = se_cfg.get(key, {})
        if ev.get("no_anunciada"):
            events.append({
                **ev,
                "product": meta.get("product", ev.get("program", "IED")),
                "frequency": meta.get("frequency", "Trimestral"),
                "category": meta.get("category", "Sector externo"),
                "institution": meta.get("institution", "Secretaría de Economía"),
                "sigla": meta.get("sigla", "IED"),
                "usar_para_frescura": meta.get("usar_para_frescura", True),
                "is_evento": False,
                "no_anunciada": True,
            })
        else:
            events.append({
                **ev,
                "product": meta.get("product", ev.get("program", "IED")),
                "frequency": meta.get("frequency", "Trimestral"),
                "category": meta.get("category", "Sector externo"),
                "institution": meta.get("institution", "Secretaría de Economía"),
                "sigla": meta.get("sigla", "IED"),
                "usar_para_frescura": meta.get("usar_para_frescura", True),
                "is_evento": False,
                "no_anunciada": False,
            })
    return events


def _normalize_period(periodo: str | None) -> str:
    if not periodo:
        return "Próximo periodo"
    # Normaliza "4T 2025" -> "4° trimestre 2025"
    m = re.match(r"(\d)T\s+(\d{4})", periodo.strip())
    if m:
        return f"{m.group(1)}° trimestre {m.group(2)}"
    m2 = re.match(r"(\d+)T\s+(\d{4})", periodo.strip())
    if m2:
        return f"{m2.group(1)}° trimestre {m2.group(2)}"
    return periodo.strip()


def _fallback_publicacion_to_event(pub: dict, entry: dict, year: int, source_name: str) -> dict | None:
    """Convierte una publicación de los respaldos anuales en evento normalizado."""
    fecha = pub.get("fecha")
    if fecha:
        try:
            d = parse_fecha(fecha)
        except Exception:
            return None
    else:
        d = None
    url = pub.get("url") or ""
    deliverables: list[dict] = []
    if url:
        deliverables.append({"type": "comunicado", "format": "pdf", "url": url, "label": "Boletín", "size": None})
    product = entry.get("producto") or entry.get("indicador") or ""
    return {
        "source": source_name,
        "institution": entry.get("institucion", "INEGI"),
        "program": product,
        "product": product,
        "period": _normalize_period(pub.get("periodo")),
        "date": d,
        "url": url or _sala_prensa_url(entry.get("clave")),
        "url_consulta": url,
        "deliverables": deliverables,
        "comentario": pub.get("comentario"),
        "indicator": entry.get("clave"),
        "frequency": entry.get("frecuencia", "Mensual"),
        "category": _category_for_key(entry.get("clave")),
        "sigla": entry.get("clave"),
        "usar_para_frescura": entry.get("usar_para_frescura", True),
        "is_evento": entry.get("tipo") == "evento",
        "no_anunciada": False,
    }


def _sala_prensa_url(clave: str | None) -> str:
    if clave == "TIPOCAMBIO":
        return "https://www.banxico.org.mx/mercados/tasas-de-referencia.html"
    if clave == "RESERVAS":
        return "https://www.banxico.org.mx/publicaciones-y-prensa/reservas-internacionales/"
    if clave == "IED":
        return "https://www.gob.mx/se"
    return "https://www.inegi.org.mx/app/saladeprensa/calendario/"


def _category_for_key(key: str | None) -> str:
    cfg = _load_map()
    for section in ("inegi", "banxico", "se"):
        ind = cfg.get(section, {}).get("indicators", {}).get(key or "")
        if ind:
            return ind.get("category", "Actividad económica")
    rules = cfg.get("rules", {})
    if key in rules:
        return rules[key].get("category", "Financiero")
    mapping = {
        "PIB": "Actividad económica", "PIBSEC": "Actividad económica", "IOAE": "Actividad económica",
        "IGAE": "Actividad económica", "IMAI": "Actividad económica", "EMIM": "Actividad económica",
        "INPC": "Precios", "INPP": "Precios", "CONSUMO": "Consumo e inversión",
        "IMFBCF": "Consumo e inversión", "DESOCUP": "Mercado laboral", "EMOE": "Mercado laboral",
        "BCMM": "Sector externo", "IED": "Sector externo",
        "TIPOCAMBIO": "Financiero", "TASA": "Financiero", "RESERVAS": "Financiero",
    }
    return mapping.get(key, "Actividad económica")


def _frequency_for_key(key: str | None) -> str:
    cfg = _load_map()
    for section in ("inegi", "banxico", "se"):
        ind = cfg.get(section, {}).get("indicators", {}).get(key or "")
        if ind:
            return ind.get("frequency", "Mensual")
    mapping = {
        "PIB": "Trimestral", "PIBSEC": "Trimestral", "IOAE": "Mensual", "IGAE": "Mensual",
        "IMAI": "Mensual", "EMIM": "Mensual", "INPC": "Mensual", "INPP": "Mensual",
        "CONSUMO": "Mensual", "IMFBCF": "Mensual", "DESOCUP": "Mensual", "EMOE": "Mensual",
        "BCMM": "Mensual", "IED": "Trimestral", "TIPOCAMBIO": "Diaria",
        "TASA": "Decisiones de política monetaria", "RESERVAS": "Semanal",
    }
    return mapping.get(key, "Mensual")


def _display_name(key: str, product: str | None) -> str:
    meta = _load_meta()
    prof = meta.get("profile", {}).get(key, {})
    if prof.get("nombre"):
        return prof["nombre"]
    scaffold = meta.get("scaffolds", {}).get(key, {})
    if scaffold.get("nombre"):
        return scaffold["nombre"]
    return product or key


def _load_fallback_events(years: list[int]) -> list[dict]:
    """Carga eventos desde los respaldos anuales en data/calendar_sources/."""
    events: list[dict] = []
    for year in years:
        for suffix, source_name in ("", "INEGI Sala de Prensa"), ("_banxico", "Banco de México"), ("_se", "Secretaría de Economía"):
            path = SRC_DIR / f"{year}{suffix}.json"
            if not path.exists():
                continue
            try:
                src = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            for entry in src.get("entries", []):
                for pub in entry.get("publicaciones", []):
                    ev = _fallback_publicacion_to_event(pub, entry, year, source_name)
                    if ev:
                        events.append(ev)
                if entry.get("proxima_no_anunciada"):
                    ev = {
                        "source": source_name,
                        "institution": entry.get("institucion", "Secretaría de Economía"),
                        "program": entry.get("producto") or entry.get("indicador"),
                        "product": entry.get("producto") or entry.get("indicador"),
                        "period": _normalize_period(entry.get("proxima_periodo")),
                        "date": None,
                        "url": "",
                        "url_consulta": "",
                        "deliverables": [],
                        "comentario": entry.get("proxima_comentario", "Próxima fecha oficial no anunciada"),
                        "indicator": entry.get("clave"),
                        "frequency": entry.get("frecuencia", "Trimestral"),
                        "category": _category_for_key(entry.get("clave")),
                        "sigla": entry.get("clave"),
                        "usar_para_frescura": entry.get("usar_para_frescura", True),
                        "is_evento": False,
                        "no_anunciada": True,
                    }
                    events.append(ev)
                # Regla sin fechas (ej. TIPOCAMBIO)
                if not entry.get("publicaciones") and entry.get("regla_publicacion") and not entry.get("proxima_no_anunciada"):
                    ev = {
                        "source": source_name,
                        "institution": entry.get("institucion", "Banco de México"),
                        "program": entry.get("indicador") or entry.get("producto"),
                        "product": entry.get("producto") or entry.get("indicador"),
                        "period": entry.get("proxima_periodo") or "Por determinar",
                        "date": None,
                        "url": entry.get("url") or _sala_prensa_url(entry.get("clave")),
                        "url_consulta": entry.get("url") or _sala_prensa_url(entry.get("clave")),
                        "deliverables": [],
                        "comentario": None,
                        "indicator": entry.get("clave"),
                        "frequency": entry.get("frecuencia", "Diaria"),
                        "category": _category_for_key(entry.get("clave")),
                        "sigla": entry.get("clave"),
                        "usar_para_frescura": entry.get("usar_para_frescura", False),
                        "is_evento": False,
                        "no_anunciada": False,
                        "regla_texto": entry.get("regla_publicacion"),
                        "es_regla": True,
                    }
                    events.append(ev)
    return events


def _dedup_events(events: list[dict]) -> list[dict]:
    """Elimina eventos duplicados por (indicador, fecha, periodo)."""
    seen: dict[tuple[str, str, str], dict] = {}
    for ev in events:
        key = ev.get("indicator", "")
        d = ev.get("date")
        d_key = d.isoformat() if d else "_"
        period = ev.get("period") or ""
        tup = (key, d_key, period)
        if tup in seen:
            # Conservar el que tenga URL / entregables; si no, el primero.
            old = seen[tup]
            if ev.get("url") and not old.get("url"):
                seen[tup] = ev
            elif ev.get("deliverables") and not old.get("deliverables"):
                seen[tup] = ev
        else:
            seen[tup] = ev
    return list(seen.values())


def _build_events(as_of: date, offline: bool) -> tuple[list[dict], list[dict], dict]:
    """Obtiene eventos de todas las fuentes y genera las reglas."""
    cfg = _load_map()
    warnings: list[str] = []
    target_years = [as_of.year - 1, as_of.year, as_of.year + 1]

    # Fuentes principales
    inegi_events, inegi_status = calendar_inegi.fetch(target_years, CACHE_DIR, offline=offline)
    banxico_events, banxico_status = calendar_banxico.fetch(target_years, CACHE_DIR, offline=offline)
    se_events, se_status = calendar_se.fetch(as_of.year, SRC_DIR)

    events: list[dict] = []
    events.extend(_map_inegi_events(inegi_events, cfg, warnings))
    events.extend(_map_banxico_events(banxico_events, cfg))
    events.extend(_map_se_events(se_events, cfg))

    # Si faltan claves, rellenar con respaldo
    present = set(ev.get("indicator") for ev in events if ev.get("indicator"))
    meta = _load_meta()
    target_keys = set(meta.get("principal", [])) | set(meta.get("complementario", []))
    missing_keys = target_keys - present
    if missing_keys or not events:
        fallback = _load_fallback_events(target_years)
        for ev in fallback:
            if not missing_keys and ev.get("indicator") not in present:
                continue
            if ev.get("indicator") in missing_keys or (not events and ev.get("indicator") in target_keys):
                events.append(ev)

    # Asegurar PIBSEC aunque no venga del INEGI
    if "PIBSEC" not in present:
        for ev in _load_fallback_events(target_years):
            if ev.get("indicator") == "PIBSEC":
                events.append(ev)

    events = _dedup_events(events)

    # Reglas
    rules: list[dict] = []
    rules_cfg = cfg.get("rules", {})
    for rkey, rmeta in rules_cfg.items():
        rules.append({
            "indicator": rkey,
            "name": rmeta.get("name", rkey),
            "product": rmeta.get("product", rkey),
            "frequency": rmeta.get("frequency", "Diaria"),
            "institution": rmeta.get("institution", ""),
            "category": rmeta.get("category", "Financiero"),
            "rule_text": rmeta.get("rule_text", ""),
            "next_period": None,
            "url": rmeta.get("url", _sala_prensa_url(rkey)),
            "type": "rule",
        })

    # Regla de IED si no hay próxima fecha exacta
    ied_events = [e for e in events if e.get("indicator") == "IED" and e.get("date")]
    ied_future = [e for e in ied_events if e.get("date") and e["date"] > as_of]
    if not ied_future:
        ied_rule = rules_cfg.get("IED", {})
        if ied_rule:
            # Evitar duplicar si ya existe
            if not any(r["indicator"] == "IED" for r in rules):
                rules.append({
                    "indicator": "IED",
                    "name": ied_rule.get("name", "Inversión Extranjera Directa"),
                    "product": ied_rule.get("product", "IED"),
                    "frequency": ied_rule.get("frequency", "Trimestral"),
                    "institution": ied_rule.get("institution", "Secretaría de Economía"),
                    "category": ied_rule.get("category", "Sector externo"),
                    "rule_text": ied_rule.get("rule_text", ""),
                    "next_period": None,
                    "url": ied_rule.get("url", "https://www.gob.mx/se"),
                    "type": "rule",
                })

    sources_status = {
        "INEGI Sala de Prensa": {**inegi_status, "url": "https://www.inegi.org.mx/app/saladeprensa/calendario/"},
        "Banco de México calendario": {**banxico_status, "url": "https://www.banxico.org.mx/publicaciones-y-prensa/calendario-de-publicaciones-banco-de-mexico/"},
        "Secretaría de Economía (manual)": {**se_status},
    }
    return events, rules, sources_status


def _new_status(ev: dict, as_of: date) -> str:
    d = ev.get("date")
    if d is None:
        return "próximo"
    if d <= as_of:
        return "publicado"
    return "próximo"


def _legacy_status(ev: dict, as_of: date) -> str:
    if ev.get("no_anunciada"):
        return "no_anunciada"
    if ev.get("es_regla"):
        return "regla"
    if ev.get("is_evento"):
        return "evento"
    d = ev.get("date")
    if d is None:
        return "regla"
    if d <= as_of:
        return "publicado"
    return "próximo"


def _to_new_event(ev: dict, as_of: date) -> dict:
    d = ev.get("date")
    status = _new_status(ev, as_of)
    url = ev.get("url") or _sala_prensa_url(ev.get("indicator"))
    deliverables = ev.get("deliverables", [])
    if not deliverables:
        deliverables = [{
            "type": "comunicado",
            "format": "html",
            "url": url,
            "label": "Boletín / página oficial",
            "size": None,
        }]
    return {
        "indicator": ev["indicator"],
        "program": ev.get("program"),
        "product": ev.get("product"),
        "publication_date": d.isoformat() if d else None,
        "publication_date_display": _display_date(d),
        "reference_period": ev.get("period") or "",
        "frequency": ev.get("frequency") or _frequency_for_key(ev.get("indicator")),
        "status": status,
        "source": ev.get("source"),
        "institution": ev.get("institution"),
        "category": ev.get("category") or _category_for_key(ev.get("indicator")),
        "sigla": ev.get("sigla") or ev.get("indicator"),
        "type": "event",
        "url": url,
        "deliverables": deliverables,
        "comentario": ev.get("comentario"),
        "anio": d.year if d else None,
        "mes": d.month if d else None,
        "fecha_iso": d.isoformat() if d else None,
    }


def _to_legacy_item(ev: dict, as_of: date) -> dict:
    d = ev.get("date")
    status = _legacy_status(ev, as_of)
    if ev.get("es_regla"):
        fecha_publicacion = None
        fecha_iso = None
        anio = None
        mes = None
    elif ev.get("no_anunciada"):
        if d:
            fecha_publicacion = _display_date(d)
            fecha_iso = d.isoformat()
            anio, mes = d.year, d.month
        else:
            fecha_publicacion = "Por anunciar"
            fecha_iso = "9999-12-31"
            anio = None
            mes = None
    else:
        fecha_publicacion = _display_date(d) if d else None
        fecha_iso = d.isoformat() if d else None
        anio = d.year if d else None
        mes = d.month if d else None

    item: dict = {
        "clave": ev["indicator"],
        "indicador": _display_name(ev["indicator"], ev.get("product")),
        "producto": ev.get("product"),
        "institucion": ev.get("institution"),
        "frecuencia": ev.get("frequency") or _frequency_for_key(ev.get("indicator")),
        "regla_publicacion": ev.get("regla_texto") or None,
        "usar_para_frescura": ev.get("usar_para_frescura", True),
        "fecha_publicacion": fecha_publicacion,
        "fecha_iso": fecha_iso,
        "anio": anio,
        "mes": mes,
        "periodo_referencia": ev.get("period") or ("Por determinar" if ev.get("es_regla") else ("Próximo periodo" if ev.get("no_anunciada") else "")),
        "estatus": status,
        "url_boletin": ev.get("url") or _sala_prensa_url(ev.get("indicator")),
    }
    if ev.get("comentario"):
        item["comentario"] = ev["comentario"]
    return item


def _to_legacy_rule(rule: dict) -> dict:
    return {
        "clave": rule["indicator"],
        "indicador": rule["name"],
        "producto": rule["product"],
        "institucion": rule["institution"],
        "frecuencia": rule["frequency"],
        "regla_publicacion": rule["rule_text"],
        "usar_para_frescura": rule.get("usar_para_frescura", False),
        "fecha_publicacion": None,
        "fecha_iso": None,
        "anio": None,
        "mes": None,
        "periodo_referencia": rule.get("next_period") or "Por determinar",
        "estatus": "regla",
        "url_boletin": rule.get("url"),
    }


def _build_new_payload(events: list[dict], rules: list[dict], sources_status: dict, as_of: date) -> dict:
    new_events = [_to_new_event(ev, as_of) for ev in events if not ev.get("es_regla")]
    for rule in rules:
        rule.setdefault("status", "regla")
    # Ordenar eventos por fecha (None al final)
    new_events.sort(key=lambda x: (x["publication_date"] or "9999-12-31", x["indicator"]))

    upcoming = sorted(
        [e for e in new_events if e["status"] == "próximo"],
        key=lambda x: (x["publication_date"] or "9999-12-31", x["indicator"]),
    )[:20]
    recent = sorted(
        [e for e in new_events if e["status"] == "publicado"],
        key=lambda x: (x["publication_date"] or "", x["indicator"]),
        reverse=True,
    )[:20]

    years = sorted({e["anio"] for e in new_events if e.get("anio")} | {as_of.year - 1, as_of.year, as_of.year + 1})

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "as_of": as_of.isoformat(),
        "fuente": "Calendario oficial de difusión",
        "sources": sources_status,
        "years": years,
        "events": new_events,
        "rules": rules,
        "upcoming": upcoming,
        "recent": recent,
        "categories": _load_map().get("categories", {}),
    }


def _build_legacy_payload(events: list[dict], rules: list[dict], as_of: date, sources_status: dict) -> dict:
    items: list[dict] = []
    for ev in events:
        if ev.get("es_regla"):
            continue
        if ev.get("no_anunciada"):
            items.append(_to_legacy_item(ev, as_of))
        else:
            items.append(_to_legacy_item(ev, as_of))
    for rule in rules:
        items.append(_to_legacy_rule(rule))

    def _sort_key(x):
        iso = x.get("fecha_iso")
        return (iso or "", 0 if iso else 1, x["indicador"])

    items.sort(key=_sort_key)

    # actualizado: usar la fecha más reciente de consulta de las fuentes, o as_of
    actualizado = as_of.isoformat()
    for st in sources_status.values():
        if st.get("consulted_at") and st["consulted_at"] > actualizado:
            actualizado = st["consulted_at"]

    return {
        "_comment": "Generado por scripts/build_calendar.py a partir de fuentes oficiales y respaldos. No editar a mano.",
        "fuente": " | ".join(s for s in sources_status) or "Calendario oficial de difusión",
        "actualizado": actualizado,
        "as_of": as_of.isoformat(),
        "anios": sorted({e.get("anio") for e in items if e.get("anio")}),
        "items": items,
    }


def build(as_of: date | None = None, offline: bool | None = None) -> dict:
    """Construye el calendario legacy y, como efecto colateral, escribe ambos JSON.

    Devuelve el diccionario legacy para mantener compatibilidad con build_data.py.
    """
    if as_of is None:
        as_of = data_as_of()
    if offline is None:
        offline = _under_pytest()

    events, rules, sources_status = _build_events(as_of, offline)

    new_payload = _build_new_payload(events, rules, sources_status, as_of)
    legacy_payload = _build_legacy_payload(events, rules, as_of, sources_status)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    NEW_OUT.write_text(json.dumps(new_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    LEGACY_OUT.write_text(json.dumps(legacy_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return legacy_payload


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Construye el calendario de publicaciones.")
    ap.add_argument("--as-of", help="Fecha de referencia YYYY-MM-DD")
    ap.add_argument("--offline", action="store_true", help="No consultar fuentes en red")
    # Bajo pytest no se hacen llamadas de red salvo que se indique lo contrario.
    if _under_pytest() and argv is None:
        argv = []
    args = ap.parse_args(argv)
    as_of = date.fromisoformat(args.as_of) if args.as_of else data_as_of()
    offline = args.offline or _under_pytest()
    legacy = build(as_of=as_of, offline=offline)
    pub = sum(1 for it in legacy["items"] if it.get("estatus") == "publicado")
    prox = len(legacy["items"]) - pub
    print(f"OK: calendarios generados · {len(legacy['items'])} publicaciones "
          f"({pub} publicadas, {prox} próximas/reglas) · as_of={as_of.isoformat()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
