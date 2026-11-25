"""Official ETEF, ENOE and IMSS tables for the 32 state profiles."""
from __future__ import annotations

import calendar
import io
import re
from pathlib import Path
import json

import pdfplumber

from build_estados_itaee import MESES, TRIMESTRES, _plano
from build_estados_remesas import http_get_bytes

INEGI = "https://www.inegi.org.mx/contenidos/saladeprensa/boletines"
IMSS = "https://www.imss.gob.mx/sites/all/statics/pdf/informes/afiliacion"
DECIMAL = r"[-−]?\d+(?: \d{3})*\.\d+"
INTEGER = r"(?:\d{1,3}(?:[ ,]\d{3}){1,2}|\d+)"
IMSS_INTEGER = r"[-−]?(?:\d{1,3}(?:,\d{3})+|\d+)"
RATES = ("Participación", "Desocupación", "Informalidad laboral (TIL1)")


def num(token):
    return float(token.replace(" ", "").replace(",", "").replace("−", "-"))


def table(pdf, selector):
    with pdfplumber.open(io.BytesIO(pdf)) as document:
        for page in document.pages:
            source = page.extract_text(layout=True) or ""
            if selector(_plano(source)):
                return source
    raise ValueError("No se encontró el cuadro oficial esperado")


def rows(text, catalog, pattern, *, national, aliases=None):
    names = {"00": national}
    names.update({e["clave"]: e["nombre_oficial"] for e in catalog["entidades"]})
    for code, name in (aliases or {}).items():
        names[code] = name
    lines = "\n".join(_plano(line).strip() for line in text.splitlines())
    result = {}
    for code, name in names.items():
        match = re.search(r"(?m)^" + re.escape(_plano(name)) + r"(?: *\d/)? +" + pattern + r"(?: |$)", lines)
        if match is None:
            raise ValueError(f"Faltan cifras para {name}")
        result[code] = tuple(num(v) for v in match.groups())
    if len(result) != 33:
        raise ValueError("Se esperaban 32 entidades y el agregado nacional")
    return result


def quarter(text):
    plain = _plano(text)
    match = re.search(r"(primer|segundo|tercer|cuarto) trimestre de (\d{4})", plain)
    if not match:
        raise ValueError("El cuadro no identifica su trimestre")
    return f"{TRIMESTRES[match[1]]}T-{match[2]}"


def extract_etef(pdf, catalog):
    text = table(pdf, lambda p: "cuadro 1" in p and
                 re.search(r"exportaciones totales (?:segun|por) entidad federativa", p) and
                 "zacatecas" in p and "participacion" in p)
    values = rows(text, catalog, rf"({DECIMAL}) ({DECIMAL}) ({DECIMAL})",
                  national="Estados Unidos Mexicanos" if "estados unidos mexicanos" in _plano(text)
                  else "Exportaciones totales")
    total = values["00"][0]
    if total <= 0 or abs(sum(v[0] for k, v in values.items() if k != "00") - total) > 1.7:
        raise ValueError(f"El total ETEF no concilia con los estados: {total}, {sum(v[0] for k, v in values.items() if k != '00')}")
    return quarter(text), values


def extract_enoe(pdf, catalog):
    text = table(pdf, lambda p: "poblacion y tasas complementarias de ocupacion y desocupacion" in p
                 and "entidad federativa" in p and "zacatecas" in p and "aguascalientes" in p)
    # Veracruz se parte en dos líneas y las cifras pueden quedar antes de «Llave».
    text = re.sub(r"Veracruz de Ignacio de la\s*\n", "Veracruz ", text)
    values = rows(text, catalog, rf"({INTEGER}) ({INTEGER}) " + " ".join([rf"({DECIMAL})"] * 9),
                  national="Estados Unidos Mexicanos", aliases={"30": "Veracruz"})
    for occupied, unemployed, *rates in values.values():
        if occupied <= 0 or unemployed < 0 or any(not 0 <= rate <= 100 for rate in rates):
            raise ValueError("Valor fuera de rango en el cuadro ENOE")
        if abs(unemployed / (occupied + unemployed) * 100 - rates[1]) > 0.051:
            raise ValueError(f"La tasa de desocupación no concilia con la población del cuadro: {occupied}, {unemployed}, {rates[1]}")
    for index in (0, 1):
        if sum(values[code][index] for code in values if code != "00") != values["00"][index]:
            raise ValueError("La población estatal ENOE no concilia con el agregado nacional")
    return quarter(text), values


