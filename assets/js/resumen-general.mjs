import { LABELS, PRINCIPAL } from "./config.js";
import { fmtVal, isTrim, perLong, perShort, periodToDate } from "./format.js";
import { computeKPI } from "./metrics.js";

const GROUPS = [
  ["Actividad", ["PIBSEC", "PIB", "IGAE", "IOAE", "SIC", "IMAI", "EMIM", "IMOAM"]],
  ["Demanda y empleo", ["CONSUMO", "IMFBCF", "DESOCUP", "EMOE"]],
  ["Precios", ["INPC", "INPP"]],
  ["Sector externo", ["BCMM"]],
];

const ROW_LABELS = {
  PIBSEC: "PIB trimestral", PIB: "PIB oportuno", IGAE: "IGAE", IOAE: "IOAE (nowcast IGAE)",
  SIC: "Indicador coincidente (SIC)", IMAI: "Actividad industrial (IMAI)",
  EMIM: "Manufactura (EMIM)", IMOAM: "IMOAM (manufactura estimada)",
  CONSUMO: "Consumo privado", IMFBCF: "Inversión fija bruta", DESOCUP: "Desocupación",
  EMOE: "Confianza empresarial (IGOEC)", INPC: "Inflación (INPC)", INPP: "Precios productor (INPP)",
  BCMM: "Balanza comercial",
};

const STATUS = {
  favorable: ["Favorables", "Favorable", "▲"],
  adverso: ["Adversos", "Adverso", "▼"],
  neutral: ["Sin clasificación", "Sin clasificación", "·"],
};

const PHASES = {
  expansion: ["Expansión", "arriba de lo normal y mejorando"],
  slowdown: ["Desaceleración", "arriba de lo normal, pero empeorando"],
  recession: ["Recesión", "abajo de lo normal y empeorando"],
  recovery: ["Recuperación", "abajo de lo normal, pero mejorando"],
};

const phase = ({ level, change }) => level >= 100
  ? (change >= 0 ? "expansion" : "slowdown")
  : (change < 0 ? "recession" : "recovery");
const number = (n, digits) => n.toLocaleString("es-MX", { minimumFractionDigits: digits, maximumFractionDigits: digits });
const sign = (n) => n > 0 ? "+" : n < 0 ? "−" : "";
const monthsText = (n) => `${n} ${n === 1 ? "mes" : "meses"}`;
const monthIndex = (date) => date.getFullYear() * 12 + date.getMonth();
const monthFormat = new Intl.DateTimeFormat("es-MX", { month: "short", year: "2-digit" });
const monthLabel = (index) => monthFormat.formatToParts(new Date(Math.floor(index / 12), index % 12, 1))
  .filter(({ type }) => type === "month" || type === "year").map(({ value }) => value.replace(/\.$/, "")).join(" ");
const periodMonth = (period) => {
  const date = periodToDate(period);
  return date ? monthIndex(date) + (isTrim(period) ? 2 : 0) : null;
};
const countByStatus = (rows) => Object.fromEntries(Object.keys(STATUS)
  .map((status) => [status, rows.filter((row) => row.assessment === status).length]));

function cycleFrom(sic) {
  const obs = sic?.observations || [];
  const points = (levelCol, changeCol) => obs.flatMap(({ period, values }) => {
    const level = values[levelCol], change = values[changeCol];
    return Number.isFinite(level) && Number.isFinite(change) ? [{ period, level, change }] : [];
  });
  const coincident = points(0, 2);
  const leadingSeries = points(1, 4);
  const current = coincident.at(-1);
  const leading = leadingSeries.at(-1);
  if (!current) return { coincident, leading };

  const currentPhase = phase(current);
  const streak = (series, matches) => {
    const end = periodMonth(series.at(-1)?.period);
    let length = 0;
    for (let i = series.length - 1; i >= 0; i--) {
      const point = series[i];
      if (periodMonth(point.period) !== end - length || !matches(point)) break;
      length++;
    }
    return length;
  };
  const duration = streak(coincident, (point) => phase(point) === currentPhase);
  const prior = coincident.at(-duration - 1);
  const contiguousPrior = prior && periodMonth(current.period) - periodMonth(prior.period) === duration;
  const recentLeading = leadingSeries.slice(-3);
  return {
    coincident: coincident.slice(-18), current, currentPhase, leading,
    duration,
    improvements: streak(coincident, (point) => point.change > 0),
    priorPhase: contiguousPrior ? phase(prior) : null,
    smallerLeadingGains: recentLeading.length === 3 && streak(recentLeading, (point) => point.change > 0) === 3
      && recentLeading[0].change > recentLeading[1].change && recentLeading[1].change > recentLeading[2].change,
  };
}

