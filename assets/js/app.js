// Orquestador del tablero macroeconómico V3 (navegación por indicador).
import { ORDER, PRINCIPAL, COMPLEMENTARIOS, LABELS, SIGLA, CAPTIONS, WINDOWS, COLORS, KPICFG, VIEWS, ESTADOS } from "./config.js";
import { computeKPI, analysis, annualVar } from "./metrics.js";
import { buildOption } from "./charts.js";
import { fmtVal, perLong } from "./format.js";

const state = {
  data: null, manifest: null, noticias: null, calendario: null,
  active: "panorama", windows: {}, charts: {}, openTables: {},
};

const $ = (sel, root = document) => root.querySelector(sel);
const el = (tag, attrs = {}, ...kids) => {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") n.className = v;
    else if (k === "html") n.innerHTML = v;
    else if (k.startsWith("on") && typeof v === "function") n.addEventListener(k.slice(2), v);
    else if (v !== null && v !== undefined) n.setAttribute(k, v);
  }
  for (const kid of kids) { if (kid == null) continue; n.append(kid.nodeType ? kid : document.createTextNode(kid)); }
  return n;
};

async function loadJSON(path, optional = false) {
  try {
    const r = await fetch(path, { cache: "no-store" });
    if (!r.ok) throw new Error(r.status);
    return await r.json();
  } catch (e) { if (optional) return null; throw e; }
}

const getInd = (key) => state.data.indicators[key];
const principalInds = () => PRINCIPAL.map(getInd).filter(Boolean);
const hasData = (ind) => ind && ind.observations && ind.observations.length > 0;

function estadoBadge(ind) {
  const est = ind.estado || "no disponible";
  const cfg = ESTADOS[est] || { cls: "na", short: est };
  return el("span", { class: `state-badge ${cfg.cls}`, title: est }, cfg.short);
}

// ---------------- Header ----------------
function latestInfo() {
  let latest = null, refPeriod = null;
  principalInds().forEach((ind) => { if (hasData(ind) && ind.last_updated && (!latest || ind.last_updated > latest)) latest = ind.last_updated; });
  const monthly = principalInds().filter((i) => hasData(i) && i.frecuencia === "Mensual");
  if (monthly.length) refPeriod = monthly.map((i) => i.last_observation).filter(Boolean).sort().slice(-1)[0];
  return { latest, refPeriod };
}
function renderHeader() {
  const { latest, refPeriod } = latestInfo();
  $("#meta-update").textContent = latest ? new Date(latest + "T00:00:00").toLocaleDateString("es-MX", { day: "2-digit", month: "long", year: "numeric" }) : "—";
  $("#meta-period").textContent = refPeriod ? perLong(refPeriod) : "—";
}

// ---------------- Navigation ----------------
function renderNav() {
  const nav = $("#tabs");
  nav.innerHTML = "";
  const primary = el("div", { class: "nav-row primary" });
  const secondary = el("div", { class: "nav-row secondary" });
  VIEWS.forEach((v) => {
    const btn = el("button", { class: "tab", role: "tab", id: `tab-${v.id}`, "aria-selected": String(v.id === state.active), "aria-controls": `view-${v.id}`, onclick: () => setView(v.id) }, v.label);
    (v.secondary ? secondary : primary).append(btn);
  });
  nav.append(primary, secondary);
}

function setView(id) {
  state.active = id;
  document.querySelectorAll(".tab").forEach((t) => t.setAttribute("aria-selected", String(t.id === `tab-${id}`)));
  document.querySelectorAll(".view").forEach((s) => s.classList.toggle("active", s.id === `view-${id}`));
  document.body.setAttribute("data-view", id);
  requestAnimationFrame(() => resizeVisibleCharts());
  window.scrollTo({ top: 0, behavior: "smooth" });
}

