"""Decide si una corrida institucional puede reutilizar el PIBT público."""

import json
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

from lib_format import period_to_date
from pilot_shared_data import HEALTH, checked_at, load_release, simulate

ZONE = ZoneInfo("America/Mexico_City")
KEY = "PIBSEC"


def choose(payload, calendar, health_file=Path(HEALTH), *, now=None, loader=None):
    now = (now or datetime.now(ZONE)).astimezone(ZONE)
    try:
        health = json.loads(health_file.read_bytes())
        if health.get("data_error") is not False:
            raise ValueError("sin comprobante institucional válido")
        data, receipt = (loader or load_release)()
        checked = checked_at(receipt["data_checked_at"]).astimezone(ZONE)
        if checked.date() != now.date() or checked > now or checked.time() < time(12):
            raise ValueError("la consulta comercial no cubre el corte local del mediodía")
        decision = simulate(payload, data, health["data_checked_at"], receipt["data_checked_at"],
                            keys=(KEY,))[KEY]
        if decision["decision"] != "equivalente":
            raise ValueError(decision.get("motivo", "el corte o la revisión requiere confirmación directa"))

        institutional = payload["indicators"][KEY]
        commercial = data["indicators"][KEY]
        cut = period_to_date(commercial["last_observation"])
        for item in calendar:
            if item.get("clave") != KEY or not item.get("usar_para_frescura", True):
                continue
            expected = period_to_date(item.get("periodo_referencia"))
            if expected and expected > cut and item["fecha_iso"] <= now.date().isoformat():
                raise ValueError("el calendario institucional ya espera un trimestre posterior")
        for field in ("periodo_boletin", "url_boletin_oficial", "subsectores"):
            if institutional.get(field) != commercial.get(field):
                raise ValueError(f"discrepancia en {field}")
        if not institutional.get("boletin_validado") or not commercial.get("boletin_validado"):
            raise ValueError("el boletín de PIBT no está validado en ambas ediciones")
        if not (payload["indicators"]["PIB"]["pibt"]["observations"]
                == data["indicators"]["PIB"]["pibt"]["observations"]):
            raise ValueError("diferencias en la serie de nivel agregado PIB.pibt")
    except (OSError, ValueError, KeyError, TypeError):
        # El detalle de un error de descarga no es necesario para el registro de datos.
        return None, "INEGI directo: la edición compartida no acredita equivalencia y vigencia"
    return commercial, receipt["release_id"]


def without_pibt(config):
    inegi = {key: value for key, value in config["inegi"].items() if key != KEY}
    specs = inegi.get("PIB", [])
    if specs:
        remaining = [spec for spec in specs if not spec.get("pibt")]
        if remaining:
            inegi["PIB"] = remaining
        else:
            inegi.pop("PIB")
    return {**config, "inegi": inegi}
