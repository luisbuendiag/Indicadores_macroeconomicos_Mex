// Configuración de presentación (paleta, indicadores, navegación). Módulo ES.
// V3: navegación por indicador, 11 principales + complementarios (entorno financiero).

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

// Los 11 indicadores principales (definición oficial de esta fase).
export const PRINCIPAL = ["PIB", "PIBSEC", "IGAE", "IMAI", "BCMM", "DESOCUP", "INPC", "CONSUMO", "IMFBCF", "IOAE", "EMIM"];

// Indicadores complementarios (no compiten en la navegación principal).
export const COMPLEMENTARIOS = ["IED", "TIPOCAMBIO", "TASA", "RESERVAS", "EMOE"];

// Orden lógico completo (principal + complementario).
export const ORDER = [...PRINCIPAL, ...COMPLEMENTARIOS];

// Etiqueta corta para navegación y tarjetas.
export const LABELS = {
  PIB: "PIB oportuno", PIBSEC: "PIB trimestral a precios constantes", IGAE: "IGAE", IMAI: "IMAI",
  BCMM: "Balanza comercial", DESOCUP: "Tasa de desocupación", INPC: "INPC",
  CONSUMO: "Consumo privado", IMFBCF: "Formación bruta de capital fijo",
  IOAE: "IOAE", EMIM: "EMIM",
  IED: "IED", TIPOCAMBIO: "Tipo de cambio FIX", TASA: "Tasa objetivo Banxico",
  RESERVAS: "Reservas internacionales", EMOE: "Confianza empresarial (EMOE)",
};

// Sigla oficial.
export const SIGLA = {
  PIB: "EOPIBT", PIBSEC: "PIBT", IGAE: "IGAE", IMAI: "IMAI",
  BCMM: "Balanza comercial", DESOCUP: "Tasa de desocupación", INPC: "INPC",
  CONSUMO: "IMCP", IMFBCF: "IMFBCF", IOAE: "IOAE", EMIM: "EMIM",
  IED: "IED", TIPOCAMBIO: "Tipo de cambio FIX", TASA: "Tasa objetivo", RESERVAS: "Reservas int.", EMOE: "EMOE",
};

// Configuración de KPI y semántica de variación por indicador.
// assess: cómo se evalúa el movimiento — "growth" (subir es favorable),
// "unemployment" (bajar es favorable), "neutral" (no se etiqueta avance/retroceso).
export const KPICFG = {
  PIB: { valCol: 0, valFmt: "pct-frac", varCol: 1, varFmt: "pct-frac", varLabel: "Var. anual desest.", yoyCol: 2, yoyFmt: "pct-frac", yoyLabel: "Var. anual original", noun: "PIB oportuno", art: "el", grupo: "growth", assess: "growth", ctx: "", vw: "variación trimestral desestacionalizada", vg: "f", comp: "frente al trimestre anterior", goodSign: 1 },
  PIBSEC: { valCol: 5, valFmt: "bill", varCol: 6, varFmt: "pct-frac", varLabel: "Var. trim. PIB", yoyCol: 7, yoyFmt: "pct-frac", yoyLabel: "Var. anual PIB", qoqLabel: "Trim.", yoyLabelShort: "Anual", noun: "Producto Interno Bruto Trimestral", art: "el", grupo: "growth", assess: "growth", ctx: " a precios constantes de 2018", vw: "nivel del PIB y variaciones trimestrales y anuales por actividad económica", vg: "m", comp: "frente al trimestre anterior", goodSign: 1 },
  IGAE: { valCol: 0, valFmt: "idx", varCol: 3, varFmt: "pct-frac", varLabel: "Var. mensual", yoyCol: 4, yoyFmt: "pct-frac", yoyLabel: "Var. anual", noun: "IGAE", art: "el", grupo: "growth", assess: "growth", ctx: " (índice base 2018=100)", vw: "variación mensual", vg: "f", comp: "frente al mes previo", goodSign: 1 },
  IMAI: { valCol: 0, valFmt: "idx", varCol: 1, varFmt: "pct-frac", varLabel: "Variación mensual", noun: "IMAI", art: "el", grupo: "growth", assess: "growth", ctx: " (índice base 2018=100)", vw: "variación mensual", vg: "f", comp: "frente al mes previo", goodSign: 1 },
  CONSUMO: { valCol: 0, valFmt: "idx", varCol: 1, varFmt: "pct-frac", varLabel: "Var. mensual", yoyCol: 2, yoyFmt: "pct-frac", yoyLabel: "Var. anual", noun: "consumo privado", art: "el", grupo: "growth", assess: "growth", ctx: " (índice base 2018=100)", vw: "variación mensual", vg: "f", comp: "frente al mes previo", goodSign: 1 },
  IMFBCF: { valCol: 0, valFmt: "idx", varCol: 1, varFmt: "pct-frac", varLabel: "Var. mensual", yoyCol: 2, yoyFmt: "pct-frac", yoyLabel: "Var. anual", noun: "formación bruta de capital fijo", art: "la", grupo: "growth", assess: "growth", ctx: " (índice base 2018=100)", vw: "variación mensual", vg: "f", comp: "frente al mes previo", goodSign: 1 },
  IOAE: { valCol: 0, valFmt: "pct-raw", varCol: 0, varFmt: "pct-raw", varLabel: "Estimación mensual", yoyCol: 1, yoyFmt: "pct-raw", yoyLabel: "Estimación anual", noun: "estimación oportuna de la actividad económica", art: "la", grupo: "growth", assess: "growth", ctx: " (variación mensual estimada)", vw: "estimación puntual", vg: "f", comp: "", goodSign: 1 },
  EMIM: { valCol: 0, valFmt: "idx", varCol: 1, varFmt: "pct-frac", varLabel: "Variación mensual", noun: "producción manufacturera", art: "la", grupo: "growth", assess: "growth", ctx: " (índice)", vw: "variación mensual", vg: "f", comp: "frente al mes previo", goodSign: 1 },
  DESOCUP: { valCol: 0, valFmt: "pct-frac", varMode: "pp-prev", varLabel: "Variación vs. mes anterior", noun: "tasa de desocupación", art: "la", grupo: "desoc", assess: "unemployment", ctx: "", vw: "variación", vg: "f", comp: "frente al mes previo", goodSign: -1 },
  INPC: { valCol: 0, valFmt: "pct-raw", varMode: "pp-prev", ppLong: true, varLabel: "Cambio de la inflación anual respecto al mes previo", noun: "inflación general anual", art: "la", grupo: "inpc", assess: "neutral", ctx: "", vw: "variación", vg: "f", comp: "frente al mes previo", goodSign: 0 },
  IED: { valCol: 0, valFmt: "usd", varMode: "pct-yoy", varLabel: "Var. anual (vs. mismo trim. año previo)", noun: "IED total", art: "la", grupo: "growth", assess: "growth", ctx: "", vw: "variación anual", vg: "f", comp: "frente al mismo trimestre del año anterior", goodSign: 1 },
  TIPOCAMBIO: { valCol: 0, valFmt: "fx", varMode: "pct-prev", varLabel: "Variación vs. periodo previo", noun: "tipo de cambio FIX", art: "el", grupo: "fx", assess: "neutral", ctx: " (pesos por dólar)", vw: "variación", vg: "f", comp: "frente al periodo previo", goodSign: 0 },
  TASA: { valCol: 0, valFmt: "pct-raw", varMode: "pp-prev", varLabel: "Variación vs. periodo previo", noun: "tasa objetivo", art: "la", grupo: "tasa", assess: "neutral", ctx: "", vw: "variación", vg: "f", comp: "frente al periodo previo", goodSign: 0 },
  RESERVAS: { valCol: 0, valFmt: "usd", varMode: "abs-prev", varLabel: "Variación semanal", noun: "reservas internacionales", art: "las", grupo: "growth", assess: "neutral", ctx: "", vw: "variación", vg: "f", comp: "frente al periodo previo", goodSign: 0 },
  EMOE: { valCol: 0, valFmt: "idx", varCol: 1, varFmt: "idx", varLabel: "Var. mensual", noun: "confianza empresarial", art: "la", grupo: "opinion", assess: "neutral", ctx: "", vw: "variación", vg: "f", comp: "frente al mes previo", goodSign: 0 },
  BCMM: { derived: "saldo", valFmt: "usd", varMode: "abs-prev", varLabel: "Variación mensual del saldo", noun: "saldo comercial", art: "el", grupo: "balanza", assess: "neutral", ctx: "", vw: "variación del saldo", vg: "f", comp: "frente al mes previo", goodSign: 0 },
};

