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

import csv
import re
import time
import urllib.error
import urllib.request
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any

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
    "IMAI": "https://www.inegi.org.mx/contenidos/saladeprensa/boletines/{year}/imai/imai{year}_{mm}.pdf",
    "PIBT": "https://www.inegi.org.mx/contenidos/saladeprensa/boletines/{year}/pibt/pib_Pconst{year}_{mm}.pdf",
    "EOPIBT": [
        "https://www.inegi.org.mx/contenidos/saladeprensa/boletines/{year}/pibo/pib_eo{year}_{mm}.pdf",
        "https://www.inegi.org.mx/contenidos/saladeprensa/boletines/{year}/pib_eo/pib_eo{year}_{mm}.pdf",
    ],
    "INPC": "https://www.inegi.org.mx/contenidos/saladeprensa/boletines/{year}/inpc/inpc_2q{year}_{mm}.pdf",
    "EMOE": "https://www.inegi.org.mx/contenidos/saladeprensa/boletines/{year}/ee/ee{year}_{mm}.pdf",
    "IOOE": "https://www.inegi.org.mx/contenidos/saladeprensa/boletines/{year}/iooe/IOE{year}_{mm}.pdf",
    "BCMM": "https://www.inegi.org.mx/contenidos/saladeprensa/boletines/{year}/comext_o/balcom_o{year}_{mm}.pdf",
}

# Mapeo de claves del dashboard a los productos de boletines.
KEY_TO_KIND = {
    "PIB": "EOPIBT",
    "PIBSEC": "PIBT",
    "IGAE": "IGAE",
    "IMAI": "IMAI",
    "BCMM": "BCMM",
    "DESOCUP": "IOOE",
    "INPC": "INPC",
    "CONSUMO": "CONSUMO",
    "IMFBCF": "IMFBCF",
    "IOAE": "IOAE",
    "EMIM": "EMIM",
    "EMOE": "EMOE",
}

# Nombres oficiales del producto de Sala de Prensa, para el mapeo.
PRODUCTO_NOMBRE = {
    "PIB": "Estimación Oportuna del Producto Interno Bruto Trimestral (EOPIBT)",
    "PIBSEC": "Producto Interno Bruto por sector de actividad (PIBT)",
    "IGAE": "Indicador Global de la Actividad Económica",
    "IMAI": "Indicador Mensual de la Actividad Industrial",
    "BCMM": "Balanza Comercial de Mercancías de México",
    "DESOCUP": "Indicadores de Ocupación y Empleo (ENOE / IOOE)",
    "INPC": "Índice Nacional de Precios al Consumidor",
    "CONSUMO": "Indicador Mensual del Consumo Privado",
    "IMFBCF": "Indicador Mensual de la Formación Bruta de Capital Fijo",
    "IOAE": "Indicador Oportuno de la Actividad Económica",
    "EMIM": "Encuesta Mensual de la Industria Manufacturera",
    "EMOE": "Encuesta Mensual de Opinión Empresarial",
}

# Alias de producto para la validación por contenido.
PRODUCTO_ALIASES = {
    "INPC": ("ÍNDICE NACIONAL DE PRECIOS", "INPC"),
    "EMOE": ("ENCUESTA MENSUAL DE OPINIÓN EMPRESARIAL", "EMOE"),
    "IOOE": ("ENCUESTA NACIONAL DE OCUPACIÓN", "ENOE", "IOOE", "DESOCUPACIÓN"),
    "BCMM": ("BALANZA COMERCIAL", "BCMM"),
    "IGAE": ("INDICADOR GLOBAL", "IGAE"),
    "IMAI": ("INDICADOR MENSUAL DE LA ACTIVIDAD INDUSTRIAL", "IMAI"),
    "CONSUMO": ("INDICADOR MENSUAL DEL CONSUMO PRIVADO", "IMCP"),
    "IMFBCF": ("INDICADOR MENSUAL DE LA FORMACIÓN BRUTA", "IMFBCF"),
    "IOAE": ("INDICADOR OPORTUNO", "IOAE", "IGAE"),
    "EMIM": ("ENCUESTA MENSUAL DE LA INDUSTRIA MANUFACTURERA", "EMIM"),
    "PIBT": ("PRODUCTO INTERNO BRUTO", "PIB"),
    "EOPIBT": ("PRODUCTO INTERNO BRUTO", "PIB", "ESTIMACIÓN OPORTUNA"),
}

MES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sep": 9, "oct": 10, "nov": 11, "dic": 12,
}

MESES_NOMBRE = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


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


def _format_pub_date(pub_date: tuple[int, int, int] | None) -> str | None:
    """Convierte (año, mes, día) a texto legible."""
    if not pub_date:
        return None
    year, month, day = pub_date
    if 1 <= month <= 12:
        return f"{day} de {MESES_NOMBRE[month - 1]} de {year}"
    return None


def _extract_bulletin_number(text: str) -> str | None:
    m = re.search(r"BOLETÍN DE INDICADOR\s+(\d+(?:/\d+)?)", text, re.IGNORECASE)
    if m:
        return m.group(1)
    return None


def _extract_bulletin_meta(text: str, pub_date: tuple[int, int, int] | None) -> dict:
    return {
        "numero_boletin": _extract_bulletin_number(text),
        "fecha_publicacion": _format_pub_date(pub_date),
        "tipo_documento": "PDF",
    }


def _parse_pct(text) -> float | None:
    if not isinstance(text, str):
        return None
    text = text.replace("%", "").replace("▲", "").replace("▼", "").strip()
    if not text:
        return None
    text = text.replace("(-)", "-")
    text = text.replace("(", "").replace(")", "")
    text = text.replace("−", "-")
    text = text.replace(",", ".")
    text = re.sub(r"\s+", "", text)
    if text == "-" or not text:
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


def _body_text(text: str) -> str:
    """Descarta la portada (título, número de boletín, fecha de publicación,
    página y próxima publicación) y conserva el cuerpo donde aparece el periodo
    de referencia."""
    # Eliminar todo antes de "Página 1/N" y, si existe, la línea de próxima publicación.
    m = re.search(r"Página\s+1/\d+\s*\n", text)
    if m:
        body = text[m.end():]
    else:
        body = text
    m = re.search(r"Próxima publicación[\s:].*?\n", body)
    if m:
        body = body[m.end():]
    return body.strip()


def _extract_ref_period(text: str) -> tuple[int, int] | None:
    """Extrae el periodo de referencia del boletín.

    Busca expresiones mensuales (con preposiciones variadas) y trimestrales en
    el cuerpo del boletín, evitando la fecha de publicación de la portada.
    Para trimestrales devuelve el mes de inicio del trimestre.
    """
    body = _body_text(text)

    # Trimestral: primer/segundo/tercer/cuarto trimestre de <año>
    trim_map = {"primer": 1, "segundo": 2, "tercer": 3, "cuarto": 4}
    m = re.search(r"\b(primer|segundo|tercer|cuarto)\s+trimestre\s+de\s+(\d{4})\b", body, re.IGNORECASE)
    if m:
        q = trim_map[m.group(1).lower()]
        year = int(m.group(2))
        month = (q - 1) * 3 + 1
        return year, month

    # Mensual: en/para/al/durante <mes> de <año>
    m = re.search(r"(?:en|para|al|durante)\s+([a-zA-Záéíóúñ]+)\s+de\s+(\d{4})(?:\D|$)", body, re.IGNORECASE)
    if m:
        try:
            return int(m.group(2)), MES[m.group(1).lower()]
        except KeyError:
            pass

    # Fallback: <mes> de <año> con asegura de no estar en una nota al pie (ej. "mayo de 20261/")
    m = re.search(r"\b(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s+de\s+(\d{4})(?:\D|$)", body, re.IGNORECASE)
    if m:
        try:
            return int(m.group(2)), MES[m.group(1).lower()]
        except KeyError:
            pass
    return None


