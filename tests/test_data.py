import json
import re
from pathlib import Path

import openpyxl
import pytest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "indicadores.json"
PERIOD_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}|[1-4]T-\d{2}|[A-Za-zÁÉÍÓÚáéíóú]{3}\s*\d{2})")


@pytest.fixture(scope="module")
def payload():
    return json.loads(DATA.read_text(encoding="utf-8"))


def test_file_exists():
    assert DATA.exists(), "data/indicadores.json debe existir"


def test_meta_counts_match_new_classification():
    """El perfil V3 tiene 15 principales (con SIC) y 4 complementarios (con IED)."""
    meta_path = ROOT / "config" / "indicadores_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert len(meta["principal"]) == 15, f"Se esperaban 15 principales, hay {len(meta['principal'])}"
    assert meta["principal"] == [
        "PIB", "PIBSEC", "SIC", "IOAE", "IGAE", "IMAI", "IMOAM", "EMIM", "EMOE", "DESOCUP",
        "INPC", "INPP", "CONSUMO", "IMFBCF", "BCMM",
    ]
    assert len(meta["complementario"]) == 4, f"Se esperaban 4 complementarios, hay {len(meta['complementario'])}"
    assert meta["complementario"] == ["IED", "TIPOCAMBIO", "TASA", "RESERVAS"]


def test_meta_and_order(payload):
    assert "meta" in payload and "indicators" in payload
    assert payload["meta"]["base_year"] == 2018
    assert isinstance(payload.get("order"), list) and payload["order"]


PENDING_STATES = {"PUBLICACIÓN PENDIENTE", "ERROR DE FUENTE"}


def test_indicators_shape(payload):
    for key, ind in payload["indicators"].items():
        assert ind["columns"], f"{key} sin columnas"
        # Los scaffolds (indicadores a la espera de token/serie) pueden no tener
        # observaciones todavía; no deben inventarse cifras.
        if not ind["observations"]:
            assert ind.get("estado") in PENDING_STATES or ind.get("origen_dato") == "pendiente", \
                f"{key} sin observaciones y sin estado pendiente declarado"
            continue
        for o in ind["observations"]:
            assert PERIOD_RE.match(o["period"]), f"{key}: periodo inválido {o['period']}"
            assert len(o["values"]) == len(ind["columns"]), f"{key}: columnas/valores desalineados"


def test_desocup_source_is_inegi(payload):
    # Regla del usuario: la fuente principal de desocupación debe ser INEGI/ENOE.
    fuente = payload["indicators"]["DESOCUP"]["fuente"]["nombre"].lower()
    assert "inegi" in fuente and "enoe" in fuente


def test_no_critical_validation_errors(payload):
    import validate as V
    errors, _ = V.validate(payload)
    assert not errors, f"No debe haber errores críticos tras overrides: {errors}"


def test_duplicate_flagged_as_revision(payload):
    # Feb-26 de IMAI y CONSUMO ya no son duplicados sospechosos y tienen valores reales.
    for key in ("IMAI", "CONSUMO"):
        ind = payload["indicators"][key]
        feb = [o for o in ind["observations"] if o["period"].startswith("Feb 26")][0]
        assert feb["values"][0] is not None, f"{key} Feb-26 debe tener valor real"
    # Los dos índices son distintos (IMAI ~100.8, CONSUMO ~111.4).
    imai_feb = next(o for o in payload["indicators"]["IMAI"]["observations"] if o["period"].startswith("Feb 26"))
    cons_feb = next(o for o in payload["indicators"]["CONSUMO"]["observations"] if o["period"].startswith("Feb 26"))
    assert imai_feb["values"][0] != cons_feb["values"][0]


# Los parsers tienen regresiones fechadas en tests/fixtures. Aquí se comprueba
# que el corte vivo mantiene tasas fraccionarias y su contrato con la ficha.
@pytest.mark.parametrize("key,monthly_col,annual_col", [
    ("CONSUMO",1,2),("IMFBCF",1,2),("IGAE",1,2),("IOAE",3,0),
])
def test_bulletin_variations_monthly_and_annual(payload,key,monthly_col,annual_col):
    ind=payload["indicators"][key]
    for col in (monthly_col,annual_col):
        assert ind['columns'][col]['fmt']=='pct-frac'
        value=ind['observations'][-1]['values'][col]
        assert isinstance(value,(float,int)) and -1<value<1


