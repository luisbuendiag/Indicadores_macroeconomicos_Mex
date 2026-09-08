---
name: testing-dashboard-indicadores
description: Test the Indicadores Macroeconómicos de México dashboard end-to-end (panorama, fichas, states, print, Excel). Use when verifying UI/data changes to this static ECharts dashboard.
---

# Testing — Tablero de Indicadores Macroeconómicos de México

Static dashboard: HTML + ES modules + ECharts, Python pipeline (build_data/build_excel), pytest.
No backend at runtime — the app reads `data/*.json`. Fully testable locally without secrets.

## Setup
1. Regenerate data offline (no tokens needed):
   ```bash
   cd <repo>
   python scripts/build_data.py --offline
   python scripts/build_excel.py
   ```
2. Serve statically and open in browser:
   ```bash
   python -m http.server 8099   # then http://localhost:8099/index.html
   ```
   The dashboard is a plain static site; there is no dev server / build step.
3. Fast checks before UI testing:
   ```bash
   python -m pytest -q            # expect all green
   python scripts/validate.py     # 0 critical errors; pending-state warnings are OK
   # JS has no bundler; sanity-check ES modules by copying to .mjs and: node --check file.mjs
   ```

## Key things to verify (V3 spec)
- **Exactly 14 principal indicators** on the panorama, in this order:
  1. PIB (EOPIBT)
  2. PIBSEC (PIB trimestral a precios constantes, sigla PIBT)
  3. SIC (Sistema de Indicadores Cíclicos)
  4. IOAE
  5. IGAE
  6. IMAI
  7. EMIM
  8. EMOE (Encuesta Mensual de Opinión Empresarial)
  9. DESOCUP (ENOE)
  10. INPC
  11. INPP
  12. CONSUMO (IMCP)
  13. IMFBCF
  14. BCMM (Balanza comercial)
  Source of truth: `assets/js/config.js` `PRINCIPAL`.

- **Complementarios (IED, TIPOCAMBIO, TASA, RESERVAS)** must appear ONLY in
  "Entorno financiero", never in the panorama. IED (Secretaría de Economía)
  es ahora complementario; SIC y EMOE son principales del Panorama.
- **SIC**: la ficha muestra el Indicador Coincidente como cifra principal, el
  Adelantado como secundario, diferencias mensuales/anuales en **puntos** (nunca
  en %) y las 12 componentes oficiales en small multiples con referencia 100.
- **Honest states** per indicator: badges "Dato de respaldo" / "En revisión" /
  "Pendiente de token". Without tokens, indicators with a backup series show "dato de
  respaldo" (NOT "actualizado automáticamente"). Scaffolds (IMFBCF/IOAE/EMIM) must show a
  pending state with NO invented figures/charts.
- **Ficha navigation**: each panorama card opens its ficha; toolbar has Volver / anterior
  / siguiente / Calendario / Imprimir ficha / Descargar Excel.
- **Balanza semantics**: "Cifra actual" = saldo (superávit, e.g. 2,259) is DISTINCT from
  "Variación del saldo (mensual)" (e.g. −2,261 mdd). A negative variation is not the same
  as a deficit. Regression to watch.
- **No duplicated "Variación anual"** on PIB (annualVar excludes PIB/IED/BALANZA/INPC/
  TASA/DESOCUP/IOAE — see `assets/js/metrics.js`).
- **Print**: "Imprimir ficha" (Ctrl+P) should show only the active ficha in letter portrait
  with an institutional header and NO nav tabs / toolbar (`@media print` in styles.css).
- **Excel download** button downloads `Indicadores_Macroeconomicos_Mexico_Actualizado.xlsx`;
  verify sheets with openpyxl — must include `Formación bruta capital fijo`, `IOAE`,
  `EMIM (Manufactura)`, `Control de actualizaciones` (uses field `estado`, not `estatus`).
- **Desocupación** attributed to INEGI/ENOE, not OCDE (regression).

## Nota conceptual — Clasificación permanente de indicadores

A partir de la V3, la separación entre Panorama macroeconómico y Entorno financiero se define de la siguiente manera:

- **Panorama macroeconómico** reúne indicadores de actividad, ciclos económicos (SIC), industria, opinión empresarial, mercado laboral, precios, consumo, inversión y sector externo. Por ello **SIC** (indicadores cíclicos oficiales) y **EMOE** (opinión/confianza empresarial) son indicadores principales del Panorama.
- **Entorno financiero** contiene la inversión externa de la **Secretaría de Economía** (**IED**) y las variables monetarias y financieras de **Banco de México**: **TIPOCAMBIO** (FIX), **TASA** (tasa objetivo) y **RESERVAS** (reservas internacionales).
- **Ni EMOE ni SIC pertenecen a Entorno financiero; IED sí.**

### Series oficiales del SIC (BIE-BISE, regresión a vigilar)

- Indicador Coincidente: `214293`
- Indicador Adelantado: `214307`
- Componentes del Coincidente: `214295`, `214297`, `214299`, `214301`, `214303`, `214305`
- Componentes del Adelantado: `214309`, `214311`, `214313`, `214315`, `214317`, `214319`
- Unidad: puntos (tendencia de largo plazo = 100); las diferencias mensual/anual
  se calculan con `mom_abs`/`yoy_abs` en `scripts/sources/inegi.py`.

### Series EMOE confirmadas (regresión a vigilar)

- IGOEC: `701401`
- Manufacturas: `701570`
- Construcción: `701407`
- Comercio: `701826`
- Servicios privados no financieros: `701975`

## Recording
Record browser interactions; annotate setup/test_start/assertion. Maximize first:
`wmctrl -r :ACTIVE: -b add,maximized_vert,maximized_horz`.

## Gotchas
- Browser may cache old `data/indicadores.json`; hard-reload after regenerating data.
- After changing `build_data`/manifest schema, re-run `build_excel.py` — a mismatch
  (e.g. renamed manifest field) surfaces as a KeyError in `build_excel.py`, not the UI.
- Validation intentionally allows indicators without observations ONLY when their state is
  pending (token/serie/no disponible); otherwise it's a critical error.

## Devin Secrets Needed
- None required for local UI/data testing (offline mode uses backup data).
- To test real automation (not yet verified): `INEGI_TOKEN`, `BANXICO_TOKEN` (GitHub
  Secrets / local `.env`). Series IDs in `config/series.json` must be confirmed first.

## Botón NOTA (fase de notas)

- Cada ficha muestra **CALENDARIO / BOLETÍN / NOTA / EXCEL**. NOTA descarga
  directamente `downloads/indicadores/{KEY}/nota/{KEY}_nota.docx` (Word `.docx`,
  atributo `download`); nunca PDF ni visor externo.
- Habilitado cuando `ind.nota_disponible === true` (hoy los 14 indicadores del
  Panorama); deshabilitado con tooltip "Nota institucional en preparación" para
  IED, TIPOCAMBIO, TASA y RESERVAS.
- BOLETÍN (producto oficial INEGI/Banxico) y NOTA (documento institucional de la
  Subsecretaría) son productos distintos y nunca comparten URL.
- Los machotes permanentes viven en `data/source/notas_machote/` y el pipeline
  no los modifica; al probar descargas verifica que el archivo servido sea un
  `.docx` real (firma `PK`, contiene `word/document.xml`).
