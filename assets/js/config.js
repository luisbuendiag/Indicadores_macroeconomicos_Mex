// Configuración de presentación (paleta, indicadores, navegación). Módulo ES.
// V3: Panorama macroeconómico (14 principales) + Entorno financiero (3 complementarios).

export const COLORS = {
  GREEN: "#1e5b4f",
  DKGREEN: "#002f2a",
  GOLD: "#a57f2c",
  CRIMSON: "#9b2247",
  WINE: "#611232",
  TEAL: "#1f7a6b",
  LTGREEN: "#7fa394",
  GRAY: "#98989a",
  INK: "#161a1d",
};

// Indicadores principales del Panorama macroeconómico.
export const PRINCIPAL = ["PIB", "PIBSEC", "IOAE", "IGAE", "IMAI", "EMIM", "EMOE", "DESOCUP", "INPC", "INPP", "CONSUMO", "IMFBCF", "IED", "BCMM"];

// Indicadores complementarios del Entorno financiero (Banco de México).
export const COMPLEMENTARIOS = ["TIPOCAMBIO", "TASA", "RESERVAS"];

// Orden lógico completo (principal + complementario).
export const ORDER = [...PRINCIPAL, ...COMPLEMENTARIOS];

// Etiqueta corta para navegación y tarjetas.
export const LABELS = {
  PIB: "PIB oportuno", PIBSEC: "PIB trimestral a precios constantes", IGAE: "IGAE", IMAI: "IMAI",
  BCMM: "Balanza comercial", DESOCUP: "Indicadores de ocupación y empleo", INPC: "INPC",
  INPP: "Índice Nacional de Precios Productor",
  CONSUMO: "Consumo privado", IMFBCF: "Formación bruta de capital fijo",
  IOAE: "IOAE", EMIM: "EMIM", EMOE: "Encuesta Mensual de Opinión Empresarial",
  IED: "Inversión Extranjera Directa", TIPOCAMBIO: "Tipo de cambio FIX", TASA: "Tasa objetivo de Banco de México",
  RESERVAS: "Reservas internacionales",
};

// Sigla oficial. Si una clave no tiene sigla corta, se usa la clave.
export const SIGLA = {
  PIB: "PIB", PIBSEC: "PIBT", IGAE: "IGAE", IMAI: "IMAI",
  BCMM: "BCMM", DESOCUP: "ENOE", INPC: "INPC",
  INPP: "INPP",
  CONSUMO: "IMCP", IMFBCF: "IMFBCF", IOAE: "IOAE", EMIM: "EMIM", EMOE: "EMOE",
  IED: "IED", TIPOCAMBIO: "FIX", TASA: "TASA OBJETIVO", RESERVAS: "RESERVAS",
};

