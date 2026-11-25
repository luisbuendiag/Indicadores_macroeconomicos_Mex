import sys
import unittest
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

from openpyxl import Workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from imcp_history import MONTHS, build_history, for_bulletin  # noqa: E402


def workbook_with_history(*, gap=False):
    workbook = Workbook()
    sheet = workbook.active
    months = [f"{m} 1993" for m in MONTHS] + ["Ene 1994", "Feb 1994"]
    if gap:
        months[7] = "Sep 1993"
    sheet.append([None, "CR362, Mensual, Indices, Base (Base 2018=100)"])
    sheet.append([None, "", *months])
    sheet.append([None, "Consumo (series originales)"])
    sheet.append([None, "● Total", 100, 200, *([100] * 10), 120, 210])
    sheet.append([None, "Consumo (series desestacionalizadas)"])
    sheet.append([None, "● Total", 100, 100, *([100] * 10), 101, 103])
    sheet.append([None, "Consumo (series de tendencia)"])
    sheet.append([None, "● Total", *([500] * 14)])
    file = BytesIO()
    workbook.save(file)
    workbook.close()
    return file.getvalue()


class ImcpHistory(unittest.TestCase):
    now = datetime(2026, 11, 23, tzinfo=timezone.utc)

    def test_series_and_comparisons_remain_separate(self):
        points = build_history(workbook_with_history(), self.now)["observaciones"]
        self.assertIsNone(points[0]["mensual_desestacionalizada"])
        self.assertIsNone(points[0]["acumulada_original"])
        february = points[-1]
        self.assertEqual(february["periodo"], "1994-02")
        self.assertEqual(february["indice_desestacionalizado"], 103)
        self.assertAlmostEqual(february["mensual_desestacionalizada"], 103 / 101 - 1)
        self.assertAlmostEqual(february["anual_desestacionalizada"], 0.03)
        self.assertAlmostEqual(february["anual_original"], 0.05)
        self.assertAlmostEqual(february["acumulada_original"], 0.1)

    def test_rejects_gap_or_duplicate_month(self):
        with self.assertRaisesRegex(ValueError, "faltantes o repetidos"):
            build_history(workbook_with_history(gap=True), self.now)

    def test_requires_latest_bulletin_agreement_without_mutating_it(self):
        raw = build_history(workbook_with_history(), self.now)
        bulletin = {"last_observation": "Feb 94", "observations": [
            {"period": "Feb 94", "values": [103, 0.020, 0.03, 0.05, 0.10]},
        ]}
        history = for_bulletin(raw, bulletin)
        self.assertEqual(history["observations"][0]["period"], "1993-01")
        self.assertEqual(history["observations"][-1]["period"], "1994-02")
        self.assertNotIn("imcp_history", bulletin)
        bulletin["observations"][0]["values"][0] = 105
        with self.assertRaisesRegex(ValueError, "difiere del boletín"):
            for_bulletin(raw, bulletin)
        bulletin["last_observation"] = bulletin["observations"][0]["period"] = "Mar 94"
        with self.assertRaisesRegex(ValueError, "meses de cierre distintos"):
            for_bulletin(raw, bulletin)
