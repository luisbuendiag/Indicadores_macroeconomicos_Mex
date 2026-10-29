# Piloto de notas IMOAM

Versión editorial 1.1 — 28 de octubre de 2026.
Adaptación para ejecución del módulo IMOAM de Skill_Notas_Boletines_INEGI_Economía
(plugin notas-boletines-inegi-economia, versión 1.0.0, 2026-10-28).
La instalación o actualización del plugin en ChatGPT no actualiza este archivo;
las modificaciones de reglas se revisan y versionan mediante PR.

Leer el boletín completo, cuadros, pies y metodología. El IMOAM es una estimación
experimental del IMAI manufacturero, no un resultado observado de EMIM o IMAI.
Conservar fecha de difusión separada del periodo estadístico, unidad, base si
está explícita en la edición, cifras originales y estatus de estimación.
No inventar ajuste estacional, contribuciones de ramas, ponderaciones, causas,
récords, series históricas ni recomendaciones de política.

Cotejar el cuadro 1 de la página 1 y sus seis cifras: índice e intervalo al 95%,
variación anual e intervalo al 95%. Las variaciones se almacenan como fracciones.
Registrar cada cifra con unidad, periodo, comparación, serie, estatus, fuente,
página/cuadro y cálculo. No inferir un año base no visible en esta edición.
Contrastar las seis cifras con la observación correspondiente del dashboard;
una discrepancia bloquea la publicación del Word, no los otros indicadores.

Priorizar lectura relevante y contrapeso material. Si el intervalo anual incluye
cero o valores negativos, el texto debe explicar la incertidumbre y no afirmar
certeza de crecimiento. Menor caída no equivale a expansión. No atribuir
causalidad. El piloto redacta párrafos controlados a partir de cifras verificadas;
el revisor por API revisa esos párrafos y no agrega cifras ni redacta resultados.

Dos páginas sustantivas por instrucción del usuario. La referencia ENOE aportada
manda en presentación: tabla inicial con fecha, producto, periodo y dos tarjetas
KPI; conservar su encabezado/pie. Plantilla visual derivada de esa referencia,
entrada de solo lectura. Word editable, Noto Sans, cuerpo 11 pt, sencillo 0/0;
notas y fuentes 8 pt. Tablas nativas, bullets nativos y visuales legibles.
Resumen ejecutivo, cuadro de estimación e IC95, gráfica de punto e intervalo,
evaluación histórica, esquema de oportunidad, cobertura y notas de interpretación.
Flujo continuo sin saltos manuales; bloquear si no son exactamente dos páginas.

Leer y trazar también evaluación y ficha metodológica: cobertura histórica,
ventana evaluada, inicio del cálculo, plazos aproximados y unidad de observación.
Reextraer en cada edición; no congelar esos números en el texto. Las amplitudes
se calculan por diferencia de límites. La cobertura histórica es desempeño pasado,
no probabilidad de certeza de la estimación actual. El esquema de publicación
no tiene escala exacta. No inventar una serie temporal a partir de una gráfica.

Auditoría A datos, B lógica, C redacción, D presentación. Renderizar todas las
páginas; revisar título, fuente, membrete, tablas/gráficas, legibilidad, recortes,
texto encimado y página vacía. El revisor recibe texto completo y páginas del
boletín, hechos trazados y todas las páginas de la nota. Solo A–D satisfactorios
sin incidencias permiten publicación automática. Ausencia de modelo/clave,
rechazo, respuesta ambigua o fallo de render conserva la última nota publicada.