def _extract_pub_date(text: str) -> tuple[int, int, int] | None:
    m = re.search(r"(\d{1,2})\s+de\s+([a-zA-Záéíóúñ]+)\s+de\s+(\d{4})", text, re.IGNORECASE)
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
    templates = BULLETIN_URLS[kind]
    if isinstance(templates, str):
        templates = [templates]
    month_iter = reversed(months) if months is not None else range(12, 0, -1)
    for year in range(end_year, start_year - 1, -1):
        for mm in month_iter:
            if len(found) >= max_count:
                break
            for url_tmpl in templates:
                time.sleep(0.5)
                url = url_tmpl.format(year=year, mm=f"{mm:02d}")
                if _head_ok(url):
                    found.append((year, mm, url))
                    break
            else:
                # El boletín de enero de 2023 publicó el 4T-2022 con el año
                # de referencia en el nombre (pib_eo2022_01.pdf) en lugar del
                # año de publicación.
                if kind == "EOPIBT" and mm == 1:
                    time.sleep(0.5)
                    url = f"https://www.inegi.org.mx/contenidos/saladeprensa/boletines/{year}/pib_eo/pib_eo{year - 1}_{mm:02d}.pdf"
                    if _head_ok(url):
                        found.append((year, mm, url))
        if months is not None:
            month_iter = reversed(months)
    return found


def _ioae_month_year(pdf_bytes: bytes, ref_month: int, pub_year: int, pub_month: int) -> tuple[int, int]:
    """Para IOAE el boletín publica 1 o 2 meses después del mes de referencia."""
    return _month_year(pub_year, pub_month, ref_month)


def _parse_ioae(pdf_bytes: bytes, pub_date: tuple[int, int, int] | None) -> dict[str, list[dict]] | None:
    """Extrae la variación mensual y anual del IGAE y su intervalo de confianza.

    El boletín incluye:
      - Página 1: un cuadro resumen con 'anual' y 'mensual' para el IGAE.
      - Página 2: un cuadro Nowcast con la estimación mensual y los límites
        inferior/superior del intervalo de confianza.
    Se descartan las filas de actividades secundarias/terciarias y el cuadro de
    niveles (índices) para no mezclar conceptos.
    """
    pub_year, pub_month, _ = pub_date or (None, None, None)
    if pub_year is None:
        return None

    tables = _pdf_page_tables(pdf_bytes, 0) + _pdf_page_tables(pdf_bytes, 1)
    ref_month: int | None = None
    anual: float | None = None
    mensual: float | None = None
    lower: float | None = None
    upper: float | None = None

    # 1) Cuadro resumen (anual / mensual)
    for table in tables:
        for i, row in enumerate(table):
            cells = [c.strip() if c else "" for c in row]
            if len(cells) < 2:
                continue
            if not ("anual" in cells[0].lower() and "mensual" in cells[1].lower()):
                continue
            if i + 1 >= len(table):
                continue
            val_row = table[i + 1]
            if len(val_row) < 2:
                continue
            anual_val = _parse_pct(val_row[0])
            mensual_val = _parse_pct(val_row[1])
            if anual_val is None or mensual_val is None:
                continue
            anual = anual_val
            mensual = mensual_val
            # Buscar el mes de referencia en las filas anteriores
            for j in range(i, -1, -1):
                for c in table[j]:
                    if c and c.lower() in MES:
                        ref_month = MES[c.lower()]
                        break
                if ref_month:
                    break
            break
        if mensual is not None:
            break

    # 2) Cuadro Nowcast (mensual + intervalo de confianza)
    # El boletín incluye un cuadro Nowcast anual y otro mensual con el mismo
    # encabezado; seleccionamos la fila de IGAE cuyo punto coincida con la
    # variación mensual del resumen, y descartamos el cuadro de niveles.
    best_match: tuple[float, float, float, int, str] | None = None
    for table in tables:
        if not table or len(table) < 3:
            continue
        header = [c.strip() if c else "" for c in table[0]]
        if not any("Concepto" in h for h in header) or not any("Nowcast" in h for h in header):
            continue

        current_concept = ""
        for row in table:
            cells = [c.strip() if c else "" for c in row]
            if not any(cells):
                continue
            if cells[0]:
                current_concept = cells[0]
            if current_concept != "IGAE":
                continue
            month_text = next((c for c in cells if c.lower() in MES), "")
            if not month_text:
                continue
            nums = [_parse_pct(c) for c in cells if _parse_pct(c) is not None]
            if len(nums) < 3:
                continue
            # Descartar cuadro de niveles (índices ~100)
            if abs(nums[0]) > 20:
                continue
            ref_m = MES[month_text.lower()]
            point, lo, hi = nums[0], nums[1], nums[2]
            # Si tenemos la variación mensual del resumen, preferimos coincidencia exacta
            if mensual is not None:
                if round(point, 1) == round(mensual, 1):
                    lower, upper = lo, hi
                    if ref_month is None:
                        ref_month = ref_m
                    break
            else:
                # Sin resumen, elegir el IGAE con menor punto (mensual vs. anual)
                if best_match is None or abs(point) < abs(best_match[0]):
                    best_match = (point, lo, hi, ref_m, month_text)
        if mensual is not None and lower is not None:
            break

    if best_match and lower is None:
        point, lo, hi, ref_m, _ = best_match
        if mensual is None:
            mensual = point
        lower, upper = lo, hi
        if ref_month is None:
            ref_month = ref_m

    # 3) Formato antiguo (2024 aprox): una sola tabla con múltiples periodos
    # y las columnas IGAE (Inferior, Nowcast, Superior) para variaciones anuales
    # y mensuales en una misma fila.
    if mensual is None or anual is None or lower is None:
        for table in tables:
            if not table or len(table) < 3:
                continue
            header = [c.strip() if c else "" for c in table[0]]
            if not any("Periodo" in h and "referencia" in h for h in header):
                continue
            subheader = [c.strip() if c else "" for c in table[1]]
            is_annual = any("Nowcast1/" in h for h in subheader)
            data_row = table[2]
            if len(data_row) < 4:
                continue
            periods = [p.strip() for p in data_row[0].replace("\r", "\n").split("\n") if p.strip()]
            parts = []
            for col in (1, 2, 3):
                raw = (data_row[col] or "").replace("\r", "\n").split("\n")
                parts.append([_parse_pct(p.strip().replace("*", "")) for p in raw if p.strip()])
            if not all(parts) or not all(len(v) == len(periods) for v in parts):
                continue
            idx = len(periods) - 1
            m = re.search(r"([a-zA-Záéíóúñ]+)\s+de\s+(\d{4})", periods[idx], re.IGNORECASE)
            if not m:
                continue
            ref_m = MES.get(m.group(1).lower())
            if ref_m is None:
                continue
            point, lo, hi = parts[1][idx], parts[0][idx], parts[2][idx]
            if point is None or lo is None or hi is None:
                continue
            if is_annual:
                anual = point
            else:
                mensual = point
                lower, upper = lo, hi
            ref_month = ref_m

    if mensual is None or anual is None:
        return None

    year, month = _ioae_month_year(pdf_bytes, ref_month or pub_month - 1, pub_year, pub_month)
    ym = f"{year:04d}-{month:02d}"
    period = inegi.ym_to_label(ym, 8)
    return {
        "mensual": [{"ym": ym, "value": mensual, "period": period}],
        "anual": [{"ym": ym, "value": anual, "period": period}],
        "lower": [{"ym": ym, "value": lower, "period": period}],
        "upper": [{"ym": ym, "value": upper, "period": period}],
    }


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
        if kind == "IMAI" and ("Actividad industrial" in flat and "índice 2018" in flat):
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

    if kind in ("CONSUMO", "IMFBCF", "IMAI"):
        if index_table is None:
            return None
        index_value = next((_parse_index(c) for row in index_table for c in row if _parse_index(c) is not None), None)
        if index_value is None:
            return None
        out["index"] = [{"ym": ym, "value": index_value, "period": period}]

    out["mensual"] = [{"ym": ym, "value": mensual_value / 100.0, "period": period}]
    out["anual"] = [{"ym": ym, "value": anual_value / 100.0, "period": period}]
    return out


