"""Conector para boletines oficiales del INEGI publicados en PDF.

Este módulo descarga y parsea los boletines de prensa del INEGI para los
indicadores que no están disponibles directamente en el BIE (o cuyos IDs no se
han podido confirmar en el catálogo BIE-BISE):

  - IOAE: Indicador Oportuno de la Actividad Económica (estimación puntual y
    límites del intervalo de confianza del IGAE).
  - CONSUMO (IMCP): Indicador Mensual del Consumo Privado (índice y var. mensual).
  - IMFBCF: Indicador Mensual de la Formación Bruta de Capital Fijo (índice y var. mensual).
  - EMIM: Encuesta Mensual de la Industria Manufacturera (producción, personal,
    horas, remuneraciones) – parseo parcial desde el boletín.

Fuentes oficiales (patrones de URL):
  - IOAE: https://www.inegi.org.mx/contenidos/saladeprensa/boletines/{year}/ioae/ioae{year}_{mm}.pdf
  - IMCP: https://www.inegi.org.mx/contenidos/saladeprensa/boletines/{year}/imcp/imcpmi{year}_{mm}.pdf
  - IMFBCF: https://www.inegi.org.mx/contenidos/saladeprensa/boletines/{year}/ifb/imfbcf{year}_{mm}.pdf
  - EMIM: https://www.inegi.org.mx/contenidos/saladeprensa/boletines/{year}/emim/emim{year}_{mm}.pdf

El parseo es defensivo: si un boletín no se puede leer o los valores no cumplen
las validaciones mínimas, se omite y se deja la observación anterior intacta.
No requiere token del INEGI porque los boletines son públicos, pero conserva
el origen API para distinguirlo de los respaldos manuales.
"""
from __future__ import annotations

import re
import time
import urllib.error
import urllib.request
from io import BytesIO
from pathlib import Path

from . import inegi
from .base import USER_AGENT, SourceResult

try:
    import pdfplumber
except ImportError:  # pragma: no cover
    pdfplumber = None

BULLETIN_URLS = {
    "IOAE": "https://www.inegi.org.mx/contenidos/saladeprensa/boletines/{year}/ioae/ioae{year}_{mm}.pdf",
    "CONSUMO": "https://www.inegi.org.mx/contenidos/saladeprensa/boletines/{year}/imcp/imcpmi{year}_{mm}.pdf",
    "IMFBCF": "https://www.inegi.org.mx/contenidos/saladeprensa/boletines/{year}/ifb/imfbcf{year}_{mm}.pdf",
    "EMIM": "https://www.inegi.org.mx/contenidos/saladeprensa/boletines/{year}/emim/emim{year}_{mm}.pdf",
}

MES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sep": 9, "oct": 10, "nov": 11, "dic": 12,
}


def _req(url: str, timeout: int = 60) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as r:
        return r.read()


