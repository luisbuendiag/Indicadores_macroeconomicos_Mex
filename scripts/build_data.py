"""Pipeline de actualización de datos (transaccional en términos funcionales).

Flujo:
  1. Cargar la capa de datos actual (o inicializarla desde el legado).
  2. Ejecutar conectores disponibles (Banxico, INEGI, World Bank). Los que no
     tengan token o IDs confirmados se omiten SIN borrar datos.
  3. Aplicar overrides de calidad (data/overrides.json).
  4. Validar. Si hay errores críticos, NO se reemplazan los datos publicados:
     se restaura la última versión válida y se registra el error.
  5. Escribir data/indicadores.json, CSV, manifest y summary.

Uso:
    python scripts/build_data.py            # actualización normal
    python scripts/build_data.py --offline  # sin llamadas de red (sólo overrides+validación)
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import lib_data as L
from sources import banxico, inegi, worldbank
import validate as V

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "series.json"
LOG_FILE = L.DATA_DIR / "update_log.json"


def merge_indicator(payload: dict, key: str, new_ind: dict) -> None:
    """Inserta/actualiza un indicador conservando su posición en 'order'."""
    payload["indicators"][key] = {**payload["indicators"].get(key, {}), **new_ind,
                                   "last_updated": L.today_iso(), "last_checked": L.today_iso(),
                                   "source_origin": "api"}
    order = payload.setdefault("order", [])
    if key not in order:
        order.append(key)


def run(offline: bool = False) -> int:
    log = {"started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "warnings": [], "changes": [], "critical": [], "mode": "offline" if offline else "online"}

    L.load_env()
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    payload = L.load_data()

    if not offline:
        for name, mod in (("banxico", banxico), ("inegi", inegi), ("worldbank", worldbank)):
            try:
                res = mod.fetch(config)
            except Exception as e:  # noqa: BLE001 - resiliencia total del pipeline
                log["warnings"].append(f"{name}: excepción no fatal: {e}")
                continue
            log["warnings"].extend(res.warnings)
            if name == "worldbank" and res.ok:
                (L.DATA_DIR / "worldbank.json").write_text(
                    json.dumps({"generated_at": log["started_at"], "series": res.data},
                               ensure_ascii=False, indent=2), encoding="utf-8")
                continue
            if res.ok:
                for key, ind in res.data.items():
                    merge_indicator(payload, key, ind)
                    log["changes"].append(f"{name}: actualizado {key}")

    # Overrides de calidad
    log["changes"].extend(L.apply_overrides(payload))

    # Perfil V3: scaffolds, orden principal/complementario y estados honestos.
    log["changes"].extend(L.apply_profile(payload))

    payload["meta"]["generated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # Validación con datos candidatos en memoria (archivo temporal)
    tmp = L.DATA_DIR / "_candidate.json"
    L.save_data(payload, tmp)
    errors, warnings = V.validate(payload)
    log["warnings"].extend(warnings)

    if errors:
        log["critical"].extend(errors)
        tmp.unlink(missing_ok=True)
        # Modo respaldo: conservar la última versión válida publicada.
        restored = L.restore_last_valid()
        log["result"] = "RECHAZADO_POR_VALIDACION" + (" (restaurada última versión válida)" if restored else " (sin respaldo previo; datos actuales sin cambios)")
        _write_log(log)
        print("ERROR: validación crítica falló; no se publican los cambios.")
        for e in errors:
            print("  -", e)
        return 1

    # Publicación: respaldar lo anterior y escribir lo nuevo
    L.backup_current()
    L.save_data(payload)
    tmp.unlink(missing_ok=True)
    L.write_csvs(payload)
    L.write_manifest(payload)
    build_summary(payload)
    log["result"] = "OK"
    _write_log(log)
    print(f"OK: datos publicados. {len(log['changes'])} cambios, {len(warnings)} advertencias.")
    return 0


def build_summary(payload: dict) -> None:
    """Resumen ejecutivo mínimo persistido (respaldo del cálculo del frontend)."""
    latest = max((i.get("last_updated") or "" for i in payload["indicators"].values()), default="")
    summary = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "last_update": latest,
               "indicadores": len(payload["indicators"])}
    (L.DATA_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_log(log: dict) -> None:
    log["finished_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    LOG_FILE.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()
    raise SystemExit(run(offline=args.offline))


if __name__ == "__main__":
    main()