export function buildResumen(indicators) {
  const latest = Object.fromEntries(PRINCIPAL.map((key) => {
    const ind = indicators[key];
    return [key, ind?.observations?.length ? computeKPI(ind) : null];
  }));
  const end = Math.max(...PRINCIPAL.map((key) => periodMonth(latest[key]?.ultimoP) ?? -Infinity));
  const months = Number.isFinite(end) ? Array.from({ length: 12 }, (_, i) => end - 11 + i) : [];

  const groups = GROUPS.map(([label, keys]) => {
    const rows = keys.map((key) => {
      const ind = indicators[key];
      const obs = ind?.observations || [];
      const cells = new Map();
      obs.forEach(({ period }, i) => {
        const month = periodMonth(period);
        if (!months.includes(month)) return;
        // La misma ruta que usa la ficha, con la serie recortada en el periodo de la celda.
        const kpi = computeKPI({ ...ind, observations: obs.slice(0, i + 1) });
        if (kpi?.ultimoP === period && Number.isFinite(kpi.varMag)) cells.set(month, kpi);
      });
      return {
        key, quarterly: ind?.frecuencia === "Trimestral" || key === "PIB" || key === "PIBSEC",
        latest: latest[key], assessment: latest[key]?.assessment ?? (obs.length ? "neutral" : null), cells,
      };
    });
    return { label, rows, counts: countByStatus(rows) };
  });
  return { months, groups, counts: countByStatus(groups.flatMap((g) => g.rows)), cycle: cycleFrom(indicators.SIC), latest };
}

const TOOLTIP_TEXT = {
  cycle: "El Indicador Coincidente del INEGI reúne el IGAE, la actividad industrial, las ventas al por menor, los asegurados en el IMSS, la desocupación urbana y las importaciones. Su tendencia de largo plazo equivale a 100 puntos. El Adelantado combina empleo manufacturero, confianza para invertir, Bolsa Mexicana, tipo de cambio real, TIIE y S&P 500 para anticipar cambios de fase. Fuente: INEGI, Sistema de Indicadores Cíclicos. El Coincidente se publica con unos dos meses de rezago.",
  reading: "El análisis usa reglas fijas y los datos publicados por INEGI en el Sistema de Indicadores Cíclicos y los 15 indicadores principales de MacroMéxico.",
  heat: "Cada celda usa el movimiento principal de la ficha. El recuadro oscuro marca el dato más reciente de cada fila. El rayado indica que no hay dato para la comparación.",
  balance: "La clasificación usa el último dato de los indicadores principales y el criterio de cada ficha. Una subida puede ser adversa, como en la desocupación.",
};

function headlineData(indicators, latest) {
  const pib = indicators.PIBSEC?.observations?.findLast((o) => Number.isFinite(o.values[7]));
  const inpc = indicators.INPC?.observations?.findLast((o) => Number.isFinite(o.values[2]));
  const desocup = latest.DESOCUP;
  const tasa = indicators.TASA ? computeKPI(indicators.TASA) : null;
  const fix = indicators.TIPOCAMBIO?.observations?.findLast((o) => Number.isFinite(o.values[0]));
  return [
    ["PIBSEC", "PIB", (pib?.values[7] > 0 ? "+" : "") + fmtVal(pib?.values[7], "pct-frac"), pib && `Anual desest. · ${perShort(pib.period)}`],
    ["INPC", "Inflación", fmtVal(inpc?.values[2], "pct-rate"), inpc && `Anual · ${perShort(inpc.period)}`],
    ["DESOCUP", "Desocupación", desocup?.ultimoFmt, desocup && `Tasa · ${perShort(desocup.ultimoP)}`],
    ["TASA", "Tasa objetivo", fmtVal(tasa?.ultimoRaw, "pct-rate"), tasa?.vigenteDesdeP && `Vigente desde ${perLong(tasa.vigenteDesdeP)}`],
    ["TIPOCAMBIO", "Tipo de cambio FIX", fix && `$${number(fix.values[0], 2)}`, fix && `Pesos por dólar · ${perLong(fix.period)}`],
  ];
}

