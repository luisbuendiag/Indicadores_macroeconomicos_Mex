# Dependencias del generador local IMAI

- PDF.js 6.5.438: archivos `legacy/build/pdf.min.mjs` y `legacy/build/pdf.worker.min.mjs` de `pdfjs-dist` (npm oficial de Mozilla). Licencia Apache-2.0 en `pdfjs/LICENSE`. Ambos archivos deben actualizarse juntos y probarse contra un PDF IMAI real.
- fflate 0.8.3: `esm/browser.js` del paquete npm `fflate`. Licencia MIT en `fflate/LICENSE`.
- Fuente local: Noto Sans variable, `ofl/notosans/NotoSans[wdth,wght].ttf` del repositorio google/fonts. Licencia SIL OFL en `../fonts/OFL.txt`.

Estas copias locales evitan CDN y solicitudes a terceros durante el procesamiento.