// Configuración de KPI y semántica de variación por indicador.
// assess: cómo se evalúa el movimiento — "growth" (subir es favorable),
// "unemployment" (bajar es favorable), "neutral" (no se etiqueta avance/retroceso).
export const KPICFG = {
  PIB: { valCol: 0, valFmt: "pct-frac", varCol: 1, varFmt: "pct-frac", varLabel: "Var. anual desest.", yoyCol: 2, yoyFmt: "pct-frac", yoyLabel: "Var. anual original", mainLabel: "Var. trimestral desest.", noun: "PIB oportuno", art: "el", grupo: "growth", assess: "growth", ctx: "", vw: "variación trimestral desestacionalizada", vg: "f", comp: "frente al trimestre anterior", goodSign: 1 },
  PIBSEC: { valCol: 5, valFmt: "bill", varCol: 6, varFmt: "pct-frac", varLabel: "Var. trim. PIB", yoyCol: 7, yoyFmt: "pct-frac", yoyLabel: "Var. anual PIB", mainLabel: "Nivel del PIB", qoqLabel: "Trim.", yoyLabelShort: "Anual", noun: "Producto Interno Bruto Trimestral", art: "el", grupo: "growth", assess: "growth", ctx: " a precios constantes de 2018", vw: "nivel del PIB y variaciones trimestrales y anuales por actividad económica", vg: "m", comp: "frente al trimestre anterior", goodSign: 1 },
  IGAE: { valCol: 0, valFmt: "idx", varCol: 1, varFmt: "pct-frac", varLabel: "Var. mensual desest.", yoyCol: 2, yoyFmt: "pct-frac", yoyLabel: "Var. anual original", mainLabel: "Índice", noun: "Indicador Global de la Actividad Económica", art: "el", grupo: "growth", assess: "growth", ctx: " (índice base 2018=100)", vw: "variación mensual desestacionalizada", vg: "f", comp: "frente al mes previo", goodSign: 1 },
  IMAI: { valCol: 0, valFmt: "idx", varCol: 1, varFmt: "pct-frac", varLabel: "Var. mensual desest.", yoyCol: 2, yoyFmt: "pct-frac", yoyLabel: "Var. anual desest.", mainLabel: "Índice", acumCol: 5, acumFmt: "pct-frac", acumLabel: "Acumulado ene-mes", noun: "Indicador Mensual de la Actividad Industrial", art: "el", grupo: "growth", assess: "growth", ctx: " (índice base 2018=100)", vw: "variación mensual desestacionalizada", vg: "m", comp: "frente al mes previo", goodSign: 1 },
  CONSUMO: { valCol: 0, valFmt: "idx", varCol: 1, varFmt: "pct-frac", varLabel: "Var. mensual desest.", yoyCol: 2, yoyFmt: "pct-frac", yoyLabel: "Var. anual desest.", acumCol: 4, acumFmt: "pct-frac", acumLabel: "Acumulado ene-mes", mainLabel: "Índice", noun: "consumo privado", art: "el", grupo: "growth", assess: "growth", ctx: " (índice base 2018=100)", vw: "variación mensual desestacionalizada", vg: "f", comp: "frente al mes previo", goodSign: 1 },
  IMFBCF: { valCol: 0, valFmt: "idx", varCol: 1, varFmt: "pct-frac", varLabel: "Var. mensual desest.", yoyCol: 2, yoyFmt: "pct-frac", yoyLabel: "Var. anual desest.", acumCol: 27, acumFmt: "pct-frac", acumLabel: "Acumulado ene-mes", mainLabel: "Índice", noun: "formación bruta de capital fijo", art: "la", grupo: "growth", assess: "growth", ctx: " (índice base 2018=100)", vw: "variación mensual desestacionalizada", vg: "f", comp: "frente al mes previo", goodSign: 1 },
  IOAE: { valCol: 0, valFmt: "pct-frac", varCol: 3, varFmt: "pct-frac", varLabel: "Var. mensual estimada", yoyCol: 12, yoyFmt: "pct-frac", yoyLabel: "IGAE observado", mainLabel: "Nowcast anual del IGAE", noun: "indicador oportuno de la actividad económica", art: "el", grupo: "growth", assess: "growth", ctx: " (variación anual estimada con intervalo de confianza al 95%)", vw: "variación mensual estimada", vg: "m", comp: "frente al mes previo", goodSign: 1 },
  EMIM: { valCol: 0, valFmt: "idx", varCol: 3, varFmt: "pct-frac", varLabel: "Var. mensual desest.", yoyCol: 4, yoyFmt: "pct-frac", yoyLabel: "Var. anual desest.", mainLabel: "Producción", origMomCol: 1, origYoyCol: 2, noun: "Encuesta Mensual de la Industria Manufacturera", art: "la", grupo: "growth", assess: "growth", ctx: " (índice base 2018=100)", vw: "variación mensual desestacionalizada", vg: "f", comp: "frente al mes previo", goodSign: 1 },
  DESOCUP: { valCol: 0, valFmt: "pct-raw", varMode: "pp-prev", varLabel: "Cambio mensual", yoyMode: "pp-yoy", yoyLabel: "Cambio anual", mainLabel: "Tasa de desocupación", noun: "tasa de desocupación", art: "la", grupo: "desoc", assess: "unemployment", ctx: "", vw: "variación", vg: "f", comp: "frente al mes previo", goodSign: -1 },
  INPC: { valCol: 2, valFmt: "pct-raw", varMode: "pp-prev", ppLong: true, varLabel: "Cambio de la inflación anual respecto al mes previo", mainLabel: "Inflación anual", noun: "inflación general anual", art: "la", grupo: "inpc", assess: "neutral", ctx: "", vw: "variación", vg: "f", comp: "frente al mes previo", goodSign: 0 },
  INPP: { valCol: 2, valFmt: "pct-raw", varCol: 1, varFmt: "pct-raw", varLabel: "Var. mensual", yoyCol: 2, yoyFmt: "pct-raw", yoyLabel: "Var. anual", mainLabel: "Variación anual", noun: "Índice Nacional de Precios Productor", art: "el", grupo: "inpc", assess: "neutral", ctx: "", vw: "variación anual", vg: "f", comp: "frente al mes previo", goodSign: 0 },
  IED: { valCol: 0, valFmt: "usd", varCol: 4, varFmt: "pct-frac", varLabel: "Var. anual del acumulado", mainLabel: "IED acumulada en el año", noun: "IED acumulada", art: "la", grupo: "growth", assess: "growth", ctx: " (acumulado ene-jun, millones de dólares)", vw: "variación anual", vg: "f", comp: "frente al mismo periodo del año anterior", goodSign: 1, flowLabel: "Flujo del 2T" },
  TIPOCAMBIO: { valCol: 0, valFmt: "fx", varMode: "pct-prev", varLabel: "Cambio diario", yoyLabel: "Cambio anual", mainLabel: "Tipo de cambio FIX", noun: "tipo de cambio FIX", art: "el", grupo: "fx", assess: "neutral", ctx: " (pesos por dólar)", vw: "variación diaria", vg: "f", comp: "frente al día hábil previo", goodSign: 0 },
  TASA: { valCol: 0, valFmt: "pct-raw", varMode: "pp-prev", varLabel: "Último ajuste", yoyLabel: "Fecha del último ajuste", mainLabel: "Tasa objetivo", noun: "tasa objetivo", art: "la", grupo: "tasa", assess: "neutral", ctx: " (% anual). No confundir con la TIIE.", vw: "cambio de política monetaria", vg: "f", comp: "en la última decisión", goodSign: 0 },
  RESERVAS: { valCol: 0, valFmt: "usd", varMode: "abs-prev", varLabel: "Var. semanal", yoyLabel: "Var. anual", mainLabel: "Reservas internacionales", noun: "reservas internacionales", art: "las", grupo: "growth", assess: "neutral", ctx: " (millones de dólares)", vw: "variación semanal", vg: "f", comp: "frente a la semana previa", goodSign: 0 },
  EMOE: { valCol: 0, valFmt: "idx", varCol: 1, varFmt: "emoe", varLabel: "Cambio mensual", yoyCol: 2, yoyFmt: "emoe", yoyLabel: "Cambio anual", mainLabel: "IGOEC", noun: "IGOEC", art: "el", grupo: "opinion", assess: "neutral", ctx: "umbral de referencia=50", vw: "cambio mensual", vg: "f", comp: "frente al mes previo", goodSign: 0, umbral: 50, unit: "puntos" },
  BCMM: { valCol: 2, valFmt: "usd", varCol: 2, varFmt: "usd", varLabel: "Variación mensual del saldo", yoyCol: 5, yoyFmt: "pct-frac", yoyLabel: "Var. anual saldo", mainLabel: "Saldo comercial", derived: "saldo", noun: "saldo comercial", art: "el", grupo: "balanza", assess: "neutral", ctx: "", vw: "variación anual", vg: "m", comp: "frente al mismo mes del año anterior", goodSign: 0 },
};

