# Auditoría del Dashboard — Indicadores Macroeconómicos de México

> **Estado:** Documento de auditoría (Fase 1). No se ha modificado el dashboard original.
> **Fecha de auditoría:** 2026-07-16
> **Repositorio auditado:** `Miguelechave89/Indicadores_macroeconomicos_Mex`
> **Dashboard publicado:** https://miguelechave89.github.io/Indicadores_macroeconomicos_Mex/
> **Autor de la auditoría:** Devin (a solicitud de luisbuendiag)

---

## 1. Diagnóstico ejecutivo

El proyecto es **un único archivo `index.html` de ~1.5 MB** publicado en GitHub Pages. Es un dashboard interactivo de **9 indicadores** macroeconómicos de México (PIB, PIB sectorial, IGAE, IMAI, Balanza comercial, IED, Tasa de desocupación, INPC, Consumo privado), construido sobre un **runtime propietario de plantillas ("dc-runtime")** basado en React, con:

- datos **embebidos en JavaScript** (`window.MACRO`);
- **gráficas SVG hechas a mano** (sin librería externa);
- un motor de **análisis textual determinista** (genera 2–3 bullets por indicador con reglas, sin IA) — de calidad notablemente alta;
- KPIs (último dato, variación, máximo, mínimo), tabla de datos con máximos/mínimos resaltados y un botón "Descargar PDF" (usa `window.print`);
- tipografías profesionales embebidas (IBM Plex Mono, Source Serif 4, Noto Sans) y una paleta institucional sobria (verde `#002f2a`, oro `#a57f2c`).

**Veredicto:** La *capa de presentación y el motor analítico son buenos y aprovechables conceptualmente*, pero el proyecto tiene **tres debilidades estructurales graves** que lo hacen inadecuado como herramienta ejecutiva de largo plazo:

1. **No es mantenible ni editable.** `index.html` es un **artefacto compilado ("bundle")**: no existe el código fuente que lo generó (plantilla + lógica + datos + fuentes se empaquetan y comprimen en base64/gzip dentro del HTML). Cualquier cambio real requiere la herramienta propietaria que lo produjo, la cual **no está en el repositorio**. Hoy el proyecto es una **caja negra**.
2. **Los datos se capturan a mano.** No hay pipeline; las cifras se teclean desde el Excel al JS. Esto es lento, propenso a errores y **no cumple** el requisito de actualización automática ni de trazabilidad por serie.
3. **No hay portada ejecutiva ni resumen global.** El dashboard muestra **un indicador a la vez** (navegación por pestañas). Un Secretario no tiene una vista de "estado general de la economía en 2 minutos", ni tarjetas comparativas, ni semáforos, ni calendario de publicaciones, ni descarga del Excel.

Además detectamos un **error de calidad de datos concreto** (ver §4): el valor de `Feb-26` del IMAI y del Consumo Privado es idéntico (`104.4568568234`), lo que evidencia el riesgo de la captura manual.

---

## 2. Problemas críticos

| # | Problema | Impacto | Severidad |
|---|----------|---------|-----------|
| C1 | `index.html` es un bundle sin fuente; no se puede regenerar sin la herramienta propietaria original. | El proyecto no es mantenible ni auditable; cambios futuros bloqueados. | **Crítica** |
| C2 | Datos capturados manualmente en `window.MACRO`; sin automatización ni validación. | Riesgo alto de error humano y de mostrar datos desactualizados. | **Crítica** |
| C3 | No hay separación datos / lógica / presentación; todo en un HTML de 1.5 MB. | Difícil de versionar, revisar en PR y probar. | **Crítica** |
| C4 | No existe descarga del Excel ni de CSV; el "producto Excel" no está integrado. | Incumple un requisito central del proyecto. | **Alta** |
| C5 | Sin fecha real de actualización por serie ni "control de actualizaciones". | No hay trazabilidad; imposible saber si un dato es viejo. | **Alta** |
| C6 | Sin pruebas, sin CI, sin `README`, sin documentación de fuentes. | Sin red de seguridad ante regresiones o datos corruptos. | **Alta** |

---

## 3. Problemas de diseño (UX/UI)

