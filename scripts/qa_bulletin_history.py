"""Mide en QA la reutilización de boletines históricos de IOAE y PIB Oportuno."""

import argparse
from collections import Counter
from copy import deepcopy
from datetime import date, timedelta
import hashlib
import json
from time import perf_counter
from unittest.mock import patch

from sources import inegi_bulletin as source

PARSERS = {"IOAE": "_parse_ioae", "EOPIBT": "_parse_eopibt"}
HISTORICAL_AGE = timedelta(days=180)


def measure(kind):
    archive = {}
    parser = getattr(source, PARSERS[kind])
    fetch_pdf = source._req
    probe_pdf = source._head_ok
    read_page = source._pdf_text_first_page
    cutoff = date.today() - HISTORICAL_AGE

    def run(reuse):
        requests = Counter()
        pending = {}
        cached = {}

        def probe(url, *args, **kwargs):
            if reuse and url in archive:
                return True
            requests["comprobaciones_red"] += 1
            return probe_pdf(url, *args, **kwargs)

        def download(url, *args, **kwargs):
            if reuse and url in archive:
                pdf, page, published, parsed = archive[url]
                cached[hashlib.sha256(pdf).digest()] = (page, published, parsed)
                requests["boletines_reutilizados"] += 1
                return pdf
            requests["descargas_red"] += 1
            pdf = fetch_pdf(url, *args, **kwargs)
            pending[hashlib.sha256(pdf).digest()] = (url, None)
            return pdf

        def extract(pdf):
            digest = hashlib.sha256(pdf).digest()
            if digest in cached:
                return cached[digest][0]
            page = read_page(pdf)
            if digest in pending:
                pending[digest] = (pending[digest][0], page)
            return page

        def parse(pdf, published):
            digest = hashlib.sha256(pdf).digest()
            if digest in cached and cached[digest][1] == published:
                return deepcopy(cached[digest][2])
            result = parser(pdf, published)
            if result and date(*published) <= cutoff and digest in pending:
                url, page = pending[digest]
                if page is not None:
                    archive[url] = (pdf, page, published, deepcopy(result))
            return result

        start = perf_counter()
        with (
            patch.object(source, "_head_ok", probe),
            patch.object(source, "_req", download),
            patch.object(source, "_pdf_text_first_page", extract),
            patch.object(source, PARSERS[kind], parse),
        ):
            items = source._fetch_kind(kind, start_year=2021)
        return items, {
            "segundos": round(perf_counter() - start, 3),
            "columnas": len(items),
            "observaciones": sum(len(item["api_total"]) for item in items),
            "ultimo_ym": max((row["ym"] for item in items for row in item["api_total"]), default=None),
            **dict(requests),
        }

    cold, first = run(False)
    warm, second = run(True)
    report = {
        "indicador": kind,
        "corte_historico": cutoff.isoformat(),
        "sin_reuso": first,
        "con_reuso": second,
        "paridad_exacta": cold == warm,
        "segundos_ahorrados": round(first["segundos"] - second["segundos"], 3),
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if cold and cold == warm and second.get("boletines_reutilizados") else 1


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("kind", choices=PARSERS)
    raise SystemExit(measure(cli.parse_args().kind))