def extract_imss(pdf, catalog):
    text = table(pdf, lambda p: re.search(r"cuadro a\.\s*6\b", p) and
                 "entidad federativa" in p and "zacatecas" in p)
    stamp = re.search(r"(\d{1,2}) (?:de )?(" + "|".join(MESES) + r") (?:de )?(\d{4})", _plano(text))
    if not stamp:
        raise ValueError("El cuadro IMSS no identifica su fecha de corte")
    month = MESES.index(stamp[2]) + 1
    aliases = {"05": "Coahuila", "15": "Estado de México", "16": "Michoacán", "30": "Veracruz"}
    normalized = _plano(text)
    for code, candidates in {"09": ("Ciudad de México", "Distrito Federal"),
                             "15": ("Estado de México", "México", "Edo. de México")}.items():
        aliases[code] = next((n for n in candidates if re.search(
            rf"(?:^| )({re.escape(_plano(n))}) {IMSS_INTEGER}", normalized)), candidates[0])
    pattern = " ".join([rf"({IMSS_INTEGER})"] * 4 + [rf"({DECIMAL})", rf"({IMSS_INTEGER})", rf"({DECIMAL})"])
    values = rows(text, catalog, pattern, national="Total", aliases=aliases)
    validate_imss(values)
    return f"{stamp[3]}-{month:02d}", values


def validate_imss(values):
    for current, previous, last_year, monthly, monthly_rate, annual, annual_rate in values.values():
        if (min(current, previous, last_year) <= 0 or current - previous != monthly
                or current - last_year != annual or abs(annual / last_year * 100 - annual_rate) > 0.051
                or abs(monthly / previous * 100 - monthly_rate) > 0.051):
            raise ValueError("Los cambios IMSS no concilian con los niveles oficiales")
    if any(sum(values[code][column] for code in values if code != "00") != values["00"][column]
           for column in range(3)):
        raise ValueError("La suma de los 32 estados no concilia con el nacional IMSS")


def imss_baseline(catalog):
    path = Path(__file__).resolve().parents[1] / "config/imss_estatal_respaldo.json"
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    aliases = {"05": "Coahuila", "15": "Estado de México", "16": "Michoacán", "30": "Veracruz"}
    names = {aliases.get(e["clave"], e["nombre_oficial"]): e["clave"] for e in catalog["entidades"]}
    names["Total"] = "00"
    values = {}
    for name, current, previous, last_year in snapshot["filas"]:
        monthly, annual = current - previous, current - last_year
        values[names[name]] = (current, previous, last_year, monthly,
                               round(100 * monthly / previous, 1), annual,
                               round(100 * annual / last_year, 1))
    if sorted(values) != [f"{code:02d}" for code in range(33)]:
        raise ValueError("Cobertura incompleta en el respaldo oficial IMSS")
    validate_imss(values)
    return snapshot["periodo"], snapshot["url"], values


def candidates(key, today):
    for offset in range(12):
        year, month_index = divmod(today.year * 12 + today.month - 1 - offset, 12)
        month = month_index + 1
        if key == "IMSS":
            # The monthly report can only have been published after its reference month ended.
            if offset:
                day = calendar.monthrange(year, month)[1]
                yield f"{IMSS}/{year}/{month}_Nota_Indicadores_HCT_{year}-{month:02d}-{day}.pdf"
        elif key == "ETEF" and month in (3, 6, 9, 12):
            yield f"{INEGI}/{year}/exporta_ef/etef{year}_{month:02d}.pdf"
        elif key == "ENOE" and month in (2, 5, 8, 11):
            yield f"{INEGI}/{year}/enoe/enoe{year}_{month:02d}.pdf"