def _parse_imai_bulletin(pdf_bytes: bytes, pub_date: tuple[int, int, int] | None) -> dict[str, list[dict]] | None:
    """Extrae del boletín IMAI: nivel, variaciones, anual original, acumulado y
    variaciones anuales desestacionalizadas de los cuatro sectores.

    Página 1 (índice 0): resumen + Cuadro 1 con componentes (desest. mensual/anual).
    Página 4 (índice 3): Cuadro 2 con variaciones anuales y acumuladas en cifras
    originales.
    """
    pub_year, pub_month, _ = pub_date or (None, None, None)
    if pub_year is None:
        return None

    text = _pdf_page_text(pdf_bytes, 0) or ""
    data_year_month = _extract_data_month(text) or _extract_ref_period(text)
    if data_year_month is None:
        return None
    year, month = data_year_month
    ym = f"{year:04d}-{month:02d}"
    period = inegi.ym_to_label(ym, 8)

    # 1) Nivel, mensual y anual del agregado desde la portada.
    page0_tables = _pdf_page_tables(pdf_bytes, 0)
    index_table = mensual_table = anual_table = None
    for table in page0_tables:
        flat = " ".join(c for row in table for c in (row or []) if c).replace("\n", " ")
        if ("Actividad industrial" in flat and "índice 2018" in flat) or ("industrial" in flat and "índice 2018" in flat):
            index_table = table
        if "Variación" in flat and "mensual" in flat:
            mensual_table = table
        if "Variación" in flat and "anual" in flat:
            anual_table = table

    index_value = next((_parse_index(c) for row in (index_table or []) for c in row if _parse_index(c) is not None), None)
    mensual_value = next((_parse_pct(c) for row in (mensual_table or []) for c in row if _parse_pct(c) is not None), None)
    anual_value = next((_parse_pct(c) for row in (anual_table or []) for c in row if _parse_pct(c) is not None), None)

    if mensual_value is None or anual_value is None or index_value is None:
        return None

    out: dict[str, list[dict]] = {
        "index": [{"ym": ym, "value": index_value, "period": period}],
        "mensual": [{"ym": ym, "value": mensual_value / 100.0, "period": period}],
        "anual": [{"ym": ym, "value": anual_value / 100.0, "period": period}],
    }

    # 2) Componentes del Cuadro 1 (página 2, índice 1).
    page1_tables = _pdf_page_tables(pdf_bytes, 1)
    comp_map = {
        "minería": 10,
        "energía": 11,
        "construcción": 12,
        "manufactureras": 13,
    }
    comp_values_anual: dict[str, float] = {}
    comp_values_mensual: dict[str, float] = {}
    for table in page1_tables:
        for row in table:
            # La etiqueta puede estar en la primera o segunda columna por celdas combinadas.
            label = ""
            for c in row[:2]:
                if c:
                    label = c.strip().lower()
                    break
            # Cuadro 1 publica mensual y anual desestacionalizadas; la primera
            # columna de porcentajes es la mensual y la segunda la anual.
            pcts = [_parse_pct(c) for c in row[2:] if c and _parse_pct(c) is not None]
            if len(pcts) >= 1:
                for key in ("minería", "energía", "construcción", "manufactureras"):
                    if key in label and key not in comp_values_mensual:
                        comp_values_mensual[key] = pcts[0] / 100.0
                        if len(pcts) >= 2:
                            comp_values_anual[key] = pcts[-1] / 100.0

    for key, col in comp_map.items():
        if key in comp_values_anual:
            out[key] = [{"ym": ym, "value": comp_values_anual[key], "period": period}]
        if key in comp_values_mensual:
            out[f"{key}_mensual"] = [{"ym": ym, "value": comp_values_mensual[key], "period": period}]

    # 3) Anual original y acumulado del Cuadro 2 (página 4, índice 3).
    page4_tables = _pdf_page_tables(pdf_bytes, 3)
    orig_anual = acumulado = None
    for table in page4_tables:
        for row in table:
            label = (row[0] or "").strip().lower() if row and len(row) > 0 else ""
            if "actividad industrial" in label and "sectores" not in label:
                nums = [_parse_pct(c) for c in row[1:] if c and _parse_pct(c) is not None]
                if len(nums) >= 2:
                    orig_anual = nums[0] / 100.0
                    acumulado = nums[1] / 100.0
                    break
        if orig_anual is not None:
            break

    if orig_anual is not None:
        out["original_anual"] = [{"ym": ym, "value": orig_anual, "period": period}]
    if acumulado is not None:
        out["acumulado"] = [{"ym": ym, "value": acumulado, "period": period}]

    return out


# Regex para el boletín EMIM.
_EMIM_CUADRO2_CODE_RE = re.compile(r"\b(3\d{2})\b")
_EMIM_CUADRO2_TOTAL_RE = re.compile(r"\b31[-–]33\b")
_EMIM_EXCLUDE_CODES = {"318", "319", "320"}


def _emim_is_num(cell) -> bool:
    """Verifica si una celda de tabla representa un valor numérico."""
    if cell is None:
        return False
    s = (cell if isinstance(cell, str) else str(cell)).strip()
    s = s.replace("\u2212", "-").replace(",", ".")
    s = s.replace("▲", "").replace("▼", "")
    if not s or s == "-":
        return False
    try:
        float(s)
        return True
    except (TypeError, ValueError):
        return False


def _emim_to_float(cell) -> float | None:
    """Convierte una celda a float, normalizando signos."""
    if cell is None:
        return None
    s = (cell if isinstance(cell, str) else str(cell)).strip()
    s = s.replace("\u2212", "-").replace(",", ".")
    s = s.replace("▲", "").replace("▼", "")
    if not s or s == "-":
        return None
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _emim_parse_pct(cell) -> float | None:
    """Convierte un porcentaje del boletín a fracción."""
    v = _parse_pct(cell)
    return v / 100.0 if v is not None else None


def _emim_ref_period(pdf_bytes: bytes) -> tuple[int, int] | None:
    """Periodo de referencia del boletín (portada o Cuadro 2)."""
    for page_index in (0, 3):
        text = _pdf_page_text(pdf_bytes, page_index)
        if not text:
            continue
        data_year_month = _extract_data_month(text)
        if data_year_month is not None:
            return data_year_month
    return None


def _emim_ref_period_fallback(pdf_bytes: bytes, pub_year: int,
                              pub_month: int) -> tuple[int, int] | None:
    """Usa el primer mes encontrado en la portada y la fecha de publicación."""
    text = _pdf_page_text(pdf_bytes, 0)
    if not text:
        return None
    months = re.findall(
        r"(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)",
        text.lower())
    if not months:
        return None
    month = MES.get(months[0])
    if month is None:
        return None
    return _month_year(pub_year, pub_month, month)


def _emim_find_cuadro1_table(tables: list[list[list[str]]]) -> list[list[str]] | None:
    """Elige la tabla del Cuadro 1 con los indicadores agregados."""
    for t in tables:
        for r in t:
            text = " ".join(c for c in r if c and c.strip()).lower()
            if "volumen físico de la producción" in text:
                return t
    return None


