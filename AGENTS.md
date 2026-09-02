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

## IMFBCF (inversión)

- El indicador `IMFBCF` es el *Indicador Mensual de la Formación Bruta de Capital Fijo* (sigla IMFBCF), base 2018=100, frecuencia mensual.
- La fuente de verdad histórica es el **SIE del Banco de México**, cuadro **CR363** (`banxico_sie.py`), que descarga las 22 series del conjunto: total, construcción, residencial, no residencial, maquinaria y equipo nacional/importado, y sus subcomponentes, tanto desestacionalizadas como originales.
- Las variaciones del mes más reciente y el índice total se completan con el **boletín de prensa del INEGI** (`ifb/imfbcf{year}_{mm}.pdf`) a través de `inegi_bulletin.py`.
- El esquema final tiene **40 columnas**: 0-2 (total desestacionalizado), 3-5 (construcción), 6-8 (maquinaria y equipo), 9-12 (residencial / no residencial), 13-24 (maquinaria nacional e importado con subcomponentes), 25-27 (total original), 28-39 (índices originales, variaciones anuales y acumulados ene-mes por componente).
- Todas las variaciones porcentuales se almacenan como fracciones y se muestran con `pct-frac`.
- La ficha presenta el índice total, la variación mensual y anual desestacionalizadas, el acumulado ene-mes, y el desglose por componentes en small multiples.

## IOAE

- El indicador `IOAE` es el *Indicador Oportuno de la Actividad Económica* (nowcast del IGAE), frecuencia mensual.
- La fuente de verdad son los **boletines oficiales de prensa del INEGI** (`ioae{year}_{mm}.pdf`) a través de `inegi_bulletin.py`.
- El esquema final tiene **13 columnas**: 0-2 (nowcast anual del IGAE e intervalo de confianza al 95%), 3 (nowcast mensual del IGAE), 4-9 (nowcast anual e intervalos de secundarias y terciarias), 10 (fecha de publicación del boletín, texto), 11 (carácter de la estimación: estimado / preliminar / revisado, texto), 12 (IGAE observado anual, copiado del IGAE para validar el error).
- Las variaciones porcentuales se almacenan como **fracciones** y se muestran con `pct-frac`.
- La ficha presenta el nowcast anual con su intervalo de confianza, la variación mensual estimada, el desglose por actividades secundarias y terciarias, y el contraste con el IGAE observado cuando ya está disponible.

## IMCP (CONSUMO)

- El indicador `CONSUMO` es el *Indicador Mensual del Consumo Privado* (sigla IMCP), base 2018=100, frecuencia mensual.
- El INEGI no publica IDs de BIE abiertos para la serie base 2018; la fuente de verdad son los boletines oficiales de prensa (`imcpmi{year}_{mm}.pdf`).
- El parser extrae 37 series del boletín: índice, variación mensual/anual desestacionalizada, variación anual original, acumulado ene-mes, y desglose por origen (nacional/importado), bienes, servicios y durabilidad (duradero, semi duradero, no duradero).
- Todas las variaciones se almacenan como fracciones y se muestran con `pct-frac` para evitar doble multiplicación por 100.
- En la ficha se presentan el índice, las variaciones desestacionalizadas, el acumulado ene-mes y un desglose por origen y durabilidad.

## Clasificación de indicadores

A partir de la V3, la clasificación permanente del dashboard separa los indicadores en dos grupos:

### Panorama macroeconómico (indicadores principales, 14)

Orden exacto:

1. **PIB** (EOPIBT)
2. **PIBSEC** (PIB trimestral a precios constantes, sigla PIBT)
3. **IOAE**
4. **IGAE**
5. **IMAI**
6. **EMIM**
7. **EMOE** (Encuesta Mensual de Opinión Empresarial)
8. **DESOCUP** (ENOE)
9. **INPC**
10. **INPP**
11. **CONSUMO** (IMCP)
12. **IMFBCF**
13. **IED** (Inversión Extranjera Directa)
14. **BCMM** (Balanza comercial)

Conceptualmente, Panorama macroeconómico agrupa indicadores de actividad, industria, opinión empresarial, mercado laboral, precios, consumo, inversión y sector externo.

### Entorno financiero (indicadores complementarios, 3)

1. **TIPOCAMBIO** (FIX)
2. **TASA** (tasa objetivo)
3. **RESERVAS** (reservas internacionales)

Entorno financiero contiene únicamente variables monetarias y financieras de **Banco de México**. **IED** y **EMOE no pertenecen a Entorno financiero**; ambos son indicadores principales del Panorama macroeconómico porque IED es inversión real hacia la economía y EMOE es opinión/confianza empresarial.

### Series EMOE confirmadas (para evitar regresión)

- IGOEC: `701401`
- Manufacturas: `701570`
- Construcción: `701407`
- Comercio: `701826`
- Servicios privados no financieros: `701975`
