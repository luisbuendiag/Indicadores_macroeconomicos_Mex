# Reporte de pruebas — Ajustes institucionales V3 (PR #2)

**Cómo se probó:** dashboard estático servido localmente en `http://localhost:8099/index.html` sobre la rama `feature/ajustes-institucionales-v3` (datos regenerados con `build_data.py --offline`, sin tokens INEGI/Banxico). Prueba E2E por navegador + verificación del Excel descargado con `openpyxl` + generación de fichas en PDF con Chrome headless (carta vertical).

**Resultado global:** todas las aserciones planeadas pasaron. Sin fallos. Limitaciones conocidas (no bloqueantes) al final.

---

## Escalaciones / limitaciones (leer primero)
- **Sin `INEGI_TOKEN`/`BANXICO_TOKEN`:** los 8 indicadores con serie muestran **dato de respaldo**, no actualización automática. Esto es el comportamiento honesto solicitado, pero significa que la automatización real **no se pudo probar** end-to-end.
- **EMIM sin datos confirmados:** su ficha (pantalla y PDF) muestra el encabezado institucional y el estado "pendiente de token"; no se inventan cifras ni se copia el contenido de la Nota EMIM.
- **Calendario 2026 exacto:** integrado desde `data/calendar_sources/2026.json` (58 publicaciones oficiales INEGI). La arquitectura admite `2027.json`, `2028.json`, etc. sin cambiar el frontend.
- Localmente `pytest -q` → **16 passed**; `validate.py` → 0 errores críticos.

---

## Resultados por aserción

| # | Prueba | Resultado |
|---|--------|-----------|
| T1 | Panorama muestra exactamente 11 principales con estados honestos | passed |
| T1 | Scaffolds (IMFBCF/IOAE/EMIM) sin cifras inventadas | passed |
| T2 | Complementarios (IED/FIX/tasa/reservas) solo en Entorno financiero | passed |
| T3 | Tarjeta abre ficha; navegación anterior/siguiente funciona | passed |
| T3 | Ficha PIB con una sola "Variación anual" (sin duplicado) | passed |
| T4 | Balanza distingue saldo (2,259) de variación del saldo (−2,261 mdd) | passed |
| T5 | Scaffold IMFBCF muestra estado "Pendiente de token", sin datos | passed |
| T6 | "Imprimir ficha": carta vertical, solo ficha activa, sin navegación | passed |
| T7 | Calendario: vista mensual con marcas por indicador y color por serie | passed |
| T7 | Calendario: vista tabular (fecha, indicador, producto, periodo, frecuencia, institución, estatus) | passed |
| T7 | "Próximo dato por publicarse" y "Próximos 30 días" usan fechas exactas del calendario | passed |
| T8 | Ficha impresa PIB/IGAE/INPC replica lenguaje Nota EMIM (encabezado, bloques, cuadro, resultados, gráfica, 2ª página) | passed |
| T8 | Ficha impresa EMIM: encabezado institucional + estado pendiente honesto (sin datos inventados) | passed |
| Reg | Desocupación atribuida a INEGI/ENOE (no OCDE) | passed |
| Reg | Descarga de Excel funciona (16 hojas; hoja "Síntesis de coyuntura") | passed |

---

## Evidencia

### T1 — Panorama: 11 principales + estados honestos
![Panorama V3](/home/ubuntu/screenshots/ss_bd2b0d32.png)

### T2 — Entorno financiero (complementarios separados)
![Entorno financiero](/home/ubuntu/screenshots/ss_f1421096.png)

### T3 — Ficha PIB (una sola "Variación anual")
![Ficha PIB](/home/ubuntu/screenshots/ss_3380bd60.png)

### T3 — Navegación "siguiente" → PIB por actividad económica
![Ficha PIBSEC](/home/ubuntu/screenshots/ss_17a5a6d1.png)

### T4 — Balanza: saldo vs. variación del saldo
![Ficha Balanza](/home/ubuntu/screenshots/ss_a31ca5f2.png)

### T5 — Scaffold IMFBCF (pendiente, sin cifras)
![Ficha IMFBCF](/home/ubuntu/screenshots/ss_d8637b7f.png)

### T6 — Impresión de ficha (carta vertical, sin navegación)
![Vista previa impresión](/home/ubuntu/screenshots/ss_f3577b18.png)

### Regresión — Desocupación atribuida a INEGI/ENOE
![Ficha Desocupación](/home/ubuntu/screenshots/ss_7b707254.png)

### Regresión — Descarga de Excel
![Descarga Excel](/home/ubuntu/screenshots/ss_7fc1a769.png)

Hojas del Excel descargado (verificadas con openpyxl, 16 hojas):
```
Síntesis de coyuntura, PIB, PIB Sectorial, IGAE, IMAI, Exportaciones, Balanza comercial,
Consumo Privado, IED, Tasa de desocupación, INPC (Inflación),
Formación bruta capital fijo, IOAE, EMIM (Manufactura),
Metodología y fuentes, Control de actualizaciones
```
La hoja **Control de actualizaciones** incluye la columna **"Próxima publicación (calendario)"** con las fechas oficiales (p. ej. PIB: `30 de julio de 2026 · 2° trimestre 2026`).

### T7 — Calendario: vista mensual
![Calendario mensual](/home/ubuntu/fichas_pdf/cal_mensual.png)

### T7 — Calendario: vista tabular
![Calendario tabular](/home/ubuntu/fichas_pdf/cal_tabular.png)

### T8 — Fichas impresas (PDF, carta vertical)
Generadas con Chrome headless desde `#PIB`, `#IGAE`, `#INPC`, `#EMIM`:
- `Ficha_PIB.pdf` — 2 páginas
- `Ficha_IGAE.pdf` — 2 páginas (con "Desempeño por componentes")
- `Ficha_INPC.pdf` — 2 páginas
- `Ficha_EMIM.pdf` — 1 página (estado pendiente honesto, sin cifras)
