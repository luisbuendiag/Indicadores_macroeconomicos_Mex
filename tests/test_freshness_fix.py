"""Tests para la lógica de frescura de FIX y otras series de alta frecuencia.

El Banco de México publica el FIX a partir de las 12:00 horas de cada día
hábil bancario. Antes de esa hora, la última observación oficial esperable es
la del día hábil anterior; la observación del día se considera disponible
una vez superada la hora de publicación más un margen de tolerancia
operativa (2 horas por defecto).
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

import lib_freshness as F

CDMX = ZoneInfo("America/Mexico_City")


def _dt(*, year: int, month: int, day: int, hour: int, minute: int) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=CDMX)


def _make_manifest(freq: str) -> dict:
    return {"frecuencia": freq}


def test_latest_expected_business_date_before_publish():
    """2026-09-01 10:00 CDMX -> último día hábil anterior (2026-08-31)."""
    now = _dt(year=2026, month=9, day=1, hour=10, minute=0)
    assert F.latest_expected_business_date(now) == date(2026, 8, 31)


def test_latest_expected_business_date_just_before_publish():
    """2026-09-01 11:59 CDMX -> aún se espera el día anterior."""
    now = _dt(year=2026, month=9, day=1, hour=11, minute=59)
    assert F.latest_expected_business_date(now) == date(2026, 8, 31)


def test_latest_expected_business_date_inside_tolerance():
    """2026-09-01 12:30 CDMX -> dentro de tolerancia, aún día anterior."""
    now = _dt(year=2026, month=9, day=1, hour=12, minute=30)
    assert F.latest_expected_business_date(now) == date(2026, 8, 31)


def test_latest_expected_business_date_after_tolerance():
    """2026-09-01 15:00/16:00 CDMX -> ya se espera el día actual."""
    now = _dt(year=2026, month=9, day=1, hour=15, minute=0)
    assert F.latest_expected_business_date(now) == date(2026, 9, 1)
    now = _dt(year=2026, month=9, day=1, hour=16, minute=0)
    assert F.latest_expected_business_date(now) == date(2026, 9, 1)


def test_latest_expected_business_date_friday_morning():
    """Viernes 4 de septiembre 10:00 -> el FIX del jueves sigue siendo válido."""
    now = _dt(year=2026, month=9, day=4, hour=10, minute=0)
    assert F.latest_expected_business_date(now) == date(2026, 9, 3)


def test_latest_expected_business_date_friday_afternoon():
    """Viernes 4 de septiembre 15:00 -> ya se espera el FIX del viernes."""
    now = _dt(year=2026, month=9, day=4, hour=15, minute=0)
    assert F.latest_expected_business_date(now) == date(2026, 9, 4)


def test_latest_expected_business_date_weekend():
    """Sábado y domingo con último dato del viernes -> ACTUALIZADO."""
    sat = _dt(year=2026, month=9, day=5, hour=10, minute=0)
    sun = _dt(year=2026, month=9, day=6, hour=10, minute=0)
    assert F.latest_expected_business_date(sat) == date(2026, 9, 4)
    assert F.latest_expected_business_date(sun) == date(2026, 9, 4)


def test_fix_actualizado_before_publish():
    """2026-09-01 10:00, FIX del 31 ago -> ACTUALIZADO."""
    now = _dt(year=2026, month=9, day=1, hour=10, minute=0)
    result = F.compute_state(
        "TIPOCAMBIO",
        "2026-08-31",
        manifest_row=_make_manifest("Diaria — días hábiles bancarios"),
        as_of=date(2026, 9, 1),
        now=now,
    )
    assert result["estado"] == "ACTUALIZADO"
    assert result["periodo_oficial"] == "Ago 26"


def test_fix_just_before_publish():
    """2026-09-01 11:59, FIX del 31 ago -> ACTUALIZADO."""
    now = _dt(year=2026, month=9, day=1, hour=11, minute=59)
    result = F.compute_state(
        "TIPOCAMBIO",
        "2026-08-31",
        manifest_row=_make_manifest("Diaria — días hábiles bancarios"),
        as_of=date(2026, 9, 1),
        now=now,
    )
    assert result["estado"] == "ACTUALIZADO"


def test_fix_inside_tolerance():
    """2026-09-01 12:30, FIX del 31 ago -> ACTUALIZADO o PUBLICACIÓN PENDIENTE, NO REZAGADO."""
    now = _dt(year=2026, month=9, day=1, hour=12, minute=30)
    result = F.compute_state(
        "TIPOCAMBIO",
        "2026-08-31",
        manifest_row=_make_manifest("Diaria — días hábiles bancarios"),
        as_of=date(2026, 9, 1),
        now=now,
    )
    assert result["estado"] in ("ACTUALIZADO", "PUBLICACIÓN PENDIENTE")
    assert result["estado"] != "REZAGADO"


def test_fix_rezagado_after_publish():
    """2026-09-01 15:00, FIX sigue en 31 ago -> REZAGADO."""
    now = _dt(year=2026, month=9, day=1, hour=15, minute=0)
    result = F.compute_state(
        "TIPOCAMBIO",
        "2026-08-31",
        manifest_row=_make_manifest("Diaria — días hábiles bancarios"),
        as_of=date(2026, 9, 1),
        now=now,
    )
    assert result["estado"] == "REZAGADO"


def test_tasa_not_rezagado_without_change():
    """Tasa objetivo no cambia todos los días; la última observación es válida."""
    now = _dt(year=2026, month=9, day=1, hour=15, minute=0)
    result = F.compute_state(
        "TASA",
        "2026-08-06",
        manifest_row=_make_manifest("Diaria (cambios discretos)"),
        as_of=date(2026, 9, 1),
        now=now,
        ind={"observations": [{"period": "2026-08-06"}]},
    )
    assert result["estado"] == "ACTUALIZADO"


def test_reservas_weekly_calendar_respects_publish_time():
    """Reservas: antes de la publicación semanal, la semana previa es válida."""
    now = _dt(year=2026, month=9, day=1, hour=10, minute=0)
    cal = [
        {"clave": "RESERVAS", "estatus": "publicado", "fecha_iso": "2026-08-25", "periodo_referencia": "21 de agosto de 2026", "usar_para_frescura": False},
        {"clave": "RESERVAS", "estatus": "publicado", "fecha_iso": "2026-09-01", "periodo_referencia": "28 de agosto de 2026", "usar_para_frescura": False},
    ]


def test_reservas_rezagado_after_publish():
    """Reservas: después de la publicación, si aún no llegó el nuevo dato -> REZAGADO."""
    now = _dt(year=2026, month=9, day=1, hour=15, minute=0)
    cal = [
        {"clave": "RESERVAS", "estatus": "publicado", "fecha_iso": "2026-08-25", "periodo_referencia": "21 de agosto de 2026", "usar_para_frescura": False},
        {"clave": "RESERVAS", "estatus": "publicado", "fecha_iso": "2026-09-01", "periodo_referencia": "28 de agosto de 2026", "usar_para_frescura": False},
    ]


@pytest.mark.parametrize("hour,minute,expected", [
    (10, 0, "ACTUALIZADO"),
    (11, 59, "ACTUALIZADO"),
    (12, 30, "ACTUALIZADO"),
    (15, 0, "REZAGADO"),
])
def test_fix_hourly_state(hour, minute, expected):
    now = _dt(year=2026, month=9, day=1, hour=hour, minute=minute)
    result = F.compute_state(
        "TIPOCAMBIO",
        "2026-08-31",
        manifest_row=_make_manifest("Diaria — días hábiles bancarios"),
        as_of=date(2026, 9, 1),
        now=now,
    )
    assert result["estado"] == expected, (hour, minute, result["motivo"])


@pytest.mark.parametrize("include_next", [True, False])
def test_pib_oportuno_usa_su_calendario_y_el_aviso_del_boletin(include_next):
    pib = {
        "observations": [{"period": "2T-26 P"}, {"period": "3T-26 P"}],
        "proxima_publicacion_boletin": {
            "fecha_publicacion": "29 de enero de 2027",
            "fecha_iso": "2027-01-29",
            "periodo_base": "3T-26 P",
        },
    }
    calendar = [
        {"clave": "PIB", "estatus": "publicado", "fecha_iso": "2025-01-30",
         "fecha_publicacion": "30 de enero de 2025", "periodo_referencia": "Cuarto trimestre de 2024"},
        {"clave": "PIB", "estatus": "publicado", "fecha_iso": "2026-10-30",
         "fecha_publicacion": "30 de octubre de 2026", "periodo_referencia": "Tercer trimestre de 2026"},
        {"clave": "PIBSEC", "estatus": "próximo", "fecha_iso": "2026-11-23",
         "fecha_publicacion": "23 de noviembre de 2026", "periodo_referencia": "Tercer trimestre de 2026"},
    ]
    if include_next:
        calendar.append({"clave": "PIB", "estatus": "próximo", "fecha_iso": "2027-01-29",
                         "periodo_referencia": "Cuarto trimestre de 2026"})

    now = _dt(year=2026, month=11, day=18, hour=14, minute=0)
    state = F.compute_state("PIB", "3T-26 P", _make_manifest("Trimestral"), {},
                            calendar, ind=pib, now=now)
    assert state["estado"] == F.ESTADOS["ACTUALIZADO"]
    assert state["periodo_oficial"] == "Tercer trimestre de 2026"
    assert state["fecha_publicacion_oficial"] == "30 de octubre de 2026"
    assert state["proxima_publicacion"] == "29 de enero de 2027"
    assert state["periodo_proximo"] == "4T-26"
    assert state["proxima_publicacion_tipo"] == "oficial"

    pib["proxima_publicacion_boletin"]["periodo_base"] = "2T-26 P"
    _, prox = F._resolve_pub_prox(calendar, "PIB", pib, now.date())
    assert (prox and prox["periodo_referencia"]) == ("Cuarto trimestre de 2026" if include_next else None)


def test_pibsec_distingue_publicacion_oficial_y_nivel_cargado():
    calendar = [
        {"clave": "PIBSEC", "estatus": "publicado", "fecha_iso": "2026-08-24",
         "periodo_referencia": "2° trimestre 2026", "url_boletin": "boletin-2t.pdf"},
        {"clave": "PIBSEC", "estatus": "publicado", "fecha_iso": "2026-11-23",
         "periodo_referencia": "3er trimestre 2026", "url_boletin": "boletin-3t.pdf"},
    ]
    ind = {"observations": [{"period": "2T-26"}]}
    manifest = _make_manifest("Trimestral")
    before = F.compute_state("PIBSEC", "2T-26", manifest, {}, calendar, date(2026, 11, 22), ind)
    assert before["estado"] == "ACTUALIZADO"
    lag = F.compute_state("PIBSEC", "2T-26", manifest, {}, calendar, date(2026, 11, 23), ind)
    assert lag["estado"] == "REZAGADO"
    assert "3er trimestre 2026" in lag["motivo"]
    assert lag["periodo_oficial"] == "2° trimestre 2026"
    assert lag["url_boletin"] == "boletin-2t.pdf"
    ind["observations"].append({"period": "3T-26"})
    updated = F.compute_state("PIBSEC", "3T-26", manifest, {}, calendar, date(2026, 11, 23), ind)
    assert updated["estado"] == "ACTUALIZADO"
    assert updated["url_boletin"] == "boletin-3t.pdf"
