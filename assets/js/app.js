// Orquestador del dashboard ejecutivo V2.
import { ORDER, LABELS, SECTIONS, CAPTIONS, WINDOWS, COLORS, KPICFG } from "./config.js";
import { computeKPI, analysis } from "./metrics.js";
import { buildOption, applyWindow } from "./charts.js";
import { fmtVal, perLong } from "./format.js";

const state = {
  data: null,          // indicadores.json
  manifest: null,
  noticias: null,
  calendario: null,
  active: "panorama",
  windows: {},         // por indicador
  charts: {},          // instancias ECharts
  openTables: {},
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
  } catch (e) {
    if (optional) return null;
    throw e;
  }
}

function indicatorsInOrder() {
  const order = state.data.order && state.data.order.length ? state.data.order : ORDER;
  const keys = order.filter((k) => state.data.indicators[k]);
  // añade cualquier indicador extra no listado en order
  Object.keys(state.data.indicators).forEach((k) => { if (!keys.includes(k)) keys.push(k); });
  return keys.map((k) => state.data.indicators[k]);
}

function lastUpdateInfo() {
  let latest = null, refPeriod = null;
  indicatorsInOrder().forEach((ind) => {
    const d = ind.last_updated;
    if (d && (!latest || d > latest)) latest = d;
  });
  // periodo de referencia: última observación mensual más reciente
  const monthly = indicatorsInOrder().filter((i) => i.frecuencia === "Mensual");
  if (monthly.length) refPeriod = monthly.map((i) => i.last_observation).sort().slice(-1)[0];
  return { latest, refPeriod };
}

// ---------------- Header ----------------
function renderHeader() {
  const { latest, refPeriod } = lastUpdateInfo();
  $("#meta-update").textContent = latest ? new Date(latest + "T00:00:00").toLocaleDateString("es-MX", { day: "2-digit", month: "long", year: "numeric" }) : "—";
  $("#meta-period").textContent = refPeriod ? perLong(refPeriod) : "—";
}

// ---------------- Nav ----------------
function renderTabs() {
  const nav = $("#tabs");
  nav.innerHTML = "";
  SECTIONS.forEach((s) => {
    nav.append(el("button", {
      class: "tab", role: "tab", id: `tab-${s.id}`,
      "aria-selected": String(s.id === state.active),
      "aria-controls": `sec-${s.id}`,
      onclick: () => setActive(s.id),
    }, s.label));
  });
}

function setActive(id) {
  state.active = id;
  document.querySelectorAll(".tab").forEach((t) => t.setAttribute("aria-selected", String(t.id === `tab-${id}`)));
  document.querySelectorAll(".section").forEach((s) => s.classList.toggle("active", s.id === `sec-${id}`));
  // redibuja/resize las gráficas visibles
  requestAnimationFrame(() => resizeVisibleCharts());
  window.scrollTo({ top: 0, behavior: "smooth" });
}

// ---------------- Portada ejecutiva ----------------
function classifyMovers() {
  const mejoraron = [], deterioraron = [], alertas = [];
  indicatorsInOrder().forEach((ind) => {
    const k = computeKPI(ind);
    if (!k) return;
    const entry = { ind, k };
    if (k.semaforo === "bueno") mejoraron.push(entry);
    else if (k.semaforo === "malo") deterioraron.push(entry);
    if (ind.key === "INPC" && k.ultimoRaw > 4) alertas.push(`Inflación general en ${fmtVal(k.ultimoRaw, "pct-raw")} — por encima del techo del objetivo de Banxico (4%).`);
    if (ind.key === "BALANZA" && k.ultimoRaw < 0) alertas.push(`Balanza comercial en déficit (${fmtVal(k.ultimoRaw, "usd")} mdd) en ${k.ultimoP}.`);
  });
  return { mejoraron, deterioraron, alertas };
}

