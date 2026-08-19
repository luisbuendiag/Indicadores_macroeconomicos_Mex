import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "indicadores.json"
PERIOD_RE = re.compile(r"^([1-4]T-\d{2}|[A-Za-zÁÉÍÓÚáéíóú]{3}\s*\d{2})")


@pytest.fixture(scope="module")
def payload():
    return json.loads(DATA.read_text(encoding="utf-8"))


def test_file_exists():
    assert DATA.exists(), "data/indicadores.json debe existir"


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


# Regresión: variaciones oficiales del boletín INEGI.
# Se comparan con los valores públicados en los boletines más recientes.
@pytest.mark.parametrize("key,monthly_col,annual_col,expected_monthly,expected_annual", [
    ("CONSUMO", 1, 2, 0.001, 0.026),
    ("IMFBCF", 1, 2, -0.004, 0.024),
    ("IGAE", 3, 4, -0.003, 0.02),
    ("IOAE", 0, 1, 0.2, 1.7),
])
def test_bulletin_variations_monthly_and_annual(payload, key, monthly_col, annual_col, expected_monthly, expected_annual):
    ind = payload["indicators"][key]
    last = ind["observations"][-1]
    assert last["values"][monthly_col] == pytest.approx(expected_monthly, abs=1e-4)
    assert last["values"][annual_col] == pytest.approx(expected_annual, abs=1e-4)


def test_pib_bulletin_variations(payload):
    pib = payload["indicators"]["PIB"]
    last = pib["observations"][-1]
    penult = pib["observations"][-2]
    # Última fila: estimación oportuna 2T-26 (variaciones, no nivel).
    assert last["period"] == "2T-26 P"
    assert last["values"][0] == pytest.approx(0.015, abs=1e-4)  # qoq
    assert last["values"][1] == pytest.approx(0.021, abs=1e-4)  # yoy desest
    assert last["values"][2] == pytest.approx(0.022, abs=1e-4)  # yoy orig
    assert last["values"][3] == pytest.approx(0.012, abs=1e-4)  # acumulado
    # Penúltima fila: 1T-26.
    assert penult["period"] == "1T-26 P"
    assert penult["values"][0] == pytest.approx(-0.008, abs=1e-4)
    assert penult["values"][1] == pytest.approx(0.002, abs=1e-4)
    assert penult["values"][2] == pytest.approx(0.001, abs=1e-4)
    assert penult["values"][3] == pytest.approx(0.004, abs=1e-4)


def test_pibsec_terciarias_bulletin_variations(payload):
    pibsec = payload["indicators"]["PIBSEC"]
    last = pibsec["observations"][-1]
    assert last["values"][3] == pytest.approx(-0.004, abs=1e-4)
    assert last["values"][4] == pytest.approx(0.011, abs=1e-4)


def test_ioae_jun_2026_and_no_secondary_total(payload):
    """El IOAE de Jun 26 debe reflejar la estimación mensual y anual del IGAE,
    no la variación de actividades secundarias."""
    ioae = payload["indicators"]["IOAE"]
    last = next(o for o in ioae["observations"] if o["period"] == "Jun 26")
    # Variación mensual y anual oficiales del IGAE, no la secundaria (0.5%).
    assert last["values"][0] == pytest.approx(0.2, abs=1e-4)
    assert last["values"][1] == pytest.approx(1.7, abs=1e-4)
    assert last["values"][0] != pytest.approx(0.5, abs=1e-4)


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

    # Último periodo y KPIs del boletín 470/26
    assert kpi["ultimoP"] == "2T-26 P"
    assert kpi["qoqText"] == "+1.5%"
    assert kpi["yoyDesestText"] == "+2.1%"
    assert kpi["yoyOrigText"] == "+2.2%"
    assert kpi["ytdText"] == "+1.2%"

    # No se muestra un nivel en billones como cifra actual
    assert "billones" not in kpi["ultimoFmt"]
    assert "millones" not in kpi["ultimoFmt"]

    # No se muestra máximo/mínimo de la serie como nivel
    assert "billones" not in (kpi.get("maxFmt") or "")
    assert "millones" not in (kpi.get("maxFmt") or "")

    # Una sola sección de lectura (resumen consolidado)
    assert len(resumen) >= 3
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
    assert "pib_eo2026_07.pdf" in pib["url_boletin_oficial"]


def test_pib_sector_scaling(payload):
    """Las variaciones por actividad se almacenan como fracción y se presentan como 3.3%, no 330%."""
    pib = payload["indicators"]["PIB"]
    sectores = pib.get("sectores", {})
    assert pytest.approx(sectores["primarias"]["qoq"], abs=1e-4) == 0.033
    assert pytest.approx(sectores["secundarias"]["qoq"], abs=1e-4) == 0.016
    assert pytest.approx(sectores["terciarias"]["qoq"], abs=1e-4) == 0.015
    # Los valores anuales también se almacenan en escala fraccionaria.
    assert sectores["primarias"].get("yoy") is None or pytest.approx(sectores["primarias"]["yoy"], abs=1e-4) == 0.073


def test_pib_resumen_uses_consistent_percentages(payload):
    pib = payload["indicators"]["PIB"]
    resumen = pib.get("metrics", {}).get("resumen", [])
    sector_bullet = next((b for b in resumen if "Avance generalizado" in b or "actividad económica" in b), "")
    assert sector_bullet
    assert "+3.3%" in sector_bullet
    assert "+1.6%" in sector_bullet
    assert "+1.5%" in sector_bullet
    assert "330%" not in sector_bullet
    assert "160%" not in sector_bullet
    assert "150%" not in sector_bullet


def test_pib_historial_ampliado(payload):
    """La ficha del PIB oportuno expone el historial y los filtros de ventana."""
    pib = payload["indicators"]["PIB"]
    wins = pib.get("windows", [])
    assert wins
    assert {w["id"] for w in wins} == {"1a", "2a", "3a", "5a", "max"}
    assert pib["observations"]
    # El periodo inicial es la primera observación publicada en el boletín.
    assert pib["observations"][0]["period"]


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
