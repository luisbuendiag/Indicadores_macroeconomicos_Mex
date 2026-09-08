"""Notas institucionales por indicador (documentos Word .docx).

Arquitectura permanente de tres piezas:

- ``data/source/notas_machote/`` — machotes por indicador (estructura editorial
  congelada) más ``_PLANTILLA_MAESTRA.docx``, la fuente de verdad visual
  institucional. El pipeline NUNCA escribe en este directorio: los machotes son
  entradas de sólo lectura.
- ``downloads/indicadores/{KEY}/nota/{KEY}_nota.docx`` — la NOTA VIGENTE que
  descarga el usuario desde el botón NOTA. Siempre Word .docx.
- ``config/notas_map.json`` — mapa indicador -> machote + metadatos de la nota
  vigente (periodo, título, fuente original).

Automatización futura (fase siguiente, NO implementada): nuevo boletín ->
leer datos oficiales -> copiar el machote del indicador -> actualizar contenidos
y gráficas -> validar el .docx resultante -> reemplazar la nota vigente. El
punto de extensión previsto es ``update_nota_vigente``; en esta fase la nota
vigente es un documento institucional existente, provisto sin alterar cifras
ni redacciones.
"""
from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MAP_FILE = ROOT / "config" / "notas_map.json"
MACHOTE_DIR = ROOT / "data" / "source" / "notas_machote"
DOWNLOADS_DIR = ROOT / "downloads" / "indicadores"

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
CAUSA_SIN_NOTA = "Nota institucional en preparación"


def load_map() -> dict[str, Any]:
    """Carga config/notas_map.json; devuelve el bloque 'notas' (vacío si falta)."""
    if not MAP_FILE.exists():
        return {}
    data = json.loads(MAP_FILE.read_text(encoding="utf-8"))
    return dict(data.get("notas", {}))


def nota_vigente_path(key: str) -> Path:
    """Ruta pública de la nota vigente de un indicador."""
    return DOWNLOADS_DIR / key / "nota" / f"{key}_nota.docx"


def nota_vigente_rel(key: str) -> str:
    return str(nota_vigente_path(key).relative_to(ROOT))


def is_valid_docx(path: Path) -> bool:
    """Un .docx real es un ZIP Office que contiene word/document.xml."""
    try:
        with zipfile.ZipFile(path) as z:
            return "word/document.xml" in z.namelist()
    except (zipfile.BadZipFile, OSError):
        return False


def machote_path(entry: dict) -> Path:
    return ROOT / entry.get("machote", "")


def update_nota_vigente(key: str, source_docx: Path) -> Path:
    """Punto de extensión para la fase de automatización.

    Reemplaza la NOTA VIGENTE con un .docx nuevo, validado, sin tocar el
    machote del indicador. Pensado para: nuevo boletín -> contenido actualizado
    sobre una copia del machote -> validación -> ``update_nota_vigente``.
    """
    src = Path(source_docx)
    if not is_valid_docx(src):
        raise ValueError(f"{src} no es un .docx válido")
    dest = nota_vigente_path(key)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest)
    return dest


def provision_notes(payload: dict) -> dict[str, Any]:
    """Asegura las notas vigentes y estampa los metadatos en el payload.

    Para cada indicador mapeado en ``config/notas_map.json``:

    1. Si falta ``downloads/indicadores/{key}/nota/{key}_nota.docx`` se copia
       desde el machote (la nota vigente inicial es la estructura del machote).
       Nunca se sobrescribe una nota vigente existente ni el machote.
    2. Se valida que el resultado sea un .docx real (word/document.xml).
    3. Se estampan ``ind['nota']``, ``nota_disponible``, ``url_nota_individual``
       y ``nota_causa``.

    Los indicadores sin nota (IED, TIPOCAMBIO, TASA, RESERVAS) quedan
    explícitamente deshabilitados.
    """
    notes_map = load_map()
    report = {"provided": [], "existing": [], "missing_machote": [], "invalid": []}
    for key, ind in payload.get("indicators", {}).items():
        entry = notes_map.get(key)
        dest = nota_vigente_path(key)
        if not entry:
            ind["nota"] = {"available": False, "format": "docx", "automatic": False}
            ind["nota_disponible"] = False
            ind["nota_causa"] = CAUSA_SIN_NOTA
            ind["url_nota_individual"] = None
            continue

        if not dest.exists():
            src = machote_path(entry)
            if src.exists() and is_valid_docx(src):
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, dest)
                report["provided"].append(key)
            else:
                report["missing_machote"].append(key)
        else:
            report["existing"].append(key)

        ok = dest.exists() and is_valid_docx(dest)
        if not ok:
            report["invalid"].append(key)
        ind["nota"] = {
            "available": ok,
            "format": "docx",
            "path": nota_vigente_rel(key),
            "periodo": entry.get("periodo"),
            "generated_from": "machote",
            "automatic": False,
        }
        ind["nota_disponible"] = ok
        ind["nota_causa"] = None if ok else CAUSA_SIN_NOTA
        ind["url_nota_individual"] = nota_vigente_rel(key) if ok else None
    return report