function svgNode(tag, attrs = {}, text) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
  if (text != null) node.textContent = text;
  return node;
}

function clockGraphic(cycle, narrow) {
  const { coincident, currentPhase, leading } = cycle;
  const width = narrow ? 400 : 620, height = narrow ? 400 : 370;
  const left = narrow ? 46 : 56, right = width - 18, top = 18, bottom = height - 44;
  const all = leading ? [...coincident, leading] : coincident;
  const xr = Math.max(0.6, Math.max(...all.map((p) => Math.abs(p.level - 100))) * 1.25);
  const yr = Math.max(0.1, Math.max(...all.map((p) => Math.abs(p.change))) * 1.3);
  const x = (level) => left + (level - (100 - xr)) / (2 * xr) * (right - left);
  const y = (change) => top + (yr - change) / (2 * yr) * (bottom - top);
  const midX = x(100), midY = y(0);

  const svg = svgNode("svg", {
    class: narrow ? "rg-clock compact" : "rg-clock wide", viewBox: `0 0 ${width} ${height}`,
    role: "group", "aria-label": "Trayectoria del ciclo económico",
  });
  const label = (tx, ty, text, attrs = {}) => svgNode("text", { x: tx, y: ty, ...attrs }, text);
  [
    ["recovery", left, top, midX, midY], ["expansion", midX, top, right, midY],
    ["recession", left, midY, midX, bottom], ["slowdown", midX, midY, right, bottom],
  ].forEach(([key, x0, y0, x1, y1]) => {
    const active = key === currentPhase;
    const onLeft = x0 === left, onTop = y0 === top;
    const tx = onLeft ? x0 + 10 : x1 - 10, ty = onTop ? y0 + 22 : y1 - 12;
    const cls = `rg-quadrant ${key}${active ? " current" : ""}`;
    const anchor = onLeft ? "start" : "end";
    svg.append(svgNode("rect", { x: x0, y: y0, width: x1 - x0, height: y1 - y0, class: cls }));
    svg.append(label(tx, ty, PHASES[key][0].toUpperCase(), { "text-anchor": anchor, class: cls }));
    if (!narrow) svg.append(label(tx, ty + (onTop ? 16 : -16), PHASES[key][1], { "text-anchor": anchor, class: `${cls} description` }));
  });
  svg.append(
    svgNode("line", { x1: midX, x2: midX, y1: top, y2: bottom, class: "rg-axis" }),
    svgNode("line", { x1: left, x2: right, y1: midY, y2: midY, class: "rg-axis" }),
    label(left, height - 10, narrow ? "← Bajo lo normal" : "← Por debajo de lo normal"),
    label(right, height - 10, narrow ? "Sobre lo normal →" : "Por encima de lo normal →", { "text-anchor": "end" }),
    label(midX, height - 26, "100 = tendencia", { "text-anchor": "middle" }),
    label(0, 0, "Mejora ↑", { transform: `translate(16 ${y(yr / 2)}) rotate(-90)`, "text-anchor": "middle" }),
    label(0, 0, "↓ Empeora", { transform: `translate(16 ${y(-yr / 2)}) rotate(-90)`, "text-anchor": "middle" }),
    svgNode("polyline", { class: "rg-trajectory", points: coincident.map((p) => `${x(p.level)},${y(p.change)}`).join(" ") }),
  );
  const pointGroup = (p, title, cls) => {
    const tip = `${title} · ${perLong(p.period)}. ${number(p.level, 2)} puntos. Cambio mensual: ${sign(p.change)}${number(Math.abs(p.change), 2)} puntos. ${PHASES[phase(p)][0]}.`;
    return svgNode("g", { class: cls, tabindex: 0, role: "button", "aria-label": tip, "data-tip": tip });
  };
  coincident.forEach((p, i) => {
    const last = i === coincident.length - 1;
    const group = pointGroup(p, "Coincidente", last ? "rg-point latest" : "rg-point");
    const px = x(p.level), py = y(p.change);
    group.append(svgNode("circle", { cx: px, cy: py, r: last ? 7 : 4, class: "rg-marker" }),
      svgNode("circle", { cx: px, cy: py, r: 10, class: "rg-hit" }));
    svg.append(group);
    if (last || i === 0) {
      svg.append(label(px, py + (py < top + 55 ? 24 : -12), perShort(p.period),
        { "text-anchor": "middle", class: last ? "rg-latest-label" : "" }));
    }
  });
  if (leading) {
    const px = x(leading.level), py = y(leading.change), reverse = px + 150 > right;
    const group = pointGroup(leading, "Adelantado", "rg-point leading");
    group.append(svgNode("rect", { x: px - 5, y: py - 5, width: 10, height: 10, transform: `rotate(45 ${px} ${py})`, class: "rg-marker" }),
      svgNode("circle", { cx: px, cy: py, r: 11, class: "rg-hit" }));
    svg.append(group, label(px + (reverse ? -12 : 12), py - 10, `Adelantado · ${perShort(leading.period)}`,
      { "text-anchor": reverse ? "end" : "start", class: "rg-leading-label" }));
  }
  return svg;
}

