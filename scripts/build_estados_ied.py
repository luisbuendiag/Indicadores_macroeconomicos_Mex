"""Build the Panorama Estatal IED payload from a validated SE snapshot."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERIES = {
    "original": ("ied_estatal.json", "IED acumulada, originalmente publicada"),
    "actualizada": ("ied_estatal_actualizada.json", "IED acumulada, cifras actualizadas"),
}
ACCUMULATED_LABELS = {1: "1T-{}", 2: "1S-{}", 3: "9M-{}", 4: "{}"}


def build_ied(catalog, source, variant):
    entities = sorted(catalog["entidades"], key=lambda item: item["clave"])
    if [entity["clave"] for entity in entities] != [f"{code:02d}" for code in range(1, 33)]:
        raise ValueError("El catálogo debe contener las 32 claves estatales")
    periods = sorted(source["periods"], key=lambda row: (row["year"], row["quarter"]))
    history = {entity["clave"]: [] for entity in entities}
    totals = []
    seen = set()
    for row in periods:
        period = ACCUMULATED_LABELS[row["quarter"]].format(row["year"])
        if period in seen:
            raise ValueError(f"Periodo duplicado: {period}")
        seen.add(period)
        values = row["values"]
        names = [next((name for name in (e["nombre_oficial"], e["nombre"]) if name in values), None)
                 for e in entities]
        if len(set(names)) != 32 or set(names) != values.keys():
            raise ValueError(f"Cobertura estatal inválida: {period}")
        total = row["total"]
        if not all(math.isfinite(v) for v in [total, *values.values()]):
            raise ValueError(f"Cifra no finita: {period}")
        if not math.isclose(math.fsum(values.values()), total, rel_tol=0, abs_tol=0.001):
            raise ValueError(f"Las entidades no cuadran con el total: {period}")
        totals.append([period, total])
        for entity, name in zip(entities, names):
            history[entity["clave"]].append([period, values[name]])

    if not totals:
        raise ValueError("La fuente no contiene periodos")
    period, total = totals[-1]
    latest = periods[-1]
    previous_period = ACCUMULATED_LABELS[latest["quarter"]].format(latest["year"] - 1)

    def comparison(series):
        previous = dict(series).get(previous_period)
        value = series[-1][1]
        return {
            "var": 100 * (value / previous - 1) if previous and previous > 0 and value >= 0 else None,
            "comparable": previous,
            "periodo_comparable": previous_period if previous is not None else None,
            "cambio": value - previous if previous is not None else None,
        }

    ranked = sorted((rows[-1][1] for rows in history.values()), reverse=True)
    output = []
    for entity in entities:
        series = history[entity["clave"]]
        value = series[-1][1]
        output.append({**entity, "ind": {"IED": {
            "valor": value, **comparison(series),
            "part": value / total * 100 if total else None,
            "lugar": ranked.index(value) + 1, "serie": series,
        }}})
    return {
        "version": 1,
        "estado": "oficial",
        "actualizado": source.get("validated_at") or source.get("last_checked"),
        "indicadores": [{
            "clave": "IED", "nombre": "Inversión extranjera directa", "sigla": "IED",
            "fuente": "Secretaría de Economía", "url_fuente": source["source_url"],
            "medida": f"Millones de dólares corrientes. {SERIES[variant][1]}",
            "periodo": period, "formato": "mdd", "escala": "secuencial",
            "lugar_por": "monto", "estatus": "oficial", "serie_origen": variant,
        }],
        "nacional": {"IED": {"valor": total, **comparison(totals), "serie": totals}},
        "entidades": output,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--serie", choices=SERIES, default="original")
    args = parser.parse_args()
    root = args.root
    catalogue = json.loads((root / "config/estados.json").read_text(encoding="utf-8"))
    source = json.loads((root / "data" / SERIES[args.serie][0]).read_text(encoding="utf-8"))
    print(json.dumps(build_ied(catalogue, source, args.serie), ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
