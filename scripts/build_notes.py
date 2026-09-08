"""Aprovisiona las notas institucionales (.docx) por indicador.

La nota vigente ya no se genera en el pipeline: son documentos institucionales
existentes que se sirven desde ``downloads/indicadores/{KEY}/nota/{KEY}_nota.docx``.
Este script delega en ``lib_notas.provision_notes``, que:

- copia el machote a la ruta de descarga sólo cuando falta la nota vigente;
- valida que cada nota sea un .docx real (word/document.xml);
- estampa ``ind['nota']``, ``nota_disponible``, ``url_nota_individual`` y
  ``nota_causa`` en ``data/indicadores.json``;
- jamás escribe en ``data/source/notas_machote/``.

Fase futura (no implementada): nuevo boletín -> datos oficiales -> copiar
machote -> actualizar contenidos/gráficas -> validar -> ``update_nota_vigente``.
"""
from __future__ import annotations

import argparse
import json

import lib_data as L
import lib_notas


def main() -> int:
    ap = argparse.ArgumentParser(description="Aprovisiona notas institucionales .docx")
    args = ap.parse_args()

    payload = L.load_data()
    report = lib_notas.provision_notes(payload)
    (L.DATA_DIR / "indicadores.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )

    total = len(report["provided"]) + len(report["existing"])
    print(f"OK: {total} notas vigentes disponibles "
          f"({len(report['provided'])} copiadas desde machote, {len(report['existing'])} ya existentes)")
    if report["missing_machote"]:
        print("Aviso: sin machote válido ->", ", ".join(report["missing_machote"]))
    if report["invalid"]:
        print("ERROR: notas inválidas ->", ", ".join(report["invalid"]))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
