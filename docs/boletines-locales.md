# Notas desde boletines recibidos

Disponible en IMAI, IGAE, IMOAM, EMIM, IMCP (CONSUMO), IMFBCF, INPC, INPP, PIB oportuno, PIB trimestral, SIC, IOAE, EMOE, ENOE (DESOCUP) y BCMM mediante **Cargar boletín**. La selección y el arrastre de un único PDF se procesan dentro de la ficha, en un lector aislado del mismo sitio. Cuando la nota está lista se oculta la zona de carga; **Borrar archivo** restablece la selección y revoca la descarga temporal.

El archivo permanece en memoria del navegador. No hay cargas al servidor, almacenamiento, analítica ni llamadas a IA. No se alteran las cifras o notas oficiales del dashboard. Los PDF preliminares conservan su fecha declarada, incluso futura, y el Word identifica la versión recibida.

Cada módulo lee sus cuadros, verifica periodos y coteja la portada. IMAI e IGAE separan tasas ajustadas, originales y acumuladas; EMIM conserva las cuatro variables y valida los 21 subsectores originales; IMOAM presenta estimaciones originales con IC al 95%, sin inventar una base o variación mensual ajustada.

IMCP e IMFBCF leen los dos cuadros completos y mantienen la jerarquía de origen, durabilidad y comprador. Los agregados repetidos deben coincidir; las compras netas con NA se conservan como nulos. El Word presenta tasas ajustadas, originales y acumuladas, con dos visuales propios.

INPC e INPP separan variaciones (%) e incidencias (pp, tres decimales). INPC admite solo la edición mensual; INPP conserva cobertura incluido petróleo, uso intermedio, finales y destino. Los genéricos se leen por posición y columnas, incluidos nombres multilínea; se seleccionan tres incidencias positivas y tres negativas entre los productos destacados, sin asumir que son toda la canasta.

PIB oportuno (PIB, cuatro páginas) y PIB trimestral (PIBSEC, cinco) conservan tasas trimestrales, anuales y acumuladas por separado. Se cotejan encabezados, portada, las siete columnas originales y el universo completo de 20 sectores del PIBT. No se reconstruyen niveles desde gráficas ni se equipara la estimación oportuna con un resultado definitivo.

SIC lee las trece páginas: dos cuadros de doce meses con siete columnas, periodos separados para Coincidente y Adelantado, cambios en puntos y relaciones inversas. Las dos gráficas utilizan las diferencias publicadas; no reconstruyen niveles ni declaran recesión por un cruce de 100.

IOAE lee seis páginas y los tres cuadros de dos meses por tres actividades. Distingue estimaciones e intervalos al 95% del dato previo observado del IMAI, cuyo intervalo sigue siendo nulo. Las gráficas muestran los rangos anual y mensual; el índice conserva unidades propias.

Se admiten archivos de hasta 20 MB con texto seleccionable: cinco páginas para IMAI, IGAE y EMIM; cuatro para IMOAM, IMCP e IMFBCF. INPC mensual requiere seis páginas e INPP ocho; SIC trece e IOAE seis. EMOE requiere siete páginas, ENOE mensual quince y BCMM oportuna nueve. El membrete vigente es de 2026. Cambios de estructura, datos ambiguos o controles fallidos detienen la generación. No se admite OCR.

Pruebas: `node --test tests/bulletin_upload.test.mjs tests/bulletin_products.test.mjs tests/bulletin_cycles.test.mjs tests/bulletin_final.test.mjs`. La ampliación requiere reglas y ejemplos propios de cada indicador. El flujo Python de publicación oficial permanece separado.

EMOE incorpora ICE/IGOEC, cuatro sectores y veinte componentes, con ajustes propios y diferencias en puntos. Rechaza pedidos/tendencia. ENOE mensual conserva población por sexo, ocupación por sector y tasas originales/ajustadas nacionales/urbanas; valida enteros con espacios mediante sus diferencias e identidades. No recalcula diferencias desde tasas redondeadas.

BCMM lee los tres cuadros completos y las tasas/saldos ajustados del texto. El histórico usa columnas geométricas, incluidas notas al pie separadas por PDF.js; S.S. permanece nulo. Distingue flujos nominales, saldos, mes/acumulado y cuotas acumuladas no petroleras. Las salidas reales verificadas de los tres productos son Word de dos páginas con tablas editables y dos gráficas.
