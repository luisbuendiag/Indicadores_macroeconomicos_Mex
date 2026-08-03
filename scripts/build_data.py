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


def apply_inegi_total(payload: dict, key: str, item: dict, prev_last: str | None) -> dict | None:
    """Fusiona una serie del INEGI sobre UNA columna del indicador existente.

    Actualiza sólo la columna objetivo (p. ej. el índice total del IGAE) con las
    observaciones oficiales de la API, conservando el resto de columnas/desgloses
    de respaldo. Agrega los periodos nuevos que la API tenga por encima del último
    periodo mostrado. Devuelve el registro de consulta para el update_log, o None
    si el indicador no existe en la capa de datos.
    """
    ind = payload["indicators"].get(key)
    if ind is None:
        return None

    tcol = item["target_column"]
    ncol = len(ind.get("columns") or []) or (tcol + 1)
    api_by_ym = {o["ym"]: o["value"] for o in item["api_total"]}

    rows: list[tuple[str, dict]] = []
    existing_yms: list[str] = []
    for o in ind.get("observations", []):
        ym = inegi.label_to_ym(o.get("period", ""))
        vals = list(o.get("values", []))
        while len(vals) < ncol:
            vals.append(None)
        if ym is not None and ym in api_by_ym and 0 <= tcol < ncol:
            vals[tcol] = round(api_by_ym[ym], 6)
        rows.append((ym or o.get("period", ""), {**o, "values": vals}))
        if ym is not None:
            existing_yms.append(ym)

    max_ym = max(existing_yms, default=None)
    for o in item["api_total"]:
        ym = o["ym"]
        if max_ym is None or ym > max_ym:
            vals = [None] * ncol
            if 0 <= tcol < ncol:
                vals[tcol] = round(o["value"], 6)
            period_label = o.get("period") or inegi.ym_to_label(ym, item.get("freq"))
            rows.append((ym, {"period": period_label, "values": vals}))

    rows.sort(key=lambda t: t[0])
    ind["observations"] = [o for _, o in rows]
    ind["last_observation"] = ind["observations"][-1]["period"]
    ind["last_updated"] = L.today_iso()
    ind["last_checked"] = L.today_iso()
    ind["source_origin"] = "api"
    fuente = dict(ind.get("fuente", {}))
    fuente["serie"] = item["serie"]
    fuente["metodo"] = "INEGI BIE API"
    if item.get("link"):
        fuente["link"] = item["link"]
    ind["fuente"] = fuente

    meta = item.get("api_meta", {})
    nueva = ind["last_observation"]
    return {
        "fuente": "inegi", "indicador": key, "serie": item["serie"],
        "observaciones": meta.get("n_obs"), "ultima_observacion": nueva,
        "ultimo_valor": meta.get("ultimo_valor"), "observacion_previa": prev_last,
        "actualizacion_fuente": meta.get("lastupdate"),
        "dato_nuevo": nueva != prev_last, "resultado": "consulta válida",
    }


def run(offline: bool = False) -> int:
    log = {"started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "mode": "offline" if offline else "online",
           "network_calls": False,
           "warnings": [], "changes": [], "consultas": [], "critical": []}

    L.load_env()
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    payload = L.load_data()
    prev_obs = {k: v.get("last_observation") for k, v in payload.get("indicators", {}).items()}

    if not offline:
        for name, mod in (("banxico", banxico), ("inegi", inegi), ("worldbank", worldbank)):
            log["network_calls"] = True
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
                    if name == "inegi":
                        items = ind if isinstance(ind, list) else [ind]
                        consultas = []
                        for it in items:
                            consulta = apply_inegi_total(payload, key, it, prev_obs.get(key))
                            if consulta is None:
                                log["warnings"].append(
                                    f"INEGI {key}: sin indicador base para fusionar; se omite.")
                                continue
                            consultas.append(consulta)
                            log["consultas"].append(consulta)
                            log["changes"].append(
                                f"{name}: actualizado {key} (última obs {consulta['ultima_observacion']}"
                                + (", dato nuevo" if consulta['dato_nuevo'] else ", sin cambio de periodo") + ")")
                        continue
                    else:
                        api_meta = ind.pop("api_meta", {})
                        merge_indicator(payload, key, ind)
                        nueva = ind.get("last_observation")
                        consulta = {
                            "fuente": name, "indicador": key,
                            "serie": api_meta.get("serie") or ind.get("fuente", {}).get("serie"),
                            "observaciones": api_meta.get("n_obs"),
                            "ultima_observacion": nueva,
                            "ultimo_valor": api_meta.get("ultimo_valor"),
                            "observacion_previa": prev_obs.get(key),
                            "actualizacion_fuente": api_meta.get("lastupdate"),
                            "dato_nuevo": nueva is not None and nueva != prev_obs.get(key),
                            "resultado": "consulta válida",
                        }
                    log["consultas"].append(consulta)
                    log["changes"].append(
                        f"{name}: actualizado {key} (última obs {consulta['ultima_observacion']}"
                        + (", dato nuevo" if consulta["dato_nuevo"] else ", sin cambio de periodo") + ")")

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
