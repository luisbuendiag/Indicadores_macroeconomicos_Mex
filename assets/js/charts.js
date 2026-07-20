// Construcción de gráficas con ECharts, replicando la identidad visual sobria.
import { COLORS, WINDOWS } from "./config.js";
import { periodToDate } from "./format.js";

const G = COLORS.GREEN, Go = COLORS.GOLD, S = COLORS.WINE, LG = COLORS.LTGREEN, INK = COLORS.INK, TEAL = COLORS.TEAL;

// Filtra las observaciones de un indicador según la ventana temporal.
export function applyWindow(ind, windowId) {
  const win = WINDOWS.find((w) => w.id === windowId) || WINDOWS[2];
  let obs = ind.observations;
  if (win.id === "max") return obs;
  if (win.months) {
    obs = obs.slice(-win.months);
  } else if (win.from) {
    obs = obs.filter((o) => { const d = periodToDate(o.period); return !d || d >= win.from; });
    if (!obs.length) obs = ind.observations; // resguardo: no dejar vacío
  }
  return obs;
}

// Devuelve una especificación neutral a partir del indicador (obs filtradas).
function chartSpec(ind, obs) {
  const P = obs.map((o) => o.period);
  const col = (i) => obs.map((o) => o.values[i] ?? null);
  const totalSec = obs.map((o) => { const [a, b, c] = o.values; return (a == null && b == null && c == null) ? null : (a || 0) + (b || 0) + (c || 0); });
  const saldo = obs.map((o) => (o.values[0] != null && o.values[1] != null) ? o.values[0] - o.values[1] : null);
  switch (ind.key) {
    case "PIB": return { periods: P, bars: [{ name: "PIB (millones de pesos)", values: col(0), color: G }], lines: [{ name: "Var. anual (%)", values: col(1).map((v) => v == null ? null : v * 100), color: Go, axis: "right" }], leftName: "Millones de pesos", rightName: "Var. anual (%)", leftFmt: "compact", rightFmt: "pct" };
    case "PIBSEC": return { periods: P, stack: "pib", bars: [{ name: "Primarias", values: col(0), color: LG }, { name: "Secundarias", values: col(1), color: Go }, { name: "Terciarias", values: col(2), color: G }], lines: [{ name: "Var. trim. terciarias (%)", values: col(3).map((v) => v == null ? null : v * 100), color: S, axis: "right" }], leftName: "Millones de pesos", rightName: "Var. trim. (%)", leftFmt: "compact", rightFmt: "pct" };
    case "IGAE": return { periods: P, lines: [{ name: "Índice global", values: col(0), color: G }, { name: "Act. secundarias", values: col(1), color: Go }, { name: "Act. terciarias", values: col(2), color: TEAL }], leftName: "Índice (2018=100)", leftFmt: "idx" };
    case "IMAI": return { periods: P, lines: [{ name: "Índice de volumen físico", values: col(0), color: G }, { name: "Var. mensual (%)", values: col(1).map((v) => v == null ? null : v * 100), color: Go, axis: "right" }], leftName: "Índice (2018=100)", rightName: "Var. mensual (%)", leftFmt: "idx", rightFmt: "pct" };
    case "CONSUMO": return { periods: P, lines: [{ name: "Índice de volumen físico", values: col(0), color: G }, { name: "Var. mensual (%)", values: col(1).map((v) => v == null ? null : v * 100), color: Go, axis: "right" }], leftName: "Índice (2018=100)", rightName: "Var. mensual (%)", leftFmt: "idx", rightFmt: "pct" };
    case "INPC": return { periods: P, lines: [{ name: "Inflación", values: col(0), color: G }, { name: "Subyacente", values: col(1), color: Go }, { name: "No subyacente", values: col(2), color: S }], leftName: "Variación anual (%)", leftFmt: "pct" };
    case "DESOCUP": return { periods: P, lines: [{ name: "Tasa de desocupación nacional", values: col(0).map((v) => v == null ? null : v * 100), color: Go }], leftName: "Porcentaje (%)", leftFmt: "pct" };
    case "IED": return { periods: P, stack: "ied", bars: [{ name: "Nuevas inversiones", values: col(1), color: G }, { name: "Reinversión de utilidades", values: col(2), color: Go }, { name: "Cuentas entre compañías", values: col(3), color: S }], lines: [{ name: "IED total", values: col(0), color: INK, dash: true }], leftName: "Millones de dólares", leftFmt: "compact" };
    case "BALANZA": return { periods: P, bars: [{ name: "Exportaciones", values: col(0), color: G }, { name: "Importaciones", values: col(1), color: Go }], lines: [{ name: "Saldo (X − M)", values: saldo, color: S, axis: "right" }], leftName: "Millones de dólares", rightName: "Saldo (mdd)", leftFmt: "compact", rightFmt: "compact" };
    case "IMFBCF": return { periods: P, lines: [{ name: "Índice (inversión)", values: col(0), color: G }, { name: "Var. mensual (%)", values: col(1).map((v) => v == null ? null : v * 100), color: Go, axis: "right" }], leftName: "Índice (2018=100)", rightName: "Var. mensual (%)", leftFmt: "idx", rightFmt: "pct" };
    case "EMIM": return { periods: P, lines: [{ name: "Producción (índice)", values: col(0), color: G }, { name: "Var. mensual (%)", values: col(1).map((v) => v == null ? null : v * 100), color: Go, axis: "right" }], leftName: "Índice", rightName: "Var. mensual (%)", leftFmt: "idx", rightFmt: "pct" };
    case "IOAE": return { periods: P, lines: [{ name: "Estimación puntual (%)", values: col(0), color: G }, { name: "Límite inferior", values: col(1), color: LG, dash: true }, { name: "Límite superior", values: col(2), color: LG, dash: true }], leftName: "Variación mensual (%)", leftFmt: "pct" };
    case "RESERVAS": return { periods: P, lines: [{ name: "Reservas internacionales", values: col(0), color: G }], leftName: "Millones de dólares", leftFmt: "compact" };
    case "TIPOCAMBIO": return { periods: P, lines: [{ name: "Tipo de cambio FIX", values: col(0), color: G }], leftName: "Pesos por dólar", leftFmt: "idx" };
    case "TASA": return { periods: P, lines: [{ name: "Tasa objetivo (%)", values: col(0), color: G }], leftName: "Porcentaje (%)", leftFmt: "pct" };
    default: return { periods: P, lines: [{ name: ind.nombre, values: col(0), color: G }], leftName: "", leftFmt: "num" };
  }
}

