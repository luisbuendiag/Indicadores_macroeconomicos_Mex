# Nota automática ENOE mensual

`python scripts/build_labor_notes.py --publish` genera DESOCUP sin modelos ni API de pago. Lee el boletín mensual completo de quince páginas; la cobertura de quince páginas es específica de ENOE y no cambia el piloto IMOAM. Extrae completos los cuadros 1, 2, 4 y 7: 21 filas de población por sexo, 29 de ocupación/sector/ingreso, 11 tasas originales y 16 ajustadas nacionales/urbanas. Los demás cuadros, gráficas, notas y método se conservan en el PDF y texto íntegros, sin reconstruir su historia.

Los enteros con espacios de millares sólo se aceptan con una partición única y diferencia anual exacta. Se cotejan identidades poblacionales, desgloses por sexo y totales de ocupación, tasas repetidas y portada. Series, denominadores, base salarial, método, edición y periodos se verifican por separado. Las diferencias porcentuales publicadas no se sustituyen con restas de cifras redondeadas.

Word de dos páginas, cuatro tablas y dos gráficas. La menor desocupación se analiza junto con PEA, participación y ocupados. La informalidad laboral total se distingue de la ocupación en el sector informal y se conserva el contrapeso de condiciones críticas. La nota usa personas, no puestos IMSS; no empalma ENOE/ENOEN/ETOE.

Se archivan PDF, texto íntegro, hechos, trazabilidad con personas/porcentajes/puntos porcentuales, revisión local y Word. Los controles Python no se presentan como auditoría visual humana. Configuración y pausas globales se respetan. PDF local sólo prepara candidata; cambios metodológicos, periodos, datos, membrete o render conservan la última nota válida.
