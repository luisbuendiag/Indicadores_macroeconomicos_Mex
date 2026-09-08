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
3. **SIC** (Sistema de Indicadores Cíclicos)
4. **IOAE**
5. **IGAE**
6. **IMAI**
7. **EMIM**
8. **EMOE** (Encuesta Mensual de Opinión Empresarial)
9. **DESOCUP** (ENOE)
10. **INPC**
11. **INPP**
12. **CONSUMO** (IMCP)
13. **IMFBCF**
14. **BCMM** (Balanza comercial)

Conceptualmente, Panorama macroeconómico agrupa indicadores de actividad, ciclos económicos, industria, opinión empresarial, mercado laboral, precios, consumo, inversión y sector externo.

### Entorno financiero (indicadores complementarios, 4)

1. **IED** (Inversión Extranjera Directa, Secretaría de Economía)
2. **TIPOCAMBIO** (FIX)
3. **TASA** (tasa objetivo)
4. **RESERVAS** (reservas internacionales)

Entorno financiero contiene la inversión externa reportada por la **Secretaría de Economía** y las variables monetarias y financieras de **Banco de México**. **IED pertenece a Entorno financiero** (no es principal); **EMOE y SIC no pertenecen a Entorno financiero**, ambos son indicadores principales del Panorama macroeconómico.

## SIC (Sistema de Indicadores Cíclicos)

- El indicador `SIC` es el *Sistema de Indicadores Cíclicos* del INEGI (boletín con los Indicadores Compuestos Coincidente y Adelantado), frecuencia mensual.
- La fuente de verdad es el **BIE-BISE del INEGI**: 14 series oficiales — el Indicador Coincidente (`214293`), el Indicador Adelantado (`214307`) y las 12 componentes oficiales (6 de cada compuesto: `214295`, `214297`, `214299`, `214301`, `214303`, `214305` del Coincidente; `214309`, `214311`, `214313`, `214315`, `214317`, `214319` del Adelantado).
- El esquema tiene **18 columnas**: 0-1 (compuestos, puntos), 2-5 (diferencias mensual y a 12 meses de cada compuesto, en **puntos** vía `mom_abs`/`yoy_abs`), 6-17 (componentes cíclicos oficiales, puntos).
- Los valores son **puntos** referenciados a la tendencia de largo plazo (=100), **no** porcentajes ni índices base; las diferencias se expresan en puntos con signo (`emoe` en columnas, `pts`/`pts-signed` en KPI/prosa).
- Las componentes **Tasa de desocupación urbana (TDU), Tipo de cambio real (TCR) y TIIE** son *inversas* a la actividad económica, como indica el boletín oficial.
- El **periodo de referencia** del SIC se alinea al último mes con cifra de los compuestos; los componentes adelantados con cobertura más reciente se conservan dentro de su periodo (ver `compute_sic_metrics` en `scripts/build_data.py`).
- Referencia metodológica oficial: `https://www.inegi.org.mx/programas/sic/` y el Reloj de los ciclos económicos (`https://www.inegi.org.mx/app/relojcicloseconomicos/`).

### Series EMOE confirmadas (para evitar regresión)

- IGOEC: `701401`
- Manufacturas: `701570`
- Construcción: `701407`
- Comercio: `701826`
- Servicios privados no financieros: `701975`

## Notas institucionales (botón NOTA)

- **Regla maestra**: el botón NOTA siempre descarga un Word `.docx` (`application/vnd.openxmlformats-officedocument.wordprocessingml.document`); nunca PDF, HTML, enlace a boletín ni preview.
- **Tres piezas**: `data/source/notas_machote/` guarda los machotes por indicador (`{NOMBRE}_machote.docx`) y `_PLANTILLA_MAESTRA.docx` (fuente de verdad visual institucional); `downloads/indicadores/{KEY}/nota/{KEY}_nota.docx` es la **nota vigente** que descarga el usuario; `config/notas_map.json` mapea indicador → machote + metadatos.
- **El pipeline jamás escribe en `data/source/notas_machote/`**: los machotes son entradas de sólo lectura (`lib_notas.provision_notes` sólo copia *desde* el machote cuando falta la nota vigente).
- **BOLETÍN ≠ NOTA**: BOLETÍN abre el producto oficial INEGI/Banxico/SE; NOTA descarga el documento institucional de la Subsecretaría. Nunca apuntan al mismo archivo.
- Notas vigentes hoy: PIB, PIBSEC (PIBT), SIC, IOAE, IGAE, IMAI, EMIM, EMOE, DESOCUP (ENOE), INPC, INPP, CONSUMO (IMCP), IMFBCF, BCMM — 14 en total. IED, TIPOCAMBIO, TASA y RESERVAS no tienen nota todavía y el botón queda deshabilitado (`nota_disponible=false`, `nota_causa` informativo).
- Metadatos por indicador en `data/indicadores.json`: `ind['nota'] = {available, format:'docx', path, periodo, generated_from:'machote', automatic:false}` además de `nota_disponible`/`url_nota_individual`/`nota_causa` para el frontend.
- `historico/` opcional dentro de `downloads/indicadores/{KEY}/nota/` queda previsto para ediciones pasadas; el botón siempre apunta a la vigente.
- Automatización futura (no implementada): nuevo boletín → datos oficiales → copiar machote → actualizar contenidos/gráficas → validar → `lib_notas.update_nota_vigente`. Sin llamadas a IA en esta fase.

### Regla tipográfica de notas

- **Noto Sans** como fuente base; **cuerpo 11 pt**; DOCX nativo
  (`compatibilityMode=15`, sin `w:useFELayout`); nunca una conversión
  PDF→Word como producto final — si el origen es PDF, reconstruir desde
  `_PLANTILLA_MAESTRA.docx` (ver `scripts/rebuild_pib_nota.py`).
- La nota PIB (2T-2026) fue reconstruida así el 08-sep-2026; sus gráficas
  viven en `data/source/notas_machote/assets/pib/` como assets del machote.