def _parse_emim_cuadro1(pdf_bytes: bytes) -> dict[str, dict[str, float]]:
    """Extrae del Cuadro 1 las variaciones mensuales y anuales desestacionalizadas.

    Retorna {variable: {mensual, anual}} en escala fraccionaria.
    """
    tables = _pdf_page_tables(pdf_bytes, 2)
    table = _emim_find_cuadro1_table(tables)
    if table is None and tables:
        # Fallback: buscar en cualquier página con la marca Cuadro 1.
        for i in (1, 2, 3, 4):
            for t in _pdf_page_tables(pdf_bytes, i):
                if any("volumen físico de la producción" in " ".join(c for c in r if c).lower()
                       for r in t):
                    table = t
                    break
            if table is not None:
                break

    out: dict[str, dict[str, float]] = {}
    if not table:
        return out

    labels = [
        ("produccion", "volumen físico de la producción"),
        ("personal", "personal ocupado total"),
        ("horas", "horas trabajadas por el personal ocupado total"),
        ("remuneraciones", "remuneraciones medias reales pagadas"),
    ]

    for r in table:
        text = " ".join(c for c in r if c and c.strip()).lower()
        text = re.sub(r"\s+", " ", text).replace("1/", "")
        nums = [_emim_to_float(c) for c in r if _emim_is_num(c)]
        if len(nums) < 2:
            continue
        for key, pat in sorted(labels, key=lambda x: -len(x[1])):
            if pat in text and key not in out:
                out[key] = {"mensual": nums[0] / 100.0, "anual": nums[1] / 100.0}
                break
    return out


def _emim_pop_code(label: str, nums: list[str]) -> tuple[str | None, str, list[str]]:
    """Separa el código SCIAN del nombre y los 8 valores del Cuadro 2."""
    # Total de industrias manufactureras.
    m = _EMIM_CUADRO2_TOTAL_RE.search(label)
    if m:
        code = "31-33"
        name = re.sub(r"\s+", " ", label[:m.start()] + label[m.end():]).strip()
        return code, name, nums

    # Código 3 dígitos dentro del nombre.
    m = _EMIM_CUADRO2_CODE_RE.search(label)
    if m and m.group(1) not in _EMIM_EXCLUDE_CODES:
        code = m.group(1)
        name = re.sub(r"\s+", " ", label[:m.start()] + label[m.end():]).strip()
        return code, name, nums

    # Código como primer valor numérico.
    if nums:
        first = nums[0].strip()
        if _EMIM_CUADRO2_CODE_RE.match(first) and first not in _EMIM_EXCLUDE_CODES:
            return first, label, nums[1:]

    return None, label, nums


def _parse_emim_cuadro2(pdf_bytes: bytes) -> tuple[dict[str, float] | None, dict[str, dict]]:
    """Extrae del Cuadro 2 el total y el desglose por subsector.

    Retorna (total, subsectores). total es un dict con los 8 valores agregados;
    subsectores es {código: {nombre, ...}}. Las variaciones anuales originales
    se devuelven como fracciones.
    """
    tables = _pdf_page_tables(pdf_bytes, 3)
    if not tables:
        return None, {}

    table = tables[0]
    # Buscar la primera fila de datos (la que contiene '31-33' o datos numéricos).
    start = 0
    for i, r in enumerate(table):
        if any("31" in (c or "") and "33" in (c or "") for c in r):
            start = i
            break
        nums = [c for c in r if _emim_is_num(c)]
        if len(nums) >= 8:
            start = i
            break

    total: dict[str, float] | None = None
    subsectores: dict[str, dict] = {}
    current: dict | None = None

    for r in table[start:]:
        texts = [c.strip() for c in r if c and c.strip() and not _emim_is_num(c)]
        nums = [c for c in r if _emim_is_num(c)]
        if len(nums) >= 8:
            if current:
                label = " ".join(current["parts"]).replace("\n", " ")
                code, name, vals = _emim_pop_code(label, current["nums"])
                if code == "31-33" and len(vals) == 8:
                    total = _emim_build_total(vals)
                elif code and len(vals) == 8:
                    subsectores[code] = _emim_build_subsector(code, name, vals)
            current = {"parts": texts, "nums": nums}
        elif current and texts:
            current["parts"].extend(texts)

    if current:
        label = " ".join(current["parts"]).replace("\n", " ")
        code, name, vals = _emim_pop_code(label, current["nums"])
        if code == "31-33" and len(vals) == 8:
            total = _emim_build_total(vals)
        elif code and len(vals) == 8:
            subsectores[code] = _emim_build_subsector(code, name, vals)

    return total, subsectores


def _emim_build_total(vals: list[str]) -> dict[str, float]:
    """Construye el dict del total del Cuadro 2."""
    v = [_emim_to_float(x) for x in vals]
    return {
        "produccion_index": v[0],
        "produccion_anual_orig": _emim_parse_pct(vals[1]),
        "personal_index": v[2],
        "personal_anual_orig": _emim_parse_pct(vals[3]),
        "horas_index": v[4],
        "horas_anual_orig": _emim_parse_pct(vals[5]),
        "remuneraciones_index": v[6],
        "remuneraciones_anual_orig": _emim_parse_pct(vals[7]),
    }


def _emim_build_subsector(code: str, name: str, vals: list[str]) -> dict:
    """Construye el dict de un subsector del Cuadro 2."""
    v = [_emim_to_float(x) for x in vals]
    return {
        "nombre": name,
        "produccion_index": v[0],
        "produccion_anual": _emim_parse_pct(vals[1]),
        "personal_index": v[2],
        "personal_anual": _emim_parse_pct(vals[3]),
        "horas_index": v[4],
        "horas_anual": _emim_parse_pct(vals[5]),
        "remuneraciones_index": v[6],
        "remuneraciones_anual": _emim_parse_pct(vals[7]),
    }


def _parse_emim(pdf_bytes: bytes, pub_date: tuple[int, int, int] | None) -> dict[str, Any] | None:
    """Extrae del boletín EMIM las cuatro dimensiones: producción, personal,
    horas trabajadas y remuneraciones medias reales.

    Fuentes dentro del boletín:
      - Cuadro 1 (cifras desestacionalizadas): variación mensual y anual
        oficial de las cuatro variables.
      - Cuadro 2 (cifras originales): índice 2018=100 y variación anual original
        de las cuatro variables, desglosado por subsector (311-339, excepto 318-320).

    Se retornan listas de observaciones para las 18 columnas del indicador y un
    diccionario 'subsectores' con el desglose por subsector.
    """
    pub_year, pub_month, _ = pub_date or (None, None, None)
    if pub_year is None:
        return None

    data_year_month = _emim_ref_period(pdf_bytes)
    if data_year_month is None:
        data_year_month = _emim_ref_period_fallback(pdf_bytes, pub_year, pub_month)
    if data_year_month is None:
        return None

    year, month = data_year_month
    ym = f"{year:04d}-{month:02d}"
    period = inegi.ym_to_label(ym, 8)

    # Cifras desestacionalizadas oficiales (Cuadro 1).
    cuadro1 = _parse_emim_cuadro1(pdf_bytes)
    if not cuadro1:
        return None

    # Cifras originales e índices por subsector (Cuadro 2).
    total, subsectores = _parse_emim_cuadro2(pdf_bytes)

    def _obs(value: float | None) -> list[dict]:
        if value is None:
            return []
        return [{"ym": ym, "value": value, "period": period}]

    out: dict[str, Any] = {
        "produccion_index": _obs(total["produccion_index"] if total else None),
        "produccion_mensual_desest": _obs(cuadro1.get("produccion", {}).get("mensual")),
        "produccion_anual_desest": _obs(cuadro1.get("produccion", {}).get("anual")),
        "produccion_anual_orig": _obs(total["produccion_anual_orig"] if total else None),
        "personal_index": _obs(total["personal_index"] if total else None),
        "personal_mensual_desest": _obs(cuadro1.get("personal", {}).get("mensual")),
        "personal_anual_desest": _obs(cuadro1.get("personal", {}).get("anual")),
        "personal_anual_orig": _obs(total["personal_anual_orig"] if total else None),
        "horas_index": _obs(total["horas_index"] if total else None),
        "horas_mensual_desest": _obs(cuadro1.get("horas", {}).get("mensual")),
        "horas_anual_desest": _obs(cuadro1.get("horas", {}).get("anual")),
        "horas_anual_orig": _obs(total["horas_anual_orig"] if total else None),
        "remuneraciones_index": _obs(total["remuneraciones_index"] if total else None),
        "remuneraciones_mensual_desest": _obs(cuadro1.get("remuneraciones", {}).get("mensual")),
        "remuneraciones_anual_desest": _obs(cuadro1.get("remuneraciones", {}).get("anual")),
        "subsectores": subsectores,
    }
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

    # Cuadro 2: variación anual por sectores de actividad (1T-26 y revisión).
    out["subsectores"] = _parse_pibt_subsectores(pdf_bytes)
    return out


