# Piloto de notas automáticas IMOAM

Este PR incorpora el primer indicador de los quince módulos de la skill de notas
INEGI. Las otras catorce notas conservan su proceso actual. El piloto no está
activado por defecto y no requiere modificar el frontend para descargar Word.

## Flujo y límites

1. El pipeline de datos actualiza la ficha y valida el boletín oficial.
2. El piloto descarga ese PDF desde el dominio INEGI permitido; valida producto,
   fecha, periodo y seis cifras. Extrae el texto de todas las páginas y conserva
   evidencia por página/cuadro. No toma cifras de imágenes del dashboard.
3. Contrasta las seis cifras con la ficha. Una discrepancia bloquea esa nota.
4. La identidad de la candidata combina PDF, plantilla, reglas, código,
   configuración y modelo. Detecta una revisión del mismo mes. Una publicación
   sin cambios no vuelve a generar el Word ni a llamar a la API.
5. Genera Word editable de exactamente dos páginas, con tabla inicial y tarjetas
   KPI como la referencia ENOE, resumen, bullets, tres tablas de apoyo, gráfica
   de intervalo y esquema de oportunidad. Extrae evaluación histórica y metodología
   de las páginas 3–4; traza catorce registros, incluidos dos cálculos de amplitud.
   No inventa base, ajuste estacional, causalidad, récords ni resultados observados.
6. Renderiza todas las páginas con LibreOffice/Poppler y comprueba extensión,
   límites de texto y presencia de Noto Sans. La auditoría visual por modelo recibe
   también TODAS las páginas del boletín y de la nota, con los hechos trazados.
7. Solo si datos, lógica, redacción y presentación son aprobados sin incidencias,
   y la publicación se habilitó, reemplaza el Word y sus metadatos. Ante un fallo
   se conserva la última versión. El snapshot Git publica los archivos juntos.

La redacción de IMOAM es determinista: el modelo revisa, no añade cifras ni redacta
hallazgos nuevos. Esta decisión es específica del piloto; ampliar análisis a otros
indicadores requiere su módulo, extractor y pruebas. La skill instalada en ChatGPT
no se ejecuta remotamente en Actions: sus reglas aplicables se adaptan y versionan
explícitamente en `config/notas_reglas/IMOAM.md`.

## Activación tras revisar el PR

En el repositorio, Settings → Secrets and variables → Actions:

| Tipo | Nombre | Valor o función |
|---|---|---|
| Variable | `NOTES_PILOT_ENABLED` | `true`: habilita generación y revisión en el pipeline existente |
| Secret | `OPENAI_API_KEY` | Clave de un proyecto API autorizado para este trabajo |
| Variable | `NOTES_REVIEW_MODEL` | Identificador de un modelo disponible en ese proyecto, con visión y salida JSON Schema |
| Variable | `NOTES_AUTO_PUBLISH` | Primero `false` para comprobar candidatas; después `true` para publicar si aprueban |

Introducir la clave únicamente en GitHub Secrets. No enviarla por chat ni
incorporarla a archivos. Esta implementación no configura credenciales, cobro ni
presupuestos del proyecto. No usa ni presupone credenciales de una sesión ChatGPT.
No se ha elegido un modelo ni realizado una llamada API de pago desde este PR.

Primero habilitar el piloto con publicación desactivada y ejecutar manualmente
“Actualizar datos (pipeline)” en Actions. Revisar el artefacto `notas-imoam-qa` y el
estado de la candidata. Luego habilitar publicación. No hay nueva tarea programada:
reutiliza las tres corridas actuales de lunes a viernes, sujetas a colas de Actions.

## Comportamiento de estados

| Estado | Word descargable |
|---|---|
| `pendiente_configuracion` | Se conserva el anterior; falta revisión por API |
| `validada_sin_publicar` | Se conserva el anterior; candidata aprobada pero publicación desactivada |
| `rechazada` | Se conserva el anterior; la auditoría detectó incidencias |
| `error` | Se conserva el anterior; extracción, concordancia, renderer o API fallaron |
| `vigente` | Nueva nota publicada con evidencia y revisión reproducibles |

