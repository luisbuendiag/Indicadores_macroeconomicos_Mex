"""Ejecuta una corrida completa de datos en un checkout de QA."""

import argparse
import hashlib
import json
from pathlib import Path
from time import perf_counter
from unittest.mock import patch

import build_data
import shared_pibt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("directo", "compartido", "atrasado"))
    args = parser.parse_args()
    loader = shared_pibt.load_release

    def late_release():
        data, receipt = loader()
        indicator = data["indicators"]["PIBSEC"]
        indicator["observations"].pop()
        indicator["last_observation"] = indicator["observations"][-1]["period"]
        return data, receipt

    start = perf_counter()
    with patch.object(shared_pibt, "load_release", late_release if args.mode == "atrasado" else loader):
        result = build_data.run(reuse_pibt=args.mode != "directo")
    elapsed = round(perf_counter() - start, 3)
    if result:
        raise SystemExit(result)

    log = json.loads(build_data.LOG_FILE.read_bytes())
    data = json.loads((build_data.L.DATA_DIR / "indicadores.json").read_bytes())["indicators"]
    consulted = [row for row in log["consultas"]
                 if row.get("indicador") == "PIBSEC" and row.get("fuente") == "inegi"]
    report = {
        "modo": args.mode,
        "segundos": elapsed,
        "compartido": log.get("shared_pibt", {}).get("used", False),
        "consultas_PIBT_registradas": len(consulted),
        "corte": data["PIBSEC"]["last_observation"],
        "historico_sha256": hashlib.sha256(json.dumps(
            data["PIBSEC"]["observations"], sort_keys=True, separators=(",", ":"),
        ).encode()).hexdigest(),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    Path("qa-pibt.json").write_text(json.dumps(report) + "\n", encoding="utf-8")
    if args.mode == "compartido":
        if not report["compartido"] or consulted:
            raise SystemExit("Esta edición no acredita que el pipeline haya evitado INEGI para PIBT")
    elif report["compartido"] or not consulted:
        raise SystemExit("La ruta de consulta directa de PIBT no quedó acreditada")


if __name__ == "__main__":
    main()