function executiveSummary() {
  const { mejoraron, deterioraron, alertas } = classifyMovers();
  const bullets = [];
  const fmtMover = (e) => `${LABELS[e.ind.key] || e.ind.nombre} (${e.k.varText}, ${e.k.ultimoP})`;
  if (mejoraron.length) bullets.push({ type: "hecho", text: `Indicadores con mejora en su último dato: ${mejoraron.map(fmtMover).join("; ")}.` });
  if (deterioraron.length) bullets.push({ type: "hecho", text: `Indicadores con deterioro en su último dato: ${deterioraron.map(fmtMover).join("; ")}.` });
  // motores de actividad
  const igae = state.data.indicators.IGAE, bal = state.data.indicators.BALANZA;
  if (igae) { const k = computeKPI(igae); if (k) bullets.push({ type: "hecho", text: `Actividad económica (IGAE): índice de ${fmtVal(k.ultimoRaw, "idx")} puntos en ${k.ultimoP}, ${k.varText} ${k.varLabel.toLowerCase()}.` }); }
  if (bal) { const k = computeKPI(bal); if (k) bullets.push({ type: "hecho", text: `Comercio exterior: saldo comercial de ${fmtVal(k.ultimoRaw, "usd")} mdd en ${k.ultimoP} (${k.ultimoRaw >= 0 ? "superávit" : "déficit"}).` }); }
  alertas.forEach((a) => bullets.push({ type: "implicacion", text: a }));
  bullets.push({ type: "interpretacion", text: "Lectura de coyuntura basada en reglas deterministas sobre las cifras oficiales más recientes; toda afirmación es rastreable al dato mostrado en cada tarjeta. No se atribuye causalidad." });
  return bullets.slice(0, 8);
}

function tagFor(type) {
  const map = { hecho: ["HECHO", "#1e8f5f"], implicacion: ["POSIBLE IMPLICACIÓN", COLORS.GOLD], interpretacion: ["INTERPRETACIÓN", COLORS.WINE] };
  const [label, color] = map[type] || ["", "#888"];
  return el("span", { class: "tag", style: `background:${color}` }, label);
}

function renderPortada() {
  const sec = $("#sec-panorama");
  sec.innerHTML = "";
  sec.append(el("div", { class: "section-title" }, "Panorama ejecutivo"));
  const { refPeriod, latest } = lastUpdateInfo();
  sec.append(el("div", { class: "section-sub" }, `Estado general de la economía mexicana · actualizado el ${latest ? new Date(latest + "T00:00:00").toLocaleDateString("es-MX") : "—"} · periodo de referencia: ${refPeriod ? perLong(refPeriod) : "—"}.`));

  // Tarjetas (6-10)
  const grid = el("div", { class: "cards" });
  indicatorsInOrder().slice(0, 10).forEach((ind) => {
    const k = computeKPI(ind);
    if (!k) return;
    const up = k.pos;
    const card = el("button", { class: "kpi-card", type: "button", onclick: () => goToIndicator(ind.key) },
      el("span", { class: `dot ${k.semaforo}`, title: k.semaforo }),
      el("div", { class: "name" }, LABELS[ind.key] || ind.nombre),
      el("div", { class: "period" }, `Periodo: ${k.ultimoP}`),
      el("div", { class: "value" }, k.ultimoFmt),
      el("div", { class: `delta ${up ? "up" : "down"}` }, `${k.varText}`, el("small", {}, k.varLabel)),
      el("div", { class: "src" }, `Fuente: ${ind.fuente?.nombre || "—"}`),
    );
    grid.append(card);
  });
  sec.append(grid);

  // Resumen ejecutivo
  const panel = el("div", { class: "panel" });
  panel.append(el("h3", {}, "Resumen ejecutivo"));
  panel.append(el("div", { class: "caption" }, "Puntos generados con reglas transparentes a partir de las cifras oficiales. Se distingue hecho / posible implicación / interpretación."));
  const ul = el("ul", { class: "summary-list" });
  executiveSummary().forEach((b) => {
    ul.append(el("li", {}, el("span", { class: "mark", style: `background:${b.type === "hecho" ? COLORS.GREEN : b.type === "implicacion" ? COLORS.GOLD : COLORS.WINE}` }), el("span", {}, tagFor(b.type), b.text)));
  });
  panel.append(ul);
  sec.append(panel);

  // Próximo dato
  const next = el("div", { class: "panel" });
  next.append(el("h3", {}, "Próximo dato por publicarse"));
  const nlist = el("div", {});
  indicatorsInOrder().forEach((ind) => {
    if (ind.proximo) nlist.append(el("div", { class: "cal-item" }, el("span", { class: "date" }, ind.proximo), el("span", {}, `${LABELS[ind.key] || ind.nombre} · ${ind.fuente?.nombre || ""}`)));
  });
  next.append(nlist);
  sec.append(next);
}

