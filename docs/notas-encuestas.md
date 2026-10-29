# Notas automáticas EMIM y EMOE

Generación Python sin API de pago. El workflow actualiza las fichas, descarga el
boletín oficial y ejecuta `python scripts/build_survey_notes.py --publish`.

EMIM lee las cinco páginas: cuatro variables desestacionalizadas del cuadro 1,
índices/tasas originales y los 21 subsectores del cuadro 2, y metodología.
Presenta producción, personal, horas y remuneraciones; selección de las tres
mayores y tres menores tasas anuales de producción, con empleo de esos mismos
subsectores. La difusión cuenta el universo completo, sin ponderaciones.

EMOE lee las siete páginas del boletín de confianza: IGOEC, los cuatro ICE y
20 componentes. No integra boletines de pedidos ni tendencia. Originales y
ajustadas se identifican por fila; los cambios siempre están en puntos. El
umbral 50 requiere respaldo metodológico en el PDF. No se trata como producción
observada ni como pronóstico cuantitativo.

Ambas notas tienen dos páginas, tablas editables, bullets, dos gráficas, notas
y fuente fechada. Se conservan PDF completo, texto, hechos con evidencia, CSV
de trazabilidad, revisión y Word en `data/notas/{KEY}/`. Se cotejan de nuevo los
cuadros Word contra el PDF y se comprueba el render antes de publicar. Son
controles Python, no una revisión humana automática. Las candidatas iniciales
se inspeccionan visualmente antes de integrar su generador.

La URL debe ser HTTPS y del producto exacto en INEGI. No se publica desde archivos
locales. El periodo debe coincidir con la ficha y el año con el membrete. La
huella incluye fuente, plantilla, configuración y código. Si cambian cuadros,
universo, serie, metodología, periodo o render, se conserva la nota previa y se
registra error. La ficha señala si el Word está pendiente o corresponde a un
periodo previo. Se respetan `enabled`, `auto_publish`, `NOTES_PILOT_ENABLED` y
`NOTES_AUTO_PUBLISH`. La reutilización de una publicación requiere hash correcto.

Pruebas: `python -m pytest -q tests/test_survey_notes.py` y la selección de
regresión de notas, snapshots y validación. Revisión local de una edición:
`python scripts/build_survey_notes.py --key EMIM --pdf /ruta/boletin.pdf`.

Las integraciones con mensaje `[notes-only]` ejecutan la misma publicación
sobre las fichas vigentes, descargando de nuevo los boletines, sin recalcular
datos, calendario, noticias ni Excel. Se mantienen los cotejos de periodo,
fuente y QA. Las corridas programadas siguen ejecutando el flujo completo.
Un push más reciente cancela una corrida obsoleta antes de publicar.
