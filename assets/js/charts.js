// Construcción de gráficas con ECharts, replicando la identidad visual sobria.
import { COLORS, WINDOWS, KPICFG } from "./config.js";
import { periodToDate } from "./format.js";
import { primarySeriesForObs } from "./metrics.js";
import { fmtVal } from "./format.js";

// Homologación institucional: principal=verde, secundaria=guinda,
// tercera=dorado, referencia/promedio/límites=gris, alerta negativa=guinda oscuro.
const G = COLORS.GREEN, SEC = COLORS.CRIMSON, Go = COLORS.GOLD, REF = COLORS.GRAY, INK = COLORS.INK;

// Filtra las observaciones de un indicador según la ventana temporal.
function addMonths(d, n) {
  return new Date(d.getFullYear(), d.getMonth() + n, 1);
}

export function applyWindow(ind, windowId) {
  const wins = ind.windows || WINDOWS;
  const win = wins.find((w) => w.id === windowId) || wins[wins.length - 1];
  const base = ind._useOriginal && ind.observations_original?.length
    ? ind.observations_original
    : (ind.key === "TASA" && ind.regimen?.length ? ind.regimen : (ind.observations || []));
  let obs = base;
  if (!obs.length || win.id === "max") return obs;
  if (win.count != null) {
    // Para series trimestrales (PIB/EOPIBT) se prefiere un número fijo
    // de observaciones: 1 año = 4 trimestres, 2 años = 8, etc.
    const n = win.count;
    if (n >= 0 && n < obs.length) obs = obs.slice(-n);
    return obs;
  }
  if (win.months) {
    const lastD = periodToDate(obs[obs.length - 1].period);
    if (lastD) {
      const fromD = addMonths(lastD, -win.months);
      const filtered = obs.filter((o) => { const d = periodToDate(o.period); return d && d >= fromD; });
      if (filtered.length) obs = filtered;
      else obs = obs.slice(-win.months);
    } else {
      obs = obs.slice(-win.months);
    }
  } else if (win.from) {
    obs = obs.filter((o) => { const d = periodToDate(o.period); return !d || d >= win.from; });
    if (!obs.length) obs = base;
  }
  return obs;
}

// Estadísticas del rango visible para la serie primaria.
export function rangeStats(ind, obs) {
  const cfg = KPICFG[ind.key] || null;
  const series = primarySeriesForObs(obs, ind.key);
  const idxs = series.map((v, i) => (v == null ? -1 : i)).filter((i) => i >= 0);
  if (!idxs.length) return null;
  const lastI = idxs[idxs.length - 1];
  let maxI = idxs[0], minI = idxs[0];
  idxs.forEach((i) => { if (series[i] > series[maxI]) maxI = i; if (series[i] < series[minI]) minI = i; });
  const valFmt = cfg ? cfg.valFmt : (ind.columns && ind.columns[0] ? ind.columns[0].fmt : "num");
  return {
    lastP: obs[lastI].period,
    lastV: fmtVal(series[lastI], valFmt),
    maxP: obs[maxI].period,
    maxV: fmtVal(series[maxI], valFmt),
    minP: obs[minI].period,
    minV: fmtVal(series[minI], valFmt),
  };
}

