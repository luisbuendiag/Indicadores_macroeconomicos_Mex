"""Extrae los datos embebidos (window.MACRO) del index.html compilado original
y los normaliza a data/indicadores.json + CSV por indicador + manifest.json.

Se ejecuta UNA sola vez para inicializar la capa de datos abierta a partir del
dashboard legado. Después, el pipeline (scripts/build_data.py + conectores)
mantiene estos archivos.

Uso:
    python scripts/extract_legacy.py [--source legacy/dashboard-original.html]
"""
from __future__ import annotations

import argparse
import base64
import csv
import gzip
import json
import re
import unicodedata
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DEFAULT_SOURCE = ROOT / "legacy" / "dashboard-original.html"

# ---- Metadatos declarativos por indicador (esquema normalizado) ----
# Estos catálogos enriquecen los datos crudos del legado con unidad, ajuste
# estacional, serie de la fuente y método de actualización previsto.
INDICATOR_META = {
    "PIB": dict(unidad="Millones de pesos (a precios de 2018)", ajuste="Serie original",
                grupo="actividad", fuente_nombre="INEGI (SCNM)", metodo="INEGI BIE API"),
    "PIBSEC": dict(unidad="Millones de pesos (a precios de 2018)", ajuste="Serie original",
                   grupo="actividad", fuente_nombre="INEGI (SCNM)", metodo="INEGI BIE API"),
    "IGAE": dict(unidad="Índice base 2018=100", ajuste="Serie original",
                 grupo="actividad", fuente_nombre="INEGI", metodo="INEGI BIE API"),
    "IMAI": dict(unidad="Índice base 2018=100", ajuste="Serie original",
                 grupo="industria", fuente_nombre="INEGI", metodo="INEGI BIE API"),
    "CONSUMO": dict(unidad="Índice base 2018=100", ajuste="Serie original",
                    grupo="mercado_interno", fuente_nombre="INEGI", metodo="INEGI BIE API"),
    "IED": dict(unidad="Millones de dólares", ajuste="No aplica",
                grupo="inversion", fuente_nombre="Secretaría de Economía (RNIE)",
                metodo="Descarga oficial RNIE / DataMéxico"),
    "DESOCUP": dict(unidad="Porcentaje de la PEA", ajuste="Serie original",
                    grupo="mercado_interno", fuente_nombre="INEGI (ENOE/ENOEN)",
                    metodo="INEGI BIE API"),
    "INPC": dict(unidad="Variación anual (%)", ajuste="No aplica",
                 grupo="precios", fuente_nombre="INEGI", metodo="INEGI BIE API"),
    "BALANZA": dict(unidad="Millones de dólares", ajuste="Serie original",
                    grupo="comercio_exterior", fuente_nombre="INEGI", metodo="INEGI BIE API"),
}

# Corrección de atribución de fuente (decisión #7 del usuario): la tasa de
# desocupación proviene de INEGI/ENOE, no de la OCDE (que sólo es comparativo).
SOURCE_FIXES = {
    "DESOCUP": dict(
        fuenteTexto="INEGI — Encuesta Nacional de Ocupación y Empleo (ENOE/ENOEN)",
        link="https://www.inegi.org.mx/temas/empleo/",
    ),
}


def clean_period(p: str) -> str:
    """Normaliza el texto de periodo: quita NBSP y espacios repetidos."""
    if p is None:
        return p
    p = p.replace("\u00a0", " ")
    p = unicodedata.normalize("NFKC", p)
    p = re.sub(r"\s+", " ", p).strip()
    return p


def load_macro(source: Path) -> dict:
    html = source.read_text(encoding="utf-8")
    man_m = re.search(r'<script type="__bundler/manifest">(.*?)</script>', html, re.S)
    if not man_m:
        raise SystemExit("No se encontró el manifiesto del bundle en el HTML.")
    manifest = json.loads(man_m.group(1))
    for uuid, entry in manifest.items():
        if entry.get("mime") not in ("application/javascript", "text/javascript"):
            continue
        raw = base64.b64decode(entry["data"])
        if entry.get("compressed"):
            raw = gzip.decompress(raw)
        text = raw.decode("utf-8", "replace")
        m = re.search(r"window\.MACRO\s*=\s*(\{.*\});?\s*$", text, re.S)
        if m:
            return json.loads(m.group(1))
    raise SystemExit("No se encontró window.MACRO en los assets del bundle.")


