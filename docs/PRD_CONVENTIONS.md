# Convención de PRD — MACRO institucional

**Edición:** 1.0 · **Fecha:** 2026-11-11

## Fuente de verdad

- Mantener **un PRD canónico por proyecto**. Si ya existe un PRD con otra ruta o nombre, conservarlo y no crear duplicados.
- Para nuevos PRD, preferir `docs/PRD.md`; para documentos existentes, preservar la ruta hasta una migración revisada.
- Usar el futuro repositorio privado `luisbuendiag/Sistema_Agentes` como sede del **PRD maestro transversal**, la plantilla común y las interfaces de supervisión. Este enlace no está activo hasta crear dicho repositorio.

## Mantenimiento

1. Leer PRD y código vigente; no confundir requisitos pendientes con funcionalidades implementadas.
2. Actualizar únicamente requisitos afectados; eliminar repeticiones y justificar cambios relevantes con evidencia.
3. Incluir versión semántica (MAJOR.MINOR.PATCH), fecha, estado, criterios de aceptación y referencias técnicas.
4. Preferir cambios trazables por rama/PR cuando se alteren arquitectura, interfaces de datos, permisos o seguridad.
5. Exportar Word/PDF sólo cuando se necesite una versión de circulación; Markdown es la fuente editable.

## Restricción específica

Mantener datos oficiales, documentos institucionales y automatizaciones totalmente separados de la beta comercial.

**No se modifica el PRD actual con esta convención.** Queda como estándar de trabajo para revisiones posteriores.