def _parse_pibt_subsectores(pdf_bytes: bytes) -> dict[str, float] | None:
    """Extrae la variación anual al 1er trimestre de 2026 del Cuadro 2 (página 4).

    Devuelve un diccionario {nombre_del_sector: fracción} con la variación anual
    real publicada para el trimestre más reciente.  El Cuadro 2 presenta
    histórico anual y trimestral; la última columna numérica de cada fila
    corresponde al 1er trimestre del año de referencia.
    """
    if pdfplumber is None:
        return None
    try:
        tables = _pdf_page_tables(pdf_bytes, 3)
    except Exception:  # noqa: BLE001
        return None
    if not tables:
        return None

    # Cabecera del Cuadro 2 ocupa las primeras filas; buscamos las filas de datos.
    data: dict[str, float] = {}
    for table in tables:
        if not table or len(table) < 7:
            continue
        # Localiza la primera fila de datos (comienza con "PIB total").
        start = 0
        for i, r in enumerate(table):
            first = (r[0] or "").strip().lower().replace("\n", " ")
            if first.startswith("pib total"):
                start = i
                break
        if start == 0:
            continue
        # Procesa las filas a partir del bloque de datos.
        label_parts: list[str] = []
        pending: str | None = None
        for r in table[start:]:
            first = (r[0] or "").strip().replace("\n", " ")
            values = [v for v in r[1:] if v not in (None, "")]
            if values:
                if first:
                    _store_pibt_subsector(data, label_parts, pending)
                    label_parts = [first]
                    try:
                        data[first] = float(values[-1]) / 100.0
                    except (ValueError, TypeError):
                        pass
                    label_parts = []
                    pending = None
                else:
                    pending = values[-1]
            else:
                if first:
                    label_parts.append(first)
        _store_pibt_subsector(data, label_parts, pending)
        if data:
            break
    return data or None


def _store_pibt_subsector(data: dict[str, float], label_parts: list[str], pending: str | None) -> None:
    if pending is not None and label_parts:
        label = " ".join(label_parts).strip()
        if not label:
            return
        try:
            data[label] = float(pending) / 100.0
        except (ValueError, TypeError):
            pass


def _extract_proxima_publicacion(text: str) -> str | None:
    m = re.search(
        r"Próxima publicación:\s*(\d{1,2}\s+de\s+[a-zA-Záéíóúñ]+\s+de\s+\d{4})",
        text,
        re.IGNORECASE,
    )
    if not m:
        return None
    return m.group(1).lower().replace("  ", " ")


def _normalize_eopibt_tables(tables: list[list[list[str]]]) -> list[list[str]]:
    """Aplana y normaliza tablas de pdfplumber, dividiendo celdas multilínea."""
    if not tables:
        return []
    out: list[list[str]] = []
    for table in tables:
        for row in table:
            if not row:
                continue
            parts = [((c or "").strip() if c is not None else "").split("\n") for c in row]
            max_len = max(len(p) for p in parts) if parts else 1
            for i in range(max_len):
                new_row = [p[i].strip() if i < len(p) else "" for p in parts]
                out.append(new_row)
    return out


def _is_eopibt_total_row(first: str) -> bool:
    if not first:
        return False
    is_total = ("pib" in first or "producto interno bruto" in first)
    is_specific = any(s in first for s in ("total", "oportuno", "bruto"))
    is_sector = any(s in first for s in ("primarias", "secundarias", "terciarias"))
    return is_total and is_specific and not is_sector


def _is_eopibt_sector_row(first: str) -> str | None:
    if not first:
        return None
    for name in ("primarias", "secundarias", "terciarias"):
        if name in first:
            return name
    return None


def _extract_eopibt_ref(text: str) -> tuple[int, int] | None:
    """Identifica el trimestre y año de referencia del boletín."""
    qmap = {
        "primer": 1, "1er": 1, "1o": 1, "1": 1,
        "segundo": 2, "2o": 2, "2": 2,
        "tercer": 3, "3er": 3, "3o": 3, "3": 3,
        "cuarto": 4, "4o": 4, "4": 4,
    }
    text_l = text.lower()
    # Prefiere expresiones tipo "al/durante/en el primer trimestre de 2024".
    m = re.search(r"(?:al|durante(?: el)?|en(?: el)?)\s+(primer|segundo|tercer|cuarto|\d)(?:o|er|°)?\s*trimestre\s+de\s+(\d{4})", text_l, re.IGNORECASE)
    if not m:
        m = re.search(r"(primer|segundo|tercer|cuarto|\d)(?:o|er|°)?\s*trimestre\s+de\s+(\d{4})", text_l, re.IGNORECASE)
    if not m:
        return None
    raw = m.group(1).lower().replace("°", "").replace(".", "")
    q = qmap.get(raw)
    if q is None:
        return None
    return q, int(m.group(2))


def _extract_eopibt_split_tables(tables: list[list[list[str]]]) -> tuple[list[float | None] | None, dict[str, dict[str, float | None]]]:
    """Respaldar boletines `pibo` 2025+ donde el cuadro de portada se fragmenta en tablas pequeñas."""
    qoq: float | None = None
    yoy: float | None = None
    ytd: float | None = None
    sectores: dict[str, dict[str, float | None]] = {}

    for table in tables:
        if not table:
            continue
        labels = []
        for row in table:
            first = (row[0] or "").strip().lower()
            if first:
                labels.append(first)
        label = None
        for lab in labels:
            if _is_eopibt_total_row(lab) or _is_eopibt_sector_row(lab):
                label = lab
                break
        if not label:
            continue

        vals: list[float] = []
        for row in reversed(table):
            if len(row) >= 2:
                v0 = _parse_pct(row[0])
                v1 = _parse_pct(row[1])
                if v0 is not None and v1 is not None:
                    vals = [v0, v1]
                    break
        if len(vals) < 2:
            continue

        if _is_eopibt_total_row(label):
            qoq, yoy = vals[0], vals[1]
        else:
            sector = _is_eopibt_sector_row(label)
            if sector:
                sectores[sector] = {"qoq": vals[0] / 100.0, "yoy": vals[1] / 100.0}

    if qoq is None and yoy is None:
        return None, {}
    return [qoq, yoy, ytd], sectores