def normalize(macro: dict) -> dict:
    today = date.today().isoformat()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    indicators = {}
    for key, ind in macro.items():
        meta = INDICATOR_META.get(key, {})
        fix = SOURCE_FIXES.get(key, {})
        cols = [
            {"label": c["label"], "index": c["k"], "fmt": c["fmt"]}
            for c in ind.get("cols", [])
        ]
        observations = [
            {"period": clean_period(r["p"]), "values": r["v"]}
            for r in ind.get("rows", [])
        ]
        last_period = observations[-1]["period"] if observations else None
        indicators[key] = {
            "key": key,
            "nombre": ind.get("nombre", "").strip(),
            "descripcion": ind.get("descripcion", "").strip(),
            "frecuencia": ind.get("frecuencia"),
            "unidad": meta.get("unidad"),
            "ajuste_estacional": meta.get("ajuste"),
            "grupo": meta.get("grupo"),
            "publicacion": ind.get("publicacion"),
            "proximo": ind.get("proximo"),
            "notas": ind.get("notas", []),
            "fuente": {
                "nombre": fix.get("fuenteTexto", ind.get("fuenteTexto") or meta.get("fuente_nombre")),
                "link": fix.get("link", ind.get("link") or ""),
                "metodo": meta.get("metodo"),
            },
            "columns": cols,
            "observations": observations,
            "last_observation": last_period,
            "last_updated": today,   # origen: dashboard legado
            "last_checked": today,
            "source_origin": "legacy_dashboard",
        }
    return {
        "meta": {
            "generated_at": now,
            "base_year": 2018,
            "default_window": "since_2018",
            "windows": ["12m", "24m", "since_2018", "max"],
            "note": "Datos inicializados desde el dashboard legado; el pipeline los actualiza.",
        },
        "order": ["PIB", "PIBSEC", "IGAE", "IMAI", "BALANZA", "IED", "DESOCUP", "INPC", "CONSUMO"],
        "indicators": indicators,
    }


def write_csvs(payload: dict) -> None:
    csv_dir = DATA_DIR / "csv"
    csv_dir.mkdir(parents=True, exist_ok=True)
    for key, ind in payload["indicators"].items():
        path = csv_dir / f"{key}.csv"
        with path.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            header = ["periodo"] + [c["label"] for c in ind["columns"]]
            w.writerow(header)
            for obs in ind["observations"]:
                w.writerow([obs["period"]] + [
                    "" if v is None else v for v in obs["values"]
                ])


def write_manifest(payload: dict) -> None:
    rows = []
    for key in payload["order"]:
        ind = payload["indicators"][key]
        rows.append({
            "indicador": ind["nombre"],
            "clave": key,
            "fuente": ind["fuente"]["nombre"],
            "serie": None,
            "frecuencia": ind["frecuencia"],
            "unidad": ind["unidad"],
            "ajuste_estacional": ind["ajuste_estacional"],
            "ultima_observacion": ind["last_observation"],
            "fecha_consulta": ind["last_checked"],
            "fecha_actualizacion_archivo": ind["last_updated"],
            "metodo_actualizacion": ind["fuente"]["metodo"],
            "estatus": "origen: dashboard legado (pendiente de verificación por API)",
            "revision_detectada": False,
            "observaciones": "",
        })
    manifest = {
        "generated_at": payload["meta"]["generated_at"],
        "indicadores": rows,
    }
    (DATA_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=str(DEFAULT_SOURCE))
    args = ap.parse_args()
    macro = load_macro(Path(args.source))
    payload = normalize(macro)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "indicadores.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_csvs(payload)
    write_manifest(payload)
    n = len(payload["indicators"])
    print(f"OK: {n} indicadores -> data/indicadores.json, data/csv/*.csv, data/manifest.json")


if __name__ == "__main__":
    main()
