# Reporte de calidad de datos — Duplicado IMAI / Consumo Privado (feb-2026)

## Hallazgo

En el dashboard original, el **Índice mensual de la actividad industrial (IMAI)**
y el **Consumo Privado** presentan **exactamente el mismo valor** en febrero de 2026:

```
104.4568568234
```

Se trata de dos series **no relacionadas** (una mide actividad industrial; la otra,
consumo de los hogares) que además operan en rangos distintos:

| Serie    | Ene-26  | **Feb-26**          | Mar-26  | Rango típico de la serie |
|----------|---------|---------------------|---------|--------------------------|
| IMAI     | 100.8   | **104.4568568234**  | 100.3   | ~99.9 – 102.4            |
| Consumo  | 110.5   | **104.4568568234**  | 113.5   | ~109.9 – 117.4           |

El valor `104.46`:
- es **anómalamente alto** para el IMAI (implica un salto de +3.6 % y una caída de −3.98 % al mes siguiente, atípico en la serie);
- es **anómalamente bajo** para el Consumo Privado (rompe la banda 110–117 en la que se mueve).

La coincidencia de **10 decimales idénticos** entre dos series independientes es
estadísticamente incompatible con un dato real: corresponde a un **error de captura
(copiado/pegado) de una celda a otra** al teclear los datos manualmente.

## Decisión aplicada (conforme a la instrucción del usuario)

> "No asumas cuál de los dos es correcto. Verifica ambos contra la fuente oficial y documenta."

Como el proyecto **aún no cuenta con `INEGI_TOKEN`**, no es posible verificar el valor
oficial de cada serie contra el Banco de Información Económica (BIE) en este momento.
Para **no propagar un dato sospechoso como si fuera correcto** y **no inventar cifras**,
se aplicó lo siguiente:

1. Se marcó la celda de febrero-2026 de **ambas** series como **"en revisión"** y se
   fijó su valor en `null` mediante `data/overrides.json` (el dashboard muestra "—").
2. Se dejó registrado el motivo, la fecha de detección y el pendiente de verificación
   en `data/manifest.json` (campo `revision_detectada` y `observaciones`) y en la hoja
   **"Control de actualizaciones"** del Excel.
3. Se implementó una **validación automática** (`scripts/validate.py`) que detecta
   valores idénticos de alta precisión compartidos entre series no relacionadas y los
   reporta como **error crítico** (bloquea la publicación en el pipeline).

## Trazabilidad

| Campo               | Valor |
|---------------------|-------|
| Valor anterior      | IMAI feb-26 = `104.4568568234`; Consumo feb-26 = `104.4568568234` |
| Valor correcto      | **Pendiente de verificación oficial** (requiere `INEGI_TOKEN` / consulta al BIE) |
| Fuente a consultar  | INEGI — Banco de Información Económica (BIE): IMAI e Índice mensual del consumo privado (IMCPMI) |
| Fecha de consulta   | Pendiente (no disponible sin token al 16-jul-2026) |
| Corrección realizada| Celda de feb-26 anulada y marcada "en revisión" en ambas series; validación anti-duplicados activada |

## Cierre del pendiente

Cuando se cargue `INEGI_TOKEN`:
1. Confirmar los IDs de serie de IMAI e IMCPMI en `config/series.json`.
2. Ejecutar `python scripts/build_data.py` para traer el valor oficial de feb-2026.
3. Actualizar `data/overrides.json` con el valor verificado (`status: "corregido"`,
   `source_checked` y `date_flagged`), o eliminar el override si el dato oficial ya es correcto.
4. Volver a validar y regenerar el Excel.
