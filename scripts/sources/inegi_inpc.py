"""Conector INPC que combina BIE, tabulado oficial y boletines de prensa.

Fuentes:
  - Nivel general y subyacente: BIE-BISE 334360 / 334452 (actualizadas a 2026).
  - Componentes históricos: BIE-BISE 8655xx (índices base 2018=100, hasta ago 2025).
  - Meses faltantes (sep 2025 en adelante): boletines oficiales de Sala de Prensa.
  - Último mes disponible: tabulado oficial INPC (CA55_2018A) como validación.

Las variaciones porcentuales se devuelven como fracciones (0.0337 = 3.37 %);
las incidencias como puntos porcentuales tal cual (0.026 = 0.026 p.p.).
"""
from __future__ import annotations

import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime
from io import BytesIO
from typing import Any

from . import inegi
from .base import USER_AGENT, SourceResult, http_get_json

try:
    import pdfplumber
except ImportError:  # pragma: no cover
    pdfplumber = None

TABULADO_URL = (
    "https://www.inegi.org.mx/app/tabulados/inp2/serviciocuadros/wsDataService.svc/"
    "obtienetabuladoinp/CA55_2018A/4/1"
)
BIE_ENDPOINT = (
    "https://www.inegi.org.mx/app/api/indicadores/desarrolladores/jsonxml/"
    "INDICATOR/{ids}/es/00/false/BIE-BISE/2.0/{token}?type=json"
)
INPC_BULLETIN_URL = (
    "https://www.inegi.org.mx/contenidos/saladeprensa/boletines/{year}/inpc/"
    "inpc_2q{year}_{mm:02d}.pdf"
)

# Mapeo de conceptos del tabulado/boletín a columnas del dashboard.
CONCEPTOS = {
    "inpc": {
        "nombre": "Índice Nacional de Precios al Consumidor",
        "bie_serie_idx": "334360",
        "bie_serie_legacy": "865541",
        "col_idx": 0,
        "col_mom": 1,
        "col_yoy": 2,
    },
    "subyacente": {
        "nombre": "Subyacente",
        "bie_serie_idx": "334452",
        "bie_serie_legacy": "865542",
        "col_idx": 3,
        "col_mom": 4,
        "col_yoy": 5,
        "col_inc": 16,
    },
    "mercancias": {
        "nombre": "Mercancías",
        "bie_serie_legacy": "865548",
        "col_mom": 6,
        "col_yoy": 7,
    },
    "servicios": {
        "nombre": "Servicios",
        "bie_serie_legacy": "865551",
        "col_mom": 8,
        "col_yoy": 9,
    },
    "no_subyacente": {
        "nombre": "No subyacente",
        "bie_serie_legacy": "865555",
        "col_mom": 10,
        "col_yoy": 11,
        "col_inc": 17,
    },
    "agropecuarios": {
        "nombre": "Agropecuarios",
        "bie_serie_legacy": "865556",
        "col_mom": 12,
        "col_yoy": 13,
    },
    "energeticos_tarifas": {
        "nombre": "Energéticos y tarifas autorizadas por el gobierno",
        "bie_serie_legacy": "865559",
        "col_mom": 14,
        "col_yoy": 15,
    },
}


def _req(url: str, timeout: int = 60) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as r:
        return r.read()


def _head_ok(url: str, timeout: int = 15) -> bool:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT}, method="HEAD")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": USER_AGENT}), timeout=timeout) as r:
                ctype = r.headers.get("Content-Type", "")
                return "pdf" in ctype.lower() or r.headers.get("Content-Length") is not None
        except Exception:
            return False


def _load_token() -> str | None:
    token = os.environ.get("INEGI_TOKEN")
    if not token:
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except Exception:
            pass
        token = os.environ.get("INEGI_TOKEN")
    return token


