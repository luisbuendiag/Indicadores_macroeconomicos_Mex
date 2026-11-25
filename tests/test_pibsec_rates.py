"""Regresión D-004: composición homogénea del PIBT y exportación."""
from datetime import date
import json
from pathlib import Path

import pytest

import build_data as pipeline
import build_excel
import lib_metrics
from sources import inegi

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config/series.json").read_text())
PROFILE = json.loads((ROOT / "config/indicadores_meta.json").read_text())["profile"]["PIBSEC"]


def test_pibsec_uses_bie_history_and_prioritizes_latest_pibt_bulletin(monkeypatch):
    # Originales deliberadamente estacionales y tasas legadas contaminadas.
    periods = ["2T-25", "3T-25", "4T-25", "1T-26", "2T-26"]
    pibsec = {
        "key": "PIBSEC",
        "columns": PROFILE["columns"],
        "frecuencia": "Trimestral",
        "unidad": PROFILE["unidad"],
        "last_observation": periods[-1],
        "observations": [
            {"period": period, "values": [v, v, v, 0.30, 0.30, v, 0.30, 0.30, 0.30, 0.30, 0.30, 0.30]}
            for period, v in zip(periods, [100, 130, 170, 85, 110])
        ],
    }
    payload = {"indicators": {"PIBSEC": pibsec}}
    pipeline.prepare_pibsec_for_separated_rates(payload)
    pipeline.compute_pibsec_variations(payload)
    assert pipeline.validate_pibsec_adjusted_history(pibsec)
    assert all(pibsec["observations"][0]["values"][i] is None for i in pipeline.PIBSEC_ADJUSTED)

    def fake_bie(url):
        assert "/BIE-BISE/" in url
        return {"Series": [{
            "FREQ": 4,
            "OBSERVATIONS": [
                {"TIME_PERIOD": quarter, "OBS_VALUE": value}
                for quarter, value in zip(
                    ["2025/02", "2025/03", "2025/04", "2026/01", "2026/02", "2026/03"],
                    [100, 101, 103, 102, 103, 107],
                )
            ],
        }]}

    monkeypatch.setattr(inegi, "http_get_json", fake_bie)
    adjusted = [spec for spec in CONFIG["inegi"]["PIBSEC"] if spec.get("transform")]
    assert {spec["serie"] for spec in adjusted} == {"736181", "736195", "736202", "736237"}
    for spec in adjusted:
        item = inegi._fetch_one(spec, "test-fixture", spec["start_year"])
        pipeline.apply_inegi_total(payload, "PIBSEC", item, periods[-1])

    # Tasas desestacionalizadas del Cuadro 1 del boletín PIBT del 2T-26.
    official = {6: 0.014, 8: 0.024, 10: 0.016, 3: 0.014,
                7: 0.019, 9: 0.048, 11: 0.009, 4: 0.023}
    bulletin = [
        {
            "target_column": col, "freq": 4, "serie": "PIBSEC_pdf",
            "metodo": "INEGI boletín PDF", "link": "https://www.inegi.org.mx/",
            "api_total": [{"ym": "2026-01", "value": 0.90}, {"ym": "2026-04", "value": value}],
        }
        for col, value in official.items()
    ]
    pipeline.apply_latest_pibsec_bulletin(payload, bulletin, periods[-1])
    pipeline.compute_pibsec_variations(payload)
    assert pibsec["last_observation"] == "2T-26"
    assert len(pibsec["observations"]) == len(periods)
    assert pibsec["observations"][-2]["values"][8] == pytest.approx(round(102 / 103 - 1, 6))
    values = pibsec["observations"][-1]["values"]
    assert {col: values[col] for col in official} == official
    assert values[12:16] == pytest.approx([0.10] * 4)
    assert pipeline.prepare_pibsec_for_separated_rates(payload) == []
    assert pipeline.validate_pibsec_adjusted_history(pibsec) == []

    kpi = lib_metrics._pibsec_metrics(pibsec, lib_metrics.get_cfg()["KPICFG"])["kpi"]
    assert kpi["cards"][0]["yoyRaw"] == pytest.approx(0.10)
    assert kpi["cards"][0]["yoyDesestRaw"] == pytest.approx(0.019)
    assert kpi["yoyText"] == "+10.0%"
    model = build_excel.build_workbook([pibsec])
    for i, value in enumerate(values):
        sheet, address = model.coords["PIBSEC", i, date(2026, 4, 1)]
        assert model.wb[sheet][address].value == value


