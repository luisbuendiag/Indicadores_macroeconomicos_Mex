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
export const PRINCIPAL = ["PIB", "PIBSEC", "IGAE", "IMAI", "BALANZA", "DESOCUP", "INPC", "CONSUMO", "IMFBCF", "IOAE", "EMIM"];

// Indicadores complementarios (no compiten en la navegación principal).
export const COMPLEMENTARIOS = ["IED", "TIPOCAMBIO", "TASA", "RESERVAS"];

// Orden lógico completo (principal + complementario).
export const ORDER = [...PRINCIPAL, ...COMPLEMENTARIOS];

// Etiqueta corta para navegación y tarjetas.
export const LABELS = {
  PIB: "PIB", PIBSEC: "PIB por actividad económica", IGAE: "IGAE", IMAI: "IMAI",
  BALANZA: "Balanza comercial", DESOCUP: "Tasa de desocupación", INPC: "INPC",
  CONSUMO: "Consumo privado", IMFBCF: "Formación bruta de capital fijo",
  IOAE: "IOAE", EMIM: "EMIM",
  IED: "IED", TIPOCAMBIO: "Tipo de cambio FIX", TASA: "Tasa objetivo Banxico",
  RESERVAS: "Reservas internacionales",
};

// Sigla oficial.
export const SIGLA = {
  PIB: "PIB", PIBSEC: "PIB por actividad económica", IGAE: "IGAE", IMAI: "IMAI",
  BALANZA: "Balanza comercial", DESOCUP: "Tasa de desocupación", INPC: "INPC",
  CONSUMO: "IMCP", IMFBCF: "IMFBCF", IOAE: "IOAE", EMIM: "EMIM",
  IED: "IED", TIPOCAMBIO: "Tipo de cambio FIX", TASA: "Tasa objetivo", RESERVAS: "Reservas int.",
};

// Configuración de KPI y semántica de variación por indicador.
// assess: cómo se evalúa el movimiento — "growth" (subir es favorable),
// "unemployment" (bajar es favorable), "neutral" (no se etiqueta avance/retroceso).
export const KPICFG = {
  PIB: { valCol: 0, valFmt: "num", varCol: 1, varFmt: "pct-frac", varLabel: "Variación anual", noun: "PIB", art: "el", grupo: "growth", assess: "growth", ctx: " (a precios de 2018)", vw: "crecimiento anual", vg: "m", comp: "frente al mismo trimestre del año anterior", goodSign: 1 },
  PIBSEC: { derived: "total", valFmt: "num", varCol: 3, varFmt: "pct-frac", varLabel: "Var. trimestral (terciarias)", noun: "PIB total por actividad económica", art: "el", grupo: "growth", assess: "growth", ctx: " (a precios de 2018)", vw: "variación trimestral en las actividades terciarias", vg: "f", comp: "frente al trimestre anterior", goodSign: 1 },
  IGAE: { valCol: 0, valFmt: "idx", varCol: null, varMode: "pct-prev", varLabel: "Variación mensual", noun: "IGAE", art: "el", grupo: "growth", assess: "growth", ctx: " (índice base 2018=100)", vw: "variación mensual", vg: "f", comp: "frente al mes previo", goodSign: 1 },
  IMAI: { valCol: 0, valFmt: "idx", varCol: 1, varFmt: "pct-frac", varLabel: "Variación mensual", noun: "IMAI", art: "el", grupo: "growth", assess: "growth", ctx: " (índice base 2018=100)", vw: "variación mensual", vg: "f", comp: "frente al mes previo", goodSign: 1 },
  CONSUMO: { valCol: 0, valFmt: "idx", varCol: 1, varFmt: "pct-frac", varLabel: "Variación mensual", noun: "consumo privado", art: "el", grupo: "growth", assess: "growth", ctx: " (índice base 2018=100)", vw: "variación mensual", vg: "f", comp: "frente al mes previo", goodSign: 1 },
  IMFBCF: { valCol: 0, valFmt: "idx", varCol: 1, varFmt: "pct-frac", varLabel: "Variación mensual", noun: "formación bruta de capital fijo", art: "la", grupo: "growth", assess: "growth", ctx: " (índice base 2018=100)", vw: "variación mensual", vg: "f", comp: "frente al mes previo", goodSign: 1 },
  IOAE: { valCol: 0, valFmt: "pct-raw", varMode: "pp-prev", varLabel: "Estimación puntual mensual", noun: "estimación oportuna de la actividad económica", art: "la", grupo: "growth", assess: "growth", ctx: " (variación mensual estimada)", vw: "estimación puntual", vg: "f", comp: "frente al mes previo", goodSign: 1 },
  EMIM: { valCol: 0, valFmt: "idx", varCol: 1, varFmt: "pct-frac", varLabel: "Variación mensual", noun: "producción manufacturera", art: "la", grupo: "growth", assess: "growth", ctx: " (índice)", vw: "variación mensual", vg: "f", comp: "frente al mes previo", goodSign: 1 },
  DESOCUP: { valCol: 0, valFmt: "pct-frac", varMode: "pp-prev", varLabel: "Variación vs. mes anterior", noun: "tasa de desocupación", art: "la", grupo: "desoc", assess: "unemployment", ctx: "", vw: "variación", vg: "f", comp: "frente al mes previo", goodSign: -1 },
  INPC: { valCol: 0, valFmt: "pct-raw", varMode: "pp-prev", varLabel: "Variación anual vs. mes anterior", noun: "inflación general anual", art: "la", grupo: "inpc", assess: "neutral", ctx: "", vw: "variación", vg: "f", comp: "frente al mes previo", goodSign: 0 },
  BALANZA: { derived: "saldo", valFmt: "usd", varMode: "abs-prev", varLabel: "Variación del saldo (mensual)", noun: "saldo de la balanza comercial", art: "el", grupo: "balanza", assess: "neutral", ctx: "", vw: "variación del saldo", vg: "f", comp: "frente al mes previo", goodSign: 0 },
  IED: { valCol: 0, valFmt: "usd", varMode: "pct-yoy", varLabel: "Var. anual (vs. mismo trim. año previo)", noun: "IED total", art: "la", grupo: "growth", assess: "growth", ctx: "", vw: "variación anual", vg: "f", comp: "frente al mismo trimestre del año anterior", goodSign: 1 },
  TIPOCAMBIO: { valCol: 0, valFmt: "fx", varMode: "pct-prev", varLabel: "Variación vs. periodo previo", noun: "tipo de cambio FIX", art: "el", grupo: "fx", assess: "neutral", ctx: " (pesos por dólar)", vw: "variación", vg: "f", comp: "frente al periodo previo", goodSign: 0 },
  TASA: { valCol: 0, valFmt: "pct-raw", varMode: "pp-prev", varLabel: "Variación vs. periodo previo", noun: "tasa objetivo", art: "la", grupo: "tasa", assess: "neutral", ctx: "", vw: "variación", vg: "f", comp: "frente al periodo previo", goodSign: 0 },
  RESERVAS: { valCol: 0, valFmt: "usd", varMode: "abs-prev", varLabel: "Variación semanal", noun: "reservas internacionales", art: "las", grupo: "growth", assess: "neutral", ctx: "", vw: "variación", vg: "f", comp: "frente al periodo previo", goodSign: 0 },
};

