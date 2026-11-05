# Nota automática IOAE

`python scripts/build_nowcast_notes.py --publish` genera la nota desde el boletín oficial enlazado en la ficha, sin modelos ni API de pago. Lee seis páginas y los tres cuadros completos de dos meses por tres actividades: anual, mensual y nivel. Valida producto, edición, fechas, referencia, confianza, base, tipos de serie y correspondencia de portada con cuadros.

La observación previa de actividades secundarias se identifica como observada según IMAI por el pie 2. La ausencia de intervalo permanece nula y nunca se completa con ceros ni con un rango inventado. Los demás valores mantienen su condición estimada. No se comparan con revisiones BIE de otra edición.

Word de dos páginas con resumen gris, bullets, cinco tablas y dos gráficas de intervalos al 95%. El texto destaca cuando el intervalo incluye valores negativos o ausencia de cambio; no presenta el punto como observado ni garantizado. Los intervalos de nivel se expresan en puntos y los de variación en porcentaje. No se reconstruyen series desde las gráficas del PDF ni se calculan contribuciones sin ponderaciones.

La evidencia archiva PDF, texto completo, hechos, 48 valores con trazabilidad, revisión Python y Word. La validación local no se presenta como auditoría visual humana. Se respetan las pausas globales y de publicación; fuente no oficial, cambios de estructura, periodo, método, membrete o render conservan la nota anterior. Un PDF local solo permite preparar una candidata, nunca publicarla.
