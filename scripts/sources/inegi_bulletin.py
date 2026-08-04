"""Conector para boletines oficiales del INEGI publicados en PDF.

Este módulo descarga y parsea los boletines de prensa del INEGI para los
indicadores que no están disponibles directamente en el BIE (o cuyos IDs no se
han podido confirmar en el catálogo BIE-BISE):

  - IOAE: Indicador Oportuno de la Actividad Económica (estimación puntual y
    límites del intervalo de confianza del IGAE).
  - IGAE: Indicador Global de la Actividad Económica (var. mensual y var. anual
    oficiales desde el boletín; el nivel se conserva de la serie BIE).
  - CONSUMO (IMCP): Indicador Mensual del Consumo Privado (índice, var. mensual
    y var. anual).
  - IMFBCF: Indicador Mensual de la Formación Bruta de Capital Fijo (índice,
    var. mensual y var. anual).
  - PIBT: Producto Interno Bruto Trimestral a precios constantes (var. trimestral
    y var. anual desestacionalizadas del PIB y actividades terciarias).
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
    "IGAE": "https://www.inegi.org.mx/contenidos/saladeprensa/boletines/{year}/igae/igae{year}_{mm}.pdf",
    "PIBT": "https://www.inegi.org.mx/contenidos/saladeprensa/boletines/{year}/pibt/pib_Pconst{year}_{mm}.pdf",
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


def _pdf_page_text(pdf_bytes: bytes, page_index: int) -> str:
    """Extrae el texto plano de una página del PDF."""
    if pdfplumber is None:
        return ""
    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        if page_index >= len(pdf.pages):
            return ""
        return pdf.pages[page_index].extract_text() or ""


def _available_issues(kind: str, start_year: int, end_year: int, max_count: int = 200,
                      months: tuple[int, ...] | None = None) -> list[tuple[int, int, str]]:
    """Descubre qué boletines existen en el rango de años, de los más recientes a los más antiguos.

    El parámetro `months` permite restringir la búsqueda a ciertos meses (útil para boletines
    trimestrales como PIBT: febrero, mayo, agosto, noviembre).
    """
    found = []
    month_iter = reversed(months) if months is not None else range(12, 0, -1)
    for year in range(end_year, start_year - 1, -1):
        for mm in month_iter:
            if len(found) >= max_count:
                break
            time.sleep(0.5)
            url = BULLETIN_URLS[kind].format(year=year, mm=f"{mm:02d}")
            if _head_ok(url):
                found.append((year, mm, url))
        if months is not None:
            month_iter = reversed(months)
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
    """Extrae índice, variación mensual y variación anual de la portada.

    Funciona para CONSUMO, IMFBCF y IGAE. El boletín expone tres cuadros
    compactos: índice, variación mensual y variación anual. Sólo se retorna
    el índice cuando tiene sentido para el indicador (CONSUMO/IMFBCF). Para
    IGAE el nivel proviene de la serie BIE, por lo que se ignoran los índices
    desestacionalizados del boletín.
    """
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

    index_table = mensual_table = anual_table = None
    for table in tables:
        flat = " ".join(c for row in table for c in (row or []) if c).replace("\n", " ")
        if kind == "CONSUMO" and ("Consumo" in flat and "privado" in flat and "índice 2018" in flat):
            index_table = table
        if kind == "IMFBCF" and ("Inversión" in flat and "índice 2018" in flat):
            index_table = table
        if kind == "IGAE" and ("IGAE" in flat and "índice 2018" in flat):
            index_table = table
        if "Variación" in flat and "mensual" in flat:
            mensual_table = table
        if "Variación" in flat and "anual" in flat:
            anual_table = table
        if (index_table or kind == "IGAE") and mensual_table and anual_table:
            break

    out: dict[str, list[dict]] = {}

    if mensual_table is None or anual_table is None:
        return None

    mensual_value = next((_parse_pct(c) for row in mensual_table for c in row if _parse_pct(c) is not None), None)
    anual_value = next((_parse_pct(c) for row in anual_table for c in row if _parse_pct(c) is not None), None)
    if mensual_value is None or anual_value is None:
        return None

    if kind in ("CONSUMO", "IMFBCF"):
        if index_table is None:
            return None
        index_value = next((_parse_index(c) for row in index_table for c in row if _parse_index(c) is not None), None)
        if index_value is None:
            return None
        out["index"] = [{"ym": ym, "value": index_value, "period": period}]

    out["mensual"] = [{"ym": ym, "value": mensual_value / 100.0, "period": period}]
    out["anual"] = [{"ym": ym, "value": anual_value / 100.0, "period": period}]
    return out


def _parse_emim(pdf_bytes: bytes, pub_date: tuple[int, int, int] | None) -> dict[str, list[dict]] | None:
    """Extrae índice de producción (Cuadro 2) y variación mensual (portada) del boletín EMIM.

    El boletín 'Indicadores del sector manufacturero' publica:
      - Portada: variación mensual y anual (cifras desestacionalizadas) del volumen de
        la producción manufacturera.
      - Cuadro 2 (cifras originales): índice 2018=100 y variación anual del volumen de
        la producción, personal ocupado, horas trabajadas y remuneraciones.

    Se retorna el índice original (columna 0) y la variación mensual a tasa desestacionalizada
    (columna 1), que es el par habitual del panel de coyuntura.
    """
    pub_year, pub_month, _ = pub_date or (None, None, None)
    if pub_year is None:
        return None

    text, _ = _pdf_text_first_page(pdf_bytes)

    # Descartar boletines antiguos de 'personal/horas/remuneraciones' que no traen producción.
    if "volumen de la producción manufacturera" not in text.lower():
        return None

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

    # Variación mensual del volumen de la producción (frase principal de la portada).
    mensual: float | None = None
    m_head = re.search(
        r"(Aument[oó]|Disminuy[oó]|No present[oó] variaci[oó]n)\s*([0-9.]+)?\s*%?\s*el volumen de la producci[oó]n manufacturera",
        text,
        re.IGNORECASE,
    )
    if m_head:
        verb = m_head.group(1).lower()
        if "no presentó" in verb:
            mensual = 0.0
        else:
            raw = m_head.group(2)
            try:
                sign = -1 if "disminuy" in verb else 1
                mensual = sign * abs(float(raw)) / 100.0
            except (TypeError, ValueError):
                mensual = None

    # Índice de producción 2018=100 y variación anual (Cuadro 2, cifras originales).
    index_value: float | None = None
    anual_value: float | None = None
    for page_index in (3, 4, 5):
        page_text = _pdf_page_text(pdf_bytes, page_index)
        if "31-33" not in page_text or "Industrias manufactureras" not in page_text:
            continue
        m = re.search(
            r"31-33\s+Industrias\s+manufactureras\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)",
            page_text,
        )
        if m:
            idx, var = float(m.group(1)), float(m.group(2))
            # El índice debe estar en un rango razonable (2018=100); si es pequeño
            # o negativo, probablemente la fila solo contiene variaciones porcentuales.
            if idx > 50:
                index_value = idx
                anual_value = var
                break

    if mensual is None:
        return None

    out: dict[str, list[dict]] = {
        "mensual": [{"ym": ym, "value": mensual, "period": period}],
    }
    if index_value is not None:
        out["index"] = [{"ym": ym, "value": index_value, "period": period}]
    if anual_value is not None:
        out["anual"] = [{"ym": ym, "value": anual_value / 100.0, "period": period}]
    return out


def _parse_pibt(pdf_bytes: bytes, pub_date: tuple[int, int, int] | None) -> dict[str, dict[str, dict]] | None:
    """Extrae la variación trimestral y anual desestacionalizada del boletín PIBT.

    Utiliza el 'Cuadro 1' del boletín 'Producto Interno Bruto Trimestral a precios
    constantes' (pib_Pconst{year}_{mm}.pdf).  Devuelve un diccionario con la
    variación trimestral (qoq) y anual (yoy) para PIB y actividades económicas.
    """
    if pub_date is None:
        return None
    pub_year, pub_month, _ = pub_date

    # El Cuadro 1 suele estar en la página 2 (índice 1).
    page_text = _pdf_page_text(pdf_bytes, 1)
    tables = _pdf_page_tables(pdf_bytes, 1)
    if not tables:
        return None

    # Identificar trimestre y año de referencia.
    qmap = {
        "primer": 1, "1er": 1, "1o": 1, "1": 1,
        "segundo": 2, "2o": 2, "2": 2,
        "tercer": 3, "3er": 3, "3o": 3, "3": 3,
        "cuarto": 4, "4o": 4, "4": 4,
    }
    ref = re.search(r"al\s+(.+?)\s+trimestre\s+de\s+(\d{4})", page_text, re.IGNORECASE)
    if not ref:
        # Fallback a la primera página.
        page_text = _pdf_page_text(pdf_bytes, 0)
        ref = re.search(r"al\s+(.+?)\s+trimestre\s+de\s+(\d{4})", page_text, re.IGNORECASE)
    if not ref:
        return None
    qraw = ref.group(1).strip().lower().replace("°", "").replace(".", "")
    qraw = re.sub(r"(\d)(er|o)$", r"\1", qraw)
    quarter = qmap.get(qraw)
    if quarter is None:
        return None
    year = int(ref.group(2))
    month = (quarter - 1) * 3 + 1
    ym = f"{year:04d}-{month:02d}"
    period = inegi.ym_to_label(ym, 4)

    # Buscar la tabla que contiene el encabezado del Cuadro 1.
    data: dict[str, dict[str, float]] = {}
    for table in tables:
        if not table or len(table) < 5:
            continue
        for row in table:
            cells = [c.strip() if c else "" for c in row]
            if not any(cells):
                continue
            label = cells[0]
            if label in ("PIB", "Actividades primarias", "Actividades secundarias", "Actividades terciarias"):
                if len(cells) < 3:
                    continue
                qoq = _parse_pct(cells[1])
                yoy = _parse_pct(cells[2])
                if qoq is not None or yoy is not None:
                    data[label] = {}
                    if qoq is not None:
                        data[label]["qoq"] = qoq
                    if yoy is not None:
                        data[label]["yoy"] = yoy
        if data:
            break

    if not data:
        return None

    out: dict[str, dict[str, dict]] = {"qoq": {}, "yoy": {}}
    for label, vals in data.items():
        if "qoq" in vals:
            out["qoq"][label] = {"ym": ym, "value": vals["qoq"] / 100.0, "period": period}
        if "yoy" in vals:
            out["yoy"][label] = {"ym": ym, "value": vals["yoy"] / 100.0, "period": period}
    return out


def _build_item(indicator: str, target_column: int, api_total: list[dict], serie: str, link: str,
                ultimo_valor: float | None = None, freq: int = 8) -> dict:
    if not api_total:
        raise ValueError(f"{indicator} col{target_column}: sin observaciones")
    last = api_total[-1]
    return {
        "key": indicator,
        "target_column": target_column,
        "api_total": api_total,
        "serie": serie,
        "link": link,
        "metodo": "INEGI boletín PDF",
        "freq": freq,
        "api_meta": {
            "serie": serie, "freq": freq, "unit": None,
            "lastupdate": None, "n_obs": len(api_total),
            "ultimo_valor": round(ultimo_valor if ultimo_valor is not None else last["value"], 6),
            "ultima_ym": last["ym"], "ultima_observacion": last.get("period", last["ym"]),
        },
    }


def _fetch_kind(kind: str, start_year: int, max_bulletins: int = 30) -> list[dict]:
    """Descubre y parsea los últimos boletines de un indicador.

    Mapeo de columnas:
      - CONSUMO:  0 = índice, 1 = var. mensual, 2 = var. anual.
      - IMFBCF:   0 = índice, 1 = var. mensual, 2 = var. anual.
      - IGAE:     3 = var. mensual, 4 = var. anual (el nivel se conserva de BIE).
      - PIBT:     PIB col 2 = qoq, col 3 = yoy;
                  PIBSEC col 3 = qoq terciarias, col 4 = yoy terciarias.
      - IOAE/EMIM: sin cambios.
    """
    this_year = 2026
    # PIBT es trimestral: publicaciones en febrero, mayo, agosto y noviembre.
    months = (2, 5, 8, 11) if kind == "PIBT" else None
    issues = _available_issues(kind, start_year, this_year, max_count=max_bulletins, months=months)
    if not issues:
        return []

    results = []
    seen: set[tuple[str, int, str]] = set()
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
                    if ("IOAE", col, o["ym"]) not in seen:
                        results.append(("IOAE", sub, col, o, url))
                        seen.add(("IOAE", col, o["ym"]))

        elif kind in ("CONSUMO", "IMFBCF"):
            parsed = _parse_imcp_imfbcf(kind, pdf, pub_date)
            if not parsed:
                continue
            for sub, col in (("index", 0), ("mensual", 1), ("anual", 2)):
                for o in parsed[sub]:
                    if (kind, col, o["ym"]) not in seen:
                        results.append((kind, sub, col, o, url))
                        seen.add((kind, col, o["ym"]))

        elif kind == "EMIM":
            parsed = _parse_emim(pdf, pub_date)
            if not parsed:
                continue
            for sub, col in (("index", 0), ("mensual", 1)):
                for o in parsed.get(sub, []):
                    if ("EMIM", col, o["ym"]) not in seen:
                        results.append(("EMIM", sub, col, o, url))
                        seen.add(("EMIM", col, o["ym"]))

        elif kind == "IGAE":
            parsed = _parse_imcp_imfbcf(kind, pdf, pub_date)
            if not parsed:
                continue
            for sub, col in (("mensual", 3), ("anual", 4)):
                for o in parsed[sub]:
                    if ("IGAE", col, o["ym"]) not in seen:
                        results.append(("IGAE", sub, col, o, url))
                        seen.add(("IGAE", col, o["ym"]))

        elif kind == "PIBT":
            parsed = _parse_pibt(pdf, pub_date)
            if not parsed:
                continue
            # PIB total: qoq en col 2, yoy en col 3.
            o_qoq = parsed.get("qoq", {}).get("PIB")
            o_yoy = parsed.get("yoy", {}).get("PIB")
            if o_qoq and ("PIB", 2, o_qoq["ym"]) not in seen:
                results.append(("PIB", "qoq", 2, o_qoq, url))
                seen.add(("PIB", 2, o_qoq["ym"]))
            if o_yoy and ("PIB", 3, o_yoy["ym"]) not in seen:
                results.append(("PIB", "yoy", 3, o_yoy, url))
                seen.add(("PIB", 3, o_yoy["ym"]))
            # Terciarias: qoq en col 3, yoy en col 4.
            o_qoq = parsed.get("qoq", {}).get("Actividades terciarias")
            o_yoy = parsed.get("yoy", {}).get("Actividades terciarias")
            if o_qoq and ("PIBSEC", 3, o_qoq["ym"]) not in seen:
                results.append(("PIBSEC", "qoq_ter", 3, o_qoq, url))
                seen.add(("PIBSEC", 3, o_qoq["ym"]))
            if o_yoy and ("PIBSEC", 4, o_yoy["ym"]) not in seen:
                results.append(("PIBSEC", "yoy_ter", 4, o_yoy, url))
                seen.add(("PIBSEC", 4, o_yoy["ym"]))

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
            freq = 4 if indicator in ("PIB", "PIBSEC") else 8
            out.append(_build_item(indicator, col, api_total, f"{indicator}_pdf", link, freq=freq))
    return out


def fetch(config: dict | None = None, start_year: int = 2024, max_bulletins: int = 18) -> SourceResult:
    """Consulta los boletines oficiales del INEGI y devuelve un SourceResult."""
    warnings: list[str] = []
    if pdfplumber is None:
        warnings.append("inegi_bulletin: pdfplumber no está instalado")
        return SourceResult(False, warnings=warnings)

    data: dict[str, list[dict]] = {}
    for kind in ("IOAE", "IGAE", "CONSUMO", "IMFBCF", "EMIM", "PIBT"):
        try:
            items = _fetch_kind(kind, start_year, max_bulletins)
            for it in (items or []):
                key = it.get("key") or kind
                data.setdefault(key, []).append(it)
        except Exception as e:  # noqa: BLE001
            warnings.append(f"inegi_bulletin {kind}: {e}")

    ok = bool(data)
    return SourceResult(ok, data=data, warnings=warnings)
