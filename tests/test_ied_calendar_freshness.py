"""El comunicado nacional de IED no debe actualizar los productos desagregados."""
from datetime import date
import json
from pathlib import Path

import pytest

import build_calendar
import build_data
import lib_freshness

DATA = Path(__file__).resolve().parents[1] / "data"
AS_OF = date(2026, 11, 25)


@pytest.fixture(autouse=True)
def isolate_generated_calendar(monkeypatch, tmp_path):
    monkeypatch.setattr(build_calendar, "NEW_OUT", tmp_path / "calendario.json")
    monkeypatch.setattr(build_calendar, "LEGACY_OUT", tmp_path / "calendario_publicaciones.json")


@pytest.fixture
def ied_communicado():
    # Snapshot reducido del contrato de datos vigente al 25-nov-2026;
    # conserva la prueba cuando el dashboard cargue trimestres posteriores.
    return {
        "key": "IED", "nombre": "Inversión Extranjera Directa (IED)",
        "frecuencia": "Trimestral", "fuente": {"nombre": "Secretaría de Economía"},
        "last_observation": "3T-26", "fecha_publicacion": "24 de noviembre de 2026",
        "corte_de_comunicado": True,
        "url_boletin_oficial": json.loads(
            (DATA / "ied_comunicado_2026_3t.json").read_text(encoding="utf-8")
        )["url_boletin"],
        "observations": [{"period": "2T-26", "values": [10464.95]}],
        "observations_acumulado": [
            {"period_acumulado": "Ene-Sep 25", "quarter": "3T-25", "values": [40906]},
            {"period_acumulado": "Ene-Sep 26", "quarter": "3T-26", "values": [43090]},
        ],
        "metrics": {"acumulado": {"periodo": "Ene-Sep 26", "valor": 43090,
                                   "corte": "Ene-Sep", "variacion_anual_pct": .053},
                    "flujo_trimestral": {"periodo": "3T-26", "valor": None},
                    "composicion_entidad": []},
    }


def test_ied_calendar_tracks_national_communicado_and_unannounced_next_cut(tmp_path):
    edition = build_calendar.build(as_of=AS_OF, offline=True)
    rows = [row for row in edition["items"] if row["clave"] == "IED"]
    national = [row for row in rows if row.get("alcance") == "acumulado_nacional"]
    assert len(national) == 1
    event = national[0]
    assert event["fecha_iso"] == "2026-11-24"
    assert event["periodo_referencia"] == "3° trimestre 2026"
    assert event["estatus"] == "publicado"
    assert "acumulado nacional" in event["producto"]
    assert "ranking estatal" in event["comentario"]
    next_cut, = [row for row in rows if row["estatus"] == "no_anunciada"]
    assert next_cut["periodo_referencia"] == "4° trimestre 2026"
    assert next_cut["fecha_publicacion"] == "Por anunciar"
    assert next_cut["anio"] is None and next_cut["mes"] is None
    modern_calendar = json.loads((tmp_path / "calendario.json").read_text(encoding="utf-8"))
    modern = next(ev for ev in modern_calendar["events"]
                  if ev["indicator"] == "IED" and ev["publication_date"] == "2026-11-24")
    assert modern["url"] == event["url_boletin"]
    assert modern["deliverables"][0]["format"] == "html"


def test_ied_communicado_updates_freshness_not_quarterly_flow(monkeypatch, tmp_path, ied_communicado):
    ind = ied_communicado
    payload = {"meta": {}, "indicators": {"IED": ind}}
    observations = json.dumps(ind["observations"])
    monkeypatch.setattr(build_data.L, "DATA_DIR", tmp_path)
    monkeypatch.setattr(build_data.lib_kpicfg, "CACHE", tmp_path / "kpicfg.json")
    build_data.apply_freshness_and_meta(payload, {"warnings": []}, as_of=AS_OF, offline=True)
    assert ind["estado"] == "ACTUALIZADO"
    assert ind["periodo_referencia_oficial"] == "3° trimestre 2026"
    assert ind["fecha_publicacion_oficial"] == "24 de noviembre de 2026"
    assert ind["proxima_publicacion"] == {"fecha_publicacion": "Por anunciar",
                                        "periodo_referencia": "4° trimestre 2026",
                                        "tipo": "no_anunciada"}
    assert "adelantado" not in ind["motivo_frescura"]
    assert "Acumulado nacional Ene-Sep 26" in ind["motivo_frescura"]
    assert "originalmente publicada" in ind["motivo_frescura"]
    assert "flujo trimestral exclusivo" in ind["motivo_frescura"]
    assert "ranking estatal" in ind["motivo_frescura"]
    assert ind["metrics"]["kpi"]["ultimoRaw"] == 43090
    assert ind["metrics"]["kpi"]["varText"] == "+5.3%"
    assert json.dumps(ind["observations"]) == observations
    assert ind["observations"][-1]["period"] == "2T-26"
    assert ind["metrics"]["flujo_trimestral"]["valor"] is None
    assert not ind["metrics"]["composicion_entidad"]


def test_ied_communicado_does_not_override_source_error(ied_communicado):
    ind = ied_communicado
    calendar = build_calendar.build(as_of=AS_OF, offline=True)["items"]
    result = lib_freshness.compute_state("IED", ind["last_observation"],
                                         update_log={"warnings": ["IED: error de fuente"]}, calendar=calendar,
                                         as_of=AS_OF, ind=ind)
    assert result["estado"] == "ERROR DE FUENTE"


def test_ied_communicado_requires_matching_official_url_and_nonfuture_publication(ied_communicado):
    ind = ied_communicado
    calendar = build_calendar.build(as_of=AS_OF, offline=True)["items"]
    for as_of, source in ((AS_OF, "https://example.com"),
                          (date(2026, 11, 23), ind["url_boletin_oficial"])):
        result = lib_freshness.compute_state("IED", ind["last_observation"], update_log={},
                                             calendar=calendar, as_of=as_of,
                                             ind={**ind, "url_boletin_oficial": source})
        assert result["fecha_publicacion_oficial"] == "24 de agosto de 2026"
        assert "Acumulado nacional" not in result["motivo"]



@pytest.mark.parametrize("quarter,value", [("3T-26", None), ("3T-26", float("nan")),
                                          ("3T-26", "43090"), ("2T-26", 43090)])
def test_ied_communicado_does_not_confirm_missing_or_mismatched_accumulated(
    ied_communicado, quarter, value,
):
    ind = ied_communicado
    ind["observations_acumulado"][-1] = {"quarter": quarter, "values": [value]}
    result = lib_freshness.compute_state("IED", ind["last_observation"], update_log={},
                                         calendar=build_calendar.build(as_of=AS_OF, offline=True)["items"],
                                         as_of=AS_OF, ind=ind)
    assert result["fecha_publicacion_oficial"] == "24 de agosto de 2026"
    assert "Acumulado nacional" not in result["motivo"]
