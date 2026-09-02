"""Construye el historial de decisiones de política monetaria de Banxico.

Usa:
- la serie diaria SIE del indicador TASA para obtener niveles vigentes; y
- el calendario de publicaciones de Banxico (eventos del tipo TASA) para
  identificar fechas de anuncio, comunicados y dirección de la decisión.

El calendario de Banxico describe cada decisión con frases como:
  "El objetivo ... disminuye en 50 puntos base"
  "El objetivo ... se mantiene sin cambio en 6.50 por ciento"

A partir de ahí y de la serie diaria se genera una lista de decisiones con:
  announcement_date, effective_date, previous_rate, new_rate, decision,
  change_bp, comunicado_url.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
CAL_FILES = [DATA_DIR / "calendario.json", DATA_DIR / "calendario_publicaciones.json"]


def _load_calendar() -> dict:
    for f in CAL_FILES:
        if f.exists():
            return json.loads(f.read_text(encoding="utf-8"))
    return {}


def _tasa_events(cal: dict) -> list[dict]:
    events = cal.get("events", []) if isinstance(cal, dict) else cal
    out = []
    for e in events:
        if (e.get("indicator") == "TASA" or e.get("sigla") == "TASA"):
            status = (e.get("status") or "").lower()
            if status in ("próximo", "proximo", "programado"):
                continue
            out.append(e)
    out.sort(key=lambda x: x.get("publication_date") or x.get("fecha_iso") or "")
    return out


def _parse_date(s: str) -> date | None:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _rate_on_or_before(by_date: dict, target: date) -> float | None:
    if target in by_date:
        return by_date[target]
    for i in range(1, 60):
        d = target - timedelta(days=i)
        if d in by_date:
            return by_date[d]
    return None


def _first_change_after(by_date: dict, start: date) -> tuple[date, float, float] | None:
    """Devuelve (effective_date, new_rate, previous_rate) del primer cambio de tasa
    en o después de start. Si no hay cambio, devuelve None."""
    sorted_dates = sorted(by_date.keys())
    prev = None
    for d in sorted_dates:
        if d < start:
            prev = by_date[d]
            continue
        if prev is not None and d >= start and abs(by_date[d] - prev) > 1e-6:
            return d, by_date[d], prev
        prev = by_date[d]
    return None


def _parse_decision_text(text: str) -> tuple[str, int | None]:
    """Infiere decisión y magnitud en puntos base a partir del texto del calendario."""
    text = (text or "").lower()
    if "disminuye" in text or "baj" in text or "recorte" in text:
        mag = _extract_bp(text)
        return "recorte", -mag if mag is not None else None
    if "aumenta" in text or "alza" in text or "incrementa" in text:
        mag = _extract_bp(text)
        return "alza", mag
    if "mantien" in text or "sin cambio" in text:
        return "sin cambio", 0
    return "sin cambio", None


def _extract_bp(text: str) -> int | None:
    m = re.search(r"(\d+)\s*puntos?\s*base", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)\s*pb", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def build_decisions(obs: list[dict], events: list[dict] | None = None) -> list[dict]:
    """Genera policy_decisions a partir de observaciones diarias y eventos del calendario."""
    if events is None:
        events = _tasa_events(_load_calendar())
    if not events:
        return []

    by_date = {}
    for o in obs:
        try:
            d = _parse_date(o["period"])
            by_date[d] = o["values"][0]
        except (ValueError, KeyError, IndexError, TypeError):
            continue

    decisions = []
    for e in events:
        pub = e.get("publication_date") or e.get("fecha_iso")
        if not pub:
            continue
        pub_dt = _parse_date(pub)
        if not pub_dt:
            continue

        # Decisión inferida del texto del calendario
        text = e.get("program") or e.get("product") or ""
        text_decision, text_bp = _parse_decision_text(text)

        # Tasa vigente inmediatamente antes del anuncio
        previous_rate = _rate_on_or_before(by_date, pub_dt - timedelta(days=1))

        # Buscar primer cambio de tasa a partir del anuncio
        change = _first_change_after(by_date, pub_dt)

        if text_decision in ("alza", "recorte") and change is not None:
            effective_dt, new_rate, _ = change
        else:
            # Sin cambio: la tasa vigente no se altera
            new_rate = _rate_on_or_before(by_date, pub_dt)
            effective_dt = pub_dt

        if new_rate is None:
            continue

        # Recalcular previous_rate como la tasa del día hábil anterior a la vigencia
        if effective_dt and previous_rate is None:
            previous_rate = _rate_on_or_before(by_date, effective_dt - timedelta(days=1))

        if previous_rate is not None:
            change_bp = round((new_rate - previous_rate) * 100, 2)
        else:
            change_bp = text_bp or 0

        if change_bp > 0:
            decision = "alza"
        elif change_bp < 0:
            decision = "recorte"
        else:
            decision = "sin cambio"

        # URL del comunicado
        url = e.get("url") or ""
        if not url and e.get("deliverables"):
            url = e["deliverables"][0].get("url") or ""

        decisions.append({
            "announcement_date": pub,
            "effective_date": effective_dt.isoformat(),
            "announcement_date_display": e.get("publication_date_display") or "",
            "previous_rate": previous_rate,
            "new_rate": new_rate,
            "decision": decision,
            "change_bp": change_bp,
            "comunicado_url": url,
            "reference_period": e.get("reference_period") or e.get("publication_date_display") or "",
        })

    return decisions


def regimen_from_observations(obs: list[dict]) -> list[dict]:
    """Reduce la serie diaria a fechas de inicio de cada nivel de tasa (regímenes)."""
    if not obs:
        return []
    out = []
    current = None
    for o in sorted(obs, key=lambda x: x.get("period", "")):
        val = o.get("values", [None])[0]
        if val is None:
            continue
        if current is None or abs(val - current) > 1e-6:
            out.append({"period": o["period"], "values": [val]})
            current = val
    return out
