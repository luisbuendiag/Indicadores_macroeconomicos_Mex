"""Mide el conector BIE y las etapas de datos en una corrida aislada de QA."""

import argparse
from collections import Counter
from contextlib import ExitStack
from functools import wraps
import json
from time import perf_counter
from unittest.mock import patch

import build_data


def benchmark_bie():
    connector = build_data.inegi
    config = json.loads(build_data.CONFIG.read_bytes())
    raw_request = connector.http_get_json
    fetch_one = connector._fetch_one
    report, results = {}, {}
    for mode in ("directo", "reutilizado"):
        calls = Counter()

        def request(url, *args, **kwargs):
            calls[url] += 1
            return raw_request(url, *args, **kwargs)

        def without_reuse(spec, token, start_year, **kwargs):
            return fetch_one(spec, token, start_year)

        start = perf_counter()
        with ExitStack() as stack:
            stack.enter_context(patch.object(connector, "http_get_json", request))
            if mode == "directo":
                stack.enter_context(patch.object(connector, "_fetch_one", without_reuse))
            result = connector.fetch(config)
        report[mode] = {
            "segundos": round(perf_counter() - start, 3),
            "solicitudes_logicas": sum(calls.values()),
            "urls_distintas": len(calls),
            "columnas_recibidas": sum(len(group) if isinstance(group, list) else 1
                                     for group in result.data.values()),
        }
        results[mode] = result

    expected = sum(len(connector._specs_for(key, value)) for key, value in config["inegi"].items()
                   if not key.startswith("_"))
    report["paridad_exacta"] = results["directo"].data == results["reutilizado"].data
    report["cobertura_esperada"] = expected
    report["solicitudes_evitadas"] = (
        report["directo"]["solicitudes_logicas"] - report["reutilizado"]["solicitudes_logicas"]
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["paridad_exacta"] and report["solicitudes_evitadas"] > 0 and all(
        report[mode]["columnas_recibidas"] == expected for mode in ("directo", "reutilizado")
    ) else 1


def profile_data():
    phases = Counter()
    detail = Counter()

    def instrument(stack, owner, attr, output, label):
        original = getattr(owner, attr)

        @wraps(original)
        def measure(*args, **kwargs):
            start = perf_counter()
            try:
                return original(*args, **kwargs)
            finally:
                phase = label(*args, **kwargs) if callable(label) else label
                output[phase] += perf_counter() - start

        stack.enter_context(patch.object(owner, attr, measure))

    start = perf_counter()
    with ExitStack() as stack:
        for connector in (
            build_data.banxico_sie, build_data.inegi_bulletin, build_data.imoam,
            build_data.banxico, build_data.inegi, build_data.inegi_inpc,
            build_data.inegi_inpp, build_data.ied, build_data.worldbank,
        ):
            instrument(stack, connector, "fetch", phases, connector.__name__.split(".")[-1])
        for owner, attr, label in (
            (build_data, "apply_freshness_and_meta", "frescura_calendario_metricas"),
            (build_data.lib_notas, "provision_notes", "aprovisionar_notas"),
            (build_data.V, "validate", "validacion"),
            (build_data.L, "backup_current", "respaldo"),
            (build_data.L, "save_data", "escritura_json"),
            (build_data.L, "write_csvs", "escritura_csv"),
            (build_data.L, "write_manifest", "escritura_manifiesto"),
        ):
            instrument(stack, owner, attr, phases, label)
        instrument(stack, build_data.inegi_bulletin, "_fetch_kind", detail,
                   lambda kind, *args, **kwargs: "boletines_" + kind)
        instrument(stack, build_data.inegi_bulletin, "discover_bulletin_url", detail,
                   lambda key, *args, **kwargs: "descubrimiento_" + key)
        instrument(stack, build_data.build_calendar, "build", detail, "calendario")
        result = build_data.run()

    total = perf_counter() - start
    phase_report = {key: round(value, 3) for key, value in phases.most_common()}
    print(json.dumps({
        "segundos_totales": round(total, 3),
        "resultado_pipeline": result,
        "etapas_segundos": phase_report,
        "detalle_incluido_en_las_etapas": {key: round(value, 3) for key, value in detail.most_common()},
        "segundos_sin_desglosar": round(total - sum(phases.values()), 3),
    }, indent=2, ensure_ascii=False))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("bie", "pipeline"))
    args = parser.parse_args()
    raise SystemExit(benchmark_bie() if args.mode == "bie" else profile_data())
