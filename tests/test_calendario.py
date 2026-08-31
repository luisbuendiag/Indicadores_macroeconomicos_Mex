"""Pruebas del calendario de publicaciones.

Verifica que `scripts/build_calendar.py` genere `data/calendario.json`
(nuevo esquema) y `data/calendario_publicaciones.json` (esquema legacy)
con los campos, estados, cobertura de indicadores y URLs correctos.
"""

import json
from datetime import date
from pathlib import Path

import pytest

import build_calendar
import lib_data as L

ROOT = Path(__file__).resolve().parents[1]
AS_OF = date(2026, 8, 31)

NEW_FILE = L.DATA_DIR / "calendario.json"
LEGACY_FILE = L.DATA_DIR / "calendario_publicaciones.json"
META_FILE = ROOT / "config" / "indicadores_meta.json"


def _meta_keys() -> set[str]:
    meta = json.loads(META_FILE.read_text(encoding="utf-8"))
    return set(meta.get("principal", [])) | set(meta.get("complementario", []))


@pytest.fixture(scope="module", autouse=True)
def regenerate():
    """Regenera ambos calendarios en modo offline con una fecha fija."""
    build_calendar.build(as_of=AS_OF, offline=True)


@pytest.fixture
def calendario_nuevo() -> dict:
    return json.loads(NEW_FILE.read_text(encoding="utf-8"))


@pytest.fixture
def calendario_legacy() -> dict:
    return json.loads(LEGACY_FILE.read_text(encoding="utf-8"))


def test_archivos_generados_y_json_valido():
    assert NEW_FILE.exists(), f"No existe {NEW_FILE}"
    assert LEGACY_FILE.exists(), f"No existe {LEGACY_FILE}"
    # Ambos deben ser JSON válido
    assert isinstance(json.loads(NEW_FILE.read_text(encoding="utf-8")), dict)
    assert isinstance(json.loads(LEGACY_FILE.read_text(encoding="utf-8")), dict)


def test_calendario_nuevo_campos_principales(calendario_nuevo):
    for clave in (
        "generated_at",
        "as_of",
        "fuente",
        "sources",
        "years",
        "events",
        "rules",
        "upcoming",
        "recent",
        "categories",
    ):
        assert clave in calendario_nuevo, f"Falta la clave {clave} en calendario.json"

    assert isinstance(calendario_nuevo["events"], list)
    assert isinstance(calendario_nuevo["rules"], list)
    assert isinstance(calendario_nuevo["upcoming"], list)
    assert isinstance(calendario_nuevo["recent"], list)
    assert AS_OF.year in calendario_nuevo["years"]


def test_calendario_nuevo_eventos_tienen_campos_requeridos(calendario_nuevo):
    required = {
        "indicator",
        "program",
        "product",
        "publication_date",
        "publication_date_display",
        "reference_period",
        "frequency",
        "status",
        "source",
        "institution",
        "category",
        "sigla",
        "type",
        "url",
        "deliverables",
        "anio",
        "mes",
        "fecha_iso",
    }
    for ev in calendario_nuevo["events"]:
        assert "type" in ev and ev["type"] == "event"
        faltantes = required - set(ev.keys())
        assert not faltantes, f"Evento {ev.get('indicator')} le faltan campos: {faltantes}"


def test_calendario_nuevo_reglas_tienen_campos_requeridos(calendario_nuevo):
    required = {
        "indicator",
        "name",
        "product",
        "frequency",
        "institution",
        "category",
        "rule_text",
        "url",
        "type",
        "status",
    }
    for rule in calendario_nuevo["rules"]:
        faltantes = required - set(rule.keys())
        assert not faltantes, f"Regla {rule.get('indicator')} le faltan campos: {faltantes}"
        assert rule["type"] == "rule"
        assert rule["status"] == "regla"


def test_estados_nuevos_son_validos(calendario_nuevo):
    valid_statuses = {"publicado", "próximo", "retrasado", "cancelado", "regla"}
    for ev in calendario_nuevo["events"]:
        assert ev["status"] in valid_statuses, (
            f"Evento {ev['indicator']} tiene estatus inválido: {ev['status']}"
        )
    for rule in calendario_nuevo["rules"]:
        assert rule["status"] == "regla"


def test_calendario_nuevo_upcoming_y_recent(calendario_nuevo):
    for ev in calendario_nuevo["upcoming"]:
        assert ev["status"] == "próximo", (
            f"upcoming contiene un evento con status {ev['status']}"
        )
    for ev in calendario_nuevo["recent"]:
        assert ev["status"] == "publicado", (
            f"recent contiene un evento con status {ev['status']}"
        )
    assert len(calendario_nuevo["upcoming"]) <= 20
    assert len(calendario_nuevo["recent"]) <= 20


def test_calendario_legacy_campos_principales(calendario_legacy):
    for clave in ("_comment", "fuente", "actualizado", "as_of", "anios", "items"):
        assert clave in calendario_legacy, f"Falta {clave} en calendario_publicaciones.json"
    assert isinstance(calendario_legacy["items"], list)


