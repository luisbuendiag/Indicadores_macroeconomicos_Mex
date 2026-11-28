# Cómo usar el tablero

[Tablero de coordinación](tablero.csv) · Corte inicial: 25 de noviembre de 2026.

- **Antes de empezar:** revisar la última versión del tablero y los PRs e issues abiertos. Si existe un PR para el ticket, continuar o revisar en ese mismo PR; no abrir una rama paralela. Si una fila aún no tiene responsable, no asumir que otro agente está libre o que trabaja en ella.
- **Al tomar trabajo:** registrar una sola persona o agente en «Quién», confirmar alcance y escribir la rama. Si dos agentes quieren el mismo ticket, confirmar el relevo antes de hacer cambios.
- **Al entregar o ceder:** actualizar solo la fila propia con fecha, siguiente paso, PR/commit y pruebas. «Completa» exige evidencia que cumpla el criterio, no solo un PR abierto.
- **Estados:** Pendiente, En curso, En revisión, Bloqueado y Completa. «En revisión» describe el estado del trabajo o del PR, no implica que alguien esté trabajando activamente. «Sin asignar» no autoriza reasignar un PR existente.
- **Tipos:** D = datos, F = presentación, N = función nueva, O = operación. **Prioridades:** 1 = urgente o bloqueante, 2 = importante, 3 = mejora. Para cruzar proyectos, enlazar al ticket de origen en lugar de copiarlo.
- **Formato:** CSV UTF-8. No crear otro registro manual para la misma lista; una eventual vista Excel debe generarse desde el CSV, no mantenerse aparte.

## Límites del proyecto

Este repositorio es público: solo estado técnico ya publicable. No copiar insumos internos ni coordinar trabajo comercial aquí. Cualquier push a `main` activa `update-data.yml` y puede publicar, incluso si solo cambia documentación.

Registrar o revisar un ticket no autoriza desplegar, activar automatizaciones, modificar producción ni fusionar cambios con esos efectos.
