# Notas desde boletines recibidos

En la ficha IMAI, **Cargar boletín** abre un panel integrado en el dashboard. Permite seleccionar o arrastrar y soltar un único PDF. El lector se mantiene aislado dentro de un iframe del mismo sitio (`cargar-boletin.html?embedded=1`), conserva su CSP y se destruye al cerrar el panel. El piloto lee un PDF con texto seleccionable, cinco páginas y hasta 20 MB. Extrae el periodo, fecha declarada, índice base 2018 y cuadros ajustados y originales; presenta las cifras y prepara un Word editable con tres tablas y dos gráficas.

El PDF se procesa en memoria del navegador. No hay cargas, almacenamiento, analítica, llamadas a IA ni cambios en datos o notas oficiales. Las dependencias y la plantilla institucional se sirven desde el mismo sitio. Limpiar el archivo elimina la selección y revoca la descarga temporal. El Word identifica el resultado como documento de trabajo, no certifica publicación oficial.

La plantilla institucional vigente es de 2026: se rechazan otros años y estructuras no reconocidas. No se admite OCR, PDF escaneado ni otro indicador. La fecha declarada puede ser futura para permitir versiones preliminares. Si faltan cifras o no coinciden portada y cuadros, se detiene la generación. Antes de distribuir una nota debe revisarse contra el archivo recibido. Los PDF preliminares con una estructura distinta requieren validación y adaptación.

Pruebas: `node --test tests/bulletin_upload.test.mjs`. La ampliación a otros indicadores exige extractores, reglas y documentos de prueba propios; no basta habilitar el botón. El flujo Python de publicación oficial permanece separado.