def test_original_yoy_requires_the_same_calendar_quarter():
    obs = [
        {"period": "1T-25", "values": [100] * 12},
        {"period": "2T-25", "values": [120] * 12},
        {"period": "4T-25", "values": [200] * 12},
        {"period": "2T-26", "values": [132] * 12},
        {"period": "3T-26", "values": [140] * 12},
    ]
    pipeline.compute_pibsec_variations({"indicators": {"PIBSEC": {"observations": obs}}})
    assert obs[-2]["values"][12:16] == pytest.approx([0.10] * 4)
    assert obs[-1]["values"][12:16] == [None] * 4


def test_pibt_subsector_selects_reference_quarter_and_preserves_missing(monkeypatch):
    from sources import inegi_bulletin as source

    header = [
        ["", "20251/", None, None, None, "20261/", None, None],
        ["PIB", "2.°", "3.er", "4.°", "", "1.er2/", "2.°", "6"],
        [None, None, None, None, "Anual", None, None, "meses"],
    ]
    table = header + [
        ["PIB total", "-0.1", "-0.2", "1.7", "0.5", "0.2", "2.1", "1.1"],
        ["43 Comercio al por mayor", "-8.3", "-4.1", "-1.0", "-4.7", "2.2", "11.3", "6.7"],
        ["44 Sin dato", "0.1", "0.2", "0.3", "0.4", "0.5", None, "1.8"],
        ["46 Comercio al por menor", "3.7", "4.1", "4.5", "4.3", "0.9", "0.9", "0.9"],
    ]
    monkeypatch.setattr(source, "_pdf_page_tables", lambda *_: [table])
    assert source._parse_pibt_subsectores(b"", 2026, 2) == pytest.approx({
        "PIB total": 0.021, "43 Comercio al por mayor": 0.113, "46 Comercio al por menor": 0.009,
    })
    assert source._parse_pibt_subsectores(b"", 2026, 3) is None


def test_pibsec_retains_bulletin_metadata_for_quarter_with_original_level():
    old = "https://www.inegi.org.mx/contenidos/saladeprensa/boletines/2026/pibt/pib_Pconst2026_08.pdf"
    new = old.replace("_08.pdf", "_11.pdf")
    ind = {"columns": PROFILE["columns"], "observations": [
        {"period": "2T-26", "values": [100] * 12},
        {"period": "3T-26", "values": [None] * 12},
    ]}
    payload = {"indicators": {"PIBSEC": ind, "PIB": {"pibt": {"observations": []}}}}
    bulletin = {
        "target_column": 6, "freq": 4, "serie": "PIBSEC_pdf", "link": new,
        "metodo": "INEGI boletín PDF", "periodo_boletin": "3T-26",
        "fecha_publicacion": "23 de noviembre de 2026", "subsectores": {"dato": 0.33},
        "api_total": [
            {"period": "2T-26", "ym": "2026-04", "value": 0.014, "source_url": old,
             "source_publication_date": "24 de agosto de 2026", "source_bulletin_number": "123/26"},
            {"period": "3T-26", "ym": "2026-07", "value": 0.009, "source_url": new},
        ],
    }
    pipeline.apply_latest_pibsec_bulletin(payload, [bulletin], "2T-26")
    assert ind["last_observation"] == ind["periodo_boletin"] == "2T-26"
    assert ind["url_boletin_oficial"] == old
    assert ind["fecha_publicacion"] == "24 de agosto de 2026"
    assert "subsectores" not in ind

    payload["indicators"]["PIB"]["pibt"]["observations"] = [
        {"period": "3T-26", "values": [115]},
    ]
    pipeline.sync_pibsec_pibt(payload)
    pipeline.apply_latest_pibsec_bulletin(payload, [bulletin], "2T-26")
    assert ind["last_observation"] == ind["periodo_boletin"] == "3T-26"
    assert ind["url_boletin_oficial"] == new
    assert ind["observations"][-1]["values"][5:7] == [115, 0.009]
