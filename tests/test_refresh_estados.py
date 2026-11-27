import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from refresh_estados import save_snapshot  # noqa: E402


class ActualizarFicha(unittest.TestCase):
    def test_repetir_consulta_conserva_el_archivo_si_solo_cambia_la_fecha(self):
        ficha = {"actualizado": "2026-11-23T18:00:00+00:00", "serie": [("3T-2026", 10)]}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "estados.json"
            self.assertTrue(save_snapshot(path, ficha))
            original = path.read_bytes()
            nueva_consulta = {**ficha, "actualizado": "2026-11-23T19:00:00+00:00"}
            self.assertFalse(save_snapshot(path, nueva_consulta))
            self.assertEqual(path.read_bytes(), original)
            self.assertTrue(save_snapshot(path, {**nueva_consulta, "serie": [("3T-2026", 11)]}))
            self.assertEqual(json.loads(path.read_text())["serie"], [["3T-2026", 11]])