function goToIndicator(key) {
  const section = SECTIONS.find((s) => s.indicators.includes(key));
  if (section) { setActive(section.id); setTimeout(() => { const anchor = document.getElementById(`ind-${key}`); if (anchor) anchor.scrollIntoView({ behavior: "smooth", block: "start" }); }, 60); }
}

// ---------------- Indicator detail block ----------------
function renderIndicatorBlock(ind) {
  const k = computeKPI(ind);
  const winId = state.windows[ind.key] || state.data.meta?.default_window || "since_2018";
  const block = el("div", { class: "panel", id: `ind-${ind.key}` });
  block.append(el("h3", {}, ind.nombre));
  block.append(el("div", { class: "caption" }, CAPTIONS[ind.key] || ""));

  const grid = el("div", { class: "detail-grid" });
  const main = el("div", {});

  // mini KPIs
  if (k) {
    const cfg = KPICFG[ind.key];
    const mini = el("div", { class: "mini-kpis" },
      el("div", { class: "mini dark" }, el("div", { class: "lbl" }, "Último dato"), el("div", { class: "num" }, k.ultimoFmt), el("div", { class: "sub" }, `Periodo: ${k.ultimoP}`)),
      el("div", { class: "mini" }, el("div", { class: "lbl" }, "Variación"), el("div", { class: "num", style: `color:${k.varColor}` }, k.varText), el("div", { class: "sub" }, k.varLabel)),
      el("div", { class: "mini" }, el("div", { class: "lbl" }, "Máximo de la serie"), el("div", { class: "num", style: `color:${COLORS.GREEN}` }, k.maxFmt), el("div", { class: "sub" }, `Periodo: ${k.maxP}`)),
      el("div", { class: "mini" }, el("div", { class: "lbl" }, "Mínimo de la serie"), el("div", { class: "num", style: `color:${COLORS.CRIMSON}` }, k.minFmt), el("div", { class: "sub" }, `Periodo: ${k.minP}`)),
    );
    main.append(mini);
  }

  // window toggle
  const wt = el("div", { class: "win-toggle", role: "group", "aria-label": "Ventana temporal" });
  WINDOWS.forEach((w) => {
    wt.append(el("button", { class: "win-btn", type: "button", "aria-pressed": String(w.id === winId), onclick: () => { state.windows[ind.key] = w.id; updateChart(ind); wt.querySelectorAll(".win-btn").forEach((b, i) => b.setAttribute("aria-pressed", String(WINDOWS[i].id === w.id))); } }, w.label));
  });
  main.append(wt);

  // chart container
  const chartBox = el("div", { class: "chart-box", id: `chart-${ind.key}`, role: "img", "aria-label": `Gráfica de ${ind.nombre}` });
  main.append(chartBox);

  // analysis
  if (k) {
    const an = el("ul", { class: "analysis" });
    analysis(ind, k).forEach((b, i) => an.append(el("li", {}, el("span", { class: "mark", style: `background:${i === 0 ? COLORS.GREEN : COLORS.GOLD}` }), el("span", {}, b))));
    main.append(el("div", { style: "margin-top:16px" }, an));
  }

  // table (accordion)
  const tableSection = el("div", { style: "margin-top:8px" });
  const openKey = ind.key;
  const btn = el("button", { class: "accordion-btn", type: "button", "aria-expanded": String(!!state.openTables[openKey]), onclick: () => { state.openTables[openKey] = !state.openTables[openKey]; renderSectionsBody(); } },
    el("span", { class: "lbl" }, "Tabla de datos ", el("span", { class: "hint" }, `${ind.observations.length} registros`)),
    el("span", {}, state.openTables[openKey] ? "▾" : "▸"));
  tableSection.append(btn);
  if (state.openTables[openKey]) tableSection.append(renderTable(ind, k));
  main.append(tableSection);

  grid.append(main);
  grid.append(renderSide(ind));
  block.append(grid);
  return block;
}

