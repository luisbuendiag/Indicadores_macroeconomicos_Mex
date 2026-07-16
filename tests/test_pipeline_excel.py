import json
from pathlib import Path

import openpyxl
import pytest

import build_data
import build_excel
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
    build_excel.main()
    out = ROOT / "downloads" / "Indicadores_Macroeconomicos_Mexico_Actualizado.xlsx"
    assert out.exists()
    wb = openpyxl.load_workbook(out, read_only=True)
    for req in ("Resumen ejecutivo", "Metodología y fuentes", "Control de actualizaciones"):
        assert req in wb.sheetnames
    # hojas originales conservadas
    for orig in ("PIB", "IGAE", "Balanza comercial", "INPC (Inflación)"):
        assert orig in wb.sheetnames
