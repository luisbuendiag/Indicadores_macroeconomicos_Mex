import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

APP = (ROOT / "assets" / "js" / "app.js").read_text(encoding="utf-8")
CSS = (ROOT / "assets" / "css" / "styles.css").read_text(encoding="utf-8")
INDICADORES = json.loads((ROOT / "data" / "indicadores.json").read_text(encoding="utf-8"))


def product_btn_source():
    m = re.search(r"function productBtn\(.*?\) \{(.*?)\nfunction ", APP, re.S)
    assert m, "productBtn no encontrado"
    return m.group(1)


def product_toolbar_source():
    m = re.search(r"function productToolbar\(ind\) \{(.*?)\nfunction ", APP, re.S)
    assert m, "productToolbar no encontrado"
    return m.group(1)


def test_product_btn_no_disabled_attr_for_active():
    src = product_btn_source()
    # Ningún botón activo debe tener el atributo disabled; solo aria-disabled para inactivos.
    assert "disabled:" not in src
    assert 'disabled = !enabled' not in src and "disabled: !enabled" not in src
    assert '"aria-disabled": enabled ? undefined : "true"' in src


def test_product_btn_disabled_has_tabindex_and_click_noop():
    src = product_btn_source()
    assert 'attrs.tabindex = "-1"' in src
    assert "attrs.onclick = () => {}" in src


def test_product_btn_data_product_kind():
    assert '"data-product": kind || label.toLowerCase()' in APP


def test_calendar_enabled_only_with_data():
    src = product_toolbar_source()
    assert "function calendarioDisponible(ind)" in APP
    assert "const calEnabled = calendarioDisponible(ind)" in src


def test_boletin_prefiere_url_boletin_oficial_y_url_fuente_oficial_fallback():
    src = product_toolbar_source()
    assert "ind.url_boletin_oficial || ind.url_fuente_oficial || (ind.fuente && ind.fuente.link)" in src


def test_boletin_opens_external_with_rel():
    assert "function openExternalLink(url)" in APP
    assert 'a.rel = "noopener noreferrer"' in APP
    assert 'a.target = "_blank"' in APP


def test_excel_download_uses_individual_file():
    src = product_toolbar_source()
    assert 'productBtn("EXCEL"' in src
    assert "xlsxUrl(ind)" in src
    assert "downloadProduct" in src


def test_excel_files_exist_for_all_available():
    for k, ind in INDICADORES["indicators"].items():
        if ind.get("xlsx_disponible"):
            path = ROOT / "downloads" / "indicadores" / k / f"{k}_datos.xlsx"
            assert path.exists(), f"Falta Excel individual de {k}: {path}"


def test_nota_disabled_cause():
    src = product_toolbar_source()
    assert 'productBtn("NOTA"' in src
    assert "Nota pendiente de plantilla aprobada" in src
    assert "notaReady = !!ind.nota_disponible" in src


def test_nota_does_not_affect_other_buttons():
    # Cada botón se evalúa con su propia variable; NOTA no modifica calEnabled/boletinEnabled/xlsxReady.
    src = product_toolbar_source()
    assert "calEnabled = calendarioDisponible" in src
    assert "boletinEnabled = !!boletinUrl" in src
    assert "xlsxReady = !!ind.xlsx_disponible" in src
    assert "notaReady = !!ind.nota_disponible" in src


def test_active_and_disabled_visuals_differ():
    # Activo: fondo blanco, texto verde, borde verde, cursor pointer.
    assert ".product-bar .product-ok" in CSS
    assert "color: var(--dkgreen)" in CSS
    assert "border: 1px solid var(--dkgreen)" in CSS
    assert "cursor: pointer" in CSS
    assert "opacity: 1" in CSS
    # Deshabilitado: gris, cursor not-allowed, sin opacidad reducida.
    assert ".product-bar .product-disabled" in CSS
    assert "background: #ebedf0" in CSS
    assert "color: #6b737a" in CSS
    assert "cursor: not-allowed" in CSS
    assert ".product-bar .product-disabled" in CSS


def test_ima_test_case_buttons():
    imai = INDICADORES["indicators"]["IMAI"]
    assert imai["last_observation"] == "Jun 26"
    assert imai.get("url_boletin_oficial")
    assert imai["url_boletin_oficial"].endswith("imai2026_08.pdf")
    assert imai.get("xlsx_disponible")
    assert imai.get("url_excel_individual") == "downloads/indicadores/IMAI/IMAI_datos.xlsx"
    assert imai.get("nota_disponible")
    assert imai.get("url_nota_individual") == "downloads/indicadores/IMAI/IMAI_nota.docx"
    nota_path = ROOT / "downloads" / "indicadores" / "IMAI" / "IMAI_nota.docx"
    assert nota_path.exists(), f"Falta nota IMAI: {nota_path}"
    # Calendario IMAI existe.
    cal = json.loads((ROOT / "data" / "calendario_publicaciones.json").read_text(encoding="utf-8"))
    assert any(c and c.get("clave") == "IMAI" for c in cal["items"])


def test_inegi_indicators_have_specific_pdf_bulletin():
    """Los indicadores INEGI deben apuntar al boletín oficial específico en saladeprensa."""
    for k in ["IMAI", "IGAE", "INPC", "BCMM", "DESOCUP", "CONSUMO", "IMFBCF", "IOAE", "EMIM", "EMOE", "PIB"]:
        ind = INDICADORES["indicators"][k]
        url = ind.get("url_boletin_oficial")
        assert url, f"{k} no tiene url_boletin_oficial"
        assert ".inegi.org.mx/" in url, f"{k}: dominio no oficial: {url}"
        if k in ("IMAI", "IGAE", "INPC", "BCMM", "DESOCUP", "IOAE", "EMIM", "EMOE"):
            assert "contenidos/saladeprensa/boletines" in url, f"{k}: no es boletín PDF: {url}"


def test_nota_files_exist_for_all_available():
    for k, ind in INDICADORES["indicators"].items():
        if ind.get("nota_disponible"):
            path = ROOT / "downloads" / "indicadores" / k / f"{k}_nota.docx"
            assert path.exists(), f"Falta nota de {k}: {path}"


def test_boletin_inegi_fallback_when_no_specific_url():
    """Si un indicador INEGI no tiene url_boletin_oficial, el fallback es el calendario."""
    src = product_toolbar_source()
    assert 'https://www.inegi.org.mx/app/saladeprensa/calendario/' in src
    assert 'esInegi = (ind.fuente && (ind.fuente.nombre || "").includes("INEGI"))' in src
    assert 'boletinUrl = ind.url_boletin_oficial || ind.url_fuente_oficial || (ind.fuente && ind.fuente.link) || null' in src


def test_financial_indicators_have_products():
    for k in ["IED", "TIPOCAMBIO", "TASA", "RESERVAS", "EMOE"]:
        ind = INDICADORES["indicators"][k]
        assert ind.get("xlsx_disponible"), f"{k} sin xlsx_disponible"
        assert ind.get("url_excel_individual")


def test_calendar_opens_filtered_panel():
    assert "function openCalendarioFiltro(ind)" in APP
    assert "openCalendarioFiltro" in product_toolbar_source()
    assert "buildCalendarioPanel(ind)" in APP
