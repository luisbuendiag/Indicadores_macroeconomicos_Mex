"""Contrasta la ingesta del PIBT desde INEGI y desde la edición pública."""

from collections import Counter
import json
from pathlib import Path
from time import perf_counter
from unittest.mock import patch
from urllib import request
from urllib.parse import urlsplit

import build_data as pipeline
import pilot_shared_data as shared

KEY = "PIBSEC"


def run():
    initial = json.loads(Path(shared.DATA).read_bytes())
    health = json.loads(Path(shared.HEALTH).read_bytes())
    config = json.loads(pipeline.CONFIG.read_bytes())
    specs = {key: config["inegi"][key] for key in ("PIB", KEY)}
    initial_pibt = initial["indicators"][KEY]
    counts = Counter()
    open_url = request.urlopen

    def count(resource, *args, **kwargs):
        url = resource if isinstance(resource, str) else resource.full_url
        host = urlsplit(url).hostname
        if host == "macromexico.com" or (host and host.endswith(".inegi.org.mx")):
            method = resource.get_method() if isinstance(resource, request.Request) else "GET"
            counts[(host, method)] += 1
        return open_url(resource, *args, **kwargs)

    with patch.object(request, "urlopen", count), patch.object(shared, "urlopen", count):
        started = perf_counter()
        commercial, receipt = shared.load_release()
        decision = shared.simulate(initial, commercial, health["data_checked_at"], receipt["data_checked_at"])[KEY]
        shared_seconds = perf_counter() - started
        shared_requests = sum(counts.values())
        counts.clear()

        started = perf_counter()
        response = pipeline.inegi.fetch({"inegi": specs})
        totals = response.data.get("PIB")
        sectors = response.data.get(KEY)
        if not isinstance(sectors, list) or len(sectors) != len(specs[KEY]) or not totals:
            raise SystemExit("BIE no entregó todos los insumos de la prueba de PIBT")
        api_seconds = perf_counter() - started
        api_requests = sum(counts.values())
        started = perf_counter()
        bulletins = pipeline.inegi_bulletin._fetch_kind("PIBT", start_year=2021, max_bulletins=30)
        if not bulletins:
            raise SystemExit("No se obtuvo ningún boletín de PIBT")
        bulletin_seconds = perf_counter() - started

    started = perf_counter()
    pipeline.prepare_pibsec_for_separated_rates(initial)
    pipeline.apply_pibt_source(initial, "PIB", totals, initial["indicators"]["PIB"]["last_observation"])
    for series in sectors:
        pipeline.apply_inegi_total(initial, KEY, series, initial_pibt["last_observation"])
    pipeline.sync_pibsec_pibt(initial)
    if not pipeline.apply_latest_pibsec_bulletin(initial, bulletins, initial_pibt["last_observation"]):
        raise SystemExit("El boletín no confirmó el último trimestre que devolvió el BIE")
    pipeline.compute_pibsec_variations(initial)
    if pipeline.validate_pibsec_adjusted_history(initial_pibt):
        raise SystemExit("El histórico directo del PIBT no quedó validado")
    local_seconds = perf_counter() - started
    direct_rows = initial_pibt["observations"]
    commercial_pibt = commercial["indicators"][KEY]
    ref_rows = commercial_pibt["observations"]
    differs = sum(a != b for a, b in zip(direct_rows, ref_rows)) + abs(len(direct_rows) - len(ref_rows))
    print(json.dumps({
        "PIBT": {
            "directo": {
                "corte": initial_pibt["last_observation"],
                "consultas_BIE": api_requests,
                "solicitudes_boletines": sum(counts.values()) - api_requests,
                "solicitudes_por_metodo": {m: sum(n for (_, verb), n in counts.items() if verb == m)
                                           for m in ("HEAD", "GET")},
                "segundos_BIE": round(api_seconds, 3),
                "segundos_boletines": round(bulletin_seconds, 3),
                "segundos_ensamble": round(local_seconds, 3),
            },
            "compartido": {
                "corte": commercial_pibt["last_observation"],
                "release_id": receipt["release_id"],
                "solicitudes": shared_requests,
                "segundos": round(shared_seconds, 3),
                "decision": decision,
            },
            "filas_con_diferencias": differs,
            "paridad_historial": differs == 0,
        },
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    run()
