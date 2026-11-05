from datetime import date

import build_calendar as b


def test_trimestral_enoe_no_actualiza_ficha_mensual():
    ev = b._precise_event({'indicator': 'DESOCUP', 'period': 'Tercer trimestre de 2026', 'frequency': 'Mensual'})
    assert ev['frequency'] == 'Trimestral'
    assert not ev['usar_para_frescura']
    assert 'trimestrales' in ev['product']


def test_bcmm_sin_boletin_no_se_confunde_con_nota_mensual():
    ev = b._precise_event({'indicator': 'BCMM', 'comentario': 'No se elabora comunicado de prensa, boletín de indicador ni reporte de resultados.'})
    assert ev['product'] == 'BCMM · Difusión de datos sin boletín'
    assert not ev['usar_para_frescura']


def test_periodos_distintos_mismo_dia_se_preservan():
    cfg = {'inegi': {'indicators': {'DESOCUP': {'acronyms': ['ENOE']}}}}
    entries = [{'program': 'Encuesta (ENOE)', 'date': date(2026, 11, 25), 'period': period}
               for period in ['Tercer trimestre de 2026', 'Octubre de 2026']]
    mapped = b._map_inegi_events(entries, cfg, [])
    assert len(mapped) == 2
    assert len(b._dedup_events(mapped + mapped)) == 2