function readingText(cycle, counts) {
  const { current, currentPhase, duration, improvements, priorPhase, leading, smallerLeadingGains } = cycle;
  const reading = [];
  if (current) {
    const label = PHASES[currentPhase][0];
    const trend = current.level >= 100 ? "por encima" : "por debajo";
    const streak = improvements ? ` y suma ${monthsText(improvements)} mejorando` : "";
    const phaseText = priorPhase
      ? `Entró en ${label.toLowerCase()} hace ${monthsText(duration)}, después de una etapa de ${PHASES[priorPhase][0].toLowerCase()}.`
      : `Se mantiene en ${label.toLowerCase()}.`;
    reading.push([label, `En ${perLong(current.period)}, la economía se ubicó ${trend} de su tendencia de largo plazo (${number(current.level, 2)} puntos)${streak}. ${phaseText}`]);
  }
  if (leading) {
    const trend = leading.level >= 100 ? "por encima" : "por debajo";
    const direction = leading.change > 0 ? "con avances mensuales" : leading.change < 0 ? "con retrocesos mensuales" : "sin cambio mensual";
    const streak = smallerLeadingGains ? " cada vez más pequeños en los últimos tres meses" : "";
    reading.push(["Hacia adelante", `El Indicador Adelantado (${perLong(leading.period)}) sigue ${trend} de su tendencia, ${direction}${streak}.`]);
  }
  const total = Object.values(counts).reduce((sum, n) => sum + n, 0);
  const population = total === PRINCIPAL.length ? "De los 15 indicadores principales" : `De los ${total} indicadores principales con datos`;
  reading.push(["Balance", `${population}, ${counts.favorable} tuvieron un movimiento favorable en su último dato, ${counts.adverso} uno adverso y ${counts.neutral} no se clasifican.`]);
  return reading;
}

function info(el, label, text) {
  return el("button", { class: "rg-info", type: "button", "aria-label": `Información sobre ${label}`, "data-tip": text }, "i");
}

function attachTooltips(root, tip) {
  let pin = null;
  let active = null;
  const close = () => {
    active?.removeAttribute("aria-describedby");
    active = null;
    tip.hidden = true;
  };
  const show = (node) => {
    if (!node) return;
    close();
    node.setAttribute("aria-describedby", tip.id);
    active = node;
    tip.textContent = node.dataset.tip;
    tip.hidden = false;
    const r = node.getBoundingClientRect(), box = tip.getBoundingClientRect();
    tip.style.left = `${Math.max(8, Math.min(r.left, document.documentElement.clientWidth - box.width - 8))}px`;
    tip.style.top = `${r.bottom + box.height + 8 > window.innerHeight ? Math.max(8, r.top - box.height - 8) : r.bottom + 8}px`;
  };
  root.addEventListener("pointerover", (e) => { if (e.pointerType !== "touch" && !pin) show(e.target.closest("[data-tip]")); });
  root.addEventListener("pointerout", (e) => { if (!pin && !active?.contains(e.relatedTarget) && active !== document.activeElement) close(); });
  root.addEventListener("focusin", (e) => { if (!pin) show(e.target.closest("[data-tip]")); });
  root.addEventListener("focusout", () => { pin = null; close(); });
  root.addEventListener("click", (e) => {
    const target = e.target.closest("[data-tip]");
    if (!target || target.matches("a")) { pin = null; close(); return; }
    if (pin === target) { pin = null; close(); return; }
    pin = target;
    show(target);
  });
  root.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { pin = null; close(); }
    if ((e.key === "Enter" || e.key === " ") && e.target.matches("svg [data-tip]")) {
      e.preventDefault();
      if (pin === e.target) { pin = null; close(); } else { pin = e.target; show(pin); }
    }
  });
}

