import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_estados import assemble_estados  # noqa: E402

CATALOG = json.loads((ROOT / "config" / "estados.json").read_text(encoding="utf-8"))


def edition(key, period, value):
    return {
        "version": 1,
        "estado": "oficial",
        "actualizado": "2026-11-23T18:00:00+00:00",
        "indicadores": [{"clave": key, "periodo": period, "estatus": "oficial"}],
        "nacional": {key: {"valor": 32 * value}},
        "entidades": [{"clave": entry["clave"], "ind": {key: {"valor": value}}}
                      for entry in CATALOG["entidades"]],
    }


class PanoramaEstatal(unittest.TestCase):
    def test_conserva_periodos_y_valores_de_cada_indicador(self):
        data = assemble_estados(CATALOG, [edition("IED", "2T-2026", -1), edition("REMESAS", "3T-2026", 2)])
        self.assertEqual([item["periodo"] for item in data["indicadores"]], ["2T-2026", "3T-2026"])
        self.assertEqual(len(data["entidades"]), 32)
        self.assertEqual(data["entidades"][0]["ind"], {"IED": {"valor": -1}, "REMESAS": {"valor": 2}})
        self.assertEqual(data["nacional"]["REMESAS"]["valor"], 64)

    def test_rechaza_indicador_duplicado(self):
        with self.assertRaisesRegex(ValueError, "una sola vez"):
            assemble_estados(CATALOG, [edition("IED", "2T-2026", 1), edition("IED", "1T-2026", 2)])

    def test_rechaza_edicion_de_prueba(self):
        with self.assertRaisesRegex(ValueError, "solo admite indicadores oficiales"):
            assemble_estados(CATALOG, [{**edition("IED", "2T-2026", 1), "estado": "prueba"}])

    def test_rechaza_ficha_incompleta(self):
        data = edition("REMESAS", "3T-2026", 2)
        data["entidades"].pop()
        with self.assertRaisesRegex(ValueError, "Cobertura estatal inválida"):
            assemble_estados(CATALOG, [data])
