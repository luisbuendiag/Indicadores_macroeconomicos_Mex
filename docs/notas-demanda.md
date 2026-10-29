# Notas automáticas de consumo e inversión

`python scripts/build_demand_notes.py --publish` se ejecuta después del
aprovisionamiento y las otras notas del workflow. No requiere API de IA,
modelo, token ni servicios de pago. La ejecución programada sigue actualizando
los datos antes de las notas; `[notes-only]` permite publicar cambios editoriales
sobre la ficha vigente y conserva los controles del boletín oficial.

CONSUMO corresponde al IMCP, con URL `imcp/imcpmiAAAA_MM.pdf`; IMFBCF utiliza
`ifb/imfbcfAAAA_MM.pdf`. Los dos parsers leen todas las páginas del boletín,
conservan el texto completo y exigen identidad, fecha y paginación compatibles.
Las cuatro páginas incluyen portada, cuadro ajustado, cuadro original y ficha
metodológica. El año base se lee en la edición y se coteja con la metodología.

Se conservan todos los renglones numéricos: 6 ajustados y 12 originales de
consumo, 11 ajustados y 20 originales de inversión en la estructura admitida.
La jerarquía se identifica por ID, etiqueta y orden: nacional/importado,
durabilidad, transporte y otras maquinarias, tipo de bien y comprador. Se cotejan
los agregados duplicados y el encabezado de portada. Los NA se preservan como
no aplicables; nunca se les asigna cero. Las tasas son reales en porcentajes
publicados dentro de la evidencia; no se sobrescriben valores fraccionarios de
las observaciones del dashboard.

Los Word tienen dos páginas, tarjeta inicial, resumen con bullets en gris,
cuadros editables, dos gráficas de corte transversal y notas. En consumo, las
gráficas comparan cambio mensual y acumulado por durabilidad/origen. En
inversión, comparan componentes mensuales y acumulados por comprador. No se
reconstruyen historias desde imágenes PDF ni se inventan ponderaciones,
contribuciones, causas o récords. El acumulado se toma del cuadro del INEGI.

La evidencia archivada comprende PDF, texto, hechos, CSV de trazabilidad,
revisión y Word, bajo `data/notas/{KEY}/`. La huella incluye fuente, plantilla,
configuración y código. Los controles cotejan de nuevo todas las tablas Word,
incluida la tarjeta, y exigen dos páginas y dos gráficos. Son validaciones
Python, no una revisión humana automática. Las nuevas composiciones se
renderizan e inspeccionan visualmente antes de integrar su generador.

Se conservan los machotes y el último Word si cambia el método, las filas, el
producto, el periodo, la fuente o el render. Se respetan `enabled`,
`auto_publish`, `NOTES_PILOT_ENABLED` y `NOTES_AUTO_PUBLISH`. La publicación
requiere HTTPS oficial, un producto exacto y periodo igual a la ficha. El PDF
local solo sirve para revisión, nunca para publicar. La publicación vuelve a
comprobar periodo y URL antes de reemplazar archivos y aplica rollback ante
fallos de escritura. Un cambio de año requiere actualizar el membrete.

Pruebas: `python -m pytest -q tests/test_demand_notes.py`. Incluyen separación de
series, durabilidad, comprador, NA, orden, totales duplicados, periodo, producto,
fuente, cotejo Word, conservación de la nota anterior y sintaxis Python 3.11.