export const CAPTIONS = {
  PIB: "Variación trimestral desestacionalizada del PIB oportuno (barras) y su variación anual desestacionalizada (línea). Ambas en porcentaje.",
  PIBSEC: "Niveles del PIB y las grandes actividades económicas (small multiples, arriba) y variaciones trimestrales y anuales agrupadas (abajo). Las variaciones a partir de 2021 provienen del boletín PIBT; antes se calculan a partir de los niveles originales.",
  IGAE: "Índice global de volumen físico (línea verde) con el desglose de actividades secundarias (línea oro) y terciarias (línea verde azulado), en índice base 2018=100.",
  IMAI: "Índice de volumen físico industrial (línea verde, eje izquierdo) y variación mensual (línea oro, eje derecho).",
  CONSUMO: "Índice de volumen físico del consumo privado (línea verde) y variación mensual (línea oro, eje derecho).",
  IMFBCF: "Índice de volumen físico de la formación bruta de capital fijo (inversión) y su variación mensual.",
  IOAE: "Estimación oportuna de la actividad económica con su intervalo de confianza, contrastada con el IGAE observado.",
  EMIM: "Producción, personal ocupado, horas trabajadas y remuneraciones de la industria manufacturera.",
  IED: "Componentes de la IED en barras apiladas y la IED total (línea punteada). Cifras en millones de dólares.",
  DESOCUP: "Tasa de desocupación mensual de México como porcentaje de la población económicamente activa.",
  INPC: "Inflación general, subyacente y no subyacente (variación anual en porcentaje).",
  TIPOCAMBIO: "Tipo de cambio FIX (pesos por dólar).",
  TASA: "Tasa de interés objetivo del Banco de México (%).",
  RESERVAS: "Reservas internacionales netas (millones de dólares).",
  EMOE: "Confianza empresarial (EMOE) y su variación mensual (puntos).",
  BCMM: "Exportaciones, importaciones y saldo de la balanza comercial de mercancías (millones de dólares)."
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

// Estados de actualización permitidos (para presentación y mapeo de estilos).
export const ESTADOS = {
  "ACTUALIZADO": { cls: "ok", short: "Actualizado" },
  "PUBLICACIÓN PENDIENTE": { cls: "pending", short: "Publicación pendiente" },
  "REZAGADO": { cls: "lag", short: "Rezagado" },
  "ERROR DE FUENTE": { cls: "error", short: "Error de fuente" },
};
