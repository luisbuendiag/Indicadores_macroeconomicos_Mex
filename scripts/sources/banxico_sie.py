"""Conector Banco de México (SIE) para el indicador IMFBCF.

Descarga el cuadro CR363 "Índice de volumen de la inversión fija bruta" del
Sistema de Información Económica (SIE) de Banco de México. El cuadro contiene
las series originales, desestacionalizadas y de tendencia del Indicador Mensual
de la Formación Bruta de Capital Fijo (IMFBCF) publicadas por el INEGI.

El conector obtiene los niveles (índices base 2018=100) y calcula las
variaciones mensuales, anuales y acumuladas ene-mes requeridas por el dashboard.
No requiere token de consulta; utiliza el exportador CSV público del SIE.
"""
from __future__ import annotations

import csv
import io
import re
import urllib.parse
import urllib.request
from datetime import datetime

from . import inegi
from .base import SourceResult, USER_AGENT

CUADRO_URL = (
    "https://www.banxico.org.mx/SieInternet/consultarDirectorioInternetAction.do"
    "?accion=consultarCuadro&idCuadro=CR363&locale=es&sector=2"
)
EXPORT_URL = (
    "https://www.banxico.org.mx/SieInternet/consultarDirectorioInternetAction.do"
    "?accion=consultarSeries"
)

# Series del SIE-Banxico (CR363) en el orden del exportador CSV.
# El primer bloque son series originales; el segundo, desestacionalizadas.
# Posiciones 0-10: originales; 11-21: desestacionalizadas.
SR_ORDER = [f"SR{n}" for n in range(17459, 17481)]

SR = {
    "orig_total": "SR17459",
    "orig_mye_total": "SR17460",
    "orig_nacional": "SR17461",
    "orig_eq_transporte_nac": "SR17462",
    "orig_mye_otros_nac": "SR17463",
    "orig_importado": "SR17464",
    "orig_eq_transporte_imp": "SR17465",
    "orig_mye_otros_imp": "SR17466",
    "orig_construccion": "SR17467",
    "orig_residencial": "SR17468",
    "orig_no_residencial": "SR17469",
    "desest_total": "SR17470",
    "desest_mye_total": "SR17471",
    "desest_nacional": "SR17472",
    "desest_eq_transporte_nac": "SR17473",
    "desest_mye_otros_nac": "SR17474",
    "desest_importado": "SR17475",
    "desest_eq_transporte_imp": "SR17476",
    "desest_mye_otros_imp": "SR17477",
    "desest_construccion": "SR17478",
    "desest_residencial": "SR17479",
    "desest_no_residencial": "SR17480",
}

# Especificación de las 40 columnas del dashboard IMFBCF.
# idx: columna objetivo en el indicador.
# sr: clave de SR a usar.
# transform: level, mom, yoy, yoy_acum.
COLUMNS_SPEC = [
    # Cifras desestacionalizadas
    {"idx": 0, "sr": "desest_total", "transform": "level"},
    {"idx": 1, "sr": "desest_total", "transform": "mom"},
    {"idx": 2, "sr": "desest_total", "transform": "yoy"},
    {"idx": 3, "sr": "desest_construccion", "transform": "level"},
    {"idx": 4, "sr": "desest_construccion", "transform": "mom"},
    {"idx": 5, "sr": "desest_construccion", "transform": "yoy"},
    {"idx": 6, "sr": "desest_mye_total", "transform": "level"},
    {"idx": 7, "sr": "desest_mye_total", "transform": "mom"},
    {"idx": 8, "sr": "desest_mye_total", "transform": "yoy"},
    {"idx": 9, "sr": "desest_residencial", "transform": "level"},
    {"idx": 10, "sr": "desest_residencial", "transform": "yoy"},
    {"idx": 11, "sr": "desest_no_residencial", "transform": "level"},
    {"idx": 12, "sr": "desest_no_residencial", "transform": "yoy"},
    {"idx": 13, "sr": "desest_nacional", "transform": "level"},
    {"idx": 14, "sr": "desest_nacional", "transform": "yoy"},
    {"idx": 15, "sr": "desest_eq_transporte_nac", "transform": "level"},
    {"idx": 16, "sr": "desest_eq_transporte_nac", "transform": "yoy"},
    {"idx": 17, "sr": "desest_mye_otros_nac", "transform": "level"},
    {"idx": 18, "sr": "desest_mye_otros_nac", "transform": "yoy"},
    {"idx": 19, "sr": "desest_importado", "transform": "level"},
    {"idx": 20, "sr": "desest_importado", "transform": "yoy"},
    {"idx": 21, "sr": "desest_eq_transporte_imp", "transform": "level"},
    {"idx": 22, "sr": "desest_eq_transporte_imp", "transform": "yoy"},
    {"idx": 23, "sr": "desest_mye_otros_imp", "transform": "level"},
    {"idx": 24, "sr": "desest_mye_otros_imp", "transform": "yoy"},
    # Cifras originales
    {"idx": 25, "sr": "orig_total", "transform": "level"},
    {"idx": 26, "sr": "orig_total", "transform": "yoy"},
    {"idx": 27, "sr": "orig_total", "transform": "yoy_acum"},
    {"idx": 28, "sr": "orig_construccion", "transform": "level"},
    {"idx": 29, "sr": "orig_construccion", "transform": "yoy"},
    {"idx": 30, "sr": "orig_construccion", "transform": "yoy_acum"},
    {"idx": 31, "sr": "orig_residencial", "transform": "level"},
    {"idx": 32, "sr": "orig_residencial", "transform": "yoy"},
    {"idx": 33, "sr": "orig_residencial", "transform": "yoy_acum"},
    {"idx": 34, "sr": "orig_no_residencial", "transform": "level"},
    {"idx": 35, "sr": "orig_no_residencial", "transform": "yoy"},
    {"idx": 36, "sr": "orig_no_residencial", "transform": "yoy_acum"},
    {"idx": 37, "sr": "orig_mye_total", "transform": "level"},
    {"idx": 38, "sr": "orig_mye_total", "transform": "yoy"},
    {"idx": 39, "sr": "orig_mye_total", "transform": "yoy_acum"},
]


