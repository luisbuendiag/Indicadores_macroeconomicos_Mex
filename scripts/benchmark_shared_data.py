"""Compara dos corridas aisladas del pipeline institucional para FIX y remesas."""

import argparse
from collections import Counter
import json
from pathlib import Path
from time import perf_counter
from unittest.mock import patch
from urllib.parse import urlsplit
from urllib import request

import build_data
import pilot_shared_data
from pilot_shared_data import DATA, HEALTH, SERIES_FIELDS, load_release, simulate
from sources.base import SourceResult

KEYS = ("TIPOCAMBIO", "REMESAS")
LOG = Path("data/update_log.json")


def measure(mode, *, retrasar_fix=False):
    initial = json.loads(Path(DATA).read_bytes())
    report = {"modo": mode}
    counts = Counter()
    open_url = request.urlopen
    fetch_banxico = build_data.banxico.fetch

    def track_url(resource, *args, **kwargs):
        url = resource if isinstance(resource, str) else resource.full_url
        host = urlsplit(url).hostname
        if host in ("www.banxico.org.mx", "macromexico.com"):
            counts[host] += 1
        return open_url(resource, *args, **kwargs)

    def source(config, *args, **kwargs):
        start = perf_counter()
        if mode == "directo":
            response = fetch_banxico(config, *args, **kwargs)
            if not response.ok or not set(KEYS) <= response.data.keys():
                raise ValueError("La consulta directa no devolvió FIX y remesas")
        else:
            commercial, receipt = load_release()
            if retrasar_fix:
                fix = commercial["indicators"]["TIPOCAMBIO"]
                local_cut = initial["indicators"]["TIPOCAMBIO"]["last_observation"]
                fix["observations"] = [row for row in fix["observations"] if row["period"] < local_cut]
                fix["last_observation"] = fix["observations"][-1]["period"]
                report["atraso_simulado"] = "TIPOCAMBIO"
            health = json.loads(Path(HEALTH).read_bytes())
            if health.get("data_error") is not False:
                raise ValueError("El comprobante institucional no acredita una consulta válida")
            decisions = simulate(initial, commercial, health["data_checked_at"], receipt["data_checked_at"])
            report.update(release_id=receipt["release_id"], decisiones=decisions)
            fallback = set(KEYS) - {key for key, decision in decisions.items()
                                    if decision["decision"] in ("equivalente", "adoptar")}
            result = {}
            if fallback:
                config = {**config, "banxico": {key: config["banxico"][key] for key in sorted(fallback)}}
                direct = fetch_banxico(config, *args, **kwargs)
                if not direct.ok or not fallback <= direct.data.keys():
                    raise ValueError("El respaldo directo no devolvió todos los indicadores")
                result.update(direct.data)
            for key in set(KEYS) - fallback:
                indicator = commercial["indicators"][key]
                last = indicator["last_observation"]
                result[key] = {
                    **{field: indicator[field] for field in SERIES_FIELDS[key]},
                    "last_observation": last,
                    "fecha_ultima_observacion": last,
                }
            response = SourceResult(True, result)
        report["segundos_fuente"] = round(perf_counter() - start, 3)
        return response

    start = perf_counter()
    with (
        patch.object(request, "urlopen", track_url),
        patch.object(pilot_shared_data, "urlopen", track_url),
        patch.object(build_data.banxico, "fetch", source),
    ):
        status = build_data.run(defer_product_validation=True, pilot_keys=KEYS)
    report.update(segundos_corrida=round(perf_counter() - start, 3), solicitudes=dict(counts))
    if status or "segundos_fuente" not in report:
        raise SystemExit(f"Corrida inválida: {mode}")
    log = json.loads(LOG.read_bytes())
    if log.get("rejected_indicators"):
        raise SystemExit(f"La validación rechazó indicadores en la corrida {mode}")
    final = json.loads(Path(DATA).read_bytes())["indicators"]
    report["cortes"] = {key: final[key]["last_observation"] for key in KEYS}
    return report


def compare(args):
    direct, shared = [json.loads(p.read_bytes()) for p in (args.direct, args.shared)]
    left, right = [json.loads(p.read_bytes())["indicators"] for p in (args.data_direct, args.data_shared)]
    parity = {key: all(left[key][field] == right[key][field] for field in SERIES_FIELDS[key]) for key in KEYS}
    host = "www.banxico.org.mx"
    report = {
        "directo": direct, "compartido": shared, "paridad_historial": parity,
        "solicitudes_banxico_evitadas": direct["solicitudes"].get(host, 0) - shared["solicitudes"].get(host, 0),
        "minutos_de_fuente_ahorrados": round((direct["segundos_fuente"] - shared["segundos_fuente"]) / 60, 4),
        "minutos_de_corrida_ahorrados": round((direct["segundos_corrida"] - shared["segundos_corrida"]) / 60, 4),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if all(parity.values()) else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for cmd in ("directo", "compartido"):
        cmd_parser = sub.add_parser(cmd)
        cmd_parser.add_argument("--report", type=Path, required=True)
        if cmd == "compartido":
            cmd_parser.add_argument("--simular-atraso-fix", action="store_true")
    diff = sub.add_parser("comparar")
    for field in ("direct", "shared", "data-direct", "data-shared"):
        diff.add_argument(f"--{field}", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "comparar":
        return compare(args)
    report = measure(args.command, retrasar_fix=getattr(args, "simular_atraso_fix", False))
    if report.get("atraso_simulado"):
        decisions = report["decisiones"]
        if (
            decisions["TIPOCAMBIO"]["decision"] != "conservar"
            or "atrasado" not in decisions["TIPOCAMBIO"]["motivo"]
            or decisions["REMESAS"]["decision"] not in ("equivalente", "adoptar")
            or report["solicitudes"].get("www.banxico.org.mx") != 1
        ):
            raise SystemExit("El respaldo no aisló correctamente el atraso del FIX")
    args.report.write_text(json.dumps(report, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