def _extract_eopibt_values(tables: list[list[list[str]]]) -> tuple[list[float | None] | None, dict[str, dict[str, float | None]]]:
    """Extrae qoq, yoy, acumulado y sectores de las tablas del boletín."""
    rows = _normalize_eopibt_tables(tables)
    pib_idx = -1
    pib_vals: list[float] = []
    for i, row in enumerate(rows):
        if _is_eopibt_total_row(row[0].lower()):
            candidate: list[float] = []
            for cell in row[1:]:
                for sub in cell.split("\n"):
                    v = _parse_pct(sub)
                    if v is not None:
                        candidate.append(v)
            if len(candidate) >= 2:
                pib_idx = i
                pib_vals = candidate
                break

    if pib_idx < 0:
        return _extract_eopibt_split_tables(tables)

    qoq = pib_vals[0]
    yoy = pib_vals[1]
    ytd = pib_vals[2] if len(pib_vals) > 2 else None

    sectores: dict[str, dict[str, float | None]] = {}
    sector_order = ["primarias", "secundarias", "terciarias"]
    order_idx = 0
    for i in range(pib_idx + 1, min(pib_idx + 8, len(rows))):
        row = rows[i]
        first = (row[0] or "").strip().lower()
        if first and not _is_eopibt_total_row(first) and not _is_eopibt_sector_row(first) and not _is_eopibt_total_row("pib " + first):
            break
        sector_name = _is_eopibt_sector_row(first)
        if sector_name is None and first == "" and order_idx < 3:
            sector_name = sector_order[order_idx]
            order_idx += 1
        elif sector_name is None:
            continue
        else:
            while order_idx < 3 and sector_order[order_idx] != sector_name:
                order_idx += 1
            if order_idx < 3:
                order_idx += 1

        svals: list[float] = []
        for cell in row[1:]:
            for sub in cell.split("\n"):
                v = _parse_pct(sub)
                if v is not None:
                    svals.append(v)
        if svals:
            sectores[sector_name] = {
                "qoq": svals[0] / 100.0 if len(svals) > 0 and svals[0] is not None else None,
                "yoy": svals[1] / 100.0 if len(svals) > 1 and svals[1] is not None else None,
            }

    if qoq is None and yoy is None:
        return _extract_eopibt_split_tables(tables)
    return [qoq, yoy, ytd], sectores


def _parse_eopibt_yoy_orig(pdf_bytes: bytes, year: int, quarter: int) -> float | None:
    """Extrae la variación anual con cifras originales del Cuadro 2 (página 3)."""
    for table in _pdf_page_tables(pdf_bytes, 2):
        pib_row: list[str] | None = None
        header_start = -1
        for i, row in enumerate(table):
            cells = [(c or "").strip() for c in row]
            if not any(cells):
                continue
            if "PIB y actividades" in cells[0]:
                header_start = max(0, i - 1)
            if cells[0] == "PIB":
                pib_row = cells
                break
        if not pib_row or header_start < 0:
            continue
        header_rows = table[header_start:header_start + 3]
        if not header_rows:
            continue

        ncols = max(len(r) for r in header_rows)

        # Localizar la primera columna del año de referencia en la primera fila de encabezado.
        top_row = header_rows[0]
        year_col: int | None = None
        for j, cell in enumerate(top_row):
            if cell and re.search(rf"\b{year}", str(cell)):
                year_col = j
                break
        if year_col is None:
            continue

        # El grupo del año se extiende hasta la siguiente columna que inicie otro año.
        def _year_in_cell(cell):
            m = re.search(r"\b(\d{4})", str(cell or ""))
            return int(m.group(1)) if m else None

        group_end = ncols
        for j in range(year_col + 1, ncols):
            if j < len(top_row) and top_row[j]:
                ycell = _year_in_cell(top_row[j])
                if ycell is not None and ycell != year:
                    group_end = j
                    break

        col_info: list[str] = []
        for j in range(ncols):
            parts = []
            for hrow in header_rows:
                if j < len(hrow):
                    parts.append(str(hrow[j] or ""))
            col_info.append(" ".join(parts))

        for j in range(year_col, min(group_end, len(pib_row))):
            m = re.search(r"(\d+)[\.\s]*(?:°|er|o|do|ndo)", col_info[j], re.IGNORECASE)
            if m and int(m.group(1)) == quarter:
                val = _parse_pct(pib_row[j])
                if val is not None:
                    return val
    return None


def _parse_eopibt(pdf_bytes: bytes, pub_date: tuple[int, int, int] | None) -> dict[str, Any] | None:
    """Extrae la variación del boletín de Estimación Oportuna del PIBT (EOPIBT).

    El boletín 'pib_eo{year}_{mm}.pdf' publica cifras preliminares con:
      - Cuadro 1 (página 2): variación trimestral (qoq), anual desestacionalizada
        (yoy) y acumulado del PIB oportuno.
      - Cuadro 2 (página 3): variación anual original del PIB.
      - Portada: próxima publicación y desglose por actividad económica.
    No contiene nivel del PIB.
    """
    text = _pdf_text_first_page(pdf_bytes)[0]
    for i in (1, 2, 3):
        text += "\n" + _pdf_page_text(pdf_bytes, i)

    if pub_date is None:
        pub_date = _extract_pub_date(text)

    ref = _extract_eopibt_ref(text)
    if not ref:
        return None
    quarter, year = ref
    month = (quarter - 1) * 3 + 1
    ym = f"{year:04d}-{month:02d}"
    period = inegi.ym_to_label(ym, 4) + " P"

    proxima = _extract_proxima_publicacion(text)

    # Extrae qoq, yoy desestacionalizada, acumulado y sectores de todas las
    # páginas, ya que el boletín publica el Cuadro 1 en página 1, 2 o 3 según
    # la época.
    qoq: float | None = None
    yoy_desest: float | None = None
    ytd: float | None = None
    ytd_label: str | None = "acumulado"
    sectores: dict[str, dict[str, float | None]] = {}

    tables: list[list[list[str]]] = []
    for i in range(4):
        tables.extend(_pdf_page_tables(pdf_bytes, i) or [])

    main_vals, parsed_sectores = _extract_eopibt_values(tables)
    if main_vals is None:
        return None
    qoq, yoy_desest, ytd = main_vals
    sectores = parsed_sectores

    # Cuadro 2 (página 3): variación anual original.
    yoy_orig = _parse_eopibt_yoy_orig(pdf_bytes, year, quarter)

    out: dict[str, Any] = {}
    if qoq is not None:
        out.setdefault("qoq", {})["PIB"] = {"ym": ym, "value": qoq / 100.0, "period": period}
    if yoy_desest is not None:
        out.setdefault("yoy", {})["PIB"] = {"ym": ym, "value": yoy_desest / 100.0, "period": period}
    if yoy_orig is not None:
        out.setdefault("yoy_orig", {})["PIB"] = {"ym": ym, "value": yoy_orig / 100.0, "period": period}
    if ytd is not None:
        out.setdefault("ytd", {})["PIB"] = {"ym": ym, "value": ytd / 100.0, "period": period, "label": ytd_label or "acumulado"}
    if sectores:
        out["sectores"] = sectores
    if proxima:
        out["proxima_publicacion"] = proxima
    return out if out else None


def _build_item(indicator: str, target_column: int, api_total: list[dict], serie: str, link: str,
                url_meta: dict[str, tuple[str, tuple[int, int, int] | None]] | None = None,
                ultimo_valor: float | None = None, freq: int = 8, kind: str = "",
                extra: dict | None = None) -> dict:
    if not api_total:
        raise ValueError(f"{indicator} col{target_column}: sin observaciones")
    last = api_total[-1]
    text, pub_date = "", None
    if url_meta and link in url_meta:
        text, pub_date = url_meta[link]
    meta = _extract_bulletin_meta(text, pub_date)
    item = {
        "key": indicator,
        "target_column": target_column,
        "api_total": api_total,
        "serie": serie,
        "link": link,
        "metodo": "INEGI boletín PDF",
        "freq": freq,
        "url_boletin_oficial": link,
        "periodo_boletin": last.get("period", last["ym"]),
        "numero_boletin": meta["numero_boletin"],
        "fecha_publicacion": meta["fecha_publicacion"],
        "tipo_documento": meta["tipo_documento"],
        "producto_boletin": PRODUCTO_NOMBRE.get(indicator, kind),
        "boletin_validado": True,
        "api_meta": {
            "serie": serie, "freq": freq, "unit": None,
            "lastupdate": None, "n_obs": len(api_total),
            "ultimo_valor": round(ultimo_valor if ultimo_valor is not None else last["value"], 6),
            "ultima_ym": last["ym"], "ultima_observacion": last.get("period", last["ym"]),
        },
    }
    if extra:
        item.update(extra)
    return item


