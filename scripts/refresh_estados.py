"""Refresh the official state snapshot in a prepared release directory."""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from build_estados import assemble_estados, load_json
from build_estados_remesas import build_remesas, export_url, http_get_bytes


def save_snapshot(path, payload):
    output = json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
    if path.exists():
        previous = load_json(path)
        # A newer consultation timestamp does not change the published figures.
        if {**previous, "actualizado": payload["actualizado"]} == json.loads(output):
            return False

    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as tmp:
        temporary_path = Path(tmp.name)
        try:
            tmp.write(output)
            tmp.close()
            os.replace(temporary_path, path)
        finally:
            temporary_path.unlink(missing_ok=True)
    return True


def previous_edition(snapshot_path, key):
    """La edición oficial ya publicada de un indicador, para no perderlo si su fuente falla hoy."""
    if not snapshot_path.exists():
        return None
    try:
        snapshot = load_json(snapshot_path)
        indicator = next(i for i in snapshot.get("indicadores", []) if i.get("clave") == key)
        if snapshot.get("estado") != "oficial" or key not in snapshot.get("nacional", {}):
            return None
        return {
            "version": 1, "estado": "oficial", "actualizado": snapshot["actualizado"],
            "indicadores": [indicator], "nacional": {key: snapshot["nacional"][key]},
            "entidades": [{**{k: v for k, v in e.items() if k != "ind"}, "ind": {key: e["ind"][key]}}
                          for e in snapshot["entidades"]],
        }
    except (StopIteration, KeyError, TypeError, ValueError):
        return None


def optional_edition(key, build, data):
    """Fuente estatal opcional: si falla, se conserva la edición publicada o se omite."""
    try:
        return build()
    except Exception as error:  # noqa: BLE001 - una fuente estatal no detiene la ficha
        print(f"AVISO {key} estatal: {type(error).__name__}: {error}")
        previous = previous_edition(data / "estados.json", key)
        if previous:
            print(f"AVISO {key} estatal: se conserva la edición publicada")
        return previous


def itaee_edition(args, catalog, data, now):
    """ITAEE estatal (INEGI, boletín trimestral)."""
    from build_estados_itaee import build_itaee, ultimo_boletin

    def build():
        if args.itaee:
            url, pdf = "archivo local", args.itaee.read_bytes()
        else:
            url, pdf = ultimo_boletin(now.date(), lambda u: http_get_bytes(u, timeout=30))
        return build_itaee(catalog, pdf, url, now, load_json(data / "indicadores.json"))
    return optional_edition("ITAEE", build, data)


def pibe_edition(args, catalog, data, now):
    """PIB por entidad federativa (INEGI, comunicado anual)."""
    from build_estados_pibe import build_pibe, ultimo_comunicado

    def build():
        if getattr(args, "pibe", None):
            url, pdf = "archivo local", args.pibe.read_bytes()
        else:
            url, pdf = ultimo_comunicado(now.date(), lambda u: http_get_bytes(u, timeout=30))
        return build_pibe(catalog, pdf, url, now)
    return optional_edition("PIB", build, data)


def main():
    from build_estados_ied import SERIES, build_ied
    from build_estados_coyuntura import build_edition

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help="Directorio de la edición preparada")
    parser.add_argument("--ce100", type=Path, help="Archivo CE100 de Banxico para ejecución local")
    parser.add_argument("--itaee", type=Path, help="Boletín ITAEE del INEGI para ejecución local")
    parser.add_argument("--pibe", type=Path, help="Comunicado PIBE del INEGI para ejecución local")
    args = parser.parse_args()
    catalog = load_json(args.root / "config" / "estados.json")
    data = args.root / "data"
    now = datetime.now(timezone.utc)
    itaee = itaee_edition(args, catalog, data, now)
    pibe = pibe_edition(args, catalog, data, now)
    ied = build_ied(catalog, load_json(data / SERIES["original"][0]), "original")
    workbook = args.ce100.read_bytes() if args.ce100 else http_get_bytes(export_url(now), timeout=30)
    remittances = build_remesas(catalog, workbook, now)
    # ITAEE primero: es el indicador con el que abre el mapa. El PIB alimenta el encabezado de la ficha.
    outlook = [optional_edition(key, lambda: build_edition(
        key, catalog, now, previous_edition(data / "estados.json", key)), data)
        for key in ("ETEF", "IMSS", "ENOE")]
    editions = [edition for edition in (itaee, pibe, outlook[0], ied, *outlook[1:], remittances)
                if edition]
    snapshot_path = data / "estados.json"
    snapshot = assemble_estados(catalog, editions)
    changed = save_snapshot(snapshot_path, snapshot)
    print("Ficha estatal actualizada" if changed else "Ficha estatal sin cambios")


if __name__ == "__main__":
    main()
