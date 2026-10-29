# Notas automáticas INPC e INPP

El workflow ejecuta `python scripts/build_price_notes.py --publish` después de las
otras notas. Generación y validación Python, sin API de IA, modelos ni claves.

INPC utiliza el boletín mensual `inpc/inpc_2qAAAA_MM.pdf` y sus seis páginas. Se
leen el cuadro de componentes, sus comparaciones históricas e incidencias y los
20 genéricos destacados (10 al alza y 10 a la baja). INPP utiliza las ocho páginas
de `inpp/inppAAAA_MM.pdf`: total, intermedios, finales, destino de la producción
y 30 genéricos destacados. Los nombres multilínea se reconstruyen por coordenadas
en cada columna del cuadro, sin combinar productos de los dos lados. El texto
completo conserva las aperturas adicionales del boletín.

Se cotejan portada, periodo, publicación, paginación, columnas y orden de las filas.
El año base se lee de la metodología. No se fija una canasta o ponderaciones
permanentes. Tasas en porcentaje e incidencias en puntos porcentuales se conservan
por separado; las incidencias se toman directamente del INEGI con tres decimales.
No se calcula una contribución a partir de ponderaciones supuestas. La comparación
anual previa corresponde al mismo mes de un año antes, no al mes inmediato anterior.

Los Word contienen dos páginas, tarjeta inicial, resumen gris con bullets, cuadros
editables, gráfica anual por componentes y gráfica de incidencias mensuales. La
selección de genéricos muestra tres incidencias positivas y tres negativas entre
los productos destacados del boletín; no se denomina universo completo. Menor
inflación no implica una caída del nivel de precios. INPP no es producción real,
ni una previsión de traslado inmediato al INPC; toda la nota conserva la cobertura
incluido petróleo. No se utiliza un índice de nivel si el boletín no lo publica.

La URL del INPP se fecha por mes de publicación. El conector la construye con el
mes siguiente a la referencia (incluye cruce diciembre/enero), descarga el PDF y
comprueba el periodo antes de asignarlo. Se elimina la búsqueda retrospectiva que
podía etiquetar un boletín de agosto como septiembre. Para la primera publicación,
el generador corrige el vínculo de la ficha solo después de validar la nota y
comprobar que periodo y URL previos no cambiaron. Publicación y rollback conservan
la coherencia de Word, evidencias, estado y vínculo. No se alteran observaciones BIE.

La evidencia conserva PDF, texto, hechos, CSV con unidades y localizadores,
revisión y Word bajo `data/notas/{KEY}/`. La huella incluye código, plantilla,
configuración y fuente; la republicación es idempotente. Las tablas Word,
incluida la tarjeta, se cotejan contra una nueva extracción. Se renderizan dos
páginas y se inspeccionan las nuevas composiciones. Los controles automáticos no
se presentan como revisión visual humana o de IA.

Se respetan `enabled`, `auto_publish`, `NOTES_PILOT_ENABLED`, `NOTES_AUTO_PUBLISH`.
Un PDF local permite revisar una candidata pero nunca publicar. Fuente, periodo,
año de membrete y render son condiciones de publicación. Un fallo conserva la
nota anterior y registra su causa. Las corridas programadas siguen actualizando
datos y notas; `[notes-only]` permite publicar una adaptación sobre la ficha vigente.

Pruebas: `python -m pytest -q tests/test_price_notes.py`. Incluyen unidades,
periodicidad, productos, etiquetas, signos, orden, tablas Word, URL mensual,
cruce de año, periodo real del PDF, carreras, rollback y compatibilidad Python 3.11.