def test_calendario_legacy_items_tienen_campos_requeridos(calendario_legacy):
    required = {
        "clave",
        "indicador",
        "producto",
        "institucion",
        "frecuencia",
        "usar_para_frescura",
        "fecha_publicacion",
        "fecha_iso",
        "anio",
        "mes",
        "periodo_referencia",
        "estatus",
        "url_boletin",
    }
    for it in calendario_legacy["items"]:
        faltantes = required - set(it.keys())
        assert not faltantes, f"Item {it.get('clave')} le faltan campos: {faltantes}"


def test_estados_legacy_son_validos(calendario_legacy):
    valid = {"publicado", "próximo", "no_anunciada", "regla", "evento"}
    for it in calendario_legacy["items"]:
        assert it["estatus"] in valid, f"{it['clave']} tiene estatus inválido {it['estatus']}"


def test_cobertura_indicadores(calendario_nuevo, calendario_legacy):
    """Cada indicador del dashboard (principal + complementario) debe aparecer
    al menos una vez en eventos o reglas del calendario."""
    target = _meta_keys()
    new_indicators = {e["indicator"] for e in calendario_nuevo["events"]}
    new_indicators |= {r["indicator"] for r in calendario_nuevo["rules"]}
    missing = target - new_indicators
    assert not missing, f"Faltan indicadores en calendario.json: {sorted(missing)}"

    legacy_keys = {it["clave"] for it in calendario_legacy["items"]}
    missing_legacy = target - legacy_keys
    assert not missing_legacy, f"Faltan claves en calendario_publicaciones.json: {sorted(missing_legacy)}"


def test_imai_no_imaief(calendario_nuevo, calendario_legacy):
    """El indicador IMAI no debe confundirse con IMAIEF en eventos ni items."""
    for ev in calendario_nuevo["events"]:
        if ev["indicator"] == "IMAI":
            assert "IMAIEF" not in (ev.get("program") or ""), "IMAI contiene referencia a IMAIEF"
            assert "IMAIEF" not in (ev.get("product") or ""), "IMAI contiene referencia a IMAIEF"
            assert "Actividad Industrial" in (ev.get("program") or "") or "IMAI" in (ev.get("program") or "")

    # Ningún evento debe tener IMAIEF como indicador
    iedef_keys = {e["indicator"] for e in calendario_nuevo["events"]}
    assert "IMAIEF" not in iedef_keys, "IMAIEF aparece como indicador en calendario.json"

    for it in calendario_legacy["items"]:
        if it["clave"] == "IMAI":
            assert "IMAIEF" not in (it.get("producto") or ""), "Legacy IMAI contiene IMAIEF"
            assert "IMAIEF" not in (it.get("indicador") or ""), "Legacy IMAI contiene IMAIEF"
    legacy_claves = {it["clave"] for it in calendario_legacy["items"]}
    assert "IMAIEF" not in legacy_claves, "IMAIEF aparece como clave legacy"


def test_sin_eventos_duplicados(calendario_nuevo, calendario_legacy):
    """No deben existir dos eventos con el mismo (indicador, fecha_iso, periodo_referencia)."""
    seen = set()
    for ev in calendario_nuevo["events"]:
        key = (ev["indicator"], ev.get("fecha_iso"), ev.get("reference_period"))
        assert key not in seen, f"Evento duplicado en calendario.json: {key}"
        seen.add(key)

    seen = set()
    for it in calendario_legacy["items"]:
        key = (it["clave"], it.get("fecha_iso"), it.get("periodo_referencia"))
        assert key not in seen, f"Item duplicado en calendario_publicaciones.json: {key}"
        seen.add(key)


def test_urls_validas(calendario_nuevo, calendario_legacy):
    """Todas las URLs del calendario deben ser cadenas http/https."""
    for ev in calendario_nuevo["events"]:
        assert isinstance(ev["url"], str) and ev["url"].startswith(("http://", "https://")), (
            f"URL inválida para {ev['indicator']}: {ev.get('url')!r}"
        )
        for d in ev.get("deliverables", []):
            assert isinstance(d.get("url"), str) and d["url"].startswith(("http://", "https://")), (
                f"Deliverable inválido para {ev['indicator']}: {d.get('url')!r}"
            )
    for rule in calendario_nuevo["rules"]:
        assert isinstance(rule["url"], str) and rule["url"].startswith(("http://", "https://")), (
            f"URL inválida para regla {rule['indicator']}"
        )

    for it in calendario_legacy["items"]:
        assert isinstance(it["url_boletin"], str) and it["url_boletin"].startswith(("http://", "https://")), (
            f"url_boletin inválida para {it['clave']}: {it.get('url_boletin')!r}"
        )


def test_fechas_consistentes_con_estado(calendario_nuevo):
    """Un evento publicado debe tener fecha <= as_of; uno próximo, fecha > as_of."""
    for ev in calendario_nuevo["events"]:
        iso = ev.get("fecha_iso")
        if iso:
            d = date.fromisoformat(iso)
            if ev["status"] == "publicado":
                assert d <= AS_OF, f"{ev['indicator']} marcado publicado pero fecha {d} > {AS_OF}"
            elif ev["status"] == "próximo":
                assert d > AS_OF, f"{ev['indicator']} marcado próximo pero fecha {d} <= {AS_OF}"
