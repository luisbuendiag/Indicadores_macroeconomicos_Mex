"""F-018: la copia histórica no desplaza a la serie oficial vigente."""

import pytest

from build_data import merge_indicator, prepare_financiero_for_v3


@pytest.mark.parametrize("key", ["TIPOCAMBIO", "TASA", "RESERVAS"])
def test_remove_frozen_duplicate_without_touching_canonical_history(key):
    canonical = [
        {"period": "2017-12-29", "values": [10]},
        {"period": "2026-08-21", "values": [20]},
        {"period": "2026-11-13", "values": [30]},
    ]
    payload = {"indicators": {key: {
        "observations": canonical,
        "observations_original": [{"period": "2026-08-21", "values": [200]}],
    }}}
    prepare_financiero_for_v3(payload)
    ind = payload["indicators"][key]
    assert ind["observations"] == canonical
    assert ind["last_observation"] == "2026-11-13"
    assert "observations_original" not in ind

    newer = canonical + [{"period": "2026-11-20", "values": [40]}]
    merge_indicator(payload, key, {"observations": newer, "last_observation": "2026-11-20"})
    assert "observations_original" not in payload["indicators"][key]
    assert payload["indicators"][key]["observations"] == newer


@pytest.mark.parametrize("current", [[], [{"period": "Ago 26", "values": [10]}]])
def test_promote_legacy_dated_history_before_removing_duplicate(current):
    historical = [{"period": "2026-08-28", "values": [10]}]
    ind = {"observations": current, "observations_original": historical}
    prepare_financiero_for_v3({"indicators": {"TIPOCAMBIO": ind}})
    assert ind["observations"] == historical
    assert ind["last_observation"] == "2026-08-28"
    assert "observations_original" not in ind


def test_monthly_history_is_preserved_if_no_dated_data_can_be_migrated():
    ind = {"observations": [{"period": "Ago 26", "values": [10]}],
           "observations_original": [{"period": "Jul 26", "values": [9]}]}
    prepare_financiero_for_v3({"indicators": {"TASA": ind}})
    assert ind["observations"][0]["period"] == "Ago 26"
    assert ind["observations_original"][0]["period"] == "Jul 26"


def test_mixed_legacy_series_does_not_overwrite_newer_dated_observation():
    current = [{"period": "Ago 26", "values": [10]},
               {"period": "2026-11-13", "values": [20]}]
    ind = {"observations": current,
           "observations_original": [{"period": "2026-08-21", "values": [10]}]}
    prepare_financiero_for_v3({"indicators": {"RESERVAS": ind}})
    assert ind["observations"] == current
    assert "observations_original" in ind
