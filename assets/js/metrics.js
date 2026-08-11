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
  if (k === "PIB") return (v / 1e6).toLocaleString("es-MX", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " billones de pesos de 2018";
  if (k === "PIBSEC") return (v / 1e6).toLocaleString("es-MX", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " billones de pesos";
  if (k === "IED" || k === "BALANZA") return money(v, "millones de dólares");
  if (k === "IGAE" || k === "IMAI" || k === "CONSUMO") return v.toLocaleString("es-MX", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + " puntos";
  if (k === "DESOCUP") return (v * 100).toLocaleString("es-MX", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + "%";
  if (k === "INPC" || k === "TASA") return v.toLocaleString("es-MX", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + "%";
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

export function computeKPI(ind) {
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
  // Evaluación del movimiento SOLO cuando es económicamente claro.
  // assess: "growth" (subir favorable) | "unemployment" (bajar favorable) | "neutral".
  const assess = cfg.assess || (cfg.goodSign > 0 ? "growth" : cfg.goodSign < 0 ? "unemployment" : "neutral");
  const dir = varInfo.mag == null ? "flat" : (varInfo.mag > 0.05 ? "up" : (varInfo.mag < -0.05 ? "down" : "flat"));
  let assessment = "neutral"; // favorable | adverso | neutral
  if (varInfo.mag != null && assess === "growth") assessment = dir === "up" ? "favorable" : (dir === "down" ? "adverso" : "neutral");
  else if (varInfo.mag != null && assess === "unemployment") assessment = dir === "down" ? "favorable" : (dir === "up" ? "adverso" : "neutral");
  // semáforo derivado (para el punto de color): favorable=bueno, adverso=malo, resto=neutral/estable.
  let semaforo = assessment === "favorable" ? "bueno" : (assessment === "adverso" ? "malo" : (varInfo.mag == null ? "neutral" : "estable"));
  return {
    assessment, dir,
    ultimoFmt: fmtVal(ultimo, cfg.valFmt), ultimoRaw: ultimo, ultimoP: P[lastI],
    varText: varInfo.text, varMag: varInfo.mag, pos: varInfo.pos,
    varColor: varInfo.pos ? COLORS.GREEN : COLORS.CRIMSON,
    varLabel: varInfo.label || cfg.varLabel,
    maxFmt: fmtVal(vals[maxI], cfg.valFmt), maxRaw: vals[maxI], maxP: P[maxI],
    minFmt: fmtVal(vals[minI], cfg.valFmt), minRaw: vals[minI], minP: P[minI],
    lastI, series: vals, periods: P, semaforo,
  };
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
  if (["INPC", "TASA", "DESOCUP", "IED", "BALANZA"].includes(ind.key)) return null;
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
  const ORIG = ["PIB", "PIBSEC", "IGAE", "IMAI", "CONSUMO"].includes(ind.key);
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
    read = `La inflación anual ${verb} respecto del mes previo. Se ubicó ${avgPhrase} (${proseVal(ind, promedio)}).`;
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
