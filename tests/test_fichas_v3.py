import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

INDEX = (ROOT / "index.html").read_text(encoding="utf-8")
APP = (ROOT / "assets" / "js" / "app.js").read_text(encoding="utf-8")
CONFIG = (ROOT / "assets" / "js" / "config.js").read_text(encoding="utf-8")
METRICS = (ROOT / "assets" / "js" / "metrics.js").read_text(encoding="utf-8")
CSS = (ROOT / "assets" / "css" / "styles.css").read_text(encoding="utf-8")
INDICADORES = json.loads((ROOT / "data" / "indicadores.json").read_text(encoding="utf-8"))


def test_no_investment_advice_wording():
    for txt in (INDEX, APP):
        assert "asesoría de inversión" not in txt
    assert "Documento de trabajo para consulta y seguimiento estadístico" in INDEX
    assert "Documento de trabajo para consulta y seguimiento estadístico" in APP


def test_no_generic_inegi_banxico_source_in_fichas():
    assert "INEGI / Banco de México" not in INDEX
    assert "Ficha de seguimiento estadístico" in INDEX
    assert "Fuente oficial:" in APP


def test_igae_official_name():
    igae = INDICADORES["indicators"]["IGAE"]
    assert igae["nombre"] == "Indicador Global de la Actividad Económica"
    assert "(IGAE)" not in igae["nombre"]


def test_inpc_uses_puntos_porcentuales():
    m = re.search(r"INPC:\s*\{[^}]*\}", CONFIG)
    assert m, "no se encontró la configuración de INPC"
    inpc = m.group(0)
    assert "ppLong: true" in inpc
    assert "Cambio de la inflación anual respecto al mes previo" in inpc
    assert "puntos porcentuales" in METRICS


def test_publication_date_and_lag_separated():
    assert "Fecha de publicación del dato" in APP
    assert "Rezago habitual" in APP


def test_balance_saldo_vs_variacion_distinct():
    # BCMM reemplaza a la antigua ficha BALANZA.
    assert "BALANZA" not in CONFIG
    assert "BCMM" in CONFIG
    m = re.search(r"BCMM:\s*\{[^}]*\}", CONFIG)
    assert m
    bal = m.group(0)
    assert 'derived: "saldo"' in bal
    assert "Variación mensual del saldo" in bal
    assert "Saldo (X − M)" in APP


def test_exactly_twelve_principal_indicators():
    m = re.search(r"PRINCIPAL\s*=\s*\[(.*?)\]", CONFIG, re.S)
    assert m, "no se encontró PRINCIPAL"
    claves = re.findall(r'"([^"]+)"', m.group(1))
    assert len(claves) == 12, claves


def test_pib_prose_uses_percentage_not_billions_for_variations():
    m = re.search(r'if \(k === "PIB"\) return ([^;]+);', METRICS)
    assert m
    # Las variaciones del PIB oportuno se presentan en porcentaje;
    # el nivel histórico en billones se conserva como respaldo.
    assert ("* 100" in m.group(1) or "%" in m.group(1))
    assert "$" not in m.group(1)


def test_ioae_uses_mensual_and_anual_not_pp():
    m = re.search(r'IOAE:\s*\{[^}]*\}', CONFIG)
    assert m, "no se encontró la configuración de IOAE"
    ioae = m.group(0)
    assert 'varLabel: "Estimación mensual"' in ioae
    assert 'yoyLabel: "Estimación anual"' in ioae
    assert 'varMode:' not in ioae or 'varMode: ""' in ioae
    assert "pp-prev" not in ioae
    assert "puntos porcentuales" not in ioae


def test_pibsec_card_labels_short_for_side_by_side():
    m = re.search(r'PIBSEC:\s*\{[^}]*\}', CONFIG)
    assert m, "no se encontró la configuración de PIBSEC"
    pibsec = m.group(0)
    assert "Trim." in pibsec and "Anual" in pibsec
    # El CSS permite que las etiquetas largas se ajusten sin desbordar.
    assert "mc-deltas { display: flex; gap: 14px; flex-wrap: nowrap;" in CSS
    assert "word-break: break-word" in CSS


