"""Validaciones de calidad de datos para data/indicadores.json.

Distingue validaciones CRÍTICAS (bloquean la publicación / reemplazo de datos)
de ADVERTENCIAS (se registran pero no bloquean). Diseñado para el modo de
respaldo: si una validación crítica falla, el pipeline conserva la última
versión válida.

Uso:
    python scripts/validate.py [--data data/indicadores.json] [--strict]
Devuelve código de salida 0 si no hay errores críticos, 1 en caso contrario.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "data" / "indicadores.json"

PERIOD_RE = re.compile(r"^([1-4]T-\d{2}|[A-Za-zÁÉÍÓÚáéíóú]{3}\s*\d{2})")

# Rangos plausibles por indicador (columna 0 de la serie primaria).
RANGES = {
    "PIB": (15_000_000, 35_000_000),
    "PIBSEC": (15_000_000, 35_000_000),
    "IGAE": (70, 130),
    "IMAI": (70, 130),
    "CONSUMO": (70, 140),
    "IED": (-5_000, 60_000),
    "DESOCUP": (0.0, 0.20),   # fracción (0-20%)
    "INPC": (-2, 15),         # porcentaje anual
    "BALANZA": (-30_000, 30_000),
}


def primary_series(ind):
    key = ind["key"]
    obs = ind["observations"]
    if key == "PIBSEC":
        return [None if all(v is None for v in o["values"][:3]) else sum(x or 0 for x in o["values"][:3]) for o in obs]
    if key == "BALANZA":
        return [(o["values"][0] - o["values"][1]) if (o["values"][0] is not None and o["values"][1] is not None) else None for o in obs]
    return [o["values"][0] if o["values"] else None for o in obs]


def validate(payload: dict):
    errors, warnings = [], []
    inds = payload["indicators"]

    # 1) Estructura y fechas
    for key, ind in inds.items():
        if not ind.get("observations"):
            errors.append(f"[{key}] sin observaciones.")
            continue
        for o in ind["observations"]:
            if not PERIOD_RE.match(o["period"] or ""):
                warnings.append(f"[{key}] periodo con formato inesperado: '{o['period']}'.")
            ncols = len(ind["columns"])
            if len(o["values"]) != ncols:
                warnings.append(f"[{key}] fila {o['period']} tiene {len(o['values'])} valores; se esperaban {ncols}.")

    # 2) Columnas obligatorias
    for key, ind in inds.items():
        if not ind.get("columns"):
            errors.append(f"[{key}] sin definición de columnas.")

    # 3) Duplicados exactos entre series NO relacionadas (regla del usuario)
    #    Recolecta (indicador, periodo, valor) de las series primarias y detecta
    #    valores idénticos con muchos decimales compartidos entre indicadores.
    value_index = defaultdict(list)
    for key, ind in inds.items():
        for o in ind["observations"]:
            for col, v in enumerate(o["values"]):
                if isinstance(v, (int, float)) and abs(v) > 5 and (abs(v - round(v)) > 1e-6):
                    # sólo valores "de alta precisión" (con decimales significativos)
                    value_index[round(v, 6)].append((key, o["period"], col))
    for v, hits in value_index.items():
        distinct_inds = {h[0] for h in hits}
        if len(distinct_inds) > 1:
            desc = "; ".join(f"{k} {p} (col {c})" for k, p, c in hits)
            errors.append(f"Valor idéntico sospechoso {v} compartido entre series no relacionadas: {desc}.")

    # 4) Nulos inesperados en el último dato de la serie primaria
    for key, ind in inds.items():
        ser = primary_series(ind)
        if ser and ser[-1] is None:
            warnings.append(f"[{key}] el último dato de la serie primaria es nulo.")

    # 5) Rango/unidades plausibles
    for key, ind in inds.items():
        rng = RANGES.get(key)
        if not rng:
            continue
        for v, o in zip(primary_series(ind), ind["observations"]):
            if v is None:
                continue
            if not (rng[0] <= v <= rng[1]):
                warnings.append(f"[{key}] valor fuera de rango plausible en {o['period']}: {v} (esperado {rng}).")

    return errors, warnings


def compare_revisions(new: dict, old: dict):
    """Detecta revisiones históricas: valores que cambiaron respecto a la
    versión previa para periodos ya publicados. Sólo informativo."""
    notes = []
    if not old:
        return notes
    for key, ind in new["indicators"].items():
        old_ind = old.get("indicators", {}).get(key)
        if not old_ind:
            continue
        old_map = {o["period"]: o["values"] for o in old_ind["observations"]}
        for o in ind["observations"]:
            prev = old_map.get(o["period"])
            if prev and prev != o["values"]:
                notes.append(f"[{key}] revisión en {o['period']}: {prev} -> {o['values']}.")
    return notes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(DEFAULT_DATA))
    ap.add_argument("--previous", default=None, help="JSON previo para detectar revisiones.")
    ap.add_argument("--strict", action="store_true", help="Trata advertencias como errores.")
    args = ap.parse_args()

    payload = json.loads(Path(args.data).read_text(encoding="utf-8"))
    errors, warnings = validate(payload)
    if args.previous and Path(args.previous).exists():
        old = json.loads(Path(args.previous).read_text(encoding="utf-8"))
        for n in compare_revisions(payload, old):
            warnings.append("Revisión histórica: " + n)

    for w in warnings:
        print(f"ADVERTENCIA: {w}")
    for e in errors:
        print(f"ERROR CRÍTICO: {e}")
    print(f"\nResumen: {len(errors)} errores críticos, {len(warnings)} advertencias.")

    fail = bool(errors) or (args.strict and bool(warnings))
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
