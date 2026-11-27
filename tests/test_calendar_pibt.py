from datetime import date
import json

import pytest

import build_calendar as calendar
from lib_freshness import compute_state, period_to_ym


PIBT = "Producto Interno Bruto Trimestral (PIBT). Año base 2018."
AS_OF = date(2026, 11, 23)


@pytest.fixture
def isolated_pibt_calendar(monkeypatch, tmp_path):
    """Usar respaldos fechados, sin depender del recorte anual del calendario vivo."""
    sources = tmp_path / "sources"
    sources.mkdir()
    snapshots = {
        2026: [
            ("23 de febrero de 2026", "Cuarto trimestre de 2025"),
            ("22 de mayo de 2026", "Primer trimestre de 2026"),
            ("24 de agosto de 2026", "Segundo trimestre de 2026"),
            ("23 de noviembre de 2026", "Tercer trimestre de 2026"),
        ],
        2027: [
            ("24 de febrero de 2027", "Cuarto trimestre de 2026"),
            ("24 de mayo de 2027", "Primer trimestre de 2027"),
        ],
    }
    for year, items in snapshots.items():
        (sources / f"{year}.json").write_text(json.dumps({"entries": [{
            "clave": "PIBSEC", "producto": PIBT, "institucion": "INEGI",
            "frecuencia": "Trimestral",
            "publicaciones": [{"fecha": d, "periodo": p} for d, p in items],
        }]}), encoding="utf-8")
    monkeypatch.setattr(calendar, "SRC_DIR", sources)
    monkeypatch.setattr(calendar, "DATA_DIR", tmp_path)
    monkeypatch.setattr(calendar, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(calendar, "NEW_OUT", tmp_path / "calendario.json")
    monkeypatch.setattr(calendar, "LEGACY_OUT", tmp_path / "calendario_publicaciones.json")
    for source in (calendar.calendar_inegi, calendar.calendar_banxico, calendar.calendar_se):
        monkeypatch.setattr(source, "fetch", lambda *_a, **_kw: ([], {}))


@pytest.mark.parametrize(("program", "key"), [
    (f"{PIBT} Precios Constantes. Cifras preliminares", "PIBSEC"),
    (f"{PIBT} Precios Corrientes. Cifras preliminares", None),
    (f"{PIBT} Por el Método del Ingreso. Cifras preliminares", None),
    (f"{PIBT} Por el Método del Gasto. Cifras preliminares", None),
    ("Estimación Oportuna del PIB Trimestral. Base 2018", "PIB"),
    ("Producto Interno Bruto Trimestral por Entidad Federativa (PIBT). Precios Constantes.", None),
])
def test_identifica_solo_pibt_a_precios_constantes(program, key):
    assert calendar._match_inegi_indicator(program, calendar._load_map()) == key


def test_el_pibt_se_rellena_por_periodo_y_prevalece_el_calendario_vigente(monkeypatch, isolated_pibt_calendar):
    official = [{
        "program": f"{PIBT} Precios Constantes. Cifras preliminares",
        "period": "Cuarto trimestre de 2026",
        "date": date(2027, 2, 25),
        "url": "https://www.inegi.org.mx/programas/pib/2018/",
    }]
    monkeypatch.setattr(calendar.calendar_inegi, "fetch", lambda *_a, **_kw: (official, {}))
    events, _, _ = calendar._build_events(AS_OF, offline=True)
    pibt = [e for e in events if e["indicator"] == "PIBSEC"]
    assert len(pibt) == 6
    assert [e["date"] for e in pibt if period_to_ym(e["period"]) == "2026-10"] == [date(2027, 2, 25)]
    assert any(e["date"] == date(2027, 5, 24) for e in pibt)


def test_respaldo_del_pibt_alimenta_los_dos_calendarios_y_la_proxima_publicacion(isolated_pibt_calendar):
    legacy = calendar.build(as_of=AS_OF, offline=True)
    new = json.loads(calendar.NEW_OUT.read_text(encoding="utf-8"))
    expected = ["2026-02-23", "2026-05-22", "2026-08-24", "2026-11-23", "2027-02-24", "2027-05-24"]
    assert sorted(e["publication_date"] for e in new["events"] if e["indicator"] == "PIBSEC") == expected
    assert sorted(e["fecha_iso"] for e in legacy["items"] if e["clave"] == "PIBSEC") == expected
    state = compute_state(
        "PIBSEC", "3T-26", {"frecuencia": "Trimestral"}, {}, legacy["items"], AS_OF,
        {"observations": [{"period": "3T-26"}]},
    )
    assert state["proxima_publicacion"] == "24 de febrero de 2027"
    assert state["proxima_publicacion_tipo"] == "oficial"
