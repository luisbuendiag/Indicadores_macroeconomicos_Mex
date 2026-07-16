"""Recopila noticias/comunicados desde RSS oficiales y escribe data/noticias.json.

Diseño a prueba de fallos: si un feed no responde o cambia de formato, se
omite y se continúa. Nunca lanza excepción hacia el pipeline principal y
siempre escribe un archivo válido (aunque sea con lista vacía), de modo que una
falla de noticias no afecte el dashboard.

Fuentes: exclusivamente oficiales/gubernamentales (INEGI, Banxico, Secretaría
de Economía / gob.mx, DOF). No integra APIs de noticias de paga.
"""
from __future__ import annotations

import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "noticias.json"
UA = "IndicadoresMacroMX/2.0 (+https://github.com/luisbuendiag/Indicadores_macroeconomicos_Mex)"

# Feeds oficiales candidatos. Se marcan con categoría e indicador relacionado.
FEEDS = [
    {"fuente": "INEGI", "categoria": "Estadística oficial", "indicador": "Varios",
     "url": "https://www.inegi.org.mx/rss/comunicados.xml"},
    {"fuente": "Banco de México", "categoria": "Política monetaria", "indicador": "TASA / INPC / TIPOCAMBIO",
     "url": "https://www.banxico.org.mx/rss/rss.xml"},
    {"fuente": "Secretaría de Economía (gob.mx)", "categoria": "Comercio e inversión", "indicador": "IED / BALANZA",
     "url": "https://www.gob.mx/se/articulos.rss"},
    {"fuente": "Diario Oficial de la Federación", "categoria": "Regulatorio", "indicador": "Entorno",
     "url": "https://www.dof.gob.mx/indicadores.rss"},
]

MAX_PER_FEED = 6

# Referencias oficiales perennes (no son noticias con fecha; son punteros a
# fuentes oficiales). Se usan como respaldo cuando los RSS oficiales no
# responden, para que la sección sea funcional sin fabricar noticias.
CURATED = [
    {"titulo": "Calendario de difusión de información estadística — INEGI",
     "enlace": "https://www.inegi.org.mx/calendario/",
     "fuente": "INEGI", "categoria": "Calendario", "indicador": "Varios",
     "porque": "Fechas oficiales de publicación de PIB, IGAE, INPC, ENOE y balanza comercial.",
     "tipo": "referencia_oficial"},
    {"titulo": "Anuncios de política monetaria — Banco de México",
     "enlace": "https://www.banxico.org.mx/publicaciones-y-prensa/anuncios-de-las-decisiones-de-politica-monetaria/anuncios-politica-monetaria-t.html",
     "fuente": "Banco de México", "categoria": "Política monetaria", "indicador": "TASA",
     "porque": "Decisiones de tasa objetivo que afectan al costo del crédito y al tipo de cambio.",
     "tipo": "referencia_oficial"},
    {"titulo": "Sala de prensa / comunicados — INEGI",
     "enlace": "https://www.inegi.org.mx/app/saladeprensa/",
     "fuente": "INEGI", "categoria": "Comunicados", "indicador": "Varios",
     "porque": "Comunicados con los resultados de cada indicador al momento de su publicación.",
     "tipo": "referencia_oficial"},
    {"titulo": "Prensa — Secretaría de Economía (gob.mx)",
     "enlace": "https://www.gob.mx/se/prensa",
     "fuente": "Secretaría de Economía", "categoria": "Comercio e inversión", "indicador": "IED / BALANZA",
     "porque": "Comunicados oficiales sobre comercio exterior, inversión extranjera y política industrial.",
     "tipo": "referencia_oficial"},
    {"titulo": "Diario Oficial de la Federación",
     "enlace": "https://www.dof.gob.mx/",
     "fuente": "DOF", "categoria": "Regulatorio", "indicador": "Entorno",
     "porque": "Publicación de disposiciones oficiales relevantes para el entorno económico y comercial.",
     "tipo": "referencia_oficial"},
]


def _fetch(url: str, timeout: int = 20) -> str | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", "replace")
    except Exception:  # noqa: BLE001 - a prueba de fallos
        return None


def _clean(txt: str | None) -> str:
    if not txt:
        return ""
    txt = re.sub(r"<[^>]+>", "", txt)
    return re.sub(r"\s+", " ", txt).strip()


def _parse_rss(xml_text: str, feed: dict) -> list[dict]:
    items = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return items
    for it in root.iter("item"):
        title = _clean(it.findtext("title"))
        link = (it.findtext("link") or "").strip()
        pub = _clean(it.findtext("pubDate"))
        desc = _clean(it.findtext("description"))
        if not title:
            continue
        items.append({
            "titulo": title, "enlace": link, "fecha": pub,
            "fuente": feed["fuente"], "categoria": feed["categoria"],
            "indicador": feed["indicador"],
            "porque": (desc[:220] + "…") if len(desc) > 220 else desc,
            "tipo": "hecho_confirmado",
        })
        if len(items) >= MAX_PER_FEED:
            break
    return items


def main() -> int:
    all_items, warnings, ok_feeds = [], [], 0
    for feed in FEEDS:
        xml_text = _fetch(feed["url"])
        if not xml_text:
            warnings.append(f"Feed no disponible: {feed['fuente']} ({feed['url']}).")
            continue
        parsed = _parse_rss(xml_text, feed)
        if parsed:
            ok_feeds += 1
            all_items.extend(parsed)
        else:
            warnings.append(f"Feed sin ítems o formato inesperado: {feed['fuente']}.")

    used_fallback = False
    if not all_items:
        all_items = list(CURATED)
        used_fallback = True
        warnings.append("Ningún RSS oficial respondió; se muestran referencias oficiales perennes (sin fabricar noticias).")

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "feeds_ok": ok_feeds, "feeds_total": len(FEEDS),
        "modo": "rss" if not used_fallback else "referencias_oficiales",
        "warnings": warnings,
        "nota": ("Sección piloto basada en RSS oficiales. Distingue hecho confirmado / posible "
                 "implicación / interpretación. No afirma causalidad. Si un feed falla, se omite "
                 "sin afectar el dashboard."),
        "items": all_items,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: noticias -> {OUT.relative_to(ROOT)} · {ok_feeds}/{len(FEEDS)} feeds, {len(all_items)} ítems, {len(warnings)} advertencias.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
