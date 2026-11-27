"""Las revisiones BIE no deben borrar la edición utilizada por una nota."""
import copy
import pytest
from build_data import apply_inegi_total

@pytest.mark.parametrize('key,column,value', [('IMAI',4,.035),('IGAE',1,.006)])
def test_preserve_bulletin_edition_when_bie_revises(key,column,value):
    payload={'indicators':{key:{'columns':[{}]*9,'observations':[{'period':'Ago 26','values':[None]*9}]}}}
    source={'target_column':column,'api_total':[{'ym':'2026-08','value':value,'period':'Ago 26'}],
            'serie':'official-pdf','metodo':'INEGI boletín PDF','freq':8,
            'link':f'https://www.inegi.org.mx/contenidos/saladeprensa/boletines/2026/{key.lower()}/{key.lower()}2026_10.pdf',
            'fecha_publicacion':'2026-10-12'}
    apply_inegi_total(payload,key,source,None)
    snapshot=copy.deepcopy(payload['indicators'][key]['boletin_cifras'])
    revised={**source,'serie':'BIE','metodo':'INEGI BIE API','link':'https://www.inegi.org.mx/app/indicadores/',
             'api_total':[{'ym':'2026-08','value':value+.001,'period':'Ago 26'}]}
    apply_inegi_total(payload,key,revised,None)
    assert payload['indicators'][key]['boletin_cifras']==snapshot
    assert snapshot['2026-08'][str(column)]['value']==value
    assert payload['indicators'][key]['observations'][-1]['values'][column]==pytest.approx(value+.001)


@pytest.mark.parametrize(
    "quarter, header, acumulado, expected",
    [
        (1, "", None, (3.2, 3.2)),
        (2, "62/\nmeses", "1.2", (3.2, 1.2)),
        (3, "92/\nmeses", "1.8", (3.2, 1.8)),
        (3, "6 meses", "1.2", (3.2, None)),
        (4, "2/\nAnual", "0.5", (3.2, 0.5)),
    ],
)
def test_eopibt_acumulado_original_del_cuadro_2(quarter, header, acumulado, expected):
    from sources.inegi_bulletin import _parse_eopibt_original

    ordinal = ("1.er", "2.o", "3.er", "4.o")[quarter - 1]
    table = [
        ["", "20251/", "20261/", None],
        ["PIB y actividades económicas", "", ordinal, header],
        ["", "Anual", "trimestre", None],
        ["PIB", "0.7", "3.2", acumulado],
    ]
    assert _parse_eopibt_original([table], 2026, quarter) == expected


def test_eopibt_edicion_470_26_conserva_series(monkeypatch):
    import json
    from pathlib import Path
    from sources import inegi_bulletin as source

    snapshot = json.loads((Path(__file__).parent / "fixtures/eopibt_470_26.json").read_text())
    monkeypatch.setattr(source, "_pdf_text_first_page", lambda _: (snapshot["header"], None))
    monkeypatch.setattr(source, "_pdf_page_text", lambda *_: "")
    monkeypatch.setattr(source, "_pdf_page_tables", lambda _, page: snapshot["tables"][page])
    parsed = source._parse_eopibt(b"fixture", (2026, 7, 30))
    expected = {"qoq": .015, "yoy": .021, "yoy_orig": .022, "ytd": .012, "ytd_orig": .012}
    for key, value in expected.items():
        assert parsed[key]["PIB"]["period"] == "2T-26 P"
        assert parsed[key]["PIB"]["value"] == pytest.approx(value)
    assert parsed["proxima_publicacion_boletin"]["fecha_iso"] == "2026-10-30"
