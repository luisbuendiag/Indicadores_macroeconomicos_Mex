#!/usr/bin/env python3
"""Construye data/calendario_publicaciones.json a partir de las fuentes
oficiales por año en data/calendar_sources/*.json.

Arquitectura preparada para 2027 y posteriores: basta con añadir un nuevo
archivo data/calendar_sources/<año>.json con el mismo esquema; este script
los fusiona, ordena, calcula fechas ISO y asigna el estatus
(publicado / próximo) respecto a una fecha de referencia.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path


def _under_pytest() -> bool:
    return "pytest" in sys.modules

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
SRC_DIR = DATA_DIR / "calendar_sources"
OUT_FILE = DATA_DIR / "calendario_publicaciones.json"

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}


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


def build(as_of: date) -> dict:
    sources = sorted(SRC_DIR.glob("*.json"))
    if not sources:
        raise SystemExit(f"No hay fuentes de calendario en {SRC_DIR}")

    items: list[dict] = []
    years: list[int] = []
    fuentes: list[str] = []
    actualizado = None
    for sf in sources:
        src = json.loads(sf.read_text("utf-8"))
        years.append(src.get("year"))
        if src.get("fuente"):
            fuentes.append(src["fuente"])
        if src.get("actualizado"):
            actualizado = max(actualizado, src["actualizado"]) if actualizado else src["actualizado"]
        for e in src.get("entries", []):
            for pub in e.get("publicaciones", []):
                d = parse_fecha(pub["fecha"])
                items.append({
                    "clave": e["clave"],
                    "indicador": e["indicador"],
                    "producto": e["producto"],
                    "institucion": e["institucion"],
                    "frecuencia": e["frecuencia"],
                    "fecha_publicacion": pub["fecha"],
                    "fecha_iso": d.isoformat(),
                    "anio": d.year,
                    "mes": d.month,
                    "periodo_referencia": pub["periodo"],
                    "estatus": "publicado" if d <= as_of else "próximo",
                })

    items.sort(key=lambda x: (x["fecha_iso"], x["indicador"]))

    return {
        "_comment": "Generado por scripts/build_calendar.py a partir de data/calendar_sources/. No editar a mano.",
        "fuente": " | ".join(sorted(set(fuentes))) or "Calendario oficial de difusión (INEGI)",
        "actualizado": actualizado or as_of.isoformat(),
        "as_of": as_of.isoformat(),
        "anios": sorted({y for y in years if y}),
        "items": items,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", help="Fecha de referencia YYYY-MM-DD (default: última actualización de datos)")
    args = ap.parse_args(argv if argv is not None else [] if _under_pytest() else None)
    as_of = date.fromisoformat(args.as_of) if args.as_of else data_as_of()
    cal = build(as_of)
    OUT_FILE.write_text(json.dumps(cal, ensure_ascii=False, indent=2) + "\n", "utf-8")
    pub = sum(1 for i in cal["items"] if i["estatus"] == "publicado")
    prox = len(cal["items"]) - pub
    print(f"OK: {OUT_FILE.relative_to(ROOT)} — {len(cal['items'])} publicaciones "
          f"({pub} publicadas, {prox} próximas) · as_of={as_of.isoformat()} · años={cal['anios']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
