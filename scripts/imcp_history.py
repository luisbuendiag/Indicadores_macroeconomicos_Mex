"""Extract one consistent vintage of the total IMCP from Banxico's CR362 export."""
from __future__ import annotations

import argparse
import json
import math
import re
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from openpyxl import load_workbook
from sources.base import http_get_bytes
from sources.inegi import label_to_ym

SOURCE = ("https://www.banxico.org.mx/SieInternet/consultarDirectorioInternetAction.do"
          "?accion=consultarCuadro&idCuadro=CR362")
MONTHS = {name: i for i, name in enumerate("Ene Feb Mar Abr May Jun Jul Ago Sep Oct Nov Dic".split(), 1)}
PERIOD = re.compile(r"([A-Za-z]{3}) (\d{4})")
FIRST_MONTH = 1993 * 12
FIELDS = ("indice_desestacionalizado", "mensual_desestacionalizada", "anual_desestacionalizada",
          "anual_original", "acumulada_original", "indice_original")


def export_url(now):
    tz = ZoneInfo("America/Mexico_City")
    local = now.astimezone(tz)
    start = datetime(1993, 1, 1, tzinfo=tz)
    end = datetime(local.year, local.month, 1, tzinfo=tz)
    return SOURCE + "&" + urlencode({"formatoXLS.x": 1, "fechaInicio": int(start.timestamp() * 1000),
                                      "fechaFin": int(end.timestamp() * 1000)})


def read_levels(raw):
    workbook = load_workbook(BytesIO(raw), read_only=True, data_only=True)
    try:
        sheet = workbook.active
        sheet.reset_dimensions()
        months = None
        section = None
        levels = {}
        base_verified = False
        for row in sheet.values:
            if len(row) > 2 and row[2] == "Ene 1993":
                if months is not None:
                    raise ValueError("Encabezado de periodos duplicado en CR362")
                months = []
                for value in row[2:]:
                    match = PERIOD.fullmatch(str(value))
                    if not match or match[1] not in MONTHS:
                        raise ValueError(f"Periodo inválido en CR362: {value!r}")
                    months.append(int(match[2]) * 12 + MONTHS[match[1]] - 1)
            if len(row) < 2 or not isinstance(row[1], str):
                continue
            label = row[1].strip()
            if label.startswith("CR362,") and "2018=100" in label:
                base_verified = True
            if label.endswith("(series originales)"):
                section = "original"
            elif label.endswith("(series desestacionalizadas)"):
                section = "desestacionalizada"
            elif label.endswith("(series de tendencia)"):
                section = None
            elif section and label.startswith("●") and label.removeprefix("●").strip() == "Total":
                values = row[2:]
                if section in levels or not months or len(values) != len(months) or not all(
                    type(v) in (int, float) and math.isfinite(v) and v > 0 for v in values
                ):
                    raise ValueError(f"Niveles del total incompletos o duplicados: {section}")
                levels[section] = values
    finally:
        workbook.close()

    if not base_verified or not months or len(months) <= 12 or set(levels) != {"original", "desestacionalizada"}:
        raise ValueError("CR362 incompleto o sin identificación de base 2018")
    if months != list(range(FIRST_MONTH, FIRST_MONTH + len(months))):
        raise ValueError("El histórico del IMCP tiene meses faltantes o repetidos")
    return months, levels["original"], levels["desestacionalizada"]


def build_history(raw, checked_at):
    months, original, adjusted = read_levels(raw)
    observations = []
    for i, month in enumerate(months):
        year, zero_month = divmod(month, 12)
        start = i - zero_month
        stop = i + 1
        accumulated = None
        if start >= 12:
            accumulated = math.fsum(original[start:stop]) / math.fsum(original[start - 12:stop - 12]) - 1
        observations.append({
            "periodo": f"{year}-{zero_month + 1:02d}",
            "indice_original": original[i],
            "indice_desestacionalizado": adjusted[i],
            "mensual_desestacionalizada": adjusted[i] / adjusted[i - 1] - 1 if i else None,
            "anual_desestacionalizada": adjusted[i] / adjusted[i - 12] - 1 if i >= 12 else None,
            "anual_original": original[i] / original[i - 12] - 1 if i >= 12 else None,
            "acumulada_original": accumulated,
        })
    return {"fuente": SOURCE, "base": "2018=100", "consultado_en": checked_at.isoformat(timespec="seconds"),
            "unidad_variaciones": "fracción", "observaciones": observations}


def for_bulletin(history, indicator):
    """Accept only a snapshot that reaches and corroborates the current bulletin."""
    latest = indicator["last_observation"]
    current = next(row for row in reversed(indicator["observations"]) if row["period"] == latest)
    points = history["observaciones"]
    if points[-1]["periodo"] != label_to_ym(latest):
        raise ValueError("CR362 y el boletín IMCP tienen meses de cierre distintos")
    tolerances = (0.051, 0.00051, 0.00051, 0.00051, 0.00051)
    for field, published, tolerance in zip(FIELDS, current["values"][:5], tolerances):
        if published is not None and not math.isclose(points[-1][field], published, rel_tol=0, abs_tol=tolerance):
            raise ValueError(f"CR362 difiere del boletín IMCP en {field}")
    return {
        "fuente": history["fuente"],
        "base": history["base"],
        "consultado_en": history["consultado_en"],
        "ultimo_periodo": latest,
        "observations": [{"period": p["periodo"], "values": [p[k] for k in FIELDS]} for p in points],
    }


def fetch_for_bulletin(indicator):
    now = datetime.now(timezone.utc)
    return for_bulletin(build_history(http_get_bytes(export_url(now), timeout=20), now), indicator)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archivo", type=Path, help="Exportación XLSX del cuadro CR362")
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    raw = args.archivo.read_bytes() if args.archivo else http_get_bytes(export_url(now), timeout=30)
    print(json.dumps(build_history(raw, now), ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
