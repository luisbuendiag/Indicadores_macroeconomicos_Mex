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
import re
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import build_calendar
import lib_data as L
import lib_freshness
import lib_kpicfg
import lib_metrics
from sources import (banxico, banxico_policy, banxico_sie, ied, inegi,
                     inegi_bulletin, inegi_inpc, inegi_inpp, worldbank)
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


def apply_pibt_source(payload: dict, key: str, item: dict, prev_last: str | None) -> dict | None:
    """Crea/actualiza el objeto 'pibt' del indicador PIB con el nivel tradicional."""
    ind = payload["indicators"].get(key)
    if ind is None:
        return None

    observations = []
    for o in item.get("api_total", []):
        period = o.get("period") or inegi.ym_to_label(o["ym"], item.get("freq"))
        if period and o.get("value") is not None:
            observations.append({"period": period, "values": [round(o["value"], 6)]})

    ind["pibt"] = {
        "observations": observations,
        "columns": [{"label": "PIB", "index": 0, "fmt": "bill"}],
        "fuente": {
            "nombre": "INEGI",
            "metodo": item.get("metodo", "INEGI BIE API"),
            "serie": item.get("serie"),
            "link": item.get("link"),
        },
        "frecuencia": ind.get("frecuencia", "Trimestral"),
        "unidad": "Millones de pesos (a precios de 2018)",
        "ajuste_estacional": "Serie original",
    }

    meta = item.get("api_meta", {})
    last = ind["pibt"]["observations"][-1]["period"] if ind["pibt"]["observations"] else None
    return {
        "fuente": "inegi", "indicador": key, "serie": item["serie"],
        "observaciones": meta.get("n_obs"), "ultima_observacion": last,
        "ultimo_valor": meta.get("ultimo_valor"), "observacion_previa": prev_last,
        "actualizacion_fuente": meta.get("lastupdate"),
        "dato_nuevo": last != prev_last, "resultado": "consulta válida (pibt)",
    }


def sync_pibsec_pibt(payload: dict) -> list[str]:
    """Copia el nivel del PIB total (objeto 'pibt' de PIB) a la columna 5 de PIBSEC.

    Permite que PIBSEC muestre el nivel oficial del PIB junto al valor agregado por
    actividades, sin duplicar series BIE.
    """
    changes: list[str] = []
    pib = payload["indicators"].get("PIB")
    pibsec = payload["indicators"].get("PIBSEC")
    if not pib or not pibsec:
        return changes
    pibt = pib.get("pibt")
    if not pibt or not pibt.get("observations"):
        return changes

    # Último valor por periodo en pibt (puede haber revisiones duplicadas).
    pibt_values: dict[str, float] = {}
    for o in pibt["observations"]:
        v = o.get("values", [None])[0]
        if v is not None:
            pibt_values[o["period"]] = v

    if not pibt_values:
        return changes

    by_period: dict[str, dict] = {o["period"]: o for o in pibsec.get("observations", [])}
    updated = 0
    for period, value in pibt_values.items():
        o = by_period.get(period)
        if not o:
            continue
        vals = list(o.get("values", []))
        while len(vals) < 12:
            vals.append(None)
        if vals[5] != value:
            vals[5] = value
            o["values"] = vals
            updated += 1
    if updated:
        changes.append(f"pibsec: nivel PIB copiado desde PIB.pibt ({updated} observaciones)")
    return changes


def compute_pibsec_variations(payload: dict) -> list[str]:
    """Completa qoq/yoy de PIBSEC a partir de niveles.

    Recalcula todas las variaciones trimestrales y anuales a partir de los
    niveles oficiales del BIE, salvo el periodo más reciente, donde prevalecen
    las cifras desestacionalizadas del boletín PIBT.
    """
    pibsec = payload["indicators"].get("PIBSEC")
    if not pibsec:
        return []
    obs = pibsec.get("observations", [])
    if not obs:
        return []
    last_period = pibsec.get("last_observation")
    def _official_range(period: str) -> bool:
        """Periodos con boletín PIBT descargado (2021 en adelante)."""
        ym = inegi.label_to_ym(period)
        if not ym:
            return False
        return ym >= "2021-01"
    # nivel_col -> (qoq_col, yoy_col)
    maps = {
        0: (8, 9),
        1: (10, 11),
        2: (3, 4),
        5: (6, 7),
    }
    updated = 0
    for i, o in enumerate(obs):
        vals = list(o.get("values", []))
        while len(vals) < 12:
            vals.append(None)
        # Conservar el boletín oficial en el periodo más reciente.
        is_last = (o.get("period") == last_period)
        for lvl_col, (qoq_col, yoy_col) in maps.items():
            cur = vals[lvl_col]
            if cur is None:
                continue
            use_official = is_last or _official_range(o.get("period", ""))
            if not use_official:
                if i > 0:
                    prev = obs[i - 1].get("values", [])
                    if lvl_col < len(prev) and prev[lvl_col] not in (None, 0):
                        vals[qoq_col] = round((cur - prev[lvl_col]) / abs(prev[lvl_col]), 6)
                        updated += 1
                if i >= 4:
                    yoy = obs[i - 4].get("values", [])
                    if lvl_col < len(yoy) and yoy[lvl_col] not in (None, 0):
                        vals[yoy_col] = round((cur - yoy[lvl_col]) / abs(yoy[lvl_col]), 6)
                        updated += 1
            else:
                # Conservar el boletín oficial; rellenar sólo vacíos.
                if i > 0:
                    prev = obs[i - 1].get("values", [])
                    if lvl_col < len(prev) and prev[lvl_col] not in (None, 0) and vals[qoq_col] is None:
                        vals[qoq_col] = round((cur - prev[lvl_col]) / abs(prev[lvl_col]), 6)
                        updated += 1
                if i >= 4:
                    yoy = obs[i - 4].get("values", [])
                    if lvl_col < len(yoy) and yoy[lvl_col] not in (None, 0) and vals[yoy_col] is None:
                        vals[yoy_col] = round((cur - yoy[lvl_col]) / abs(yoy[lvl_col]), 6)
                        updated += 1
        o["values"] = vals
    if updated:
        return [f"pibsec: variaciones calculadas desde niveles ({updated} celdas)"]
    return []


