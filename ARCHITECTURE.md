# Arquitectura

El proyecto separa claramente **datos**, **lógica de análisis**, **gráficas**,
**interfaz**, **generación de Excel**, **scripts de actualización**, **configuración**
y **validaciones**, priorizando estabilidad, auditabilidad y facilidad de mantenimiento
(sin sobreingeniería).

## Capas

### 1. Datos (`data/`)
- `indicadores.json` es la **única fuente de verdad** del frontend. Esquema:
  ```jsonc
  {
    "meta": { "base_year": 2018, "default_window": "since_2018", "windows": [...] },
    "order": ["PIB", "PIBSEC", ...],
    "indicators": {
      "PIB": {
        "key", "nombre", "descripcion", "frecuencia", "unidad",
        "ajuste_estacional", "grupo", "publicacion", "proximo", "notas",
        "fuente": { "nombre", "serie", "link", "metodo" },
        "columns": [{ "label", "index", "fmt" }],
        "observations": [{ "period", "values": [...] }],
        "last_observation", "last_updated", "last_checked",
        "data_quality": [{ "period", "column", "status", "reason" }]
      }
    }
  }
  ```
- Derivados: `csv/*.csv`, `manifest.json` (control de actualizaciones), `summary.json`.
- `overrides.json` aplica correcciones de calidad **sin inventar cifras** (marca celdas
  como `revision`/`corregido`).

### 2. Configuración (`config/series.json`, `assets/js/config.js`)
- `config/series.json`: mapeo indicador → serie de cada fuente (IDs de Banxico son
  públicos; los de INEGI se dejan en `null` hasta confirmarlos con el token).
- `assets/js/config.js`: presentación (paleta, `KPICFG`, `CAPTIONS`, secciones, ventanas).

### 3. Lógica de análisis (`assets/js/metrics.js`, espejo en `scripts/lib_metrics.py`)
- `computeKPI(ind)`: último valor, variación (varias semánticas: yoy, mensual, pp, abs),
  máximo/mínimo, semáforo.
- `analysis(ind, k)`: 2 bullets deterministas (nivel, tendencia, promedio, rango,
  dirección reciente) + reglas específicas (INPC vs objetivo Banxico, composición IED,
  superávit/déficit, contexto de desempleo). No afirma causalidad.
- **SIC** usa una ruta especializada (`_sic_metrics` en `lib_metrics.py` y bloque
  `SIC` en `computeKPI`): el Coincidente es la cifra principal, el Adelantado la
  secundaria; ambos en **puntos** (tendencia de largo plazo = 100) y sus
  diferencias en puntos con signo, nunca en porcentajes.

### 4. Gráficas (`assets/js/charts.js`)
- `buildOption(ind, windowId)` traduce cada indicador a una opción de ECharts
  (barras/apiladas/líneas/doble eje) con la identidad visual sobria, tooltips, toolbox
  de exportación y filtrado por ventana temporal.

### 5. Interfaz (`index.html`, `assets/js/app.js`, `assets/css/styles.css`)
- `app.js` orquesta: carga de datos, header, navegación por secciones, portada ejecutiva,
  bloques por indicador (KPIs, gráfica, análisis, tabla, ficha), noticias, calendario,
  metodología y descargas. Accesibilidad básica (roles ARIA, skip-link, foco visible).

### 6. Pipeline (`scripts/`)
```
extract_legacy.py   (una vez) bundle original -> indicadores.json + csv + manifest
build_data.py       conectores -> overrides -> validación -> respaldo/publicación
  sources/inegi.py      INEGI BIE (requiere INEGI_TOKEN + IDs confirmados;
                        incluye SIC con transformaciones mom_abs/yoy_abs en puntos)
  sources/banxico.py    Banxico SIE (requiere BANXICO_TOKEN)
  sources/worldbank.py  World Bank (sin token; contexto anual)
validate.py         validaciones críticas/advertencias + revisiones
build_excel.py      Excel base + hojas nuevas
fetch_news.py       RSS oficiales (a prueba de fallos)
```

## Flujo transaccional (modo de respaldo)

`build_data.py` es transaccional en términos funcionales:
1. Ejecuta conectores; los que no tienen token/IDs **se omiten sin borrar datos**.
2. Aplica overrides de calidad.
3. Valida en un candidato en memoria/archivo temporal.
4. Si hay **errores críticos**, **no publica**: restaura `data/_backup/last_valid.json`
   y registra el error en `data/update_log.json`.
5. Si pasa, respalda lo anterior (`last_valid.json`) y publica; regenera CSV/manifest/summary.

## Decisiones de diseño

- **Sin framework de build**: HTML + módulos ES + ECharts por CDN (pinned). Cero paso de
  compilación → compatible con GitHub Pages y fácil de auditar.
- **Datos fuera del código**: cambiar cifras nunca requiere tocar JS.
- **Dependencias mínimas** en Python (`openpyxl`, `pytest`); conectores con `urllib` estándar.

## Notas institucionales (.docx)

La descarga de notas sigue una arquitectura de tres capas:

- **Plantilla maestra** (`data/source/notas_machote/_PLANTILLA_MAESTRA.docx`):
  diseño institucional común (tipografía, márgenes, encabezados, paleta
  verde/vino/dorado, pie institucional). Fuente de verdad visual.
- **Machote por indicador** (`data/source/notas_machote/{NOMBRE}_machote.docx`):
  estructura editorial específica del producto. El pipeline nunca lo sobrescribe.
- **Nota vigente** (`downloads/indicadores/{KEY}/nota/{KEY}_nota.docx`):
  el `.docx` que descarga el botón NOTA; siempre Word, máximo ~2 páginas.

`config/notas_map.json` asocia cada indicador con su machote y metadatos.
`scripts/lib_notas.py` (`provision_notes`) aprovisiona la nota vigente desde el
machote sólo cuando falta el archivo, valida que sea un `.docx` real
(`word/document.xml`) y estampa `ind['nota']`/`nota_disponible` en el payload;
`scripts/build_data.py` lo invoca antes de validar, y `scripts/build_notes.py`
expone el mismo paso como CLI. `scripts/validate.py` falla en crítico si una
nota declarada disponible no es un `.docx` válido. La ruta
`downloads/indicadores/{KEY}/nota/historico/` queda prevista para ediciones
anteriores (fase futura).
