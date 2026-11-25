"""Assemble official state indicator payloads into the Panorama Estatal contract."""
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def assemble_estados(catalog, editions):
    entities = {entity["clave"]: {**entity, "ind": {}} for entity in catalog["entidades"]}
    if len(catalog["entidades"]) != 32 or set(entities) != {f"{code:02d}" for code in range(1, 33)}:
        raise ValueError("El catálogo debe contener las 32 entidades una sola vez")

    indicators = {}
    national = {}
    checked = []
    for edition in editions:
        if edition.get("version") != 1 or edition.get("estado") != "oficial":
            raise ValueError("La ficha estatal solo admite indicadores oficiales con contrato v1")
        updated_at = datetime.fromisoformat(edition["actualizado"])
        if updated_at.utcoffset() is None:
            raise ValueError("La fecha de actualización debe incluir zona horaria")
        checked.append(updated_at)

        keys = [indicator["clave"] for indicator in edition["indicadores"]]
        if not keys or len(keys) != len(set(keys)) or indicators.keys() & set(keys):
            raise ValueError("Cada indicador debe aparecer una sola vez en la ficha")
        for indicator in edition["indicadores"]:
            if indicator["estatus"] != "oficial" or not indicator.get("periodo"):
                raise ValueError(f"Indicador sin período oficial: {indicator['clave']}")
            indicators[indicator["clave"]] = indicator

        entries = {entry["clave"]: entry["ind"] for entry in edition["entidades"]}
        if len(edition["entidades"]) != 32 or entries.keys() != entities.keys():
            raise ValueError(f"Cobertura estatal inválida: {', '.join(keys)}")
        for observations in [edition["nacional"], *entries.values()]:
            if set(observations) != set(keys) or any(
                type(observation.get("valor")) not in (int, float) or not math.isfinite(observation["valor"])
                for observation in observations.values()
            ):
                raise ValueError(f"Cobertura o valor inválido: {', '.join(keys)}")
        national.update(edition["nacional"])
        for code, observations in entries.items():
            entities[code]["ind"].update(observations)

    if not indicators:
        raise ValueError("La ficha estatal requiere al menos un indicador oficial")
    return {
        "version": 1,
        "estado": "oficial",
        "actualizado": max(checked).astimezone(timezone.utc).isoformat(timespec="seconds"),
        "indicadores": list(indicators.values()),
        "nacional": national,
        "entidades": [entities[code] for code in sorted(entities)],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archivos", nargs="+", type=Path, help="Salidas JSON de los conectores estatales")
    parser.add_argument("--catalogo", type=Path, default=ROOT / "config" / "estados.json")
    args = parser.parse_args()
    try:
        payload = assemble_estados(load_json(args.catalogo), map(load_json, args.archivos))
        output = json.dumps(payload, ensure_ascii=False, allow_nan=False)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"{error}\n")
    print(output)


if __name__ == "__main__":
    main()