def _eopibt_opendata_rows() -> list[tuple[str, int, int, dict, str]]:
    """Descarga los datos abiertos EOPIBT trimestrales y emite observaciones de respaldo.

    El archivo CSV (Anexo 2) contiene la variación anual original y desestacionalizada
    del Producto Interno Bruto Oportuno de 2015-T1 a 2023-T2. Se usa únicamente para
    llenar los trimestres 2015-T1 a 2015-T3 donde no hay boletín, y como respaldo de
    la serie anual original (col 2) cuando el boletín no publica esa cifra.
    """
    url = "https://www.inegi.org.mx/contenidos/programas/pibo/2013/datosabiertos/eopibt_trimestral_csv.zip"
    try:
        pdf_bytes = _req(url)
        with zipfile.ZipFile(BytesIO(pdf_bytes)) as zf:
            name = next((n for n in zf.namelist() if "anexo2trimestral" in n.lower() and n.endswith(".csv")), None)
            if not name:
                return []
            data = zf.read(name).decode("utf-8-sig")
    except Exception:  # noqa: BLE001
        return []

    rows = list(csv.reader(data.splitlines()))
    if not rows or len(rows) < 2:
        return []
    headers = rows[0]
    desest_idx = next((i for i, r in enumerate(rows) if r and "desestacionalizada" in r[0].lower() and "producto interno bruto" in r[0].lower() and "actividades" not in r[0].lower()), None)
    orig_idx = next((i for i, r in enumerate(rows) if r and "originales" in r[0].lower() and "producto interno bruto" in r[0].lower() and "actividades" not in r[0].lower()), None)
    if desest_idx is None or orig_idx is None:
        return []

    out: list[tuple[str, int, int, dict, str]] = []
    for col, h in enumerate(headers[1:], start=1):
        m = re.match(r"(\d{4})\|T(\d)", h)
        if not m:
            continue
        year, quarter = int(m.group(1)), int(m.group(2))
        month = (quarter - 1) * 3 + 1
        ym = f"{year:04d}-{month:02d}"
        period = inegi.ym_to_label(ym, 4) + " P"
        v_desest = _parse_pct(rows[desest_idx][col])
        v_orig = _parse_pct(rows[orig_idx][col])
        if v_desest is not None:
            out.append(("PIB", "yoy", 1, {"ym": ym, "value": v_desest / 100.0, "period": period}, url))
        if v_orig is not None:
            out.append(("PIB", "yoy_orig", 2, {"ym": ym, "value": v_orig / 100.0, "period": period}, url))
    return out


def _fetch_kind(kind: str, start_year: int, max_bulletins: int = 30) -> list[dict]:
    """Descubre y parsea los últimos boletines de un indicador.

    Mapeo de columnas:
      - CONSUMO:  0 = índice, 1 = var. mensual, 2 = var. anual.
      - IMFBCF:   0 = índice, 1 = var. mensual, 2 = var. anual.
      - IGAE:     1 = var. mensual desestacionalizada (el nivel y la var. anual se calculan desde la serie BIE).
      - PIBT:     PIBSEC col 3/4 = qoq/yoy terciarias;
                  col 5 = nivel PIB (BIE); col 6/7 = qoq/yoy PIB total;
                  col 8/9 = qoq/yoy primarias; col 10/11 = qoq/yoy secundarias.
      - IOAE/EMIM: sin cambios.
    """
    this_year = 2026
    # EOPIBT requiere histórico desde 2016 para disponer de al menos 5 años.
    if kind == "EOPIBT":
        start_year = 2016
        max_bulletins = max(max_bulletins, 60)
    # PIBT es trimestral: publicaciones en febrero, mayo, agosto y noviembre.
    # EOPIBT es trimestral: publicaciones en enero, abril, julio y octubre.
    if kind == "PIBT":
        months = (2, 5, 8, 11)
    elif kind == "EOPIBT":
        months = (1, 4, 7, 10)
    else:
        months = None
    issues = _available_issues(kind, start_year, this_year, max_count=max_bulletins, months=months)
    if not issues:
        return []

    results = []
    url_meta: dict[str, tuple[str, tuple[int, int, int] | None]] = {}
    parsed_by_url: dict[str, dict] = {}
    seen: set[tuple[str, int, str]] = set()
    for year, mm, url in issues[:max_bulletins]:
        try:
            pdf = _req(url)
            text, _ = _pdf_text_first_page(pdf)
            pub_date = _extract_pub_date(text)
            if not pub_date:
                continue
            url_meta[url] = (text, pub_date)
        except Exception as e:  # noqa: BLE001
            continue

        if kind == "IOAE":
            parsed = _parse_ioae(pdf, pub_date)
            if not parsed:
                continue
            for sub, col in (("mensual", 0), ("anual", 1), ("lower", 2), ("upper", 3)):
                for o in parsed[sub]:
                    if ("IOAE", col, o["ym"]) not in seen:
                        results.append(("IOAE", sub, col, o, url))
                        seen.add(("IOAE", col, o["ym"]))

        elif kind == "IMAI":
            parsed = _parse_imai_bulletin(pdf, pub_date)
            if not parsed:
                continue
            col_map = {
                "index": 0,
                "mensual": 1,
                "anual": 2,
                "original_anual": 4,
                "acumulado": 5,
                "minería": 10,
                "energía": 11,
                "construcción": 12,
                "manufactureras": 13,
                "minería_mensual": 14,
                "energía_mensual": 15,
                "construcción_mensual": 16,
                "manufactureras_mensual": 17,
            }
            for sub, col in col_map.items():
                for o in parsed.get(sub, []):
                    if ("IMAI", col, o["ym"]) not in seen:
                        results.append(("IMAI", sub, col, o, url))
                        seen.add(("IMAI", col, o["ym"]))

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
            emim_col_map = {
                "produccion_index": 0,
                "produccion_mensual_desest": 3,
                "produccion_anual_desest": 4,
                "produccion_anual_orig": 2,
                "personal_index": 5,
                "personal_mensual_desest": 8,
                "personal_anual_desest": 9,
                "personal_anual_orig": 7,
                "horas_index": 10,
                "horas_mensual_desest": 13,
                "horas_anual_desest": 14,
                "horas_anual_orig": 12,
                "remuneraciones_index": 15,
                "remuneraciones_mensual_desest": 16,
                "remuneraciones_anual_desest": 17,
            }
            for sub, col in emim_col_map.items():
                for o in parsed.get(sub, []):
                    if ("EMIM", col, o["ym"]) not in seen:
                        results.append(("EMIM", sub, col, o, url))
                        seen.add(("EMIM", col, o["ym"]))
            if "subsectores" in parsed:
                parsed_by_url[url] = {"subsectores": parsed["subsectores"]}

        elif kind == "IGAE":
            parsed = _parse_imcp_imfbcf(kind, pdf, pub_date)
            if not parsed:
                continue
            # Sólo la variación mensual desestacionalizada del boletín (col 1).
            # La variación anual original se calcula en build_data.py desde los índices BIE.
            for sub, col in (("mensual", 1),):
                for o in parsed[sub]:
                    if ("IGAE", col, o["ym"]) not in seen:
                        results.append(("IGAE", sub, col, o, url))
                        seen.add(("IGAE", col, o["ym"]))

        elif kind == "PIBT":
            parsed = _parse_pibt(pdf, pub_date)
            if not parsed:
                continue
            # Mapeo de columnas para PIBSEC: 12 columnas.
            # 0-2 niveles de actividades (BIE); 3-4 variaciones terciarias;
            # 5 nivel PIB (BIE); 6-7 variaciones PIB total;
            # 8-9 variaciones primarias; 10-11 variaciones secundarias.
            pibt_map = {
                ("qoq", "PIB", 6),
                ("yoy", "PIB", 7),
                ("qoq", "Actividades primarias", 8),
                ("yoy", "Actividades primarias", 9),
                ("qoq", "Actividades secundarias", 10),
                ("yoy", "Actividades secundarias", 11),
                ("qoq", "Actividades terciarias", 3),
                ("yoy", "Actividades terciarias", 4),
            }
            for sub, label, col in pibt_map:
                o = parsed.get(sub, {}).get(label)
                if o and ("PIBSEC", col, o["ym"]) not in seen:
                    results.append(("PIBSEC", f"{sub}_{label}", col, o, url))
                    seen.add(("PIBSEC", col, o["ym"]))
            # Guarda los subsectores del Cuadro 2 (último boletín procesado).
            if "subsectores" in parsed:
                parsed_by_url[url] = {"subsectores": parsed["subsectores"]}

        elif kind == "EOPIBT":
            parsed = _parse_eopibt(pdf, pub_date)
            if not parsed:
                continue
            # PIB oportuno:
            #   col 0 = variación trimestral desestacionalizada (qoq)
            #   col 1 = variación anual desestacionalizada (yoy)
            #   col 2 = variación anual original (yoy_orig)
            #   col 3 = acumulado / año
            o_qoq = parsed.get("qoq", {}).get("PIB")
            o_yoy = parsed.get("yoy", {}).get("PIB")
            o_yoy_orig = parsed.get("yoy_orig", {}).get("PIB")
            o_ytd = parsed.get("ytd", {}).get("PIB")
            if o_qoq and ("PIB", 0, o_qoq["ym"]) not in seen:
                results.append(("PIB", "qoq", 0, o_qoq, url))
                seen.add(("PIB", 0, o_qoq["ym"]))
            if o_yoy and ("PIB", 1, o_yoy["ym"]) not in seen:
                results.append(("PIB", "yoy", 1, o_yoy, url))
                seen.add(("PIB", 1, o_yoy["ym"]))
            if o_yoy_orig and ("PIB", 2, o_yoy_orig["ym"]) not in seen:
                results.append(("PIB", "yoy_orig", 2, o_yoy_orig, url))
                seen.add(("PIB", 2, o_yoy_orig["ym"]))
            if o_ytd and ("PIB", 3, o_ytd["ym"]) not in seen:
                results.append(("PIB", "ytd", 3, o_ytd, url))
                seen.add(("PIB", 3, o_ytd["ym"]))
            # Guardar metadatos adicionales (próxima publicación y sectores)
            # para agregarlos al item que use el boletín más reciente.
            extra = {}
            if "proxima_publicacion" in parsed:
                extra["proxima_publicacion"] = parsed["proxima_publicacion"]
            if "sectores" in parsed:
                extra["sectores"] = parsed["sectores"]
            if extra:
                parsed_by_url[url] = extra

    if kind == "EOPIBT":
        # Rellena los trimestres 2015-T1 a 2015-T3 con los datos abiertos oficiales
        # (la serie publicada hasta 2023-T2) y sirve de respaldo para yoy_orig.
        for row in _eopibt_opendata_rows():
            key, sub, col, o, url = row
            if (key, col, o["ym"]) not in seen:
                results.append(row)
                seen.add((key, col, o["ym"]))

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
            extra = parsed_by_url.get(link)
            out.append(_build_item(indicator, col, api_total, f"{indicator}_pdf", link,
                                   url_meta=url_meta, freq=freq, kind=kind, extra=extra))
    return out


