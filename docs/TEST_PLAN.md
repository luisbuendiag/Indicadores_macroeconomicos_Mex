# Test plan — Tablero ejecutivo V2 (E2E)

Target: `http://localhost:8099/index.html` (código mergeado en `main` del fork).
Evidencia de código: `assets/js/app.js` L349, L408 (descarga Excel), L205-206/L368 (ventana temporal → `buildOption`), `renderPortada`/`renderNews`/`renderCalendar`.

## T1 — Portada ejecutiva carga en <2 min con panorama completo
Acción: abrir el sitio; observar la portada.
Pass: se ven fecha de última actualización ("16 de julio de 2026"), periodo de referencia ("mayo de 2026"), 9 tarjetas KPI con valor+variación+semáforo, bloque "Resumen ejecutivo" con etiquetas HECHO/INTERPRETACIÓN, "Próximo dato por publicarse" y botón "Descargar Excel actualizado".
Fail si: faltan tarjetas, el resumen está vacío o no hay botón de Excel.

## T2 — Navegación por secciones + ECharts renderiza
Acción: clic en pestaña "Actividad económica".
Pass: se dibuja la gráfica del PIB (barras verdes + línea oro, doble eje) dentro de un `<canvas>`; se ven KPIs (Último dato 24,973,976; Máx/Mín) y el panel "Información del indicador".
Fail si: el contenedor de la gráfica queda vacío/gris o no cambia la sección.

## T3 — Ventana temporal cambia la gráfica (adversarial)
Acción: en la gráfica del PIB, clic "Últimos 12 meses"; luego "Máximo disponible".
Pass: el número de barras del eje X **disminuye visiblemente** con "Últimos 12 meses" (≤ ~4 trimestres) y **aumenta** con "Máximo disponible" (toda la serie, ~21 puntos). El botón activo queda marcado (`aria-pressed`).
Fail si: la gráfica no cambia entre ambas ventanas (indicaría que `applyWindow` no filtra).

## T4 — Descarga del Excel funciona
Acción: volver a Panorama; clic "Descargar Excel actualizado".
Pass: el navegador descarga `Indicadores_Macroeconomicos_Mexico_Actualizado.xlsx`. Verificación fuera de UI: el archivo abre con 13 hojas (10 originales + Resumen ejecutivo, Metodología y fuentes, Control de actualizaciones).
Fail si: no se descarga nada o el archivo no tiene las 3 hojas nuevas.

## T5 — Secciones modulares: Noticias, Calendario, Metodología, Descargas
Acción: clic en "Noticias y eventos", "Calendario de publicaciones", "Descargas".
Pass: Noticias muestra el piloto con referencias oficiales (título/fuente/categoría/enlace) y una nota de que es piloto; Calendario muestra la tabla de publicaciones; Descargas lista el Excel + JSON/CSV. Ninguna sección rompe el dashboard.
Fail si: alguna sección lanza error en consola que impide el render del resto.

## Regresión (etiquetar como tal)
- Fuente de "Tasa de desocupación" dice INEGI/ENOE (no OCDE) en la tarjeta.