function heatTable(el, months, groups) {
  const table = el("table", { class: "rg-heat", "aria-label": "Movimientos por indicador y mes" },
    el("thead", {}, el("tr", {}, el("th", { scope: "col", class: "rg-name" }, "Indicador"),
      ...months.map((m) => el("th", { scope: "col" }, monthLabel(m))))));
  groups.forEach(({ label, rows }) => {
    const body = el("tbody", {}, el("tr", {}, el("th", { class: "rg-group", scope: "rowgroup", colspan: months.length + 1 }, el("span", {}, label))));
    rows.forEach(({ key, cells, quarterly, latest }) => {
      const label = LABELS[key] || SIGLA[key] || key;
      const tr = el("tr", { "data-indicator": key }, el("th", { scope: "row", class: "rg-name" },
        el("a", { href: `#${key}`, "data-tip": latest ? `${label} · ${latest.varLabel}` : label }, ROW_LABELS[key] || label)));
      const last = Array.from(cells.keys()).at(-1);
      for (let i = 0; i < months.length;) {
        const m = months[i], remaining = quarterly ? 3 - m % 3 : 1;
        const span = Math.min(remaining, months.length - i), period = m + remaining - 1;
        const kpi = cells.get(period);
        const cell = el("td", { colspan: span, class: kpi ? `${kpi.assessment}${period === last ? " latest" : ""}` : "empty" });
        if (kpi) {
          const [, status, glyph] = STATUS[kpi.assessment];
          const value = kpi.varText.replace(/^-/, "−");
          const compact = value.replace(/ (puntos porcentuales|puntos|p\.p\.|mdd)$/, "");
          const tip = `${label} · ${perShort(kpi.ultimoP)}. ${kpi.varLabel}: ${value}${key === "BCMM" ? " mdd" : ""}. ${status}.`;
          cell.append(el("button", { type: "button", "data-tip": tip, "aria-label": tip, "data-period": kpi.ultimoP },
            el("span", { "aria-hidden": "true" }, `${glyph} ${compact}`)));
        } else {
          cell.setAttribute("aria-label", "Sin dato");
        }
        tr.append(cell);
        i += span;
      }
      body.append(tr);
    });
    table.append(body);
  });
  return table;
}

