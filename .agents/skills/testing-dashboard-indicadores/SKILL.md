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
  3. IOAE
  4. IGAE
  5. IMAI
  6. EMIM
  7. EMOE (Encuesta Mensual de Opinión Empresarial)
  8. DESOCUP (ENOE)
  9. INPC
  10. INPP
  11. CONSUMO (IMCP)
  12. IMFBCF
  13. IED (Inversión Extranjera Directa)
  14. BCMM (Balanza comercial)
  Source of truth: `assets/js/config.js` `PRINCIPAL`.

- **Complementarios (TIPOCAMBIO, TASA, RESERVAS)** must appear ONLY in
  "Entorno financiero", never in the panorama. IED and EMOE are now principal
  indicators in Panorama macroeconómico.
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

- **Panorama macroeconómico** reúne indicadores de actividad, industria, opinión empresarial, mercado laboral, precios, consumo, inversión y sector externo. Por ello **IED** (inversión real hacia la economía) y **EMOE** (opinión/confianza empresarial) son indicadores principales del Panorama.
- **Entorno financiero** contiene únicamente variables monetarias y financieras de **Banco de México**: **TIPOCAMBIO** (FIX), **TASA** (tasa objetivo) y **RESERVAS** (reservas internacionales).
- **Ni IED ni EMOE pertenecen a Entorno financiero.**

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
