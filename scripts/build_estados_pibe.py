"""Panorama Estatal: PIB por entidad federativa (PIBE) desde el comunicado oficial del INEGI.

Lee el Cuadro 1 del comunicado «Producto Interno Bruto por Entidad Federativa (PIBE)»: PIB a
precios de mercado de los dos últimos años (miles de millones de pesos de 2018) y su variación
anual real, para el total nacional y las 32 entidades. Es el mismo PDF público que se cita.

El cuadro usa un espacio como separador de miles («3 806»). Para no confundirlo con el salto
entre columnas, las cifras se arman por la distancia entre palabras. Los renglones con cifras se
asignan en orden (nacional y luego claves 01 a 32) después de comprobar que los nombres aparecen
en ese orden; se coteja además que cada variación cuadre con sus niveles y que la suma de las
entidades cuadre con el total. Si algo no cuadra, el conector falla y la ficha conserva lo anterior.
"""
from __future__ import annotations

import argparse
import io
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path

from build_estados_itaee import MESES, _plano, _renglones

ROOT = Path(__file__).resolve().parents[1]
URL = "https://www.inegi.org.mx/contenidos/saladeprensa/boletines/{y}/pibent/PIBE{a}_CP.pdf"
DECIMAL = re.compile(r"^[−–-]?\d{1,3}\.\d$")
ENTERO = re.compile(r"^\d{1,3}(?:[\u00a0\u2009\u202f]\d{3})*$")  # admite espacio fino o duro dentro de la cifra
ESPACIOS = str.maketrans("", "", "\u00a0\u2009\u202f")
SEPARADOR_MILES = 4.0  # pt: el espacio de miles es angosto; entre columnas hay más aire


def _num(texto: str) -> float:
    return float(texto.replace("−", "-").replace("–", "-"))


def _enteros(palabras):
    """Une «3» + «806» en 3806 cuando están pegados; separa columnas cuando hay aire."""
    numeros, actual, fin = [], "", None
    for w in palabras:
        texto = w["text"].translate(ESPACIOS)
        if actual and fin is not None and w["x0"] - fin < SEPARADOR_MILES and len(texto) == 3:
            actual += texto
        else:
            if actual:
                numeros.append(int(actual))
            actual = texto
        fin = w["x1"]
    if actual:
        numeros.append(int(actual))
    return numeros


def leer_cuadro(pdf: bytes, entidades: list[dict]) -> dict:
    import pdfplumber

    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        paginas = [(p, p.extract_text() or "") for p in doc.pages]
    portada = paginas[0][1] if paginas else ""
    for pagina, texto in paginas:
        plano = _plano(texto)
        if "cuadro 1" in plano and "estados unidos mexicanos" in plano and "zacatecas" in plano:
            break
    else:
        raise ValueError("No se encontró el Cuadro 1 del PIBE")

    palabras = pagina.extract_words(keep_blank_chars=False, use_text_flow=False)
    renglones = _renglones(palabras)
    con_cifras = []
    for r in renglones:
        decimales = [w for w in r if DECIMAL.match(w["text"])]
        if len(decimales) >= 3:
            primero = decimales[0]
            antes = [w for w in r if w["x1"] <= primero["x0"] and ENTERO.match(w["text"])]
            niveles = _enteros(antes)
            if len(niveles) != 2:
                raise ValueError(f"Renglón del PIBE sin dos niveles legibles: {' '.join(w['text'] for w in r)}")
            con_cifras.append((niveles[0], niveles[1], _num(primero["text"])))
    if len(con_cifras) != 33:
        raise ValueError(f"El Cuadro 1 del PIBE debe tener 33 renglones con cifras; tiene {len(con_cifras)}")

    texto_cuadro = _plano(" ".join(" ".join(w["text"] for w in r) for r in renglones))
    pos = texto_cuadro.find("estados unidos mexicanos")
    if pos < 0:
        raise ValueError("El Cuadro 1 del PIBE no trae el total nacional")
    for e in entidades:
        clave = max(_plano(e["nombre_oficial"]).split(" "), key=len)
        encontrado = texto_cuadro.find(clave, pos + 1)
        if encontrado < 0:
            raise ValueError(f"Cuadro 1 del PIBE sin la entidad esperada: {e['nombre_oficial']}")
        pos = encontrado

    for anterior, actual, var in con_cifras:
        calculada = 100 * (actual / anterior - 1) if anterior else 0
        if abs(calculada - var) > max(1.5, 100 * 1.0 / max(anterior, 1)):
            raise ValueError("Una variación del PIBE no cuadra con sus niveles")
    nacional, estados = con_cifras[0], con_cifras[1:]
    suma = sum(x[1] for x in estados)
    if abs(suma - nacional[1]) > 0.01 * nacional[1]:
        raise ValueError("La suma de las entidades no cuadra con el total nacional del PIBE")

    plano = _plano(portada + " " + texto)
    anios = (re.search(r"(\d{4})\s*-\s*(\d{4})", plano)
             or re.search(r"(pibe)\D{0,3}(20\d{2})", plano)
             or re.search(r"(20\d{2})\s+(20\d{2})", _plano(texto)))
    fecha = re.search(r"(\d{1,2}) de (" + "|".join(MESES) + r") de (\d{4})", _plano(portada))
    numero = re.search(r"prensa (?:numero |num\.? )?(\d{1,4}/\d{2})", _plano(portada))
    if not anios:
        raise ValueError("El Cuadro 1 del PIBE no indica los años")
    return {
        "anio": int(anios[2]),
        "publicacion": date(int(fecha[3]), MESES.index(fecha[2]) + 1, int(fecha[1])).isoformat() if fecha else None,
        "boletin": numero[1] if numero else None,
        "nacional": {"nivel": nacional[1], "var": nacional[2]},
        "valores": {e["clave"]: {"nivel": n, "var": v} for e, (_, n, v) in zip(entidades, estados)},
    }