def observation(key, values, national):
    if key == "ETEF":
        value, annual, _ = values
        return {"valor": value, "var": annual, "part": 100 * value / national[0]}
    if key == "IMSS":
        value, _, _, _, _, annual, annual_rate = values
        return {"valor": int(value), "var": annual_rate, "cambio": int(annual),
                "part": 100 * value / national[0]}
    employed, _, participation, unemployment, *remaining = values
    national_rates = (national[2], national[3], national[9])
    return {"valor": unemployment, "ocupados": int(employed),
            "tasas": {name: [value, reference] for name, value, reference in
                      zip(RATES, (participation, unemployment, remaining[5]), national_rates)}}


METADATA = {
    "ETEF": ("Exportaciones", "INEGI (ETEF, cuadro 1)", "Millones de dólares corrientes, cifras preliminares", "mdd", "monto"),
    "ENOE": ("Desocupación (ENOE)", "INEGI (ENOE, cuadro estatal)", "Tasa de desocupación como porcentaje de la PEA", "pct", "tasa"),
    "IMSS": ("Puestos de trabajo registrados", "IMSS (Informe de Afiliación, cuadro A.6)", "Puestos registrados al cierre del mes", "num", "numero de puestos"),
}
EXTRACTORS = {"ETEF": extract_etef, "ENOE": extract_enoe, "IMSS": extract_imss}


def build_edition(key, catalog, now, previous=None, *, fetch=http_get_bytes):
    items = []
    last_error = None
    # Use a short lookback for the current edition. Fill the first ETEF trend from
    # previous quarterly reports, then maintain it as each new edition arrives.
    for index, url in enumerate(candidates(key, now.date())):
        if index >= (4 if key == "ETEF" and not previous else 2):
            break
        try:
            pdf = fetch(url, timeout=12)
            if not pdf.startswith(b"%PDF"):
                raise ValueError("Respuesta distinta de PDF")
            period, values = EXTRACTORS[key](pdf, catalog)
        except (OSError, ValueError) as error:
            last_error = error
            continue
        items.append((period, url, values))
        if key != "ETEF" or previous:
            break
    if not items:
        if key != "IMSS" or previous:
            raise ValueError(f"No se encontró una edición oficial de {key}") from last_error
        items.append(imss_baseline(catalog))
        print(f"AVISO IMSS estatal: se inicia con el cuadro oficial de {items[0][0]}")
    period, url, values = items[0]
    if previous:
        previous_period = previous["indicadores"][0]["periodo"]
        period_key = lambda p: (p[3:], p[0]) if "T-" in p else (p, "")
        if period_key(period) < period_key(previous_period):
            return previous

    name, source, measure, fmt, ranking = METADATA[key]
    national = observation(key, values["00"], values["00"])
    order = sorted((v[3 if key == "ENOE" else 0]
                    for c, v in values.items() if c != "00"), reverse=True)
    prior = {e["clave"]: e["ind"][key] for e in previous["entidades"]} if previous else {}
    def trend(code, prior_observation):
        series = dict(prior_observation.get("serie", []))
        series.update({p: data[code][0] for p, _, data in items})
        return sorted(series.items(), key=lambda item: (item[0][3:], item[0][0]))[-8:]

    if key == "ETEF":
        prior_national = previous["nacional"]["ETEF"] if previous else {}
        national["serie"] = trend("00", prior_national)
    entities = []
    for entity in catalog["entidades"]:
        code = entity["clave"]
        entry = observation(key, values[code], values["00"])
        entry["lugar"] = order.index(entry["valor"]) + 1
        if key == "ETEF":
            entry["serie"] = trend(code, prior.get(code, {}))
        entities.append({**entity, "ind": {key: entry}})
    indicator = {"clave": key, "nombre": name, "sigla": key, "fuente": source,
                              "medida": measure, "periodo": period, "formato": fmt,
                              "escala": "secuencial", "lugar_por": ranking, "estatus": "oficial",
                              "url_fuente": url}
    if key == "ETEF":
        urls = dict(previous["indicadores"][0].get("fuentes_serie", {})) if previous else {}
        urls.update({p: link for p, link, _ in items})
        indicator["fuentes_serie"] = {p: urls[p] for p, _ in national["serie"] if p in urls}
    return {"version": 1, "estado": "oficial", "actualizado": now.isoformat(timespec="seconds"),
            "indicadores": [indicator], "nacional": {key: national}, "entidades": entities}