export const CAPTIONS = {
  PIB: "Variación trimestral desestacionalizada del PIB oportuno (barras) y su variación anual desestacionalizada (línea). Ambas en porcentaje.",
  PIBSEC: "Niveles del PIB y las grandes actividades económicas (small multiples, arriba) y variaciones trimestrales y anuales agrupadas (abajo). Las variaciones a partir de 2021 provienen del boletín PIBT; antes se calculan a partir de los niveles originales.",
  IGAE: "Niveles del IGAE y actividades primarias, secundarias y terciarias (small multiples, arriba) y variación anual original agrupada (abajo). La variación mensual desestacionalizada proviene del boletín oficial.",
  IMAI: "Niveles desestacionalizados del IMAI y sus cuatro sectores (small multiples, arriba) y variaciones mensuales y anuales desestacionalizadas agrupadas (abajo). Las variaciones del mes más reciente provienen del boletín oficial.",
  CONSUMO: "Índice de volumen físico del consumo privado (línea verde), variación mensual desestacionalizada (línea guinda) y variación anual desestacionalizada (línea oro), ambas en eje derecho.",
  IMFBCF: "Niveles desestacionalizados del IMFBCF y sus componentes (construcción, maquinaria y equipo, nacional e importado; small multiples, arriba) y variaciones mensuales y anuales agrupadas (abajo). Las variaciones del mes más reciente provienen del boletín oficial; las series históricas se obtienen de Banco de México (SIE).",
  IOAE: "Nowcast anual del IGAE con intervalo de confianza al 95%, variación mensual estimada y contraste con el IGAE observado una vez publicado.",
  EMIM: "Evolución de la producción, personal ocupado, horas trabajadas y remuneraciones medias reales de la industria manufacturera. Las variaciones históricas son cifras originales calculadas a partir de los índices BIE; las desestacionalizadas provienen del boletín oficial para el mes más reciente.",
  IED: "Acumulado anual de inversión extranjera directa, flujo exclusivo del trimestre y componentes. Incluye desgloses por tipo de inversión, país de origen, sector económico y entidad federativa.",
  DESOCUP: "Indicadores del mercado laboral: tasa de desocupación, participación, informalidad y subocupación (mensuales), más población ocupada (trimestral). Fuente: ENOE/BIE.",
  INPC: "Inflación general, subyacente, no subyacente y componentes: índices, variaciones mensuales, inflaciones anuales e incidencias mensuales en puntos porcentuales.",
  INPP: "Precios productor con y sin petróleo, bienes intermedios, actividades primarias y subsectores: índices y variaciones mensuales, anuales y acumuladas.",
  TIPOCAMBIO: "Tipo de cambio FIX (pesos por dólar).",
  TASA: "Objetivo para la Tasa de Interés Interbancaria a un día (tasa objetivo) fijado por la Junta de Gobierno de Banco de México. No confundir con la TIIE de fondeo ni con las TIIE a 28, 91 o 182 días.",
  RESERVAS: "Reservas internacionales netas (millones de dólares).",
  EMOE: "Indicador Global de Opinión Empresarial de Confianza (IGOEC) y su cambio mensual y anual en puntos. Línea de referencia en 50 puntos. Desglose sectorial: Manufacturas, Construcción, Comercio y Servicios privados no financieros.",
  BCMM: "Exportaciones, importaciones y saldo comercial de mercancías de México (millones de dólares). Incluye desglose petrolero/no petrolero, por tipo de bien importado y composición de las exportaciones no petroleras, además de sus variaciones anuales y acumulados ene-mes."
};

