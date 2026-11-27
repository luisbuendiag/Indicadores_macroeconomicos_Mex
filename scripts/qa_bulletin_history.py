"""Mide lecturas institucionales con un archivo de boletines entre procesos."""

import argparse
import hashlib
import json
from pathlib import Path
from time import perf_counter
from unittest.mock import patch

from sources import inegi_bulletin as source


def summary(payload):
    return hashlib.sha256(json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()


def measure(kind, root=None):
    wall = perf_counter()
    if kind == "pipeline":
        import build_data

        fetch = source.fetch

        def with_archive(*args, **kwargs):
            start = perf_counter()
            result = fetch(*args, archive_dir=root, **kwargs)
            print(f"Boletines INEGI: {perf_counter() - start:.3f} s")
            return result

        with patch.object(source, "fetch", with_archive):
            if build_data.run():
                raise SystemExit("Falló la validación del flujo institucional de datos")
        indicators = json.loads((build_data.L.DATA_DIR / "indicadores.json").read_bytes())["indicators"]
        payload = {key: indicators[key]["observations"] for key in ("IOAE", "PIB")}
    else:
        archive = source.open_archive(root, kind)
        pending = len(archive.records())
        payload = source._fetch_kind(kind, start_year=2021, archive=archive)
        print(f"Boletines históricos disponibles al iniciar: {pending}")
    if not payload:
        raise SystemExit("La consulta no produjo datos")
    report = {"modo": kind, "segundos": round(perf_counter() - wall, 3), "sha256": summary(payload)}
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("kind", choices=(*source.ARCHIVED_KINDS, "pipeline"))
    cli.add_argument("--archivo", type=Path)
    cli.add_argument("--informe", type=Path, required=True)
    args = cli.parse_args()
    if args.kind != "pipeline" and args.archivo is None:
        cli.error("La medición por indicador requiere --archivo")
    args.informe.write_text(json.dumps(measure(args.kind, args.archivo)) + "\n", encoding="utf-8")
