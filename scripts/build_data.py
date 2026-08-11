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
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import build_calendar
import lib_data as L
import lib_freshness
import lib_kpicfg
import lib_metrics
from sources import banxico, inegi, inegi_bulletin, worldbank
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


def _quarter_start(ym: str) -> str:
    """Devuelve el primer mes del trimestre al que pertenece ym."""
    year, month = map(int, ym.split("-"))
    q = (month - 1) // 3
    month = q * 3 + 1
    return f"{year:04d}-{month:02d}"


def apply_inegi_total(payload: dict, key: str, item: dict, prev_last: str | None) -> dict | None:
    """Fusiona una serie del INEGI sobre UNA columna del indicador existente.

    Actualiza sólo la columna objetivo (p. ej. el índice total del IGAE) con las
    observaciones oficiales de la API, conservando el resto de columnas/desgloses
    de respaldo. Agrega los periodos nuevos que la API tenga. Devuelve el registro
    de consulta para el update_log, o None si el indicador no existe en la capa de
    datos.
    """
    ind = payload["indicators"].get(key)
    if ind is None:
        return None

    tcol = item["target_column"]
    ncol = len(ind.get("columns") or []) or (tcol + 1)
    api_by_ym = {o["ym"]: o["value"] for o in item["api_total"]}

    # Para series trimestrales, la API de INEGI puede devolver observaciones con
    # TIME_PERIOD en cada mes del trimestre; las colapsamos al primer mes.
    is_quarter = item.get("freq") == 4 or "trimest" in (ind.get("frecuencia") or "").lower()

    def _key(ym: str) -> str:
        return _quarter_start(ym) if is_quarter else ym

    # Fusionar por ym (o primer mes del trimestre) para evitar duplicados.
    rows_by_ym: dict[str, dict] = {}
    for o in ind.get("observations", []):
        ym = inegi.label_to_ym(o.get("period", ""))
        if ym is None:
            continue
        key = _key(ym)
        vals = list(o.get("values", []))
        while len(vals) < ncol:
            vals.append(None)
        rows_by_ym[key] = {"period": o.get("period", ""), "values": vals}

    # Actualizar la columna objetivo y agregar nuevos periodos.
    for o in item["api_total"]:
        if o.get("value") is None:
            continue
        key = _key(o["ym"])
        if key in rows_by_ym:
            vals = rows_by_ym[key]["values"]
        else:
            vals = [None] * ncol
            period_label = o.get("period") or inegi.ym_to_label(key, item.get("freq"))
            rows_by_ym[key] = {"period": period_label, "values": vals}
        if 0 <= tcol < ncol:
            vals[tcol] = round(o["value"], 6)

    rows = sorted(rows_by_ym.items(), key=lambda t: t[0])
    ind["observations"] = [o for _, o in rows]
    ind["last_observation"] = ind["observations"][-1]["period"]
    ind["last_updated"] = L.today_iso()
    ind["last_checked"] = L.today_iso()
    ind["source_origin"] = "api"
    fuente = dict(ind.get("fuente", {}))
    fuente["serie"] = item["serie"]
    fuente["metodo"] = item.get("metodo", "INEGI BIE API")
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
        # inegi_bulletin se ejecuta primero para evitar throttling del sitio de prensa
        # después de las llamadas masivas al BIE.
        for name, mod in (("inegi_bulletin", inegi_bulletin), ("banxico", banxico), ("inegi", inegi), ("worldbank", worldbank)):
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
                    if name in ("inegi", "inegi_bulletin"):
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

    # Perfil V3: scaffolds, orden principal/complementario y metadatos base.
    log["changes"].extend(L.apply_profile(payload))

    # Frescura, calendario, métricas compartidas y metadatos temporales.
    log["changes"].extend(apply_freshness_and_meta(payload, log))

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


def _periodo_referencia_reciente(payload: dict) -> dict:
    """Periodo de referencia más reciente entre indicadores principales (cronológico)."""
    from sources import inegi
    principal = lib_kpicfg.get_cfg("PRINCIPAL")
    candidates = []
    for key in principal:
        ind = payload["indicators"].get(key)
        if not ind or not ind.get("last_observation"):
            continue
        ym = inegi.label_to_ym(ind["last_observation"])
        if ym:
            candidates.append((ym, ind["last_observation"]))
    if not candidates:
        return None
    candidates.sort()
    return {"period": candidates[-1][1], "period_long": inegi.ym_to_label(candidates[-1][0])}