- **No hay portada / panorama ejecutivo.** Se navega indicador por indicador; falta la vista "de un vistazo" con 6–10 tarjetas, semáforos y variaciones.
- **Gráfica SVG de ancho fijo (940×520 px).** En pantallas pequeñas obliga a *scroll horizontal*; no es realmente responsiva (aunque escala con `viewBox`, los textos quedan diminutos en móvil).
- **Panel lateral fijo de 340 px** que en tablet/móvil compite por espacio; el layout es `flex` de dos columnas sin *breakpoints* claros.
- **Tamaños de letra por debajo de lo recomendado** para uso ejecutivo: bullets de análisis a `13.5px`, notas a `12px`, KPIs a `19px`. El brief pide cifras principales de 24–34 px y texto general de 15–17 px.
- **`line-height:1.15`** en los bullets de análisis: demasiado apretado para lectura cómoda.
- **Sin modo comparativo** entre indicadores ni navegación temática (Actividad, Comercio exterior, Inversión, Precios…). El brief pide una estructura por secciones (Fase 6).
- El botón "Descargar PDF" depende de `window.print`: útil, pero no sustituye a una ficha ejecutiva ni al Excel.

**Lo bueno (conservar):** paleta institucional, tipografías, KPIs, tabla con máx/mín resaltados, tooltips en gráfica, y sobre todo el **motor de análisis determinista**.

---

## 4. Problemas de datos

- **DQ1 — Valor duplicado sospechoso:** `IMAI[Feb-26] = CONSUMO[Feb-26] = 104.4568568234`. Es casi seguro un error de copiado. Un pipeline con validación lo habría detectado.
- **DQ2 — Sin fecha de última consulta/actualización por serie.** Solo hay "frecuencia" y "próximo dato" en texto libre.
- **DQ3 — Mezcla de nomenclaturas de periodo** con caracteres invisibles: los periodos usan espacios no separables (`\u00a0`) inconsistentes (`'Jun\xa025'` vs `'May 25'`), lo que complica *parsear* y ordenar.
- **DQ4 — Series original vs. desestacionalizada:** el propio código advierte que PIB/IGAE/IMAI/Consumo son series **originales** (no desestacionalizadas) y que sus variaciones intertemporales llevan estacionalidad. Correcto que lo advierta, pero **no se ofrece la serie desestacionalizada**, que es la relevante para lectura de coyuntura.
- **DQ5 — Ventanas de datos cortas e irregulares:** IGAE/IMAI/Consumo/DESOCUP/INPC traen ~12 meses; PIB/IED ~21 trimestres; Balanza ~25 meses. Series históricas más largas darían mejor contexto (comparativo prepandemia que el brief pide).
- **DQ6 — El Excel tiene 10 hojas y el dashboard 9 indicadores:** el Excel separa "Exportaciones" y "Balanza comercial"; el dashboard las fusiona en BALANZA. No es un error, pero hay que documentar el mapeo.
- **DQ7 — Fuente de la tasa de desocupación** apunta a un enlace de la OCDE, cuando el dato es de la ENOE/INEGI (la OCDE es solo el comparativo 4.9%). Debe corregirse la atribución.

---

## 5. Problemas de arquitectura

- **A1 — Monolito compilado.** Sin separación de capas; imposible de mantener (ver C1/C3).
- **A2 — Datos acoplados al código.** No hay `data/*.json` ni `data/*.csv` como fuente de verdad.
- **A3 — Sin capa de ingesta.** No existen scripts que consulten fuentes oficiales.
- **A4 — Sin CI/CD.** El despliegue es "subir el HTML a mano" (los commits del historial son "Add files via upload").
- **A5 — Fuentes tipográficas embebidas en base64** inflan el HTML a 1.5 MB (pago de descarga en cada visita, sin caché por archivo).
- **A6 — Runtime propietario** (`dc-runtime`) del que dependemos sin poder reconstruirlo.

---

## 6. Riesgos

| Riesgo | Tipo | Probabilidad | Mitigación propuesta |
|--------|------|--------------|----------------------|
| Mostrar datos desactualizados sin avisar | Datos | Alta | Fecha de actualización por serie + semáforo de frescura |
| Error humano al teclear cifras | Datos | Alta | Pipeline automatizado + validaciones |
| No poder modificar el dashboard (caja negra) | Técnico | **Cierta hoy** | Reescritura a stack abierto y mantenible |
| Caída/cambio de una fuente rompe la actualización | Técnico | Media | Conservar último dato válido; nunca borrar; registrar error |
| Publicar datos parciales/inconsistentes | Datos | Media | *Gate* de validación que detiene el workflow |
| Revisión histórica de cifras sin registro | Datos | Media | Detección de cambios vs. versión previa + bitácora |
| Perder el dashboard original | Operativo | Baja | Rama `backup/dashboard-original` + Release del estado actual |
| Fugas de secretos (tokens API) | Seguridad | Baja | Tokens solo como *GitHub Secrets*; nunca en el repo |

---

## 7. Oportunidades de mejora

