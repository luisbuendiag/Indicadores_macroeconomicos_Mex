"""Panorama Estatal: ITAEE de las 32 entidades desde el boletín oficial del INEGI.

Lee el Cuadro 1 del boletín «Indicador Trimestral de la Actividad Económica Estatal»
(variación trimestral y anual, cifras desestacionalizadas). No requiere token: es el mismo
PDF público que se cita como fuente.

Lectura robusta del cuadro: tiene dos bloques (16 entidades a la izquierda y 16 a la
derecha, en orden de clave INEGI) y algunos nombres se parten en dos renglones. Por eso no
se empareja texto con números: se toman los pares de cifras de cada bloque, renglón por
renglón, y se asignan en el orden de clave. Antes se comprueba que los 32 nombres aparezcan
en ese mismo orden; si algo no cuadra, el conector falla y la ficha conserva lo anterior.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import unicodedata
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URL = "https://www.inegi.org.mx/contenidos/saladeprensa/boletines/{y}/itaee/itaee{y}_{m:02d}.pdf"
NUMERO = re.compile(r"^[−–-]?\d{1,2}\.\d$")
TRIMESTRES = {"primer": 1, "segundo": 2, "tercer": 3, "cuarto": 4}
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]


def _plano(texto: str) -> str:
    sin_acentos = unicodedata.normalize("NFKD", texto)
    return re.sub(r"\s+", " ", "".join(c for c in sin_acentos if not unicodedata.combining(c))).lower()


def _num(texto: str) -> float:
    return float(texto.replace("−", "-").replace("–", "-"))


def _renglones(palabras, tolerancia=3.0):
    """Agrupa palabras por renglón (misma altura) y las ordena de izquierda a derecha."""
    filas = []
    for w in sorted(palabras, key=lambda w: (w["top"], w["x0"])):
        if filas and abs(filas[-1][0] - w["top"]) <= tolerancia:
            filas[-1][1].append(w)
        else:
            filas.append([w["top"], [w]])
    return [sorted(f[1], key=lambda w: w["x0"]) for f in filas]


def leer_cuadro(pdf: bytes, entidades: list[dict]) -> dict:
    import pdfplumber

    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        paginas = [(p, p.extract_text() or "") for p in doc.pages]
    portada = paginas[0][1] if paginas else ""
    for pagina, texto in paginas:
        plano = _plano(texto)
        if "cuadro 1" in plano and "aguascalientes" in plano and "zacatecas" in plano \
                and "desestacionalizad" in plano:
            break
    else:
        raise ValueError("No se encontró el Cuadro 1 del ITAEE")

    palabras = pagina.extract_words(keep_blank_chars=False, use_text_flow=False)
    # El cuadro empieza en el «Aguascalientes» que trae sus dos cifras en el mismo renglón
    # (la página puede mencionar entidades en el texto antes del cuadro).
    candidatos = [w["top"] for w in palabras if _plano(w["text"]).startswith("aguascalientes")
                  and sum(1 for n in palabras if NUMERO.match(n["text"]) and abs(n["top"] - w["top"]) <= 3
                          and n["x0"] > w["x0"] and n["x0"] < pagina.width / 2) >= 2]
    if not candidatos:
        raise ValueError("El Cuadro 1 del ITAEE no tiene cifras junto a Aguascalientes")
    inicio = min(candidatos)
    fuentes = [w["top"] for w in palabras if w["top"] > inicio and _plano(w["text"]).startswith("fuente")]
    fin = min(fuentes) if fuentes else pagina.height
    zona = [w for w in palabras if inicio - 4 <= w["top"] < fin - 1]

    # Los 32 nombres deben aparecer en orden de clave dentro del cuadro.
    texto_zona = {}
    mitad = pagina.width / 2
    for lado, sel in (("izq", lambda w: w["x0"] < mitad), ("der", lambda w: w["x0"] >= mitad)):
        texto_zona[lado] = _plano(" ".join(" ".join(w["text"] for w in r) for r in _renglones([w for w in zona if sel(w)])))
    nombres = [_plano(e["nombre_oficial"]) for e in entidades]
    bloques = (nombres[:16], nombres[16:])
    for lado, esperados in zip(("izq", "der"), bloques):
        pos = 0
        for nombre in esperados:
            # Un nombre partido en dos renglones puede llevar cifras en medio: basta con su primera palabra larga.
            clave = max(nombre.split(" "), key=len)
            encontrado = texto_zona[lado].find(clave, pos)
            if encontrado < 0:
                raise ValueError(f"Cuadro 1 del ITAEE sin la entidad esperada: {nombre}")
            pos = encontrado + len(clave)

    pares = []
    for lado, sel in (("izq", lambda w: w["x0"] < mitad), ("der", lambda w: w["x0"] >= mitad)):
        numeros = [w for w in zona if sel(w) and NUMERO.match(w["text"])]
        filas = _renglones(numeros)
        if len(filas) != 16 or any(len(f) != 2 for f in filas):
            raise ValueError(f"El bloque {lado} del Cuadro 1 no tiene 16 renglones con dos cifras")
        pares += [(_num(f[0]["text"]), _num(f[1]["text"])) for f in filas]
    if any(abs(v) > 60 for par in pares for v in par):
        raise ValueError("Variación fuera de rango en el Cuadro 1 del ITAEE")

    plano = _plano(portada + " " + texto)
    ref = re.search(r"(primer|segundo|tercer|cuarto) trimestre de (\d{4})", plano)
    if not ref:
        raise ValueError("El boletín no indica el trimestre de referencia")
    fecha = re.search(r"(\d{1,2}) de (" + "|".join(MESES) + r") de (\d{4})", _plano(portada))
    numero = re.search(r"(?:indicador|prensa)(?: numero| num\.?)? (\d{1,4}/\d{2})", _plano(portada))
    return {
        "trimestre": TRIMESTRES[ref[1]], "anio": int(ref[2]),
        "publicacion": date(int(fecha[3]), MESES.index(fecha[2]) + 1, int(fecha[1])).isoformat() if fecha else None,
        "boletin": numero[1] if numero else None,
        "valores": {e["clave"]: {"trim": t, "anual": a} for e, (t, a) in zip(entidades, pares)},
    }


def ultimo_boletin(hoy: date, obtener) -> tuple[str, bytes]:
    """El ITAEE se publica en enero, abril, julio y octubre: prueba hacia atrás hasta 15 meses."""
    y, m = hoy.year, hoy.month
    for _ in range(15):
        url = URL.format(y=y, m=m)
        try:
            contenido = obtener(url)
        except Exception:  # noqa: BLE001 - 404 de los meses sin boletín
            contenido = b""
        if contenido.startswith(b"%PDF"):
            return url, contenido
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    raise ValueError("No se encontró un boletín del ITAEE en los últimos 15 meses")


def nacional_pib(indicadores: dict, trimestre: int, anio: int) -> float:
    """Referencia nacional: variación anual del PIB desestacionalizado del mismo trimestre (PIBT)."""
    periodo = f"{trimestre}T-{str(anio)[2:]}"
    for obs in indicadores["indicators"]["PIBSEC"]["observations"]:
        if obs["period"] == periodo and len(obs["values"]) > 7 and obs["values"][7] is not None:
            return round(100 * obs["values"][7], 1)
    raise ValueError(f"No hay PIB nacional para {periodo}")


def build_itaee(catalog: dict, pdf: bytes, url: str, checked_at: datetime, indicadores: dict) -> dict:
    entidades = sorted(catalog["entidades"], key=lambda e: e["clave"])
    if [e["clave"] for e in entidades] != [f"{c:02d}" for c in range(1, 33)]:
        raise ValueError("El catálogo debe contener las 32 claves estatales")
    cuadro = leer_cuadro(pdf, entidades)
    periodo = f"{cuadro['trimestre']}T-{cuadro['anio']}"
    anuales = sorted((v["anual"] for v in cuadro["valores"].values()), reverse=True)
    salida = []
    for e in entidades:
        v = cuadro["valores"][e["clave"]]
        salida.append({**e, "ind": {"ITAEE": {"valor": v["anual"], "trim": v["trim"],
                                               "lugar": anuales.index(v["anual"]) + 1}}})
    detalle = ", ".join(x for x in (f"boletín {cuadro['boletin']}" if cuadro["boletin"] else "",
                                     cuadro["publicacion"] or "") if x)
    return {
        "version": 1, "estado": "oficial", "actualizado": checked_at.isoformat(timespec="seconds"),
        "indicadores": [{
            "clave": "ITAEE", "nombre": "Actividad económica (ITAEE)", "sigla": "ITAEE",
            "fuente": f"INEGI (ITAEE{', ' + detalle if detalle else ''})", "url_fuente": url,
            "medida": "Variación anual real, cifras desestacionalizadas",
            "periodo": periodo, "formato": "pct", "escala": "divergente",
            "lugar_por": "crecimiento anual", "estatus": "oficial",
            "nota_nacional": "México: variación anual del PIB desestacionalizado del mismo trimestre (PIBT).",
        }],
        "nacional": {"ITAEE": {"valor": nacional_pib(indicadores, cuadro["trimestre"], cuadro["anio"])}},
        "entidades": salida,
    }


def main():
    from sources.base import http_get_bytes

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--archivo", type=Path, help="Boletín ITAEE guardado localmente")
    args = parser.parse_args()
    catalog = json.loads((args.root / "config/estados.json").read_text(encoding="utf-8"))
    indicadores = json.loads((args.root / "data/indicadores.json").read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc)
    if args.archivo:
        url, pdf = "archivo local", args.archivo.read_bytes()
    else:
        url, pdf = ultimo_boletin(now.date(), lambda u: http_get_bytes(u, timeout=30))
    print(json.dumps(build_itaee(catalog, pdf, url, now, indicadores), ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