// Vistas de navegación. type: "home" | "indicator" | "group" | "page".
export const VIEWS = [
  { id: "panorama", type: "home", label: "Panorama macroeconómico" },
  ...ORDER.map((k) => ({ id: k, type: "indicator", key: k, label: LABELS[k] })),
  { id: "entorno", type: "page", label: "Entorno financiero", indicators: COMPLEMENTARIOS, secondary: true },
  { id: "calendario", type: "page", label: "Calendario de publicaciones", secondary: true },
  { id: "metodologia", type: "page", label: "Fuentes y metodología", secondary: true },
  { id: "descargas", type: "page", label: "Descargas", secondary: true },
];

// Ventanas temporales de visualización.
export const WINDOWS = [
  { id: "3m", label: "3 meses", months: 3 },
  { id: "6m", label: "6 meses", months: 6 },
  { id: "1a", label: "1 año", months: 12 },
  { id: "5a", label: "5 años", months: 60 },
  { id: "max", label: "Máximo", months: null },
];

// Ventanas especiales para IED: acumulado comparable (años) y flujo trimestral.
export const IED_WINDOWS = [
  { id: "5a", label: "5 años", count: 5 },
  { id: "10a", label: "10 años", count: 10 },
  { id: "max", label: "Máximo", count: null },
];
export const IED_WINDOWS_FLUJO = [
  { id: "1a", label: "1 año", count: 4 },
  { id: "3a", label: "3 años", count: 12 },
  { id: "5a", label: "5 años", count: 20 },
  { id: "max", label: "Máximo", count: null },
];

// Estados de actualización permitidos (para presentación y mapeo de estilos).
export const ESTADOS = {
  "ACTUALIZADO": { cls: "ok", short: "Actualizado" },
  "PUBLICACIÓN PENDIENTE": { cls: "pending", short: "Publicación pendiente" },
  "REZAGADO": { cls: "lag", short: "Rezagado" },
  "ERROR DE FUENTE": { cls: "error", short: "Error de fuente" },
};
