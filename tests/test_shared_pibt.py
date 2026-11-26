from copy import deepcopy
from datetime import datetime
import json

import pytest

from shared_pibt import choose, without_pibt


def case(tmp_path):
    path = tmp_path / "estado.json"
    path.write_text(json.dumps({
        "data_error": False, "data_checked_at": "2026-11-25T10:00:00-06:00",
    }))
    rows = [{"period": cut, "values": [20]} for cut in ("2T-26", "3T-26")]
    indicator = {
        "key": "PIBSEC", "last_observation": "3T-26", "columns": [{"index": 0}],
        "unidad": "mdd", "frecuencia": "Trimestral", "ajuste_estacional": "Original",
        "fuente": {"nombre": "INEGI"}, "observations": rows, "boletin_validado": True,
    }
    data = {"indicators": {"PIBSEC": indicator, "PIB": {"pibt": {"observations": rows}}}}
    receipt = {"data_checked_at": "2026-11-25T12:31:00-06:00", "release_id": "qa"}
    now = datetime.fromisoformat("2026-11-25T13:00:00-06:00")
    return data, deepcopy(data), receipt, path, now


def test_accepts_equivalent_after_midday(tmp_path):
    local, public, receipt, path, now = case(tmp_path)
    chosen, reference = choose(local, [], path, now=now, loader=lambda: (public, receipt))
    assert chosen is public["indicators"]["PIBSEC"]
    assert reference == "qa"


@pytest.mark.parametrize("condition", ["atrasado", "anterior", "calendario", "publicacion", "revision", "red"])
def test_returns_to_direct_source(tmp_path, condition):
    local, public, receipt, path, now = case(tmp_path)
    calendar = []
    indicator = public["indicators"]["PIBSEC"]
    if condition == "atrasado":
        indicator["observations"] = indicator["observations"][:-1]
        indicator["last_observation"] = "2T-26"
    elif condition == "anterior":
        receipt["data_checked_at"] = "2026-11-24T12:30:00-06:00"
    elif condition == "calendario":
        calendar = [{"clave": "PIBSEC", "periodo_referencia": "4T-26", "fecha_iso": "2026-11-25"}]
    elif condition == "publicacion":
        indicator["boletin_validado"] = False
    elif condition == "revision":
        indicator["observations"][-1]["values"] = [25]

    def get():
        if condition == "red":
            raise OSError("fallo simulado")
        return public, receipt

    chosen, reason = choose(local, calendar, path, now=now, loader=get)
    assert chosen is None
    assert reason.startswith("INEGI directo")


def test_keeps_unrelated_keys_and_pib_oportuno():
    historic = {"pibt": True}
    unaffected = {"serie": "123"}
    config = {"inegi": {"PIB": [historic, unaffected], "PIBSEC": [{}], "IGAE": unaffected}}
    assert without_pibt(config) == {"inegi": {"PIB": [unaffected], "IGAE": unaffected}}
    assert config["inegi"]["PIB"] == [historic, unaffected]