// ---------------- Panorama (home) ----------------
function sparkline(k) {
  const vals = (k.series || []).filter((v) => v != null).slice(-24);
  if (vals.length < 2) return el("div", { class: "spark empty" });
  const min = Math.min(...vals), max = Math.max(...vals), rng = (max - min) || 1;
  const W = 120, H = 30, step = W / (vals.length - 1);
  const pts = vals.map((v, i) => `${(i * step).toFixed(1)},${(H - ((v - min) / rng) * H).toFixed(1)}`).join(" ");
  const up = vals[vals.length - 1] >= vals[0];
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`); svg.setAttribute("class", "spark"); svg.setAttribute("preserveAspectRatio", "none"); svg.setAttribute("aria-hidden", "true");
  const pl = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
  pl.setAttribute("points", pts); pl.setAttribute("fill", "none");
  pl.setAttribute("stroke", up ? COLORS.GREEN : COLORS.CRIMSON); pl.setAttribute("stroke-width", "1.6");
  svg.append(pl);
  return svg;
}

function panoramaCard(ind) {
  const k = computeKPI(ind);
  if (!k) {
    return el("button", { class: "matrix-card na", type: "button", onclick: () => setView(ind.key) },
      el("div", { class: "mc-top" }, el("div", { class: "mc-name" }, LABELS[ind.key]), estadoBadge(ind)),
      el("div", { class: "mc-sigla" }, SIGLA[ind.key]),
      el("div", { class: "mc-value muted" }, "Sin dato disponible"),
      el("div", { class: "mc-sub" }, "Se activará al cargar la fuente oficial."));
  }
  const yoy = annualVar(ind, k);
  const cfg = KPICFG[ind.key];
  const deltaCls = k.assessment === "favorable" ? "up" : (k.assessment === "adverso" ? "down" : "flat");
  const card = el("button", { class: "matrix-card", type: "button", onclick: () => setView(ind.key) },
    el("div", { class: "mc-top" }, el("div", { class: "mc-name" }, LABELS[ind.key]), estadoBadge(ind)),
    el("div", { class: "mc-sigla" }, `${SIGLA[ind.key]} · ${k.ultimoP}`),
    el("div", { class: "mc-value" }, k.ultimoFmt),
    sparkline(k),
    el("div", { class: "mc-deltas" },
      el("div", { class: `mc-delta ${deltaCls}` }, el("span", { class: "d-val" }, k.varText), el("span", { class: "d-lbl" }, cfg.varLabel)),
      yoy ? el("div", { class: "mc-delta neutral" }, el("span", { class: "d-val" }, yoy.text), el("span", { class: "d-lbl" }, "Var. anual")) : null),
  );
  return card;
}

function classifyPanorama() {
  const avances = [], retrocesos = [], senales = [];
  principalInds().forEach((ind) => {
    const k = computeKPI(ind);
    if (!hasData(ind)) { senales.push(`${LABELS[ind.key]}: sin datos cargados (${ESTADOS[ind.estado]?.short || ind.estado}).`); return; }
    if (ind.origen_dato === "respaldo") { /* alerta global de respaldo, no por indicador */ }
    if (!k) return;
    const label = `${LABELS[ind.key]} (${k.varText}, ${k.ultimoP})`;
    if (k.assessment === "favorable") avances.push(label);
    else if (k.assessment === "adverso") retrocesos.push(label);
    if (ind.key === "INPC" && k.ultimoRaw > 4) senales.push(`Inflación general en ${fmtVal(k.ultimoRaw, "pct-raw")}: por encima del límite superior del objetivo del Banco de México (3% ±1 pp).`);
    if (ind.key === "BALANZA" && k.ultimoRaw < 0) senales.push(`Balanza comercial en déficit (${fmtVal(k.ultimoRaw, "usd")} mdd) en ${k.ultimoP}.`);
    if (k.assessment === "neutral" && ind.key === "BALANZA") { /* saldo se comenta en señales solo si déficit */ }
  });
  return { avances, retrocesos, senales };
}

function coyunturaBullets() {
  const bullets = [];
  const igae = getInd("IGAE");
  if (hasData(igae)) { const k = computeKPI(igae); if (k) bullets.push(`La actividad económica (IGAE) se ubicó en ${fmtVal(k.ultimoRaw, "idx")} puntos en ${k.ultimoP}, con una ${k.varText} ${k.varLabel.toLowerCase()}.`); }
  const pib = getInd("PIB");
  if (hasData(pib)) { const k = computeKPI(pib); if (k) bullets.push(`El PIB registró un crecimiento anual de ${k.varText} en ${k.ultimoP}.`); }
  const bal = getInd("BALANZA");
  if (hasData(bal)) { const k = computeKPI(bal); if (k) bullets.push(`La balanza comercial cerró ${k.ultimoP} con un ${k.ultimoRaw >= 0 ? "superávit" : "déficit"} de ${fmtVal(Math.abs(k.ultimoRaw), "usd")} mdd (saldo = exportaciones − importaciones); su variación mensual del saldo fue de ${k.varText}.`); }
  const inpc = getInd("INPC");
  if (hasData(inpc)) { const k = computeKPI(inpc); if (k) bullets.push(`La inflación general anual fue de ${fmtVal(k.ultimoRaw, "pct-raw")} en ${k.ultimoP} (variación de ${k.varText} frente al mes previo); su clasificación depende del contexto de política monetaria, no del signo por sí solo.`); }
  const des = getInd("DESOCUP");
  if (hasData(des)) { const k = computeKPI(des); if (k) bullets.push(`La tasa de desocupación fue de ${fmtVal(k.ultimoRaw, "pct-frac")} de la PEA en ${k.ultimoP}.`); }
  return bullets;
}

function renderPanorama() {
  const sec = $("#view-panorama");
  sec.innerHTML = "";
  const { latest, refPeriod } = latestInfo();
  sec.append(el("div", { class: "section-title" }, "Panorama macroeconómico"));
  sec.append(el("div", { class: "section-sub" }, `Actualizado el ${latest ? new Date(latest + "T00:00:00").toLocaleDateString("es-MX") : "—"} · periodo de referencia: ${refPeriod ? perLong(refPeriod) : "—"}. Selecciona un indicador para ver su ficha.`));

  // Alerta discreta de estado global (respaldo / pendiente / revisión).
  const conRespaldo = principalInds().filter((i) => i.origen_dato === "respaldo");
  const pendientes = principalInds().filter((i) => (i.estado || "").startsWith("pendiente") || i.estado === "no disponible");
  const revision = principalInds().filter((i) => i.estado === "dato en revisión" || (i.data_quality && i.data_quality.length));
  if (conRespaldo.length || pendientes.length || revision.length) {
    const parts = [];
    if (conRespaldo.length) parts.push(`${conRespaldo.length} indicador(es) muestran el último dato validado (dato de respaldo; sin token de la fuente conectado)`);
    if (pendientes.length) parts.push(`${pendientes.length} pendiente(s) de token o de datos`);
    if (revision.length) parts.push(`${revision.length} con celdas en revisión`);
    sec.append(el("div", { class: "alert-discreet" }, el("span", { class: "ad-dot" }), `Estado de los datos: ${parts.join("; ")}. Detalle en “Fuentes y metodología”.`));
  }

  // Matriz de 11 indicadores.
  const grid = el("div", { class: "matrix" });
  principalInds().forEach((ind) => grid.append(panoramaCard(ind)));
  sec.append(grid);

  const cols = el("div", { class: "panorama-cols" });

  // Avances / Retrocesos / Señales.
  const { avances, retrocesos, senales } = classifyPanorama();
  const movBox = el("div", { class: "panel" });
  movBox.append(el("h3", {}, "Movimientos del periodo"));
  movBox.append(el("p", { class: "caption" }, "Clasificación solo cuando el signo tiene un significado económico claro; no todo aumento es favorable ni toda caída es desfavorable."));
  const movGrid = el("div", { class: "mov-grid" });
  movGrid.append(movList("Avances", avances, "up"));
  movGrid.append(movList("Retrocesos", retrocesos, "down"));
  movGrid.append(movList("Señales de atención", senales, "warn"));
  movBox.append(movGrid);
  cols.append(movBox);

  // Próximos datos.
  const next = el("div", { class: "panel" });
  next.append(el("h3", {}, "Próximos datos por publicarse"));
  const nlist = el("div", {});
  const cal = state.calendario;
  const upcoming = (cal && cal.items ? cal.items : []).filter((c) => c.estatus === "próximo" || c.estatus === "pendiente").slice(0, 8);
  if (upcoming.length) {
    upcoming.forEach((c) => nlist.append(el("div", { class: "cal-item" }, el("span", { class: "date" }, c.fecha_publicacion || c.fecha || "—"), el("span", {}, `${c.indicador} · ${c.periodo_referencia || c.periodo || ""}`))));
  } else {
    principalInds().forEach((ind) => { if (ind.proximo) nlist.append(el("div", { class: "cal-item" }, el("span", { class: "date" }, ind.proximo), el("span", {}, `${LABELS[ind.key]} · ${ind.fuente?.nombre || ""}`))); });
    if (!nlist.children.length) nlist.append(el("div", { class: "muted" }, "Sin fechas confirmadas. Ver Calendario de publicaciones."));
  }
  next.append(nlist);
  cols.append(next);
  sec.append(cols);

  // Síntesis de coyuntura.
  const syn = el("div", { class: "panel" });
  syn.append(el("h3", {}, "Síntesis de coyuntura"));
  const ul = el("ul", { class: "summary-list" });
  coyunturaBullets().forEach((b) => ul.append(el("li", {}, el("span", { class: "mark" }), el("span", {}, b))));
  syn.append(ul);
  sec.append(syn);
}

function movList(title, items, cls) {
  const box = el("div", { class: `mov-col ${cls}` });
  box.append(el("div", { class: "mov-title" }, title, el("span", { class: "mov-count" }, String(items.length))));
  if (!items.length) { box.append(el("div", { class: "muted" }, "—")); return box; }
  const ul = el("ul", {});
  items.forEach((t) => ul.append(el("li", {}, t)));
  box.append(ul);
  return box;
}

// ---------------- Indicator view ----------------
function indicatorToolbar(key) {
  const idx = PRINCIPAL.indexOf(key);
  const prev = idx > 0 ? PRINCIPAL[idx - 1] : null;
  const next = idx >= 0 && idx < PRINCIPAL.length - 1 ? PRINCIPAL[idx + 1] : null;
  const bar = el("div", { class: "ind-toolbar" });
  bar.append(el("button", { class: "btn btn-ghost", type: "button", onclick: () => setView("panorama") }, "← Volver al panorama"));
  if (prev) bar.append(el("button", { class: "btn btn-ghost", type: "button", onclick: () => setView(prev) }, `‹ ${LABELS[prev]}`));
  if (next) bar.append(el("button", { class: "btn btn-ghost", type: "button", onclick: () => setView(next) }, `${LABELS[next]} ›`));
  bar.append(el("span", { class: "tb-spacer" }));
  bar.append(el("button", { class: "btn btn-ghost", type: "button", onclick: () => setView("calendario") }, "Calendario"));
  bar.append(el("button", { class: "btn btn-ghost", type: "button", onclick: () => window.print() }, "Imprimir ficha"));
  bar.append(el("button", { class: "btn btn-primary", type: "button", onclick: downloadExcel }, "Descargar Excel"));
  return bar;
}

function fichaHeader(ind) {
  const head = el("div", { class: "ficha-head" });
  const left = el("div", {},
    el("div", { class: "fh-sigla" }, SIGLA[ind.key]),
    el("h2", { class: "fh-name" }, ind.nombre),
    el("p", { class: "fh-desc" }, ind.descripcion || ""));
  const meta = el("div", { class: "fh-meta" });
  const rows = [
    ["Periodo de referencia", ind.periodo_referencia || ind.last_observation || "—"],
    ["Fecha de publicación", ind.fecha_publicacion || "—"],
    ["Fecha de actualización", ind.last_updated || "—"],
    ["Fuente", ind.fuente?.nombre || "—"],
  ];
  rows.forEach(([k, v]) => meta.append(el("div", { class: "fh-item" }, el("span", { class: "k" }, k), el("span", { class: "v" }, v))));
  meta.append(el("div", { class: "fh-item" }, el("span", { class: "k" }, "Estado de actualización"), el("span", { class: "v" }, estadoBadge(ind))));
  head.append(left, meta);
  return head;
}

function renderIndicatorView(key) {
  const sec = document.getElementById(`view-${key}`);
  const ind = getInd(key);
  sec.innerHTML = "";
  sec.append(indicatorToolbar(key));
  const panel = el("div", { class: "panel ficha" });
  panel.append(fichaHeader(ind));

  if (!hasData(ind)) {
    panel.append(el("div", { class: "notice" }, `Este indicador todavía no tiene observaciones cargadas. Estado: ${ind.estado}. ${ind.requiere_token ? `Se activará al configurar ${ind.requiere_token}_TOKEN y confirmar la serie oficial.` : "Se incorporará con el pipeline."} No se muestran cifras estimadas ni inventadas.`));
    if (ind.fuente?.link) panel.append(el("p", {}, el("a", { href: ind.fuente.link, target: "_blank", rel: "noopener" }, "Consultar fuente oficial ↗")));
    sec.append(panel);
    return;
  }

  const k = computeKPI(ind);
  const cfg = KPICFG[ind.key];
  const yoy = annualVar(ind, k);
  const winId = state.windows[ind.key] || state.data.meta?.default_window || "since_2018";

  // KPIs
  const mini = el("div", { class: "mini-kpis" },
    el("div", { class: "mini dark" }, el("div", { class: "lbl" }, "Cifra actual"), el("div", { class: "num" }, k.ultimoFmt), el("div", { class: "sub" }, `Periodo: ${k.ultimoP}`)),
    el("div", { class: "mini" }, el("div", { class: "lbl" }, cfg.varLabel), el("div", { class: "num", style: `color:${k.varColor}` }, k.varText), el("div", { class: "sub" }, cfg.comp)),
    yoy ? el("div", { class: "mini" }, el("div", { class: "lbl" }, "Variación anual"), el("div", { class: "num", style: `color:${yoy.pos ? COLORS.GREEN : COLORS.CRIMSON}` }, yoy.text), el("div", { class: "sub" }, "Frente al mismo periodo del año previo")) : null,
    el("div", { class: "mini" }, el("div", { class: "lbl" }, "Máximo de la serie"), el("div", { class: "num", style: `color:${COLORS.GREEN}` }, k.maxFmt), el("div", { class: "sub" }, `Periodo: ${k.maxP}`)),
    el("div", { class: "mini" }, el("div", { class: "lbl" }, "Mínimo de la serie"), el("div", { class: "num", style: `color:${COLORS.CRIMSON}` }, k.minFmt), el("div", { class: "sub" }, `Periodo: ${k.minP}`)),
  );
  panel.append(mini);

  // window toggle + chart
  const wt = el("div", { class: "win-toggle no-print", role: "group", "aria-label": "Ventana temporal" });
  WINDOWS.forEach((w) => wt.append(el("button", { class: "win-btn", type: "button", "aria-pressed": String(w.id === winId), onclick: () => { state.windows[ind.key] = w.id; mountChart(ind); wt.querySelectorAll(".win-btn").forEach((b, i) => b.setAttribute("aria-pressed", String(WINDOWS[i].id === w.id))); } }, w.label)));
  panel.append(wt);
  panel.append(el("div", { class: "chart-caption" }, CAPTIONS[ind.key] || ""));
  panel.append(el("div", { class: "chart-box", id: `chart-${ind.key}`, role: "img", "aria-label": `Gráfica de ${ind.nombre}` }));

  // Síntesis / Principales resultados (sin etiquetas HECHO/INTERPRETACIÓN)
  const syn = el("div", { class: "ficha-block" });
  syn.append(el("h3", { class: "block-sub" }, "Evolución reciente"));
  const bullets = analysis(ind, k);
  syn.append(el("p", { class: "prose" }, bullets[0]));
  if (bullets[1]) { syn.append(el("h3", { class: "block-sub" }, "Principales resultados")); syn.append(el("p", { class: "prose" }, bullets[1])); }
  panel.append(syn);

  // Desglose (breakdown) por componentes cuando aplica
  const bd = breakdown(ind, k);
  if (bd) panel.append(bd);

  // Tabla
  const tbl = el("div", { class: "ficha-block" });
  tbl.append(el("h3", { class: "block-sub" }, "Tabla de datos"));
  tbl.append(renderTable(ind, k));
  panel.append(tbl);

  // Fuente y notas
  const src = el("div", { class: "notes" });
  if (ind.notas && ind.notas.length) src.append(el("div", {}, ind.notas.join("  ·  ")));
  src.append(el("div", {}, `Fuente: ${ind.fuente?.nombre || "—"} · Unidad: ${ind.unidad || "—"} · Ajuste: ${ind.ajuste_estacional || "—"}`, ind.fuente?.link ? el("span", {}, " · ", el("a", { href: ind.fuente.link, target: "_blank", rel: "noopener" }, "serie oficial ↗")) : null));
  if (ind.proximo || ind.fecha_publicacion) src.append(el("div", {}, `Próxima publicación: ${ind.proximo || ind.fecha_publicacion}`));
  panel.append(src);

  sec.append(panel);
}

function breakdown(ind, k) {
  const last = ind.observations[k.lastI];
  if (!last) return null;
  const rowsFor = () => {
    if (ind.key === "PIBSEC") return [["Primarias", last.values[0], "num"], ["Secundarias", last.values[1], "num"], ["Terciarias", last.values[2], "num"]];
    if (ind.key === "IGAE") return [["Índice global", last.values[0], "idx"], ["Actividades secundarias", last.values[1], "idx"], ["Actividades terciarias", last.values[2], "idx"]];
    if (ind.key === "IED") return [["Nuevas inversiones", last.values[1], "usd"], ["Reinversión de utilidades", last.values[2], "usd"], ["Cuentas entre compañías", last.values[3], "usd"]];
    if (ind.key === "INPC") return [["General", last.values[0], "pct-raw"], ["Subyacente", last.values[1], "pct-raw"], ["No subyacente", last.values[2], "pct-raw"]];
    if (ind.key === "BALANZA") return [["Exportaciones", last.values[0], "usd"], ["Importaciones", last.values[1], "usd"], ["Saldo (X − M)", (last.values[0] != null && last.values[1] != null) ? last.values[0] - last.values[1] : null, "usd"]];
    return null;
  };
  const rows = rowsFor();
  if (!rows) return null;
  const box = el("div", { class: "ficha-block" });
  box.append(el("h3", { class: "block-sub" }, ind.key === "BALANZA" ? "Componentes del saldo" : ind.key === "INPC" ? "Desagregación de la inflación" : "Desempeño por componentes"));
  const g = el("div", { class: "breakdown" });
  rows.forEach(([lbl, val, fmt]) => g.append(el("div", { class: "bd-item" }, el("div", { class: "bd-lbl" }, lbl), el("div", { class: "bd-val" }, fmtVal(val, fmt)))));
  box.append(g);
  return box;
}

function renderTable(ind, k) {
  const wrap = el("div", { class: "table-wrap" });
  const table = el("table");
  table.append(el("thead", {}, el("tr", {}, el("th", {}, "Periodo"), ...ind.columns.map((c) => el("th", {}, c.label)))));
  const series = k ? k.series : [];
  const idxs = series.map((v, i) => (v == null ? -1 : i)).filter((i) => i >= 0);
  let maxI = idxs[0], minI = idxs[0];
  idxs.forEach((i) => { if (series[i] > series[maxI]) maxI = i; if (series[i] < series[minI]) minI = i; });
  const tbody = el("tbody");
  ind.observations.forEach((o, ri) => {
    const cls = ri === maxI ? "max" : (ri === minI ? "min" : "");
    tbody.append(el("tr", { class: cls }, el("td", {}, o.period), ...ind.columns.map((c) => el("td", {}, fmtVal(o.values[c.index], c.fmt)))));
  });
  table.append(tbody);
  wrap.append(table);
  return wrap;
}

// ---------------- Entorno financiero (complementarios) ----------------
function renderEntorno() {
  const sec = $("#view-entorno");
  sec.innerHTML = "";
  sec.append(el("div", { class: "section-title" }, "Entorno financiero"));
  sec.append(el("div", { class: "section-sub" }, "Indicadores complementarios (Banco de México y otros). No forman parte de los 11 principales; se activan al configurar los tokens correspondientes."));
  const grid = el("div", { class: "matrix" });
  COMPLEMENTARIOS.map(getInd).filter(Boolean).forEach((ind) => grid.append(panoramaCard(ind)));
  sec.append(grid);
  const withData = COMPLEMENTARIOS.map(getInd).filter((i) => hasData(i));
  withData.forEach((ind) => {
    const p = el("div", { class: "panel" });
    p.append(el("h3", {}, ind.nombre));
    p.append(el("div", { class: "chart-caption" }, CAPTIONS[ind.key] || ""));
    p.append(el("div", { class: "chart-box", id: `chart-${ind.key}` }));
    sec.append(p);
  });
}

// ---------------- Calendar ----------------
function renderCalendar() {
  const sec = $("#view-calendario");
  sec.innerHTML = "";
  sec.append(el("div", { class: "section-title" }, "Calendario de publicaciones"));
  const cal = state.calendario;
  if (!cal || !cal.items || !cal.items.length) {
    sec.append(el("div", { class: "notice" }, "El calendario oficial 2026 (fechas exactas) se integra a partir del PDF de la INEGI/Banxico. Mientras tanto se muestran las próximas fechas indicativas de cada indicador."));
    const panel = el("div", { class: "panel" });
    principalInds().forEach((ind) => { if (ind.proximo || ind.fecha_publicacion) panel.append(el("div", { class: "cal-item" }, el("span", { class: "date" }, ind.proximo || ind.fecha_publicacion), el("span", {}, `${LABELS[ind.key]} · ${ind.fuente?.nombre || ""} · ${ind.frecuencia || ""}`))); });
    sec.append(panel);
    return;
  }
  sec.append(el("div", { class: "section-sub" }, `Fuente: ${cal.fuente || "Calendario oficial de difusión"} · actualizado el ${cal.actualizado || cal.generated_at || "—"}.`));
  // filtro
  const filterWrap = el("div", { class: "cal-filter no-print" });
  const sel = el("select", { onchange: () => drawCalTable(sel.value) }, el("option", { value: "" }, "Todos los indicadores"));
  [...new Set(cal.items.map((c) => c.indicador))].forEach((n) => sel.append(el("option", { value: n }, n)));
  filterWrap.append(el("span", {}, "Filtrar: "), sel);
  sec.append(filterWrap);
  const tableHost = el("div", { id: "cal-table-host" });
  sec.append(tableHost);
  drawCalTable("");
}

function statusChip(st) { return el("span", { class: `cal-status ${st}` }, st || "—"); }
function drawCalTable(filter) {
  const host = document.getElementById("cal-table-host");
  if (!host) return;
  host.innerHTML = "";
  const items = (state.calendario.items || []).filter((c) => !filter || c.indicador === filter);
  const table = el("table");
  table.append(el("thead", {}, el("tr", {}, ...["Fecha", "Indicador", "Producto", "Periodo", "Frecuencia", "Institución", "Estatus"].map((h) => el("th", {}, h)))));
  const tb = el("tbody");
  items.forEach((c) => tb.append(el("tr", {},
    el("td", {}, c.fecha_publicacion || "—"), el("td", {}, c.indicador || "—"), el("td", {}, c.producto || "—"),
    el("td", {}, c.periodo_referencia || "—"), el("td", {}, c.frecuencia || "—"), el("td", {}, c.institucion || "—"),
    el("td", {}, statusChip(c.estatus)))));
  table.append(tb);
  host.append(el("div", { class: "panel", style: "padding:0;overflow:hidden" }, el("div", { class: "table-wrap", style: "max-height:none;border:none" }, table)));
}

// ---------------- Methodology ----------------
function renderMethodology() {
  const sec = $("#view-metodologia");
  sec.innerHTML = "";
  sec.append(el("div", { class: "section-title" }, "Fuentes y metodología"));
  sec.append(el("div", { class: "section-sub" }, "Estado de actualización, fuente y serie por indicador. La metodología de análisis usa reglas transparentes sobre las cifras oficiales; toda afirmación es rastreable al dato mostrado."));
  const table = el("table");
  table.append(el("thead", {}, el("tr", {}, ...["Indicador", "Fuente", "Serie", "Frecuencia", "Últ. consulta", "Últ. observación", "Estado"].map((h) => el("th", {}, h)))));
  const tb = el("tbody");
  ORDER.map(getInd).filter(Boolean).forEach((ind) => {
    tb.append(el("tr", {},
      el("td", {}, ind.nombre), el("td", {}, ind.fuente?.nombre || "—"),
      el("td", {}, ind.fuente?.serie || (ind.serie_confirmada ? "—" : "por confirmar")),
      el("td", {}, ind.frecuencia || "—"), el("td", {}, ind.fecha_consulta || ind.last_updated || "—"),
      el("td", {}, ind.last_observation || "—"), el("td", {}, estadoBadge(ind))));
  });
  table.append(tb);
  sec.append(el("div", { class: "panel", style: "padding:0;overflow:hidden" }, el("div", { class: "table-wrap", style: "max-height:none;border:none" }, table)));
  sec.append(el("div", { class: "panel" },
    el("h3", {}, "Notas metodológicas"),
    el("ul", { class: "summary-list" },
      el("li", {}, el("span", { class: "mark" }), el("span", {}, "Series originales (sin ajuste estacional) salvo indicación en contrario; las variaciones mensuales de series originales pueden incorporar efectos de calendario.")),
      el("li", {}, el("span", { class: "mark" }), el("span", {}, "El saldo de la balanza comercial es exportaciones menos importaciones; la “variación del saldo” compara ese saldo con el mes previo y no debe confundirse con el nivel del saldo.")),
      el("li", {}, el("span", { class: "mark" }), el("span", {}, "La inflación se reporta como variación anual del INPC; una reducción no se clasifica automáticamente como “mejora” sin considerar el objetivo del Banco de México.")),
      el("li", {}, el("span", { class: "mark" }), el("span", {}, "Cuando falta un token o una serie no está confirmada, se conserva el último dato validado y se señala el estado, sin presentarlo como actualización definitiva.")),
    )));
}

// ---------------- Downloads ----------------
function renderDownloads() {
  const sec = $("#view-descargas");
  sec.innerHTML = "";
  sec.append(el("div", { class: "section-title" }, "Descargas"));
  sec.append(el("div", { class: "section-sub" }, "Última versión validada de los datos y la documentación."));
  const grid = el("div", { class: "dl-grid" });
  const items = [
    ["Excel actualizado", "Todas las hojas de datos + Síntesis, Metodología y fuentes y Control de actualizaciones.", "downloads/Indicadores_Macroeconomicos_Mexico_Actualizado.xlsx", "Descargar .xlsx"],
    ["Datos (JSON)", "Capa de datos normalizada que alimenta el tablero.", "data/indicadores.json", "Ver JSON"],
    ["Datos (CSV)", "Un archivo CSV por indicador.", "data/csv/", "Ver carpeta CSV"],
    ["Manifest de actualización", "Estado, fuente y última observación por indicador.", "data/manifest.json", "Ver manifest"],
    ["Fuentes y metodología", "Documento de fuentes oficiales y método de actualización.", "DATA_SOURCES.md", "Ver documento"],
  ];
  items.forEach(([t, d, href, cta]) => grid.append(el("div", { class: "dl-card" }, el("h4", {}, t), el("p", {}, d), el("a", { class: "btn btn-ghost", href, target: "_blank", rel: "noopener" }, cta))));
  sec.append(grid);
}

// ---------------- Charts lifecycle ----------------
function mountChart(ind) {
  const dom = document.getElementById(`chart-${ind.key}`);
  if (!dom || typeof echarts === "undefined" || !hasData(ind)) return;
  let chart = state.charts[ind.key];
  if (!chart) { chart = echarts.init(dom, null, { renderer: "canvas" }); state.charts[ind.key] = chart; }
  const winId = state.windows[ind.key] || state.data.meta?.default_window || "since_2018";
  chart.setOption(buildOption(ind, winId), true);
}
function mountAllCharts() { ORDER.map(getInd).filter(Boolean).forEach((ind) => { if (KPICFG[ind.key] && hasData(ind)) mountChart(ind); }); }
function resizeVisibleCharts() { Object.entries(state.charts).forEach(([key, c]) => { const dom = document.getElementById(`chart-${key}`); if (dom && dom.offsetParent !== null) c.resize(); }); }

// ---------------- Body ----------------
function buildViewShells() {
  const host = $("#sections");
  host.innerHTML = "";
  VIEWS.forEach((v) => host.append(el("section", { class: `view${v.id === state.active ? " active" : ""}`, id: `view-${v.id}`, role: "tabpanel", "aria-labelledby": `tab-${v.id}` })));
}

function renderAll() {
  renderPanorama();
  PRINCIPAL.forEach((k) => renderIndicatorView(k));
  renderEntorno();
  renderCalendar();
  renderMethodology();
  renderDownloads();
  mountAllCharts();
  resizeVisibleCharts();
}

function downloadExcel() { window.location.href = "downloads/Indicadores_Macroeconomicos_Mexico_Actualizado.xlsx"; }

async function init() {
  try {
    state.data = await loadJSON("data/indicadores.json");
    state.manifest = await loadJSON("data/manifest.json", true);
    state.noticias = await loadJSON("data/noticias.json", true);
    state.calendario = await loadJSON("data/calendario_publicaciones.json", true) || await loadJSON("data/calendario.json", true);
  } catch (e) {
    $("#status").textContent = "No se pudieron cargar los datos (data/indicadores.json).";
    return;
  }
  $("#status").style.display = "none";
  renderHeader();
  renderNav();
  buildViewShells();
  renderAll();
  setView(state.active);
  window.addEventListener("resize", () => resizeVisibleCharts());
  $("#btn-excel").addEventListener("click", downloadExcel);
}

document.addEventListener("DOMContentLoaded", init);
