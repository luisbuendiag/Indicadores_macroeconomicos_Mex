# Test plan — Ajustes institucionales V3 (E2E)

Target: `http://localhost:8099/index.html` (rama `feature/ajustes-institucionales-v3`, PR #2).
Evidencia de código: `assets/js/config.js` (PRINCIPAL = 11 claves, COMPLEMENTARIOS = 4); `assets/js/app.js` `renderNav`/`panoramaCard`/`indicatorToolbar`/`renderIndicatorView`/`annualVar`; `assets/js/metrics.js` `annualVar` (excluye PIB/BALANZA/INPC…); `scripts/lib_data.apply_profile` (estados).

## T1 — Panorama muestra exactamente 11 tarjetas principales con estados honestos
Acción: abrir el sitio en la vista "Panorama macroeconómico".
Pass: título "Panorama macroeconómico" (no "ejecutivo"); se ven 11 tarjetas: PIB, PIB por actividad económica, IGAE, IMAI, Balanza comercial, Tasa de desocupación, INPC, Consumo privado, Formación bruta de capital fijo, IOAE, EMIM. Los badges muestran "Dato de respaldo" (PIB, PIBSEC, IGAE, BALANZA, DESOCUP, INPC), "En revisión" (IMAI, Consumo) y "Pendiente de token" (IMFBCF, IOAE, EMIM). IMFBCF/IOAE/EMIM dicen "Sin dato disponible" **sin cifra**.
Fail si: aparecen tarjetas complementarias (IED/FIX/tasa/reservas) en el panorama, o los scaffolds muestran cifras inventadas, o el título dice "ejecutivo".

## T2 — Complementarios solo en "Entorno financiero"
Acción: clic en pestaña "Entorno financiero".
Pass: IED, tipo de cambio FIX, tasa objetivo y reservas aparecen aquí (no en el panorama). No compiten con los 11 principales.
Fail si: los complementarios aparecen en el panorama o faltan por completo.

## T3 — Ficha por indicador con navegación (adversarial)
Acción: en el panorama, clic en la tarjeta "PIB"; en la ficha, clic "PIB por actividad económica ›"; luego "← Volver al panorama".
Pass: la tarjeta abre la ficha del PIB (nombre oficial "Producto Interno Bruto", sigla, periodo 1T-26 P, fuente INEGI, estado, gráfica, tabla). El botón "siguiente" cambia a la ficha de PIBSEC. "Volver" regresa al panorama. La ficha del PIB muestra **una sola** tarjeta "Variación anual" (+0.2%), NO dos.
Fail si: la tarjeta no navega, el botón siguiente/anterior no cambia de indicador, o aparecen dos tarjetas "Variación anual" en PIB.

## T4 — Semántica de balanza: saldo ≠ variación del saldo (adversarial)
Acción: observar la tarjeta/ficha de Balanza comercial.
Pass: se muestra el superávit del saldo **2,259** (mdd) y, como concepto distinto, la "Variación del saldo (mensual)" **−2,261 mdd**. La síntesis del panorama describe ambos por separado.
Fail si: el saldo se etiqueta como "variación negativa/deterioro" o ambos números se confunden en una sola métrica.

## T5 — Scaffold honesto (IMFBCF) sin datos inventados
Acción: clic en tarjeta/pestaña "Formación bruta de capital fijo".
Pass: la ficha muestra nombre oficial, estado "Pendiente de token" y el mensaje "…no tiene observaciones cargadas… Se activará al configurar INEGI_TOKEN… No se muestran cifras estimadas ni inventadas." Sin gráfica ni tabla con números.
Fail si: aparece cualquier cifra, gráfica con datos, o el estado dice "actualizado".

## T6 — Impresión "Imprimir ficha" (@media print)
Acción: en una ficha con datos (PIB), abrir vista previa de impresión del navegador (Ctrl+P) para inspeccionar el layout print.
Pass: la vista previa muestra solo la ficha activa (sin barra de navegación/pestañas ni toolbar de botones), con encabezado institucional, en carta vertical. Tabla y gráfica legibles.
Fail si: se imprime toda la navegación/otras vistas, o la ficha se corta ilegible.

## Regresión (etiquetar como tal)
- Descarga de Excel: clic "Descargar Excel" → descarga `Indicadores_Macroeconomicos_Mexico_Actualizado.xlsx`.
- Fuente de "Tasa de desocupación" atribuida a INEGI/ENOE (no OCDE).
