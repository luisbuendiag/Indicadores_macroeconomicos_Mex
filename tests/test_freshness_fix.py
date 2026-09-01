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