1. **Portada ejecutiva** con 6–10 tarjetas, semáforos y "próximo dato".
2. **Resumen ejecutivo narrativo** (5–8 puntos) generado con reglas — reutilizar el excelente motor de análisis ya existente.
3. **Datos como archivos abiertos** (`data/*.json` + `*.csv`) versionados y auditables.
4. **Pipeline en Python + GitHub Actions** que consulta INEGI/Banxico/World Bank y regenera datos, Excel y dashboard.
5. **Excel descargable y automático** con hojas "Metodología y fuentes", "Resumen ejecutivo" y "Control de actualizaciones".
6. **Series desestacionalizadas** y **comparativo prepandemia** (índice base 100).
7. **Secciones temáticas** (Actividad, Industria, Comercio exterior, Inversión, Mercado interno, Precios) + **calendario de publicaciones**.
8. **Responsividad real** con *breakpoints* y gráficas fluidas.
9. **Indicadores adicionales esenciales** (ver `DATA_SOURCES.md`): inflación subyacente/no subyacente (ya presentes), tipo de cambio, tasa de referencia, IMSS empleo formal, producción industrial por componente.

---

## 8. Propuesta de estructura (repositorio)

```
/
  index.html                 ← Cascarón ligero (carga JS + data)
  assets/
    css/styles.css
    js/app.js                ← Render del dashboard (vanilla o lib ligera)
    js/charts.js             ← Gráficas (ECharts o D3, ver §12)
    js/analysis.js           ← Motor de análisis determinista (portado del actual)
    fonts/                    ← woff2 servidos como archivos (no base64)
  data/
    indicadores.json         ← Fuente de verdad normalizada (todas las series)
    <indicador>.csv          ← CSV por indicador (descargable)
    manifest.json            ← Fechas de última consulta/actualización, estatus
  scripts/                   ← Pipeline Python
    fetch_*.py               ← Ingesta por fuente (INEGI, Banxico, WorldBank…)
    validate.py              ← Validaciones de calidad
    build_excel.py           ← Genera el .xlsx
    build_data.py            ← Normaliza y escribe data/
  downloads/
    Indicadores_Macroeconomicos_Mexico_Actualizado.xlsx
  docs/
    AUDITORIA_DASHBOARD.md
    DATA_SOURCES.md
    ARCHITECTURE.md
    UPDATE_GUIDE.md
  tests/                     ← Pruebas de datos y de build
  .github/workflows/
    update-data.yml          ← Cron + workflow_dispatch
    deploy-pages.yml         ← Publicación en GitHub Pages
  README.md
```

**Nota de dominio:** el sitio se publica en `https://miguelechave89.github.io/Indicadores_macroeconomicos_Mex/`, por lo que las rutas de `assets/` y `data/` deben ser **relativas** (compatibles con el subdirectorio de GitHub Pages).

---

## 9. Propuesta de automatización

Pipeline **estático + GitHub Actions**, respetando la frecuencia real de cada indicador:

```
[GitHub Actions: cron semanal + workflow_dispatch + local]
        │
        ▼
  fetch_*.py  ──► consulta APIs oficiales (INEGI BIE, Banxico SIE, World Bank)
        │
        ▼
  validate.py ──► columnas obligatorias, fechas, duplicados, nulos, unidades,
        │          saltos atípicos, series orig vs. desest., compara vs. versión previa
        │          (si falla algo crítico → DETIENE y conserva la versión anterior)
        ▼
  build_data.py ──► data/indicadores.json + data/*.csv + manifest.json
        │
        ▼
  build_excel.py ──► downloads/…xlsx (hojas + Metodología + Resumen + Control)
        │
        ▼
  commit + push ──► deploy-pages.yml publica el sitio actualizado
```

- **Frecuencia sugerida:** un cron **semanal** (p. ej. lunes) es suficiente porque casi todos los indicadores son mensuales/trimestrales; el pipeline solo escribe si detecta datos nuevos.
- **Tolerancia a fallos:** si una fuente no responde, se **conserva el último dato válido**, se registra el error y se genera una alerta en Actions; **nunca** se borra el último dato bueno.

---

## 10. Plan de implementación por fases

| Fase | Entregable | Depende de |
|------|-----------|------------|
| **F0** | Respaldo: rama `backup/dashboard-original` + Release del `index.html` actual; rama `feature/dashboard-ejecutivo-v2`. | Acceso de escritura al repo (ver §14). |
| **F1** | `AUDITORIA_DASHBOARD.md` + `DATA_SOURCES.md` (este entregable). | — |
| **F2** | Extracción del `window.MACRO` actual a `data/*.json` + `*.csv` (base de verdad inicial, sin tocar el original). | F1 |
| **F3** | Scripts de ingesta `fetch_*.py` + `validate.py` (INEGI/Banxico/World Bank). | F2, tokens API |
| **F4** | `build_excel.py` con las hojas nuevas + botón de descarga. | F2 |
| **F5** | Dashboard V2 (portada ejecutiva + secciones + responsividad) sobre stack abierto. | F2 |
| **F6** | GitHub Actions (`update-data.yml`, `deploy-pages.yml`). | F3, F4, F5 |
| **F7** | Pruebas (`tests/`) + docs (`README`, `ARCHITECTURE`, `UPDATE_GUIDE`). | F5, F6 |
| **F8** | Evidencia visual (escritorio/tablet/móvil) + PR documentado + rollback. | F5 |

