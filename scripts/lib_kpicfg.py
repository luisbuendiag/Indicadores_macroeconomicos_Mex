"""Extrae la configuración de assets/js/config.js a config/kpicfg.json.

Mantiene a assets/js/config.js como fuente única de verdad de KPICFG, COLORS,
PRINCIPAL, COMPLEMENTARIOS, ORDER, LABELS, SIGLA, CAPTIONS, WINDOWS, VIEWS y
ESTADOS. El pipeline genera el JSON derivado para que Python no duplique la
configuración.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_JS = ROOT / "assets" / "js" / "config.js"
CACHE = ROOT / "config" / "kpicfg.json"

NAMES = ["KPICFG", "COLORS", "PRINCIPAL", "COMPLEMENTARIOS",
         "LABELS", "SIGLA", "CAPTIONS", "ESTADOS"]


def _extract(name: str, src: str) -> str:
    """Extrae el bloque `export const NAME = ...;` del ES module."""
    pat = re.compile(rf"export const {re.escape(name)}\s*=\s*(\{{[\s\S]*?\n\}});", re.MULTILINE)
    if name in ("PRINCIPAL", "COMPLEMENTARIOS", "ORDER"):
        pat = re.compile(rf"export const {re.escape(name)}\s*=\s*(\[[^\]]+\]);", re.MULTILINE)
    m = pat.search(src)
    if not m:
        raise ValueError(f"No se encontró {name} en {CONFIG_JS}")
    return m.group(1)


def _to_json_like(raw: str) -> str:
    """Convierte un literal de objeto JS a JSON válido (solo para esta config)."""

    def quote_key(m: re.Match) -> str:
        before = m.group(1) or ""
        return f'{before}"{m.group(2)}":'

    # Claves al inicio de línea (después de espacios).
    s = re.sub(r'(^[ \t]*)([A-Za-z_ÁÉÍÓÚáéíóú][A-Za-z0-9_ÁÉÍÓÚáéíóú]*)[ \t]*:', quote_key, raw, flags=re.MULTILINE)
    # Claves que siguen a '{' o ',' en la misma línea (no reemplaza dentro de cadenas,
    # pues las claves dentro de strings no están precedidas por { o ,).
    s = re.sub(r'(?<=\{|\,)([ \t]*)([A-Za-z_ÁÉÍÓÚáéíóú][A-Za-z0-9_ÁÉÍÓÚáéíóú]*)[ \t]*:', quote_key, s)
    # JS permite trailing commas; JSON no.
    s = re.sub(r',\s*}', '}', s)
    s = re.sub(r',\s*]', ']', s)
    return s


def _parse_block(name: str, src: str):
    raw = _extract(name, src)
    if name in ("PRINCIPAL", "COMPLEMENTARIOS", "ORDER"):
        return json.loads(raw)
    json_like = _to_json_like(raw)
    try:
        return json.loads(json_like)
    except json.JSONDecodeError as e:
        raise ValueError(f"No se pudo parsear {name}: {e}") from e


def build_cfg(force: bool = False) -> dict:
    if not force and CACHE.exists():
        src = CACHE.read_text("utf-8")
        cached = json.loads(src)
        return cached
    if not CONFIG_JS.exists():
        raise FileNotFoundError(CONFIG_JS)
    src = CONFIG_JS.read_text("utf-8")
    cfg = {n: _parse_block(n, src) for n in NAMES}
    CACHE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", "utf-8")
    return cfg


def get_cfg(key: str | None = None) -> Any:
    """Configuración JS disponible como dict Python. Cacheada en config/kpicfg.json."""
    cfg = build_cfg()
    return cfg[key] if key else cfg


if __name__ == "__main__":
    import sys
    cfg = build_cfg(force="--force" in sys.argv)
    print(f"OK: {CACHE.relative_to(ROOT)} generado con {len(cfg['KPICFG'])} indicadores.")