def _fetch_csv(warnings: list[str]) -> str | None:
    """Inicia sesión en el SIE y descarga el CSV del cuadro CR363."""
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
    try:
        with opener.open(
            urllib.request.Request(CUADRO_URL, headers={"User-Agent": USER_AGENT}),
            timeout=20,
        ) as r:
            _ = r.read()
    except Exception as e:  # noqa: BLE001
        warnings.append(f"banxico_sie: no se pudo iniciar sesión en el SIE: {e}")
        return None

    data = {
        "idCuadro": "CR363",
        "sector": "2",
        "version": "3",
        "locale": "es",
        "formatoHorizontal": "false",
        "metadatosWeb": "false",
        "series": SR_ORDER,
        "anoInicial": "Todo",
        "anoFinal": "2026",
        "tipoInformacion": "4,1",
        "formatoCSV.x": "0",
        "formatoCSV.y": "0",
    }
    encoded = urllib.parse.urlencode(data, doseq=True).encode("latin-1")
    req = urllib.request.Request(
        EXPORT_URL,
        data=encoded,
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": CUADRO_URL,
        },
        method="POST",
    )
    try:
        with opener.open(req, timeout=120) as r:
            raw = r.read()
            content_type = r.headers.get("Content-Type", "")
            if "csv" not in content_type.lower() and not raw.lstrip().startswith(b'"Banco de'):
                warnings.append(
                    f"banxico_sie: respuesta inesperada ({content_type})"
                )
                return None
            return raw.decode("latin-1")
    except Exception as e:  # noqa: BLE001
        warnings.append(f"banxico_sie: error al descargar CSV: {e}")
        return None


def _parse_csv(csv_text: str, warnings: list[str]) -> dict[str, list[dict]] | None:
    """Parsea el CSV y devuelve un diccionario {serie: [observaciones]}."""
    reader = csv.reader(io.StringIO(csv_text), delimiter=",", quotechar='"')
    rows = list(reader)
    header_idx = None
    for i, row in enumerate(rows):
        if row and row[0].strip() == "Fecha":
            header_idx = i
            break
    if header_idx is None:
        warnings.append("banxico_sie: no se encontró la fila de encabezado 'Fecha'")
        return None

    header = rows[header_idx]
    if len(header) < 2:
        warnings.append("banxico_sie: encabezado sin series")
        return None
    sr_cols = [h.strip() for h in header[1:]]

    series: dict[str, list[dict]] = {sr: [] for sr in sr_cols}
    date_re = re.compile(r"\d{2}/\d{2}/\d{4}")
    for row in rows[header_idx + 1:]:
        if not row or not row[0].strip():
            continue
        date_str = row[0].strip()
        if not date_re.match(date_str):
            continue
        dd, mm, yyyy = date_str.split("/")
        ym = f"{yyyy}-{mm}"
        period = inegi.ym_to_label(ym, 8)
        for j, sr in enumerate(sr_cols):
            if j + 1 >= len(row):
                continue
            raw = row[j + 1].strip()
            if raw == "":
                continue
            try:
                val = float(raw)
            except ValueError:
                continue
            series[sr].append({"ym": ym, "period": period, "value": val})

    for sr in series:
        series[sr].sort(key=lambda o: o["ym"])
    return series


