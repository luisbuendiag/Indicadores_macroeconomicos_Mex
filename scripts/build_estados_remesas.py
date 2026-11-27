"""Build the Panorama Estatal remittances payload from Banxico's CE100 export."""
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

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ("https://www.banxico.org.mx/SieInternet/consultarDirectorioInternetAction.do"
          "?accion=consultarCuadro&idCuadro=CE100")
QUARTERS = {"Ene-Mar": 1, "Abr-Jun": 2, "Jul-Sep": 3, "Oct-Dic": 4}
PERIOD = re.compile(r"(Ene-Mar|Abr-Jun|Jul-Sep|Oct-Dic) (\d{4})")


def export_url(now):
    local = now.astimezone(ZoneInfo("America/Mexico_City"))
    start = datetime(2003, 1, 1, tzinfo=local.tzinfo)
    end = datetime(local.year, 3 * ((local.month - 1) // 3) + 1, 1, tzinfo=local.tzinfo)
    return SOURCE + "&" + urlencode({"formatoXLS.x": 1, "fechaInicio": int(start.timestamp() * 1000),
                                      "fechaFin": int(end.timestamp() * 1000)})


def read_series(workbook_bytes, entities):
    workbook = load_workbook(BytesIO(workbook_bytes), read_only=True, data_only=True)
    try:
        sheet = workbook.active
        # The official export declares A1:A1 even when the worksheet has data.
        sheet.reset_dimensions()
        rows = iter(sheet.values)
        for row in rows:
            if len(row) > 2 and isinstance(row[2], str) and PERIOD.fullmatch(row[2]):
                headers = row[2:]
                break
        else:
            raise ValueError("El cuadro CE100 no tiene encabezados trimestrales")

        periods = []
        for header in headers:
            match = PERIOD.fullmatch(str(header))
            if not match:
                raise ValueError(f"Encabezado trimestral no reconocido: {header!r}")
            periods.append((int(match[2]), QUARTERS[match[1]]))
        serial = [year * 4 + quarter for year, quarter in periods]
        if periods[0] != (2003, 1) or serial != list(range(serial[0], serial[-1] + 1)):
            raise ValueError("El historial trimestral CE100 está incompleto o duplicado")

        by_name = {entity[field]: entity["clave"] for entity in entities
                   for field in ("nombre", "nombre_oficial")}
        series = {}
        for row in rows:
            if len(row) < 2 or not isinstance(row[1], str) or "●" not in row[1]:
                continue
            name = row[1].split("●", 1)[1].strip()
            key = "00" if name == "TOTAL" else by_name.get(name)
            if key is None or key in series:
                raise ValueError(f"Entidad desconocida o duplicada en CE100: {name}")
            values = row[2:]
            if len(values) != len(periods) or not all(
                    type(value) in (int, float) and math.isfinite(value) and value >= 0 for value in values):
                raise ValueError(f"Observaciones incompletas en CE100: {name}")
            series[key] = values
    finally:
        workbook.close()

    if set(series) != {"00", *(f"{code:02d}" for code in range(1, 33))}:
        raise ValueError("CE100 debe incluir las 32 entidades y el total nacional")
    for i, period in enumerate(periods):
        value = math.fsum(values[i] for key, values in series.items() if key != "00")
        if not math.isclose(value, series["00"][i], rel_tol=0, abs_tol=0.001):
            raise ValueError(f"Las remesas estatales no cuadran con el total: {period}")
    return periods, series


def build_remesas(catalog, workbook_bytes, checked_at):
    entities = sorted(catalog["entidades"], key=lambda item: item["clave"])
    if [entity["clave"] for entity in entities] != [f"{code:02d}" for code in range(1, 33)]:
        raise ValueError("El catálogo debe contener las 32 claves estatales")
    periods, series = read_series(workbook_bytes, entities)
    labels = [f"{quarter}T-{year}" for year, quarter in periods]
    national = series["00"][-1]
    ranked = sorted((series[e["clave"]][-1] for e in entities), reverse=True)

    def indicator(key):
        values = series[key]
        prior = values[-5] if len(values) >= 5 else None
        return {"valor": values[-1], "var": 100 * (values[-1] / prior - 1) if prior else None,
                "serie": list(zip(labels, values))}

    output = []
    for entity in entities:
        data = indicator(entity["clave"])
        data.update(part=100 * data["valor"] / national if national else None,
                    lugar=ranked.index(data["valor"]) + 1)
        output.append({**entity, "ind": {"REMESAS": data}})
    return {
        "version": 1, "estado": "oficial", "actualizado": checked_at.isoformat(timespec="seconds"),
        "indicadores": [{
            "clave": "REMESAS", "nombre": "Ingresos por remesas", "sigla": "Remesas",
            "fuente": "Banco de México (SIE, CE100)", "url_fuente": SOURCE,
            "medida": "Flujo trimestral en millones de dólares. Cifras preliminares.",
            "periodo": labels[-1], "formato": "mdd", "escala": "secuencial",
            "lugar_por": "monto", "estatus": "oficial",
        }],
        "nacional": {"REMESAS": indicator("00")}, "entidades": output,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--archivo", type=Path, help="Use a locally saved CE100 export")
    args = parser.parse_args()
    catalog = json.loads((args.root / "config/estados.json").read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc)
    raw = args.archivo.read_bytes() if args.archivo else http_get_bytes(export_url(now), timeout=30)
    print(json.dumps(build_remesas(catalog, raw, now), ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
