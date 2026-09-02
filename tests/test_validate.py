import copy

import validate as V


BASE = {
    "meta": {"base_year": 2018},
    "order": ["A", "B"],
    "indicators": {
        "A": {"key": "A", "columns": [{"label": "x", "index": 0, "fmt": "idx"}],
              "observations": [{"period": "Ene 25", "values": [100.123456]},
                               {"period": "Feb 25", "values": [101.5]}]},
        "B": {"key": "B", "columns": [{"label": "y", "index": 0, "fmt": "idx"}],
              "observations": [{"period": "Ene 25", "values": [55.7]},
                               {"period": "Feb 25", "values": [56.2]}]},
    },
}


def test_clean_passes():
    errors, _ = V.validate(copy.deepcopy(BASE))
    assert errors == []


def test_detects_suspicious_duplicate():
    payload = copy.deepcopy(BASE)
    # inyecta el mismo valor de alta precisión en dos series no relacionadas
    payload["indicators"]["B"]["observations"][0]["values"][0] = 100.123456
    errors, _ = V.validate(payload)
    assert any("idéntico" in e for e in errors), errors


def test_out_of_range_is_warning_not_error():
    payload = copy.deepcopy(BASE)
    ind = payload["indicators"].pop("A")
    ind["key"] = "INPC"
    ind["observations"][0]["values"][0] = 999  # fuera de rango
    payload["indicators"]["INPC"] = ind
    payload["order"] = ["INPC", "B"]
    errors, warnings = V.validate(payload)
    assert not errors
    assert any("fuera de rango" in w for w in warnings)


def test_revision_detection():
    old = copy.deepcopy(BASE)
    new = copy.deepcopy(BASE)
    new["indicators"]["A"]["observations"][0]["values"][0] = 200.0
    notes = V.compare_revisions(new, old)
    assert any("revisión" in n for n in notes)


def test_ied_and_bcmm_are_principal_and_not_duplicated():
    """Con la nueva clasificación, IED y BCMM son principales y no deben marcarse como duplicados."""
    import json
    from pathlib import Path
    meta_path = Path(__file__).resolve().parents[1] / "config" / "indicadores_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert "IED" in meta["principal"]
    assert "BCMM" in meta["principal"]
    assert "IED" not in meta.get("complementario", [])
    assert "BCMM" not in meta.get("complementario", [])

    # Validar el payload real: no debe haber errores críticos ni duplicados entre IED/BCMM.
    data_path = Path(__file__).resolve().parents[1] / "data" / "indicadores.json"
    payload = json.loads(data_path.read_text(encoding="utf-8"))
    errors, warnings = V.validate(payload)
    dup_msgs = [w for w in warnings if "idéntico" in w]
    ied_bcmm_dups = [m for m in dup_msgs if "IED" in m and "BCMM" in m]
    assert not errors, f"Errores críticos: {errors}"
    assert not ied_bcmm_dups, f"IED y BCMM marcados como duplicados: {ied_bcmm_dups}"
