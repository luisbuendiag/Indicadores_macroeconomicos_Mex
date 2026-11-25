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



class SharedDataSimulationTests(unittest.TestCase):
    def setUp(self):
        reports = {
            "PIBSEC": ("2T-26", "3T-26", "4T-26"),
            "TIPOCAMBIO": ("2026-11-24", "2026-11-25", "2026-11-26"),
            "REMESAS": ("Ago 26", "Sep 26", "Oct 26"),
        }
        self.series = reports
        self.current = {"indicators": {}}
        for key, (first, most_recent, _) in reports.items():
            ind = {
                "key": key, "last_observation": most_recent, "columns": [{"index": 0}],
                "unidad": "mdd", "frecuencia": "Mensual", "ajuste_estacional": "Original",
                "fuente": {"nombre": "Fuente oficial"},
                "observations": [
                    {"period": first, "values": [10]}, {"period": most_recent, "values": [20]},
                ],
            }
            if key == "TIPOCAMBIO":
                ind["observations_mensual"] = [{"period": "Nov 26", "values": [20]}]
            self.current["indicators"][key] = ind
        self.shared = deepcopy(self.current)

    def simulate(self, commercial_time="2026-12-01T20:00:00+00:00"):
        return pilot.simulate(self.current, self.shared, "2026-11-25T21:00:00+00:00", commercial_time)

    def test_new_period_and_same_cut_revision(self):
        key = "PIBSEC"
        updated = self.shared["indicators"][key]
        updated["observations"][-1]["values"] = [22]
        updated["last_observation"] = self.series[key][2]
        updated["observations"].append({"period": updated["last_observation"], "values": [30]})
        self.shared["indicators"]["REMESAS"]["observations"][-1]["values"] = [25]

        report = self.simulate()
        self.assertEqual(report[key]["decision"], "adoptar")
        self.assertEqual(report[key]["series"]["observations"], {"nuevos": 1, "revisados": 1})
        self.assertEqual(report["REMESAS"]["decision"], "adoptar")
        self.assertEqual(report["TIPOCAMBIO"]["decision"], "equivalente")
        self.assertEqual(self.current["indicators"][key]["last_observation"], "3T-26")

    def test_late_and_lower_coverage_releases_are_retained_independently(self):
        old = self.shared["indicators"]["REMESAS"]
        old["observations"].pop()
        old["last_observation"] = old["observations"][-1]["period"]
        self.shared["indicators"]["TIPOCAMBIO"]["observations_mensual"][0]["values"] = [None]
        self.shared["indicators"]["PIBSEC"]["observations"].pop(0)
        report = self.simulate()
        for key, reason in (("PIBSEC", "faltan periodos"), ("TIPOCAMBIO", "perderían valores"),
                            ("REMESAS", "atrasado")):
            with self.subTest(key=key):
                self.assertEqual(report[key]["decision"], "conservar")
                self.assertIn(reason, report[key]["motivo"])

    def test_old_edition_cannot_supersede_same_cut(self):
        self.shared["indicators"]["REMESAS"]["observations"][-1]["values"] = [25]
        report = self.simulate("2026-11-25T20:00:00+00:00")
        self.assertEqual(report["REMESAS"]["decision"], "conservar")
        self.assertEqual(report["TIPOCAMBIO"]["decision"], "equivalente")

    def test_duplicate_period_is_kept_out(self):
        rows = self.shared["indicators"]["TIPOCAMBIO"]["observations"]
        rows.insert(0, deepcopy(rows[0]))
        report = self.simulate()
        self.assertIn("repetidos", report["TIPOCAMBIO"]["motivo"])

    def test_real_fix_monthly_history_from_1991_keeps_its_order(self):
        rows = [{"period": label, "values": [10]} for label in ("Nov 91", "Dic 92", "Ene 93", "Nov 26")]
        self.current["indicators"]["TIPOCAMBIO"]["observations_mensual"] = deepcopy(rows)
        self.shared["indicators"]["TIPOCAMBIO"]["observations_mensual"] = deepcopy(rows)
        self.assertEqual(self.simulate()["TIPOCAMBIO"]["decision"], "equivalente")
