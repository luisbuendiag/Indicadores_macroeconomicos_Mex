# Convenciones del proyecto

## Porcentajes y escalas

- **Variaciones porcentuales** (variación trimestral, anual, acumulada, anual original y las de actividades económicas del PIB/EOPIBT) se almacenan internamente como **fracciones**.
  - Ejemplo: `+1.5%` se guarda como `0.015`; `+3.3%` se guarda como `0.033`.
- Para mostrarlas se usa el formato `pct-frac`, que multiplica por `100` y añade `%`.
- Los **valores que ya son porcentaje en la fuente** (tasa de desocupación, inflación, tasa de referencia) se almacenan tal cual y se muestran con `pct-raw`.
- Nunca se almacena un valor como `3.3` y se vuelve a multiplicar por `100`; eso produce resultados como `330%`.

## IGAE

- El indicador `IGAE` es el *Indicador Global de la Actividad Económica*, aproximación mensual del PIB.
- Publica **niveles** (índice base 2018=100) para el IGAE total y actividades primarias, secundarias y terciarias.
- La **variación mensual desestacionalizada** del IGAE proviene del boletín oficial del INEGI (dato puntual del mes más reciente).
- La **variación anual** se calcula a partir del índice original del BIE, se almacena como fracción y se muestra con `pct-frac`.
- No se mezclan series: no se deriva una variación mensual desestacionalizada del índice original.

## PIB Oportuno (EOPIBT)

- El indicador `PIB` es ahora la *Estimación Oportuna del Producto Interno Bruto Trimestral*.
- Publica **variaciones** (no niveles absolutos): trimestral desestacionalizado, anual desestacionalizado, anual original y acumulado.
- Las actividades económicas (`sectores`) se guardan en la misma escala fraccionaria que el resto del indicador.
- La sección de actividades económicas se titula *Variación trimestral por actividad económica* y subtitula *Cambio real respecto al trimestre inmediato anterior, cifras desestacionalizadas*.
