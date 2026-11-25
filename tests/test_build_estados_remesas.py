import json
import sys
import unittest
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

from openpyxl import Workbook

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_estados_remesas import build_remesas  # noqa: E402


class RemesasEstatales(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalogo = json.loads((ROOT / "config" / "estados.json").read_text(encoding="utf-8"))
        cls.consultado = datetime(2026, 11, 23, tzinfo=timezone.utc)

    def libro(self, modificar=None):
        libro = Workbook()
        hoja = libro.active
        hoja.append(["Ingresos por remesas"])
        hoja.append([None, None, "Ene-Mar 2003", "Abr-Jun 2003", "Jul-Sep 2003",
                     "Oct-Dic 2003", "Ene-Mar 2004"])
        for posicion, entidad in enumerate(self.catalogo["entidades"], 1):
            hoja.append([None, "● " + entidad["nombre_oficial"], *[posicion * t for t in range(1, 6)]])
        hoja.append([None, "● TOTAL", 528, 1056, 1584, 2112, 2640])
        if modificar:
            modificar(hoja)
        archivo = BytesIO()
        libro.save(archivo)
        libro.close()
        return archivo.getvalue()

    def procesar(self, modificar=None):
        return build_remesas(self.catalogo, self.libro(modificar), self.consultado)

    def test_historico_y_calculos_para_32_entidades_y_nacional(self):
        datos = self.procesar()
        self.assertEqual(datos["indicadores"][0]["periodo"], "1T-2004")
        self.assertEqual(len(datos["entidades"]), 32)
        nacional = datos["nacional"]["REMESAS"]
        self.assertEqual(nacional["valor"], 2640)
        self.assertEqual(nacional["serie"][0], ("1T-2003", 528))
        self.assertEqual(nacional["var"], 400)
        primera = datos["entidades"][0]["ind"]["REMESAS"]
        self.assertEqual(primera["lugar"], 32)
        self.assertEqual(primera["var"], 400)
        self.assertAlmostEqual(primera["part"], 100 * 5 / 2640)
        self.assertEqual(datos["entidades"][-1]["ind"]["REMESAS"]["lugar"], 1)

    def test_rechaza_salto_trimestral(self):
        with self.assertRaisesRegex(ValueError, "historial trimestral CE100"):
            self.procesar(lambda hoja: hoja.delete_cols(4))

    def test_rechaza_entidad_ausente(self):
        with self.assertRaisesRegex(ValueError, "32 entidades y el total nacional"):
            self.procesar(lambda hoja: hoja.delete_rows(3))

    def test_rechaza_dato_faltante(self):
        def quitar_dato(hoja):
            hoja["D3"] = None

        with self.assertRaisesRegex(ValueError, "Observaciones incompletas"):
            self.procesar(quitar_dato)

    def test_rechaza_total_que_no_cuadra(self):
        def desajustar(hoja):
            hoja.cell(hoja.max_row, 5, 1585)

        with self.assertRaisesRegex(ValueError, "no cuadran con el total"):
            self.procesar(desajustar)


if __name__ == "__main__":
    unittest.main()