El botón NOTA sigue descargando DOCX. La ficha indica periodo de la nota disponible
y mensaje de actualización, evitando presentar una candidata como vigente. Si llega
un periodo nuevo, la nota previa se identifica como pendiente mientras se procesa.

## Costos y reintentos

Una revisión usa una petición API con texto completo y páginas renderizadas. El
límite de salida está en `max_output_tokens` de `config/notas_automaticas.json`.
La tarifa depende del modelo y de las imágenes; no se fija un precio en el código.
Configurar el presupuesto y controles de consumo en el proyecto API antes de activar.

Sin cambios de entrada y con nota publicada no se repite la revisión. Un rechazo
no se vuelve a enviar automáticamente hasta que cambien código/reglas/fuente/modelo.
Los errores transitorios permiten como máximo tres intentos por identidad de entrada.
El operador puede ejecutar `--retry-review` para reintentar expresamente, tras
resolver la causa. Una respuesta incompleta, una negativa o un JSON incorrecto
nunca autorizan publicación. No hay reintentos automáticos dentro de la llamada.

## Preparación local

Se requieren las dependencias Python de requirements.txt, LibreOffice Writer,
Poppler y Noto Sans instalada. En CI se instalan en la etapa del piloto.

```bash
python scripts/build_auto_notes.py
python scripts/build_auto_notes.py --pdf /ruta/boletin.pdf
```

La preparación crea `.notes-work/IMOAM/<identidad>/` (ignorado por Git). No reemplaza
Word ni datos publicados. Si el entorno tiene clave y modelo, ejecuta revisión;
sin ellos prepara las candidatas con estado pendiente. Un PDF local no se permite
con `--publish`: la publicación requiere descarga de la fuente oficial.

```bash
python scripts/build_auto_notes.py --publish --record-status
```

Para publicar también debe estar `NOTES_AUTO_PUBLISH=true`. En CI, `NOTES_WORK_DIR`
apunta a runner.temp para excluir candidatas del artefacto de Pages. Las imágenes,
PDF de render y diagnósticos se guardan siete días en el artefacto de Actions;
no se publican como productos finales. Las fuentes y notas aprobadas quedan en
`data/notas/IMOAM/<identidad>-<hash-word>/`. No sobrescribir los machotes. El año del membrete está declarado en `template_year`: al cambiar de año el piloto exige actualizar la plantilla, sus referencias y esa configuración antes de publicar.

## Fuentes, pruebas y revisión pendiente

Reglas: Skill_Notas_Boletines_INEGI_Economía 1.0.0 (2026-10-28), módulo IMOAM y
contratos de análisis, redacción y QA; presentación sobre la referencia ENOE
aportada por el usuario y la plantilla visual derivada, conservada en el repositorio. Cambiar la skill del chat no modifica estas reglas sin un nuevo PR.

La muestra `docs/examples/notas/IMOAM_nota_piloto.docx` se generó con el boletín
639/26 (28 de octubre de 2026), tiene dos páginas; se renderizó y se inspeccionó visualmente. No
sustituye el Word de producción ni constituye una aprobación de la API. Las
pruebas de API usan respuestas simuladas. Falta comprobar una ejecución real en
Actions con las credenciales/modelo elegidos antes de activar publicación automática.

Referencias de la integración API:
- https://developers.openai.com/api/docs/guides/images-vision
- https://developers.openai.com/api/docs/guides/structured-outputs

La arquitectura existente conserva dos workflows capaces de desplegar Pages.
Este piloto no agrega un tercero. Su consolidación y la extensión al segundo
indicador se dejan para la siguiente etapa, con pruebas de concurrencia específicas.