function axisFormatter(fmt) {
  return (v) => {
    if (fmt === "pct") return (Math.round(v * 10) / 10).toLocaleString("es-MX") + "%";
    if (fmt === "idx") return (Math.round(v * 10) / 10).toLocaleString("es-MX");
    if (fmt === "compact") return v.toLocaleString("es-MX", { notation: "compact", maximumFractionDigits: 1 });
    return Math.round(v).toLocaleString("es-MX");
  };
}

function tipFormatter(specFmt) {
  return (v) => {
    if (v == null || isNaN(v)) return "—";
    if (specFmt === "pct") return v.toLocaleString("es-MX", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + "%";
    if (specFmt === "idx") return v.toLocaleString("es-MX", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
    return Math.round(v).toLocaleString("es-MX");
  };
}

const FONT = "'Noto Sans', system-ui, sans-serif";

// Construye la opción de ECharts a partir del indicador y la ventana.
export function buildOption(ind, windowId) {
  const obs = applyWindow(ind, windowId);
  const spec = chartSpec(ind, obs);
  const bars = spec.bars || [];
  const lines = spec.lines || [];
  const hasRight = [...bars, ...lines].some((s) => s.axis === "right");

  const yAxis = [{
    type: "value", name: spec.leftName, nameLocation: "middle", nameGap: 52,
    nameTextStyle: { color: "#6c6f6a", fontFamily: FONT, fontSize: 11, fontWeight: 500 },
    axisLabel: { color: "#8a8d86", fontFamily: FONT, fontSize: 11, formatter: axisFormatter(spec.leftFmt) },
    splitLine: { lineStyle: { color: "#ece7da" } }, axisLine: { show: false }, axisTick: { show: false },
  }];
  if (hasRight) {
    yAxis.push({
      type: "value", name: spec.rightName || "", nameLocation: "middle", nameGap: 48,
      nameTextStyle: { color: "#6c6f6a", fontFamily: FONT, fontSize: 11, fontWeight: 500 },
      axisLabel: { color: "#8a8d86", fontFamily: FONT, fontSize: 11, formatter: axisFormatter(spec.rightFmt) },
      splitLine: { show: false }, axisLine: { show: false }, axisTick: { show: false },
    });
  }

  const series = [];
  const leftFmt = spec.leftFmt, rightFmt = spec.rightFmt;
  bars.forEach((b) => {
    series.push({
      name: b.name, type: "bar", data: b.values, itemStyle: { color: b.color },
      stack: spec.stack && bars.length > 1 ? spec.stack : undefined,
      yAxisIndex: b.axis === "right" ? 1 : 0, barMaxWidth: 34, emphasis: { focus: "series" },
      _fmt: b.axis === "right" ? rightFmt : leftFmt,
    });
  });
  lines.forEach((l) => {
    series.push({
      name: l.name, type: "line", data: l.values, yAxisIndex: l.axis === "right" ? 1 : 0,
      smooth: false, symbol: "circle", symbolSize: 5, connectNulls: false,
      lineStyle: { color: l.color, width: 2.4, type: l.dash ? "dashed" : "solid" },
      itemStyle: { color: l.color }, emphasis: { focus: "series" },
      _fmt: l.axis === "right" ? rightFmt : leftFmt,
    });
  });

  // markPoint de máximo/mínimo sobre la primera serie de barras o línea principal.
  if (series.length) {
    const primary = series[0];
    primary.markPoint = {
      symbol: "pin", symbolSize: 0,
      label: { show: false },
      data: [],
    };
  }

  const rotate = spec.periods.length > 12;
  return {
    color: [G, Go, S, TEAL, LG, INK],
    animation: false,
    grid: { left: 66, right: hasRight ? 62 : 24, top: 44, bottom: rotate ? 64 : 44, containLabel: false },
    legend: {
      top: 6, left: 0, itemWidth: 12, itemHeight: 12, icon: "roundRect",
      textStyle: { color: "#3d403b", fontFamily: FONT, fontSize: 12 },
    },
    tooltip: {
      trigger: "axis",
      backgroundColor: "#fff", borderColor: "#ddd7c6", borderWidth: 1,
      textStyle: { color: INK, fontFamily: FONT, fontSize: 12 },
      extraCssText: "box-shadow:0 5px 16px rgba(0,0,0,.13);border-radius:9px;",
      formatter: (params) => {
        if (!params || !params.length) return "";
        let html = `<div style="font-family:'IBM Plex Mono',monospace;font-weight:600;color:#002f2a;margin-bottom:5px">${params[0].axisValue}</div>`;
        params.forEach((p) => {
          const s = series.find((se) => se.name === p.seriesName);
          const fmt = s ? s._fmt : "num";
          html += `<div style="display:flex;align-items:center;gap:8px;margin:2px 0">${p.marker}<span style="flex:1;color:#5c5f5a;font-size:11px">${p.seriesName}</span><span style="font-family:'IBM Plex Mono',monospace;font-weight:600">${tipFormatter(fmt)(p.value)}</span></div>`;
        });
        return html;
      },
    },
    toolbox: {
      right: 4, top: 2, itemSize: 14,
      feature: { saveAsImage: { title: "Guardar imagen", name: `${ind.key}`, pixelRatio: 2, backgroundColor: "#fff" } },
      iconStyle: { borderColor: "#8a8d86" },
    },
    xAxis: {
      type: "category", data: spec.periods, boundaryGap: bars.length > 0,
      axisLabel: { color: "#8a8d86", fontFamily: FONT, fontSize: rotate ? 9 : 10, rotate: rotate ? 42 : 0, interval: spec.periods.length > 16 ? "auto" : 0 },
      axisLine: { lineStyle: { color: "#c9c2b2" } }, axisTick: { show: false },
    },
    yAxis,
    series,
  };
}
