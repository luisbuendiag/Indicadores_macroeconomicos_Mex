import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_estados_ied import build_ied  # noqa: E402

CATALOG = json.loads((ROOT / "config" / "estados.json").read_text(encoding="utf-8"))


def row(year, quarter, value):
    values = {e["nombre_oficial"]: value for e in CATALOG["entidades"]}
    return {"year": year, "quarter": quarter, "period": f"{quarter}T-{year}",
            "total": sum(values.values()), "values": values}


class IedEstatal(unittest.TestCase):
    def test_periodos_acumulados_nacionales_y_estatales(self):
        source = {"source_url": "https://www.economia.gob.mx/",
                  "periods": [row(2025, q, q) for q in range(1, 5)] + [row(2026, 1, 15), row(2026, 2, 6)]}
        result = build_ied(CATALOG, source, "original")
        state = result["entidades"][0]["ind"]["IED"]
        national = result["nacional"]["IED"]
        labels = ["1T-2025", "1S-2025", "9M-2025", "2025", "1T-2026", "1S-2026"]
        self.assertEqual(result["indicadores"][0]["periodo"], "1S-2026")
        self.assertEqual([p for p, _ in state["serie"]], labels)
        self.assertEqual([p for p, _ in national["serie"]], labels)
        self.assertAlmostEqual(state["var"], 200)
        self.assertAlmostEqual(national["var"], 200)

    def test_sin_base_comparable_o_con_base_cero_devuelve_null(self):
        for periods in ([row(2025, 1, 10), row(2026, 2, 5)],
                        [row(2025, 2, 0), row(2026, 2, 5)]):
            result = build_ied(CATALOG, {"source_url": "", "periods": periods}, "actualizada")
            self.assertIsNone(result["nacional"]["IED"]["var"])
            self.assertIsNone(result["entidades"][0]["ind"]["IED"]["var"])

    def test_una_base_negativa_o_un_flujo_negativo_se_expresa_en_monto(self):
        for prior, current in [(-5, 10), (10, -5)]:
            source = {"source_url": "", "periods": [row(2025, 2, prior), row(2026, 2, current)]}
            data = build_ied(CATALOG, source, "original")["entidades"][0]["ind"]["IED"]
            self.assertIsNone(data["var"])
            self.assertEqual(data["comparable"], prior)
            self.assertEqual(data["cambio"], current - prior)