def fetch(config: dict | None = None, start_year: int = 2021, max_bulletins: int = 30) -> SourceResult:
    """Consulta los boletines oficiales del INEGI y devuelve un SourceResult."""
    warnings: list[str] = []
    if pdfplumber is None:
        warnings.append("inegi_bulletin: pdfplumber no está instalado")
        return SourceResult(False, warnings=warnings)

    data: dict[str, list[dict]] = {}
    for kind in ("IOAE", "IGAE", "CONSUMO", "IMFBCF", "IMAI", "EMIM", "PIBT", "EOPIBT"):
        # EOPIBT ahora conserva histórico disponible para una serie coherente
        # de variaciones (qoq, yoy, yoy_orig, acumulado).
        try:
            items = _fetch_kind(kind, start_year, max_bulletins)
            for it in (items or []):
                key = it.get("key") or kind
                data.setdefault(key, []).append(it)
        except Exception as e:  # noqa: BLE001
            warnings.append(f"inegi_bulletin {kind}: {e}")

    ok = bool(data)
    return SourceResult(ok, data=data, warnings=warnings)


def discover_bulletin_url(key: str, period: str | None, start_year: int = 2024,
                          max_search: int = 18) -> dict | None:
    """Descubre la URL del boletín oficial del INEGI para un periodo validado.

    No extrae datos de series; solo valida existencia, dominio oficial,
    indicador correcto y periodo de referencia.  Útil para alimentar
    `url_boletin_oficial` independientemente de si los valores vienen del BIE.
    """
    if not period:
        return None
    ym = inegi.label_to_ym(period)
    if not ym:
        return None
    kind = KEY_TO_KIND.get(key)
    if not kind or kind not in BULLETIN_URLS:
        return None
    # PIB/PIBSEC son trimestrales; el resto mensuales.
    freq = 4 if key in ("PIB", "PIBSEC") else 8
    year, month = int(ym.split("-")[0]), int(ym.split("-")[1])
    this_year = 2026
    issues: list[tuple[int, int, str]] = []
    templates = BULLETIN_URLS[kind]
    if isinstance(templates, str):
        templates = [templates]
    for y in range(this_year, start_year - 1, -1):
        for m in range(12, 0, -1):
            if len(issues) >= max_search:
                break
            for url_tmpl in templates:
                url = url_tmpl.format(year=y, mm=f"{m:02d}")
                if _head_ok(url):
                    issues.append((y, m, url))
                    break

    ref_label = inegi.ym_to_label(ym, freq=freq)
    for y, m, url in issues:
        try:
            text, _ = _pdf_text_first_page(_req(url))
        except Exception:  # noqa: BLE001
            continue
        if not text:
            continue
        # Validación de dominio/URL ya está implícita en BULLETIN_URLS.
        # Validación de indicador correcto.
        titulo = text[:500].upper()
        ok_producto = True
        if kind in PRODUCTO_ALIASES:
            ok_producto = any(alias in titulo for alias in PRODUCTO_ALIASES[kind])
        if not ok_producto:
            continue
        # Validación de periodo de referencia.
        data_ym = _extract_ref_period(text)
        if data_ym:
            data_label = inegi.ym_to_label(f"{data_ym[0]:04d}-{data_ym[1]:02d}", freq=freq)
            if data_label == ref_label or ref_label.startswith(data_label):
                pub = _extract_pub_date(text)
                meta = _extract_bulletin_meta(text, pub)
                return {
                    "url": url,
                    "periodo": ref_label,
                    "fecha_publicacion": meta["fecha_publicacion"],
                    "numero_boletin": meta["numero_boletin"],
                    "tipo_documento": "PDF",
                    "producto_boletin": PRODUCTO_NOMBRE.get(key, PRODUCTO_NOMBRE.get(kind, kind)),
                    "metodo": f"INEGI descubrimiento automático ({kind})",
                }
    return None