def _parse_bie_series(serie_id: str, token: str) -> list[dict]:
    """Consulta el BIE y devuelve observaciones {ym, value, period}."""
    url = BIE_ENDPOINT.format(ids=serie_id, token=token)
    try:
        raw = http_get_json(url, timeout=30)
    except Exception as exc:
        raise RuntimeError(f"BIE {serie_id}: {exc}") from exc
    parsed = inegi._parse_series(raw)
    if not parsed:
        raise RuntimeError(f"BIE {serie_id}: sin observaciones")
    return parsed[0]


def _compute_variations(index_obs: list[dict]) -> tuple[dict[str, float], dict[str, float], dict[str, float]]:
    """Dado un índice ordenado por ym, devuelve (idx, mom, yoy).

    - idx: nivel del índice (sin escalar).
    - mom / yoy: variación porcentual expresada como número en porcentaje
      (p. ej. 3.37 para una inflación anual del 3.37 %), coherente con pct-raw.
    """
    by_ym = {o["ym"]: o["value"] for o in index_obs}
    idx: dict[str, float] = {}
    mom: dict[str, float] = {}
    yoy: dict[str, float] = {}
    for ym in sorted(by_ym):
        idx[ym] = by_ym[ym]
        prev = inegi._ym_minus_months(ym, 1)
        if prev and prev in by_ym and by_ym[prev] != 0:
            mom[ym] = (by_ym[ym] / by_ym[prev] - 1.0) * 100.0
        prev_y = inegi._ym_minus_months(ym, 12)
        if prev_y and prev_y in by_ym and by_ym[prev_y] != 0:
            yoy[ym] = (by_ym[ym] / by_ym[prev_y] - 1.0) * 100.0
    return idx, mom, yoy


def _parse_tabulado() -> dict[str, dict[str, Any]] | None:
    """Recupera el tabulado oficial CA55_2018A (único periodo disponible)."""
    try:
        data = http_get_json(TABULADO_URL, timeout=30)
    except Exception as exc:
        return None
    encab = (data.get("Encab") or [{}])[0]
    periodo = (encab.get("periodo_actual") or "").strip()
    if not periodo:
        return None
    mes, anio = _parse_mes_anio(periodo)
    if not mes or not anio:
        return None
    ym = f"{anio:04d}-{mes:02d}"
    period = inegi.ym_to_label(ym, 8)
    out: dict[str, dict[str, Any]] = {}
    for fila in data.get("Datos") or []:
        desc = _normalizar_concepto(fila.get("descripcion", ""))
        out[desc] = {
            "ym": ym,
            "period": period,
            "mensual": _parse_pct(fila.get("valor_mensual")),
            "anual": _parse_pct(fila.get("valor_anual")),
            "incidencia": _parse_pct(fila.get("valor_incidencia")),
            "serie": fila.get("serie"),
        }
    return out


def _parse_mes_anio(texto: str) -> tuple[int | None, int | None]:
    meses = {
        "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
        "jul": 7, "ago": 8, "sep": 9, "oct": 10, "nov": 11, "dic": 12,
        "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
        "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
    }
    m = re.search(r"([A-Za-záéíóúñ]+)\s+(\d{4})", texto)
    if not m:
        return None, None
    mes_str, anio = m.group(1).lower(), int(m.group(2))
    return meses.get(mes_str), anio


def _normalizar_concepto(desc: str) -> str:
    d = desc.lower().strip()
    d = re.sub(r"\s+", " ", d)
    d = re.sub(r"\d+/", "", d)
    # Quitar notas al pie (superscript) y contenido entre paréntesis.
    d = re.sub(r"\s*\d+/\s*$", "", d).strip()
    d = re.sub(r"\s*\([^)]*\)", "", d).strip()
    if d == "precios al consumidor (inpc)":
        d = "inpc"
    if "inpc" in d or d.startswith("índice nacional de precios") or d.startswith("precios al consumidor"):
        return "inpc"
    if d == "subyacente" or ("subyacente" in d and "no" not in d):
        return "subyacente"
    if d == "mercancías" or d == "mercancias":
        return "mercancias"
    if d == "servicios":
        return "servicios"
    if d == "no subyacente" or d == "no subyacente":
        return "no_subyacente"
    if d == "agropecuarios":
        return "agropecuarios"
    if "energéticos" in d and "tarifas" in d:
        return "energeticos_tarifas"
    return ""