def prepare_igae_for_v3(payload: dict) -> list[str]:
    """Migra el indicador IGAE al esquema de 9 columnas antes de fusionar fuentes.

    El esquema anterior tenía 5 columnas: índice global, índices de actividades
    secundarias/terciarias y dos variaciones. El nuevo esquema separa los cuatro
    componentes (global + primarias + secundarias + terciarias) con su índice y
    su variación anual. Esta función reordena los valores antiguos y descarta las
    variaciones (se recalcularán o se obtendrán del boletín).
    """
    changes: list[str] = []
    ind = payload["indicators"].get("IGAE")
    if not ind:
        return changes

    # Tomar la definición de columnas del perfil V3.
    meta = json.loads(L.META_FILE.read_text(encoding="utf-8"))
    igae_prof = meta.get("profile", {}).get("IGAE", {})
    new_cols = igae_prof.get("columns")
    if not new_cols or len(new_cols) != 9:
        return changes

    old_cols = ind.get("columns", [])
    old_labels = [c.get("label", "") for c in old_cols]
    is_old_schema = (
        len(old_cols) == 5
        and "Índice de volumen físico" in old_labels[0]
        and "Act. Secundarias" in old_labels[1]
        and "Act. Terciarias" in old_labels[2]
    )

    if is_old_schema:
        new_obs = []
        for o in ind.get("observations", []):
            vals = list(o.get("values", []))
            nv = [None] * 9
            if len(vals) > 0:
                nv[0] = vals[0]  # IGAE global
            if len(vals) > 1:
                nv[5] = vals[1]  # act. secundarias
            if len(vals) > 2:
                nv[7] = vals[2]  # act. terciarias
            # Las variaciones antiguas (cols 3 y 4) se descartan.
            new_obs.append({"period": o["period"], "values": nv})
        ind["observations"] = new_obs
        changes.append(
            f"IGAE: migradas {len(new_obs)} observaciones del esquema antiguo de 5 columnas a 9"
        )

    ind["columns"] = new_cols
    if "windows" in igae_prof:
        ind["windows"] = igae_prof["windows"]

    # Normalizar la fuente principal al total del IGAE (columna 0 / serie 737121).
    # Esto corrige datos antiguos o ejecuciones offline donde no se consulta la API.
    if CONFIG.exists():
        try:
            series_cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
        except Exception:
            series_cfg = {}
        igae_specs = series_cfg.get("inegi", {}).get("IGAE", [])
        total_spec = next(
            (s for s in igae_specs if s.get("columna_objetivo") == 0), None
        )
        if total_spec:
            fuente = dict(ind.get("fuente", {}))
            fuente.setdefault("nombre", "INEGI")
            total_serie = str(total_spec.get("serie", ""))
            if total_serie and fuente.get("serie") != total_serie:
                fuente["serie"] = total_serie
            if total_spec.get("link") and fuente.get("link") != total_spec["link"]:
                fuente["link"] = total_spec["link"]
            fuente.setdefault("metodo", "INEGI BIE API")
            ind["fuente"] = fuente
            changes.append(f"IGAE: fuente normalizada a serie total {total_serie}")

    return changes



def prepare_imfbcf_for_v3(payload: dict) -> list[str]:
    """Migra el indicador IMFBCF al esquema de 40 columnas antes de fusionar fuentes.

    El esquema anterior tenía 2 columnas: índice y variación mensual. El nuevo esquema
    separa la inversión total y sus componentes (construcción, maquinaria y equipo,
    nacional, importado, etc.) con cifras desestacionalizadas, originales, variaciones
    mensuales, anuales y acumulados ene-mes. Las variaciones antiguas se conservan en
    los primeros slots y las demás se recalculan o se obtienen de los conectores.
    """
    changes: list[str] = []
    ind = payload["indicators"].get("IMFBCF")
    if not ind:
        return changes

    meta = json.loads(L.META_FILE.read_text(encoding="utf-8"))
    imfbcf_prof = (
        meta.get("profile", {}).get("IMFBCF", {})
        or meta.get("scaffolds", {}).get("IMFBCF", {})
    )
    new_cols = imfbcf_prof.get("columns")
    if not new_cols or len(new_cols) != 40:
        return changes

    old_cols = ind.get("columns", [])
    old_labels = [c.get("label", "") for c in old_cols]
    is_old_schema = (
        len(old_cols) == 2
        and "Índice (inversión)" in old_labels[0]
        and "Var. mensual" in old_labels[1]
    )

    if is_old_schema:
        new_obs = []
        for o in ind.get("observations", []):
            vals = list(o.get("values", []))
            nv = [None] * 40
            if len(vals) > 0:
                nv[0] = vals[0]  # índice total desest.
            if len(vals) > 1:
                nv[1] = vals[1]  # var. mensual total desest.
            new_obs.append({"period": o.get("period"), "values": nv})
        ind["observations"] = new_obs
        changes.append(
            f"IMFBCF: migradas {len(new_obs)} observaciones del esquema antiguo de 2 columnas a 40"
        )

    ind["columns"] = new_cols
    if "windows" in imfbcf_prof:
        ind["windows"] = imfbcf_prof["windows"]
    # Sincroniza metadatos del perfil V3 para IMFBCF.
    for field in ("nombre", "sigla", "descripcion", "frecuencia", "unidad",
                  "ajuste_estacional", "grupo", "publicacion", "fuente"):
        if imfbcf_prof.get(field) is not None and ind.get(field) != imfbcf_prof[field]:
            ind[field] = imfbcf_prof[field]
            changes.append(f"IMFBCF: actualizado {field}")
    return changes