def _head_size(url: str, timeout: int = 15) -> int:
    """Devuelve el Content-Length reportado; 0 si no es un PDF válido o no existe."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT}, method="HEAD")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as r:
            cl = r.headers.get("Content-Length")
            if cl:
                return int(cl)
            return 1
    except (urllib.error.HTTPError, Exception):  # noqa: BLE001
        return 0


def _pdf_size(url: str, timeout: int = 15, retries: int = 2) -> int:
    """Respalda a GET con reintentos para evitar throttling del servidor."""
    for attempt in range(retries + 1):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=timeout) as r:
                ctype = r.headers.get("Content-Type", "")
                if "pdf" in ctype.lower():
                    cl = r.headers.get("Content-Length")
                    if cl:
                        return int(cl)
                    return len(r.read(8192))
                return 0
        except (urllib.error.HTTPError, Exception):  # noqa: BLE001
            if attempt < retries:
                time.sleep(1.0)
            continue
    return 0


def _head_ok(url: str, timeout: int = 15) -> bool:
    # Se usa GET como respaldo porque INEGI no siempre devuelve Content-Length correcto en HEAD.
    return _pdf_size(url, timeout) > 5000


def _month_year(pub_year: int, pub_month: int, ref_month: int) -> tuple[int, int]:
    """El mes de referencia suele estar 1-2 meses antes de la publicación."""
    if ref_month <= pub_month:
        return pub_year, ref_month
    return pub_year - 1, ref_month


def _parse_pct(text) -> float | None:
    if not isinstance(text, str):
        return None
    text = text.replace("%", "").replace("▲", "").replace("▼", "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _parse_index(text) -> float | None:
    if not isinstance(text, str):
        return None
    text = text.strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _extract_data_month(text: str) -> tuple[int, int] | None:
    """Busca la frase 'en <mes> de <año>' del periodo de referencia (excluye la fecha de publicación)."""
    m = re.search(r"en\s+([a-zA-Záéíóúñ]+)\s+de\s+(\d{4})", text, re.IGNORECASE)
    if m:
        try:
            return int(m.group(2)), MES[m.group(1).lower()]
        except KeyError:
            pass
    return None


def _extract_pub_date(text: str) -> tuple[int, int, int] | None:
    m = re.search(r"(\d{1,2})\s+de\s+([a-zA-Záéíóúñ]+)\s+de\s+(\d{4})", text)
    if not m:
        return None
    try:
        day, month_name, year = int(m.group(1)), m.group(2).lower(), int(m.group(3))
        return year, MES[month_name], day
    except (KeyError, ValueError):
        return None


def _pdf_text_first_page(pdf_bytes: bytes) -> tuple[str, list[list[str]]]:
    if pdfplumber is None:
        return "", []
    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        page = pdf.pages[0]
        return page.extract_text() or "", [list(row) for row in (page.extract_tables() or [])]


def _pdf_page_tables(pdf_bytes: bytes, page_index: int) -> list[list[list[str]]]:
    if pdfplumber is None:
        return []
    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        if page_index >= len(pdf.pages):
            return []
        return [list(row) for row in (pdf.pages[page_index].extract_tables() or [])]


def _available_issues(kind: str, start_year: int, end_year: int, max_count: int = 200) -> list[tuple[int, int, str]]:
    """Descubre qué boletines existen en el rango de años, de los más recientes a los más antiguos."""
    found = []
    for year in range(end_year, start_year - 1, -1):
        for mm in range(12, 0, -1):
            if len(found) >= max_count:
                break
            time.sleep(0.5)
            url = BULLETIN_URLS[kind].format(year=year, mm=f"{mm:02d}")
            if _head_ok(url):
                found.append((year, mm, url))
    return found


def _ioae_month_year(pdf_bytes: bytes, ref_month: int, pub_year: int, pub_month: int) -> tuple[int, int]:
    """Para IOAE el boletín publica 1 o 2 meses después del mes de referencia."""
    return _month_year(pub_year, pub_month, ref_month)


def _parse_ioae(pdf_bytes: bytes, pub_date: tuple[int, int, int] | None) -> dict[str, list[dict]] | None:
    """Extrae la estimación puntual e intervalo de confianza del IGAE (tasa mensual)."""
    pub_year, pub_month, _ = pub_date or (None, None, None)
    if pub_year is None:
        return None

    tables = _pdf_page_tables(pdf_bytes, 1)
    for table in tables:
        # Formato 2024-2026: encabezado con 'Concepto' y 'Nowcast'
        if not table or len(table) < 3:
            continue
        header = [c.strip() if c else "" for c in table[0]]
        if not any("Concepto" in h for h in header) or not any("Nowcast" in h for h in header):
            continue

        values = []
        current_concept = ""
        for row in table:
            cells = [c.strip() if c else "" for c in row]
            if not any(cells):
                continue
            if cells[0]:
                current_concept = cells[0]
            if current_concept != "IGAE":
                continue
            # Localizar el mes y los tres valores
            month_text = next((c for c in cells[1:] if c.lower() in MES), "")
            if not month_text:
                continue
            nums = [_parse_pct(c) for c in cells if _parse_pct(c) is not None]
            if len(nums) < 3:
                continue
            year, month = _ioae_month_year(pdf_bytes, MES[month_text.lower()], pub_year, pub_month)
            ym = f"{year:04d}-{month:02d}"
            values.append({
                "ym": ym,
                "period": inegi.ym_to_label(ym, 8),
                "point": nums[0],
                "lower": nums[1],
                "upper": nums[2],
            })

        if values:
            values.sort(key=lambda x: x["ym"])
            return {
                "point": [{"ym": v["ym"], "value": v["point"], "period": v["period"]} for v in values],
                "lower": [{"ym": v["ym"], "value": v["lower"], "period": v["period"]} for v in values],
                "upper": [{"ym": v["ym"], "value": v["upper"], "period": v["period"]} for v in values],
            }

    # Formato antiguo (2023 aprox) – tabla compacta
    for table in tables:
        if not table or len(table) < 3:
            continue
        header = [c.strip() if c else "" for c in table[0]]
        if "Mes de" in header[0] or "referencia" in header[0]:
            row = table[-1]
            months = [m.strip() for m in re.findall(r"(\d{4}/\d{1,2})", row[0])]
            if not months:
                continue
            # Los índices de columnas para IGAE inferior/nowcast/superior
            # header[1..3] = IGAE Inferior/Nowcast/Superior
            igae_vals = []
            for i, raw in enumerate(row[1:4]):
                parts = [p.strip() for p in (raw or "").split("\n") if p.strip()]
                igae_vals.append(parts)
            if len(igae_vals) < 3 or not all(igae_vals):
                continue
            out = {"point": [], "lower": [], "upper": []}
            for idx, month_ref in enumerate(months):
                y, m = month_ref.split("/")
                year, month = int(y), int(m)
                # Si el mes ya pasó y la publicación es de inicio de año, puede pertenecer al año anterior
                ym = f"{year:04d}-{month:02d}"
                period = inegi.ym_to_label(ym, 8)
                vals = []
                for col in igae_vals:
                    val = col[idx] if idx < len(col) else None
                    if val is None:
                        vals.append(None)
                    else:
                        vals.append(_parse_pct(val) if "." in val or val.replace("-", "").isdigit() else _parse_index(val))
                if all(v is not None for v in vals[:3]):
                    out["point"].append({"ym": ym, "value": vals[1], "period": period})
                    out["lower"].append({"ym": ym, "value": vals[0], "period": period})
                    out["upper"].append({"ym": ym, "value": vals[2], "period": period})
            if out["point"]:
                return out
    return None


def _parse_imcp_imfbcf(kind: str, pdf_bytes: bytes, pub_date: tuple[int, int, int] | None) -> dict[str, list[dict]] | None:
    """Extrae índice y variación mensual del primer cuadro de la portada."""
    pub_year, pub_month, _ = pub_date or (None, None, None)
    if pub_year is None:
        return None

    text, tables = _pdf_text_first_page(pdf_bytes)

    # El mes/año de referencia suele estar en una frase como "en abril de 2026"
    data_year_month = _extract_data_month(text)
    if data_year_month is None:
        # Fallback: tomar el primer mes que aparezca en el texto y ajustar el año
        months = [m.lower() for m in re.findall(
            r"(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)",
            text.lower())]
        month = MES.get(months[0]) if months else None
        if month is None:
            return None
        data_year, month = _month_year(pub_year, pub_month, month)
        data_year_month = (data_year, month)
    year, month = data_year_month
    ym = f"{year:04d}-{month:02d}"
    period = inegi.ym_to_label(ym, 8)

    index_table = mensual_table = None
    for table in tables:
        flat = " ".join(c for row in table for c in (row or []) if c).replace("\n", " ")
        if kind == "CONSUMO" and ("Consumo" in flat and "privado" in flat and "índice 2018" in flat):
            index_table = table
        if kind == "IMFBCF" and ("Inversión" in flat and "índice 2018" in flat):
            index_table = table
        if "Variación" in flat and "mensual" in flat:
            mensual_table = table
        if index_table and mensual_table:
            break

    if index_table is None or mensual_table is None:
        return None

    index_value = next((_parse_index(c) for row in index_table for c in row if _parse_index(c) is not None), None)
    mensual_value = next((_parse_pct(c) for row in mensual_table for c in row if _parse_pct(c) is not None), None)
    if index_value is None or mensual_value is None:
        return None

    return {
        "index": [{"ym": ym, "value": index_value, "period": period}],
        "mensual": [{"ym": ym, "value": mensual_value / 100.0, "period": period}],
    }


def _parse_emim(pdf_bytes: bytes, pub_date: tuple[int, int, int] | None) -> dict[str, list[dict]] | None:
    """Extrae la variación mensual de la producción desde la portada del boletín EMIM.

    El EMIM no publica el índice de producción en el boletín; por eso este conector
    devuelve solo la columna de variación mensual.
    """
    pub_year, pub_month, _ = pub_date or (None, None, None)
    if pub_year is None:
        return None

    text, tables = _pdf_text_first_page(pdf_bytes)
    data_year_month = _extract_data_month(text)
    if data_year_month is None:
        months = [m.lower() for m in re.findall(
            r"(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)",
            text.lower())]
        month = MES.get(months[0]) if months else None
        if month is None:
            return None
        year, month = _month_year(pub_year, pub_month, month)
    else:
        year, month = data_year_month
    ym = f"{year:04d}-{month:02d}"
    period = inegi.ym_to_label(ym, 8)

    # La tabla de variación mensual de la producción es la que solo tiene la celda
    # 'mensual' y un único porcentaje (la cuarta tabla en la portada).
    for table in (tables or []):
        flat = " ".join(c for row in table for c in (row or []) if c).replace("\n", " ")
        if "mensual" in flat and "anual" not in flat:
            pcts = [p for p in (_parse_pct(c) for row in table for c in row) if p is not None]
            if pcts:
                return {
                    "mensual": [{"ym": ym, "value": pcts[0] / 100.0, "period": period}],
                }
    return None


def _build_item(indicator: str, target_column: int, api_total: list[dict], serie: str, link: str,
                ultimo_valor: float | None = None) -> dict:
    if not api_total:
        raise ValueError(f"{indicator} col{target_column}: sin observaciones")
    last = api_total[-1]
    return {
        "target_column": target_column,
        "api_total": api_total,
        "serie": serie,
        "link": link,
        "metodo": "INEGI boletín PDF",
        "freq": 8,
        "api_meta": {
            "serie": serie, "freq": 8, "unit": None,
            "lastupdate": None, "n_obs": len(api_total),
            "ultimo_valor": round(ultimo_valor if ultimo_valor is not None else last["value"], 6),
            "ultima_ym": last["ym"], "ultima_observacion": last.get("period", last["ym"]),
        },
    }


def _fetch_kind(kind: str, start_year: int, max_bulletins: int = 30) -> list[dict]:
    """Descubre y parsea los últimos boletines de un indicador."""
    this_year = 2026
    issues = _available_issues(kind, start_year, this_year, max_count=max_bulletins)
    if not issues:
        return []

    results = []
    seen_yms = set()
    for year, mm, url in issues[:max_bulletins]:
        try:
            pdf = _req(url)
            text, _ = _pdf_text_first_page(pdf)
            pub_date = _extract_pub_date(text)
            if not pub_date:
                continue
        except Exception as e:  # noqa: BLE001
            continue

        if kind == "IOAE":
            parsed = _parse_ioae(pdf, pub_date)
            if not parsed:
                continue
            for sub, col in (("point", 0), ("lower", 1), ("upper", 2)):
                for o in parsed[sub]:
                    if o["ym"] not in seen_yms:
                        # conservar y reagrupar después
                        results.append(("IOAE", sub, col, o, url))
            for o in parsed["point"]:
                seen_yms.add(o["ym"])

        elif kind in ("CONSUMO", "IMFBCF"):
            parsed = _parse_imcp_imfbcf(kind, pdf, pub_date)
            if not parsed:
                continue
            for sub, col in (("index", 0), ("mensual", 1)):
                for o in parsed[sub]:
                    if o["ym"] not in seen_yms:
                        results.append((kind, sub, col, o, url))
            for o in parsed["index"]:
                seen_yms.add(o["ym"])

        elif kind == "EMIM":
            parsed = _parse_emim(pdf, pub_date)
            if not parsed:
                continue
            for o in parsed["mensual"]:
                if o["ym"] not in seen_yms:
                    results.append(("EMIM", "mensual", 1, o, url))
                    seen_yms.add(o["ym"])

    # Agrupar por indicador y columna
    grouped: dict[str, dict[int, list[dict]]] = {}
    for indicator, sub, col, o, url in results:
        grouped.setdefault(indicator, {}).setdefault(col, []).append((o, url))

    out = []
    for indicator, cols in grouped.items():
        for col in sorted(cols):
            rows = sorted(cols[col], key=lambda x: x[0]["ym"])
            api_total = [r[0] for r in rows]
            link = rows[-1][1]
            out.append(_build_item(indicator, col, api_total, f"{indicator}_pdf", link))
    return out


def fetch(config: dict | None = None, start_year: int = 2024, max_bulletins: int = 18) -> SourceResult:
    """Consulta los boletines oficiales del INEGI y devuelve un SourceResult."""
    warnings: list[str] = []
    if pdfplumber is None:
        warnings.append("inegi_bulletin: pdfplumber no está instalado")
        return SourceResult(False, warnings=warnings)

    data: dict[str, list[dict]] = {}
    for kind in ("IOAE", "CONSUMO", "IMFBCF", "EMIM"):
        try:
            items = _fetch_kind(kind, start_year, max_bulletins)
            if items:
                data.setdefault(kind, []).extend(items)
        except Exception as e:  # noqa: BLE001
            warnings.append(f"inegi_bulletin {kind}: {e}")

    ok = bool(data)
    return SourceResult(ok, data=data, warnings=warnings)
