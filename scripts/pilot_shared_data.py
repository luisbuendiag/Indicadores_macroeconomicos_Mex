"""Prepara una edición institucional de prueba desde la edición pública de MacroMéxico."""

import argparse
from copy import deepcopy
from datetime import datetime
import hashlib
import json
from math import isfinite
from pathlib import Path
from urllib.request import Request, urlopen

from lib_format import period_to_date

ORIGIN = "https://macromexico.com"
RECEIPT = "data/release_receipt.json"
DATA = "data/indicadores.json"
HEALTH = "data/update_health.json"
TIMEOUT = 30
MAX_BYTES = 24 * 1024 * 1024
SERIES_FIELDS = {
    "PIBSEC": ("observations",),
    "TIPOCAMBIO": ("observations", "observations_mensual"),
    "REMESAS": ("observations",),
}
SCHEMA_FIELDS = ("key", "columns", "unidad", "frecuencia", "ajuste_estacional", "fuente")


def sha256(content):
    return hashlib.sha256(content).hexdigest()


def download(path, release_id=None):
    suffix = f"?edition={release_id}" if release_id else ""
    url = f"{ORIGIN}/{path}{suffix}"
    request = Request(url, headers={"Cache-Control": "no-cache", "Accept-Encoding": "identity"})
    with urlopen(request, timeout=TIMEOUT) as response:
        if response.geturl() != url:
            raise ValueError(f"URL inesperada al descargar {path}")
        content = response.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise ValueError(f"Archivo demasiado grande: {path}")
    return content


def load_release(get=download):
    receipt = json.loads(get(RECEIPT))
    files = receipt["files"]
    canonical = json.dumps(files, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    release_id = sha256(canonical)
    if receipt.get("version") != 1 or receipt.get("release_id") != release_id:
        raise ValueError("El comprobante de publicación no es válido")

    payloads = {}
    for path in (HEALTH, DATA):
        raw = get(path, release_id)
        if sha256(raw) != files.get(path):
            raise ValueError(f"No coincide el SHA-256 de {path}")
        payloads[path] = json.loads(raw)
    health = payloads[HEALTH]
    if (
        health.get("data_error") is not False
        or health.get("query_coverage") != "valid"
        or health.get("pending_data")
        or health.get("isolated_failures")
        or not health.get("data_checked_at")
        or health["data_checked_at"] != receipt.get("data_checked_at")
        or not SERIES_FIELDS.keys() <= set(health.get("queried_indicators", []))
    ):
        raise ValueError("La edición no acredita una consulta válida de los indicadores del piloto")
    return payloads[DATA], receipt


def stage(institutional, commercial):
    """Copia series con paridad exacta y conserva los metadatos institucionales."""
    candidate = deepcopy(institutional)
    results = {}
    for key, fields in SERIES_FIELDS.items():
        current = institutional["indicators"][key]
        shared = commercial["indicators"][key]
        if shared["key"] != key or any(current[field] != shared[field] for field in SCHEMA_FIELDS):
            raise ValueError(f"{key}: esquema o fuente distintos")
        if shared["last_observation"] != current["last_observation"]:
            raise ValueError(f"{key}: corte distinto ({current['last_observation']} / {shared['last_observation']})")
        for field in fields:
            if not shared[field] or current[field] != shared[field]:
                raise ValueError(f"{key}: diferencias en la serie {field}")
            candidate["indicators"][key][field] = deepcopy(shared[field])
        results[key] = {
            "corte": shared["last_observation"],
            **{field: len(shared[field]) for field in fields},
        }
    return candidate, results


def checked_at(value):
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError("La fecha de consulta requiere zona horaria")
    return result


def indexed_rows(rows, width):
    if not isinstance(rows, list) or not rows:
        raise ValueError("serie vacía")
    result = {}
    for row in rows:
        period = period_to_date(row["period"])
        values = row["values"]
        if period is None or (result and period <= next(reversed(result))):
            raise ValueError("periodos inválidos, repetidos o fuera de orden")
        if not isinstance(values, list) or len(values) != width or any(
            v is not None and (type(v) not in (int, float) or not isfinite(v))
            for v in values
        ):
            raise ValueError("observación incompatible con el esquema numérico")
        result[period] = row
    return result


def compare_series(current, shared, field):
    width = len(current["columns"]) if field == "observations" else 1
    original = indexed_rows(current[field], width)
    incoming = indexed_rows(shared[field], width)
    if next(reversed(incoming)) < next(reversed(original)):
        raise ValueError(f"{field}: corte comercial atrasado")
    if original.keys() - incoming.keys():
        raise ValueError(f"{field}: faltan periodos institucionales")
    if any(
        old is not None and new is None
        for period, row in original.items()
        for old, new in zip(row["values"], incoming[period]["values"])
    ):
        raise ValueError(f"{field}: se perderían valores publicados")
    return {
        "nuevos": len(incoming.keys() - original.keys()),
        "revisados": sum(original[p] != incoming[p] for p in original),
    }


def simulate(institutional, commercial, institutional_checked_at, commercial_checked_at):
    """Evalúa actualizaciones sin escribir datos ni productos institucionales."""
    baseline = checked_at(institutional_checked_at)
    published = checked_at(commercial_checked_at)
    report = {}
    for key, fields in SERIES_FIELDS.items():
        current = institutional["indicators"][key]
        existing_cut = current["last_observation"]
        try:
            shared = commercial["indicators"][key]
            incoming_cut = shared["last_observation"]
            if shared["key"] != key or any(current[f] != shared[f] for f in SCHEMA_FIELDS):
                raise ValueError("esquema o fuente distintos")
            for indicator in (current, shared):
                last = indicator["observations"][-1]
                if indicator["last_observation"] != last["period"] or last["values"][0] is None:
                    raise ValueError("último periodo incongruente con la serie")
            series = {field: compare_series(current, shared, field) for field in fields}
            changed = any(counts["nuevos"] or counts["revisados"] for counts in series.values())
            if changed and published <= baseline:
                raise ValueError("consulta comercial anterior o igual a la consulta institucional")
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            report[key] = {"decision": "conservar", "corte": existing_cut, "motivo": str(exc)}
        else:
            report[key] = {
                "decision": "adoptar" if changed else "equivalente",
                "corte": incoming_cut,
                "series": series,
            }
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--institucional", type=Path, default=Path(DATA))
    parser.add_argument("--salida", type=Path, help="Archivo nuevo para la edición de prueba")
    parser.add_argument("--estado-institucional", type=Path,
                        help="Comprobante institucional para simular una actualización")
    args = parser.parse_args()
    if args.estado_institucional and args.salida:
        parser.error("La simulación emite un informe y no admite --salida")
    try:
        institutional = json.loads(args.institucional.read_bytes())
        commercial, receipt = load_release()
        if args.estado_institucional:
            health = json.loads(args.estado_institucional.read_bytes())
            if health.get("data_error") is not False:
                raise ValueError("El estado institucional no acredita una consulta válida")
            results = simulate(institutional, commercial, health["data_checked_at"], receipt["data_checked_at"])
        else:
            candidate, results = stage(institutional, commercial)
            if args.salida:
                content = json.dumps(candidate, ensure_ascii=False, indent=2, allow_nan=False)
                with args.salida.open("x", encoding="utf-8") as output:
                    output.write(content + "\n")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f"Piloto sin edición candidata: {exc}\n")
    print(json.dumps({
        "release_id": receipt["release_id"],
        "data_checked_at": receipt["data_checked_at"],
        "indicadores": results,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

