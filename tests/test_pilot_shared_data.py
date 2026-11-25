from copy import deepcopy
import json
import unittest

import pilot_shared_data as pilot


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


class SharedDataPilotTests(unittest.TestCase):
    def setUp(self):
        indicators = {}
        for key, fields in pilot.SERIES_FIELDS.items():
            row = [{"period": "1", "values": [10]}]
            indicators[key] = {
                "key": key, "last_observation": "1", "columns": [{"index": 0}],
                "unidad": "mdd", "frecuencia": "Mensual", "ajuste_estacional": "Original",
                "fuente": {"nombre": "Fuente oficial"}, "nota": "institucional",
                **{field: deepcopy(row) for field in fields},
            }
        indicators["IED"] = {"nota": "institucional"}
        self.current = {"indicators": indicators}
        self.shared = deepcopy(self.current)
        self.shared["indicators"]["PIBSEC"]["nota"] = "comercial"
        self.shared["indicators"]["IED"]["nota"] = "comercial"
        self.health = {
            "data_error": False, "query_coverage": "valid",
            "data_checked_at": "2026-11-25T18:31:41+00:00",
            "queried_indicators": list(pilot.SERIES_FIELDS),
        }

    def release(self):
        documents = {pilot.DATA: encoded(self.shared), pilot.HEALTH: encoded(self.health)}
        files = {path: pilot.sha256(content) for path, content in documents.items()}
        documents[pilot.RECEIPT] = encoded({
            "version": 1, "files": files, "release_id": pilot.sha256(encoded(files)),
            "data_checked_at": self.health["data_checked_at"],
        })
        return documents

    def test_validated_release_preserves_institutional_products_and_ied(self):
        release = self.release()
        commercial, _ = pilot.load_release(lambda path, *_: release[path])
        candidate, report = pilot.stage(self.current, commercial)
        self.assertEqual(candidate, self.current)
        self.assertEqual(set(report), set(pilot.SERIES_FIELDS))
        self.assertIsNot(candidate["indicators"]["PIBSEC"]["observations"],
                         commercial["indicators"]["PIBSEC"]["observations"])

    def test_mixed_release_is_rejected(self):
        release = self.release()
        release[pilot.DATA] += b" "
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            pilot.load_release(lambda path, *_: release[path])

    def test_missing_query_coverage_is_rejected(self):
        self.health["queried_indicators"].remove("REMESAS")
        release = self.release()
        with self.assertRaisesRegex(ValueError, "consulta válida"):
            pilot.load_release(lambda path, *_: release[path])

    def test_differences_are_rejected_before_staging(self):
        for field, value in (
            ("columns", []), ("last_observation", "0"),
            ("observations", [{"period": "1", "values": [20]}]),
        ):
            with self.subTest(field=field):
                snapshot = deepcopy(self.shared)
                snapshot["indicators"]["REMESAS"][field] = value
                with self.assertRaisesRegex(ValueError, "REMESAS"):
                    pilot.stage(self.current, snapshot)