def ultimo_comunicado(hoy: date, obtener) -> tuple[str, bytes]:
    """El PIBE del año a-1 se publica en diciembre del año a: prueba este año y los dos anteriores."""
    for y in (hoy.year, hoy.year - 1, hoy.year - 2):
        url = URL.format(y=y, a=y - 1)
        try:
            contenido = obtener(url)
        except Exception:  # noqa: BLE001 - 404 mientras no se publica
            contenido = b""
        if contenido.startswith(b"%PDF"):
            return url, contenido
    raise ValueError("No se encontró el comunicado del PIBE")


def build_pibe(catalog: dict, pdf: bytes, url: str, checked_at: datetime) -> dict:
    entidades = sorted(catalog["entidades"], key=lambda e: e["clave"])
    if [e["clave"] for e in entidades] != [f"{c:02d}" for c in range(1, 33)]:
        raise ValueError("El catálogo debe contener las 32 claves estatales")
    cuadro = leer_cuadro(pdf, entidades)
    total = cuadro["nacional"]["nivel"]
    niveles = sorted((v["nivel"] for v in cuadro["valores"].values()), reverse=True)
    salida = []
    for e in entidades:
        v = cuadro["valores"][e["clave"]]
        salida.append({**e, "ind": {"PIB": {
            "valor": v["nivel"] * 1000, "var": v["var"],
            "part": round(100 * v["nivel"] / total, 1), "lugar": niveles.index(v["nivel"]) + 1}}})
    detalle = ", ".join(x for x in (f"comunicado {cuadro['boletin']}" if cuadro["boletin"] else "",
                                     cuadro["publicacion"] or "") if x)
    return {
        "version": 1, "estado": "oficial", "actualizado": checked_at.isoformat(timespec="seconds"),
        "indicadores": [{
            "clave": "PIB", "nombre": "PIB estatal", "sigla": "PIBE",
            "fuente": f"INEGI (PIBE{', ' + detalle if detalle else ''})", "url_fuente": url,
            "medida": "PIB a precios de mercado, pesos constantes de 2018",
            "periodo": str(cuadro["anio"]), "formato": "mdp", "escala": "secuencial",
            "lugar_por": "tamaño de la economía", "estatus": "oficial",
            "nota_part": "Participación calculada con el PIB a precios de 2018.",
        }],
        "nacional": {"PIB": {"valor": total * 1000, "var": cuadro["nacional"]["var"]}},
        "entidades": salida,
    }


def main():
    from sources.base import http_get_bytes

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--archivo", type=Path, help="Comunicado PIBE guardado localmente")
    args = parser.parse_args()
    catalog = json.loads((args.root / "config/estados.json").read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc)
    if args.archivo:
        url, pdf = "archivo local", args.archivo.read_bytes()
    else:
        url, pdf = ultimo_comunicado(now.date(), lambda u: http_get_bytes(u, timeout=30))
    print(json.dumps(build_pibe(catalog, pdf, url, now), ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
