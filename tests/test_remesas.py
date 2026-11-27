from datetime import date
from unittest.mock import patch

from sources import banxico, calendar_banxico


def test_remesas_monthly_uses_calendar_comparisons_and_complete_accumulations(monkeypatch):
    monkeypatch.setenv("BANXICO_TOKEN", "test")
    config = {"banxico": {"REMESAS": {"serie": "SE27803", "frecuencia": "Mensual"}}}
    datos = [
        {"fecha": "30/04/2026", "dato": "600"},
        {"fecha": "28/02/2026", "dato": "300"},
        {"fecha": "31/01/2026", "dato": "500"},
        {"fecha": "30/04/2025", "dato": "400"},
        {"fecha": "28/02/2025", "dato": "200"},
        {"fecha": "31/01/2025", "dato": "200"},
    ]
    with patch.object(banxico, "http_get_json", return_value={"bmx": {"series": [{"datos": datos}]}}):
        result = banxico.fetch(config)

    assert result.ok
    ind = result.data["REMESAS"]
    assert ind["last_observation"] == "Abr 26"
    assert ind["observations"][-2:] == [
        {"period": "Feb 26", "values": [300, 0.5, 800, 1.0]},
        {"period": "Abr 26", "values": [600, 0.5, None, None]},
    ]


def test_remesas_calendar_separates_release_date_from_reference_month():
    data = {"webFutureResources": {"events": [{
        "parentId": 23, "categoryId": 37,
        "futureResources": [{
            "title": "Remesas con el exterior, octubre 2026",
            "referenceDate": "01/12/2026",
        }],
    }]}}
    event, = calendar_banxico._remesas_events(data)
    assert event["indicator"] == "REMESAS"
    assert event["date"] == date(2026, 12, 1)
    assert event["period"] == "Octubre 2026"
    assert event["deliverables"] == []