export const CAPTIONS = {
  PIB: "PIB a precios constantes (barras verdes, eje izquierdo) y su variación anual (línea oro, eje derecho).",
  PIBSEC: "Composición del PIB por actividad económica en barras apiladas y variación trimestral de terciarias (línea, eje derecho).",
  IGAE: "Índice global de volumen físico (línea verde) con el desglose de actividades secundarias (línea oro) y terciarias (línea verde azulado), en índice base 2018=100.",
  IMAI: "Índice de volumen físico industrial (línea verde, eje izquierdo) y variación mensual (línea oro, eje derecho).",
  CONSUMO: "Índice de volumen físico del consumo privado (línea verde) y variación mensual (línea oro, eje derecho).",
  IMFBCF: "Índice de volumen físico de la formación bruta de capital fijo (inversión) y su variación mensual.",
  IOAE: "Estimación oportuna de la actividad económica con su intervalo de confianza, contrastada con el IGAE observado.",
  EMIM: "Producción, personal ocupado, horas trabajadas y remuneraciones de la industria manufacturera.",
  IED: "Componentes de la IED en barras apiladas y la IED total (línea punteada). Cifras en millones de dólares.",
  DESOCUP: "Tasa de desocupación mensual de México como porcentaje de la población económicamente activa.",
  INPC: "Inflación general, subyacente y no subyacente (variación anual en porcentaje).",
  BALANZA: "Exportaciones e importaciones (barras) y el saldo comercial (línea, eje derecho). Cifras en millones de dólares.",
  TIPOCAMBIO: "Tipo de cambio FIX (pesos por dólar).",
  TASA: "Tasa de interés objetivo del Banco de México (%).",
  RESERVAS: "Reservas internacionales netas (millones de dólares).",
};

// Vistas de navegación. type: "home" | "indicator" | "group" | "page".
export const VIEWS = [
  { id: "panorama", type: "home", label: "Panorama macroeconómico" },
  ...PRINCIPAL.map((k) => ({ id: k, type: "indicator", key: k, label: LABELS[k] })),
  { id: "entorno", type: "group", label: "Entorno financiero", indicators: COMPLEMENTARIOS, secondary: true },
  { id: "calendario", type: "page", label: "Calendario de publicaciones", secondary: true },
  { id: "metodologia", type: "page", label: "Fuentes y metodología", secondary: true },
  { id: "descargas", type: "page", label: "Descargas", secondary: true },
];

// Ventanas temporales de visualización.
export const WINDOWS = [
  { id: "12m", label: "Últimos 12 meses", months: 12 },
  { id: "24m", label: "Últimos 24 meses", months: 24 },
  { id: "since_2018", label: "Desde 2018", from: new Date(2018, 0, 1) },
  { id: "max", label: "Máximo disponible", months: null },
];

// Estados de actualización permitidos (para presentación y mapeo de estilos).
export const ESTADOS = {
  "actualizado automáticamente": { cls: "ok", short: "Actualizado" },
  "dato de respaldo vigente": { cls: "backup", short: "Dato de respaldo" },
  "pendiente de token": { cls: "pending", short: "Pendiente de token" },
  "pendiente de confirmar serie": { cls: "pending", short: "Serie por confirmar" },
  "error de fuente": { cls: "error", short: "Error de fuente" },
  "dato en revisión": { cls: "review", short: "En revisión" },
  "actualización parcial": { cls: "partial", short: "Actualización parcial" },
  "no disponible": { cls: "na", short: "No disponible" },
};
