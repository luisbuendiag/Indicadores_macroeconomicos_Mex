# Notas desde boletines recibidos

Disponible en IMAI, IGAE, IMOAM, EMIM, IMCP (CONSUMO) e IMFBCF mediante **Cargar boletín**. La selección y el arrastre de un único PDF se procesan dentro de la ficha, en un lector aislado del mismo sitio. Cuando la nota está lista se oculta la zona de carga; **Borrar archivo** restablece la selección y revoca la descarga temporal.

El archivo permanece en memoria del navegador. No hay cargas al servidor, almacenamiento, analítica ni llamadas a IA. No se alteran las cifras o notas oficiales del dashboard. Los PDF preliminares conservan su fecha declarada, incluso futura, y el Word identifica la versión recibida.

Cada módulo lee sus cuadros, verifica periodos y coteja la portada. IMAI e IGAE separan tasas ajustadas, originales y acumuladas; EMIM conserva las cuatro variables y valida los 21 subsectores originales; IMOAM presenta estimaciones originales con IC al 95%, sin inventar una base o variación mensual ajustada.

IMCP e IMFBCF leen los dos cuadros completos y mantienen la jerarquía de origen, durabilidad y comprador. Los agregados repetidos deben coincidir; las compras netas con NA se conservan como nulos. El Word presenta tasas ajustadas, originales y acumuladas, con dos visuales propios.

Se admiten archivos de hasta 20 MB con texto seleccionable: cinco páginas para IMAI, IGAE y EMIM; cuatro para IMOAM, IMCP e IMFBCF. El membrete vigente es de 2026. Cambios de estructura, datos ambiguos o controles fallidos detienen la generación. No se admite OCR.

Pruebas: `node --test tests/bulletin_upload.test.mjs tests/bulletin_products.test.mjs`. La ampliación requiere reglas y ejemplos propios de cada indicador. El flujo Python de publicación oficial permanece separado.
