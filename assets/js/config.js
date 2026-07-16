// Configuración de presentación (paleta, KPIs, secciones). Módulo ES.
// Portado y ampliado del dashboard legado.

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

// Orden lógico de indicadores (base actual).
export const ORDER = ["PIB", "PIBSEC", "IGAE", "IMAI", "BALANZA", "IED", "DESOCUP", "INPC", "CONSUMO"];

export const LABELS = {
  PIB: "PIB", PIBSEC: "PIB Sectorial", IGAE: "IGAE", IMAI: "IMAI",
  CONSUMO: "Consumo Privado", IED: "IED", DESOCUP: "Tasa de desocupación",
  INPC: "INPC (Inflación)", BALANZA: "Balanza comercial",
  TIPOCAMBIO: "Tipo de cambio FIX", TASA: "Tasa objetivo Banxico",
};

// Configuración de KPI y semántica de variación por indicador.
export const KPICFG = {
  PIB: { valCol: 0, valFmt: "num", varCol: 1, varFmt: "pct-frac", varLabel: "Variación anual", noun: "PIB", art: "el", grupo: "growth", ctx: " (a precios de 2018)", vw: "crecimiento anual", vg: "m", comp: "frente al mismo periodo del año anterior", goodSign: 1 },
  PIBSEC: { derived: "total", valFmt: "num", varCol: 3, varFmt: "pct-frac", varLabel: "Var. trimestral (terciarias)", noun: "PIB total por actividad económica", art: "el", grupo: "growth", ctx: " (a precios de 2018)", vw: "variación trimestral en las actividades terciarias", vg: "f", comp: "frente al trimestre anterior", goodSign: 1 },
  IGAE: { valCol: 0, valFmt: "idx", varCol: null, varMode: "pct-prev", varLabel: "Variación mensual", noun: "IGAE", art: "el", grupo: "growth", ctx: " (índice base 2018=100)", vw: "variación mensual", vg: "f", comp: "frente al mes previo", goodSign: 1 },
  IMAI: { valCol: 0, valFmt: "idx", varCol: 1, varFmt: "pct-frac", varLabel: "Variación mensual", noun: "IMAI", art: "el", grupo: "growth", ctx: " (índice base 2018=100)", vw: "variación mensual", vg: "f", comp: "frente al mes previo", goodSign: 1 },
  CONSUMO: { valCol: 0, valFmt: "idx", varCol: 1, varFmt: "pct-frac", varLabel: "Variación mensual", noun: "consumo privado", art: "el", grupo: "growth", ctx: " (índice base 2018=100)", vw: "variación mensual", vg: "f", comp: "frente al mes previo", goodSign: 1 },
  IED: { valCol: 0, valFmt: "usd", varMode: "pct-yoy", varLabel: "Var. anual (vs. mismo trim. año previo)", noun: "IED total", art: "la", grupo: "growth", ctx: "", vw: "variación anual", vg: "f", comp: "frente al mismo trimestre del año anterior", goodSign: 1 },
  DESOCUP: { valCol: 0, valFmt: "pct-frac", varMode: "pp-prev", varLabel: "Variación vs. mes anterior", noun: "tasa de desocupación", art: "la", grupo: "desoc", ctx: "", vw: "variación", vg: "f", comp: "frente al mes previo", goodSign: -1 },
  INPC: { valCol: 0, valFmt: "pct-raw", varMode: "pp-prev", varLabel: "Variación vs. mes anterior", noun: "inflación general anual", art: "la", grupo: "inpc", ctx: "", vw: "variación", vg: "f", comp: "frente al mes previo", goodSign: -1 },
  BALANZA: { derived: "saldo", valFmt: "usd", varMode: "abs-prev", varLabel: "Variación del saldo", noun: "saldo de la balanza comercial", art: "el", grupo: "balanza", ctx: "", vw: "variación", vg: "f", comp: "frente al mes previo", goodSign: 1 },
  TIPOCAMBIO: { valCol: 0, valFmt: "idx", varMode: "pct-prev", varLabel: "Variación vs. periodo previo", noun: "tipo de cambio FIX", art: "el", grupo: "fx", ctx: " (pesos por dólar)", vw: "variación", vg: "f", comp: "frente al periodo previo", goodSign: 0 },
  TASA: { valCol: 0, valFmt: "pct-raw", varMode: "pp-prev", varLabel: "Variación vs. periodo previo", noun: "tasa objetivo", art: "la", grupo: "tasa", ctx: "", vw: "variación", vg: "f", comp: "frente al periodo previo", goodSign: 0 },
};

export const CAPTIONS = {
  PIB: "PIB a precios constantes (barras verdes, eje izquierdo) y su variación anual (línea oro, eje derecho).",
  PIBSEC: "Composición del PIB por actividad económica en barras apiladas y variación trimestral de terciarias (línea, eje derecho).",
  IGAE: "Índice global de volumen físico (línea verde) con el desglose de actividades secundarias —industria— (línea oro) y terciarias —servicios— (línea verde azulado), en índice base 2018=100.",
  IMAI: "Índice de volumen físico industrial (línea verde, eje izquierdo) y variación mensual (línea oro, eje derecho).",
  CONSUMO: "Índice de volumen físico del consumo privado (línea verde) y variación mensual (línea oro, eje derecho).",
  IED: "Componentes de la IED en barras apiladas y la IED total (línea punteada). Cifras en millones de dólares.",
  DESOCUP: "Tasa de desocupación mensual de México (línea oro) frente al promedio de desempleo de la OCDE (línea punteada vino, 4.9%). Porcentaje de la población económicamente activa.",
  INPC: "Inflación general, subyacente y no subyacente (variación anual en porcentaje).",
  BALANZA: "Exportaciones e importaciones (barras) y el saldo comercial (línea, eje derecho). Cifras en millones de dólares.",
};

// Secciones ejecutivas (Fase 6 del brief). Cada sección agrupa indicadores.
export const SECTIONS = [
  { id: "panorama", label: "Panorama ejecutivo", indicators: [] },
  { id: "actividad", label: "Actividad económica", indicators: ["PIB", "PIBSEC", "IGAE"] },
  { id: "industria", label: "Industria y manufactura", indicators: ["IMAI"] },
  { id: "comercio", label: "Comercio exterior", indicators: ["BALANZA"] },
  { id: "inversion", label: "Inversión", indicators: ["IED"] },
  { id: "mercado", label: "Mercado interno", indicators: ["CONSUMO", "DESOCUP"] },
  { id: "precios", label: "Precios y entorno financiero", indicators: ["INPC", "TIPOCAMBIO", "TASA"] },
  { id: "noticias", label: "Noticias y eventos", indicators: [] },
  { id: "calendario", label: "Calendario de publicaciones", indicators: [] },
  { id: "metodologia", label: "Fuentes y metodología", indicators: [] },
  { id: "descargas", label: "Descargas", indicators: [] },
];

// Ventanas temporales de visualización (decisión #6).
export const WINDOWS = [
  { id: "12m", label: "Últimos 12 meses", months: 12 },
  { id: "24m", label: "Últimos 24 meses", months: 24 },
  { id: "since_2018", label: "Desde 2018", from: new Date(2018, 0, 1) },
  { id: "max", label: "Máximo disponible", months: null },
];
