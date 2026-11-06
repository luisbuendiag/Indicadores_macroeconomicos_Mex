import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "indicadores.json"


def _load():
    return json.loads(DATA.read_text(encoding="utf-8"))["indicators"]["TASA"]


def test_tasa_nombre_y_no_tiie():
    ind = _load()
    assert "Tasa de Interes Interbancaria" in ind["nombre"]
    assert "objetivo" in ind["nombre"].lower()
    assert "TIIE" not in ind["nombre"]
    assert "no confundir con la tiie" in ind["descripcion"].lower()


def test_tasa_vigente_coincide_con_serie_y_decision():
    ind=_load()
    assert ind['tasa_vigente']==pytest.approx(ind['observations'][-1]['values'][0])
    assert ind['metrics']['kpi']['ultimoFmt']==f"{ind['tasa_vigente']:.2f}%"
    assert ind['tasa_vigente']==ind['policy_decisions'][-1]['new_rate']


def test_tasa_ultima_decision_y_cambio_en_pb():
    decisions=_load()['policy_decisions']
    assert [d['announcement_date'] for d in decisions]==sorted(set(d['announcement_date'] for d in decisions))
    for d in decisions:
        assert d['change_bp']==pytest.approx((d['new_rate']-d['previous_rate'])*100)
        assert d['effective_date']>=d['announcement_date']
        assert d['decision']==('recorte' if d['change_bp']<0 else 'alza' if d['change_bp']>0 else 'sin cambio')


def test_tasa_ultimo_ajuste_y_vigencia():
    ind=_load()
    adjusted=[d for d in ind['policy_decisions'] if d['change_bp']!=0]
    assert ind['ultimo_ajuste']==adjusted[-1]
    assert ind['vigente_desde']==adjusted[-1]['effective_date']


def test_tasa_proxima_decision_posterior_a_la_ultima():
    ind=_load(); kpi=ind['metrics']['kpi']
    assert kpi['nextDecisionP']>ind['policy_decisions'][-1]['announcement_date']
    assert any((e.get('publication_date') or e.get('fecha_iso'))==kpi['nextDecisionP'] for e in ind['calendario_publicaciones'])


def test_tasa_no_cambio_diario_kpi():
    ind = _load()
    kpi = ind["metrics"]["kpi"]
    assert "cambio diario" not in kpi.get("varLabel", "").lower()
    assert kpi.get("varLabel") == "Último ajuste"


def test_tasa_no_maximo_minimo_kpi():
    ind = _load()
    kpi = ind["metrics"]["kpi"]
    assert "máximo" not in kpi or not kpi.get("maxFmt")
    assert "mínimo" not in kpi or not kpi.get("minFmt")


def test_tasa_resumen_bullets():
    ind = _load()
    resumen = ind["metrics"]["resumen"]
    assert len(resumen) <= 4
    from lib_format import per_long
    assert any(f"{ind['tasa_vigente']:.2f}%" in b for b in resumen)
    assert any('último ajuste' in b.lower() for b in resumen)
    assert any('próxima decisión' in b.lower() for b in resumen)


def test_tasa_decisions_tiene_comunicados():
    ind = _load()
    decisions = ind["policy_decisions"]
    assert decisions
    for d in decisions:
        if d.get("comunicado_url"):
            assert d["comunicado_url"].startswith("https://")


def test_tasa_excel_tiene_dos_hojas():
    xlsx = ROOT / "downloads" / "indicadores" / "TASA" / "TASA_datos.xlsx"
    assert xlsx.exists(), f"No se generó {xlsx}"
    from openpyxl import load_workbook
    wb = load_workbook(xlsx)
    try:
        assert "Serie diaria" in wb.sheetnames
        assert "Decisiones" in wb.sheetnames
    finally:
        wb.close()