def prepare_ioae_for_v3(payload: dict) -> list[str]:
    """Migra el indicador IOAE al esquema de 13 columnas y normaliza metadatos.

    Esquema anterior (4 columnas): 0=mensual, 1=anual, 2=inferior, 3=superior.
    Esquema nuevo (13 columnas): ver indicadores_meta.json.
    Las variaciones antiguas venían en formato pct-raw (2.7), por lo que se
    convierten a fracciones (0.027) para el nuevo esquema pct-frac.
    """
    changes: list[str] = []
    ind = payload["indicators"].get("IOAE")
    if not ind:
        return changes

    try:
        meta = json.loads(L.META_FILE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return changes
    ioae_prof = (
        meta.get("profile", {}).get("IOAE", {})
        or meta.get("scaffolds", {}).get("IOAE", {})
    )
    new_cols = ioae_prof.get("columns")
    if not new_cols or len(new_cols) != 13:
        return changes

    old_cols = ind.get("columns", [])
    old_labels = [c.get("label", "") for c in old_cols]
    is_old_schema = (
        len(old_cols) == 4
        and any("mensual" in l for l in old_labels)
        and any("anual" in l for l in old_labels)
    )

    if is_old_schema:
        new_obs = []
        for o in ind.get("observations", []):
            vals = list(o.get("values", []))
            nv = [None] * 13
            if len(vals) > 1 and vals[1] is not None:
                nv[0] = vals[1] / 100.0  # anual -> col 0
            if len(vals) > 2 and vals[2] is not None:
                nv[1] = vals[2] / 100.0  # inferior -> col 1
            if len(vals) > 3 and vals[3] is not None:
                nv[2] = vals[3] / 100.0  # superior -> col 2
            if len(vals) > 0 and vals[0] is not None:
                nv[3] = vals[0] / 100.0  # mensual -> col 3
            new_obs.append({"period": o.get("period"), "values": nv})
        ind["observations"] = new_obs
        changes.append(
            f"IOAE: migradas {len(new_obs)} observaciones del esquema antiguo de 4 columnas a 13"
        )

    # Asegurar observaciones con 13 valores.
    fixed = 0
    for o in ind.get("observations", []):
        vals = list(o.get("values", []))
        if len(vals) < 13:
            vals.extend([None] * (13 - len(vals)))
            o["values"] = vals
            fixed += 1
    if fixed:
        changes.append(f"IOAE: {fixed} observaciones ajustadas a 13 columnas")

    ind["columns"] = new_cols
    if "windows" in ioae_prof:
        ind["windows"] = ioae_prof["windows"]
    # Sincroniza metadatos del perfil V3.
    for field in ("nombre", "sigla", "descripcion", "frecuencia", "unidad",
                  "ajuste_estacional", "grupo", "publicacion", "fuente"):
        if ioae_prof.get(field) is not None and ind.get(field) != ioae_prof[field]:
            ind[field] = ioae_prof[field]
            changes.append(f"IOAE: actualizado {field}")
    return changes




def prepare_financiero_for_v3(payload: dict) -> list[str]:
    """Migra los indicadores del Entorno financiero a su frecuencia oficial.

    FIX (TIPOCAMBIO) y TASA pasan a ser series diarias; RESERVAS, semanal.
    Si el archivo local aún conserva agregaciones mensuales y las observaciones
    originales, intercambia la serie principal. También normaliza metadatos.
    """
    changes: list[str] = []
    try:
        meta = json.loads(L.META_FILE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return changes

    profile = {**(meta.get("profile") or {}), **(meta.get("scaffolds") or {})}
    cfg = {
        "TIPOCAMBIO": {"frecuencia": "Diaria", "fmt": "fx"},
        "TASA": {"frecuencia": "Diaria", "fmt": "pct-raw"},
        "RESERVAS": {"frecuencia": "Semanal", "fmt": "usd"},
    }

    for key, meta_cfg in cfg.items():
        ind = payload["indicators"].get(key)
        if not ind:
            continue

        prof = profile.get(key, {})
        original = ind.get("observations_original")
        current = ind.get("observations", [])

        # Detectar si la serie principal aún es mensual.
        current_is_monthly = current and not any(
            re.match(r"^\d{4}-\d{2}-\d{2}$", str(o.get("period", "")))
            for o in current
        )

        if original and current_is_monthly:
            ind["observations"] = list(original)
            changes.append(f"{key}: migradas observaciones originales a la serie principal")

        obs = ind.get("observations", [])
        if obs:
            last = obs[-1]
            last_period = last.get("period")
            if re.match(r"^\d{4}-\d{2}-\d{2}$", str(last_period)):
                ind["last_observation"] = last_period
                ind["fecha_ultima_observacion"] = last_period

        # Normalizar frecuencia y columnas desde el perfil si están disponibles.
        if prof.get("frecuencia"):
            ind["frecuencia"] = prof["frecuencia"]
        else:
            ind["frecuencia"] = meta_cfg["frecuencia"]

        if prof.get("columns"):
            ind["columns"] = prof["columns"]
        else:
            ind["columns"] = [{
                "label": prof.get("nombre") or ind.get("nombre") or key,
                "index": 0,
                "fmt": meta_cfg["fmt"],
            }]

        if prof.get("windows"):
            ind["windows"] = prof["windows"]

        for field in ("nombre", "descripcion", "unidad", "ajuste_estacional",
                      "grupo", "publicacion", "proximo", "fuente"):
            if prof.get(field) is not None and ind.get(field) != prof[field]:
                ind[field] = prof[field]
                changes.append(f"{key}: actualizado {field}")

    return changes

def compute_imai_metrics(payload: dict) -> list[str]:
    """Completa el esquema de 14 columnas del IMAI y calcula el acumulado original.

    Las columnas 6-13 llegan directamente del BIE a través de apply_inegi_total.
    La columna 5 (acumulado ene-mes original) se deriva de la columna 3 (índice
    original corregido por efectos del calendario) promediando enero-mes actual
    del año en curso y del año previo.
    """
    changes: list[str] = []
    ind = payload["indicators"].get("IMAI")
    if not ind:
        return changes
    obs = ind.get("observations")
    if not obs:
        return changes

    by_ym: dict[str, dict] = {}
    for o in obs:
        ym = inegi.label_to_ym(o.get("period", ""))
        if ym:
            by_ym[ym] = o

    updated = 0
    for o in obs:
        vals = list(o.get("values", []))
        while len(vals) < 14:
            vals.append(None)

        ym = inegi.label_to_ym(o.get("period", ""))
        if not ym:
            o["values"] = vals
            continue

        year, month = map(int, ym.split("-"))
        cur_sum = 0.0
        cur_n = 0
        prev_sum = 0.0
        prev_n = 0
        # Si ya existe un acumulado oficial (p. ej. del boletín de prensa), no
        # lo sobrescribe el cálculo aproximado desde los índices BIE.
        if vals[5] is None:
            for m in range(1, month + 1):
                cur_key = f"{year:04d}-{m:02d}"
                cur_o = by_ym.get(cur_key)
                if cur_o:
                    cur_vals = list(cur_o.get("values", []))
                    if len(cur_vals) > 3 and cur_vals[3] is not None:
                        cur_sum += float(cur_vals[3])
                        cur_n += 1
                prev_key = f"{year - 1:04d}-{m:02d}"
                prev_o = by_ym.get(prev_key)
                if prev_o:
                    prev_vals = list(prev_o.get("values", []))
                    if len(prev_vals) > 3 and prev_vals[3] is not None:
                        prev_sum += float(prev_vals[3])
                        prev_n += 1

            if cur_n > 0 and prev_n > 0 and prev_sum != 0:
                vals[5] = round((cur_sum / cur_n) / (prev_sum / prev_n) - 1, 6)
                updated += 1

        o["values"] = vals

    fuente = dict(ind.get("fuente", {}))
    fuente.setdefault("nombre", "INEGI")
    fuente["serie"] = "737233"
    fuente.setdefault("metodo", "INEGI BIE API")
    ind["fuente"] = fuente

    changes.append(f"IMAI: esquema de 14 columnas aplicado; acumulado calculado para {updated} periodos")
    return changes


def compute_emim_metrics(payload: dict) -> list[str]:
    """Asegura que el indicador EMIM use el esquema de 18 columnas.

    El esquema separa claramente:
      - cols 0-2, 5-7, 10-12: índices y variaciones originales del BIE.
      - cols 3-4, 8-9, 13-17: cifras desestacionalizadas y el índice de
        remuneraciones del boletín oficial.

    Si alguna observación llega con menos de 18 valores, se rellena con None
    para mantener el orden sin imputar datos.
    """
    changes: list[str] = []
    ind = payload["indicators"].get("EMIM")
    if not ind:
        return changes

    try:
        meta = json.loads(L.META_FILE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return changes

    emim_prof = meta.get("profile", {}).get("EMIM", {})
    new_cols = emim_prof.get("columns")
    if not new_cols or len(new_cols) != 18:
        return changes

    if len(ind.get("columns", [])) != 18:
        ind["columns"] = new_cols
        changes.append("EMIM: esquema de 18 columnas aplicado")

    fixed = 0
    for o in ind.get("observations", []):
        vals = list(o.get("values", []))
        if len(vals) < 18:
            vals.extend([None] * (18 - len(vals)))
            o["values"] = vals
            fixed += 1

    if fixed:
        changes.append(f"EMIM: {fixed} observaciones ajustadas a 18 columnas")

    # Normalizar subsectores: el parser conserva el detalle completo, pero el
    # frontend y las métricas esperan un dict plano {etiqueta: variación anual
    # original de la producción}. El detalle queda en subsectores_detalle.
    subsectores = ind.get("subsectores")
    if subsectores and isinstance(subsectores, dict):
        sample = next(iter(subsectores.values()), {})
        if isinstance(sample, dict):
            ind["subsectores_detalle"] = subsectores
            ind["subsectores"] = {
                f"{code} {info.get('nombre', '')}".strip(): info.get("produccion_anual")
                for code, info in subsectores.items()
                if isinstance(info, dict) and info.get("produccion_anual") is not None
            }
            changes.append(f"EMIM: {len(ind['subsectores'])} subsectores normalizados")

    return changes


def compute_igae_variations(payload: dict) -> list[str]:
    """Calcula las variaciones anuales originales para IGAE y sus componentes.

    Usa los índices de las columnas 0, 3, 5 y 7 y guarda el resultado en las
    columnas 2, 4, 6 y 8 respectivamente. La columna 1 (variación mensual
    desestacionalizada del boletín) se conserva intacta.
    """
    changes: list[str] = []
    ind = payload["indicators"].get("IGAE")
    if not ind:
        return changes
    obs = ind.get("observations")
    if not obs:
        return changes

    by_ym: dict[str, dict] = {}
    for o in obs:
        ym = inegi.label_to_ym(o.get("period", ""))
        if ym:
            by_ym[ym] = o

    src_to_dst = [(0, 2), (3, 4), (5, 6), (7, 8)]
    updated = 0
    for o in obs:
        ym = inegi.label_to_ym(o.get("period", ""))
        if not ym:
            continue
        prev_ym = inegi._ym_minus_months(ym, 12)
        if not prev_ym or prev_ym not in by_ym:
            continue
        prev_o = by_ym[prev_ym]

        vals = list(o.get("values", []))
        while len(vals) < 9:
            vals.append(None)
        prev_vals = list(prev_o.get("values", []))
        while len(prev_vals) < 9:
            prev_vals.append(None)

        for src, dst in src_to_dst:
            cur = vals[src]
            if cur is None:
                continue
            prev = prev_vals[src]
            if prev is None or prev == 0:
                continue
            vals[dst] = round((cur - prev) / abs(prev), 6)
            updated += 1

        o["values"] = vals

    if updated:
        changes.append(f"IGAE: variaciones anuales calculadas para {updated} celdas")
    else:
        changes.append("IGAE: sin variaciones anuales calculadas (datos insuficientes)")
    return changes


def apply_inegi_total(payload: dict, key: str, item: dict, prev_last: str | None) -> dict | None:
    """Fusiona una serie del INEGI sobre UNA columna del indicador existente.

    Actualiza sólo la columna objetivo (p. ej. el índice total del IGAE) con las
    observaciones oficiales de la API, conservando el resto de columnas/desgloses
    de respaldo. Agrega los periodos nuevos que la API tenga. Devuelve el registro
    de consulta para el update_log, o None si el indicador no existe en la capa de
    datos.
    """
    if item.get("pibt"):
        return apply_pibt_source(payload, key, item, prev_last)
    ind = payload["indicators"].get(key)
    if ind is None:
        return None

    tcol = item["target_column"]
    ncol = max(len(ind.get("columns") or []), tcol + 1)
    api_by_ym = {o["ym"]: o["value"] for o in item["api_total"]}

    # Para series trimestrales, la API de INEGI puede devolver observaciones con
    # TIME_PERIOD en cada mes del trimestre; las colapsamos al primer mes.
    is_quarter = str(item.get("freq")) == "4"

    def _key(ym: str) -> str:
        return _quarter_start(ym) if is_quarter else ym

    # Fusionar por ym (o primer mes del trimestre) para evitar duplicados.
    rows_by_ym: dict[str, dict] = {}
    for o in ind.get("observations", []):
        ym = inegi.label_to_ym(o.get("period", ""))
        if ym is None:
            continue
        ym_key = _key(ym)
        vals = list(o.get("values", []))
        while len(vals) < ncol:
            vals.append(None)
        row = {"period": o.get("period", ""), "values": vals}
        for mk in ("pub_date", "caracter"):
            if o.get(mk) is not None:
                row[mk] = o[mk]
        rows_by_ym[ym_key] = row

    # Actualizar la columna objetivo y agregar nuevos periodos.
    for o in item["api_total"]:
        if o.get("value") is None:
            continue
        ym_key = _key(o["ym"])
        period_label = o.get("period") or inegi.ym_to_label(ym_key, item.get("freq"))
        if ym_key in rows_by_ym:
            vals = rows_by_ym[ym_key]["values"]
            # Conserva la etiqueta de periodo más reciente/representativa.
            if period_label:
                rows_by_ym[ym_key]["period"] = period_label
        else:
            vals = [None] * ncol
            rows_by_ym[ym_key] = {"period": period_label, "values": vals}
        if 0 <= tcol < ncol:
            if isinstance(o.get("value"), str):
                vals[tcol] = o["value"]
            else:
                vals[tcol] = round(o["value"], 6)
            # Propagar metadatos por observación (p.ej. IOAE).
            for mk in ("pub_date", "caracter"):
                if o.get(mk) is not None:
                    rows_by_ym[ym_key][mk] = o[mk]

    rows = sorted(rows_by_ym.items(), key=lambda t: t[0])
    ind["observations"] = [o for _, o in rows]
    ind["last_observation"] = ind["observations"][-1]["period"]
    ind["last_updated"] = L.today_iso()
    ind["last_checked"] = L.today_iso()
    ind["source_origin"] = "api"
    fuente = dict(ind.get("fuente", {}))
    # La serie/link principales deben corresponder siempre al total del indicador
    # (columna objetivo 0); los componentes o boletines no los sobrescriben.
    is_bie = item.get("metodo") == "INEGI BIE API"
    if is_bie and (tcol == 0 or not fuente.get("serie")):
        fuente["serie"] = item["serie"]
    if is_bie and item.get("link") and (tcol == 0 or not fuente.get("link")):
        fuente["link"] = item["link"]
    if item.get("metodo"):
        fuente["metodo"] = item["metodo"]
    if item.get("link") and (
        "saladeprensa/boletines" in item["link"] or item.get("metodo") == "INEGI boletín PDF"
    ):
        ind["url_boletin_oficial"] = item["link"]
        # Conserva metadatos del boletín validado por el parser de Sala de Prensa.
        for meta_key in ("periodo_boletin", "numero_boletin", "fecha_publicacion",
                         "tipo_documento", "producto_boletin", "boletin_validado",
                         "proxima_publicacion", "sectores", "subsectores"):
            if item.get(meta_key) is not None:
                ind[meta_key] = item[meta_key]
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


def compute_bcmm_metrics(payload: dict) -> list[str]:
    """Construye el esquema de 29 columnas del BCMM y deriva saldo, variaciones anuales y acumulados."""
    changes: list[str] = []
    ind = payload["indicators"].get("BCMM")
    if not ind:
        return changes
    try:
        meta = json.loads(L.META_FILE.read_text(encoding="utf-8"))
    except Exception:
        return changes
    bcmm_prof = meta.get("profile", {}).get("BCMM", {})
    new_cols = bcmm_prof.get("columns")
    if not new_cols or len(new_cols) != 29:
        return changes
    if len(ind.get("columns", [])) != 29:
        ind["columns"] = new_cols
        changes.append("BCMM: esquema de 29 columnas aplicado")
    for o in ind.get("observations", []):
        vals = list(o.get("values", []))
        if len(vals) < 29:
            vals.extend([None] * (29 - len(vals)))
            o["values"] = vals
    by_ym: dict[str, dict] = {}
    for o in ind.get("observations", []):
        ym = inegi.label_to_ym(o.get("period", ""))
        if ym:
            by_ym[ym] = o
    yoy_map = {3: 0, 4: 1, 5: 2, 10: 6, 11: 7, 12: 8, 13: 9, 17: 14, 18: 15, 19: 16, 23: 20, 24: 21, 25: 22}
    yoy_updated = saldo_updated = acum_updated = 0
    for o in ind.get("observations", []):
        vals = list(o.get("values", []))
        if len(vals) < 29:
            continue
        ym = inegi.label_to_ym(o.get("period", ""))
        if not ym:
            continue
        if vals[0] is not None and vals[1] is not None:
            vals[2] = round(vals[0] - vals[1], 6)
            saldo_updated += 1
        prev_ym = inegi._ym_minus_months(ym, 12)
        prev_o = by_ym.get(prev_ym)
        if prev_o:
            prev_vals = list(prev_o.get("values", []))
            while len(prev_vals) < 29:
                prev_vals.append(None)
            for ycol, vcol in yoy_map.items():
                if vals[ycol] is None and vals[vcol] is not None and prev_vals[vcol] is not None:
                    d = round((vals[vcol] - prev_vals[vcol]) / abs(prev_vals[vcol]), 6)
                    if d is not None:
                        vals[ycol] = d
                        yoy_updated += 1
        year, month = map(int, ym.split("-"))
        acum = [None, None, None]
        can = True
        for m in range(1, month + 1):
            key = f"{year:04d}-{m:02d}"
            mo = by_ym.get(key)
            if not mo:
                can = False
                break
            mvals = list(mo.get("values", []))
            while len(mvals) < 29:
                mvals.append(None)
            for i, src in enumerate([0, 1, 2]):
                if mvals[src] is None:
                    can = False
                    break
                if acum[i] is None:
                    acum[i] = 0.0
                acum[i] += mvals[src]
            if not can:
                break
        if can:
            for i, dst in enumerate([26, 27, 28]):
                vals[dst] = round(acum[i], 6)
            acum_updated += 1
        o["values"] = vals
    if saldo_updated:
        changes.append(f"BCMM: saldo derivado para {saldo_updated} periodos")
    if yoy_updated:
        changes.append(f"BCMM: variaciones anuales calculadas para {yoy_updated} celdas")
    if acum_updated:
        changes.append(f"BCMM: acumulados ene-mes calculados para {acum_updated} periodos")
    fuente = dict(ind.get("fuente", {}))
    fuente.setdefault("nombre", "INEGI")
    fuente.setdefault("metodo", "INEGI BIE API")
    if not fuente.get("link"):
        fuente["link"] = "https://www.inegi.org.mx/datos/temas/comercio-exterior/"
    ind["fuente"] = fuente
    return changes


def compute_desocup_metrics(payload: dict) -> list[str]:
    """Ordena el esquema de 6 columnas del DESOCUP y mantiene población ocupada trimestral.

    Esquema:
      - 0: Tasa de desocupación (%).
      - 1: Tasa de participación (%).
      - 2: Tasa de informalidad laboral 1 (%).
      - 3: Tasa de subocupación (%).
      - 4: Población ocupada (millones de personas) — oficial trimestral.
      - 5: Población ocupada (personas) — oficial trimestral.

    NO deriva una serie mensual de población ocupada.
    """
    changes: list[str] = []
    ind = payload["indicators"].get("DESOCUP")
    if not ind:
        return changes

    try:
        meta = json.loads(L.META_FILE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return changes

    des_prof = meta.get("profile", {}).get("DESOCUP", {})
    new_cols = des_prof.get("columns")
    if not new_cols or len(new_cols) != 6:
        return changes

    if len(ind.get("columns", [])) != 6:
        ind["columns"] = new_cols
        changes.append("DESOCUP: esquema de 6 columnas aplicado")

    fixed = 0
    for o in ind.get("observations", []):
        vals = list(o.get("values", []))
        if len(vals) < 6:
            vals.extend([None] * (6 - len(vals)))
            o["values"] = vals
            fixed += 1

    if fixed:
        changes.append(f"DESOCUP: {fixed} observaciones ajustadas a 6 columnas")

    # Normaliza las tasas a puntos porcentuales (0-100): si el BIE las entrega
    # como fracciones (0.029) y todas son menores a 1, las multiplica por 100.
    # Si ya vienen como porcentaje (2.9), se conservan.
    norm_updated = 0
    for col in range(4):
        cvals = [o["values"][col] for o in ind.get("observations", []) if o["values"][col] is not None]
        if not cvals or max(cvals) > 1:
            continue
        for o in ind.get("observations", []):
            vals = list(o.get("values", []))
            if vals[col] is not None:
                vals[col] = round(vals[col] * 100, 6)
                o["values"] = vals
                norm_updated += 1

    if norm_updated:
        changes.append(f"DESOCUP: {norm_updated} observaciones normalizadas a puntos porcentuales")

    # Copia la población ocupada (personas) a millones y asegura etiquetas mensuales
    # en las observaciones que provienen de series mensuales, dejando los datos
    # trimestrales en el mes que les corresponde (inicio del trimestre).
    updated = 0
    q_updated = 0
    for o in ind.get("observations", []):
        vals = list(o.get("values", []))
        if vals[5] is not None:
            vals[4] = round(vals[5] / 1_000_000, 6)
            updated += 1
            ym = inegi.label_to_ym(o.get("period", ""))
            if ym:
                o["q_period"] = inegi.ym_to_label(ym, 4)
                q_updated += 1
        o["values"] = vals

    if updated:
        changes.append(f"DESOCUP: población ocupada en millones calculada para {updated} periodos")
    if q_updated:
        changes.append(f"DESOCUP: etiquetas trimestrales agregadas a {q_updated} observaciones")

    # La frecuencia del indicador sigue siendo mensual para las tasas; la población
    # ocupada se indica como trimestral en metadatos y ficha.
    ind["frecuencia"] = des_prof.get("frecuencia", "Mensual")
    ind["unidad"] = des_prof.get("unidad", "Porcentaje")
    ind["nombre"] = des_prof.get("nombre", "Indicadores de ocupación y empleo")
    ind["descripcion"] = des_prof.get(
        "descripcion",
        "Reúne los principales indicadores de la Encuesta Nacional de Ocupación y Empleo (ENOE).",
    )

    fuente = dict(ind.get("fuente", {}))
    fuente.setdefault("nombre", "INEGI")
    fuente.setdefault("metodo", "INEGI BIE API")
    if not fuente.get("link"):
        fuente["link"] = "https://www.inegi.org.mx/datos/temas/mercado-laboral/"
    fuente["serie"] = "444603, 444602, 444607, 444610, 446565"
    ind["fuente"] = fuente

    return changes


def compute_ioae_metrics(payload: dict) -> list[str]:
    """Completa el esquema de 13 columnas del IOAE y añade el IGAE observado.

    - Cols 0-9: nowcasts e intervalos de confianza al 95% (del boletín).
    - Col 10: fecha de publicación del boletín (string).
    - Col 11: carácter de la estimación (string).
    - Col 12: variación anual observada del IGAE (copia de IGAE col 2).
    """
    changes: list[str] = []
    ind = payload["indicators"].get("IOAE")
    if not ind:
        return changes

    try:
        meta = json.loads(L.META_FILE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return changes
    ioae_prof = meta.get("profile", {}).get("IOAE", {}) or meta.get("scaffolds", {}).get("IOAE", {})
    new_cols = ioae_prof.get("columns")
    if not new_cols or len(new_cols) != 13:
        return changes

    if len(ind.get("columns", [])) != 13:
        ind["columns"] = new_cols
        changes.append("IOAE: esquema de 13 columnas aplicado")

    fixed = 0
    for o in ind.get("observations", []):
        vals = list(o.get("values", []))
        if len(vals) < 13:
            vals.extend([None] * (13 - len(vals)))
            o["values"] = vals
            fixed += 1
    if fixed:
        changes.append(f"IOAE: {fixed} observaciones ajustadas a 13 columnas")

    # Copiar IGAE observado anual (col 2) al IOAE (col 12).
    igae = payload["indicators"].get("IGAE")
    if igae:
        igae_by_ym = {}
        for o in igae.get("observations", []):
            ym = inegi.label_to_ym(o.get("period", ""))
            if ym:
                igae_by_ym[ym] = o
        updated = 0
        for o in ind.get("observations", []):
            ym = inegi.label_to_ym(o.get("period", ""))
            if not ym:
                continue
            igae_o = igae_by_ym.get(ym)
            if not igae_o:
                continue
            igae_vals = list(igae_o.get("values", []))
            if len(igae_vals) > 2 and igae_vals[2] is not None:
                o["values"][12] = round(igae_vals[2], 6)
                updated += 1
        if updated:
            changes.append(f"IOAE: {updated} observaciones con IGAE observado anual")

    # Sincroniza metadatos del perfil V3.
    for field in ("nombre", "sigla", "descripcion", "frecuencia", "unidad",
                  "ajuste_estacional", "grupo", "publicacion", "fuente"):
        if ioae_prof.get(field) is not None and ind.get(field) != ioae_prof[field]:
            ind[field] = ioae_prof[field]
            changes.append(f"IOAE: actualizado {field}")

    return changes



def compute_emoe_metrics(payload: dict) -> list[str]:
    """Asegura que EMOE presente IGOEC en puntos, cambio mensual/anual en puntos
    y metadatos consistentes con el Indicador de Confianza Empresarial (ICE).
    """
    changes: list[str] = []
    ind = payload["indicators"].get("EMOE")
    if not ind or not ind.get("observations"):
        return changes
    obs = ind["observations"]

    # Normalizar a 7 columnas (padding a None).
    for o in obs:
        vals = list(o.get("values", []))
        while len(vals) < 7:
            vals.append(None)
        o["values"] = vals

    by_ym: dict[str, dict] = {}
    for o in obs:
        ym = inegi.label_to_ym(o.get("period", ""))
        if ym:
            by_ym[ym] = o

    updated = 0
    for o in obs:
        vals = list(o.get("values", []))
        cur = vals[0]
        if cur is None:
            continue
        ym = inegi.label_to_ym(o.get("period", ""))
        if ym:
            prev_m = inegi._ym_minus_months(ym, 1)
            if prev_m and prev_m in by_ym:
                prev_vals = by_ym[prev_m].get("values", [])
                prev = prev_vals[0] if len(prev_vals) > 0 else None
                if prev is not None and vals[1] is None:
                    vals[1] = round(cur - prev, 6)
                    updated += 1
            prev_y = inegi._ym_minus_months(ym, 12)
            if prev_y and prev_y in by_ym:
                prev_vals = by_ym[prev_y].get("values", [])
                prev = prev_vals[0] if len(prev_vals) > 0 else None
                if prev is not None and vals[2] is None:
                    vals[2] = round(cur - prev, 6)
                    updated += 1
        o["values"] = vals

    if updated:
        changes.append(f"EMOE: {updated} variaciones calculadas (puntos)")

    ind["nombre"] = "Encuesta Mensual de Opinión Empresarial"
    ind["nombre_corto"] = "EMOE"
    ind["descripcion"] = (
        "La EMOE genera indicadores mensuales de opinión y confianza empresarial para conocer oportunamente "
        "la percepción de directivos de los sectores manufacturero, construcción, comercio y servicios privados no financieros "
        "sobre la situación económica de sus empresas y del país."
    )
    ind["unidad"] = "Puntos"
    ind["umbral"] = 50
    ind["indicador_principal"] = "IGOEC"
    # Dejar url_boletin_oficial para el descubrimiento posterior del boletín ICE.
    ind["boletin_validado"] = False
    return changes


def compute_tasa_metrics(payload: dict) -> list[str]:
    """Construye policy_decisions y metadatos de regimen para la tasa objetivo."""
    changes: list[str] = []
    ind = payload["indicators"].get("TASA")
    if not ind or not ind.get("observations"):
        return changes
    obs = ind["observations"]
    cal = banxico_policy._load_calendar()
    events = banxico_policy._tasa_events(cal)
    decisions = banxico_policy.build_decisions(obs, events)
    if not decisions:
        return changes
    ind["policy_decisions"] = decisions
    ind["regimen"] = banxico_policy.regimen_from_observations(obs)
    ind["frecuencia"] = "Diaria"
    ind["frecuencia_naturaleza"] = "Cambios discretos por decision de politica monetaria"
    ind["nombre"] = "Objetivo para la Tasa de Interes Interbancaria a un dia"
    ind["descripcion"] = (
        "Tasa objetivo de politica monetaria fijada por la Junta de Gobierno de Banco de Mexico "
        "para las operaciones de fondeo interbancario a un dia. No confundir con la TIIE."
    )
    ind["nombre_corto"] = "Tasa objetivo de Banco de Mexico"
    cal_tasa = [e for e in (cal.get("events", []) if isinstance(cal, dict) else cal)
                if e.get("indicator") == "TASA" or e.get("sigla") == "TASA"]
    if cal_tasa:
        ind["calendario_publicaciones"] = cal_tasa
        changes.append(f"TASA: calendario de publicaciones con {len(cal_tasa)} eventos")
    latest = decisions[-1]
    last_adj = next(
        (d for d in reversed(decisions) if d.get("decision") in ("alza", "recorte")),
        None,
    )
    ind["tasa_vigente"] = latest.get("new_rate")
    ind["vigente_desde"] = last_adj.get("effective_date") if last_adj else latest.get("effective_date")
    ind["ultima_decision"] = latest.get("announcement_date")
    ind["ultimo_ajuste"] = last_adj
    ind["url_boletin_oficial"] = latest.get("comunicado_url") or ""
    ind["boletin_label"] = "Comunicado"
    changes.append(f"TASA: {len(decisions)} decisiones de politica monetaria construidas")
    changes.append(f"TASA: {len(ind['regimen'])} regímenes detectados")
    return changes


def run(offline: bool = False) -> int:
    log = {"started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "mode": "offline" if offline else "online",
           "network_calls": False,
           "warnings": [], "changes": [], "consultas": [], "critical": []}

    L.load_env()
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    payload = L.load_data()
    prev_obs = {k: v.get("last_observation") for k, v in payload.get("indicators", {}).items()}

    # Limpiar banderas de validación previas para permitir revalidar boletines
    # con el periodo actual en cada ejecución.
    for ind in payload.get("indicators", {}).values():
        ind.pop("boletin_validado", None)

    # Migrar IGAE al esquema de 9 columnas antes de fusionar fuentes.
    log["changes"].extend(prepare_igae_for_v3(payload))

    # Migrar IMFBCF al esquema de 40 columnas antes de fusionar fuentes.
    log["changes"].extend(prepare_imfbcf_for_v3(payload))

    # Migrar IOAE al esquema de 13 columnas antes de fusionar fuentes.
    log["changes"].extend(prepare_ioae_for_v3(payload))

    # Migrar Entorno financiero a frecuencias oficiales (diario/semanal).
    log["changes"].extend(prepare_financiero_for_v3(payload))

    if not offline:
        # Asegurar que los indicadores del perfil (incluyendo nuevos) existan
        # antes de consultar las fuentes; si faltan, se crean desde el perfil.
        log["changes"].extend(L.apply_profile(payload))

        # inegi_bulletin se ejecuta primero para evitar throttling del sitio de prensa
        # después de las llamadas masivas al BIE.
        for name, mod in (("banxico_sie", banxico_sie), ("inegi_bulletin", inegi_bulletin), ("banxico", banxico), ("inegi", inegi), ("inegi_inpc", inegi_inpc), ("inegi_inpp", inegi_inpp), ("ied", ied), ("worldbank", worldbank)):
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
                    if name in ("inegi", "inegi_bulletin", "inegi_inpc", "inegi_inpp", "banxico_sie"):
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

    # Nivel del PIB total en PIBSEC (desde el objeto 'pibt' del PIB).
    log["changes"].extend(sync_pibsec_pibt(payload))

    # Variaciones calculadas desde niveles para periodos sin boletín oficial.
    log["changes"].extend(compute_pibsec_variations(payload))

    # Variaciones anuales originales de IGAE (a partir de los índices BIE).
    log["changes"].extend(compute_igae_variations(payload))

    # IMAI V3: esquema de 14 columnas y acumulado original.
    log["changes"].extend(compute_imai_metrics(payload))

    # EMIM V2: esquema de 18 columnas con separación original/desestacionalizado.
    log["changes"].extend(compute_emim_metrics(payload))

    # BCMM: esquema de 29 columnas (totales, componentes, variaciones y acumulados).
    log["changes"].extend(compute_bcmm_metrics(payload))

    # DESOCUP: cuatro tasas laborales mensuales y población ocupada trimestral.
    log["changes"].extend(compute_desocup_metrics(payload))

    # IOAE: esquema de 13 columnas e IGAE observado para comparación.
    log["changes"].extend(compute_ioae_metrics(payload))

    # EMOE: IGOEC, cambios mensual/anual en puntos y metadatos de confianza.
    log["changes"].extend(compute_emoe_metrics(payload))

    # TASA: decisiones de política monetaria y metadatos de régimen.
    log["changes"].extend(compute_tasa_metrics(payload))

    # Frescura, calendario, métricas compartidas y metadatos temporales.
    log["changes"].extend(apply_freshness_and_meta(payload, log, offline=offline))

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


def apply_freshness_and_meta(payload: dict, log: dict, as_of: date | None = None, offline: bool = False) -> list[str]:
    """Aplica frescura (estados ACTUALIZADO/PENDIENTE/REZAGADO/ERROR), escribe el
    calendario, calcula métricas y actualiza metadatos temporales."""
    changes: list[str] = []
    if as_of is None:
        as_of = date.today()

    # Calendario oficial con la fecha de referencia del pipeline.
    cal = build_calendar.build(as_of=as_of, offline=offline)
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
        ind["url_fuente_oficial"] = ind.get("fuente", {}).get("link") or info.get("url_boletin")
        ind["url_boletin_oficial"] = ind.get("url_boletin_oficial") or info.get("url_boletin") or ind.get("fuente", {}).get("link")
        ind["fecha_publicacion"] = ind.get("fecha_publicacion") or info["fecha_publicacion_oficial"]

        # Descubrimiento automático del boletín oficial en el sitio de prensa del INEGI
        # cuando aún no se tiene una URL directa a un PDF de boletín.
        es_inegi = (ind.get("fuente", {}).get("nombre") or "").upper().startswith("INEGI")
        url_actual = ind.get("url_boletin_oficial") or ""
        if es_inegi and ("saladeprensa/boletines" not in url_actual or not ind.get("url_boletin_oficial") or not ind.get("boletin_validado")):
            try:
                desc = inegi_bulletin.discover_bulletin_url(key, ind.get("last_observation"))
                if desc:
                    ind["url_boletin_oficial"] = desc["url"]
                    if desc.get("fecha_publicacion"):
                        ind["fecha_publicacion"] = desc["fecha_publicacion"]
                    ind["periodo_boletin"] = desc.get("periodo")
                    ind["numero_boletin"] = desc.get("numero_boletin")
                    ind["tipo_documento"] = desc.get("tipo_documento")
                    ind["producto_boletin"] = desc.get("producto_boletin")
                    ind["boletin_validado"] = True
                    changes.append(f"boletín: {key} descubierto {desc['url']}")
            except Exception as e:  # noqa: BLE001
                log["warnings"].append(f"discover_bulletin {key}: {e}")
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