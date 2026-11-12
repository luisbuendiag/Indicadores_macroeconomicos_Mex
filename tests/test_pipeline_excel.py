import json
from pathlib import Path

import openpyxl
import pytest

import build_data
import build_excel
import build_calendar
import lib_data as L

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def preserve_pipeline_files():
    # Los tests de integración pueden escribir: restaurar también cuando fallan.
    paths=list((ROOT/'data').rglob('*.json'))+[ROOT/'config/kpicfg.json']
    original={p:p.read_bytes() for p in paths}
    yield
    for p,content in original.items():p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(content)


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


def test_apply_overrides_nulls_duplicate(tmp_path):
    from extract_legacy import load_macro, normalize
    macro = load_macro(ROOT / "legacy" / "dashboard-original.html")
    fresh = normalize(macro)
    # Crear un override de prueba y aplicarlo
    overrides_file = tmp_path / "overrides.json"
    overrides_file.write_text(json.dumps({
        "overrides": [{
            "indicator": "IMAI",
            "period": "Feb 26 P",
            "column": 0,
            "status": "revision",
            "value": None,
            "reason": "Test override",
        }]
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    log = L.apply_overrides(fresh, overrides_file)
    assert log, "debe registrar cambios de override"
    feb_imai = [o for o in fresh["indicators"]["IMAI"]["observations"] if o["period"].startswith("Feb 26")][0]
    assert feb_imai["values"][0] is None


def test_excel_has_historical_sheets_only(tmp_path):
    payload=json.loads((ROOT / "data/indicadores.json").read_text())
    report=build_excel.generate(payload,tmp_path)
    wb=openpyxl.load_workbook(tmp_path/build_excel.OUT_XLSX.name)
    # 22 hojas históricas tradicionales + anexos genuinos de IED estatal.
    # No eliminar los anexos para satisfacer un conteo de la versión anterior.
    has_ied = (ROOT / "data/ied_estatal.json").is_file()
    has_revised = (ROOT / "data/ied_estatal_actualizada.json").is_file()
    extras = ({"IED Historia estatal", "IED Ranking estatal", "IED Cifras originales"}
              if has_ied else set())
    if has_ied and has_revised:
        extras.add("IED Estatal revisada")
    assert len(wb.sheetnames) == 22 + len(extras)
    assert len(report) == 20
    assert not {"Resumen ejecutivo","Síntesis de coyuntura","Metodología y fuentes","Control de actualizaciones"}.intersection(wb.sheetnames)
    assert {"PIB","PIBT","SIC","IGAE","BCMM","INPC","INPP","ENOE","Población ocupada","IMFBCF","IOAE","EMIM","EMOE","IED","FIX","TASA","RESERVAS"} <= set(wb.sheetnames)
    assert extras <= set(wb.sheetnames)
    # Hojas de series se grafican; la historia y originales estatales son bases
    # tabulares auditables (el ranking sí debe conservar su gráfica).
    source_tables = {"IED Historia estatal", "IED Cifras originales", "IED Estatal revisada"}
    assert all(ws._charts for ws in wb if ws.title not in source_tables)
    if has_ied:
        rank = wb["IED Ranking estatal"]
        assert rank._charts
        assert isinstance(rank["B4"].value, str) and rank["B4"].value.startswith("=")


def test_calendar_build_and_schema():
    rc = build_calendar.main()
    assert rc == 0
    cal = json.loads((L.DATA_DIR / "calendario_publicaciones.json").read_text(encoding="utf-8"))
    assert cal["items"], "el calendario debe tener publicaciones"
    required = {"clave", "indicador", "producto", "fecha_publicacion", "fecha_iso",
                "periodo_referencia", "frecuencia", "institucion", "estatus"}
    valid_statuses = {"publicado", "próximo", "pendiente", "no_anunciada", "evento", "regla"}
    for it in cal["items"]:
        assert required <= set(it), f"faltan campos en {it}"
        assert it["estatus"] in valid_statuses
    # fechas exactas ordenadas; items sin fecha (reglas) se dejan al final
    isos = [it["fecha_iso"] or "" for it in cal["items"]]
    assert isos == sorted(isos, key=lambda x: (x or "", 0 if x else 1))


def test_sources_live_with_the_history_not_in_admin_tabs(tmp_path):
    payload=json.loads((ROOT / "data/indicadores.json").read_text())
    model=build_excel.build_workbook([payload['indicators']['IGAE']])
    ws=model.wb.active
    assert ws['A3'].hyperlink
    assert 'Fuente:' in ws['A3'].value
    assert not any('Control' in name or 'Metodología' in name for name in model.wb.sheetnames)