function renderSide(ind) {
  const side = el("aside", { class: "info-side" });
  side.append(el("div", { class: "head" }, "Información del indicador"));
  const body = el("div", { class: "body" });
  body.append(el("div", { class: "info-row" }, el("div", { class: "k" }, "Descripción"), el("div", { class: "v" }, ind.descripcion || "—")));
  const rows = [
    ["Frecuencia", ind.frecuencia], ["Unidad", ind.unidad], ["Ajuste estacional", ind.ajuste_estacional],
    ["Próximo dato", ind.proximo, true], ["Periodo a publicar", ind.publicacion], ["Fuente", ind.fuente?.nombre],
  ];
  rows.forEach(([kk, vv, hi]) => { if (!vv) return; body.append(el("div", { class: `info-row${hi ? " hi" : ""}` }, el("div", { class: "k" }, kk), el("div", { class: "v" }, vv))); });
  if (ind.fuente?.link) body.append(el("div", { class: "info-row" }, el("div", { class: "k" }, "Consulta"), el("div", { class: "v" }, el("a", { href: ind.fuente.link, target: "_blank", rel: "noopener" }, "Fuente oficial ↗"))));
  side.append(body);
  return side;
}

function renderTable(ind, k) {
  const wrap = el("div", { class: "table-wrap" });
  const table = el("table");
  const thead = el("thead");
  const htr = el("tr", {}, el("th", {}, "Periodo"), ...ind.columns.map((c) => el("th", {}, c.label)));
  thead.append(htr);
  const series = k ? k.series : [];
  const idxs = series.map((v, i) => (v == null ? -1 : i)).filter((i) => i >= 0);
  let maxI = idxs[0], minI = idxs[0];
  idxs.forEach((i) => { if (series[i] > series[maxI]) maxI = i; if (series[i] < series[minI]) minI = i; });
  const tbody = el("tbody");
  ind.observations.forEach((o, ri) => {
    const cls = ri === maxI ? "max" : (ri === minI ? "min" : "");
    const tr = el("tr", { class: cls }, el("td", {}, o.period), ...ind.columns.map((c) => el("td", {}, fmtVal(o.values[c.index], c.fmt))));
    tbody.append(tr);
  });
  table.append(thead, tbody);
  wrap.append(table);
  const notes = el("div", { class: "notes" });
  if (ind.notas && ind.notas.length) notes.append(el("div", {}, ind.notas.join("  ·  ")));
  notes.append(el("div", {}, "Celdas resaltadas: verde = máximo, rojo = mínimo. Última fila = dato más reciente. Cifras sujetas a revisión oficial."));
  notes.append(el("div", {}, `Fuente: ${ind.fuente?.nombre || "—"}`, ind.fuente?.link ? el("span", {}, " · ", el("a", { href: ind.fuente.link, target: "_blank", rel: "noopener" }, "serie completa ↗")) : null));
  wrap.append(notes);
  return wrap;
}

// ---------------- Themed sections ----------------
function renderThematicSections() {
  SECTIONS.filter((s) => s.indicators.length).forEach((s) => {
    const sec = document.getElementById(`sec-${s.id}`);
    sec.innerHTML = "";
    sec.append(el("div", { class: "section-title" }, s.label));
    let any = false;
    s.indicators.forEach((key) => { const ind = state.data.indicators[key]; if (ind) { sec.append(renderIndicatorBlock(ind)); any = true; } });
    if (!any) sec.append(el("div", { class: "notice" }, "Indicadores de esta sección aún no disponibles en la capa de datos. Se incorporarán con el pipeline."));
  });
}

