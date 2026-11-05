# Nota automática del SIC

El generador Python no usa modelos ni APIs de pago. Lee las trece páginas del boletín oficial SIC. El formato de trece páginas se valida específicamente en este módulo; no altera la cobertura del piloto IMOAM.

La URL se obtiene de la fecha oficial del calendario de la ficha y se confirma con la fecha impresa y el periodo del Coincidente dentro del PDF. Nunca asigna un periodo a un archivo solo por existir ni usa un vínculo antiguo como evidencia actual. La publicación actualiza enlace y nota con control de carrera y rollback; conserva todas las observaciones BIE, que pueden tener una edición distinta de la del boletín.

Se leen los dos cuadros completos: doce meses, indicador compuesto y seis componentes. Las filas deben ser consecutivas, sus encabezados conservar identidad y orden, y las diferencias finales coincidir con la portada. Coincidente y Adelantado mantienen referencias separadas. Niveles a un decimal; cambios a dos, en puntos. Las series inversas se rotulan sin cambiar sus signos publicados.

Word de dos páginas, tres tablas nativas, dos gráficas de diferencias mensuales y resumen gris. La línea cero de las gráficas indica cambio nulo; no sustituye la referencia de nivel de 100. No se reconstruyen niveles, no se infieren aportaciones ni recesiones por cruce de umbral. Se archivan PDF, texto íntegro, hechos, 170 registros de trazabilidad (dos niveles y 168 diferencias), revisión y Word. Los controles locales no equivalen a revisión visual humana.

Ejecutar `python scripts/build_cycle_notes.py --publish`. Sin `--publish`, preparar candidata. `--pdf` nunca permite publicación. Las pausas globales y de publicación se respetan; cambios de producto, edición, periodos, método, membrete o render preservan el Word anterior.