def test_all_indicators_have_indicator_view():
    """Cada clave en ORDER genera una vista de ficha individual."""
    assert '...ORDER.map((k) => ({ id: k, type: "indicator"' in CONFIG
    assert 'VIEWS.filter((v) => v.type === "indicator").forEach((v) => renderIndicatorView(v.key))' in APP
    from lib_kpicfg import get_cfg
    for k in [*get_cfg("PRINCIPAL"), *get_cfg("COMPLEMENTARIOS")]:
        assert f'"{k}"' in CONFIG


def test_financial_cards_open_individual_view():
    """Las tarjetas del Entorno financiero usan setView(clave)."""
    entorno_render = re.search(r"function renderEntorno\(\).*?(?=\nfunction |\Z)", APP, re.S)
    assert entorno_render
    assert "panoramaCard(ind)" in entorno_render.group(0)
    for k in ["IED", "TIPOCAMBIO", "TASA", "RESERVAS", "EMOE"]:
        assert f'"{k}"' in CONFIG


def test_product_buttons_evaluated_independently():
    """Cada botón decide su propia disponibilidad; no hay dependencia global."""
    assert "boletinEnabled = !!boletinUrl" in APP
    assert "notaReady = !!ind.nota_disponible" in APP
    assert "xlsxReady = !!ind.xlsx_disponible" in APP
    assert "product-ok" in CSS
    assert "product-disabled" in CSS


def test_nota_disabled_tooltip():
    assert "Nota pendiente de plantilla aprobada" in APP


def test_individual_excel_routes():
    for k in INDICADORES["indicators"]:
        ind = INDICADORES["indicators"][k]
        if ind.get("xlsx_disponible"):
            assert ind["url_excel_individual"] == f"downloads/indicadores/{k}/{k}_datos.xlsx"


def test_navegacion_prev_next_por_seccion():
    """indicatorToolbar usa la sección correcta (PRINCIPAL o COMPLEMENTARIOS)."""
    assert "function indicatorSection(key)" in APP
    assert "if (PRINCIPAL.includes(key)) return PRINCIPAL" in APP
    assert "if (COMPLEMENTARIOS.includes(key)) return COMPLEMENTARIOS" in APP


def test_calendario_filtrado_por_indicador():
    assert "openCalendarioFiltro(ind)" in APP
    assert "buildCalendarioPanel(ind)" in APP
    assert "modal-overlay" in INDEX


def test_ficha_layout_compacto_sin_altura_forzada():
    assert ".ficha-head { display: grid" in CSS
    assert "align-items: start" in CSS
    assert ".fh-item { display: flex; justify-content: space-between; align-items: baseline; gap: 10px; padding: 6px 10px" in CSS
    assert "min-height: 0" in CSS
    # La cabecera y metadatos de la ficha no deben forzar altura con min-height.
    assert ".ficha-head {" in CSS
    ficha_head = CSS.split(".ficha-head {")[1].split("}")[0]
    assert "min-height" not in ficha_head
    assert ".fh-meta {" in CSS
    fh_meta = CSS.split(".fh-meta {")[1].split("}")[0]
    assert "min-height" not in fh_meta


def test_pib_sector_breakdown_title_and_format():
    """El desglose PIB muestra variaciones trimestrales, no niveles."""
    assert '"Variación trimestral por actividad económica"' in APP
    assert '"Cambio real respecto al trimestre inmediato anterior, cifras desestacionalizadas."' in APP
    assert '"vs. trimestre anterior"' in APP
    # Se usa un helper que aplica pct-frac (multiplica por 100) para evitar 330%.
    assert 'const signedPct' in APP
    assert 'signedPct(s.qoq)' in APP


def test_pib_historial_ampliado_ui():
    """La ficha del PIB incluye el historial compacto."""
    assert '"Historial del indicador"' in APP
    assert "Periodo inicial" in APP
    assert "Periodo final" in APP
    assert "Observaciones" in APP
    assert 'pibHistoryBlock' in APP
    assert '.pib-history' in CSS


def test_pibt_nivel_tradicional_ui():
    """El nivel tradicional del PIB se presenta en una tarjeta y gráfica independientes."""
    assert '"Nivel tradicional del PIB"' in APP
    assert '"Último nivel disponible"' in APP
    assert 'pibtBlock' in APP
    assert 'mountPibtChart' in APP
    assert '"chart-pibt"' in APP
    assert '.pibt-block' in CSS
    assert '.pibt-chart' in CSS