export function renderResumen(el, indicators, upcoming) {
  const { months, groups, counts, cycle, latest } = buildResumen(indicators);
  const root = el("div", { class: "resumen-general" });
  const heading = (title, text) => el("h3", {}, title, text && info(el, title, text));
  const panel = (title, text, ...kids) => el("section", { class: "rg-panel" }, heading(title, text), ...kids);

  root.append(el("h2", { class: "rg-sr-only" }, "Resumen general"));
  root.append(el("div", { class: "rg-ticker", "aria-label": "Indicadores destacados" },
    ...headlineData(indicators, latest).map(([key, title, value, sub]) =>
      el("a", { href: `#${key}` }, el("span", {}, title), el("strong", {}, value || "—"), el("small", {}, sub || "Sin dato")))));

  const clock = panel("Reloj del ciclo económico", TOOLTIP_TEXT.cycle);
  if (cycle.current) {
    const { current, currentPhase, duration, leading } = cycle;
    clock.append(
      el("p", { class: "rg-caption" }, `Cifras a ${perLong(current.period)} (Coincidente)${leading ? ` y ${perLong(leading.period)} (Adelantado)` : ""}.`),
      el("p", { class: `rg-phase ${currentPhase}` }, `Fase actual: ${PHASES[currentPhase][0]} · ${monthsText(duration)}`),
      clockGraphic(cycle, false), clockGraphic(cycle, true),
      el("div", { class: "rg-legend" },
        el("span", {}, el("i", { class: "rg-line" }), "Coincidente (cómo va la economía)"),
        leading && el("span", {}, el("i", { class: "rg-diamond" }), "Adelantado (hacia dónde podría ir)")),
    );
  } else {
    clock.append(el("p", { class: "rg-caption" }, "Datos del Indicador Coincidente pendientes."));
  }

  const reading = panel("Análisis actual", TOOLTIP_TEXT.reading,
    el("ol", { class: "rg-reading" }, ...readingText(cycle, counts)
      .map(([lead, text]) => el("li", {}, el("strong", {}, `${lead}. `), text))),
    el("div", { class: "rg-guide" }, el("h4", {}, "Cómo leer el reloj"),
      el("ul", {},
        el("li", {}, el("b", {}, "→"), " A la derecha, la economía está por encima de su nivel normal (100 = tendencia)."),
        el("li", {}, el("b", {}, "↑"), " Hacia arriba, la economía mejoró respecto al mes anterior."),
        el("li", {}, el("b", {}, "●"), " Cada punto es un mes. El giro habitual es recuperación → expansión → desaceleración → recesión."))));
  reading.classList.add("rg-analysis");
  root.append(el("div", { class: "rg-hero" }, clock, reading));

  const heat = el("div", { class: "rg-heat-wrap", tabindex: 0, role: "region", "aria-label": "Mapa de movimientos. Desplazable horizontalmente." },
    months.length ? heatTable(el, months, groups) : el("p", { class: "rg-caption" }, "Datos pendientes."));
  root.append(panel("Mapa de movimientos, últimos 12 meses", TOOLTIP_TEXT.heat, heat,
    el("div", { class: "rg-legend" }, ...Object.entries(STATUS).map(([key, [, label, glyph]]) =>
      el("span", {}, el("i", { class: key, "aria-hidden": "true" }, glyph), label)),
    el("span", {}, el("i", { class: "empty", "aria-hidden": "true" }), "Sin dato"))));

  const balance = panel("Balance de movimientos", TOOLTIP_TEXT.balance,
    el("div", { class: "rg-counts" }, ...Object.entries(STATUS).map(([status, [label]]) =>
      el("div", {}, el("strong", { class: status }, String(counts[status])), el("span", {}, label)))),
    el("div", { class: "rg-bars" }, ...groups.map(({ label, counts }) => {
      const parts = Object.keys(STATUS).map((status) => counts[status]);
      const total = parts.reduce((sum, n) => sum + n, 0);
      const description = Object.entries(STATUS).map(([status, [name]]) => `${counts[status]} ${name.toLowerCase()}`).join(", ");
      return el("div", { class: "rg-bar-row" }, el("span", {}, label),
        el("div", { class: "rg-bar", "aria-hidden": "true" }, ...Object.keys(STATUS).filter((status) => counts[status] > 0)
          .map((status) => el("span", { class: status, style: `flex-basis:${100 * counts[status] / total}%` }))),
        el("span", { class: "rg-bar-count", "aria-label": description }, parts.join(" · ")));
    })),
    el("a", { class: "acceso-link", href: "#metodologia" }, "Criterios de interpretación →"));
  root.append(el("div", { class: "rg-columns" }, balance, upcoming));

  const tip = el("div", { class: "rg-tip", id: "rg-tooltip", role: "tooltip", hidden: "" });
  root.append(tip);
  attachTooltips(root, tip);
  const nameColumn = heat.querySelector(".rg-name");
  if (nameColumn) {
    const buttons = Array.from(heat.querySelectorAll("td button"));
    const updateTouchTargets = () => {
      const left = nameColumn.getBoundingClientRect().right;
      const wrap = heat.getBoundingClientRect();
      const partial = buttons.map((button) => {
        const rect = button.getBoundingClientRect();
        const visible = Math.min(wrap.right, rect.right) - Math.max(left, rect.left);
        const overlapsViewport = rect.right > wrap.left && rect.left < wrap.right;
        return overlapsViewport && visible < 24 && button !== document.activeElement;
      });
      buttons.forEach((button, i) => button.classList.toggle("rg-partial", partial[i]));
    };
    let initial = true;
    const resize = new ResizeObserver(() => {
      if (!heat.clientWidth) return;
      if (initial) {
        heat.scrollLeft = heat.scrollWidth;
        initial = false;
      }
      updateTouchTargets();
    });
    resize.observe(heat);
    heat.addEventListener("scroll", updateTouchTargets, { passive: true });
  }
  return root;
}
