import json
from pathlib import Path

import openpyxl
import pytest

import build_data
import build_excel
import build_calendar
import lib_data as L

ROOT = Path(__file__).resolve().parents[1]


def test_offline_pipeline_ok():
    rc = build_data.run(offline=True)
    assert rc == 0
    assert (L.DATA_DIR / "manifest.json").exists()
    assert (L.DATA_DIR / "update_log.json").exists()


def test_backup_and_restore(tmp_path):
    # backup_current crea last_valid; restore_last_valid lo recupera
    L.backup_current()
    assert (L.BACKUP_DIR / "last_valid.json").exists()
    assert L.restore_last_valid() is True


def test_apply_overrides_nulls_duplicate():
    payload = json.loads((ROOT / "data" / "source" if False else L.DATA_FILE).read_text(encoding="utf-8"))
    # recargar datos crudos del legado y aplicar overrides desde cero
    from extract_legacy import load_macro, normalize
    macro = load_macro(ROOT / "legacy" / "dashboard-original.html")
    fresh = normalize(macro)
    log = L.apply_overrides(fresh)
    assert log, "debe registrar cambios de override"
    feb_imai = [o for o in fresh["indicators"]["IMAI"]["observations"] if o["period"].startswith("Feb 26")][0]
    assert feb_imai["values"][0] is None


def test_excel_has_new_sheets(tmp_path):
    build_calendar.main()  # calendario oficial disponible para la hoja de control
    build_excel.main()
    out = ROOT / "downloads" / "Indicadores_Macroeconomicos_Mexico_Actualizado.xlsx"
    assert out.exists()
    wb = openpyxl.load_workbook(out, read_only=True)
    for req in ("Síntesis de coyuntura", "Metodología y fuentes", "Control de actualizaciones"):
        assert req in wb.sheetnames
    assert "Resumen ejecutivo" not in wb.sheetnames
    # se conservan exactamente 16 hojas
    assert len(wb.sheetnames) == 16
    # hojas originales conservadas
    for orig in ("PIB", "IGAE", "Balanza comercial", "INPC (Inflación)"):
        assert orig in wb.sheetnames


def test_calendar_build_and_schema():
    rc = build_calendar.main()
    assert rc == 0
    cal = json.loads((L.DATA_DIR / "calendario_publicaciones.json").read_text(encoding="utf-8"))
    assert cal["items"], "el calendario debe tener publicaciones"
    required = {"clave", "indicador", "producto", "fecha_publicacion", "fecha_iso",
                "periodo_referencia", "frecuencia", "institucion", "estatus"}
    for it in cal["items"]:
        assert required <= set(it), f"faltan campos en {it}"
        assert it["estatus"] in ("publicado", "próximo", "pendiente")
    # fechas exactas (no provisionales) y ordenadas
    isos = [it["fecha_iso"] for it in cal["items"]]
    assert isos == sorted(isos)


def test_control_sheet_reflects_calendar():
    build_calendar.main()
    build_excel.main()
    out = ROOT / "downloads" / "Indicadores_Macroeconomicos_Mexico_Actualizado.xlsx"
    wb = openpyxl.load_workbook(out, read_only=True)
    ws = wb["Control de actualizaciones"]
    headers = [c.value for c in list(ws.iter_rows(min_row=4, max_row=4))[0]]
    assert "Próxima publicación (calendario)" in headers