def _parse_pct(value: Any) -> float | None:
    """Convierte un texto porcentual/p.p. al número tal cual (3.37 % -> 3.37)."""
    if value is None:
        return None
    s = str(value).replace("%", "").replace("▲", "").replace("▼", "").replace(",", "").strip()
    if s in ("", "-", "—", "N/D"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _available_bulletins(end_year: int, end_month: int, count: int) -> list[tuple[int, int, str]]:
    """Descubre los últimos `count` boletines INPC hacia atrás desde (end_year, end_month).

    El boletín `inpc_2qYEAR_MM.pdf` se publica en el mes `MM` y contiene datos del mes `MM-1`.
    """
    found = []
    year, mm = end_year, end_month
    while len(found) < count:
        url = INPC_BULLETIN_URL.format(year=year, mm=mm)
        if _head_ok(url):
            found.append((year, mm, url))
        time.sleep(0.5)
        mm -= 1
        if mm == 0:
            year -= 1
            mm = 12
        if year < 2020:
            break
    return found


def _parse_inpc_bulletin(pdf_bytes: bytes) -> dict[str, Any] | None:
    """Extrae del boletín INPC el mes de referencia y la tabla de variaciones."""
    if pdfplumber is None:
        return None
    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        text_p0 = pdf.pages[0].extract_text() or ""
        tables = _extract_main_table(pdf)
    data_month, data_year = _extract_ref_month_year(text_p0)
    if not data_month or not data_year:
        return None
    ym = f"{data_year:04d}-{data_month:02d}"
    period = inegi.ym_to_label(ym, 8)
    rows = _parse_inpc_table_rows([tables])
    out: dict[str, Any] = {"ym": ym, "period": period, "concepts": {}}
    for key, vals in rows.items():
        out["concepts"][key] = {
            "mensual": vals.get("mensual"),
            "anual": vals.get("anual"),
            "incidencia": vals.get("incidencia"),
        }
    return out


def _extract_ref_month_year(text: str) -> tuple[int | None, int | None]:
    m = re.search(r"en\s+([A-Za-záéíóúñ]+)\s+de\s+(\d{4})", text, re.IGNORECASE)
    if m:
        mes, anio = _parse_mes_anio(f"{m.group(1)} {m.group(2)}")
        if mes and anio:
            return mes, anio
    m = re.search(r"([A-Za-záéíóúñ]+)\s+(\d{4})", text)
    if m:
        return _parse_mes_anio(f"{m.group(1)} {m.group(2)}")
    return None, None


def _extract_main_table(pdf) -> list[list[list[str]]]:
    """Devuelve una lista con la tabla principal (fila de conceptos y años)."""
    for i, page in enumerate(pdf.pages):
        tables = page.extract_tables() or []
        for t in tables:
            if not t:
                continue
            flat = [str(cell or "").strip() for row in t if row for cell in row]
            text = " ".join(flat).lower()
            if "variación porcentual" in text and "incidencia" in text:
                return [list(row) for row in t if row]
    # Respaldos frecuentes: tabla en página 2 (índice 1) o en página 1 (índice 0).
    for pidx in (1, 0):
        if pidx < len(pdf.pages):
            tables = pdf.pages[pidx].extract_tables() or []
            if tables and tables[0]:
                return [list(row) for row in tables[0] if row]
    return []


def _parse_inpc_table_rows(tables: list[list[list[str]]]) -> dict[str, dict[str, float | None]]:
    """Parsea la tabla Cuadro 1 del boletín INPC.

    Estructura observada:
      [0] Concepto
      [1-3] Variación mensual (tres años, el último = año de referencia)
      [4-6] Variación anual   (tres años, el último = año de referencia)
      [7-9] Incidencia mensual(tres años, el último = año de referencia)
      [10]  Incidencia anual (año de referencia)
    """
    concepts: dict[str, dict[str, float | None]] = {}
    for table in tables:
        if not table:
            continue
        header_idx = None
        for i, row in enumerate(table):
            if not row:
                continue
            row_text = [str(c or "").strip() for c in row if c is not None]
            if any(re.match(r"^\d{4}$", c) for c in row_text):
                header_idx = i
                break
        if header_idx is None:
            continue
        for row in table[header_idx + 1 :]:
            if not row:
                continue
            first = str(row[0] or "").strip()
            if not first:
                continue
            concept = _normalizar_concepto(first)
            if not concept:
                continue
            # Alargar fila con None para evitar IndexError.
            cells = list(row) + [None] * (11 - len(row))
            # El último año de cada bloque es la columna de interés.
            mensual = _parse_pct(cells[3])
            anual = _parse_pct(cells[6])
            incidencia = _parse_pct(cells[9])
            incidencia_anual = _parse_pct(cells[10])
            if concept in CONCEPTOS:
                concepts[concept] = {
                    "mensual": mensual,
                    "anual": anual,
                    "incidencia": incidencia,
                    "incidencia_anual": incidencia_anual,
                }
    return concepts


def fetch(config: dict | None = None, start_year: int = 2018) -> SourceResult:
    warnings: list[str] = []
    token = _load_token()
    if not token:
        warnings.append("inegi_inpc: falta INEGI_TOKEN")
        return SourceResult(False, warnings=warnings)

    if pdfplumber is None:
        warnings.append("inegi_inpc: pdfplumber no está instalado")

    # Acumulador por ym -> {col: value}
    values: dict[str, list[float | None]] = {}

    # 1) General y subyacente desde BIE 334360 / 334452
    try:
        for key in ("inpc", "subyacente"):
            serie = CONCEPTOS[key]["bie_serie_idx"]
            obs = _parse_bie_series(serie, token)
            idx, mom, yoy = _compute_variations(obs)
            for ym in sorted(idx):
                if int(ym[:4]) < start_year:
                    continue
                vals = values.setdefault(ym, [None] * 18)
                vals[CONCEPTOS[key]["col_idx"]] = round(idx[ym], 6)
                vals[CONCEPTOS[key]["col_mom"]] = round(mom.get(ym, None) or 0, 6) if mom.get(ym) is not None else None
                vals[CONCEPTOS[key]["col_yoy"]] = round(yoy.get(ym, None) or 0, 6) if yoy.get(ym) is not None else None
    except Exception as exc:
        warnings.append(f"inegi_inpc BIE general/subyacente: {exc}")

    # 2) Componentes desde BIE 8655xx (hasta ago 2025)
    try:
        for key, cfg in CONCEPTOS.items():
            if key in ("inpc", "subyacente") or not cfg.get("bie_serie_legacy"):
                continue
            obs = _parse_bie_series(cfg["bie_serie_legacy"], token)
            _, mom, yoy = _compute_variations(obs)
            for ym in sorted(mom):
                if int(ym[:4]) < start_year:
                    continue
                vals = values.setdefault(ym, [None] * 18)
                if mom.get(ym) is not None:
                    vals[cfg["col_mom"]] = round(mom[ym], 6)
                if yoy.get(ym) is not None:
                    vals[cfg["col_yoy"]] = round(yoy[ym], 6)
    except Exception as exc:
        warnings.append(f"inegi_inpc BIE componentes: {exc}")

    # 3) Boletines para meses faltantes (desde el mes más reciente disponible en BIE hacia adelante)
    if pdfplumber is not None:
        try:
            bie_latest = max((ym for ym in values if all(values[ym][c] is not None for c in (6, 7)) or all(values[ym][c] is not None for c in (8, 9))), default=None)
            if bie_latest:
                year, month = int(bie_latest[:4]), int(bie_latest[5:7])
                # Avanzamos al mes siguiente al último BIE.
                month += 1
                if month > 12:
                    year += 1
                    month = 1
            else:
                year, month = 2025, 9
            # Pedimos hasta 18 meses hacia atrás desde el mes actual para cubrir el hueco.
            now = datetime.now()
            bulletins = _available_bulletins(now.year, now.month, 18)
            for pub_year, pub_month, url in bulletins:
                try:
                    pdf_bytes = _req(url, timeout=60)
                    parsed = _parse_inpc_bulletin(pdf_bytes)
                    if not parsed:
                        continue
                    ym = parsed["ym"]
                    # Tomar solo los meses a partir del hueco detectado.
                    if ym < bie_latest or (bie_latest and ym <= bie_latest):
                        continue
                    vals = values.setdefault(ym, [None] * 18)
                    for key, v in parsed["concepts"].items():
                        cfg = CONCEPTOS.get(key)
                        if not cfg:
                            continue
                        if v.get("mensual") is not None:
                            vals[cfg["col_mom"]] = round(v["mensual"], 6)
                        if v.get("anual") is not None:
                            vals[cfg["col_yoy"]] = round(v["anual"], 6)
                        if v.get("incidencia") is not None and cfg.get("col_inc") is not None:
                            # Las incidencias se almacenan como puntos porcentuales tal cual.
                            vals[cfg["col_inc"]] = round(v["incidencia"], 6)
                except Exception as exc:
                    warnings.append(f"inegi_inpc boletín {url}: {exc}")
        except Exception as exc:
            warnings.append(f"inegi_inpc boletines: {exc}")

    # 4) Tabulado oficial para el mes más reciente (validación/respuesta si boletín no llegó).
    try:
        tab = _parse_tabulado()
        if tab:
            for key, cfg in CONCEPTOS.items():
                t = tab.get(key)
                if not t:
                    continue
                ym = t["ym"]
                vals = values.setdefault(ym, [None] * 18)
                if t.get("mensual") is not None and cfg.get("col_mom") is not None:
                    vals[cfg["col_mom"]] = round(t["mensual"], 6)
                if t.get("anual") is not None and cfg.get("col_yoy") is not None:
                    vals[cfg["col_yoy"]] = round(t["anual"], 6)
                if t.get("incidencia") is not None and cfg.get("col_inc") is not None:
                    vals[cfg["col_inc"]] = round(t["incidencia"], 6)
    except Exception as exc:
        warnings.append(f"inegi_inpc tabulado: {exc}")

    if not values:
        return SourceResult(False, warnings=warnings + ["inegi_inpc: sin observaciones"])

    # Convertir a items por columna como espera build_data.apply_inegi_total.
    by_col: dict[int, list[dict]] = {}
    for ym in sorted(values):
        period = inegi.ym_to_label(ym, 8)
        for col, val in enumerate(values[ym]):
            if val is None:
                continue
            by_col.setdefault(col, []).append({"ym": ym, "value": val, "period": period})

    items = []
    for col in sorted(by_col):
        api_total = by_col[col]
        if not api_total:
            continue
        last = api_total[-1]
        items.append({
            "key": "INPC",
            "target_column": col,
            "api_total": api_total,
            "serie": "inegi_inpc_combined",
            "link": "https://www.inegi.org.mx/app/tabulados/inp/default.aspx?nc=ca55_2018a",
            "metodo": "INEGI BIE + Tabulado INPC + Boletines INPC",
            "freq": 8,
            "api_meta": {
                "serie": "334360/334452/8655xx",
                "freq": 8,
                "unit": "1012",
                "n_obs": len(api_total),
                "ultimo_valor": round(last["value"], 6),
                "ultima_ym": last["ym"],
                "ultima_observacion": last["period"],
            },
        })

    return SourceResult(True, data={"INPC": items}, warnings=warnings)