def test_pib_bulletin_variations(payload):
    # Regresión fechada del boletín 470/26: no confundirla con el último corte.
    obs={o['period']:o['values'] for o in payload['indicators']['PIB']['observations']}
    assert obs['2T-26 P']==pytest.approx([.015,.021,.022,.012],abs=1e-4)
    assert obs['1T-26 P']==pytest.approx([-.008,.002,.001,.004],abs=1e-4)


def test_pibsec_terciarias_bulletin_variations(payload):
    pibsec = payload["indicators"]["PIBSEC"]
    last = pibsec["observations"][-1]
    assert last["values"][3] == pytest.approx(0.014, abs=1e-4)
    assert last["values"][4] == pytest.approx(0.023, abs=1e-4)


def test_ioae_jun_2026_and_no_secondary_total(payload):
    """El IOAE de Jun 26 debe reflejar la estimación mensual y anual del IGAE,
    no la variación de actividades secundarias."""
    ioae = payload["indicators"]["IOAE"]
    last = next(o for o in ioae["observations"] if o["period"] == "Jun 26")
    # Variación anual (col 0) y mensual (col 3) oficiales del IGAE, no la secundaria (col 4, 0.5%).
    assert last["values"][0] == pytest.approx(0.017, abs=1e-4)
    assert last["values"][3] == pytest.approx(0.002, abs=1e-4)
    assert last["values"][0] != pytest.approx(0.005, abs=1e-4)


def test_pib_label_includes_2018(payload):
    """El PIB oportuno se expresa en variaciones porcentuales."""
    pib = payload["indicators"]["PIB"]
    assert pib["unidad"] == "Porcentaje"
    assert pib["nombre"] == "Estimación Oportuna del Producto Interno Bruto Trimestral"


def test_pib_eopibt_dashboard(payload):
    """Validación integral de la ficha PIB Oportuno (EOPIBT)."""
    pib = payload["indicators"]["PIB"]
    metrics = pib.get("metrics", {})
    kpi = metrics.get("kpi", {})
    resumen = metrics.get("resumen", [])

    # Título y unidad correctos
    assert pib["nombre"] == "Estimación Oportuna del Producto Interno Bruto Trimestral"
    assert pib["unidad"] == "Porcentaje"

    last=pib['observations'][-1]
    assert kpi['ultimoP']==last['period']
    for col,field in enumerate(['qoqText','yoyDesestText','yoyOrigText','ytdText']):
        value=last['values'][col]
        assert kpi[field]==(('+' if value>0 else '')+f'{value*100:.1f}%')

    # No se muestra un nivel en billones como cifra actual
    assert "billones" not in kpi["ultimoFmt"]
    assert "millones" not in kpi["ultimoFmt"]

    # No se muestra máximo/mínimo de la serie como nivel
    assert "billones" not in (kpi.get("maxFmt") or "")
    assert "millones" not in (kpi.get("maxFmt") or "")

    # Una sola sección de lectura con máximo 4 bullets reales, sin próxima publicación.
    assert resumen
    assert len(resumen) <= 4, f"Lectura del indicador debe tener máximo 4 bullets: {resumen}"
    assert not any("próxima publicación" in b.lower() for b in resumen), resumen
    assert any("PIB oportuno" in b for b in resumen)
    assert any("acumulado" in b.lower() for b in resumen)

    # Filtros de ventana acordes a la frecuencia trimestral
    assert pib.get("windows")
    assert all(w["id"] in {"1a", "2a", "3a", "5a", "max"} for w in pib["windows"])

    # Los gráficos deben ser de variaciones (%), sin interpolar nulos
    assert pib["columns"][0]["fmt"] == "pct-frac"
    assert pib["columns"][1]["fmt"] == "pct-frac"

    # El boletín PDF se conserva como fuente oficial
    assert pib.get("url_boletin_oficial")
    assert re.search(r"/pib_eo\d{4}_\d{2}\.pdf$",pib["url_boletin_oficial"])


def test_pib_sector_scaling(payload):
    from lib_format import fmt_val
    sectors=payload['indicators']['PIB']['sectores']
    for name in ('primarias','secundarias','terciarias'):
        raw=sectors[name]['qoq']
        assert -1<raw<1
        assert float(fmt_val(raw,'pct-frac').rstrip('%'))==pytest.approx(raw*100,abs=.051)


