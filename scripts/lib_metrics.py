"""Motor de métricas determinista en Python.

Replica exactamente la lógica de assets/js/metrics.js y usa lib_format
(puerto de assets/js/format.js) para la presentación es-MX.

El módulo lee la configuración desde assets/js/config.js a través de
lib_kpicfg, lee data/indicadores.json y expone compute_all_metrics() para
que build_data.py, build_excel.py y build_notes.py compartan los mismos
números y textos que el dashboard.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any

import lib_format as F
from lib_kpicfg import get_cfg

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DATA_FILE = DATA_DIR / "indicadores.json"
METRICS_FILE = DATA_DIR / "metrics.json"

# Orden de compatibilidad con build_notes.py
__all__ = [
    "fmt_val",
    "primary_series",
    "compute_var",
    "annual_var",
    "compute_kpi",
    "analysis",
    "resumen",
    "prose_val",
    "per_long",
    "en_frase",
    "resp_frase",
    "is_trim",
    "period_to_date",
    "compute_all_metrics",
    "save_metrics",
    "load_metrics",
]

# Alias con mayúsculas/camelCase para quien prefiera el nombre original del JS
fmtVal = fmt_val = F.fmt_val
perLong = per_long = F.per_long
enFrase = en_frase = F.en_frase
respFrase = resp_frase = F.resp_frase
isTrim = is_trim = F.is_trim
periodToDate = period_to_date = F.period_to_date


def _kpicfg_and_colors():
    cfg = get_cfg()
    return cfg.get("KPICFG", {}), cfg.get("COLORS", {})


def prose_val(key: str, v: float | int | None) -> str:
    """proseVal equivalente."""
    if v is None:
        return "—"
    if key == "PIB":
        # El PIB oportuno publica variaciones, no nivel. Si el valor es una fracción,
        # se presenta como porcentaje; el nivel histórico se conserva como respaldo.
        if abs(v) < 1:
            return F._to_fixed(v * 100, 1, 1) + "%"
        return F._to_fixed(v / 1e6, 2, 2) + " billones de pesos de 2018"
    if key == "PIBSEC":
        return F._to_fixed(v / 1e6, 2, 2) + " billones de pesos"
    if key in ("IED", "BALANZA"):
        sign = "−" if v < 0 else ""
        return sign + "$" + F._to_fixed(abs(F._js_round(v)), 0, 0) + " millones de dólares"
    if key in ("IGAE", "IMAI", "CONSUMO", "EMIM"):
        return F._to_fixed(v, 1, 1) + " puntos"
    if key == "DESOCUP":
        return F._to_fixed(v * 100, 1, 1) + "%"
    if key in ("INPC", "TASA"):
        return F._to_fixed(v, 1, 1) + "%"
    if key == "TIPOCAMBIO":
        return "$" + F._to_fixed(v, 2, 2)
    return str(v)


def primary_series(ind: dict, cfg: dict) -> list[float | None]:
    """primarySeries equivalente."""
    obs = ind.get("observations", [])
    if cfg.get("derived") == "total":
        return [
            None if all(v is None for v in o["values"][:3]) else sum((v or 0) for v in o["values"][:3])
            for o in obs
        ]
    if cfg.get("derived") == "saldo":
        return [
            None if o["values"][0] is None or o["values"][1] is None else o["values"][0] - o["values"][1]
            for o in obs
        ]
    val_col = cfg.get("valCol", 0)
    return [o["values"][val_col] if val_col < len(o.get("values", [])) else None for o in obs]


def _val_at(ind: dict, i: int, col: int | None) -> float | None:
    if col is None or i < 0 or i >= len(ind.get("observations", [])):
        return None
    vals = ind["observations"][i].get("values", [])
    return vals[col] if col < len(vals) else None


def _var_val_fmt(mag: float | None, cfg: dict) -> str:
    """varValFmt equivalente (formato para análisis textual)."""
    if mag is None:
        return "—"
    s = "+" if mag > 0 else ""
    if cfg.get("varMode") == "abs-prev":
        return s + F._to_fixed(F._js_round(mag), 0, 0) + " mdd"
    if cfg.get("varMode") == "pp-prev":
        d = 1 if cfg.get("ppLong") else 2
        unit = " puntos porcentuales" if cfg.get("ppLong") else " pp"
        return s + F._to_fixed(mag, d, d) + unit
    # Si no hay varMode, respetar el formato numérico del valor.
    vfmt = cfg.get("varFmt") or cfg.get("valFmt")
    if vfmt == "num":
        return s + F._to_fixed(mag, 2, 2)
    if vfmt in ("pct-raw", "pct-frac"):
        return s + F._to_fixed(mag, 2, 2) + "%"
    return s + F._to_fixed(mag, 2, 2) + "%"


def compute_var(ind: dict, cfg: dict, vals: list, last_i: int, prev_i: int | None) -> dict[str, Any]:
    """computeVar equivalente."""
    var_col = cfg.get("varCol")
    if var_col is not None:
        raw = _val_at(ind, last_i, var_col)
        if raw is None:
            return {"mag": None, "text": "—", "pos": True, "label": cfg.get("varLabel")}
        mag = raw * 100 if cfg.get("varFmt") == "pct-frac" else raw
        text = ("+" if raw > 0 else "") + F.fmt_val(raw, cfg.get("varFmt"))
        return {"mag": mag, "text": text, "pos": raw >= 0, "label": cfg.get("varLabel")}

    cur = vals[last_i]
    lag = 4 if ind.get("frecuencia") == "Trimestral" else 12

    if cfg.get("varMode") == "pct-yoy":
        b = vals[last_i - lag] if last_i - lag >= 0 else None
        if cur is not None and b is not None and b != 0:
            d = (cur - b) / abs(b) * 100
            return {
                "mag": d,
                "text": ("+" if d >= 0 else "") + F._to_fixed(d, 1, 1) + "%",
                "pos": d >= 0,
                "label": cfg.get("varLabel"),
            }
        if prev_i is not None and vals[prev_i] is not None and vals[prev_i] != 0:
            d = (cur - vals[prev_i]) / abs(vals[prev_i]) * 100
            return {
                "mag": d,
                "text": ("+" if d >= 0 else "") + F._to_fixed(d, 1, 1) + "%",
                "pos": d >= 0,
                "label": "Variación vs. periodo previo",
            }
        return {"mag": None, "text": "—", "pos": True, "label": cfg.get("varLabel")}

    if cfg.get("varMode") == "pct-prev" and prev_i is not None and vals[prev_i] is not None and vals[prev_i] != 0:
        d = (cur - vals[prev_i]) / abs(vals[prev_i]) * 100
        return {
            "mag": d,
            "text": ("+" if d >= 0 else "") + F._to_fixed(d, 1, 1) + "%",
            "pos": d >= 0,
            "label": cfg.get("varLabel"),
        }

    if cfg.get("varMode") == "pp-prev" and prev_i is not None and vals[prev_i] is not None:
        d = cur - vals[prev_i]
        if cfg.get("valFmt") == "pct-frac":
            d *= 100
        unit = " puntos porcentuales" if cfg.get("ppLong") else " pp"
        return {
            "mag": d,
            "text": ("+" if d >= 0 else "") + F._to_fixed(d, 1, 1) + unit,
            "pos": d >= 0,
            "label": cfg.get("varLabel"),
        }

    if cfg.get("varMode") == "abs-prev" and prev_i is not None and vals[prev_i] is not None:
        d = cur - vals[prev_i]
        return {
            "mag": d,
            "text": ("+" if d >= 0 else "") + F._to_fixed(F._js_round(d), 0, 0) + " mdd",
            "pos": d >= 0,
            "label": cfg.get("varLabel"),
        }

    return {"mag": None, "text": "—", "pos": True, "label": cfg.get("varLabel")}


def compute_kpi(ind: dict, kpicfg: dict | None = None) -> dict[str, Any] | None:
    """computeKPI equivalente."""
    full_kpicfg, colors = _kpicfg_and_colors()
    kpicfg = kpicfg if kpicfg is not None else full_kpicfg
    cfg = kpicfg.get(ind["key"])
    if not cfg:
        return None

    periods = [o["period"] for o in ind.get("observations", [])]
    vals = primary_series(ind, cfg)
    idxs = [i for i, v in enumerate(vals) if v is not None]
    if not idxs:
        return None

    last_i = idxs[-1]
    prev_i = idxs[-2] if len(idxs) >= 2 else None
    ultimo = vals[last_i]
    var_info = compute_var(ind, cfg, vals, last_i, prev_i)

    max_i = max(idxs, key=lambda i: vals[i])
    min_i = min(idxs, key=lambda i: vals[i])

    assess = cfg.get("assess") or (
        "growth"
        if cfg.get("goodSign", 0) > 0
        else "unemployment"
        if cfg.get("goodSign", 0) < 0
        else "neutral"
    )
    mag = var_info["mag"]
    if mag is None:
        dir_ = "flat"
    elif mag > 0.05:
        dir_ = "up"
    elif mag < -0.05:
        dir_ = "down"
    else:
        dir_ = "flat"

    assessment = "neutral"
    if mag is not None and assess == "growth":
        assessment = "favorable" if dir_ == "up" else ("adverso" if dir_ == "down" else "neutral")
    elif mag is not None and assess == "unemployment":
        assessment = "favorable" if dir_ == "down" else ("adverso" if dir_ == "up" else "neutral")

    semaforo = (
        "bueno"
        if assessment == "favorable"
        else "malo"
        if assessment == "adverso"
        else ("neutral" if mag is None else "estable")
    )

    return {
        "assessment": assessment,
        "dir": dir_,
        "ultimoFmt": F.fmt_val(ultimo, cfg.get("valFmt")),
        "ultimoRaw": ultimo,
        "ultimoP": periods[last_i],
        "varText": var_info["text"],
        "varMag": var_info["mag"],
        "pos": var_info["pos"],
        "varColor": colors.get("GREEN") if var_info["pos"] else colors.get("CRIMSON"),
        "varLabel": var_info.get("label") or cfg.get("varLabel"),
        "maxFmt": F.fmt_val(vals[max_i], cfg.get("valFmt")),
        "maxRaw": vals[max_i],
        "maxP": periods[max_i],
        "minFmt": F.fmt_val(vals[min_i], cfg.get("valFmt")),
        "minRaw": vals[min_i],
        "minP": periods[min_i],
        "lastI": last_i,
        "series": vals,
        "periods": periods,
        "semaforo": semaforo,
    }


def _var_at(ind: dict, cfg: dict, vals: list, idx: int) -> float | None:
    """varAt equivalente."""
    if idx < 0:
        return None

    var_col = cfg.get("varCol")
    if var_col is not None:
        raw = _val_at(ind, idx, var_col)
        if raw is None:
            return None
        return raw * 100 if cfg.get("varFmt") == "pct-frac" else raw

    lag = 4 if ind.get("frecuencia") == "Trimestral" else 12
    a = vals[idx]

    if cfg.get("varMode") == "pct-yoy":
        b = vals[idx - lag] if idx - lag >= 0 else None
        if a is not None and b is not None and b != 0:
            return (a - b) / abs(b) * 100
        p = vals[idx - 1] if idx - 1 >= 0 else None
        if a is not None and p is not None and p != 0:
            return (a - p) / abs(p) * 100
        return None

    if cfg.get("varMode") == "pct-prev":
        b = vals[idx - 1] if idx - 1 >= 0 else None
        if a is not None and b is not None and b != 0:
            return (a - b) / abs(b) * 100
        return None

    if cfg.get("varMode") == "pp-prev":
        b = vals[idx - 1] if idx - 1 >= 0 else None
        if a is not None and b is not None:
            d = a - b
            if cfg.get("valFmt") == "pct-frac":
                d *= 100
            return d
        return None

    if cfg.get("varMode") == "abs-prev":
        b = vals[idx - 1] if idx - 1 >= 0 else None
        if a is not None and b is not None:
            return a - b
        return None

    return None


def annual_var(ind: dict, kpi: dict, kpicfg: dict | None = None) -> dict[str, Any] | None:
    """annualVar equivalente."""
    kpicfg = _kpicfg_and_colors()[0] if kpicfg is None else kpicfg
    cfg = kpicfg.get(ind["key"])
    if not cfg or not kpi:
        return None

    if cfg.get("yoyCol") is not None:
        raw = _val_at(ind, kpi["lastI"], cfg["yoyCol"])
        if raw is None:
            return None
        mag = raw * 100 if cfg.get("yoyFmt") == "pct-frac" else raw
        return {
            "mag": mag,
            "pos": raw >= 0,
            "text": ("+" if raw > 0 else "") + F.fmt_val(raw, cfg.get("yoyFmt")),
            "label": cfg.get("yoyLabel", "Var. anual"),
        }

    if ind["key"] in ("INPC", "TASA", "DESOCUP", "IED", "BALANZA"):
        return None

    vals = kpi["series"]
    lag = 4 if ind.get("frecuencia") == "Trimestral" else 12
    last_i = kpi["lastI"]
    cur = vals[last_i]
    base = vals[last_i - lag] if last_i - lag >= 0 else None
    if cur is None or base is None or base == 0:
        return None
    d = (cur - base) / abs(base) * 100
    return {
        "mag": d,
        "pos": d >= 0,
        "text": ("+" if d >= 0 else "") + F._to_fixed(d, 1, 1) + "%",
        "label": "Var. anual",
    }


def analysis(ind: dict, kpi: dict, kpicfg: dict | None = None) -> list[str]:
    """analysis equivalente: bullets de análisis deterministas."""
    if not kpi:
        return []
    kpicfg = _kpicfg_and_colors()[0] if kpicfg is None else kpicfg
    cfg = kpicfg.get(ind["key"])
    if not cfg:
        return []

    key = ind["key"]
    valid = [v for v in kpi["series"] if v is not None]
    if not valid:
        return []
    promedio = sum(valid) / len(valid)
    cur_var = kpi["varMag"]
    prev_var = _var_at(ind, cfg, kpi["series"], kpi["lastI"] - 1)
    prev_p = kpi["periods"][kpi["lastI"] - 1]
    a_mag = abs(cur_var or 0)
    g = cfg.get("vg", "m")

    if cfg.get("grupo") in ("balanza", "inpc", "desoc", "fx", "tasa"):
        mag_adj = ""
    elif a_mag < 0.5:
        mag_adj = "marginal"
    elif a_mag < 1.5:
        mag_adj = "moderado" if g == "m" else "moderada"
    elif a_mag < 4:
        mag_adj = "sólido" if g == "m" else "sólida"
    else:
        mag_adj = "elevado" if g == "m" else "elevada"

    ORIG = ("PIB", "PIBSEC", "IGAE", "IMAI", "CONSUMO", "EMIM")
    big = abs(cur_var - prev_var) if (cur_var is not None and prev_var is not None) else a_mag

    trend = ""
    if cfg.get("grupo") == "growth":
        if cur_var is not None and cur_var < 0:
            trend = ("una marcada" if a_mag >= 1 else "una") + " contracción"
        elif prev_var is not None and cur_var is not None and cur_var < prev_var - 0.05:
            trend = ("una marcada" if big >= 1 else "una ligera") + " desaceleración"
        elif prev_var is not None and cur_var is not None and cur_var > prev_var + 0.05:
            trend = ("una marcada" if big >= 1 else "una ligera") + " aceleración"
        else:
            trend = "un ritmo de expansión estable"
    elif cfg.get("grupo") == "desoc":
        if cur_var is not None and cur_var > 0.001:
            trend = ("un marcado" if a_mag >= 0.3 else "un ligero") + " repunte del desempleo"
        elif cur_var is not None and cur_var < -0.001:
            trend = ("un marcado" if a_mag >= 0.3 else "un ligero") + " descenso del desempleo"
        else:
            trend = "estabilidad en el mercado laboral"
    elif cfg.get("grupo") == "inpc":
        if cur_var is not None and cur_var > 0.001:
            trend = ("un marcado" if a_mag >= 0.3 else "un ligero") + " repunte inflacionario"
        elif cur_var is not None and cur_var < -0.001:
            trend = ("una marcada" if a_mag >= 0.3 else "una ligera") + " moderación de la inflación"
        else:
            trend = "estabilidad en los precios"
    elif cfg.get("grupo") == "balanza":
        if cur_var is not None and cur_var > 0:
            trend = "una mejora del saldo comercial"
        elif cur_var is not None and cur_var < 0:
            trend = "un deterioro del saldo comercial"
        else:
            trend = "un saldo prácticamente estable"
    elif cfg.get("grupo") == "fx":
        if cur_var is not None and cur_var > 0.05:
            trend = "una depreciación del peso"
        elif cur_var is not None and cur_var < -0.05:
            trend = "una apreciación del peso"
        else:
            trend = "estabilidad cambiaria"
    elif cfg.get("grupo") == "tasa":
        if cur_var is not None and cur_var > 0.001:
            trend = "un alza en la tasa de referencia"
        elif cur_var is not None and cur_var < -0.001:
            trend = "un recorte en la tasa de referencia"
        else:
            trend = "una tasa de referencia sin cambios"

    same_round = prose_val(key, kpi["ultimoRaw"]) == prose_val(key, promedio)
    avg_phrase = (
        "en línea con el promedio del periodo mostrado"
        if same_round
        else ("por encima" if kpi["ultimoRaw"] > promedio else "por debajo")
        + " del promedio del periodo mostrado"
    )
    art = "un" if cfg.get("vg") == "m" else "una"

    if prev_var is not None and cfg.get("grupo") != "balanza":
        prev_clause = f" respecto {resp_frase(prev_p)} ({_var_val_fmt(prev_var, cfg)})"
    elif prev_var is not None:
        prev_clause = f" respecto {resp_frase(prev_p)}"
    else:
        prev_clause = ""

    skel_mag_adj = "" if (cfg.get("grupo") == "growth" and key in ORIG) else mag_adj
    mag_adj_fragment = f" {skel_mag_adj}" if skel_mag_adj else ""

    b1 = (
        f"En {en_frase(kpi['ultimoP'])}, {cfg.get('art')} {cfg.get('noun')} "
        f"se ubicó en {prose_val(key, kpi['ultimoRaw'])}{cfg.get('ctx', '')}, "
        f"con {art} {cfg.get('vw')}{mag_adj_fragment} "
        f"de {_var_val_fmt(cur_var, cfg)} {cfg.get('comp', '')}."
    )

    if cfg.get("grupo") == "growth" and key in ORIG:
        if ind.get("frecuencia") == "Trimestral":
            label = (
                "crecimiento anual"
                if "anual" in cfg.get("varLabel", "").lower()
                else "variación trimestral"
            )
            read = f"El {label} fue {mag_adj or 'marginal'}. La comparación entre trimestres debe considerar el comportamiento estacional de la serie original."
        else:
            if cur_var is None:
                verb = "se mantuvo sin cambio"
            elif cur_var > 0.05:
                verb = "aumentó"
            elif cur_var < -0.05:
                verb = "disminuyó"
            else:
                verb = "se mantuvo prácticamente sin cambio"
            read = (
                f"La variación mensual publicada por el INEGI muestra que el indicador {verb} "
                "respecto del mes previo. El nivel mostrado es la serie original; "
                "la variación mensual se calcula sobre cifras desestacionalizadas."
            )
    elif cfg.get("grupo") == "inpc":
        if cur_var is None:
            verb = "se mantuvo"
        elif cur_var > 0.001:
            verb = "aumentó"
        elif cur_var < -0.001:
            verb = "disminuyó"
        else:
            verb = "no cambió"
        read = f"La inflación anual {verb} respecto del mes previo. Se ubicó {avg_phrase} ({prose_val(key, promedio)})."
    else:
        read = f"Este resultado refleja {trend}{prev_clause}, y deja al indicador {avg_phrase} de {prose_val(key, promedio)}."

    b1 += " " + read

    tail = valid[-4:]
    direccion = "lateral"
    if len(tail) >= 2:
        ch = tail[-1] - tail[0]
        rel = abs(ch) / (abs(tail[0]) or 1)
        if rel >= 0.01:
            direccion = "ascendente" if ch > 0 else "descendente"

    pos_avg = (
        "por encima del promedio del periodo mostrado"
        if kpi["ultimoRaw"] > promedio
        else (
            "por debajo del promedio del periodo mostrado"
            if kpi["ultimoRaw"] < promedio
            else "en línea con el promedio del periodo mostrado"
        )
    )

    if kpi["ultimoRaw"] == kpi["maxRaw"]:
        extremo = " y fue el registro más alto de la serie mostrada"
    elif kpi["ultimoRaw"] == kpi["minRaw"]:
        extremo = " y fue el registro más bajo de la serie mostrada"
    else:
        extremo = ""

    if len(tail) >= 2:
        if direccion == "lateral":
            cmp = " El último dato se mantuvo cercano al del inicio del periodo mostrado."
        elif direccion == "ascendente":
            cmp = " El último dato fue superior al del inicio del periodo mostrado."
        else:
            cmp = " El último dato fue inferior al del inicio del periodo mostrado."
    else:
        cmp = ""

    b2 = (
        f"A lo largo de la serie mostrada, el indicador osciló entre un máximo de "
        f"{prose_val(key, kpi['maxRaw'])} ({per_long(kpi['maxP'])}) y un mínimo de "
        f"{prose_val(key, kpi['minRaw'])} ({per_long(kpi['minP'])}). "
        f"El resultado más reciente se ubicó {pos_avg}{extremo}.{cmp}"
    )
    if key in ORIG and direccion != "lateral":
        b2 += " Esta comparación se realiza sobre la serie original, que incorpora efectos estacionales."

    extra = ""
    if key == "INPC":
        lvl = kpi["ultimoRaw"]
        if lvl > 4:
            extra = (
                " En este nivel, la inflación se mantiene por encima del límite superior del "
                "objetivo del Banco de México (3 % ±1 punto), lo que limita el margen para "
                "relajar la política monetaria."
            )
        elif lvl >= 2:
            extra = (
                " Con ello, la inflación se mantiene dentro del intervalo de variabilidad del "
                "Banco de México (3 % ±1 punto), aunque todavía por encima de la meta puntual de 3 %."
            )
        else:
            extra = " Este nivel se sitúa por debajo de la meta de 3 % del Banco de México."
    elif key == "IED":
        v = ind["observations"][kpi["lastI"]].get("values", [])
        comps = [
            ["nuevas inversiones", v[1] if len(v) > 1 else None],
            ["reinversión de utilidades", v[2] if len(v) > 2 else None],
            ["cuentas entre compañías", v[3] if len(v) > 3 else None],
        ]
        comps = [c for c in comps if c[1] is not None]
        comps.sort(key=lambda c: c[1], reverse=True)
        if comps:
            dom = comps[0]
            share = F._js_round(dom[1] / kpi["ultimoRaw"] * 100) if kpi["ultimoRaw"] else 0
            if dom[0] == "reinversión de utilidades":
                rest = "refleja sobre todo la permanencia de capital ya instalado más que la llegada de proyectos nuevos"
            else:
                rest = "apunta a la captación de capital fresco"
            extra = (
                f" En su composición, el rubro predominante fue {dom[0]} "
                f"(≈{share}% del total), lo que {rest}."
            )
    elif key == "BALANZA":
        sup = kpi["ultimoRaw"] >= 0
        extra = (
            f" El saldo del último mes corresponde a un "
            f"{'superávit comercial, con exportaciones por encima de las importaciones' if sup else 'déficit comercial, con importaciones por encima de las exportaciones'}."
        )
    elif key == "DESOCUP":
        extra = (
            " La tasa se mantiene en niveles históricamente bajos para la economía mexicana. "
            "Su lectura debe acompañarse de la población ocupada y de las condiciones de informalidad, "
            "que la tasa de desocupación por sí sola no captura."
        )

    return [b1, b2 + extra]


def resumen(ind: dict, kpi: dict, yoy: dict | None, kpicfg: dict | None = None) -> list[str]:
    """Resumen ejecutivo de 3-4 bullets para la ficha y la nota."""
    if not kpi:
        return []
    if kpicfg is None:
        kpicfg, _ = _kpicfg_and_colors()
    cfg = kpicfg.get(ind["key"], {})
    bullets = []
    ctx = (cfg.get("ctx") or "").strip(" \t()")
    ctx_text = f" ({ctx})" if ctx else ""
    bullets.append(
        f"En {F.per_long(kpi['ultimoP'])}, {cfg.get('art', 'el')} {cfg.get('noun', ind.get('nombre'))} "
        f"se ubicó en {prose_val(ind['key'], kpi['ultimoRaw'])}{ctx_text}. "
        f"El valor de {kpi['varLabel'].lower()} fue de {kpi['varText']} {cfg.get('comp', '')}."
    )
    if yoy:
        label = yoy.get("label", "variación anual").lower()
        bullets.append(f"La {label} se situó en {yoy['text']}, lo que refleja la comparación contra {F.per_long(kpi['ultimoP'])} del año previo.")
    if kpi["ultimoRaw"] == kpi["maxRaw"]:
        rango_pos = "coincide con el máximo de la serie mostrada."
    elif kpi["ultimoRaw"] == kpi["minRaw"]:
        rango_pos = "coincide con el mínimo de la serie mostrada."
    else:
        rango_pos = "se ubica dentro del rango observado en el periodo mostrado."
    bullets.append(
        f"En la serie mostrada, el indicador oscila entre un máximo de {prose_val(ind['key'], kpi['maxRaw'])} "
        f"({F.per_long(kpi['maxP'])}) y un mínimo de {prose_val(ind['key'], kpi['minRaw'])} ({F.per_long(kpi['minP'])}). "
        f"El último dato {rango_pos}"
    )
    if kpi["assessment"] == "favorable":
        bullets.append("La variación se clasifica como favorable según la lectura económica del indicador.")
    elif kpi["assessment"] == "adverso":
        bullets.append("La variación se clasifica como adversa según la lectura económica del indicador.")
    else:
        bullets.append("La variación no tiene una clasificación clara de favorable/adversa sin contexto adicional.")
    return bullets


def _eopibt_metrics(ind: dict, kpicfg: dict) -> dict[str, Any] | None:
    """KPI y resumen específico para el PIB oportuno (EOPIBT).

    El PIB oportuno publica variaciones, no nivel. Se exponen cuatro KPIs:
    variación trimestral, anual desestacionalizada, anual original y acumulado,
    junto con un resumen ejecutivo que evita repetir las mismas cifras.
    """
    cfg = kpicfg.get(ind["key"])
    if not cfg:
        return None
    kpi = compute_kpi(ind, kpicfg)
    if not kpi:
        return None
    yoy = annual_var(ind, kpi, kpicfg)
    obs = ind.get("observations", [])
    if not obs:
        return None
    last_i = kpi["lastI"]
    prev_i = kpi["lastI"] - 1 if kpi["lastI"] > 0 else None

    qoq = _val_at(ind, last_i, 0)
    yoy_desest = _val_at(ind, last_i, 1)
    yoy_orig = _val_at(ind, last_i, 2)
    ytd = _val_at(ind, last_i, 3)
    prev_qoq = _val_at(ind, prev_i, 0) if prev_i is not None else None
    prev_yoy_desest = _val_at(ind, prev_i, 1) if prev_i is not None else None

    def _pct(v):
        if v is None:
            return "—"
        s = "+" if v > 0 else ""
        return s + F.fmt_val(v, "pct-frac")

    def _delta(v, prev):
        if v is None or prev is None:
            return None
        return v - prev

    def _delta_text(v, prev):
        d = _delta(v, prev)
        if d is None:
            return None
        if d > 0:
            return f"aceleró {d * 100:.1f} p.p."
        if d < 0:
            return f"desaceleró {-d * 100:.1f} p.p."
        return "se mantuvo sin cambio"

    # Campos amigables para el frontend.
    kpi["qoqRaw"] = qoq
    kpi["qoqText"] = _pct(qoq)
    kpi["qoqLabel"] = "Var. trimestral"
    kpi["yoyDesestRaw"] = yoy_desest
    kpi["yoyDesestText"] = _pct(yoy_desest)
    kpi["yoyDesestLabel"] = "Var. anual desest."
    kpi["yoyOrigRaw"] = yoy_orig
    kpi["yoyOrigText"] = _pct(yoy_orig)
    kpi["yoyOrigLabel"] = "Var. anual original"
    kpi["ytdRaw"] = ytd
    kpi["ytdText"] = _pct(ytd)
    kpi["ytdLabel"] = "Acumulado"

    # Usar variación trimestral como "cifra actual" en tarjetas y matriz.
    kpi["ultimoFmt"] = kpi["qoqText"]
    kpi["varText"] = kpi["yoyDesestText"]
    kpi["varLabel"] = kpi["yoyDesestLabel"]
    if yoy:
        kpi["yoyText"] = kpi["yoyOrigText"]
        kpi["yoyLabel"] = kpi["yoyOrigLabel"]

    per = kpi["ultimoP"] or ""
    m = re.match(r"(\d)T-(\d{2})", per)
    if m:
        q = int(m.group(1))
        year = 2000 + int(m.group(2))
        same_q_prev_year = f"{q}T-{year - 1 - 2000:02d}"
        prev_q_num = q - 1 if q > 1 else 4
        prev_q_year = year if q > 1 else year - 1
        prev_q = f"{prev_q_num}T-{prev_q_year - 2000:02d}"
        ytd_labels = {
            1: "Acumulado enero–marzo",
            2: "Acumulado enero–junio",
            3: "Acumulado enero–septiembre",
            4: "Acumulado enero–diciembre",
        }
        kpi["ytdLabel"] = ytd_labels.get(q, "Acumulado")
    else:
        prev_q = None
        same_q_prev_year = None

    def _trend_verb(v):
        if v is None:
            return "registró"
        if v > 0:
            return "creció"
        if v < 0:
            return "disminuyó"
        return "se mantuvo sin cambio"

    # Resumen ejecutivo (máximo 4 bullets), sin frases genéricas ni próxima publicación.
    bullets = []
    per_long = F.per_long(per)
    prev_q_long = F.per_long(prev_q) if prev_q else "el trimestre previo"
    same_q_long = F.per_long(same_q_prev_year) if same_q_prev_year else "el mismo trimestre del año previo"

    # 1. Aceleración trimestral.
    if qoq is not None:
        b1 = f"En {per_long}, el PIB oportuno {_trend_verb(qoq)} {kpi['qoqText']} respecto a {prev_q_long}"
        if prev_qoq is not None:
            b1 += f"; {_delta_text(qoq, prev_qoq)} respecto al trimestre previo"
        b1 += "."
        bullets.append(b1)

    # 2. Crecimiento anual.
    if yoy_desest is not None:
        b2 = f"La variación anual desestacionalizada fue {kpi['yoyDesestText']}"
        if yoy_orig is not None:
            b2 += f" y la anual original {kpi['yoyOrigText']}"
        b2 += f" respecto a {same_q_long}."
        bullets.append(b2)

    # 3. Avance generalizado.
    sectores = ind.get("sectores")
    if sectores and qoq is not None:
        parts = []
        for name in ("primarias", "secundarias", "terciarias"):
            if name in sectores:
                parts.append(f"{name} {_pct(sectores[name].get('qoq'))}")
        if parts:
            qoq_vals = [sectores[n].get("qoq") for n in ("primarias", "secundarias", "terciarias") if n in sectores]
            all_grew = all(v is not None and v > 0 for v in qoq_vals)
            if all_grew:
                bullets.append(f"Avance generalizado: las tres grandes actividades crecieron — {', '.join(parts)}.")
            else:
                bullets.append(f"El avance por actividad fue mixto — {', '.join(parts)}.")

    # 4. Balance acumulado.
    if ytd is not None and same_q_prev_year:
        bullets.append(f"El {kpi['ytdLabel'].lower()} de {year} {_trend_verb(ytd)} {kpi['ytdText']} frente al mismo periodo de {year - 1}.")

    return {
        "kpi": kpi,
        "yoy": yoy,
        "annualVar": yoy,
        "resumen": bullets[:4],
        "analysis": bullets[:1],
    }


def _pibsec_metrics(ind: dict, kpicfg: dict) -> dict[str, Any] | None:
    """KPI y resumen específico para PIB por actividades económicas (PIBSEC).

    Expone el nivel del PIB total y las variaciones trimestrales/anuales del
    PIB y de cada gran actividad, evitando mostrar máximos/mínimos como KPIs.
    """
    cfg = kpicfg.get(ind["key"])
    if not cfg:
        return None
    kpi = compute_kpi(ind, kpicfg)
    if not kpi:
        return None
    yoy = annual_var(ind, kpi, kpicfg)
    obs = ind.get("observations", [])
    if not obs:
        return None
    last_i = kpi["lastI"]

    def _pct(v):
        if v is None:
            return "—"
        s = "+" if v > 0 else ""
        return s + F.fmt_val(v, "pct-frac")

    def _nivel(v):
        if v is None:
            return "—"
        return F.fmt_val(v, "bill")

    col_cards = [
        ("PIB total", 5, 6, 7),
        ("Actividades primarias", 0, 8, 9),
        ("Actividades secundarias", 1, 10, 11),
        ("Actividades terciarias", 2, 3, 4),
    ]
    cards = []
    for name, nivel_col, qoq_col, yoy_col in col_cards:
        nivel = _val_at(ind, last_i, nivel_col)
        qoq = _val_at(ind, last_i, qoq_col)
        y = _val_at(ind, last_i, yoy_col)
        short = "PIB" if name == "PIB total" else name.split()[-1]
        cards.append({
            "name": short,
            "full": name,
            "nivelRaw": nivel,
            "nivelText": _nivel(nivel),
            "qoqRaw": qoq,
            "qoqText": _pct(qoq),
            "yoyRaw": y,
            "yoyText": _pct(y),
        })

    pib_card = cards[0]
    per = kpi["ultimoP"]
    per_long = F.per_long(per)

    # Resumen ejecutivo (máximo 4 bullets).
    bullets = []
    bullets.append(
        f"En {per_long}, el {ind.get('nombre')} se ubicó en {pib_card['nivelText']}. "
        f"La variación trimestral fue {pib_card['qoqText']} y la anual {pib_card['yoyText']} "
        "frente al mismo trimestre del año previo."
    )

    qoq_parts = [
        f"{c['name']} {c['qoqText']}" for c in cards[1:] if c['qoqRaw'] is not None
    ]
    if qoq_parts:
        bullets.append(
            f"El desempeño por actividad a tasa trimestral fue: {', '.join(qoq_parts)}."
        )

    yoy_parts = [
        f"{c['name']} {c['yoyText']}" for c in cards[1:] if c['yoyRaw'] is not None
    ]
    if yoy_parts:
        # Si hay contracciones, el verbo se adapta.
        verbs = ["contrajo" if c['yoyRaw'] and c['yoyRaw'] < 0 else "creció" for c in cards[1:]]
        # Frase: "Las actividades terciarias crecieron..., las primarias... y las secundarias contrajeron..."
        parts = []
        for c in cards[1:]:
            if c['yoyRaw'] is None:
                continue
            verb = "contrajo" if c['yoyRaw'] < 0 else "creció"
            parts.append(f"{c['name']} {verb} {c['yoyText']}")
        if parts:
            bullets.append(
                "A tasa anual, " + ", ".join(parts[:-1]) +
                (f" y {parts[-1]}" if len(parts) > 1 else parts[0]) + "."
            )

    subsectores = ind.get("subsectores") or {}
    # Filtra agregados (PIB y las 3 grandes actividades) y toma los 14 sectores.
    sectores = {
        k: v for k, v in subsectores.items()
        if not k.lower().startswith("pib") and "actividades" not in k.lower()
    }
    if sectores:
        top = sorted(sectores.items(), key=lambda x: x[1], reverse=True)[:3]
        bottom = sorted(sectores.items(), key=lambda x: x[1])[:3]

        def _short_sector(label):
            # Quita código numérico inicial y toma el primer fragmento.
            s = re.sub(r"^[\d\-]+\s+", "", label)
            s = s.split(",")[0].split(" y ")[0]
            # Limita longitud sin romper palabras.
            words = s.split()
            if len(words) > 8:
                s = " ".join(words[:8]) + "..."
            return s.strip()

        top_txt = ", ".join(f"{_short_sector(k)} ({_pct(v)})" for k, v in top)
        bot_txt = ", ".join(f"{_short_sector(k)} ({_pct(v)})" for k, v in bottom)
        bullets.append(
            f"A nivel subsectorial, los mayores dinamismos anuales fueron {top_txt}; "
            f"los mayores retrocesos: {bot_txt}."
        )

    kpi["cards"] = cards
    if yoy:
        kpi["yoyText"] = yoy["text"]
        kpi["yoyLabel"] = yoy["label"]
    return {
        "kpi": kpi,
        "yoy": yoy,
        "annualVar": yoy,
        "resumen": bullets[:4],
        "analysis": bullets[:1],
    }


def _igae_metrics(ind: dict, kpicfg: dict) -> dict[str, Any] | None:
    """KPI y resumen para IGAE con el esquema V3 de 9 columnas.

    El esquema V3 tiene:
      - col 0: IGAE (índice)
      - col 1: Var. mensual desest. (%)  (del boletín INEGI)
      - col 2: Var. anual original (%)   (calculada)
      - col 3 / 5 / 7: índices de actividades prim/sec/ter
      - col 4 / 6 / 8: var. anuales originales de actividades

    El KPI principal usa el índice global (col 0), la variación mensual
    desestacionalizada (col 1) y la variación anual original (col 2). Los
    componentes se conservan en las observaciones y en el Excel; el resumen
    se centra en el agregado para evitar sobrecargar la ficha.
    """
    cfg = (kpicfg.get(ind["key"]) or {}).copy()
    if not cfg:
        return None

    # Forzar las columnas correctas del esquema V3, independientemente de
    # la configuración de KPICFG (que puede estar desfasada hasta que el
    # frontend se actualice en el otro hilo).
    cfg["valCol"] = 0
    cfg["valFmt"] = "idx"
    cfg["varCol"] = 1
    cfg["varFmt"] = "pct-frac"
    cfg["varLabel"] = "Var. mensual desest."
    cfg["yoyCol"] = 2
    cfg["yoyFmt"] = "pct-frac"
    cfg["yoyLabel"] = "Var. anual original"
    cfg["ctx"] = " (índice base 2018=100)"
    cfg["comp"] = "frente al mes previo"
    cfg["vw"] = "variación mensual desestacionalizada"

    kpi = compute_kpi(ind, {ind["key"]: cfg})
    if not kpi:
        return None
    yoy = annual_var(ind, kpi, {ind["key"]: cfg})
    if yoy:
        kpi["yoyText"] = yoy["text"]
        kpi["yoyLabel"] = yoy["label"]
    else:
        kpi["yoyText"] = "—"
        kpi["yoyLabel"] = cfg.get("yoyLabel", "Var. anual")
    bullets = resumen(ind, kpi, yoy, {ind["key"]: cfg})
    return {
        "kpi": kpi,
        "yoy": yoy,
        "annualVar": yoy,
        "resumen": bullets,
        "analysis": analysis(ind, kpi, {ind["key"]: cfg}),
    }


def _imai_metrics(ind: dict, kpicfg: dict) -> dict[str, Any] | None:
    """KPI y resumen para IMAI con el esquema V3 de 14 columnas.

    El esquema V3 tiene:
      - col 0: IMAI índice desestacionalizado
      - col 1: Var. mensual desest. (%)
      - col 2: Var. anual desest. (%)
      - col 3: IMAI índice original
      - col 4: Var. anual original (%)
      - col 5: Acumulado ene-mes original (%)
      - col 6-9: índices desest. de Minería, Energía, Construcción y Manufacturas
      - col 10-13: var. anuales desest. de los cuatro sectores
    """
    cfg = (kpicfg.get(ind["key"]) or {}).copy()
    if not cfg:
        return None

    cfg["valCol"] = 0
    cfg["valFmt"] = "idx"
    cfg["varCol"] = 1
    cfg["varFmt"] = "pct-frac"
    cfg["varLabel"] = "Var. mensual desest."
    cfg["yoyCol"] = 2
    cfg["yoyFmt"] = "pct-frac"
    cfg["yoyLabel"] = "Var. anual desest."
    cfg["acumCol"] = 5
    cfg["acumFmt"] = "pct-frac"
    cfg["acumLabel"] = "Acumulado ene-mes"
    cfg["ctx"] = " (índice base 2018=100)"
    cfg["comp"] = "frente al mes previo"
    cfg["vw"] = "variación mensual desestacionalizada"

    kpi = compute_kpi(ind, {ind["key"]: cfg})
    if not kpi:
        return None

    yoy = annual_var(ind, kpi, {ind["key"]: cfg})
    if yoy:
        kpi["yoyText"] = yoy["text"]
        kpi["yoyLabel"] = yoy["label"]
    else:
        kpi["yoyText"] = "—"
        kpi["yoyLabel"] = cfg.get("yoyLabel", "Var. anual")

    # Acumulado ene-mes (col 5)
    acum_raw = _val_at(ind, kpi["lastI"], 5)
    if acum_raw is not None:
        kpi["acumRaw"] = acum_raw
        kpi["acumText"] = ("+" if acum_raw > 0 else "") + F.fmt_val(acum_raw, "pct-frac")
        kpi["acumLabel"] = "Acumulado ene-mes"
    else:
        kpi["acumRaw"] = None
        kpi["acumText"] = "—"
        kpi["acumLabel"] = "Acumulado ene-mes"

    # Componentes para el resumen.
    comp_cfg = [
        {"name": "Minería", "idxCol": 6, "yoyCol": 10},
        {"name": "Energía, agua y gas", "idxCol": 7, "yoyCol": 11},
        {"name": "Construcción", "idxCol": 8, "yoyCol": 12},
        {"name": "Industrias manufactureras", "idxCol": 9, "yoyCol": 13},
    ]
    cards = []
    for c in comp_cfg:
        idx = _val_at(ind, kpi["lastI"], c["idxCol"])
        y = _val_at(ind, kpi["lastI"], c["yoyCol"])
        cards.append({
            "name": c["name"],
            "nivelRaw": idx,
            "nivelText": F.fmt_val(idx, "idx") if idx is not None else "—",
            "yoyRaw": y,
            "yoyText": F.fmt_val(y, "pct-frac") if y is not None else "—",
        })
    kpi["cards"] = cards

    bullets = resumen(ind, kpi, yoy, {ind["key"]: cfg})

    # Añadir lectura de componentes al resumen (solo si hay datos).
    comp_parts = [
        f"{c['name']} {('contrajo' if c['yoyRaw'] is not None and c['yoyRaw'] < 0 else 'creció')} {c['yoyText']}"
        for c in cards if c["yoyRaw"] is not None
    ]
    if comp_parts and yoy:
        bullets.append(
            "A tasa anual, " + ", ".join(comp_parts[:-1]) +
            (f" y {comp_parts[-1]}" if len(comp_parts) > 1 else comp_parts[0]) + "."
        )
    if kpi.get("acumText") and kpi["acumText"] != "—":
        bullets.append(f"El acumulado ene-mes, en cifras originales, fue de {kpi['acumText']}.")

    return {
        "kpi": kpi,
        "yoy": yoy,
        "annualVar": yoy,
        "resumen": bullets[:4],
        "analysis": analysis(ind, kpi, {ind["key"]: cfg}),
    }


def _emim_metrics(ind: dict, kpicfg: dict) -> dict[str, Any] | None:
    """KPI y resumen para EMIM con el esquema de 18 columnas.

    El esquema tiene:
      - cols 0-4: Producción (índice, mom orig, yoy orig, mom desest, yoy desest)
      - cols 5-9: Personal ocupado
      - cols 10-14: Horas trabajadas
      - cols 15-17: Remuneraciones medias reales (índice, mom desest, yoy desest)
    """
    cfg = (kpicfg.get(ind["key"]) or {}).copy()
    if not cfg:
        return None

    # Forzar el uso del esquema 18-columnas, combinando cifra desestacionalizada
    # mensual con variación anual original, siguiendo el patrón del IGAE.
    cfg["valCol"] = 0
    cfg["valFmt"] = "idx"
    cfg["varCol"] = 3
    cfg["varFmt"] = "pct-frac"
    cfg["varLabel"] = "Var. mensual desest."
    cfg["yoyCol"] = 2
    cfg["yoyFmt"] = "pct-frac"
    cfg["yoyLabel"] = "Var. anual original"
    cfg["ctx"] = " (índice base 2018=100)"
    cfg["comp"] = "frente al mes previo"
    cfg["vw"] = "variación mensual desestacionalizada"

    kpi = compute_kpi(ind, {ind["key"]: cfg})
    if not kpi:
        return None
    yoy = annual_var(ind, kpi, {ind["key"]: cfg})
    if yoy:
        kpi["yoyText"] = yoy["text"]
        kpi["yoyLabel"] = yoy["label"]
    else:
        kpi["yoyText"] = "—"
        kpi["yoyLabel"] = cfg.get("yoyLabel", "Var. anual")

    def _pct(v: float | None) -> str:
        if v is None:
            return "—"
        return ("+" if v > 0 else "") + F.fmt_val(v, "pct-frac")

    def _idx(v: float | None) -> str:
        if v is None:
            return "—"
        return F.fmt_val(v, "idx")

    # Cards: una por cada una de las cuatro variables.
    cards_cfg = [
        {
            "name": "Producción",
            "idxCol": 0, "origMomCol": 1, "origYoyCol": 2,
            "desestMomCol": 3, "desestYoyCol": 4,
        },
        {
            "name": "Personal ocupado",
            "idxCol": 5, "origMomCol": 6, "origYoyCol": 7,
            "desestMomCol": 8, "desestYoyCol": 9,
        },
        {
            "name": "Horas trabajadas",
            "idxCol": 10, "origMomCol": 11, "origYoyCol": 12,
            "desestMomCol": 13, "desestYoyCol": 14,
        },
        {
            "name": "Remuneraciones medias reales",
            "idxCol": 15, "origMomCol": None, "origYoyCol": None,
            "desestMomCol": 16, "desestYoyCol": 17,
        },
    ]
    last_i = kpi["lastI"]
    cards = []
    for c in cards_cfg:
        idx = _val_at(ind, last_i, c["idxCol"])
        om = _val_at(ind, last_i, c["origMomCol"])
        oy = _val_at(ind, last_i, c["origYoyCol"])
        dm = _val_at(ind, last_i, c["desestMomCol"]) if c["desestMomCol"] is not None else None
        dy = _val_at(ind, last_i, c["desestYoyCol"]) if c["desestYoyCol"] is not None else None
        cards.append({
            "name": c["name"],
            "idxCol": c["idxCol"],
            "idxRaw": idx,
            "idxText": _idx(idx),
            "origMomCol": c["origMomCol"],
            "origMomRaw": om,
            "origMomText": _pct(om),
            "origYoyCol": c["origYoyCol"],
            "origYoyRaw": oy,
            "origYoyText": _pct(oy),
            "desestMomCol": c["desestMomCol"],
            "desestMomRaw": dm,
            "desestMomText": _pct(dm),
            "desestYoyCol": c["desestYoyCol"],
            "desestYoyRaw": dy,
            "desestYoyText": _pct(dy),
        })
    kpi["cards"] = cards

    per = kpi["ultimoP"]
    per_long = F.per_long(per)
    prod = cards[0]

    bullets = []
    b1 = (
        f"En {per_long}, el índice de producción se ubicó en {prod['idxText']} puntos. "
        f"La variación mensual desestacionalizada fue {prod['desestMomText']} y la anual original {prod['origYoyText']}."
    )
    if prod["desestYoyRaw"] is not None:
        b1 += f" La anual desestacionalizada fue {prod['desestYoyText']}."
    bullets.append(b1)

    # Personal y horas
    pers = cards[1]
    horas = cards[2]
    parts = []
    if pers["idxRaw"] is not None:
        pers_part = f"el personal ocupado {pers['idxText']} puntos ({pers['origYoyText']} anual original"
        if pers["desestYoyRaw"] is not None:
            pers_part += f", {pers['desestYoyText']} desest."
        pers_part += ")"
        parts.append(pers_part)
    if horas["idxRaw"] is not None:
        horas_part = f"las horas trabajadas {horas['idxText']} puntos ({horas['origYoyText']} anual original"
        if horas["desestYoyRaw"] is not None:
            horas_part += f", {horas['desestYoyText']} desest."
        horas_part += ")"
        parts.append(horas_part)
    if parts:
        bullets.append(f"En el lado laboral, {' y '.join(parts)}.")

    rem = cards[3]
    if rem["idxRaw"] is not None:
        if rem["origYoyRaw"] is not None:
            rem_var = f"variación anual original de {rem['origYoyText']}"
        elif rem["desestYoyRaw"] is not None:
            rem_var = f"variación anual desestacionalizada de {rem['desestYoyText']}"
        else:
            rem_var = "variación anual no disponible"
        bullets.append(
            f"Las remuneraciones medias reales se ubicaron en {rem['idxText']} puntos, "
            f"con {rem_var}."
        )

    # Subsectores (variación anual original) si están disponibles.
    subsectores = ind.get("subsectores")
    if subsectores and isinstance(subsectores, dict) and len(subsectores) > 0:
        top = sorted(subsectores.items(), key=lambda x: x[1], reverse=True)[:3]
        bottom = sorted(subsectores.items(), key=lambda x: x[1])[:3]

        def _short_sector(label):
            s = re.sub(r"^[\d\-]+\s+", "", label)
            s = s.split(",")[0].split(" y ")[0]
            words = s.split()
            if len(words) > 8:
                s = " ".join(words[:8]) + "..."
            return s.strip()

        top_txt = ", ".join(f"{_short_sector(k)} ({_pct(v)})" for k, v in top)
        bot_txt = ", ".join(f"{_short_sector(k)} ({_pct(v)})" for k, v in bottom)
        bullets.append(
            f"A nivel subsectorial, los mayores dinamismos anuales fueron {top_txt}; "
            f"los mayores retrocesos: {bot_txt}."
        )

    return {
        "kpi": kpi,
        "yoy": yoy,
        "annualVar": yoy,
        "resumen": bullets[:4],
        "analysis": analysis(ind, kpi, {ind["key"]: cfg}),
    }


def compute_all_metrics(payload: dict | None = None, kpicfg: dict | None = None) -> dict[str, dict[str, Any]]:
    """Calcula kpi, analysis y annualVar para todos los indicadores."""
    if payload is None:
        payload = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    if kpicfg is None:
        kpicfg, _ = _kpicfg_and_colors()

    out: dict[str, dict[str, Any]] = {}
    for key, ind in payload.get("indicators", {}).items():
        if key == "PIB":
            eopibt = _eopibt_metrics(ind, kpicfg)
            if eopibt:
                out[key] = eopibt
                continue
        if key == "PIBSEC":
            pibsec = _pibsec_metrics(ind, kpicfg)
            if pibsec:
                out[key] = pibsec
                continue
        if key == "IGAE" and len(ind.get("columns", [])) >= 9:
            igae = _igae_metrics(ind, kpicfg)
            if igae:
                out[key] = igae
                continue
        if key == "IMAI" and len(ind.get("columns", [])) >= 14:
            imai = _imai_metrics(ind, kpicfg)
            if imai:
                out[key] = imai
                continue
        if key == "EMIM" and len(ind.get("columns", [])) >= 18:
            emim = _emim_metrics(ind, kpicfg)
            if emim:
                out[key] = emim
                continue
        kpi = compute_kpi(ind, kpicfg)
        yoy = annual_var(ind, kpi, kpicfg) if kpi else None
        bullets = resumen(ind, kpi, yoy, kpicfg) if kpi else []
        if kpi:
            if yoy:
                kpi["yoyText"] = yoy["text"]
                kpi["yoyLabel"] = yoy["label"]
            else:
                kpi["yoyText"] = "—"
                kpi["yoyLabel"] = "—"
        out[key] = {"kpi": kpi, "analysis": analysis(ind, kpi, kpicfg) if kpi else [], "resumen": bullets, "annualVar": yoy}
    return out


def save_metrics(metrics: dict[str, dict[str, Any]], path: Path = METRICS_FILE, last_update_ct: str | None = None) -> None:
    payload = {
        "indicators": metrics,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "last_update_ct": last_update_ct,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_metrics(path: Path = METRICS_FILE) -> dict[str, dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    payload = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    metrics = compute_all_metrics(payload)
    out = {
        "indicators": metrics,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "last_update_ct": payload.get("meta", {}).get("last_update_ct") or payload.get("meta", {}).get("generated_at"),
    }
    METRICS_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: {METRICS_FILE.relative_to(ROOT)} con {len(metrics)} indicadores.")
