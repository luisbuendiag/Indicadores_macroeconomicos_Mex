# Actualizaciones y recuperación

Datos: lunes a viernes, 01:17, 07:17, 09:17 y 13:17, Ciudad de México.
Se concede una hora de margen para iniciar, consultar fuentes y publicar.
La fecha de consulta no equivale al periodo de referencia de una serie.

- JSON de fuentes y PDF del conector INEGI: hasta tres intentos ante timeout,
  408, 429 o errores 5xx transitorios. Un 404 o un contenido incompatible no
  se considera transitorio. No se altera la validación de cifras ni documentos.
- Las actualizaciones se serializan; otro push no cancela una corrida activa.
  Ambos publicadores comparten el bloqueo `pages`. Artefactos distintos por
  intento permiten repetir un despliegue fallido sin colisiones de nombres.
- `data/update_health.json` registra la consulta en línea que superó validación
  y separa los pendientes de datos de los pendientes de Word. El aviso del
  dashboard vuelve a calcular su antigüedad con el reloj del visitante.
- `Vigilar actualizaciones` verifica la publicación al terminar cada pipeline
  y en cuatro controles posteriores. Recupera hasta dos veces por corte:
  solo despliegue si el repositorio ya está al día; pipeline si faltan datos.
  No inicia otra corrida mientras haya una activa dentro de su plazo.
- Una ejecución detenida o el agotamiento de intentos marca la vigilancia como
  fallida, deja una advertencia y un resumen en Actions. El repositorio tiene
  Issues desactivado: no depende de crear incidencias ni habilita esa función.
  Las notificaciones propias de GitHub dependen de las preferencias del usuario;
  la vigilancia externa en ChatGPT avisa ante una omisión o recuperación.
- Un Word detenido por cambios del boletín conserva su versión anterior,
  aparece pendiente y requiere adaptar el lector. No se publica sin validar
  ni provoca reintentos ilimitados. Las pausas editoriales siguen vigentes.

La comprobación externa en ChatGPT vigila las omisiones del programador de
GitHub con el mismo calendario. Es complementaria: depende de que la tarea y
la conexión GitHub permanezcan activas. Nunca debe iniciar otra corrida si
hay una en curso. No utiliza APIs de IA pagadas en el generador del dashboard.

Ningún programador garantiza disponibilidad absoluta. Una caída simultánea
puede requerir intervención; el último sitio válido se conserva.

## Validación

`python -m pytest -q tests/test_update_health.py`

`node --test tests/update_health.test.mjs`

Las pruebas simulan fallos de red, límites de recuperación, corridas activas,
publicación atrasada, notas pendientes, fin de semana y ausencia de falsas alarmas.
