import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_estados_coyuntura import build_edition, observation, rows  # noqa: E402

CATALOG = json.loads((ROOT / "config/estados.json").read_text(encoding="utf-8"))


def test_state_names_do_not_match_the_end_of_other_state_names():
    catalog = {"entidades": CATALOG["entidades"]}
    table = "\n".join(["Total 500"] + [f"{e['nombre_oficial']} {int(e['clave'])}"
                                             for e in catalog["entidades"]])
    values = rows(table, catalog, r"(\d+)", national="Total")
    assert values["09"] == (9,)
    assert values["15"] == (15,)


def test_imss_uses_verifiable_baseline_if_source_is_blocked():
    def unavailable(_url, **_kwargs):
        return b"<html>Unavailable</html>"

    edition = build_edition("IMSS", CATALOG, datetime(2026, 11, 24, tzinfo=timezone.utc),
                            fetch=unavailable)
    assert edition["indicadores"][0]["periodo"] == "2026-09"
    puebla = next(e["ind"]["IMSS"] for e in edition["entidades"] if e["clave"] == "21")
    assert (puebla["valor"], puebla["var"], puebla["cambio"], puebla["lugar"]) == (662046, 0.6, 4053, 12)


def test_enoe_til1_uses_informal_employment_not_informal_sector():
    puebla = (3111161, 57052, 61.2, 1.8, 8.4, 4.9, 62.0, 6.4, 45.7, 70.3, 35.6)
    national = (60040094, 1636604, 59.1, 2.7, 9.3, 5.5, 66.0, 6.9, 37.7, 55.1, 30.2)
    assert observation("ENOE", puebla, national)["tasas"]["Informalidad laboral (TIL1)"] == [70.3, 55.1]