// Devuelve una especificación neutral a partir del indicador (obs filtradas).
function chartSpec(ind, obs) {
  const P = obs.map((o) => o.period);
  const col = (i) => obs.map((o) => o.values[i] ?? null);
  const totalSec = obs.map((o) => { const [a, b, c] = o.values; return (a == null && b == null && c == null) ? null : (a || 0) + (b || 0) + (c || 0); });
  const saldo = obs.map((o) => (o.values[0] != null && o.values[1] != null) ? o.values[0] - o.values[1] : null);
  switch (ind.key) {
    case "PIB": return { periods: P, bars: [{ name: "Var. trimestral (%)", values: col(0).map((v) => v == null ? null : v * 100), color: G }], lines: [{ name: "Var. anual desest. (%)", values: col(1).map((v) => v == null ? null : v * 100), color: Go }], leftName: "Variación (%)", leftFmt: "pct" };
    case "PIBSEC": return {
      periods: P,
      stack: "pib",
      bars: [
        { name: "Primarias", values: col(0), color: G },
        { name: "Secundarias", values: col(1), color: SEC },
        { name: "Terciarias", values: col(2), color: Go },
      ],
      lines: [
        { name: "PIB total", values: col(5), color: INK },
        { name: "Var. trim. PIB (%)", values: col(6).map((v) => v == null ? null : v * 100), color: INK, dash: true, axis: "right" },
        { name: "Var. trim. Primarias (%)", values: col(8).map((v) => v == null ? null : v * 100), color: G, dash: true, axis: "right" },
        { name: "Var. trim. Secundarias (%)", values: col(10).map((v) => v == null ? null : v * 100), color: SEC, dash: true, axis: "right" },
        { name: "Var. trim. Terciarias (%)", values: col(3).map((v) => v == null ? null : v * 100), color: Go, dash: true, axis: "right" },
      ],
      leftName: "Millones de pesos",
      rightName: "Variación trimestral (%)",
      leftFmt: "compact",
      rightFmt: "pct",
    };
    case "IGAE": return { periods: P, lines: [{ name: "Índice global", values: col(0), color: G }, { name: "Act. secundarias", values: col(1), color: SEC }, { name: "Act. terciarias", values: col(2), color: Go }], leftName: "Índice (2018=100)", leftFmt: "idx" };
    case "IMAI": return { periods: P, lines: [{ name: "Índice de volumen físico", values: col(0), color: G }, { name: "Var. mensual (%)", values: col(1).map((v) => v == null ? null : v * 100), color: SEC, axis: "right" }, { name: "Var. anual (%)", values: col(2).map((v) => v == null ? null : v * 100), color: Go, axis: "right" }], leftName: "Índice (2018=100)", rightName: "Var. (%)", leftFmt: "idx", rightFmt: "pct" };
    case "CONSUMO": return { periods: P, lines: [{ name: "Índice de volumen físico", values: col(0), color: G }, { name: "Var. mensual desest. (%)", values: col(1).map((v) => v == null ? null : v * 100), color: SEC, axis: "right" }, { name: "Var. anual desest. (%)", values: col(2).map((v) => v == null ? null : v * 100), color: Go, axis: "right" }, { name: "Acumulado ene-mes (%)", values: col(4).map((v) => v == null ? null : v * 100), color: REF, axis: "right" }], leftName: "Índice (2018=100)", rightName: "Var. (%)", leftFmt: "idx", rightFmt: "pct" };
    case "INPC": return { periods: P, lines: [
      { name: "Inflación general", values: col(2), color: G },
      { name: "Subyacente", values: col(5), color: SEC },
      { name: "No subyacente", values: col(11), color: Go }
    ], leftName: "Inflación anual (%)", leftFmt: "pct" };
    case "INPP": return { periods: P, lines: [
      { name: "INPP con petróleo", values: col(2), color: G },
      { name: "INPP sin petróleo", values: col(6), color: SEC },
      { name: "Bienes intermedios", values: col(8), color: Go }
    ], leftName: "Variación anual (%)", leftFmt: "pct" };
    case "DESOCUP": return { periods: P, lines: [{ name: "Tasa de desocupación nacional", values: col(0).map((v) => v == null ? null : v * 100), color: G }], leftName: "Porcentaje (%)", leftFmt: "pct" };
    case "IED": return { periods: P, stack: "ied", bars: [{ name: "Nuevas inversiones", values: col(1), color: G }, { name: "Reinversión de utilidades", values: col(2), color: SEC }, { name: "Cuentas entre compañías", values: col(3), color: Go }], lines: [{ name: "IED total", values: col(0), color: REF, dash: true }], leftName: "Millones de dólares", leftFmt: "compact" };
    case "BALANZA": return { periods: P, bars: [{ name: "Exportaciones", values: col(0), color: G }, { name: "Importaciones", values: col(1), color: SEC }], lines: [{ name: "Saldo (X − M)", values: saldo, color: Go, axis: "right" }], leftName: "Millones de dólares", rightName: "Saldo (mdd)", leftFmt: "compact", rightFmt: "compact" };
    case "IMFBCF": return { periods: P, lines: [{ name: "Índice (inversión)", values: col(0), color: G }, { name: "Var. mensual (%)", values: col(1).map((v) => v == null ? null : v * 100), color: SEC, axis: "right" }], leftName: "Índice (2018=100)", rightName: "Var. mensual (%)", leftFmt: "idx", rightFmt: "pct" };
    case "EMIM": return { periods: P, lines: [{ name: "Producción (índice)", values: col(0), color: G }, { name: "Var. mensual (%)", values: col(1).map((v) => v == null ? null : v * 100), color: SEC, axis: "right" }], leftName: "Índice", rightName: "Var. mensual (%)", leftFmt: "idx", rightFmt: "pct" };
    case "IOAE": return {
      periods: P,
      lines: [
        { name: "Nowcast anual IGAE (%)", values: col(0).map((v) => v == null ? null : v * 100), color: G },
        { name: "IC 95% inferior", values: col(1).map((v) => v == null ? null : v * 100), color: REF, dash: true },
        { name: "IC 95% superior", values: col(2).map((v) => v == null ? null : v * 100), color: REF, dash: true },
        { name: "IGAE observado", values: col(12).map((v) => v == null ? null : v * 100), color: Go, dash: true },
        { name: "Nowcast secundarias (%)", values: col(4).map((v) => v == null ? null : v * 100), color: COLORS.TEAL },
        { name: "Nowcast terciarias (%)", values: col(7).map((v) => v == null ? null : v * 100), color: COLORS.WINE },
        { name: "Nowcast mensual IGAE (%)", values: col(3).map((v) => v == null ? null : v * 100), color: COLORS.DKGREEN, dash: true, axis: "right" },
      ],
      leftName: "Variación anual (%)", rightName: "Var. mensual (%)", leftFmt: "pct", rightFmt: "pct"
    };
    case "RESERVAS": return { periods: P, lines: [{ name: "Reservas internacionales", values: col(0), color: G }], leftName: "Millones de dólares", leftFmt: "compact" };
    case "TIPOCAMBIO": return { periods: P, lines: [{ name: "Tipo de cambio FIX", values: col(0), color: G }], leftName: "Pesos por dólar", leftFmt: "idx" };
    case "TASA": return { periods: P, lines: [{ name: "Tasa objetivo (%)", values: col(0), color: G, step: "start" }], leftName: "Porcentaje (%)", leftFmt: "pct" };
    case "EMOE": return { periods: P, lines: [{ name: "IGOEC", values: col(0), color: G, refLine: 50 }], leftName: "Puntos", leftFmt: "idx" };
    case "BCMM": return { periods: P, bars: [{ name: "Exportaciones", values: col(0), color: G }, { name: "Importaciones", values: col(1), color: SEC }], lines: [{ name: "Saldo (X − M)", values: saldo, color: Go, axis: "right" }], leftName: "Millones de dólares", rightName: "Saldo (mdd)", leftFmt: "compact", rightFmt: "compact" };
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

  const leftHasBars = bars.some((b) => b.axis !== "right");
  const rightHasBars = bars.some((b) => b.axis === "right");
  const yAxis = [{
    type: "value", name: spec.leftName, nameLocation: "middle", nameGap: 52,
    nameTextStyle: { color: "#6c6f6a", fontFamily: FONT, fontSize: 11, fontWeight: 500 },
    axisLabel: { color: "#8a8d86", fontFamily: FONT, fontSize: 11, formatter: axisFormatter(spec.leftFmt) },
    splitLine: { lineStyle: { color: "#ece7da" } }, axisLine: { show: false }, axisTick: { show: false },
    scale: !leftHasBars,
  }];
  if (hasRight) {
    yAxis.push({
      type: "value", name: spec.rightName || "", nameLocation: "middle", nameGap: 48,
      nameTextStyle: { color: "#6c6f6a", fontFamily: FONT, fontSize: 11, fontWeight: 500 },
      axisLabel: { color: "#8a8d86", fontFamily: FONT, fontSize: 11, formatter: axisFormatter(spec.rightFmt) },
      splitLine: { show: false }, axisLine: { show: false }, axisTick: { show: false },
      scale: !rightHasBars,
    });
  }

  const series = [];
  const leftFmt = spec.leftFmt, rightFmt = spec.rightFmt;
  bars.forEach((b) => {
    const fmt = b.axis === "right" ? rightFmt : leftFmt;
    const s = {
      name: b.name, type: "bar", data: b.values, itemStyle: { color: b.color },
      stack: spec.stack && bars.length > 1 ? spec.stack : undefined,
      yAxisIndex: b.axis === "right" ? 1 : 0, barMaxWidth: 34, emphasis: { focus: "series" },
      _fmt: fmt,
    };
    if (fmt === "pct") {
      s.markLine = { symbol: "none", data: [{ yAxis: 0, name: "Cero", lineStyle: { color: COLORS.GRAY, type: "dashed", width: 1 }, label: { show: false } }], animation: false };
    }
    series.push(s);
  });
  function refLine(fmt, customY) {
    if (customY != null) return { yAxis: customY, name: "Referencia", lineStyle: { color: COLORS.GRAY, type: "dashed", width: 1 }, label: { show: false } };
    if (fmt === "pct") return { yAxis: 0, name: "Cero", lineStyle: { color: COLORS.GRAY, type: "dashed", width: 1 }, label: { show: false } };
    if (fmt === "idx") return { yAxis: 100, name: "Base 100", lineStyle: { color: COLORS.GRAY, type: "dashed", width: 1 }, label: { show: false } };
    return null;
  }
  lines.forEach((l) => {
    const fmt = l.axis === "right" ? rightFmt : leftFmt;
    const ref = refLine(fmt, l.refLine);
    const s = {
      name: l.name, type: "line", data: l.values, yAxisIndex: l.axis === "right" ? 1 : 0,
      smooth: false, symbol: "circle", symbolSize: 5, connectNulls: false,
      step: l.step || undefined,
      lineStyle: { color: l.color, width: 2.4, type: l.dash ? "dashed" : "solid" },
      itemStyle: { color: l.color }, emphasis: { focus: "series" },
      _fmt: fmt,
    };
    if (ref) s.markLine = { symbol: "none", data: [ref], animation: false };
    series.push(s);
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

  const allValues = (src) => src.flatMap((s) => s.values || []).filter((v) => v != null && !Number.isNaN(v));
  const leftSources = [...bars, ...lines].filter((s) => s.axis !== "right");
  const rightSources = [...bars, ...lines].filter((s) => s.axis === "right");
  const leftVals = allValues(leftSources);
  const rightVals = allValues(rightSources);
  const leftRef = (lines.find((l) => l.axis !== "right" && l.refLine != null) || {}).refLine;
  const rightRef = (lines.find((l) => l.axis === "right" && l.refLine != null) || {}).refLine;
  if (yAxis[0].scale && leftVals.length) {
    const yRange = computeYRange(leftVals, { padding: 0.08, includeZero: false, ref: leftRef });
    if (yRange) { yAxis[0].min = yRange.min; yAxis[0].max = yRange.max; }
  }
  if (yAxis[1] && yAxis[1].scale && rightVals.length) {
    const yRange = computeYRange(rightVals, { padding: 0.08, includeZero: false, ref: rightRef });
    if (yRange) { yAxis[1].min = yRange.min; yAxis[1].max = yRange.max; }
  }

  const rotate = spec.periods.length > 12;
  return {
    color: [G, SEC, Go, REF, COLORS.DKGREEN, COLORS.WINE],
    animation: false,
    grid: { left: 66, right: hasRight ? 62 : 24, top: 52, bottom: rotate ? 64 : 44, containLabel: false },
    legend: {
      top: 6, left: "center", right: 8, itemWidth: 12, itemHeight: 12, icon: "roundRect",
      textStyle: { color: "#3d403b", fontFamily: FONT, fontSize: 12 },
      type: "scroll",
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

// ---------------- PIBT: 4 small multiples (niveles) ----------------
function computeYRange(values, { padding = 0.08, includeZero = false, ref = null } = {}) {
  const v = values.filter((x) => x != null && !Number.isNaN(x));
  if (!v.length && ref == null) return null;
  const actualMin = v.length ? Math.min(...v) : ref;
  const actualMax = v.length ? Math.max(...v) : ref;
  let min = actualMin, max = actualMax;
  if (ref != null) {
    min = Math.min(min, ref);
    max = Math.max(max, ref);
  }
  if (min === max) {
    const span = Math.max(Math.abs(min), Math.abs(max)) || 1;
    min -= span * 0.05;
    max += span * 0.05;
  } else {
    const range = max - min;
    const pad = range * padding;
    min -= pad;
    max += pad;
  }
  if (includeZero) {
    if (min > 0) min = 0;
    if (max < 0) max = 0;
  } else if (actualMin >= 0) {
    min = Math.max(0, min);
  }
  return { min, max };
}

const PIBSEC_COLORS = { PIB: COLORS.INK, Primarias: G, Secundarias: COLORS.CRIMSON, Terciarias: Go };
const PIBSEC_LEVELS = [
  { key: "PIB", col: 5, top: "PIB total" },
  { key: "Primarias", col: 0, top: "Actividades primarias" },
  { key: "Secundarias", col: 1, top: "Actividades secundarias" },
  { key: "Terciarias", col: 2, top: "Actividades terciarias" },
];

function lastHighlight(series, periods, values, color, formatter) {
  const fmt = formatter || ((v) => (v == null ? "—" : v.toLocaleString("es-MX", { minimumFractionDigits: 2, maximumFractionDigits: 2 })));
  const n = values.length;
  for (let i = n - 1; i >= 0; i--) {
    if (values[i] != null) {
      series.markPoint = {
        symbol: "circle", symbolSize: 7,
        itemStyle: { color: COLORS.INK, borderColor: color, borderWidth: 2 },
        label: {
          show: true, position: "top", distance: 4, color: "#3d403b",
          fontFamily: "'IBM Plex Mono',monospace", fontSize: 10,
          formatter: (p) => fmt(p.value),
        },
        data: [{ coord: [periods[i], values[i]] }],
      };
      break;
    }
  }
}

export function buildPibsecLevels(obs) {
  const periods = obs.map((o) => o.period);
  const grids = [];
  const xAxes = [];
  const yAxes = [];
  const series = [];
  const titles = [];
  const rotate = periods.length > 12;
  PIBSEC_LEVELS.forEach((cfg, i) => {
    const row = Math.floor(i / 2);
    const col = i % 2;
    const left = col === 0 ? "4%" : "54%";
    const top = row === 0 ? 20 : 225;
    const height = 165;
    const width = "42%";
    grids.push({ left, top, width, height, containLabel: false });
    xAxes.push({
      gridIndex: i, type: "category", data: periods, boundaryGap: false,
      axisLabel: { color: "#8a8d86", fontFamily: FONT, fontSize: rotate ? 8 : 9, rotate: rotate ? 42 : 0, interval: periods.length > 16 ? "auto" : 0 },
      axisLine: { lineStyle: { color: "#c9c2b2" } }, axisTick: { show: false },
    });
    yAxes.push({
      gridIndex: i, type: "value", name: "Billones de pesos (2018)", nameLocation: "middle", nameGap: 34,
      nameTextStyle: { color: "#6c6f6a", fontFamily: FONT, fontSize: 10, fontWeight: 500 },
      axisLabel: { color: "#8a8d86", fontFamily: FONT, fontSize: 10, formatter: (v) => (v / 1e6).toLocaleString("es-MX", { minimumFractionDigits: 1, maximumFractionDigits: 2 }) },
      splitLine: { lineStyle: { color: "#ece7da" } }, axisLine: { show: false }, axisTick: { show: false }, scale: false,
    });
    const values = obs.map((o) => o.values[cfg.col] ?? null);
    const s = {
      name: cfg.top, type: "line", xAxisIndex: i, yAxisIndex: i,
      data: values, smooth: false, symbol: "circle", symbolSize: 3,
      lineStyle: { color: PIBSEC_COLORS[cfg.key], width: 2 },
      itemStyle: { color: PIBSEC_COLORS[cfg.key] },
      areaStyle: { color: PIBSEC_COLORS[cfg.key], opacity: 0.08 },
    };
    lastHighlight(s, periods, values, PIBSEC_COLORS[cfg.key], (v) => v == null ? "—" : (v / 1e6).toLocaleString("es-MX", { minimumFractionDigits: 2, maximumFractionDigits: 2 }));
    series.push(s);
    const yRange = computeYRange(values, { padding: 0.08, includeZero: false });
    if (yRange) { yAxes[i].min = yRange.min; yAxes[i].max = yRange.max; yAxes[i].scale = true; }
    titles.push({ text: cfg.top, left, top: top - 18, textStyle: { color: "#3d403b", fontFamily: FONT, fontSize: 12, fontWeight: 600 } });
  });
  return {
    animation: false, color: [G, SEC, Go, COLORS.INK],
    title: titles, grid: grids, xAxis: xAxes, yAxis: yAxes, series,
    tooltip: {
      trigger: "axis", backgroundColor: "#fff", borderColor: "#ddd7c6", borderWidth: 1,
      textStyle: { color: COLORS.INK, fontFamily: FONT, fontSize: 12 },
      extraCssText: "box-shadow:0 5px 16px rgba(0,0,0,.13);border-radius:9px;",
      formatter: (params) => {
        if (!params || !params.length) return "";
        const p = params[0];
        const v = p.value;
        const val = v == null ? "—" : (v / 1e6).toLocaleString("es-MX", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " billones de pesos de 2018";
        return `<div style="font-family:'IBM Plex Mono',monospace;font-weight:600;color:#002f2a;margin-bottom:5px">${p.axisValue}</div>`
          + `<div style="display:flex;align-items:center;gap:8px;margin:2px 0">${p.marker}<span style="flex:1;color:#5c5f5a;font-size:11px">${p.seriesName}</span><span style="font-family:'IBM Plex Mono',monospace;font-weight:600">${val}</span></div>`;
      },
    },
    toolbox: { right: 4, top: 2, itemSize: 14, feature: { saveAsImage: { title: "Guardar imagen", name: "PIBT-niveles", pixelRatio: 2, backgroundColor: "#fff" } }, iconStyle: { borderColor: "#8a8d86" } },
  };
}

// ---------------- PIBT: variaciones agrupadas (qoq / yoy) ----------------
const PIBSEC_VAR = [
  { name: "PIB", qoq: 6, yoy: 7, color: COLORS.INK },
  { name: "Primarias", qoq: 8, yoy: 9, color: G },
  { name: "Secundarias", qoq: 10, yoy: 11, color: COLORS.CRIMSON },
  { name: "Terciarias", qoq: 3, yoy: 4, color: Go },
];

function pctTip(value, name, color) {
  if (value == null) return "";
  const s = value >= 0 ? "+" : "";
  return `<div style="display:flex;align-items:center;gap:8px;margin:2px 0"><span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:${color}"></span><span style="flex:1;color:#5c5f5a;font-size:11px">${name}</span><span style="font-family:'IBM Plex Mono',monospace;font-weight:600">${s}${value.toFixed(2)}%</span></div>`;
}

export function buildPibsecVariations(obs) {
  const periods = obs.map((o) => o.period);
  const grids = [
    { left: "4%", top: 50, width: "44%", height: 180, containLabel: false },
    { left: "54%", top: 50, width: "44%", height: 180, containLabel: false },
  ];
  const xAxis = grids.map((_, i) => ({
    gridIndex: i, type: "category", data: periods, boundaryGap: true,
    axisLabel: { color: "#8a8d86", fontFamily: FONT, fontSize: periods.length > 12 ? 8 : 9, interval: periods.length > 16 ? "auto" : 0, rotate: periods.length > 16 ? 42 : 0 },
    axisLine: { lineStyle: { color: "#c9c2b2" } }, axisTick: { show: false },
  }));
  const qoqAll = [];
  const yoyAll = [];
  const series = [];
  PIBSEC_VAR.forEach((cfg, si) => {
    const qoqData = obs.map((o) => (o.values[cfg.qoq] == null ? null : o.values[cfg.qoq] * 100));
    const yoyData = obs.map((o) => (o.values[cfg.yoy] == null ? null : o.values[cfg.yoy] * 100));
    qoqAll.push(...qoqData);
    yoyAll.push(...yoyData);
    series.push({
      name: cfg.name, type: "bar", xAxisIndex: 0, yAxisIndex: 0,
      data: qoqData, itemStyle: { color: cfg.color }, barMaxWidth: 14,
      emphasis: { focus: "series" },
      markLine: si === 0 ? { symbol: "none", data: [{ yAxis: 0, lineStyle: { color: COLORS.GRAY, type: "dashed", width: 1 }, label: { show: false } }], animation: false } : undefined,
    });
    series.push({
      name: cfg.name, type: "bar", xAxisIndex: 1, yAxisIndex: 1,
      data: yoyData, itemStyle: { color: cfg.color }, barMaxWidth: 14,
      emphasis: { focus: "series" },
      markLine: si === 0 ? { symbol: "none", data: [{ yAxis: 0, lineStyle: { color: COLORS.GRAY, type: "dashed", width: 1 }, label: { show: false } }], animation: false } : undefined,
    });
  });
  const qoqRange = computeYRange(qoqAll, { padding: 0.12, includeZero: true });
  const yoyRange = computeYRange(yoyAll, { padding: 0.12, includeZero: true });
  const yAxis = grids.map((_, i) => {
    const range = i === 0 ? qoqRange : yoyRange;
    const ay = {
      gridIndex: i, type: "value", name: i === 0 ? "Variación trimestral (%)" : "Variación anual (%)", nameLocation: "middle", nameGap: 40,
      nameTextStyle: { color: "#6c6f6a", fontFamily: FONT, fontSize: 11, fontWeight: 500 },
      axisLabel: { color: "#8a8d86", fontFamily: FONT, fontSize: 10, formatter: (v) => v.toFixed(1) + "%" },
      splitLine: { lineStyle: { color: "#ece7da" } }, axisLine: { show: false }, axisTick: { show: false }, scale: false,
    };
    if (range) { ay.min = range.min; ay.max = range.max; }
    return ay;
  });
  return {
    animation: false, color: [G, SEC, Go, COLORS.INK],
    grid: grids, xAxis, yAxis, series,
    tooltip: {
      trigger: "axis", backgroundColor: "#fff", borderColor: "#ddd7c6", borderWidth: 1,
      textStyle: { color: COLORS.INK, fontFamily: FONT, fontSize: 12 },
      extraCssText: "box-shadow:0 5px 16px rgba(0,0,0,.13);border-radius:9px;",
      formatter: (params) => {
        if (!params || !params.length) return "";
        const p0 = params[0];
        let html = `<div style="font-family:'IBM Plex Mono',monospace;font-weight:600;color:#002f2a;margin-bottom:5px">${p0.axisValue}</div>`;
        params.forEach((p) => {
          const cfg = PIBSEC_VAR.find((c) => c.name === p.seriesName);
          html += pctTip(p.value, p.seriesName, cfg ? cfg.color : COLORS.GRAY);
        });
        return html;
      },
    },
    legend: { top: 10, left: "center", itemWidth: 12, itemHeight: 12, icon: "roundRect", textStyle: { color: "#3d403b", fontFamily: FONT, fontSize: 11 } },
    toolbox: { right: 4, top: 2, itemSize: 14, feature: { saveAsImage: { title: "Guardar imagen", name: "PIBT-variaciones", pixelRatio: 2, backgroundColor: "#fff" } }, iconStyle: { borderColor: "#8a8d86" } },
  };
}

// ---------------- EMOE: small multiples de sectores (ICE) ----------------
const EMOE_SECTOR_COLORS = { Manufacturas: G, Construccion: COLORS.CRIMSON, Comercio: Go, Servicios: COLORS.TEAL };
const EMOE_SECTORS = [
  { key: "Manufacturas", col: 3, top: "Manufacturas" },
  { key: "Construccion", col: 4, top: "Construcción" },
  { key: "Comercio", col: 5, top: "Comercio" },
  { key: "Servicios", col: 6, top: "Servicios privados no financieros" },
];

export function buildEmoeSectors(obs) {
  const periods = obs.map((o) => o.period);
  const grids = [], xAxes = [], yAxes = [], series = [], titles = [];
  const rotate = periods.length > 12;
  EMOE_SECTORS.forEach((cfg, i) => {
    const row = Math.floor(i / 2);
    const col = i % 2;
    const left = col === 0 ? "4%" : "54%";
    const top = row === 0 ? 20 : 225;
    const height = 165;
    const width = "42%";
    grids.push({ left, top, width, height, containLabel: false });
    xAxes.push({
      gridIndex: i, type: "category", data: periods, boundaryGap: false,
      axisLabel: { color: "#8a8d86", fontFamily: FONT, fontSize: rotate ? 8 : 9, interval: periods.length > 16 ? "auto" : 0, rotate: rotate ? 42 : 0 },
      axisLine: { lineStyle: { color: "#c9c2b2" } }, axisTick: { show: false },
    });
    yAxes.push({
      gridIndex: i, type: "value", name: "Puntos", nameLocation: "middle", nameGap: 34,
      nameTextStyle: { color: "#6c6f6a", fontFamily: FONT, fontSize: 10, fontWeight: 500 },
      axisLabel: { color: "#8a8d86", fontFamily: FONT, fontSize: 10, formatter: (v) => v.toLocaleString("es-MX", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) },
      splitLine: { lineStyle: { color: "#ece7da" } }, axisLine: { show: false }, axisTick: { show: false }, scale: false,
    });
    const values = obs.map((o) => o.values[cfg.col] ?? null);
    const s = {
      name: cfg.top, type: "line", xAxisIndex: i, yAxisIndex: i,
      data: values, smooth: false, symbol: "circle", symbolSize: 3,
      lineStyle: { color: EMOE_SECTOR_COLORS[cfg.key], width: 2 },
      itemStyle: { color: EMOE_SECTOR_COLORS[cfg.key] },
      areaStyle: { color: EMOE_SECTOR_COLORS[cfg.key], opacity: 0.08 },
      markLine: { symbol: "none", data: [{ yAxis: 50, name: "Umbral 50", lineStyle: { color: COLORS.GRAY, type: "dashed", width: 1 }, label: { show: false } }], animation: false },
    };
    lastHighlight(s, periods, values, EMOE_SECTOR_COLORS[cfg.key], (v) => v == null ? "—" : v.toLocaleString("es-MX", { minimumFractionDigits: 2, maximumFractionDigits: 2 }));
    series.push(s);
    const yRange = computeYRange(values, { padding: 0.08, includeZero: false, ref: 50 });
    if (yRange) { yAxes[i].min = yRange.min; yAxes[i].max = yRange.max; yAxes[i].scale = true; }
    titles.push({ text: cfg.top, left, top: top - 18, textStyle: { color: "#3d403b", fontFamily: FONT, fontSize: 12, fontWeight: 600 } });
  });
  return {
    animation: false, color: [G, COLORS.CRIMSON, Go, COLORS.TEAL],
    title: titles, grid: grids, xAxis: xAxes, yAxis: yAxes, series,
    tooltip: {
      trigger: "axis", backgroundColor: "#fff", borderColor: "#ddd7c6", borderWidth: 1,
      textStyle: { color: COLORS.INK, fontFamily: FONT, fontSize: 12 },
      extraCssText: "box-shadow:0 5px 16px rgba(0,0,0,.13);border-radius:9px;",
      formatter: (params) => {
        if (!params || !params.length) return "";
        const p = params[0];
        const v = p.value;
        const val = v == null ? "—" : v.toLocaleString("es-MX", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " puntos";
        return `<div style="font-family:'IBM Plex Mono',monospace;font-weight:600;color:#002f2a;margin-bottom:5px">${p.axisValue}</div>`
          + `<div style="display:flex;align-items:center;gap:8px;margin:2px 0">${p.marker}<span style="flex:1;color:#5c5f5a;font-size:11px">${p.seriesName}</span><span style="font-family:'IBM Plex Mono',monospace;font-weight:600">${val}</span></div>`;
      },
    },
    toolbox: { right: 4, top: 2, itemSize: 14, feature: { saveAsImage: { title: "Guardar imagen", name: "EMOE-sectores", pixelRatio: 2, backgroundColor: "#fff" } }, iconStyle: { borderColor: "#8a8d86" } },
  };
}

// ---------------- IGAE: small multiples (niveles) ----------------
const IGAE_COLORS = { IGAE: COLORS.INK, Primarias: G, Secundarias: COLORS.CRIMSON, Terciarias: Go };
const IGAE_LEVELS = [
  { key: "IGAE", col: 0, top: "IGAE" },
  { key: "Primarias", col: 3, top: "Actividades primarias" },
  { key: "Secundarias", col: 5, top: "Actividades secundarias" },
  { key: "Terciarias", col: 7, top: "Actividades terciarias" },
];

export function buildIgaeLevels(obs) {
  const periods = obs.map((o) => o.period);
  const grids = [], xAxes = [], yAxes = [], series = [], titles = [];
  const rotate = periods.length > 12;
  IGAE_LEVELS.forEach((cfg, i) => {
    const row = Math.floor(i / 2);
    const col = i % 2;
    const left = col === 0 ? "4%" : "54%";
    const top = row === 0 ? 20 : 225;
    const height = 165;
    const width = "42%";
    grids.push({ left, top, width, height, containLabel: false });
    xAxes.push({
      gridIndex: i, type: "category", data: periods, boundaryGap: false,
      axisLabel: { color: "#8a8d86", fontFamily: FONT, fontSize: rotate ? 8 : 9, interval: periods.length > 16 ? "auto" : 0, rotate: rotate ? 42 : 0 },
      axisLine: { lineStyle: { color: "#c9c2b2" } }, axisTick: { show: false },
    });
    yAxes.push({
      gridIndex: i, type: "value", name: "Índice (2018=100)", nameLocation: "middle", nameGap: 34,
      nameTextStyle: { color: "#6c6f6a", fontFamily: FONT, fontSize: 10, fontWeight: 500 },
      axisLabel: { color: "#8a8d86", fontFamily: FONT, fontSize: 10, formatter: (v) => v.toLocaleString("es-MX", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) },
      splitLine: { lineStyle: { color: "#ece7da" } }, axisLine: { show: false }, axisTick: { show: false }, scale: false,
    });
    const values = obs.map((o) => o.values[cfg.col] ?? null);
    const s = {
      name: cfg.top, type: "line", xAxisIndex: i, yAxisIndex: i,
      data: values, smooth: false, symbol: "circle", symbolSize: 3,
      lineStyle: { color: IGAE_COLORS[cfg.key], width: 2 },
      itemStyle: { color: IGAE_COLORS[cfg.key] },
      areaStyle: { color: IGAE_COLORS[cfg.key], opacity: 0.08 },
    };
    lastHighlight(s, periods, values, IGAE_COLORS[cfg.key], (v) => v == null ? "—" : v.toLocaleString("es-MX", { minimumFractionDigits: 1, maximumFractionDigits: 1 }));
    series.push(s);
    const yRange = computeYRange(values, { padding: 0.08, includeZero: false });
    if (yRange) { yAxes[i].min = yRange.min; yAxes[i].max = yRange.max; yAxes[i].scale = true; }
    titles.push({ text: cfg.top, left, top: top - 18, textStyle: { color: "#3d403b", fontFamily: FONT, fontSize: 12, fontWeight: 600 } });
  });
  return {
    animation: false, color: [COLORS.INK, G, COLORS.CRIMSON, Go],
    title: titles, grid: grids, xAxis: xAxes, yAxis: yAxes, series,
    tooltip: {
      trigger: "axis", backgroundColor: "#fff", borderColor: "#ddd7c6", borderWidth: 1,
      textStyle: { color: COLORS.INK, fontFamily: FONT, fontSize: 12 },
      extraCssText: "box-shadow:0 5px 16px rgba(0,0,0,.13);border-radius:9px;",
      formatter: (params) => {
        if (!params || !params.length) return "";
        const p = params[0];
        const v = p.value;
        const val = v == null ? "—" : v.toLocaleString("es-MX", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
        return `<div style="font-family:'IBM Plex Mono',monospace;font-weight:600;color:#002f2a;margin-bottom:5px">${p.axisValue}</div>`
          + `<div style="display:flex;align-items:center;gap:8px;margin:2px 0">${p.marker}<span style="flex:1;color:#5c5f5a;font-size:11px">${p.seriesName}</span><span style="font-family:'IBM Plex Mono',monospace;font-weight:600">${val}</span></div>`;
      },
    },
    toolbox: { right: 4, top: 2, itemSize: 14, feature: { saveAsImage: { title: "Guardar imagen", name: "IGAE-niveles", pixelRatio: 2, backgroundColor: "#fff" } }, iconStyle: { borderColor: "#8a8d86" } },
  };
}

// ---------------- IGAE: variaciones anuales agrupadas ----------------
const IGAE_VAR = [
  { name: "IGAE", yoy: 2, color: COLORS.INK },
  { name: "Primarias", yoy: 4, color: G },
  { name: "Secundarias", yoy: 6, color: COLORS.CRIMSON },
  { name: "Terciarias", yoy: 8, color: Go },
];

export function buildIgaeVariations(obs) {
  const periods = obs.map((o) => o.period);
  const yoyAll = [];
  const series = [];
  IGAE_VAR.forEach((cfg, si) => {
    const yoyData = obs.map((o) => (o.values[cfg.yoy] == null ? null : o.values[cfg.yoy] * 100));
    yoyAll.push(...yoyData);
    series.push({
      name: cfg.name, type: "bar",
      data: yoyData, itemStyle: { color: cfg.color }, barMaxWidth: 14,
      emphasis: { focus: "series" },
      markLine: si === 0 ? { symbol: "none", data: [{ yAxis: 0, lineStyle: { color: COLORS.GRAY, type: "dashed", width: 1 }, label: { show: false } }], animation: false } : undefined,
    });
  });
  const yoyRange = computeYRange(yoyAll, { padding: 0.12, includeZero: true });
  const yAxis = {
    type: "value", name: "Variación anual (%)", nameLocation: "middle", nameGap: 40,
    nameTextStyle: { color: "#6c6f6a", fontFamily: FONT, fontSize: 11, fontWeight: 500 },
    axisLabel: { color: "#8a8d86", fontFamily: FONT, fontSize: 10, formatter: (v) => v.toFixed(1) + "%" },
    splitLine: { lineStyle: { color: "#ece7da" } }, axisLine: { show: false }, axisTick: { show: false }, scale: false,
  };
  if (yoyRange) { yAxis.min = yoyRange.min; yAxis.max = yoyRange.max; }
  return {
    animation: false, color: [COLORS.INK, G, COLORS.CRIMSON, Go],
    grid: { left: "4%", right: "4%", top: 50, height: 240, containLabel: false },
    xAxis: { type: "category", data: periods, boundaryGap: true, axisLabel: { color: "#8a8d86", fontFamily: FONT, fontSize: periods.length > 12 ? 8 : 9, interval: periods.length > 16 ? "auto" : 0, rotate: periods.length > 16 ? 42 : 0 }, axisLine: { lineStyle: { color: "#c9c2b2" } }, axisTick: { show: false } },
    yAxis,
    series,
    tooltip: {
      trigger: "axis", backgroundColor: "#fff", borderColor: "#ddd7c6", borderWidth: 1,
      textStyle: { color: COLORS.INK, fontFamily: FONT, fontSize: 12 },
      extraCssText: "box-shadow:0 5px 16px rgba(0,0,0,.13);border-radius:9px;",
      formatter: (params) => {
        if (!params || !params.length) return "";
        const p0 = params[0];
        let html = `<div style="font-family:'IBM Plex Mono',monospace;font-weight:600;color:#002f2a;margin-bottom:5px">${p0.axisValue}</div>`;
        params.forEach((p) => {
          const cfg = IGAE_VAR.find((c) => c.name === p.seriesName);
          html += pctTip(p.value, p.seriesName, cfg ? cfg.color : COLORS.GRAY);
        });
        return html;
      },
    },
    legend: { top: 10, left: "center", itemWidth: 12, itemHeight: 12, icon: "roundRect", textStyle: { color: "#3d403b", fontFamily: FONT, fontSize: 11 } },
    toolbox: { right: 4, top: 2, itemSize: 14, feature: { saveAsImage: { title: "Guardar imagen", name: "IGAE-variaciones", pixelRatio: 2, backgroundColor: "#fff" } }, iconStyle: { borderColor: "#8a8d86" } },
  };
}

// ---------------- IMAI: small multiples (niveles) ----------------
const IMAI_COLORS = { IMAI: COLORS.INK, Mineria: G, Energia: COLORS.CRIMSON, Construccion: Go, Manufacturas: COLORS.GOLD };
const IMAI_LEVELS = [
  { key: "IMAI", col: 0, top: "IMAI" },
  { key: "Mineria", col: 6, top: "Minería" },
  { key: "Energia", col: 7, top: "Energía, agua y gas" },
  { key: "Construccion", col: 8, top: "Construcción" },
  { key: "Manufacturas", col: 9, top: "Industrias manufactureras" },
];

export function buildImaiLevels(obs) {
  const periods = obs.map((o) => o.period);
  const grids = [], xAxes = [], yAxes = [], series = [], titles = [];
  const rotate = periods.length > 12;
  IMAI_LEVELS.forEach((cfg, i) => {
    const row = Math.floor(i / 2);
    const col = i % 2;
    const left = col === 0 ? "4%" : "54%";
    const top = row === 0 ? 20 : (row === 1 ? 225 : 430);
    const height = 165;
    const width = "42%";
    grids.push({ left, top, width, height, containLabel: false });
    xAxes.push({
      gridIndex: i, type: "category", data: periods, boundaryGap: false,
      axisLabel: { color: "#8a8d86", fontFamily: FONT, fontSize: rotate ? 8 : 9, interval: periods.length > 16 ? "auto" : 0, rotate: rotate ? 42 : 0 },
      axisLine: { lineStyle: { color: "#c9c2b2" } }, axisTick: { show: false },
    });
    yAxes.push({
      gridIndex: i, type: "value", name: "Índice (2018=100)", nameLocation: "middle", nameGap: 34,
      nameTextStyle: { color: "#6c6f6a", fontFamily: FONT, fontSize: 10, fontWeight: 500 },
      axisLabel: { color: "#8a8d86", fontFamily: FONT, fontSize: 10, formatter: (v) => v.toLocaleString("es-MX", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) },
      splitLine: { lineStyle: { color: "#ece7da" } }, axisLine: { show: false }, axisTick: { show: false }, scale: false,
    });
    const values = obs.map((o) => (o.values && o.values.length > cfg.col ? o.values[cfg.col] : null));
    const s = {
      name: cfg.top, type: "line", xAxisIndex: i, yAxisIndex: i,
      data: values, smooth: false, symbol: "circle", symbolSize: 3,
      lineStyle: { color: IMAI_COLORS[cfg.key], width: 2 },
      itemStyle: { color: IMAI_COLORS[cfg.key] },
      areaStyle: { color: IMAI_COLORS[cfg.key], opacity: 0.08 },
    };
    lastHighlight(s, periods, values, IMAI_COLORS[cfg.key], (v) => v == null ? "—" : v.toLocaleString("es-MX", { minimumFractionDigits: 1, maximumFractionDigits: 1 }));
    series.push(s);
    const yRange = computeYRange(values, { padding: 0.08, includeZero: false });
    if (yRange) { yAxes[i].min = yRange.min; yAxes[i].max = yRange.max; yAxes[i].scale = true; }
    titles.push({ text: cfg.top, left, top: top - 18, textStyle: { color: "#3d403b", fontFamily: FONT, fontSize: 12, fontWeight: 600 } });
  });
  return {
    animation: false, color: [COLORS.INK, G, COLORS.CRIMSON, Go, COLORS.GOLD],
    title: titles, grid: grids, xAxis: xAxes, yAxis: yAxes, series,
    tooltip: {
      trigger: "axis", backgroundColor: "#fff", borderColor: "#ddd7c6", borderWidth: 1,
      textStyle: { color: COLORS.INK, fontFamily: FONT, fontSize: 12 },
      extraCssText: "box-shadow:0 5px 16px rgba(0,0,0,.13);border-radius:9px;",
      formatter: (params) => {
        if (!params || !params.length) return "";
        const p = params[0];
        const v = p.value;
        const val = v == null ? "—" : v.toLocaleString("es-MX", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
        return `<div style="font-family:'IBM Plex Mono',monospace;font-weight:600;color:#002f2a;margin-bottom:5px">${p.axisValue}</div>`
          + `<div style="display:flex;align-items:center;gap:8px;margin:2px 0">${p.marker}<span style="flex:1;color:#5c5f5a;font-size:11px">${p.seriesName}</span><span style="font-family:'IBM Plex Mono',monospace;font-weight:600">${val}</span></div>`;
      },
    },
    toolbox: { right: 4, top: 2, itemSize: 14, feature: { saveAsImage: { title: "Guardar imagen", name: "IMAI-niveles", pixelRatio: 2, backgroundColor: "#fff" } }, iconStyle: { borderColor: "#8a8d86" } },
  };
}

// ---------------- IMAI: variaciones mensuales y anuales agrupadas ----------------
const IMAI_VAR = [
  { name: "IMAI", mom: 1, yoy: 2, color: COLORS.INK },
  { name: "Minería", mom: 14, yoy: 10, color: G },
  { name: "Energía", mom: 15, yoy: 11, color: COLORS.CRIMSON },
  { name: "Construcción", mom: 16, yoy: 12, color: Go },
  { name: "Manufacturas", mom: 17, yoy: 13, color: COLORS.GOLD },
];

export function buildImaiVariations(obs) {
  const periods = obs.map((o) => o.period);
  const grids = [
    { left: "4%", top: 50, width: "44%", height: 220, containLabel: false },
    { left: "54%", top: 50, width: "44%", height: 220, containLabel: false },
  ];
  const xAxes = grids.map((_, i) => ({
    gridIndex: i, type: "category", data: periods, boundaryGap: true,
    axisLabel: { color: "#8a8d86", fontFamily: FONT, fontSize: periods.length > 12 ? 8 : 9, interval: periods.length > 16 ? "auto" : 0, rotate: periods.length > 16 ? 42 : 0 },
    axisLine: { lineStyle: { color: "#c9c2b2" } }, axisTick: { show: false },
  }));
  const momAll = [];
  const yoyAll = [];
  const series = [];
  IMAI_VAR.forEach((cfg, si) => {
    const momData = obs.map((o) => (o.values && o.values.length > cfg.mom ? o.values[cfg.mom] : null)).map((v) => v == null ? null : v * 100);
    const yoyData = obs.map((o) => (o.values && o.values.length > cfg.yoy ? o.values[cfg.yoy] : null)).map((v) => v == null ? null : v * 100);
    momAll.push(...momData);
    yoyAll.push(...yoyData);
    series.push({
      name: cfg.name, type: "bar", xAxisIndex: 0, yAxisIndex: 0,
      data: momData, itemStyle: { color: cfg.color }, barMaxWidth: 10,
      emphasis: { focus: "series" },
      markLine: si === 0 ? { symbol: "none", data: [{ yAxis: 0, lineStyle: { color: COLORS.GRAY, type: "dashed", width: 1 }, label: { show: false } }], animation: false } : undefined,
    });
    series.push({
      name: cfg.name, type: "bar", xAxisIndex: 1, yAxisIndex: 1,
      data: yoyData, itemStyle: { color: cfg.color }, barMaxWidth: 10,
      emphasis: { focus: "series" },
      markLine: si === 0 ? { symbol: "none", data: [{ yAxis: 0, lineStyle: { color: COLORS.GRAY, type: "dashed", width: 1 }, label: { show: false } }], animation: false } : undefined,
    });
  });
  const momRange = computeYRange(momAll, { padding: 0.12, includeZero: true });
  const yoyRange = computeYRange(yoyAll, { padding: 0.12, includeZero: true });
  const yAxis = grids.map((_, i) => {
    const range = i === 0 ? momRange : yoyRange;
    const ay = {
      gridIndex: i, type: "value", name: i === 0 ? "Variación mensual (%)" : "Variación anual (%)", nameLocation: "middle", nameGap: 40,
      nameTextStyle: { color: "#6c6f6a", fontFamily: FONT, fontSize: 11, fontWeight: 500 },
      axisLabel: { color: "#8a8d86", fontFamily: FONT, fontSize: 10, formatter: (v) => v.toFixed(1) + "%" },
      splitLine: { lineStyle: { color: "#ece7da" } }, axisLine: { show: false }, axisTick: { show: false }, scale: false,
    };
    if (range) { ay.min = range.min; ay.max = range.max; }
    return ay;
  });
  return {
    animation: false, color: [COLORS.INK, G, COLORS.CRIMSON, Go, COLORS.GOLD],
    grid: grids, xAxis: xAxes, yAxis,
    series,
    tooltip: {
      trigger: "axis", backgroundColor: "#fff", borderColor: "#ddd7c6", borderWidth: 1,
      textStyle: { color: COLORS.INK, fontFamily: FONT, fontSize: 12 },
      extraCssText: "box-shadow:0 5px 16px rgba(0,0,0,.13);border-radius:9px;",
      formatter: (params) => {
        if (!params || !params.length) return "";
        const p0 = params[0];
        let html = `<div style="font-family:'IBM Plex Mono',monospace;font-weight:600;color:#002f2a;margin-bottom:5px">${p0.axisValue}</div>`;
        params.forEach((p) => {
          const cfg = IMAI_VAR.find((c) => c.name === p.seriesName);
          html += pctTip(p.value, p.seriesName, cfg ? cfg.color : COLORS.GRAY);
        });
        return html;
      },
    },
    legend: { top: 10, left: "center", itemWidth: 12, itemHeight: 12, icon: "roundRect", textStyle: { color: "#3d403b", fontFamily: FONT, fontSize: 11 } },
    toolbox: { right: 4, top: 2, itemSize: 14, feature: { saveAsImage: { title: "Guardar imagen", name: "IMAI-variaciones", pixelRatio: 2, backgroundColor: "#fff" } }, iconStyle: { borderColor: "#8a8d86" } },
  };
}

// ---------------- IMFBCF: small multiples (niveles) ----------------
const IMFBCF_COLORS = {
  Total: COLORS.INK,
  Construccion: G,
  MyE: COLORS.CRIMSON,
  Residencial: Go,
  NoResidencial: COLORS.GOLD,
  Importado: COLORS.WINE,
};
const IMFBCF_LEVELS = [
  { key: "Total", col: 0, top: "IMFBCF" },
  { key: "Construccion", col: 3, top: "Construcción" },
  { key: "MyE", col: 6, top: "Maquinaria y equipo" },
  { key: "Residencial", col: 9, top: "Residencial" },
  { key: "NoResidencial", col: 11, top: "No residencial" },
  { key: "Importado", col: 19, top: "Maquinaria y equipo importado" },
];

export function buildImfbcfLevels(obs) {
  const periods = obs.map((o) => o.period);
  const grids = [], xAxes = [], yAxes = [], series = [], titles = [];
  const rotate = periods.length > 12;
  IMFBCF_LEVELS.forEach((cfg, i) => {
    const row = Math.floor(i / 2);
    const col = i % 2;
    const left = col === 0 ? "4%" : "54%";
    const top = row === 0 ? 20 : (row === 1 ? 225 : 430);
    const height = 165;
    const width = "42%";
    grids.push({ left, top, width, height, containLabel: false });
    xAxes.push({
      gridIndex: i, type: "category", data: periods, boundaryGap: false,
      axisLabel: { color: "#8a8d86", fontFamily: FONT, fontSize: rotate ? 8 : 9, interval: periods.length > 16 ? "auto" : 0, rotate: rotate ? 42 : 0 },
      axisLine: { lineStyle: { color: "#c9c2b2" } }, axisTick: { show: false },
    });
    yAxes.push({
      gridIndex: i, type: "value", name: "Índice (2018=100)", nameLocation: "middle", nameGap: 34,
      nameTextStyle: { color: "#6c6f6a", fontFamily: FONT, fontSize: 10, fontWeight: 500 },
      axisLabel: { color: "#8a8d86", fontFamily: FONT, fontSize: 10, formatter: (v) => v.toLocaleString("es-MX", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) },
      splitLine: { lineStyle: { color: "#ece7da" } }, axisLine: { show: false }, axisTick: { show: false }, scale: false,
    });
    const values = obs.map((o) => o.values[cfg.col] ?? null);
    const s = {
      name: cfg.top, type: "line", xAxisIndex: i, yAxisIndex: i,
      data: values, smooth: false, symbol: "circle", symbolSize: 3,
      lineStyle: { color: IMFBCF_COLORS[cfg.key], width: 2 },
      itemStyle: { color: IMFBCF_COLORS[cfg.key] },
      areaStyle: { color: IMFBCF_COLORS[cfg.key], opacity: 0.08 },
    };
    lastHighlight(s, periods, values, IMFBCF_COLORS[cfg.key], (v) => v == null ? "—" : v.toLocaleString("es-MX", { minimumFractionDigits: 1, maximumFractionDigits: 1 }));
    series.push(s);
    const yRange = computeYRange(values, { padding: 0.08, includeZero: false });
    if (yRange) { yAxes[i].min = yRange.min; yAxes[i].max = yRange.max; yAxes[i].scale = true; }
    titles.push({ text: cfg.top, left, top: top - 18, textStyle: { color: "#3d403b", fontFamily: FONT, fontSize: 12, fontWeight: 600 } });
  });
  return {
    animation: false, color: [COLORS.INK, G, COLORS.CRIMSON, Go, COLORS.GOLD, COLORS.WINE],
    title: titles, grid: grids, xAxis: xAxes, yAxis: yAxes, series,
    tooltip: {
      trigger: "axis", backgroundColor: "#fff", borderColor: "#ddd7c6", borderWidth: 1,
      textStyle: { color: COLORS.INK, fontFamily: FONT, fontSize: 12 },
      extraCssText: "box-shadow:0 5px 16px rgba(0,0,0,.13);border-radius:9px;",
      formatter: (params) => {
        if (!params || !params.length) return "";
        const p = params[0];
        const v = p.value;
        const val = v == null ? "—" : v.toLocaleString("es-MX", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
        return `<div style="font-family:'IBM Plex Mono',monospace;font-weight:600;color:#002f2a;margin-bottom:5px">${p.axisValue}</div>`
          + `<div style="display:flex;align-items:center;gap:8px;margin:2px 0">${p.marker}<span style="flex:1;color:#5c5f5a;font-size:11px">${p.seriesName}</span><span style="font-family:'IBM Plex Mono',monospace;font-weight:600">${val}</span></div>`;
      },
    },
    toolbox: { right: 4, top: 2, itemSize: 14, feature: { saveAsImage: { title: "Guardar imagen", name: "IMFBCF-niveles", pixelRatio: 2, backgroundColor: "#fff" } }, iconStyle: { borderColor: "#8a8d86" } },
  };
}

// ---------------- IMFBCF: variaciones mensuales y anuales ----------------
const IMFBCF_VAR = [
  { name: "IMFBCF", mom: 1, yoy: 2, color: COLORS.INK },
  { name: "Construcción", mom: 4, yoy: 5, color: G },
  { name: "Maquinaria y equipo", mom: 7, yoy: 8, color: COLORS.CRIMSON },
  { name: "Residencial", yoy: 10, color: Go },
  { name: "No residencial", yoy: 12, color: COLORS.GOLD },
  { name: "Importado", yoy: 20, color: COLORS.WINE },
];

export function buildImfbcfVariations(obs) {
  const periods = obs.map((o) => o.period);
  const grids = [
    { left: "4%", top: 50, width: "44%", height: 220, containLabel: false },
    { left: "54%", top: 50, width: "44%", height: 220, containLabel: false },
  ];
  const xAxes = grids.map((_, i) => ({
    gridIndex: i, type: "category", data: periods, boundaryGap: true,
    axisLabel: { color: "#8a8d86", fontFamily: FONT, fontSize: periods.length > 12 ? 8 : 9, interval: periods.length > 16 ? "auto" : 0, rotate: periods.length > 16 ? 42 : 0 },
    axisLine: { lineStyle: { color: "#c9c2b2" } }, axisTick: { show: false },
  }));
  const momAll = [];
  const yoyAll = [];
  const series = [];
  IMFBCF_VAR.forEach((cfg, si) => {
    const momData = cfg.mom == null ? [] : obs.map((o) => (o.values && o.values.length > cfg.mom ? o.values[cfg.mom] : null)).map((v) => v == null ? null : v * 100);
    const yoyData = obs.map((o) => (o.values && o.values.length > cfg.yoy ? o.values[cfg.yoy] : null)).map((v) => v == null ? null : v * 100);
    if (cfg.mom != null) momAll.push(...momData);
    yoyAll.push(...yoyData);
    if (cfg.mom != null) {
      series.push({
        name: cfg.name, type: "bar", xAxisIndex: 0, yAxisIndex: 0,
        data: momData, itemStyle: { color: cfg.color }, barMaxWidth: 10,
        emphasis: { focus: "series" },
        markLine: si === 0 ? { symbol: "none", data: [{ yAxis: 0, lineStyle: { color: COLORS.GRAY, type: "dashed", width: 1 }, label: { show: false } }], animation: false } : undefined,
      });
    }
    series.push({
      name: cfg.name, type: "bar", xAxisIndex: 1, yAxisIndex: 1,
      data: yoyData, itemStyle: { color: cfg.color }, barMaxWidth: 10,
      emphasis: { focus: "series" },
      markLine: si === 0 ? { symbol: "none", data: [{ yAxis: 0, lineStyle: { color: COLORS.GRAY, type: "dashed", width: 1 }, label: { show: false } }], animation: false } : undefined,
    });
  });
  const momRange = momAll.length ? computeYRange(momAll, { padding: 0.12, includeZero: true }) : null;
  const yoyRange = computeYRange(yoyAll, { padding: 0.12, includeZero: true });
  const yAxis = grids.map((_, i) => {
    const range = i === 0 ? momRange : yoyRange;
    const ay = {
      gridIndex: i, type: "value", name: i === 0 ? "Variación mensual desest. (%)" : "Variación anual desest. (%)", nameLocation: "middle", nameGap: 40,
      nameTextStyle: { color: "#6c6f6a", fontFamily: FONT, fontSize: 11, fontWeight: 500 },
      axisLabel: { color: "#8a8d86", fontFamily: FONT, fontSize: 10, formatter: (v) => v.toFixed(1) + "%" },
      splitLine: { lineStyle: { color: "#ece7da" } }, axisLine: { show: false }, axisTick: { show: false }, scale: false,
    };
    if (range) { ay.min = range.min; ay.max = range.max; }
    return ay;
  });
  return {
    animation: false, color: [COLORS.INK, G, COLORS.CRIMSON, Go, COLORS.GOLD, COLORS.WINE],
    grid: grids, xAxis: xAxes, yAxis,
    series,
    tooltip: {
      trigger: "axis", backgroundColor: "#fff", borderColor: "#ddd7c6", borderWidth: 1,
      textStyle: { color: COLORS.INK, fontFamily: FONT, fontSize: 12 },
      extraCssText: "box-shadow:0 5px 16px rgba(0,0,0,.13);border-radius:9px;",
      formatter: (params) => {
        if (!params || !params.length) return "";
        const p0 = params[0];
        let html = `<div style="font-family:'IBM Plex Mono',monospace;font-weight:600;color:#002f2a;margin-bottom:5px">${p0.axisValue}</div>`;
        params.forEach((p) => {
          const cfg = IMFBCF_VAR.find((c) => c.name === p.seriesName);
          html += pctTip(p.value, p.seriesName, cfg ? cfg.color : COLORS.GRAY);
        });
        return html;
      },
    },
    legend: { top: 10, left: "center", itemWidth: 12, itemHeight: 12, icon: "roundRect", textStyle: { color: "#3d403b", fontFamily: FONT, fontSize: 11 } },
    toolbox: { right: 4, top: 2, itemSize: 14, feature: { saveAsImage: { title: "Guardar imagen", name: "IMFBCF-variaciones", pixelRatio: 2, backgroundColor: "#fff" } }, iconStyle: { borderColor: "#8a8d86" } },
  };
}

// ---------------- EMIM: small multiples (niveles) ----------------
const EMIM_COLORS = { Produccion: COLORS.INK, Personal: G, Horas: COLORS.CRIMSON, Remuneraciones: Go };
const EMIM_LEVELS = [
  { key: "Produccion", col: 0, top: "Producción" },
  { key: "Personal", col: 5, top: "Personal ocupado" },
  { key: "Horas", col: 10, top: "Horas trabajadas" },
  { key: "Remuneraciones", col: 15, top: "Remuneraciones medias reales" },
];

export function buildEmimLevels(obs) {
  const periods = obs.map((o) => o.period);
  const grids = [], xAxes = [], yAxes = [], series = [], titles = [];
  const rotate = periods.length > 12;
  EMIM_LEVELS.forEach((cfg, i) => {
    const row = Math.floor(i / 2);
    const col = i % 2;
    const left = col === 0 ? "4%" : "54%";
    const top = row === 0 ? 20 : 225;
    const height = 165;
    const width = "42%";
    grids.push({ left, top, width, height, containLabel: false });
    xAxes.push({
      gridIndex: i, type: "category", data: periods, boundaryGap: false,
      axisLabel: { color: "#8a8d86", fontFamily: FONT, fontSize: rotate ? 8 : 9, interval: periods.length > 16 ? "auto" : 0, rotate: rotate ? 42 : 0 },
      axisLine: { lineStyle: { color: "#c9c2b2" } }, axisTick: { show: false },
    });
    yAxes.push({
      gridIndex: i, type: "value", name: "Índice (2018=100)", nameLocation: "middle", nameGap: 34,
      nameTextStyle: { color: "#6c6f6a", fontFamily: FONT, fontSize: 10, fontWeight: 500 },
      axisLabel: { color: "#8a8d86", fontFamily: FONT, fontSize: 10, formatter: (v) => v.toLocaleString("es-MX", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) },
      splitLine: { lineStyle: { color: "#ece7da" } }, axisLine: { show: false }, axisTick: { show: false }, scale: false,
    });
    const values = obs.map((o) => (o.values && o.values.length > cfg.col ? o.values[cfg.col] : null));
    const s = {
      name: cfg.top, type: "line", xAxisIndex: i, yAxisIndex: i,
      data: values, smooth: false, symbol: "circle", symbolSize: 3,
      lineStyle: { color: EMIM_COLORS[cfg.key], width: 2 },
      itemStyle: { color: EMIM_COLORS[cfg.key] },
      areaStyle: { color: EMIM_COLORS[cfg.key], opacity: 0.08 },
    };
    lastHighlight(s, periods, values, EMIM_COLORS[cfg.key], (v) => v == null ? "—" : v.toLocaleString("es-MX", { minimumFractionDigits: 1, maximumFractionDigits: 1 }));
    series.push(s);
    const yRange = computeYRange(values, { padding: 0.08, includeZero: false });
    if (yRange) { yAxes[i].min = yRange.min; yAxes[i].max = yRange.max; yAxes[i].scale = true; }
    titles.push({ text: cfg.top, left, top: top - 18, textStyle: { color: "#3d403b", fontFamily: FONT, fontSize: 12, fontWeight: 600 } });
  });
  return {
    animation: false, color: [COLORS.INK, G, COLORS.CRIMSON, Go],
    title: titles, grid: grids, xAxis: xAxes, yAxis: yAxes, series,
    tooltip: {
      trigger: "axis", backgroundColor: "#fff", borderColor: "#ddd7c6", borderWidth: 1,
      textStyle: { color: COLORS.INK, fontFamily: FONT, fontSize: 12 },
      extraCssText: "box-shadow:0 5px 16px rgba(0,0,0,.13);border-radius:9px;",
      formatter: (params) => {
        if (!params || !params.length) return "";
        const p = params[0];
        const v = p.value;
        const val = v == null ? "—" : v.toLocaleString("es-MX", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
        return `<div style="font-family:'IBM Plex Mono',monospace;font-weight:600;color:#002f2a;margin-bottom:5px">${p.axisValue}</div>`
          + `<div style="display:flex;align-items:center;gap:8px;margin:2px 0">${p.marker}<span style="flex:1;color:#5c5f5a;font-size:11px">${p.seriesName}</span><span style="font-family:'IBM Plex Mono',monospace;font-weight:600">${val}</span></div>`;
      },
    },
    toolbox: { right: 4, top: 2, itemSize: 14, feature: { saveAsImage: { title: "Guardar imagen", name: "EMIM-niveles", pixelRatio: 2, backgroundColor: "#fff" } }, iconStyle: { borderColor: "#8a8d86" } },
  };
}

// ---------------- EMIM: variaciones anuales (originales + desest del último dato) ----------------
const EMIM_VAR = [
  { name: "Producción", orig: 2, desest: 4, color: COLORS.INK },
  { name: "Personal ocupado", orig: 7, desest: 9, color: G },
  { name: "Horas trabajadas", orig: 12, desest: 14, color: COLORS.CRIMSON },
  { name: "Remuneraciones medias reales", orig: null, desest: 17, color: Go },
];

function lastNonNullIndex(obs, col) {
  for (let i = obs.length - 1; i >= 0; i--) {
    if (obs[i].values && obs[i].values[col] != null) return i;
  }
  return -1;
}

export function buildEmimVariations(obs) {
  const periods = obs.map((o) => o.period);
  const yoyAll = [];
  const series = [];
  EMIM_VAR.forEach((cfg, si) => {
    if (cfg.orig != null) {
      const yoyData = obs.map((o) => (o.values && o.values.length > cfg.orig && o.values[cfg.orig] != null ? o.values[cfg.orig] * 100 : null));
      yoyAll.push(...yoyData);
      series.push({
        name: cfg.name, type: "bar",
        data: yoyData, itemStyle: { color: cfg.color }, barMaxWidth: 12,
        emphasis: { focus: "series" },
        markLine: si === 0 ? { symbol: "none", data: [{ yAxis: 0, lineStyle: { color: COLORS.GRAY, type: "dashed", width: 1 }, label: { show: false } }], animation: false } : undefined,
      });
    }
    if (cfg.desest != null) {
      const lastI = lastNonNullIndex(obs, cfg.desest);
      const desestData = obs.map((o, i) => {
        if (i !== lastI) return null;
        if (!o.values || o.values.length <= cfg.desest || o.values[cfg.desest] == null) return null;
        return o.values[cfg.desest] * 100;
      });
      yoyAll.push(...desestData);
      series.push({
        name: `${cfg.name} (desest.)`, type: "line",
        data: desestData, itemStyle: { color: cfg.color },
        symbol: "circle", symbolSize: 8, showSymbol: true,
        lineStyle: { color: cfg.color, type: "dashed", width: 2 },
        emphasis: { focus: "series" },
      });
    }
  });
  const yoyRange = computeYRange(yoyAll, { padding: 0.12, includeZero: true });
  const yAxis = {
    type: "value", name: "Variación anual (%)", nameLocation: "middle", nameGap: 40,
    nameTextStyle: { color: "#6c6f6a", fontFamily: FONT, fontSize: 11, fontWeight: 500 },
    axisLabel: { color: "#8a8d86", fontFamily: FONT, fontSize: 10, formatter: (v) => v.toFixed(1) + "%" },
    splitLine: { lineStyle: { color: "#ece7da" } }, axisLine: { show: false }, axisTick: { show: false }, scale: false,
  };
  if (yoyRange) { yAxis.min = yoyRange.min; yAxis.max = yoyRange.max; }
  return {
    animation: false, color: [COLORS.INK, G, COLORS.CRIMSON, Go],
    grid: { left: "4%", right: "4%", top: 50, height: 240, containLabel: false },
    xAxis: { type: "category", data: periods, boundaryGap: true, axisLabel: { color: "#8a8d86", fontFamily: FONT, fontSize: periods.length > 12 ? 8 : 9, interval: periods.length > 16 ? "auto" : 0, rotate: periods.length > 16 ? 42 : 0 }, axisLine: { lineStyle: { color: "#c9c2b2" } }, axisTick: { show: false } },
    yAxis,
    series,
    tooltip: {
      trigger: "axis", backgroundColor: "#fff", borderColor: "#ddd7c6", borderWidth: 1,
      textStyle: { color: COLORS.INK, fontFamily: FONT, fontSize: 12 },
      extraCssText: "box-shadow:0 5px 16px rgba(0,0,0,.13);border-radius:9px;",
      formatter: (params) => {
        if (!params || !params.length) return "";
        const p0 = params[0];
        let html = `<div style="font-family:'IBM Plex Mono',monospace;font-weight:600;color:#002f2a;margin-bottom:5px">${p0.axisValue}</div>`;
        params.forEach((p) => {
          const cfg = EMIM_VAR.find((c) => p.seriesName === c.name || p.seriesName === `${c.name} (desest.)`);
          html += pctTip(p.value, p.seriesName, cfg ? cfg.color : COLORS.GRAY);
        });
        return html;
      },
    },
    legend: { top: 10, left: "center", itemWidth: 12, itemHeight: 12, icon: "roundRect", textStyle: { color: "#3d403b", fontFamily: FONT, fontSize: 11 } },
    toolbox: { right: 4, top: 2, itemSize: 14, feature: { saveAsImage: { title: "Guardar imagen", name: "EMIM-variaciones", pixelRatio: 2, backgroundColor: "#fff" } }, iconStyle: { borderColor: "#8a8d86" } },
  };
}

// ---------------- BCMM: niveles y componentes ----------------
const BCMM_LEVELS = [
  {
    top: "Exportaciones e importaciones",
    cols: [
      { name: "Exportaciones", col: 0, color: COLORS.GREEN },
      { name: "Importaciones", col: 1, color: COLORS.CRIMSON },
    ],
    yName: "Millones de dólares",
    fmt: (v) => v == null ? "—" : v.toLocaleString("es-MX", { maximumFractionDigits: 0 }),
  },
  {
    top: "Saldo comercial",
    cols: [{ name: "Saldo", col: 2, color: COLORS.INK }],
    yName: "Millones de dólares",
    fmt: (v) => v == null ? "—" : v.toLocaleString("es-MX", { maximumFractionDigits: 0 }),
    includeZero: true,
  },
  {
    top: "Exportaciones por origen",
    cols: [
      { name: "Petroleras", col: 6, color: COLORS.GOLD },
      { name: "No petroleras", col: 8, color: COLORS.GREEN },
      { name: "Manufactureras", col: 20, color: G },
      { name: "Agropecuarias", col: 21, color: Go },
      { name: "Extractivas", col: 22, color: COLORS.CRIMSON },
    ],
    yName: "Millones de dólares",
    fmt: (v) => v == null ? "—" : v.toLocaleString("es-MX", { maximumFractionDigits: 0 }),
  },
  {
    top: "Importaciones por tipo de bien",
    cols: [
      { name: "Consumo", col: 14, color: COLORS.GOLD },
      { name: "Intermedios", col: 15, color: G },
      { name: "Capital", col: 16, color: COLORS.CRIMSON },
    ],
    yName: "Millones de dólares",
    fmt: (v) => v == null ? "—" : v.toLocaleString("es-MX", { maximumFractionDigits: 0 }),
  },
];

function moneyTip(value, name, color) {
  if (value == null) return "";
  const s = value < 0 ? "−" : "";
  const txt = s + "$" + Math.abs(value).toLocaleString("es-MX", { maximumFractionDigits: 0 }) + " mdd";
  return `<div style="display:flex;align-items:center;gap:8px;margin:2px 0"><span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:${color}"></span><span style="flex:1;color:#5c5f5a;font-size:11px">${name}</span><span style="font-family:'IBM Plex Mono',monospace;font-weight:600">${txt}</span></div>`;
}

export function buildBcmmLevels(obs) {
  const periods = obs.map((o) => o.period);
  const grids = [], xAxes = [], yAxes = [], series = [], titles = [];
  const rotate = periods.length > 12;
  BCMM_LEVELS.forEach((cfg, i) => {
    const row = Math.floor(i / 2);
    const col = i % 2;
    const left = col === 0 ? "4%" : "54%";
    const top = row === 0 ? 20 : 260;
    const height = 190;
    const width = "42%";
    grids.push({ left, top, width, height, containLabel: false });
    xAxes.push({
      gridIndex: i, type: "category", data: periods, boundaryGap: false,
      axisLabel: { color: "#8a8d86", fontFamily: FONT, fontSize: rotate ? 8 : 9, interval: periods.length > 16 ? "auto" : 0, rotate: rotate ? 42 : 0 },
      axisLine: { lineStyle: { color: "#c9c2b2" } }, axisTick: { show: false },
    });
    yAxes.push({
      gridIndex: i, type: "value", name: cfg.yName, nameLocation: "middle", nameGap: 36,
      nameTextStyle: { color: "#6c6f6a", fontFamily: FONT, fontSize: 10, fontWeight: 500 },
      axisLabel: { color: "#8a8d86", fontFamily: FONT, fontSize: 10, formatter: (v) => v.toLocaleString("es-MX", { maximumFractionDigits: 0 }) },
      splitLine: { lineStyle: { color: "#ece7da" } }, axisLine: { show: false }, axisTick: { show: false }, scale: false,
    });
    let allValues = [];
    cfg.cols.forEach((c) => {
      const values = obs.map((o) => (o.values && o.values.length > c.col ? o.values[c.col] : null));
      allValues = allValues.concat(values);
      const s = {
        name: c.name, type: "line", xAxisIndex: i, yAxisIndex: i,
        data: values, smooth: false, symbol: "circle", symbolSize: 3,
        lineStyle: { color: c.color, width: 2 }, itemStyle: { color: c.color },
        areaStyle: cfg.cols.length === 1 ? { color: c.color, opacity: 0.08 } : undefined,
      };
      lastHighlight(s, periods, values, c.color, cfg.fmt);
      series.push(s);
    });
    const yRange = computeYRange(allValues, { padding: 0.08, includeZero: cfg.includeZero || false });
    if (yRange) { yAxes[i].min = yRange.min; yAxes[i].max = yRange.max; yAxes[i].scale = true; }
    titles.push({ text: cfg.top, left, top: top - 18, textStyle: { color: "#3d403b", fontFamily: FONT, fontSize: 12, fontWeight: 600 } });
  });
  return {
    animation: false,
    color: [COLORS.GREEN, COLORS.CRIMSON, COLORS.INK, COLORS.GOLD, G, Go],
    title: titles, grid: grids, xAxis: xAxes, yAxis: yAxes, series,
    tooltip: {
      trigger: "axis", backgroundColor: "#fff", borderColor: "#ddd7c6", borderWidth: 1,
      textStyle: { color: COLORS.INK, fontFamily: FONT, fontSize: 12 },
      extraCssText: "box-shadow:0 5px 16px rgba(0,0,0,.13);border-radius:9px;",
      formatter: (params) => {
        if (!params || !params.length) return "";
        const p0 = params[0];
        let html = `<div style="font-family:'IBM Plex Mono',monospace;font-weight:600;color:#002f2a;margin-bottom:5px">${p0.axisValue}</div>`;
        params.forEach((p) => {
          html += moneyTip(p.value, p.seriesName, p.color);
        });
        return html;
      },
    },
    legend: { top: 10, left: "center", itemWidth: 12, itemHeight: 12, icon: "roundRect", textStyle: { color: "#3d403b", fontFamily: FONT, fontSize: 11 } },
    toolbox: { right: 4, top: 2, itemSize: 14, feature: { saveAsImage: { title: "Guardar imagen", name: "BCMM-niveles", pixelRatio: 2, backgroundColor: "#fff" } }, iconStyle: { borderColor: "#8a8d86" } },
  };
}

// ---------------- BCMM: variaciones anuales ----------------
const BCMM_VAR = [
  { top: "Total", cols: [
    { name: "Exportaciones", col: 3, color: COLORS.GREEN },
    { name: "Importaciones", col: 4, color: COLORS.CRIMSON },
    { name: "Saldo", col: 5, color: COLORS.INK },
  ]},
  { top: "Exportaciones petrolero / no petrolero", cols: [
    { name: "Exp. petroleras", col: 10, color: COLORS.GOLD },
    { name: "Exp. no petroleras", col: 12, color: COLORS.GREEN },
  ]},
  { top: "Importaciones petrolero / no petrolero", cols: [
    { name: "Imp. petroleras", col: 11, color: COLORS.GOLD },
    { name: "Imp. no petroleras", col: 13, color: COLORS.CRIMSON },
  ]},
  { top: "Importaciones por tipo de bien", cols: [
    { name: "Consumo", col: 17, color: COLORS.GOLD },
    { name: "Intermedios", col: 18, color: G },
    { name: "Capital", col: 19, color: COLORS.CRIMSON },
  ]},
  { top: "Exportaciones no petroleras por origen", cols: [
    { name: "Manufactureras", col: 23, color: G },
    { name: "Agropecuarias", col: 24, color: Go },
    { name: "Extractivas", col: 25, color: COLORS.CRIMSON },
  ]},
];

export function buildBcmmVariations(obs) {
  const periods = obs.map((o) => o.period);
  const grids = [], xAxes = [], yAxes = [], series = [], titles = [];
  const rotate = periods.length > 12;
  BCMM_VAR.forEach((cfg, i) => {
    const row = Math.floor(i / 3);
    const col = i % 3;
    const left = col === 0 ? "4%" : (col === 1 ? "36%" : "68%");
    const top = row === 0 ? 40 : 300;
    const width = "28%";
    const height = 200;
    grids.push({ left, top, width, height, containLabel: false });
    xAxes.push({
      gridIndex: i, type: "category", data: periods, boundaryGap: true,
      axisLabel: { color: "#8a8d86", fontFamily: FONT, fontSize: rotate ? 8 : 9, interval: periods.length > 16 ? "auto" : 0, rotate: rotate ? 42 : 0 },
      axisLine: { lineStyle: { color: "#c9c2b2" } }, axisTick: { show: false },
    });
    yAxes.push({
      gridIndex: i, type: "value", name: "Variación anual (%)", nameLocation: "middle", nameGap: 34,
      nameTextStyle: { color: "#6c6f6a", fontFamily: FONT, fontSize: 10, fontWeight: 500 },
      axisLabel: { color: "#8a8d86", fontFamily: FONT, fontSize: 10, formatter: (v) => v.toFixed(1) + "%" },
      splitLine: { lineStyle: { color: "#ece7da" } }, axisLine: { show: false }, axisTick: { show: false }, scale: false,
    });
    let allValues = [];
    cfg.cols.forEach((c, ci) => {
      const values = obs.map((o) => {
        if (!o.values || o.values.length <= c.col || o.values[c.col] == null) return null;
        return o.values[c.col] * 100;
      });
      allValues = allValues.concat(values);
      const s = {
        name: c.name, type: "bar", xAxisIndex: i, yAxisIndex: i,
        data: values, itemStyle: { color: c.color }, barMaxWidth: 10,
        emphasis: { focus: "series" },
        markLine: ci === 0 ? { symbol: "none", data: [{ yAxis: 0, lineStyle: { color: COLORS.GRAY, type: "dashed", width: 1 }, label: { show: false } }], animation: false } : undefined,
      };
      series.push(s);
    });
    const yRange = computeYRange(allValues, { padding: 0.12, includeZero: true });
    if (yRange) { yAxes[i].min = yRange.min; yAxes[i].max = yRange.max; }
    titles.push({ text: cfg.top, left, top: top - 25, textStyle: { color: "#3d403b", fontFamily: FONT, fontSize: 11, fontWeight: 600 } });
  });
  return {
    animation: false,
    color: [COLORS.GREEN, COLORS.CRIMSON, COLORS.INK, COLORS.GOLD, G, Go],
    title: titles, grid: grids, xAxis: xAxes, yAxis: yAxes, series,
    tooltip: {
      trigger: "axis", backgroundColor: "#fff", borderColor: "#ddd7c6", borderWidth: 1,
      textStyle: { color: COLORS.INK, fontFamily: FONT, fontSize: 12 },
      extraCssText: "box-shadow:0 5px 16px rgba(0,0,0,.13);border-radius:9px;",
      formatter: (params) => {
        if (!params || !params.length) return "";
        const p0 = params[0];
        let html = `<div style="font-family:'IBM Plex Mono',monospace;font-weight:600;color:#002f2a;margin-bottom:5px">${p0.axisValue}</div>`;
        params.forEach((p) => {
          html += pctTip(p.value, p.seriesName, p.color);
        });
        return html;
      },
    },
    legend: { top: 10, left: "center", itemWidth: 12, itemHeight: 12, icon: "roundRect", textStyle: { color: "#3d403b", fontFamily: FONT, fontSize: 11 } },
    toolbox: { right: 4, top: 2, itemSize: 14, feature: { saveAsImage: { title: "Guardar imagen", name: "BCMM-variaciones", pixelRatio: 2, backgroundColor: "#fff" } }, iconStyle: { borderColor: "#8a8d86" } },
  };
}


// ---------------- DESOCUP: small multiples de tasas laborales ----------------
export function buildDesocupRates(ind, obs) {
  const periods = obs.map((o) => o.period);
  const rotate = periods.length > 12;
  const rateCfgs = [
    { col: 0, name: "Tasa de desocupación", color: COLORS.CRIMSON },
    { col: 1, name: "Tasa de participación", color: COLORS.GREEN },
    { col: 2, name: "Tasa de informalidad", color: COLORS.GOLD },
    { col: 3, name: "Tasa de subocupación", color: COLORS.TEAL },
  ];
  const grids = [], xAxes = [], yAxes = [], series = [], titles = [];
  rateCfgs.forEach((cfg, i) => {
    const row = Math.floor(i / 2);
    const col = i % 2;
    const left = col === 0 ? "4%" : "54%";
    const top = row === 0 ? 20 : 225;
    const height = 165;
    const width = "42%";
    grids.push({ left, top, width, height, containLabel: false });
    xAxes.push({
      gridIndex: i, type: "category", data: periods, boundaryGap: false,
      axisLabel: { color: "#8a8d86", fontFamily: FONT, fontSize: rotate ? 8 : 9, interval: periods.length > 16 ? "auto" : 0, rotate: rotate ? 42 : 0 },
      axisLine: { lineStyle: { color: "#c9c2b2" } }, axisTick: { show: false },
    });
    yAxes.push({
      gridIndex: i, type: "value", name: "%", nameLocation: "middle", nameGap: 30,
      nameTextStyle: { color: "#6c6f6a", fontFamily: FONT, fontSize: 10, fontWeight: 500 },
      axisLabel: { color: "#8a8d86", fontFamily: FONT, fontSize: 10, formatter: (v) => v.toFixed(1) + "%" },
      splitLine: { lineStyle: { color: "#ece7da" } }, axisLine: { show: false }, axisTick: { show: false }, scale: false,
    });
    const values = obs.map((o) => o.values[cfg.col] ?? null);
    const s = {
      name: cfg.name, type: "line", xAxisIndex: i, yAxisIndex: i,
      data: values, smooth: false, symbol: "circle", symbolSize: 3,
      lineStyle: { color: cfg.color, width: 2 },
      itemStyle: { color: cfg.color },
      areaStyle: { color: cfg.color, opacity: 0.08 },
    };
    lastHighlight(s, periods, values, cfg.color, (v) => v == null ? "—" : v.toFixed(1) + "%");
    series.push(s);
    const yRange = computeYRange(values, { padding: 0.08, includeZero: false });
    if (yRange) { yAxes[i].min = yRange.min; yAxes[i].max = yRange.max; yAxes[i].scale = true; }
    titles.push({ text: cfg.name, left, top: top - 18, textStyle: { color: "#3d403b", fontFamily: FONT, fontSize: 12, fontWeight: 600 } });
  });
  return {
    animation: false, color: rateCfgs.map((c) => c.color),
    title: titles, grid: grids, xAxis: xAxes, yAxis: yAxes, series,
    tooltip: {
      trigger: "axis", backgroundColor: "#fff", borderColor: "#ddd7c6", borderWidth: 1,
      textStyle: { color: COLORS.INK, fontFamily: FONT, fontSize: 12 },
      extraCssText: "box-shadow:0 5px 16px rgba(0,0,0,.13);border-radius:9px;",
      formatter: (params) => {
        if (!params || !params.length) return "";
        const p = params[0];
        const v = p.value;
        const val = v == null ? "—" : v.toFixed(1) + "%";
        return `<div style="font-family:'IBM Plex Mono',monospace;font-weight:600;color:#002f2a;margin-bottom:5px">${p.axisValue}</div>`
          + `<div style="display:flex;align-items:center;gap:8px;margin:2px 0">${p.marker}<span style="flex:1;color:#5c5f5a;font-size:11px">${p.seriesName}</span><span style="font-family:'IBM Plex Mono',monospace;font-weight:600">${val}</span></div>`;
      },
    },
    toolbox: { right: 4, top: 2, itemSize: 14, feature: { saveAsImage: { title: "Guardar imagen", name: "desocup-rates", pixelRatio: 2, backgroundColor: "#fff" } }, iconStyle: { borderColor: "#8a8d86" } },
  };
}

// ---------------- DESOCUP: población ocupada (trimestral) ----------------
export function buildDesocupPoblacion(ind, obs) {
  const periods = obs.map((o) => o.q_period || o.period);
  const rotate = periods.length > 12;
  const values = obs.map((o) => o.values[4] ?? null);
  const yRange = computeYRange(values, { padding: 0.1, includeZero: false });
  const yAxis = {
    type: "value", name: "Millones de personas", nameLocation: "middle", nameGap: 40,
    nameTextStyle: { color: "#6c6f6a", fontFamily: FONT, fontSize: 11, fontWeight: 500 },
    axisLabel: { color: "#8a8d86", fontFamily: FONT, fontSize: 10, formatter: (v) => v.toLocaleString("es-MX", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) },
    splitLine: { lineStyle: { color: "#ece7da" } }, axisLine: { show: false }, axisTick: { show: false }, scale: false,
  };
  if (yRange) { yAxis.min = yRange.min; yAxis.max = yRange.max; yAxis.scale = true; }
  const s = {
    name: "Población ocupada", type: "line",
    data: values, smooth: false, symbol: "circle", symbolSize: 4,
    lineStyle: { color: COLORS.GREEN, width: 2.5 },
    itemStyle: { color: COLORS.GREEN },
    areaStyle: { color: COLORS.GREEN, opacity: 0.08 },
  };
  lastHighlight(s, periods, values, COLORS.GREEN, (v) => v == null ? "—" : v.toLocaleString("es-MX", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + " millones");
  return {
    animation: false,
    grid: { left: "8%", right: "4%", top: 40, height: 220, containLabel: false },
    xAxis: { type: "category", data: periods, boundaryGap: false, axisLabel: { color: "#8a8d86", fontFamily: FONT, fontSize: rotate ? 8 : 9, interval: periods.length > 16 ? "auto" : 0, rotate: rotate ? 42 : 0 }, axisLine: { lineStyle: { color: "#c9c2b2" } }, axisTick: { show: false } },
    yAxis,
    series: [s],
    tooltip: {
      trigger: "axis", backgroundColor: "#fff", borderColor: "#ddd7c6", borderWidth: 1,
      textStyle: { color: COLORS.INK, fontFamily: FONT, fontSize: 12 },
      extraCssText: "box-shadow:0 5px 16px rgba(0,0,0,.13);border-radius:9px;",
      formatter: (params) => {
        if (!params || !params.length) return "";
        const p = params[0];
        const v = p.value;
        const val = v == null ? "—" : v.toLocaleString("es-MX", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + " millones de personas";
        return `<div style="font-family:'IBM Plex Mono',monospace;font-weight:600;color:#002f2a;margin-bottom:5px">${p.axisValue}</div>`
          + `<div style="display:flex;align-items:center;gap:8px;margin:2px 0">${p.marker}<span style="flex:1;color:#5c5f5a;font-size:11px">Población ocupada</span><span style="font-family:'IBM Plex Mono',monospace;font-weight:600">${val}</span></div>`;
      },
    },
    toolbox: { right: 4, top: 2, itemSize: 14, feature: { saveAsImage: { title: "Guardar imagen", name: "desocup-poblacion", pixelRatio: 2, backgroundColor: "#fff" } }, iconStyle: { borderColor: "#8a8d86" } },
  };
}

// ---------------- RESERVAS: nivel semanal y cambio semanal ----------------
export function buildReservasLevel(obs) {
  const periods = obs.map((o) => o.period);
  const values = obs.map((o) => o.values?.[0] ?? null);
  const yRange = computeYRange(values, { padding: 0.08, includeZero: false });
  return {
    animation: false,
    color: [COLORS.GREEN],
    grid: { left: 66, right: 24, top: 52, bottom: 44 },
    legend: { show: false },
    tooltip: {
      trigger: "axis",
      backgroundColor: "#fff", borderColor: "#ddd7c6", borderWidth: 1,
      textStyle: { color: COLORS.INK, fontFamily: FONT, fontSize: 12 },
      extraCssText: "box-shadow:0 5px 16px rgba(0,0,0,.13);border-radius:9px;",
      formatter: (params) => {
        const p = params[0];
        const v = p.value;
        const val = v == null ? "—" : fmtVal(v, "mdd");
        return `<div style="font-family:'IBM Plex Mono',monospace;font-weight:600;color:#002f2a;margin-bottom:5px">${p.axisValue}</div>`
          + `<div style="display:flex;align-items:center;gap:8px;margin:2px 0">${p.marker}<span style="flex:1;color:#5c5f5a;font-size:11px">Reserva internacional</span><span style="font-family:'IBM Plex Mono',monospace;font-weight:600">${val}</span></div>`;
      },
    },
    toolbox: { right: 4, top: 2, itemSize: 14, feature: { saveAsImage: { title: "Guardar imagen", name: "reservas-nivel", pixelRatio: 2, backgroundColor: "#fff" } }, iconStyle: { borderColor: "#8a8d86" } },
    xAxis: {
      type: "category", data: periods, boundaryGap: false,
      axisLabel: { color: "#8a8d86", fontFamily: FONT, fontSize: periods.length > 16 ? 9 : 10, rotate: periods.length > 16 ? 42 : 0, interval: periods.length > 24 ? "auto" : 0 },
      axisLine: { lineStyle: { color: "#c9c2b2" } }, axisTick: { show: false },
    },
    yAxis: (() => {
      const ay = { type: "value", name: "Millones de dólares", nameLocation: "middle", nameGap: 52,
        nameTextStyle: { color: "#6c6f6a", fontFamily: FONT, fontSize: 11, fontWeight: 500 },
        axisLabel: { color: "#8a8d86", fontFamily: FONT, fontSize: 11, formatter: (v) => fmtVal(v, "mdd") },
        splitLine: { lineStyle: { color: "#ece7da" } }, axisLine: { show: false }, axisTick: { show: false }, scale: true,
      };
      if (yRange) { ay.min = yRange.min; ay.max = yRange.max; }
      return ay;
    })(),
    series: [{
      name: "Reserva internacional", type: "line", data: values,
      smooth: false, symbol: "circle", symbolSize: 4,
      lineStyle: { color: COLORS.GREEN, width: 2.4 },
      itemStyle: { color: COLORS.GREEN },
      areaStyle: { color: COLORS.GREEN, opacity: 0.08 },
    }],
  };
}

export function buildReservasChange(obs) {
  const periods = obs.map((o) => o.period);
  const changes = obs.map((o) => o.values?.[1] ?? null);
  const yRange = computeYRange(changes, { padding: 0.12, includeZero: true });
  return {
    animation: false,
    color: [COLORS.GREEN],
    grid: { left: 66, right: 24, top: 52, bottom: 44 },
    legend: { show: false },
    tooltip: {
      trigger: "axis",
      backgroundColor: "#fff", borderColor: "#ddd7c6", borderWidth: 1,
      textStyle: { color: COLORS.INK, fontFamily: FONT, fontSize: 12 },
      extraCssText: "box-shadow:0 5px 16px rgba(0,0,0,.13);border-radius:9px;",
      formatter: (params) => {
        const p = params[0];
        const v = p.value;
        const val = v == null ? "—" : fmtVal(v, "mdd-signed");
        return `<div style="font-family:'IBM Plex Mono',monospace;font-weight:600;color:#002f2a;margin-bottom:5px">${p.axisValue}</div>`
          + `<div style="display:flex;align-items:center;gap:8px;margin:2px 0">${p.marker}<span style="flex:1;color:#5c5f5a;font-size:11px">Cambio semanal</span><span style="font-family:'IBM Plex Mono',monospace;font-weight:600">${val}</span></div>`;
      },
    },
    toolbox: { right: 4, top: 2, itemSize: 14, feature: { saveAsImage: { title: "Guardar imagen", name: "reservas-cambio", pixelRatio: 2, backgroundColor: "#fff" } }, iconStyle: { borderColor: "#8a8d86" } },
    xAxis: {
      type: "category", data: periods, boundaryGap: true,
      axisLabel: { color: "#8a8d86", fontFamily: FONT, fontSize: periods.length > 16 ? 9 : 10, rotate: periods.length > 16 ? 42 : 0, interval: periods.length > 24 ? "auto" : 0 },
      axisLine: { lineStyle: { color: "#c9c2b2" } }, axisTick: { show: false },
    },
    yAxis: (() => {
      const ay = { type: "value", name: "Cambio semanal (mdd)", nameLocation: "middle", nameGap: 52,
        nameTextStyle: { color: "#6c6f6a", fontFamily: FONT, fontSize: 11, fontWeight: 500 },
        axisLabel: { color: "#8a8d86", fontFamily: FONT, fontSize: 11, formatter: (v) => fmtVal(v, "mdd-signed") },
        splitLine: { lineStyle: { color: "#ece7da" } }, axisLine: { show: false }, axisTick: { show: false }, scale: false,
      };
      if (yRange) { ay.min = yRange.min; ay.max = yRange.max; }
      return ay;
    })(),
    series: [{
      name: "Cambio semanal", type: "bar", data: changes,
      itemStyle: {
        color: (p) => p.value == null ? COLORS.GRAY : (p.value >= 0 ? COLORS.GREEN : COLORS.CRIMSON),
      },
      barMaxWidth: 12,
      markLine: { symbol: "none", data: [{ yAxis: 0, lineStyle: { color: COLORS.GRAY, type: "dashed", width: 1 }, label: { show: false } }], animation: false },
    }],
  };
}