function renderNews() {
  const sec = $("#sec-noticias");
  sec.innerHTML = "";
  sec.append(el("div", { class: "section-title" }, "Noticias y eventos relevantes"));
  sec.append(el("div", { class: "section-sub" }, "Sección modular alimentada por RSS y comunicados oficiales. No sustituye al análisis estadístico y no afirma causalidad."));
  const items = state.noticias?.items || [];
  if (!items.length) {
    sec.append(el("div", { class: "notice" }, "No hay noticias cargadas en este momento (o los RSS oficiales no respondieron). El dashboard principal no se ve afectado. Ver limitaciones en la documentación."));
    return;
  }
  if (state.noticias?.generated_at) sec.append(el("div", { class: "section-sub" }, `Última recopilación: ${new Date(state.noticias.generated_at).toLocaleString("es-MX")}.`));
  items.forEach((it) => {
    const item = el("div", { class: "news-item" },
      el("div", { class: "meta" }, el("span", {}, it.fecha || ""), el("span", {}, "·"), el("span", {}, it.fuente || ""), it.categoria ? el("span", { class: "chip" }, it.categoria) : null, it.indicador ? el("span", { class: "chip" }, it.indicador) : null),
      el("h4", {}, it.titulo || ""),
      it.porque ? el("p", {}, el("strong", {}, "Por qué importa: "), it.porque) : null,
      it.enlace ? el("p", {}, el("a", { href: it.enlace, target: "_blank", rel: "noopener" }, "Fuente original ↗")) : null,
    );
    sec.append(item);
  });
}

function renderCalendar() {
  const sec = $("#sec-calendario");
  sec.innerHTML = "";
  sec.append(el("div", { class: "section-title" }, "Calendario de publicaciones"));
  sec.append(el("div", { class: "section-sub" }, "Próximas fechas esperadas según el calendario oficial de difusión de cada fuente."));
  const panel = el("div", { class: "panel" });
  const items = state.calendario?.items;
  if (items && items.length) {
    items.forEach((c) => panel.append(el("div", { class: "cal-item" }, el("span", { class: "date" }, c.fecha_esperada || ""), el("span", {}, `${c.indicador} · ${c.institucion || ""} · ${c.periodo || ""} (${c.frecuencia || ""})`))));
  } else {
    indicatorsInOrder().forEach((ind) => { if (ind.proximo) panel.append(el("div", { class: "cal-item" }, el("span", { class: "date" }, ind.proximo), el("span", {}, `${LABELS[ind.key] || ind.nombre} · ${ind.fuente?.nombre || ""} · ${ind.frecuencia || ""}`))); });
  }
  sec.append(panel);
}

function renderMethodology() {
  const sec = $("#sec-metodologia");
  sec.innerHTML = "";
  sec.append(el("div", { class: "section-title" }, "Fuentes y metodología"));
  sec.append(el("div", { class: "section-sub" }, "Ficha por indicador: fuente, unidad, frecuencia, ajuste estacional y enlace oficial."));
  const table = el("table");
  table.append(el("thead", {}, el("tr", {}, ...["Indicador", "Fuente", "Unidad", "Frecuencia", "Ajuste", "Última obs.", "Actualizado", "Enlace"].map((h) => el("th", {}, h)))));
  const tb = el("tbody");
  indicatorsInOrder().forEach((ind) => {
    tb.append(el("tr", {}, el("td", {}, ind.nombre), el("td", {}, ind.fuente?.nombre || "—"), el("td", {}, ind.unidad || "—"), el("td", {}, ind.frecuencia || "—"), el("td", {}, ind.ajuste_estacional || "—"), el("td", {}, ind.last_observation || "—"), el("td", {}, ind.last_updated || "—"), el("td", {}, ind.fuente?.link ? el("a", { href: ind.fuente.link, target: "_blank", rel: "noopener" }, "↗") : "—")));
  });
  table.append(tb);
  sec.append(el("div", { class: "panel", style: "padding:0;overflow:hidden" }, el("div", { class: "table-wrap", style: "max-height:none;border:none" }, table)));
}

