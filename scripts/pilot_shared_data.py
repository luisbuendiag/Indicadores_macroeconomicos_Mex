"""Prepara una edición institucional de prueba desde la edición pública de MacroMéxico."""

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--institucional", type=Path, default=Path(DATA))
    parser.add_argument("--salida", type=Path, help="Archivo nuevo para la edición de prueba")
    args = parser.parse_args()
    try:
        institutional = json.loads(args.institucional.read_bytes())
        commercial, receipt = load_release()
        candidate, results = stage(institutional, commercial)
        if args.salida:
            with args.salida.open("x", encoding="utf-8") as output:
                json.dump(candidate, output, ensure_ascii=False, indent=2, allow_nan=False)
                output.write("\n")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f"Piloto sin edición candidata: {exc}\n")
    print(json.dumps({
        "release_id": receipt["release_id"],
        "data_checked_at": receipt["data_checked_at"],
        "indicadores": results,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
