"""Regresiones de formato observadas en ENOE 738/26 e IMOAM 739/26."""
import unittest

from notas_enoe import population_rows
from notas_imoam import context_from_pages


class OctubreFormatRegression(unittest.TestCase):
    def test_enoe_ingresos_permits_exact_extra_zero(self):
        data = 'Nivel de ingresos2/ 60 899 893 60 715 334 -184 559 100.0 100.00'
        row, = population_rows(data, ['Nivel de ingresos'], ['income_total'], 'p. 6, cuadro 2')
        self.assertEqual(row['difference'], -184559)
        self.assertEqual(row['relative_current'], 100.0)
        self.assertIsNone(row['relative_difference'])
        self.assertIn('100.00', row['evidence'])
        with self.assertRaisesRegex(ValueError, 'Precisión relativa inesperada'):
            population_rows(data, ['Nivel de ingresos'], ['position_total'], 'p. 6, cuadro 2')
        with self.assertRaisesRegex(ValueError, 'diferencia poblacional incompatible'):
            population_rows(data.replace('-184 559', '-184 560'), ['Nivel de ingresos'], ['income_total'], 'p. 6, cuadro 2')

    def test_imoam_accepts_wrapped_year_but_not_missing_year(self):
        pages = ['', '', 'En 90 % de las ocasiones; comenzó a calcularse en agosto de 2015. '
                          'Comparación entre enero de 2019 y septiembre de\n2026.',
                          'RENEM CFE CENACE confidencialidad\nalrededor de 18 días antes y alrededor de 40 días después.'
                          '\nUnidad de observación Empresa formal en el sector manufacturero de México']
        result = context_from_pages(pages)
        self.assertEqual(result['evaluation_end'], '2026-09')
        self.assertIn('\n', result['evidence']['window'])
        pages[2] = pages[2].replace('\n2026.', '')
        with self.assertRaisesRegex(ValueError, 'bloque de evaluación'):
            context_from_pages(pages)