function renderDownloads() {
  const sec = $("#sec-descargas");
  sec.innerHTML = "";
  sec.append(el("div", { class: "section-title" }, "Descargas"));
  sec.append(el("div", { class: "section-sub" }, "Descarga la última versión validada de los datos y la documentación."));
  const grid = el("div", { class: "dl-grid" });
  const items = [
    ["Excel actualizado", "Todas las hojas + Resumen ejecutivo, Metodología y Control de actualizaciones.", "downloads/Indicadores_Macroeconomicos_Mexico_Actualizado.xlsx", "Descargar .xlsx"],
    ["Datos (JSON)", "Capa de datos normalizada que alimenta el dashboard.", "data/indicadores.json", "Ver JSON"],
    ["Datos (CSV)", "Un archivo CSV por indicador.", "data/csv/", "Ver carpeta CSV"],
    ["Metodología y fuentes", "Documento de fuentes oficiales y método de actualización.", "DATA_SOURCES.md", "Ver documento"],
    ["Dashboard original", "Copia de referencia del dashboard previo (respaldo).", "legacy/dashboard-original.html", "Abrir respaldo"],
  ];
  items.forEach(([t, d, href, cta]) => grid.append(el("div", { class: "dl-card" }, el("h4", {}, t), el("p", {}, d), el("a", { class: "btn btn-ghost", href, target: "_blank", rel: "noopener" }, cta))));
  sec.append(grid);
}

// ---------------- Charts lifecycle ----------------
function mountChart(ind) {
  const dom = document.getElementById(`chart-${ind.key}`);
  if (!dom || typeof echarts === "undefined") return;
  let chart = state.charts[ind.key];
  if (!chart) { chart = echarts.init(dom, null, { renderer: "canvas" }); state.charts[ind.key] = chart; }
  const winId = state.windows[ind.key] || state.data.meta?.default_window || "since_2018";
  chart.setOption(buildOption(ind, winId), true);
}
function updateChart(ind) { mountChart(ind); }
function mountAllCharts() { Object.values(state.data.indicators).forEach((ind) => { if (KPICFG[ind.key]) mountChart(ind); }); }
function resizeVisibleCharts() { Object.entries(state.charts).forEach(([key, c]) => { const dom = document.getElementById(`chart-${key}`); if (dom && dom.offsetParent !== null) c.resize(); }); }

// ---------------- Body render ----------------
function renderSectionsBody() {
  renderPortada();
  renderThematicSections();
  renderNews();
  renderCalendar();
  renderMethodology();
  renderDownloads();
  mountAllCharts();
  resizeVisibleCharts();
}

function buildSectionShells() {
  const host = $("#sections");
  host.innerHTML = "";
  SECTIONS.forEach((s) => host.append(el("section", { class: `section${s.id === state.active ? " active" : ""}`, id: `sec-${s.id}`, role: "tabpanel", "aria-labelledby": `tab-${s.id}` })));
}

async function init() {
  try {
    state.data = await loadJSON("data/indicadores.json");
    state.manifest = await loadJSON("data/manifest.json", true);
    state.noticias = await loadJSON("data/noticias.json", true);
    state.calendario = await loadJSON("data/calendario.json", true);
  } catch (e) {
    $("#status").textContent = "No se pudieron cargar los datos (data/indicadores.json). Verifica la ruta.";
    return;
  }
  $("#status").style.display = "none";
  renderHeader();
  renderTabs();
  buildSectionShells();
  renderSectionsBody();
  setActive(state.active);
  window.addEventListener("resize", () => resizeVisibleCharts());
  // Descargar Excel
  $("#btn-excel").addEventListener("click", () => { window.location.href = "downloads/Indicadores_Macroeconomicos_Mexico_Actualizado.xlsx"; });
  $("#btn-print").addEventListener("click", () => window.print());
}

document.addEventListener("DOMContentLoaded", init);
