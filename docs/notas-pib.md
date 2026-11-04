# Notas automáticas del PIB

PIB oportuno (`pibo/pib_eo`) y PIB trimestral (`pibt/pib_Pconst`) se generan sin API de IA, usando exclusivamente la edición oficial enlazada en cada ficha. Sus referencias pueden ser distintas y no se alinean artificialmente.

El parser verifica todas las páginas, identidad, edición, fecha, trimestre, encabezados históricos, series y metodología. Coteja las ocho tasas de portada contra el cuadro ajustado; conserva el cuadro original completo, incluidos los 20 sectores SCIAN del PIB trimestral. El acumulado procede del cuadro, sin promediar tasas. La estimación oportuna conserva su carácter y no se calcula una revisión entre periodos distintos.

La nota tiene dos páginas, resumen gris con bullets, tres tablas y dos gráficas. Las tasas sectoriales no son contribuciones; la selección de extremos usa los 20 sectores sin ponderarlos. Se archivan fuente, hechos, trazabilidad, revisión y Word. Los controles Python no se presentan como revisión visual humana.

Ejecución: `python scripts/build_gdp_notes.py --publish`. Sin `--publish` prepara candidata. `--pdf` solo admite preparación, nunca publicación. Las pausas globales y de publicación se respetan. Fuente no oficial, cambios de estructura, periodo, membrete o render impiden sustituir la nota anterior.
