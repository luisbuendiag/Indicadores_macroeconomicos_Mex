# Nota automática BCMM

`python scripts/build_trade_notes.py --publish` completa la cobertura de los 15 indicadores de Panorama sin modelos ni API de pago. Procesa nueve páginas del boletín oportuno. Extrae 19 filas del cuadro original con mes, anual, acumulado y anual del acumulado; nueve filas históricas por seis columnas; siete filas de mercados por seis columnas; catorce tasas mensuales ajustadas y tres saldos ajustados para dos meses.

El cuadro histórico se extrae a partir de palabras y posiciones del PDF, delimitadas por sus encabezados. No se dividen los enteros con espacios de millares suponiendo que cada grupo es una observación. Se validan orden, periodos, subtotales y saldos de todas las columnas, con tolerancias de redondeo explícitas; la portada se coteja con el cuadro 1.

Word de dos páginas, cuatro tablas y dos gráficas. Los flujos son nominales y se separan originales/ajustados y mes/acumulado. Los saldos no se presentan como crecimiento porcentual; S.S. permanece nulo. Las participaciones de mercados se identifican como cuota acumulada de exportaciones no petroleras. No se reconstruyen historias desde gráficas ni se atribuye fortaleza automática a un superávit.

Se archivan PDF, texto completo, hechos, 191 valores trazables, revisión Python y Word. Las pruebas locales no se presentan como revisión visual humana. Las pausas se respetan y un PDF local nunca permite publicación. Ante cambios de estructura, edición, método, periodo o render se conserva la nota anterior.

La corrección común de fuentes alternativas normaliza los slots ASCII, hAnsi, eastAsia y cs en Noto Sans sin modificar machotes. La conservación de recursos de encabezado y pie se prueba mediante vínculos y hashes frente a plantillas aprobadas, sin exigir nombres o formatos de imagen de una edición antigua.
