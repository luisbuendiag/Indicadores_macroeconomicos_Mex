// Motor de métricas determinista: series primarias, KPIs y análisis textual.
// Portado del dashboard legado (DCLogic) al modelo de datos abierto.
import { KPICFG, COLORS } from "./config.js";
import { fmtVal, perLong, enFrase, respFrase, isTrim } from "./format.js";

function periods(ind) { return ind.observations.map((o) => o.period); }
function valAt(ind, i, col) {
  const o = ind.observations[i];
  return o ? (o.values[col] ?? null) : null;
}

export function primarySeriesForObs(obs, key) {
  const cfg = KPICFG[key];
  if (cfg.derived === "total") {
    return obs.map((o) => {
      const [a, b, c] = o.values;
      return (a == null && b == null && c == null) ? null : (a || 0) + (b || 0) + (c || 0);
    });
  }
  if (cfg.derived === "saldo") {
    return obs.map((o) => (o.values[0] != null && o.values[1] != null) ? o.values[0] - o.values[1] : null);
  }
  return obs.map((o) => o.values[cfg.valCol] ?? null);
}

export function primarySeries(ind) {
  return primarySeriesForObs(ind.observations, ind.key);
}

function proseVal(ind, v) {
  if (v == null) return "—";
  const k = ind.key;
  const money = (x, u) => (x < 0 ? "−$" : "$") + Math.abs(Math.round(x)).toLocaleString("es-MX") + " " + u;
  if (k === "PIB") return (Math.abs(v) < 1 ? (v * 100) : (v / 1e6)).toLocaleString("es-MX", { minimumFractionDigits: Math.abs(v) < 1 ? 1 : 2, maximumFractionDigits: Math.abs(v) < 1 ? 1 : 2 }) + (Math.abs(v) < 1 ? "%" : " billones de pesos de 2018");
  if (k === "PIBSEC") return (v / 1e6).toLocaleString("es-MX", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " billones de pesos";
  if (k === "IED" || k === "BALANZA" || k === "BCMM") return money(v, "millones de dólares");
  if (k === "IGAE" || k === "IMAI" || k === "CONSUMO" || k === "EMIM") return v.toLocaleString("es-MX", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + " puntos";
  if (k === "DESOCUP") return v.toLocaleString("es-MX", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + "%";
  if (k === "INPC" || k === "INPP" || k === "TASA") return v.toLocaleString("es-MX", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + "%";
  if (k === "TIPOCAMBIO") return "$" + v.toLocaleString("es-MX", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return String(v);
}

// Devuelve {mag, text, pos, label, mode} para el último dato.
function computeVar(ind, cfg, vals, lastI, prevI) {
  if (cfg.varCol != null) {
    const raw = valAt(ind, lastI, cfg.varCol);
    if (raw == null) return { mag: null, text: "—", pos: true };
    const mag = cfg.varFmt === "pct-frac" ? raw * 100 : raw;
    return { mag, text: (raw > 0 ? "+" : "") + fmtVal(raw, cfg.varFmt), pos: raw >= 0 };
  }
  const cur = vals[lastI];
  const lag = ind.frecuencia === "Trimestral" ? 4 : 12;
  if (cfg.varMode === "pct-yoy") {
    const b = vals[lastI - lag];
    if (cur != null && b != null && b !== 0) {
      const d = (cur - b) / Math.abs(b) * 100;
      return { mag: d, text: (d >= 0 ? "+" : "") + d.toLocaleString("es-MX", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + "%", pos: d >= 0 };
    }
    // fallback a variación contra periodo previo si no hay historia anual
    if (prevI != null && vals[prevI] != null && vals[prevI] !== 0) {
      const d = (cur - vals[prevI]) / Math.abs(vals[prevI]) * 100;
      return { mag: d, text: (d >= 0 ? "+" : "") + d.toLocaleString("es-MX", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + "%", pos: d >= 0, label: "Variación vs. periodo previo" };
    }
    return { mag: null, text: "—", pos: true };
  }
  if (cfg.varMode === "pct-prev" && prevI != null && vals[prevI] != null && vals[prevI] !== 0) {
    const d = (cur - vals[prevI]) / Math.abs(vals[prevI]) * 100;
    return { mag: d, text: (d >= 0 ? "+" : "") + d.toLocaleString("es-MX", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + "%", pos: d >= 0 };
  }
  if (cfg.varMode === "pp-prev" && prevI != null && vals[prevI] != null) {
    let d = cur - vals[prevI];
    if (cfg.valFmt === "pct-frac") d *= 100;
    const mag = d;
    if (Math.abs(mag) < 0.0001) return { mag: 0, text: "Sin cambio", pos: true, label: cfg.varLabel };
    const unit = cfg.ppLong ? " puntos porcentuales" : " pp";
    return { mag, text: (d >= 0 ? "+" : "") + d.toLocaleString("es-MX", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + unit, pos: d >= 0 };
  }
  if (cfg.varMode === "abs-prev" && prevI != null && vals[prevI] != null) {
    const d = cur - vals[prevI];
    return { mag: d, text: (d >= 0 ? "+" : "") + Math.round(d).toLocaleString("es-MX") + " mdd", pos: d >= 0 };
  }
  return { mag: null, text: "—", pos: true };
}

function toFixed1(v) { return v.toLocaleString("es-MX", { minimumFractionDigits: 1, maximumFractionDigits: 1 }); }

function ppText(d) {
  if (d == null) return "—";
  if (Math.abs(d) < 0.0001) return "Sin cambio";
  return (d >= 0 ? "+" : "") + toFixed1(d) + " p.p.";
}

function quarterLabelFromPeriod(p) {
  if (!p) return p;
  const mo = p.match(/^(Ene|Feb|Mar|Abr|May|Jun|Jul|Ago|Sep|Oct|Nov|Dic)\s+(\d{2})$/i);
  if (!mo) return p;
  const meses = { ene: 1, feb: 2, mar: 3, abr: 4, may: 5, jun: 6, jul: 7, ago: 8, sep: 9, oct: 10, nov: 11, dic: 12 };
  const m = meses[mo[1].toLowerCase()];
  const yy = parseInt(mo[2], 10);
  const year = (yy >= 93 ? 1900 : 2000) + yy;
  const q = Math.ceil(m / 3);
  return `${q}T-${mo[2]}`;
}

function computeDesocupKPI(ind) {
  const obs = ind.observations;
  if (!obs || !obs.length) return null;

  function lastNotNull(col) {
    for (let i = obs.length - 1; i >= 0; i--) {
      if (obs[i].values[col] != null) return i;
    }
    return null;
  }
  function valAt(col, i) { return i == null ? null : (obs[i].values[col] ?? null); }

  const cards = [
    [0, "Desocupación"],
    [1, "Participación"],
    [2, "Informalidad"],
    [3, "Subocupación"],
  ].map(([col, name]) => {
    const lastI = lastNotNull(col);
    if (lastI == null) return null;
    const cur = valAt(col, lastI);
    const prev = valAt(col, lastI - 1);
    const yoy = valAt(col, lastI - 12);
    const mom = (cur != null && prev != null) ? round6(cur - prev) : null;
    const yoyPP = (cur != null && yoy != null) ? round6(cur - yoy) : null;
    return {
      name,
      col,
      nivelRaw: cur,
      nivelText: fmtVal(cur, "pct-raw"),
      momRaw: mom,
      momText: ppText(mom),
      yoyRaw: yoyPP,
      yoyText: ppText(yoyPP),
      ultimoP: obs[lastI].period,
    };
  }).filter(Boolean);

  if (!cards.length) return null;

  const main = cards[0];
  const lastI = lastNotNull(0) || 0;
  const series = obs.map((o) => o.values[0] ?? null);
  const periods = obs.map((o) => o.period);
  const valid = series.filter((v) => v != null);
  let maxI = 0, minI = 0;
  for (let i = 0; i < series.length; i++) {
    if (series[i] != null) {
      if (maxI == null || series[i] > series[maxI]) maxI = i;
      if (minI == null || series[i] < series[minI]) minI = i;
    }
  }

  // Población ocupada trimestral
  const popI = lastNotNull(5);
  let poblacion = null;
  if (popI != null) {
    const personas = valAt(5, popI);
    const millones = valAt(4, popI);
    const pPeriod = obs[popI].q_period || quarterLabelFromPeriod(obs[popI].period);
    poblacion = {
      periodo: pPeriod,
      personas,
      millones,
      textMillones: millones != null ? toFixed1(millones) + " millones de personas" : "—",
    };
  }

  const mom = main.momRaw;
  const yoyPP = main.yoyRaw;
  let assessment = "neutral";
  let dir = "flat";
  if (mom != null) {
    dir = mom > 0.05 ? "up" : (mom < -0.05 ? "down" : "flat");
    if (mom < -0.05) assessment = "favorable";
    else if (mom > 0.05) assessment = "adverso";
  }
  const semaforo = assessment === "favorable" ? "bueno" : (assessment === "adverso" ? "malo" : (mom == null ? "neutral" : "estable"));

  const kpi = {
    assessment, dir, semaforo,
    ultimoP: main.ultimoP,
    ultimoRaw: main.nivelRaw,
    ultimoFmt: main.nivelText,
    varText: main.momText,
    varRaw: mom,
    varMag: mom,
    pos: mom != null && mom >= 0,
    varColor: (mom != null && mom >= 0) ? COLORS.GREEN : COLORS.CRIMSON,
    varLabel: "Cambio mensual",
    yoyText: main.yoyText,
    yoyRaw: yoyPP,
    yoyMag: yoyPP,
    yoyPos: yoyPP != null && yoyPP >= 0,
    yoyColor: (yoyPP != null && yoyPP >= 0) ? COLORS.GREEN : COLORS.CRIMSON,
    yoyLabel: "Cambio anual",
    maxRaw: valAt(0, maxI),
    maxP: periods[maxI],
    minRaw: valAt(0, minI),
    minP: periods[minI],
    maxFmt: fmtVal(valAt(0, maxI), "pct-raw"),
    minFmt: fmtVal(valAt(0, minI), "pct-raw"),
    lastI,
    series,
    periods,
    cards,
    poblacion,
    yoy: { mag: yoyPP, pos: yoyPP != null && yoyPP >= 0, text: ppText(yoyPP), label: "Cambio anual" },
  };

  // Bullets
  const bullets = [];
  const p = main.ultimoP;
  const qPeriod = poblacion ? poblacion.periodo : "—";
  const qText = poblacion ? poblacion.textMillones : "—";

  bullets.push(
    `En ${enFrase(p)}, la tasa de desocupación fue ${main.nivelText} (${main.momText} respecto al mes anterior; ${main.yoyText} respecto al mismo mes del año previo).`
  );

  const other = cards.slice(1).map((c) => `${c.name.toLowerCase()} ${c.nivelText} (${c.momText})`).join(", ");
  if (other) bullets.push(`Las demás tasas laborales se ubicaron: ${other}.`);

  if (poblacion) {
    bullets.push(`La población ocupada se ubicó en ${qText} en ${enFrase(qPeriod)} (dato trimestral).`);
  }

  kpi.analysis = bullets.slice(0, 4);
  kpi.resumen = bullets.slice(0, 4);
  return kpi;
}

function round6(v) { return Math.round(v * 1_000_000) / 1_000_000; }

export function computeKPI(ind) {
  if (ind.key === "DESOCUP") return computeDesocupKPI(ind);
  const cfg = KPICFG[ind.key];
  const P = periods(ind);
  const vals = primarySeries(ind);
  const idxs = vals.map((v, i) => (v == null ? -1 : i)).filter((i) => i >= 0);
  if (!idxs.length) return null;
  const lastI = idxs[idxs.length - 1];
  const prevI = idxs.length >= 2 ? idxs[idxs.length - 2] : null;
  const ultimo = vals[lastI];
  const varInfo = computeVar(ind, cfg, vals, lastI, prevI);
  let maxI = idxs[0], minI = idxs[0];
  idxs.forEach((i) => { if (vals[i] > vals[maxI]) maxI = i; if (vals[i] < vals[minI]) minI = i; });
  // Variación acumulada (col 5 para IMAI, si existe).
  let acumInfo = null;
  if (cfg.acumCol != null) {
    const raw = valAt(ind, lastI, cfg.acumCol);
    if (raw != null) {
      const mag = cfg.acumFmt === "pct-frac" ? raw * 100 : raw;
      acumInfo = {
        acumMag: mag,
        acumText: (raw > 0 ? "+" : "") + fmtVal(raw, cfg.acumFmt),
        acumPos: raw >= 0,
        acumLabel: cfg.acumLabel || "Acumulado",
      };
    }
  }

  // Evaluación del movimiento SOLO cuando es económicamente claro.
  // assess: "growth" (subir favorable) | "unemployment" (bajar favorable) | "neutral".
  const assess = cfg.assess || (cfg.goodSign > 0 ? "growth" : cfg.goodSign < 0 ? "unemployment" : "neutral");
  const dir = varInfo.mag == null ? "flat" : (varInfo.mag > 0.05 ? "up" : (varInfo.mag < -0.05 ? "down" : "flat"));
  let assessment = "neutral"; // favorable | adverso | neutral
  if (varInfo.mag != null && assess === "growth") assessment = dir === "up" ? "favorable" : (dir === "down" ? "adverso" : "neutral");
  else if (varInfo.mag != null && assess === "unemployment") assessment = dir === "down" ? "favorable" : (dir === "up" ? "adverso" : "neutral");
  // semáforo derivado (para el punto de color): favorable=bueno, adverso=malo, resto=neutral/estable.
  let semaforo = assessment === "favorable" ? "bueno" : (assessment === "adverso" ? "malo" : (varInfo.mag == null ? "neutral" : "estable"));
  const out = {
    assessment, dir,
    ultimoFmt: fmtVal(ultimo, cfg.valFmt), ultimoRaw: ultimo, ultimoP: P[lastI],
    varText: varInfo.text, varMag: varInfo.mag, pos: varInfo.pos,
    varColor: varInfo.pos ? COLORS.GREEN : COLORS.CRIMSON,
    varLabel: varInfo.label || cfg.varLabel,
    maxFmt: fmtVal(vals[maxI], cfg.valFmt), maxRaw: vals[maxI], maxP: P[maxI],
    minFmt: fmtVal(vals[minI], cfg.valFmt), minRaw: vals[minI], minP: P[minI],
    lastI, series: vals, periods: P, semaforo,
  };
  if (acumInfo) Object.assign(out, acumInfo);

  // Métricas adicionales del IOAE: intervalo de confianza, observado y error.
  if (ind.key === "IOAE") {
    const lastObs = ind.observations[lastI];
    if (lastObs) {
      const v = lastObs.values;
      const lower = v[1] ?? null, upper = v[2] ?? null, observed = v[12] ?? null, monthly = v[3] ?? null;
      if (lower != null && upper != null) {
        const w = (upper - lower) * 100;
        out.icWidth = w;
        out.icWidthText = (w > 0 ? "±" : "") + w.toLocaleString("es-MX", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " pp";
      }
      if (monthly != null) {
        out.monthlyText = (monthly > 0 ? "+" : "") + fmtVal(monthly, "pct-frac");
      }
      if (observed != null) {
        out.observedRaw = observed;
        out.observedText = (observed > 0 ? "+" : "") + fmtVal(observed, "pct-frac");
        const err = observed - ultimo;
        out.errorRaw = err;
        out.errorText = (err > 0 ? "+" : "-") + fmtVal(Math.abs(err) * 100, "pp");
        out.errorPP = err * 100;
      }
    }
    // IGAE observado más reciente (puede ser dos meses atrás).
    for (let i = lastI; i >= 0; i--) {
      const v = ind.observations[i].values;
      if (v[12] != null) {
        const observed = v[12];
        const now = v[0];
        out.latestObservedP = ind.observations[i].period;
        out.latestObservedText = (observed > 0 ? "+" : "") + fmtVal(observed, "pct-frac");
        if (now != null) {
          const err = observed - now;
          out.latestErrorPP = err * 100;
          out.latestErrorText = (err > 0 ? "+" : "-") + fmtVal(Math.abs(err) * 100, "pp");
        }
        break;
      }
    }
    let n = 0, sse = 0;
    ind.observations.forEach((o) => {
      const v = o.values;
      if (v[0] != null && v[12] != null) {
        const e = v[12] - v[0];
        sse += e * e;
        n += 1;
      }
    });
    if (n > 0) {
      const rmse = Math.sqrt(sse / n) * 100;
      out.rmseN = n;
      out.rmseText = rmse.toLocaleString("es-MX", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " pp";
    }
  }

  return out;
}

function varValFmt(mag, cfg) {
  if (mag == null) return "—";
  const s = mag > 0 ? "+" : "";
  if (cfg.varMode === "abs-prev") return s + Math.round(mag).toLocaleString("es-MX") + " mdd";
  if (cfg.varMode === "pp-prev") { const d = cfg.ppLong ? 1 : 2; return s + mag.toLocaleString("es-MX", { minimumFractionDigits: d, maximumFractionDigits: d }) + (cfg.ppLong ? " puntos porcentuales" : " pp"); }
  return s + mag.toLocaleString("es-MX", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + "%";
}

function varAt(ind, cfg, vals, idx) {
  if (idx < 0) return null;
  if (cfg.varCol != null) { const raw = valAt(ind, idx, cfg.varCol); if (raw == null) return null; return cfg.varFmt === "pct-frac" ? raw * 100 : raw; }
  const a = vals[idx];
  const lag = ind.frecuencia === "Trimestral" ? 4 : 12;
  if (cfg.varMode === "pct-yoy") { const b = vals[idx - lag]; if (a == null || b == null || b === 0) { const p = vals[idx - 1]; return (a == null || p == null || p === 0) ? null : (a - p) / Math.abs(p) * 100; } return (a - b) / Math.abs(b) * 100; }
  if (cfg.varMode === "pct-prev") { const b = vals[idx - 1]; if (a == null || b == null || b === 0) return null; return (a - b) / Math.abs(b) * 100; }
  if (cfg.varMode === "pp-prev") { const b = vals[idx - 1]; if (a == null || b == null) return null; let d = a - b; if (cfg.valFmt === "pct-frac") d *= 100; return d; }
  if (cfg.varMode === "abs-prev") { const b = vals[idx - 1]; if (a == null || b == null) return null; return a - b; }
  return null;
}

// Variación anual (u otra secundaria, p. ej. trimestral para PIB) para la matriz.
// Devuelve {text,pos,mag,label} o null si no es aplicable/insuficiente historia.
export function annualVar(ind, k) {
  if (ind.key === "DESOCUP") {
    if (k && k.yoy) return k.yoy;
    return null;
  }
  const cfg = KPICFG[ind.key];
  // Si hay una columna oficial (yoyCol), se usa directamente.
  if (cfg.yoyCol != null) {
    const raw = valAt(ind, k.lastI, cfg.yoyCol);
    if (raw == null) return null;
    const mag = cfg.yoyFmt === "pct-frac" ? raw * 100 : raw;
    return {
      mag,
      pos: raw >= 0,
      text: (raw > 0 ? "+" : "") + fmtVal(raw, cfg.yoyFmt),
      label: cfg.yoyLabel || "Var. anual",
    };
  }
  // No se calcula variación anual del nivel cuando: (a) el valor ya es una tasa,
  // (b) la variación primaria ya es interanual (evita duplicar), o
  // (c) la interanual del saldo no tiene lectura económica clara.
  if (["INPC", "INPP", "TASA", "DESOCUP", "IED", "BALANZA", "IOAE"].includes(ind.key)) return null;
  const vals = k.series;
  const lag = ind.frecuencia === "Trimestral" ? 4 : 12;
  const cur = vals[k.lastI];
  const base = vals[k.lastI - lag];
  if (cur == null || base == null || base === 0) return null;
  const d = (cur - base) / Math.abs(base) * 100;
  return { mag: d, pos: d >= 0, text: (d >= 0 ? "+" : "") + d.toLocaleString("es-MX", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + "%", label: "Var. anual" };
}

// Genera 2-3 bullets de análisis determinista, auditables.
export function analysis(ind, k) {
  if (ind.key === "DESOCUP") {
    if (k && k.analysis) return k.analysis;
    const kk = computeDesocupKPI(ind);
    return kk ? kk.analysis : [];
  }
  const cfg = KPICFG[ind.key];
  const valid = k.series.filter((v) => v != null);
  const promedio = valid.reduce((a, b) => a + b, 0) / valid.length;
  const curVar = k.varMag;
  const prevVar = varAt(ind, cfg, k.series, k.lastI - 1);
  const prevP = k.periods[k.lastI - 1];
  const aMag = Math.abs(curVar || 0);
  const g = cfg.vg;
  const magAdj = (cfg.grupo === "balanza" || cfg.grupo === "inpc" || cfg.grupo === "desoc" || cfg.grupo === "fx" || cfg.grupo === "tasa") ? ""
    : (aMag < 0.5 ? "marginal" : (aMag < 1.5 ? (g === "m" ? "moderado" : "moderada") : (aMag < 4 ? (g === "m" ? "sólido" : "sólida") : (g === "m" ? "elevado" : "elevada"))));
  const ORIG = ["PIB", "PIBSEC", "IGAE", "IMAI", "CONSUMO", "EMIM"].includes(ind.key);
  const big = prevVar != null ? Math.abs(curVar - prevVar) : aMag;
  let trend = "";
  if (cfg.grupo === "growth") {
    if (curVar < 0) trend = (aMag >= 1 ? "una marcada" : "una") + " contracción";
    else if (prevVar != null && curVar < prevVar - 0.05) trend = (big >= 1 ? "una marcada" : "una ligera") + " desaceleración";
    else if (prevVar != null && curVar > prevVar + 0.05) trend = (big >= 1 ? "una marcada" : "una ligera") + " aceleración";
    else trend = "un ritmo de expansión estable";
  } else if (cfg.grupo === "desoc") {
    if (curVar > 0.001) trend = (aMag >= 0.3 ? "un marcado" : "un ligero") + " repunte del desempleo";
    else if (curVar < -0.001) trend = (aMag >= 0.3 ? "un marcado" : "un ligero") + " descenso del desempleo";
    else trend = "estabilidad en el mercado laboral";
  } else if (cfg.grupo === "inpc") {
    if (curVar > 0.001) trend = (aMag >= 0.3 ? "un marcado" : "un ligero") + " repunte inflacionario";
    else if (curVar < -0.001) trend = (aMag >= 0.3 ? "una marcada" : "una ligera") + " moderación de la inflación";
    else trend = "estabilidad en los precios";
  } else if (cfg.grupo === "balanza") {
    if (curVar > 0) trend = "una mejora del saldo comercial";
    else if (curVar < 0) trend = "un deterioro del saldo comercial";
    else trend = "un saldo prácticamente estable";
  } else if (cfg.grupo === "fx") {
    if (curVar > 0.05) trend = "una depreciación del peso";
    else if (curVar < -0.05) trend = "una apreciación del peso";
    else trend = "estabilidad cambiaria";
  } else if (cfg.grupo === "tasa") {
    if (curVar > 0.001) trend = "un alza en la tasa de referencia";
    else if (curVar < -0.001) trend = "un recorte en la tasa de referencia";
    else trend = "una tasa de referencia sin cambios";
  }
  const sameRound = proseVal(ind, k.ultimoRaw) === proseVal(ind, promedio);
  const avgPhrase = sameRound ? "en línea con el promedio del periodo mostrado" : ((k.ultimoRaw > promedio ? "por encima" : "por debajo") + " del promedio del periodo mostrado");
  const art = cfg.vg === "m" ? "un" : "una";
  const prevClause = (prevVar != null && cfg.grupo !== "balanza") ? ` respecto ${respFrase(prevP)} (${varValFmt(prevVar, cfg)})` : (prevVar != null ? ` respecto ${respFrase(prevP)}` : "");

  // La serie original con lectura por grupo aporta el matiz en la 2ª frase;
  // se omite el adjetivo aquí para no duplicarlo.
  const skelMagAdj = (cfg.grupo === "growth" && ORIG) ? "" : magAdj;
  let b1 = `En ${enFrase(k.ultimoP)}, ${cfg.art} ${cfg.noun} se ubicó en ${proseVal(ind, k.ultimoRaw)}${cfg.ctx}, con ${art} ${cfg.vw}${skelMagAdj ? " " + skelMagAdj : ""} de ${varValFmt(curVar, cfg)} ${cfg.comp}.`;
  // Segunda frase de b1: lectura prudente por grupo (sin adjetivos de tendencia
  // automatizados; advierte sobre la serie original cuando corresponde).
  let read;
  if (cfg.grupo === "growth" && ORIG) {
    if (ind.frecuencia === "Trimestral") {
      const label = cfg.varLabel.toLowerCase().includes("anual") ? "crecimiento anual" : "variación trimestral";
      read = `El ${label} fue ${magAdj || "marginal"}. La comparación entre trimestres debe considerar el comportamiento estacional de la serie original.`;
    } else {
      const verb = curVar == null ? "se mantuvo sin cambio" : (curVar > 0.05 ? "aumentó" : (curVar < -0.05 ? "disminuyó" : "se mantuvo prácticamente sin cambio"));
      read = `La variación mensual publicada por el INEGI muestra que el indicador ${verb} respecto del mes previo. El nivel mostrado es la serie original; la variación mensual se calcula sobre cifras desestacionalizadas.`;
    }
  } else if (cfg.grupo === "inpc") {
    const verb = curVar == null ? "se mantuvo" : (curVar > 0.001 ? "aumentó" : (curVar < -0.001 ? "disminuyó" : "no cambió"));
    const noun = ind.key === "INPP" ? "La variación anual de precios productor" : "La inflación anual";
    read = `${noun} ${verb} respecto del mes previo. Se ubicó ${avgPhrase} (${proseVal(ind, promedio)}).`;
  } else {
    read = `Este resultado refleja ${trend}${prevClause}, y deja al indicador ${avgPhrase} de ${proseVal(ind, promedio)}.`;
  }
  b1 += " " + read;

  const tail = valid.slice(-4);
  let dir = "lateral";
  if (tail.length >= 2) { const ch = tail[tail.length - 1] - tail[0], rel = Math.abs(ch) / (Math.abs(tail[0]) || 1); if (rel >= 0.01) dir = ch > 0 ? "ascendente" : "descendente"; }
  const posAvg = k.ultimoRaw > promedio ? "por encima del promedio del periodo mostrado" : (k.ultimoRaw < promedio ? "por debajo del promedio del periodo mostrado" : "en línea con el promedio del periodo mostrado");
  const extremo = k.ultimoRaw === k.maxRaw ? " y fue el registro más alto de la serie mostrada" : (k.ultimoRaw === k.minRaw ? " y fue el registro más bajo de la serie mostrada" : "");
  let cmp = "";
  if (tail.length >= 2) {
    cmp = dir === "lateral" ? " El último dato se mantuvo cercano al del inicio del periodo mostrado."
      : (dir === "ascendente" ? " El último dato fue superior al del inicio del periodo mostrado."
        : " El último dato fue inferior al del inicio del periodo mostrado.");
  }
  let b2 = `A lo largo de la serie mostrada, el indicador osciló entre un máximo de ${proseVal(ind, k.maxRaw)} (${perLong(k.maxP)}) y un mínimo de ${proseVal(ind, k.minRaw)} (${perLong(k.minP)}). El resultado más reciente se ubicó ${posAvg}${extremo}.${cmp}`;
  if (ORIG && dir !== "lateral") b2 += " Esta comparación se realiza sobre la serie original, que incorpora efectos estacionales.";

  let extra = "";
  if (ind.key === "INPC") {
    const lvl = k.ultimoRaw;
    extra = lvl > 4 ? " En este nivel, la inflación se mantiene por encima del límite superior del objetivo del Banco de México (3 % ±1 punto), lo que limita el margen para relajar la política monetaria."
      : (lvl >= 2 ? " Con ello, la inflación se mantiene dentro del intervalo de variabilidad del Banco de México (3 % ±1 punto), aunque todavía por encima de la meta puntual de 3 %."
        : " Este nivel se sitúa por debajo de la meta de 3 % del Banco de México.");
  } else if (ind.key === "IED") {
    const v = ind.observations[k.lastI].values;
    const comps = [["nuevas inversiones", v[1]], ["reinversión de utilidades", v[2]], ["cuentas entre compañías", v[3]]].filter((c) => c[1] != null);
    comps.sort((a, b) => b[1] - a[1]);
    const dom = comps[0], share = k.ultimoRaw ? Math.round(dom[1] / k.ultimoRaw * 100) : 0;
    extra = ` En su composición, el rubro predominante fue ${dom[0]} (≈${share}% del total), lo que ${dom[0] === "reinversión de utilidades" ? "refleja sobre todo la permanencia de capital ya instalado más que la llegada de proyectos nuevos" : "apunta a la captación de capital fresco"}.`;
  } else if (ind.key === "BALANZA") {
    const sup = k.ultimoRaw >= 0;
    extra = ` El saldo del último mes corresponde a un ${sup ? "superávit comercial, con exportaciones por encima de las importaciones" : "déficit comercial, con importaciones por encima de las exportaciones"}.`;
  } else if (ind.key === "DESOCUP") {
    extra = " La tasa se mantiene en niveles históricamente bajos para la economía mexicana. Su lectura debe acompañarse de la población ocupada y de las condiciones de informalidad, que la tasa de desocupación por sí sola no captura.";
  }
  return [b1, b2 + extra];
}
