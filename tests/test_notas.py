"""Regresiones de la fase de notas institucionales.

Regla maestra: el botón NOTA siempre descarga un Word .docx real
(application/vnd.openxmlformats-officedocument.wordprocessingml.document);
nunca PDF, HTML, enlace a boletín ni preview.

Arquitectura bajo prueba:

- data/source/notas_machote/ — machotes permanentes por indicador +
  _PLANTILLA_MAESTRA.docx. El pipeline jamás los sobrescribe.
- downloads/indicadores/{KEY}/nota/{KEY}_nota.docx — nota vigente descargable.
- config/notas_map.json — mapa indicador -> machote + metadatos.
- indicadores.json — ind['nota'] + nota_disponible/url_nota_individual.
"""
from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import lib_notas  # noqa: E402

PAYLOAD = json.loads((ROOT / "data" / "indicadores.json").read_text(encoding="utf-8"))
MAP = json.loads((ROOT / "config" / "notas_map.json").read_text(encoding="utf-8"))

# Las 14 notas institucionales existentes (llave interna del dashboard).
CON_NOTA = [
    "PIB", "PIBSEC", "SIC", "IOAE", "IGAE", "IMAI", "EMIM", "EMOE",
    "DESOCUP", "INPC", "INPP", "CONSUMO", "IMFBCF", "BCMM",
]
# Indicadores sin nota institucional por ahora.
SIN_NOTA = ["IED", "TIPOCAMBIO", "TASA", "RESERVAS"]

MACHOTE_DIR = ROOT / "data" / "source" / "notas_machote"
MIN_DOCX_BYTES = 20_000  # una nota institucional con gráficas pesa > 20 KB


def _docx_ok(path: Path) -> bool:
    try:
        with zipfile.ZipFile(path) as z:
            return "word/document.xml" in z.namelist()
    except (zipfile.BadZipFile, OSError):
        return False


def test_mapa_cubre_exactamente_las_14_notas():
    notas = MAP.get("notas", {})
    assert sorted(notas.keys()) == sorted(CON_NOTA), (
        f"notas_map no coincide con las 14 notas: {sorted(notas.keys())}"
    )
    for k in SIN_NOTA:
        assert k not in notas, f"{k} no debería tener nota todavía"


@pytest.mark.parametrize("key", CON_NOTA)
def test_nota_vigente_existe_y_es_docx_real(key):
    ind = PAYLOAD["indicators"][key]
    nota = ind.get("nota") or {}
    assert nota.get("available") is True
    assert nota.get("format") == "docx"
    assert nota.get("automatic") is False
    assert nota.get("periodo"), f"{key}: la nota no declara periodo"
    assert ind.get("nota_disponible") is True
    rel = nota.get("path") or ind.get("url_nota_individual")
    assert rel, f"{key}: sin ruta de descarga"
    assert rel == f"downloads/indicadores/{key}/nota/{key}_nota.docx", rel
    assert ind.get("url_nota_individual") == rel
    path = ROOT / rel
    assert path.exists(), f"Falta la nota vigente de {key}: {rel}"
    assert path.suffix == ".docx"
    assert path.stat().st_size > MIN_DOCX_BYTES
    # Es un ZIP Office real, no un PDF renombrado ni un HTML.
    head = path.read_bytes()[:4]
    assert head[:2] == b"PK", f"{key}: el archivo no es un ZIP/Office"
    assert head != b"%PDF", f"{key}: la nota es un PDF, no un .docx"
    assert _docx_ok(path), f"{key}: falta word/document.xml en {rel}"


@pytest.mark.parametrize("key", SIN_NOTA)
def test_indicadores_sin_nota_quedan_deshabilitados(key):
    ind = PAYLOAD["indicators"][key]
    nota = ind.get("nota") or {}
    assert ind.get("nota_disponible") is not True
    assert nota.get("available") is not True
    assert ind.get("url_nota_individual") is None
    assert ind.get("nota_causa"), f"{key}: falta causa de nota no disponible"
    path = ROOT / "downloads" / "indicadores" / key / "nota" / f"{key}_nota.docx"
    assert not path.exists(), f"{key} no debería tener nota vigente: {path}"


def test_plantilla_maestra_existe():
    p = MACHOTE_DIR / "_PLANTILLA_MAESTRA.docx"
    assert p.exists(), "Falta data/source/notas_machote/_PLANTILLA_MAESTRA.docx"
    assert p.suffix == ".docx" and p.stat().st_size > 0
    assert _docx_ok(p)


@pytest.mark.parametrize("key", CON_NOTA)
def test_machote_existe_y_es_docx_valido(key):
    entry = MAP["notas"][key]
    p = ROOT / entry["machote"]
    assert p.exists(), f"{key}: falta machote {entry['machote']}"
    assert p.parent == MACHOTE_DIR, "los machotes viven en data/source/notas_machote/"
    assert p.name.endswith("_machote.docx")
    assert p.stat().st_size > MIN_DOCX_BYTES
    assert _docx_ok(p)
    with zipfile.ZipFile(p) as z:
        names = z.namelist()
        assert "word/document.xml" in names
        # Un machote Word real incluye estilos del documento.
        assert "word/styles.xml" in names


def test_pipeline_nunca_escribe_en_machotes():
    """provision_notes jamás modifica data/source/notas_machote/."""
    before = {f.name: (f.stat().st_mtime_ns, hashlib.sha256(f.read_bytes()).hexdigest())
              for f in MACHOTE_DIR.glob("*.docx")}
    import copy
    payload = copy.deepcopy(PAYLOAD)
    lib_notas.provision_notes(payload)
    after = {f.name: (f.stat().st_mtime_ns, hashlib.sha256(f.read_bytes()).hexdigest())
             for f in MACHOTE_DIR.glob("*.docx")}
    assert before == after, "El pipeline modificó archivos de data/source/notas_machote/"


def test_provision_notes_no_sobrescribe_nota_vigente():
    """Una nota vigente existente nunca se reemplaza por el machote."""
    payload = json.loads((ROOT / "data" / "indicadores.json").read_text(encoding="utf-8"))
    key = CON_NOTA[0]
    dest = lib_notas.nota_vigente_path(key)
    digest = hashlib.sha256(dest.read_bytes()).hexdigest()
    lib_notas.provision_notes(payload)
    assert hashlib.sha256(dest.read_bytes()).hexdigest() == digest


def test_boton_nota_descarga_docx_en_frontend():
    """El toolbar del indicador habilita NOTA con nota_disponible y descarga
    directa vía atributo download (sin preview ni visor externo)."""
    src = (ROOT / "assets" / "js" / "app.js").read_text(encoding="utf-8")
    assert "notaReady = !!ind.nota_disponible" in src
    assert 'productBtn("NOTA"' in src
    assert "a.download = fallbackName" in src
    assert "downloads/indicadores/${ind.key}/nota/${ind.key}_nota.docx" in src
    # El boletín y la nota son productos distintos: rutas separadas.
    assert "openBoletin(boletinUrl)" in src
    assert "downloadProduct(notaUrl(ind)" in src


def test_nota_y_boletin_no_apuntan_al_mismo_archivo():
    for key in CON_NOTA:
        ind = PAYLOAD["indicators"][key]
        boletin = ind.get("url_boletin_oficial") or ""
        nota = ind.get("url_nota_individual") or ""
        assert nota and boletin != nota, f"{key}: BOLETÍN y NOTA apuntan a lo mismo"
        assert nota.endswith(".docx")
