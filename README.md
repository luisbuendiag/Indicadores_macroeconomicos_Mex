# Indicadores macroeconómicos de México — Tablero ejecutivo V2

Herramienta ejecutiva de consulta de la coyuntura macroeconómica de México, con
datos oficiales, análisis por reglas deterministas, descarga de Excel actualizado
y un pipeline de actualización automática. Sitio estático compatible con GitHub Pages.

> Reescritura completa sobre un stack abierto y mantenible. El dashboard original
> (artefacto compilado sin código fuente) se conserva intacto como respaldo en
> [`legacy/dashboard-original.html`](legacy/dashboard-original.html) y en la rama
> `backup/dashboard-original`.

## Qué incluye

- **Portada ejecutiva** para entender la coyuntura en <2 min: tarjetas KPI (6–10),
  indicadores que mejoraron / se deterioraron, alertas, próximo dato por publicarse,
  resumen ejecutivo por reglas y botón de descarga del Excel.
- **Secciones**: Panorama, Actividad económica, Industria, Comercio exterior,
  Inversión, Mercado interno, Precios y entorno financiero, Noticias, Calendario,
  Fuentes y metodología, y Descargas.
- **Gráficas ECharts** responsivas, con tooltips, leyendas ejecutivas, exportación a
  imagen y ventanas temporales (12m / 24m / desde 2018 / máximo).
- **Motor de análisis determinista** portado del dashboard original (auditable, sin
  causalidad no demostrada).
- **Excel actualizado** en `downloads/` con las hojas originales + Resumen ejecutivo,
  Metodología y fuentes, y Control de actualizaciones.
- **Pipeline** con conectores para INEGI (BIE), Banco de México (SIE) y World Bank,
  validaciones de calidad, modo de respaldo sin tokens y GitHub Actions.

## Estructura

```
index.html                 Shell del dashboard (carga datos y módulos)
assets/
  css/styles.css           Estilos institucionales + responsive
  js/                       Módulos ES: config, format, metrics, charts, app
data/
  indicadores.json         Capa de datos normalizada (fuente de verdad del front)
  csv/*.csv                Un CSV por indicador
  manifest.json            Control de actualizaciones / calidad
  overrides.json           Correcciones de calidad (no inventa cifras)
  calendario.json          Calendario de publicaciones
  noticias.json            Noticias/referencias oficiales (generado)
  worldbank.json           Contexto anual (fuente sin token)
scripts/
  extract_legacy.py        Inicializa la capa de datos desde el bundle original
  build_data.py            Pipeline transaccional (conectores + validación + respaldo)
  validate.py              Validaciones de calidad
  build_excel.py           Genera el Excel actualizado
  fetch_news.py            Recopila RSS oficiales (a prueba de fallos)
  lib_data.py              Utilidades compartidas
  sources/                 Conectores INEGI / Banxico / World Bank
config/series.json         Mapa indicador -> series de cada fuente
downloads/                 Excel publicado
legacy/                    Respaldo del dashboard original
tests/                     Pruebas (pytest)
.github/workflows/         CI: pruebas, actualización de datos, despliegue a Pages
docs / *.md                Auditoría, fuentes, arquitectura, guía de actualización, rollback
```

## Uso local

```bash
# 1) (opcional) tokens
cp .env.example .env   # y coloca INEGI_TOKEN / BANXICO_TOKEN si los tienes

# 2) dependencias
pip install -r requirements.txt

# 3) pipeline de datos (usa .env; sin tokens conserva el último dato válido)
python scripts/build_data.py            # online (World Bank + los que tengan token)
python scripts/build_data.py --offline  # sin red

# 4) noticias y Excel
python scripts/fetch_news.py
python scripts/build_excel.py

# 5) servir el sitio (los módulos ES requieren http)
python -m http.server 8099
# abre http://localhost:8099/index.html
```

## Documentación

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — diseño y separación de capas.
- [`UPDATE_GUIDE.md`](UPDATE_GUIDE.md) — cómo actualizar datos, cargar tokens y hacer rollback.
- [`DATA_SOURCES.md`](DATA_SOURCES.md) — fuentes oficiales, series y viabilidad de automatización.
- [`AUDITORIA_DASHBOARD.md`](AUDITORIA_DASHBOARD.md) — auditoría del dashboard original.
- [`REPORTE_IMAI_CONSUMO.md`](REPORTE_IMAI_CONSUMO.md) — reporte del valor duplicado feb-2026.
- [`COMPARACION_ANTES_DESPUES.md`](COMPARACION_ANTES_DESPUES.md) — antes/después.

## Notas

- Cifras oficiales sujetas a revisión. El análisis es por reglas; no se atribuye causalidad.
- Fuente de la tasa de desocupación: **INEGI/ENOE** (la OCDE es sólo comparativo internacional).
- No se incluyen secretos en el repositorio; los tokens se cargan como GitHub Secrets o `.env`.
