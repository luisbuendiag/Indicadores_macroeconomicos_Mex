import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

INDEX = (ROOT / "index.html").read_text(encoding="utf-8")
APP = (ROOT / "assets" / "js" / "app.js").read_text(encoding="utf-8")
CONFIG = (ROOT / "assets" / "js" / "config.js").read_text(encoding="utf-8")
METRICS = (ROOT / "assets" / "js" / "metrics.js").read_text(encoding="utf-8")
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
    assert "no disponible en la base actual" in APP


def test_balance_saldo_vs_variacion_distinct():
    m = re.search(r"BALANZA:\s*\{[^}]*\}", CONFIG)
    assert m
    bal = m.group(0)
    assert 'derived: "saldo"' in bal
    assert "Variación del saldo" in bal
    assert "Saldo (X − M)" in APP


def test_exactly_eleven_principal_indicators():
    m = re.search(r"PRINCIPAL\s*=\s*\[(.*?)\]", CONFIG, re.S)
    assert m, "no se encontró PRINCIPAL"
    claves = re.findall(r'"([^"]+)"', m.group(1))
    assert len(claves) == 11, claves


def test_pib_prose_uses_billones_not_dollar():
    assert '" billones de pesos' in METRICS
    m = re.search(r'if \(k === "PIB"\) return ([^;]+);', METRICS)
    assert m
    assert "$" not in m.group(1)
    assert "2018" in m.group(1)


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
    css = (ROOT / "assets" / "css" / "styles.css").read_text(encoding="utf-8")
    assert "mc-deltas { display: flex; gap: 14px; flex-wrap: nowrap;" in css
    assert "word-break: break-word" in css
