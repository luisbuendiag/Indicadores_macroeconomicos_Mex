# Notas IMOAM automáticas con Python

El piloto genera y publica notas IMOAM sin claves, modelos ni llamadas a servicios
de IA. Reutiliza el pipeline y calendario de GitHub Actions existentes. Las otras
catorce notas conservan su proceso actual. No requiere contratar servicios nuevos;
se ejecuta con los recursos de Actions del repositorio.

## Flujo

1. Descarga únicamente el boletín oficial IMOAM identificado por la ficha.
2. Lee sus cuatro páginas, valida producto, fecha, periodo, serie original,
   carácter experimental y nivel de confianza; contrasta seis cifras con la ficha.
3. Extrae evaluación histórica, ventana, plazos e insumos metodológicos. Cambios
   incompatibles bloquean la publicación; no se completan con cifras supuestas.
4. Genera Word editable de dos páginas según la referencia ENOE: cuadro inicial,
   KPI, resumen, bullets, tablas, intervalo de confianza, esquema de oportunidad
   y notas/fuentes. Traza catorce registros de trazabilidad, incluidos dos cálculos.
5. Renderiza y valida localmente: segunda extracción del PDF, hechos y trazabilidad,
   límites e intervalos, cuadro Word, texto nativo, secciones, bullets, tablas,
   visuales, páginas, integridad de las imágenes, presencia de Noto Sans y geometría.
6. Si todos los controles aprueban, reemplaza Word y metadatos juntos y archiva
   fuente, hechos, trazabilidad y revisión local. Conserva la nota anterior si falla.

La redacción es controlada por reglas por indicador. La cobertura histórica no se
presenta como certeza de la estimación actual. No se inventan series históricas,
bases ausentes, causas, récords ni ajustes estacionales.

## Activación y pausa

La configuración versionada `config/notas_automaticas.json` habilita IMOAM y su
publicación. No hay que crear secretos ni variables nuevas en GitHub. El workflow
no recibe `OPENAI_API_KEY` ni `NOTES_REVIEW_MODEL`; aunque existan, no se usan.

| Control opcional | Efecto |
|---|---|
| Variable Actions `NOTES_PILOT_ENABLED=false` | Omite toda la etapa de notas |
| Variable Actions `NOTES_AUTO_PUBLISH=false` | Genera y valida candidatas sin sustituir el Word |
| Configuración `enabled=false` | Deshabilita el generador |
| Configuración `auto_publish=false` | Desactiva publicación por defecto, salvo variable explícita |

Los controles de pausa existentes en GitHub se respetan. Sin variables,
la configuración versionada habilita generación y publicación. Se reutilizan
las tres corridas entre semana existentes; las colas y fuentes pueden retrasarlas.

## Estados y excepciones

- `vigente`: nota publicada con controles Python aprobados.
- `validada_sin_publicar`: candidata aprobada, publicación desactivada.
- `rechazada`: reglas locales detectaron incidencias; revisar evidencia.
- `error`: descarga, extracción, metodología, concordancia o render fallaron.
- `deshabilitada`: generador desactivado en configuración.

Los estados de error/rechazo conservan el Word descargable y su periodo anterior.
Las candidatas se guardan siete días en `notas-imoam-qa` de Actions, fuera de Pages.
Una excepción puede revisarse en ChatGPT con el boletín, Word y diagnóstico; no
se envía sola a ChatGPT ni crea una tarea o alerta. La corrección se incorpora por
código/reglas y una nueva ejecución. No hay aprobación manual ficticia ni IA.

## Alcance de los controles

`revision.json` identifica `kind=reglas_python`, la versión del validador y cuatro
familias de controles: datos, lógica, estructura y render. **No certifica revisión
visual humana, auditoría editorial abierta ni revisión por un modelo.** Los
controles geométricos no detectan todos los posibles solapamientos o matices.
La muestra institucional sí se inspeccionó visualmente durante su implementación.

El año del membrete se comprueba mediante `template_year`; al cambiar de año se
actualiza la plantilla antes de publicar. Nunca se escriben machotes en ejecución.
La identidad combina fuente, plantilla, reglas, configuración y código; una nota
publicada sin cambios no se genera de nuevo. Un rechazo idéntico espera cambios o
`--retry-review`; los errores de ejecución tienen tres intentos por identidad.

## Prueba local

Requiere dependencias de requirements.txt, LibreOffice, Poppler y Noto Sans.

```bash
python scripts/build_auto_notes.py --pdf /ruta/boletin.pdf
python scripts/build_auto_notes.py --publish --record-status
```

La primera instrucción solo prepara y valida; un PDF local no puede publicarse.
La segunda descarga la fuente oficial y publica si pasa los controles y la
configuración lo permite. `.notes-work/` es temporal e ignorado por Git. En CI,
`NOTES_WORK_DIR` apunta a runner.temp. El botón NOTA sigue descargando un DOCX.

## Reglas y extensión

Adaptación versionada de Skill_Notas_Boletines_INEGI_Economía 1.0.0, con prioridad
a la instrucción del usuario de dos páginas y su referencia ENOE. Actualizar la
skill de ChatGPT no actualiza automáticamente las reglas de Actions. Cada nuevo
indicador requiere extractor, análisis, tablas, gráficas y pruebas específicos.

## Extensión IMAI e IGAE

`build_activity_notes.py --publish` procesa ambos después de IMOAM, sin API de IA.
La extracción lee las cinco páginas y separa cuadro 1 desestacionalizado de cuadro 2
original; valida periodo, producto, base y carácter preliminar. Usa la edición
fechada del boletín, no sustituye las series BIE vigentes. Contrasta la fotografía
registrada por el pipeline cuando existe y corresponde a la misma URL.

Cada Word contiene dos páginas, tres tablas, dos gráficas de componentes, resumen,
bullets y notas. Los límites de los controles geométricos locales también aplican.
Los errores conservan la nota anterior. Archivo, hashes, metadatos y rollback se
comparten con IMOAM; el validador admite únicamente los tres indicadores habilitados.
La configuración de pausa de Actions se comparte con el piloto.