---

## 11. Nivel de dificultad por mejora

| Mejora | Dificultad | Notas |
|--------|-----------|-------|
| Extraer datos a JSON/CSV | Baja | Ya tengo el `window.MACRO` decodificado. |
| Reescritura del dashboard a stack abierto | Media–Alta | Es el trabajo mayor; se reutiliza el motor de análisis. |
| Excel automático con hojas nuevas | Media | `openpyxl`; requiere diseño de plantilla. |
| Ingesta INEGI/Banxico | Media | APIs bien documentadas; requieren token gratuito. |
| Validaciones de calidad | Media | Reglas claras (ver Fase 3 del brief). |
| GitHub Actions | Baja–Media | Cron + workflow_dispatch estándar. |
| Sección de noticias | Alta | Requiere fuentes RSS estables; ver §14 (decisión). |
| Portada ejecutiva + secciones | Media | Principalmente diseño y layout. |
| Responsividad | Media | *Breakpoints* + gráficas fluidas. |
| Pruebas | Baja–Media | `pytest` para datos; *smoke test* de carga para el sitio. |

---

## 12. Dependencias y costos potenciales

- **Runtime del sitio:** propongo **stack abierto**. Dos opciones de gráficas, ambas gratuitas y compatibles con GitHub Pages:
  - **ECharts** (o Chart.js): rápido de implementar, responsivo, buen soporte de tooltips/leyendas.
  - **Portar el renderer SVG actual**: conserva la estética exacta, sin dependencia externa. *(Recomendación: ECharts para velocidad de desarrollo + responsividad; se puede replicar la paleta.)*
- **Pipeline:** Python + `pandas` + `openpyxl` + `requests`. Todo gratuito.
- **CI/CD:** GitHub Actions (gratis en repos públicos).
- **APIs:** INEGI BIE y Banxico SIE requieren **token gratuito** (registro sin costo); World Bank/OECD no requieren token. **Ningún servicio de pago es necesario** para la versión principal.

---

## 13. Qué se puede hacer gratuitamente

- Todo el núcleo: dashboard V2, datos JSON/CSV, Excel automático, pipeline, GitHub Actions, pruebas, documentación, hosting en GitHub Pages.
- Ingesta desde INEGI, Banxico, World Bank, OECD, DataMéxico (tokens gratuitos donde aplique).

## 14. Qué requeriría servicios externos o APIs de pago

- **Sección de noticias automática:** las APIs de noticias de calidad suelen ser de pago o tener límites. **Recomendación:** versión inicial gratuita basada en **RSS/comunicados oficiales** (Banxico, INEGI, Secretaría de Economía) y **calendarios económicos**, con clasificación por reglas; sin API de pago.
- **Análisis con IA generativa:** **no** es necesario. El motor de reglas actual ya genera texto de calidad; una IA sería solo un extra **opcional**.
- **Mapas por entidad federativa:** viable gratis con GeoJSON de INEGI, pero es esfuerzo alto; se propone como *complementario* (fase posterior).

---

## Decisiones que requieren tu autorización (antes de implementar)

1. **Reescritura vs. parche.** El `index.html` actual es un bundle no editable. Recomiendo **reescribir** a un stack abierto y mantenible (conservando estética y motor de análisis). ¿Autorizas la reescritura?
2. **Librería de gráficas:** ECharts (recomendado) vs. portar el SVG actual.
3. **Alcance de indicadores:** ¿nos ceñimos a los 9 actuales + inflación subyacente/no subyacente, o incorporamos ya los "esenciales" extra (tipo de cambio, tasa de referencia, empleo IMSS)? Ver clasificación en `DATA_SOURCES.md`.
4. **Sección de noticias:** ¿versión gratuita por RSS oficiales, o la dejamos como mejora pendiente?
5. **Tokens de API** (INEGI y Banxico, gratuitos): ¿los tramitas tú y los cargamos como *GitHub Secrets*, o arrancamos el pipeline solo con World Bank/OECD y datos actuales mientras tanto?

> Una vez confirmadas estas decisiones, procedo con la implementación por fases (F2→F8).