def apply_freshness_and_meta(payload: dict, log: dict, as_of: date | None = None) -> list[str]:
    """Aplica frescura (estados ACTUALIZADO/PENDIENTE/REZAGADO/ERROR), escribe el
    calendario, calcula métricas y actualiza metadatos temporales."""
    changes: list[str] = []
    if as_of is None:
        as_of = date.today()

    # Calendario oficial con la fecha de referencia del pipeline.
    cal = build_calendar.build(as_of=as_of)
    (L.DATA_DIR / "calendario_publicaciones.json").write_text(
        json.dumps(cal, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    changes.append(f"calendario: regenerado con as_of={as_of.isoformat()}")

    # Métricas compartidas para dashboard, Excel, Word, JSON y CSV.
    lib_kpicfg.build_cfg(force=True)
    metrics = lib_metrics.compute_all_metrics(payload)
    (L.DATA_DIR / "metrics.json").write_text(
        json.dumps({
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "last_update_ct": payload.get("meta", {}).get("last_update_ct") or payload.get("meta", {}).get("generated_at"),
            "indicators": metrics,
        }, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    for key, m in metrics.items():
        payload["indicators"][key]["metrics"] = {
            "kpi": m["kpi"],
            "yoy": m["annualVar"],
            "resumen": m["resumen"],
        }
    changes.append("métricas: data/metrics.json regenerado")

    # Rellenar columnas derivadas (saldo, total) en las observaciones para que
    # Excel, CSV y el frontend compartan el mismo valor sin recalcularlo.
    full_cfg = lib_kpicfg.get_cfg()
    kpicfg = full_cfg.get("KPICFG", {})
    for key, ind in payload["indicators"].items():
        cfg = kpicfg.get(key, {})
        if cfg.get("derived") == "saldo":
            for o in ind.get("observations", []):
                vals = o.get("values", [])
                if len(vals) >= 3 and vals[2] is None and vals[0] is not None and vals[1] is not None:
                    vals[2] = round(vals[0] - vals[1], 6)

    # Frescura por indicador.
    manifest_rows = {key: {
        "clave": key,
        "fuente": ind.get("fuente", {}).get("nombre"),
        "serie": ind.get("fuente", {}).get("serie"),
        "frecuencia": ind.get("frecuencia"),
    } for key, ind in payload["indicators"].items()}
    diag = lib_freshness.diagnose_all(
        payload["indicators"],
        manifest_rows=manifest_rows,
        update_log=log,
        calendar=cal["items"],
        as_of=as_of,
    )
    for key, info in diag.items():
        ind = payload["indicators"][key]
        ind["estado"] = info["estado"]
        ind["periodo_referencia_oficial"] = info["periodo_oficial"]
        ind["fecha_publicacion_oficial"] = info["fecha_publicacion_oficial"]
        ind["proxima_publicacion"] = info["proxima_publicacion"] and {
            "fecha_publicacion": info["proxima_publicacion"],
            "periodo_referencia": info["periodo_proximo"],
        }
        motivo = info["motivo"]
        # Si el periodo vigente tiene componentes marcados como revisión/pendiente,
        # reflejarlo explícitamente en el motivo de frescura para no confundir estado.
        for q in ind.get("data_quality", []):
            if q.get("status") in ("revisión", "pendiente") and q.get("period") == ind.get("last_observation"):
                col_idx = q.get("column")
                col_label = None
                if isinstance(col_idx, int) and 0 <= col_idx < len(ind.get("columns", [])):
                    col_label = ind["columns"][col_idx].get("label")
                motivo += f" Nota: {col_label or f'componente {col_idx}'} del último periodo está pendiente de publicación ({q.get('reason', 'sin detalle')})."
        ind["motivo_frescura"] = motivo
        ind["url_fuente_oficial"] = info.get("url_boletin") or ind.get("fuente", {}).get("link")
        ind["url_boletin_oficial"] = info.get("url_boletin") or ind.get("fuente", {}).get("link")
        ind["fecha_publicacion"] = info["fecha_publicacion_oficial"]
        ind["fecha_ultima_publicacion"] = info.get("fecha_publicacion_oficial")
        ind["regla_publicacion"] = info.get("regla_publicacion")
        if info.get("proxima_publicacion_tipo") and ind.get("proxima_publicacion"):
            ind["proxima_publicacion"]["tipo"] = info["proxima_publicacion_tipo"]
        elif info.get("proxima_publicacion_tipo") and (info.get("proxima_publicacion") or info.get("periodo_proximo")):
            ind["proxima_publicacion"] = {"tipo": info["proxima_publicacion_tipo"], "fecha_publicacion": info.get("proxima_publicacion"), "periodo_referencia": info.get("periodo_proximo")}
        changes.append(f"frescura: {key} -> {info['estado']}")
        if info["estado"] == lib_freshness.ESTADOS["REZAGADO"]:
            log["warnings"].append(f"{key}: REZAGADO – {info['motivo']}")
        if info["estado"] == lib_freshness.ESTADOS["ERROR_FUENTE"]:
            log["warnings"].append(f"{key}: ERROR DE FUENTE – {info['motivo']}")

    # Metadatos temporales y de referencia.
    now_ct = datetime.now(ZoneInfo("America/Mexico_City"))
    payload["meta"] = payload.get("meta", {})
    payload["meta"]["last_update_ct"] = now_ct.isoformat(timespec="seconds")
    payload["meta"]["periodo_referencia_reciente"] = _periodo_referencia_reciente(payload)
    changes.append(f"meta: last_update_ct={payload['meta']['last_update_ct']}")
    return changes


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