def _yoy_acum(ym: str, by_ym: dict[str, float]) -> float | None:
    """Acumulado ene-mes: promedio ene-mes actual / promedio ene-mes año anterior - 1."""
    year, month = map(int, ym.split("-"))
    cur_sum = 0.0
    prev_sum = 0.0
    for m in range(1, month + 1):
        cur_ym = f"{year:04d}-{m:02d}"
        prev_ym = f"{year - 1:04d}-{m:02d}"
        if cur_ym not in by_ym or prev_ym not in by_ym:
            return None
        cur_sum += by_ym[cur_ym]
        prev_sum += by_ym[prev_ym]
    if prev_sum == 0:
        return None
    return round(cur_sum / prev_sum - 1.0, 6)


def _build_items(series: dict[str, list[dict]]) -> list[dict]:
    """Construye los 40 items del IMFBCF a partir de las series de niveles."""
    by_ym: dict[str, dict[str, float]] = {}
    for sr, obs in series.items():
        by_ym[sr] = {o["ym"]: o["value"] for o in obs}

    # Orden común de periodos a partir de la primera serie disponible.
    first_sr = next(iter(series))
    yms = [o["ym"] for o in series[first_sr]]

    items: list[dict] = []
    for spec in COLUMNS_SPEC:
        sr = SR[spec["sr"]]
        transform = spec["transform"]
        src = by_ym.get(sr, {})
        api_total: list[dict] = []
        for ym in yms:
            val = src.get(ym)
            if val is None:
                continue
            if transform == "level":
                value = round(val, 6)
            elif transform == "mom":
                prev_ym = inegi._ym_minus_months(ym, 1)
                if prev_ym is None or prev_ym not in src or src[prev_ym] == 0:
                    continue
                value = round(val / src[prev_ym] - 1.0, 6)
            elif transform == "yoy":
                prev_ym = inegi._ym_minus_months(ym, 12)
                if prev_ym is None or prev_ym not in src or src[prev_ym] == 0:
                    continue
                value = round(val / src[prev_ym] - 1.0, 6)
            elif transform == "yoy_acum":
                value = _yoy_acum(ym, src)
                if value is None:
                    continue
            else:
                continue
            period = inegi.ym_to_label(ym, 8)
            api_total.append({"ym": ym, "period": period, "value": value})

        if api_total:
            last = api_total[-1]
            item = {
                "key": "IMFBCF",
                "target_column": spec["idx"],
                "serie": sr,
                "api_total": api_total,
                "link": CUADRO_URL,
                "metodo": "Banco de México (SIE) - cuadro CR363",
                "freq": 8,
                "api_meta": {
                    "n_obs": len(api_total),
                    "ultimo_valor": last["value"],
                    "ultima_observacion": last["period"],
                    "ultima_ym": last["ym"],
                    "lastupdate": None,
                },
            }
            items.append(item)
    return items


def fetch(config: dict | None = None) -> SourceResult:
    """Consulta el cuadro CR363 del SIE-Banxico y devuelve un SourceResult."""
    warnings: list[str] = []
    csv_text = _fetch_csv(warnings)
    if csv_text is None:
        return SourceResult(False, warnings=warnings)

    series = _parse_csv(csv_text, warnings)
    if series is None:
        return SourceResult(False, warnings=warnings)

    if not all(series.get(sr) for sr in SR_ORDER):
        missing = [sr for sr in SR_ORDER if not series.get(sr)]
        warnings.append(f"banxico_sie: faltan series en el CSV: {missing}")
        # Continuamos con las que tengamos; las demás quedarán en el indicador.

    items = _build_items(series)
    if not items:
        warnings.append("banxico_sie: no se pudieron construir observaciones")
        return SourceResult(False, warnings=warnings)

    data = {"IMFBCF": items}
    return SourceResult(True, data=data, warnings=warnings)