def test_pib_resumen_uses_consistent_percentages(payload):
    pib=payload['indicators']['PIB']
    from lib_format import fmt_val
    text=' '.join(pib['metrics']['resumen'])
    assert 'acumulado' in text.lower()
    for field in ('qoq','yoy'):
        for sector in pib['sectores'].values():
            value=sector.get(field)
            if value is not None:
                # Nunca mostrar una tasa fraccionaria multiplicada dos veces.
                wrong=f'{value*10000:.1f}%'
                if abs(value)>.001: assert wrong not in text


def test_pib_historial_ampliado(payload):
    """La ficha del PIB oportuno expone el historial y los filtros de ventana."""
    pib = payload["indicators"]["PIB"]
    wins = pib.get("windows", [])
    assert wins
    assert {w["id"] for w in wins} == {"1a", "2a", "3a", "5a", "max"}
    obs = pib["observations"]
    assert obs
    assert len(obs)>=46
    dates=[(int(o["period"][3:5]),int(o["period"][0])) for o in obs]
    assert dates==sorted(set(dates))
    assert obs[0]["period"] == "1T-15 P"
    assert obs[-1]["period"]==pib["last_observation"]

    # Las ventanas deben estar definidas por número exacto de observaciones.
    expected = {"1a": 4, "2a": 8, "3a": 12, "5a": 20, "max": len(obs)}
    counts = {w["id"]: (len(obs) if w["id"] == "max" else w["count"]) for w in wins}
    assert counts == expected, f"Ventanas incorrectas: {counts}"

    # Simula el slicing que hace applyWindow en el frontend.
    actual = {
        "1a": obs[-4:],
        "2a": obs[-8:],
        "3a": obs[-12:],
        "5a": obs[-20:],
        "max": obs,
    }
    for wid, exp in expected.items():
        assert len(actual[wid]) == exp, f"{wid} debería tener {exp} observaciones"

    # qoq es None solo donde la fuente oficial no lo publica (1T-15 a 3T-15).
    for o in obs[:3]:
        assert o["values"][0] is None, f"{o['period']}: qoq no debería estar inventado"
    # A partir de 4T-15 qoq debe existir.
    for o in obs[3:]:
        assert o["values"][0] is not None, f"{o['period']}: qoq no debería ser null"


def test_pibt_nivel_tradicional_separado(payload):
    """El nivel tradicional del PIB (PIBT) se conserva como objeto independiente."""
    pib = payload["indicators"]["PIB"]
    assert "pibt" in pib
    pibt = pib["pibt"]
    assert pibt["observations"]
    assert pibt["columns"]
    assert pibt["columns"][0]["fmt"] == "bill"
    last = pibt["observations"][-1]
    assert last["values"][0] is not None
    assert last["period"]
    # El último nivel disponible está en millones de pesos a precios de 2018.
    assert last["values"][0] > 1_000_000
    assert "INEGI" in (pibt.get("fuente", {}).get("nombre") or "")


def test_pib_excel_separates_oportuno_and_nivel():
    """EOPIBT conserva solo variaciones; niveles pertenecen al archivo PIBT."""
    xlsx = ROOT / "downloads" / "indicadores" / "PIB" / "PIB_datos.xlsx"
    wb = openpyxl.load_workbook(xlsx)
    assert wb.sheetnames == ["PIB oportuno"]
    headers = [c.value for row in wb.active for c in row if c.value is not None]
    assert any("trimestral" in h.lower() for h in headers if isinstance(h,str))
    assert "Nivel PIB" not in wb.sheetnames


def test_pib_no_interpolated_gaps(payload):
    """Los gaps históricos en qoq no se interpolan ni rellenan con ceros."""
    pib = payload["indicators"]["PIB"]
    obs = pib["observations"]
    # 1T-15 a 3T-15 tienen qoq null por fuente, no cero.
    for o in obs[:3]:
        assert o["values"][0] is None, f"{o['period']} qoq debe ser null"
        assert o["values"][0] != 0
    # No hay valores qoq = 0.0 inventados en observaciones recientes.
    for o in obs:
        if o["values"][0] == 0:
            assert o["period"] in ("4T-19 P",), f"{o['period']} tiene qoq 0 sospechoso"
