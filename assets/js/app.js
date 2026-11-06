// Orquestador del tablero macroeconómico V3 (navegación por indicador).
import { ORDER, PRINCIPAL, COMPLEMENTARIOS, LABELS, SIGLA, CAPTIONS, WINDOWS, IED_WINDOWS, IED_WINDOWS_FLUJO, COLORS, KPICFG, VIEWS, ESTADOS } from "./config.js";
import { computeKPI, analysis, annualVar } from "./metrics.js";
import { buildOption, rangeStats, applyWindow, buildPibsecLevels, buildPibsecVariations, buildIgaeLevels, buildIgaeVariations, buildImaiLevels, buildImaiVariations, buildEmimLevels, buildEmimVariations, buildBcmmLevels, buildBcmmVariations, buildImfbcfLevels, buildImfbcfVariations, buildDesocupRates, buildDesocupPoblacion, buildEmoeSectors, buildSicComponents, buildReservasLevel, buildReservasChange } from "./charts.js";
import { fmtVal, perLong, perShort } from "./format.js";
import * as cal from "./calendar.js?v=editorial-20261106";

const state = {
  data: null, manifest: null, noticias: null, calendario: null,
  active: "panorama", windows: {}, charts: {}, openTables: {},
};

const FONT = "'Noto Sans', system-ui, sans-serif";

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

const signedPct = (v) => v == null ? "—" : (v > 0 ? "+" : "") + fmtVal(v, "pct-frac");

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

// ---------------- Calendario (fechas oficiales) ----------------
const calCtx = () => ({ state, $, el, getInd, setView, openModal, closeModal });
function nextPublication(key) { return cal.nextPublication(calCtx(), key); }
function upcomingPublications(n = 8) { return cal.upcomingPublications(calCtx(), n); }
function calendarioDisponible(ind) { return cal.calendarioDisponible(calCtx(), ind); }
function openCalendarioFiltro(ind) { cal.openCalendarioFiltro(calCtx(), ind); }
function buildCalendarioPanel(ind) { return cal.buildCalendarioPanel(calCtx(), ind); }
function renderCalendar() { cal.renderCalendar(calCtx()); }

function sourceInstitution(source) {
  return /INEGI/i.test(source) ? "INEGI" : /Banco de M[eé]xico|Banxico/i.test(source) ? "Banco de México" : /Secretar[ií]a de Econom[ií]a/i.test(source) ? "Secretaría de Economía" : source;
}

function estadoBadge(ind) {
  const est = ind.estado || "no disponible";
  const cfg = ESTADOS[est] || { cls: "na", short: est };
  return el("span", { class: `state-badge ${cfg.cls}`, title: est }, cfg.short);
}

// ---------------- Productos por indicador ----------------
function xlsxUrl(ind) { return ind.url_excel_individual || `downloads/indicadores/${ind.key}/${ind.key}_datos.xlsx`; }
function notaUrl(ind) { return ind.url_nota_individual || `downloads/indicadores/${ind.key}/nota/${ind.key}_nota.docx`; }

function openExternalLink(url) {
  if (!url) return;
  const a = document.createElement("a");
  a.href = url;
  a.target = "_blank";
  a.rel = "noopener noreferrer";
  a.style.display = "none";
  document.body.appendChild(a);
  a.click();
  a.remove();
}

function openBoletin(url) {
  openExternalLink(url);
}

function downloadProduct(url, fallbackName) {
  if (!url) return;
  const a = document.createElement("a");
  a.href = url;
  a.download = fallbackName || url.split("/").pop();
  a.rel = "noopener noreferrer";
  document.body.appendChild(a);
  a.click();
  a.remove();
}

function productBtn(label, icon, enabled, title, onClick, kind) {
  const cls = enabled ? "btn btn-ghost product-ok" : "btn btn-ghost product-disabled";
  const attrs = {
    class: cls,
    type: "button",
    title: title || label,
    "data-product": kind || label.toLowerCase(),
    "aria-disabled": enabled ? undefined : "true",
  };
  if (!enabled) {
    attrs.tabindex = "-1";
    attrs.onclick = () => {};
  } else {
    attrs.onclick = (e) => onClick(e);
  }
  return el("button", attrs, el("span", { "aria-hidden": "true" }, icon), label);
}

function productToolbar(ind) {
  const bar = el("div", { class: "product-bar", "data-key": ind.key });

  // Boletín: prioridad 1 = url_boletin_oficial; 2 = calendario Sala de Prensa INEGI;
  // 3 = url_fuente_oficial/BIE solo como último respaldo técnico. Así el botón
  // BOLETÍN no lleva normalmente al BIE, que es fuente de datos, no Sala de Prensa.
  const esInegi = (ind.fuente && (ind.fuente.nombre || "").includes("INEGI"));
  const CALENDARIO_PRENSA = "https://www.inegi.org.mx/app/saladeprensa/calendario/";
  let boletinUrl = null;
  let boletinTitle = "Abrir último boletín oficial";
  if (esInegi) {
    boletinUrl = ind.url_boletin_oficial || CALENDARIO_PRENSA || ind.url_fuente_oficial || (ind.fuente && ind.fuente.link) || null;
    if (boletinUrl === CALENDARIO_PRENSA) {
      boletinTitle = "Abrir publicaciones oficiales del INEGI";
    } else if (!boletinUrl) {
      boletinTitle = "Boletín / fuente oficial no identificado";
    }
  } else {
    boletinUrl = ind.url_boletin_oficial || ind.url_fuente_oficial || (ind.fuente && ind.fuente.link) || null;
    if (!boletinUrl) {
      boletinTitle = "Boletín / fuente oficial no identificado";
    }
  }
  const boletinEnabled = !!boletinUrl;

  // Nota institucional: habilitada sólo cuando existe el .docx vigente.
  const notaReady = !!ind.nota_disponible;
  const notaTitle = notaReady
    ? `Descargar nota Word · ${ind.nota?.periodo || ind.periodo_referencia || ""}`
    : (ind.nota_causa || "Nota institucional en preparación");

  // Excel: activo si se generó el archivo individual.
  const xlsxReady = !!ind.xlsx_disponible;
  const xlsxTitle = xlsxReady
    ? "Descargar Excel individual"
    : (ind.xlsx_causa || "Excel individual no generado");

  bar.append(
    productBtn(ind.boletin_label || "Boletín oficial", "", boletinEnabled, boletinTitle, () => openBoletin(boletinUrl), "boletin"),
    productBtn("Descargar nota Word", "↓", notaReady, notaTitle, () => downloadProduct(notaUrl(ind), `${ind.key}_nota.docx`), "nota"),
    productBtn("Excel", "↓", xlsxReady, xlsxTitle, () => downloadProduct(xlsxUrl(ind), `${ind.key}_datos.xlsx`), "excel")
  );
  if (["IMAI", "IGAE", "IMOAM", "EMIM"].includes(ind.key)) {
    const uploadButton = productBtn("Cargar boletín", "↑", true, "Crear una nota Word desde un PDF, sin subirlo al servidor", () => {
      const head = bar.closest(".ficha-head");
      if (!head) return;
      const previous = head.querySelector(".bulletin-upload-panel");
      if (previous) { previous.remove(); uploadButton.setAttribute("aria-expanded", "false"); return; }
      const close = () => { panel.remove(); uploadButton.setAttribute("aria-expanded", "false"); uploadButton.focus(); };
      const panel = el("section", { class: "bulletin-upload-panel", id: `bulletin-upload-${ind.key}`, "aria-label": `Crear nota desde un boletín ${ind.key}` });
      const closeButton = el("button", { type: "button", class: "btn bulletin-panel-close", onclick: close, "aria-label": "Cerrar carga de boletín" }, "Cerrar ×");
      const frame = el("iframe", { src: `cargar-boletin.html?embedded=1&indicator=${ind.key}&v=actividad-manufactura-20261106`, title: `Generador local de notas ${ind.key}`, class: "bulletin-upload-frame", referrerpolicy: "no-referrer" });
      panel.append(el("div", { class: "bulletin-panel-heading" }, el("h3", {}, "Nota desde un boletín recibido"), closeButton), frame);
      head.append(panel);
      uploadButton.setAttribute("aria-expanded", "true");
      closeButton.focus();
    }, "cargar-boletin");
    uploadButton.setAttribute("aria-expanded", "false");
    uploadButton.setAttribute("aria-controls", `bulletin-upload-${ind.key}`);
    bar.append(uploadButton);
  }
  const noteButton = bar.querySelector('[data-product="nota"]');
  if (noteButton) bar.prepend(noteButton);
  return bar;
}

// ---------------- Modal de calendario individual ----------------
let modal = null;
function ensureModal() {
  if (modal) return modal;
  const overlay = $("#modal-overlay");
  if (!overlay) return null;
  const close = () => closeModal();
  overlay.hidden = false;
  $("#modal-close").addEventListener("click", close);
  $("#modal-backdrop").addEventListener("click", close);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") close(); });
  modal = {
    overlay,
    title: $("#modal-title"),
    body: $("#modal-body"),
  };
  return modal;
}
function openModal(title, bodyContent) {
  const m = ensureModal();
  if (!m) return;
  m.title.textContent = title;
  m.body.innerHTML = "";
  m.body.append(bodyContent);
  m.overlay.classList.add("active");
  m.overlay.setAttribute("aria-hidden", "false");
  m.overlay.hidden = false;
  document.body.style.overflow = "hidden";
  requestAnimationFrame(() => m.body.querySelector("button, [href]")?.focus());
}
function closeModal() {
  if (!modal) return;
  modal.overlay.classList.remove("active");
  modal.overlay.setAttribute("aria-hidden", "true");
  modal.overlay.hidden = true;
  document.body.style.overflow = "";
}

// ---------------- Header ----------------
function renderHeader() {
  const meta = state.data.meta || {};
  const lastUpdate = meta.last_update_ct;
  if (lastUpdate) {
    const d = new Date(lastUpdate);
    $("#meta-update").textContent = d.toLocaleDateString("es-MX", { timeZone: "America/Mexico_City", day: "2-digit", month: "long", year: "numeric" });
    $("#meta-update").setAttribute("title", d.toLocaleString("es-MX", { timeZone: "America/Mexico_City" }));
  } else {
    $("#meta-update").textContent = "—";
    $("#meta-update").removeAttribute("title");
  }
}

// ---------------- Navigation ----------------
function renderNav() {
  const nav = $("#tabs");
  nav.innerHTML = "";
  const row = el("div", { class: "nav-row" });
  // Navegación discreta por secciones; las fichas se abren desde las tarjetas
  // del panorama, no desde una barra de indicadores duplicada.
  VIEWS.filter((v) => v.type === "home" || v.type === "page").forEach((v) => {
    const btn = el("button", { class: "tab", role: "tab", id: `tab-${v.id}`, "aria-selected": String(v.id === state.active), "aria-controls": `view-${v.id}`, onclick: () => setView(v.id) }, v.label);
    row.append(btn);
  });
  nav.append(row);
}

function setView(id) {
  state.active = id;
  const section=PRINCIPAL.includes(id) ? "panorama" : COMPLEMENTARIOS.includes(id) ? "entorno" : id;
  document.querySelectorAll(".tab").forEach(t=>{
    const selected=t.id === `tab-${section}`;
    t.setAttribute("aria-selected",String(selected));
    t.setAttribute("aria-controls",selected ? `view-${id}` : `view-${t.id.slice(4)}`);
  });
  document.querySelectorAll(".view").forEach((s) => s.classList.toggle("active", s.id === `view-${id}`));
  document.body.setAttribute("data-view", id);
  if (`#${id}` !== window.location.hash) { try { history.replaceState(null, "", `#${id}`); } catch (e) { /* file:// */ } }
  requestAnimationFrame(() => {
    const ind = getInd(id);
    if (ind) mountChart(ind);
    resizeVisibleCharts();
  });
  window.scrollTo({ top: 0, behavior: "smooth" });
}
const validView = (id) => VIEWS.some((v) => v.id === id);

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
  const cfg = KPICFG[ind.key];
  const metrics = ind.metrics || {};
  const k = metrics.kpi || computeKPI(ind);
  const stateBadge = ind.estado === "ACTUALIZADO" ? null : estadoBadge(ind);
  const sigla = SIGLA[ind.key] || ind.key;
  const fullName = ind.nombre || LABELS[ind.key];
  let period = k ? k.ultimoP : (ind.last_observation || "—");
  if (ind.key === "RESERVAS") period = period.toUpperCase();

  const top = el("div", { class: "mc-top" },
    el("div", { class: "mc-title" }, sigla),
    stateBadge
  );
  const name = el("div", { class: "mc-name" }, fullName);
  const eyebrow = el("div", { class: "mc-eyebrow" }, period);

  if (!k) {
    return el("button", { class: "matrix-card na", type: "button", onclick: () => setView(ind.key) },
      top, name, eyebrow,
      el("div", { class: "mc-value muted" }, "Sin dato"),
      el("div", { class: "mc-metric" }, "—"),
      el("div", { class: "spark empty" }),
      el("div", { class: "mc-sub" }, "Se activará al cargar la fuente oficial."));
  }

  const yoy = metrics.yoy || annualVar(ind, k);
  const deltaCls = k.assessment === "favorable" ? "up" : (k.assessment === "adverso" ? "down" : "flat");
  const showYoy = ind.key !== "IED" && ind.key !== "TASA" && yoy && (yoy.mag === null || Math.abs((yoy.mag ?? 0) - (k.ultimoRaw ?? 0)) > 1e-9);
  const flowKpi = ind.key === "IED" && k.flujoText ? { text: k.flujoText, label: cfg.flowLabel || "Flujo del 2T" } : null;
  const yoyKpi = ind.key === "IED" && yoy ? { text: yoy.text, label: yoy.label || "Var. anual flujo" } : null;

  const decisionKpi = ind.key === "TASA" && k.decisionDisplay
    ? { text: k.decisionDisplay, label: `${k.decisionLabel} · ${k.decisionText}` }
    : null;
  const adjKpi = ind.key === "TASA" && k.yoyText
    ? { text: k.varText, label: `${k.yoyLabel} · ${k.yoyText}` }
    : null;

  const secondKpi = decisionKpi || adjKpi || flowKpi ||
    (showYoy ? { text: yoy.text, label: yoy.label || "Var. anual" } : null) ||
    (yoyKpi ? { text: yoyKpi.text, label: yoyKpi.label } : null);

  const card = el("button", { class: "matrix-card", type: "button", onclick: () => setView(ind.key) },
    top, name, eyebrow,
    el("div", { class: "mc-value" }, k.ultimoFmt),
    el("div", { class: "mc-metric" }, cfg.mainLabel || "Cifra principal"),
    sparkline(k),
    el("div", { class: "mc-deltas" },
      el("div", { class: `mc-delta ${deltaCls}` }, el("span", { class: "d-val" }, k.varText), el("span", { class: "d-lbl" }, k.varLabel || cfg.varLabel)),
      secondKpi ? el("div", { class: "mc-delta neutral" }, el("span", { class: "d-val" }, secondKpi.text), el("span", { class: "d-lbl" }, secondKpi.label)) : null),
  );
  splitMetricValue(card.querySelector(".mc-value"));
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

function renderPanorama() {
  const sec = $("#view-panorama");
  sec.innerHTML = "";
  sec.append(el("div", { class: "section-title" }, "Panorama macroeconómico"));


  // Alerta discreta de estado global (rezagos y errores de fuente).
  const rezagados = principalInds().filter((i) => i.estado === "REZAGADO");
  const errores = principalInds().filter((i) => i.estado === "ERROR DE FUENTE");
  const pendientes = principalInds().filter((i) => i.estado === "PUBLICACIÓN PENDIENTE");
  if (rezagados.length || errores.length || pendientes.length) {
    const parts = [];
    if (rezagados.length) parts.push(`${rezagados.length} indicador(es) REZAGADO(s)`);
    if (errores.length) parts.push(`${errores.length} indicador(es) con ERROR DE FUENTE`);
    if (pendientes.length) parts.push(`${pendientes.length} con publicación pendiente`);
    sec.append(el("div", { class: "alert-discreet" }, el("span", { class: "ad-dot" }), `Estado de los datos: ${parts.join("; ")}. Detalle en “Fuentes y metodología”.`));
  }

  // Matriz de 12 indicadores principales.
  const grid = el("div", { class: "matrix" });
  principalInds().forEach((ind) => grid.append(panoramaCard(ind)));
  sec.append(grid);

  // Paneles laterales: movimientos y próximos datos.
  const cols = el("div", { class: "panorama-cols" });

  const { avances, retrocesos, senales } = classifyPanorama();
  const movBox = el("div", { class: "panel" });
  movBox.append(el("h3", {}, "Balance de movimientos"));
  const counts = el("div", {class:"movement-counts"});
  [["Favorables",avances.length,"up"],["Adversos",retrocesos.length,"down"],["Sin clasificación",principalInds().filter(hasData).length-avances.length-retrocesos.length,"neutral"]].forEach(([label,count,cls])=>
    counts.append(el("div",{class:`movement-count ${cls}`},el("strong",{},String(count)),el("span",{},label))));
  movBox.append(counts,el("p",{class:"caption"},"Según la comparación propia de cada indicador; los periodos de referencia pueden diferir."));
  if(senales.length) movBox.append(el("ul",{class:"attention-list"},...senales.slice(0,2).map(text=>el("li",{},text))));
  movBox.append(el("a",{class:"acceso-link",href:"#metodologia"},"Criterios de interpretación →"));
  cols.append(movBox);

  const next = el("div", { class: "panel" });
  next.append(el("h3", {}, "Próximos datos por publicarse"));
  const nlist = el("div", {});
  const upcoming = upcomingPublications(3);
  if (upcoming.length) {
    upcoming.forEach((c) => {
      const row = el("div", { class: "cal-item" }, el("span", { class: "date" }, c.fecha_publicacion || "—"), el("span", {}, `${c.indicador} · ${c.periodo_referencia || ""}`));
      if (c.clave && getInd(c.clave)) { row.classList.add("clickable"); row.setAttribute("role", "link"); row.addEventListener("click", () => setView(c.clave)); }
      nlist.append(row);
    });
  } else {
    principalInds().forEach((ind) => { if (ind.proximo) nlist.append(el("div", { class: "cal-item" }, el("span", { class: "date" }, ind.proximo), el("span", {}, `${LABELS[ind.key]} · ${ind.fuente?.nombre || ""}`))); });
    if (!nlist.children.length) nlist.append(el("div", { class: "muted" }, "Sin fechas confirmadas. Ver Calendario de publicaciones."));
  }
  next.append(nlist,el("a",{class:"acceso-link",href:"#calendario"},"Ver calendario completo →"));
  cols.append(next);
  sec.append(cols);
}

// ---------------- Indicator view ----------------
function indicatorSection(key) {
  if (PRINCIPAL.includes(key)) return PRINCIPAL;
  if (COMPLEMENTARIOS.includes(key)) return COMPLEMENTARIOS;
  return ORDER;
}

function indicatorToolbar(key) {
  const section = indicatorSection(key);
  const idx = section.indexOf(key);
  const prev = idx > 0 ? section[idx - 1] : null;
  const next = idx >= 0 && idx < section.length - 1 ? section[idx + 1] : null;
  const isFinancial = COMPLEMENTARIOS.includes(key);
  const backTarget = isFinancial ? "entorno" : "panorama";
  const backLabel = isFinancial ? "← Volver al entorno" : "← Volver al panorama";
  const ind = getInd(key);
  const wrap = el("div", { class: "ind-toolbar-wrap" });
  const nav = el("div", { class: "ind-nav" });
  nav.append(el("a", { class: "nav-link", href: `#${backTarget}`, onclick: (e) => { e.preventDefault(); setView(backTarget); } }, backLabel));
  if (prev) nav.append(el("a", { title: LABELS[prev], class: "nav-link", href: `#${prev}`, onclick: (e) => { e.preventDefault(); setView(prev); } }, `‹ ${SIGLA[prev] || LABELS[prev]}`));
  if (next) nav.append(el("a", { title: LABELS[next], class: "nav-link", href: `#${next}`, onclick: (e) => { e.preventDefault(); setView(next); } }, `${SIGLA[next] || LABELS[next]} ›`));
  wrap.append(nav);

  return wrap;
}

// Fecha exacta de publicación del dato (solo si no es una descripción de rezago).
function fechaPubDato(ind) {
  const v = ind.fecha_publicacion || "";
  return (v && !/aproximad/i.test(v)) ? v : null;
}
// Rezago habitual de publicación (texto declarativo del calendario de difusión).
function rezagoHabitual(ind) { return ind.publicacion || (/aproximad/i.test(ind.fecha_publicacion || "") ? ind.fecha_publicacion : null); }

// Tabla compacta Componente | Estado para indicadores sin serie confirmada.
function componentStatusTable(title, components) {
  const box = el("div", { class: "ficha-block" });
  box.append(el("h3", { class: "block-sub" }, title));
  const table = el("table");
  table.append(el("thead", {}, el("tr", {}, el("th", {}, "Componente"), el("th", {}, "Estado"))));
  const tb = el("tbody");
  components.forEach((c) => tb.append(el("tr", {}, el("td", {}, c), el("td", {}, "Pendiente de conexión"))));
  table.append(tb);
  box.append(el("div", { class: "table-wrap", style: "max-height:none;border:none" }, table));
  return box;
}

function fichaHeader(ind) {
  const head = el("div", { class: "ficha-head" });
  const period=ind.periodo_referencia || ind.last_observation || "—";
  const source=ind.fuente?.nombre || "Fuente oficial";
  const institution=sourceInstitution(source);
  const identity=el("div",{class:"fh-identity"},
    el("div",{class:"fh-sigla"},SIGLA[ind.key] || ind.key),
    el("h2",{class:"fh-name"},ind.nombre),
    el("div",{class:"fh-context"},el("span",{class:"fh-period"},period),
      el("span",{class:"fh-source"},institution),estadoBadge(ind)));
  const top=el("div",{class:"fh-top"},identity,productToolbar(ind));
  const dates=el("div",{class:"fh-dates"});
  const pub=fechaPubDato(ind);
  if(pub) dates.append(el("div",{},el("span",{class:"fh-date-label"},"Publicado"),el("span",{},pub)));
  const np=ind.proxima_publicacion || nextPublication(ind.key);
  if(np) dates.append(el("div",{},el("span",{class:"fh-date-label"},ind.key==="TASA" ? "Próxima decisión" : "Próxima publicación"),
    el("span",{},np.fecha_publicacion || "Por anunciar")));
  if(calendarioDisponible(ind)) dates.append(productBtn("Ver calendario","",true,"Consultar calendario del indicador",()=>openCalendarioFiltro(ind),"calendario"));
  const details=el("details",{class:"fh-details"},el("summary",{},"Acerca del indicador y la fuente"));
  if(ind.descripcion) details.append(el("p",{class:"fh-desc"},ind.descripcion));
  const rows=[
    ["Frecuencia",ind.frecuencia], ind.frecuencia_original !== ind.frecuencia ? ["Frecuencia original",ind.frecuencia_original] : null,
    institution !== source ? ["Fuente",source] : null,
    ["Última observación original",ind.fecha_ultima_observacion],
    ["Rezago habitual",rezagoHabitual(ind)],
    ["Consulta de la fuente",ind.fecha_consulta || ind.last_updated],
    np?.periodo_referencia ? ["Periodo de la próxima publicación",np.periodo_referencia] : null
  ].filter(r=>r && r[1]);
  const metadata=el("dl",{class:"fh-technical"});
  rows.forEach(([key,value])=>metadata.append(el("div",{},el("dt",{},key),el("dd",{},value))));
  details.append(metadata);
  if(ind.fuente?.link) details.append(el("a",{href:ind.fuente.link,target:"_blank",rel:"noopener noreferrer"},"Consultar fuente oficial ↗"));
  head.append(top,dates,details);
  return head;
}

function indicatorCaption(ind, last = null) {
  const text=(CAPTIONS[ind.key] || "").replace(/small multiples, /g, "");
  return last && last !== ind.last_observation && last !== ind.periodo_referencia ? `${text} Datos hasta ${last}.`.trim() : text;
}

function splitMetricValue(node) {
  const text=node.textContent;
  const match=text.match(/^([+−-]?[\d,.]+)\s+((?:billones|millones|mdd|mdp|pesos|puntos|personas|USD|MXN)\b.*)$/i);
  if(match) node.replaceChildren(el("span",{class:"metric-value"},match[1])," ",el("span",{class:"metric-unit"},match[2]));
  if(text.length>24 && !match) node.classList.add("metric-long");
}

// Separar cifra y unidad sin convertir valores ni cambiar su precisión.
function refineMetricCards(mini, ind, k) {
  mini.querySelectorAll(".num").forEach(node=>{
    splitMetricValue(node);
  });
  if(ind.key === "INPP" && KPICFG.INPP.valCol === KPICFG.INPP.yoyCol) {
    const cards=[...mini.querySelectorAll(".mini")];
    const firstValue=cards[0]?.querySelector(".num")?.textContent;
    cards.slice(1).forEach(card=>{
      if(/^(var\.?|variación) anual$/i.test(card.querySelector(".lbl")?.textContent || "") && card.querySelector(".num")?.textContent===firstValue) card.remove();
    });
  }
  const sharedPeriod=ind.periodo_referencia || ind.last_observation;
  mini.querySelectorAll(".sub").forEach(node=>{
    if(node.textContent===`Periodo: ${sharedPeriod}` || node.textContent===`Periodo: ${k.ultimoP}` && k.ultimoP===sharedPeriod) node.remove();
  });
  const np=ind.proxima_publicacion || nextPublication(ind.key);
  if(np) mini.querySelectorAll(".mini").forEach(card=>{
    const label=card.querySelector(".lbl")?.textContent || "";
    if(label==="Próxima publicación" && card.querySelector(".num")?.textContent===np.fecha_publicacion) card.remove();
  });
}

// ---------------- Impresión: lenguaje visual tipo "Nota" (EMIM) ----------------
const arrow = (mag) => (mag == null ? "■" : (mag > 0.0001 ? "▲" : (mag < -0.0001 ? "▼" : "■")));
// Color por evaluación económica (no clasifica dirección como buena/mala salvo lectura clara).
function assessColor(assessment) {
  return assessment === "favorable" ? "#1e5b4f" : (assessment === "adverso" ? "#9b2247" : "#6b6f68");
}

// Encabezado institucional de la ficha para impresión (solo print).
function fichaPrintHead(ind, k) {
  const np = nextPublication(ind.key);
  const per = (k && k.ultimoP) || ind.periodo_referencia || ind.last_observation || "—";
  const head = el("div", { class: "ficha-print-head print-only" });
  head.append(el("div", { class: "fph-bar" },
    el("div", { class: "fph-title" }, ind.nombre),
    el("div", { class: "fph-sub" }, `${SIGLA[ind.key]} · ${per}`)));
  const src = ind.fuente?.nombre || "INEGI";
  const meta = [
    `Periodo de referencia: ${ind.periodo_referencia || per}`,
    `Fecha de publicación del dato: ${fechaPubDato(ind) || "no disponible en la base actual"}`,
    rezagoHabitual(ind) ? `Rezago habitual: ${rezagoHabitual(ind)}` : null,
    `Fuente oficial: ${src}`,
    ESTADOS[ind.estado] ? `Estado: ${ESTADOS[ind.estado].short}` : null,
    np ? `Próxima publicación: ${np.fecha_publicacion}` : null,
  ].filter(Boolean).join("  |  ");
  head.append(el("div", { class: "fph-meta" }, meta));
  return head;
}

// Bloques principales de variación con flechas (▲/▼), estilo Nota.
function fichaVarBlocks(ind, k, cfg, yoy) {
  const wrap = el("div", { class: "print-varblocks print-only" });
  const block = (lbl, text, mag, note, assessment) => {
    const color = assessment != null ? assessColor(assessment) : (mag == null ? "#6b6f68" : (mag >= 0 ? "#1e5b4f" : "#9b2247"));
    return el("div", { class: "pvb" },
      el("div", { class: "pvb-lbl" }, lbl),
      el("div", { class: "pvb-val", style: `color:${color}` }, `${arrow(mag)} ${text}`),
      el("div", { class: "pvb-note" }, note));
  };
  wrap.append(block(cfg.varLabel, k.varText, k.varMag, cfg.comp || "", k.assessment));
  const yoyLbl = ind.key === "SIC" ? (yoy && yoy.label) || "Dif. a 12 meses" : "Variación anual";
  const yoyNota = ind.key === "SIC" ? "Diferencia en puntos frente al mismo mes del año previo" : "Frente al mismo periodo del año previo";
  if (yoy) wrap.append(block(yoyLbl, yoy.text, yoy.mag, yoyNota, null));
  wrap.append(block("Cifra actual", k.ultimoFmt, null, `Periodo: ${k.ultimoP}`, null));
  return wrap;
}

// Tabla comparativa adaptada al indicador (solo print).
function fichaCompareTable(ind, k, cfg, yoy) {
  const box = el("div", { class: "ficha-block print-only print-compare" });
  box.append(el("h3", { class: "block-sub" }, "Cuadro comparativo"));
  const rows = [
    ["Cifra actual", k.ultimoP, k.ultimoFmt],
    [cfg.varLabel, cfg.comp || "—", k.varText],
  ];
  if (yoy) rows.push([ind.key === "SIC" ? "Dif. a 12 meses" : "Variación anual", "Año previo", yoy.text]);
  if (ind.key !== "TASA" && ind.key !== "RESERVAS") {
    rows.push(["Máximo de la serie", k.maxP, k.maxFmt]);
    rows.push(["Mínimo de la serie", k.minP, k.minFmt]);
  }
  const table = el("table");
  table.append(el("thead", {}, el("tr", {}, el("th", {}, "Concepto"), el("th", {}, "Referencia"), el("th", {}, "Valor"))));
  const tb = el("tbody");
  rows.forEach(([a, b, c]) => tb.append(el("tr", {}, el("td", {}, a), el("td", {}, b), el("td", {}, c))));
  table.append(tb);
  box.append(el("div", { class: "table-wrap", style: "max-height:none;border:none" }, table));
  return box;
}

const POB_WINDOWS = [
  { id: "1a", label: "1 año", quarters: 4 },
  { id: "2a", label: "2 años", quarters: 8 },
  { id: "3a", label: "3 años", quarters: 12 },
  { id: "5a", label: "5 años", quarters: 20 },
  { id: "max", label: "Máximo", quarters: null },
];

function buildWinToggle(ind, winId) {
  const wt = el("div", { class: "win-toggle no-print", role: "group", "aria-label": "Ventana temporal" });
  const wins = ind.windows || WINDOWS;
  wins.forEach((w) => {
    const pressed = w.id === winId;
    wt.append(el("button", {
      class: "win-btn", type: "button", "aria-pressed": String(pressed),
      "data-ind": ind.key, "data-win-id": w.id,
      onclick: () => {
        state.windows[ind.key] = w.id;
        mountChart(ind);
        document.querySelectorAll(`.win-btn[data-ind="${ind.key}"]`).forEach((b) => {
          b.setAttribute("aria-pressed", String(b.dataset.winId === w.id));
        });
      },
    }, w.label));
  });
  return wt;
}

function buildWinToggleForObservations(ind, winId, tipo) {
  const wt = el("div", { class: "win-toggle no-print", role: "group", "aria-label": `Ventana temporal ${tipo}` });
  const wins = tipo === "acumulado" ? (ind.windows || IED_WINDOWS) : (ind.windows_flujo || IED_WINDOWS_FLUJO);
  wins.forEach((w) => {
    const pressed = w.id === winId;
    wt.append(el("button", {
      class: "win-btn", type: "button", "aria-pressed": String(pressed),
      "data-ind": ind.key, "data-win-id": w.id, "data-tipo": tipo,
      onclick: () => {
        state.windows[`${ind.key}_${tipo}`] = w.id;
        mountIedCharts(ind);
        document.querySelectorAll(`.win-btn[data-ind="${ind.key}"][data-tipo="${tipo}"]`).forEach((b) => {
          b.setAttribute("aria-pressed", String(b.dataset.winId === w.id));
        });
      },
    }, w.label));
  });
  return wt;
}

function buildPobWinToggle(ind) {
  const wt = el("div", { class: "win-toggle no-print", role: "group", "aria-label": "Ventana de población ocupada" });
  const winId = state.windows[`${ind.key}_POB`] || "max";
  POB_WINDOWS.forEach((w) => {
    const pressed = w.id === winId;
    wt.append(el("button", {
      class: "win-btn", type: "button", "aria-pressed": String(pressed),
      "data-ind": `${ind.key}_POB`, "data-win-id": w.id,
      onclick: () => {
        state.windows[`${ind.key}_POB`] = w.id;
        mountChart(ind);
      },
    }, w.label));
  });
  return wt;
}

function applyPobWindow(ind, winId) {
  const win = POB_WINDOWS.find((w) => w.id === winId) || POB_WINDOWS[POB_WINDOWS.length - 1];
  const pobObs = (ind.observations || []).filter((o) => (o.values?.[5] ?? null) != null);
  if (!pobObs.length || win.id === "max" || win.quarters == null) return pobObs;
  return pobObs.slice(-win.quarters);
}

function renderIndicatorView(key) {
  const sec = document.getElementById(`view-${key}`);
  const ind = getInd(key);
  sec.innerHTML = "";
  sec.append(indicatorToolbar(key));
  const panel = el("div", { class: "panel ficha" });
  panel.append(fichaHeader(ind));
  if (ind.nota?.status && ind.nota.status !== "vigente") {
    panel.append(el("div", {class:"ficha-note-status",role:"status"},
      `Nota disponible: ${ind.nota.periodo || "periodo por confirmar"}. Consulta su periodo antes de utilizarla.`));
  }

  if (!hasData(ind)) {
    panel.append(fichaPrintHead(ind, null));
    panel.append(el("div", { class: "notice" }, `Este indicador todavía no tiene observaciones cargadas. Estado: ${ind.estado}. ${ind.requiere_token ? `Se activará al configurar ${ind.requiere_token}_TOKEN y confirmar la serie oficial.` : "Se incorporará con el pipeline."} No se muestran cifras estimadas ni inventadas.`));
    if (ind.key === "EMIM") panel.append(componentStatusTable("Componentes de la EMIM", ["Producción", "Personal ocupado", "Horas trabajadas", "Remuneraciones"]));
    if (ind.fuente?.link) panel.append(el("p", {}, el("a", { href: ind.fuente.link, target: "_blank", rel: "noopener" }, "Consultar fuente oficial ↗")));
    sec.append(panel);
    return;
  }

  const metrics = ind.metrics || {};
  const k = metrics.kpi || computeKPI(ind);
  const cfg = KPICFG[ind.key];
  const yoy = metrics.yoy || annualVar(ind, k);
  const resumen = metrics.resumen || [];
  const wins = ind.windows || WINDOWS;
  const winId = state.windows[ind.key] || wins[wins.length - 1]?.id || "max";

  // Encabezado institucional + bloques de variación (impresión, estilo Nota).
  panel.append(fichaPrintHead(ind, k));
  panel.append(fichaVarBlocks(ind, k, cfg, yoy));

  // KPIs
  let mini;
  if (ind.key === "PIB") {
    mini = el("div", { class: "mini-kpis" },
      el("div", { class: "mini dark" }, el("div", { class: "lbl" }, k.qoqLabel), el("div", { class: "num" }, k.qoqText), el("div", { class: "sub" }, `Periodo: ${k.ultimoP}`)),
      el("div", { class: "mini" }, el("div", { class: "lbl" }, k.yoyDesestLabel), el("div", { class: "num", style: `color:${k.yoyDesestRaw >= 0 ? COLORS.GREEN : COLORS.CRIMSON}` }, k.yoyDesestText), el("div", { class: "sub" }, "Frente al mismo trimestre del año previo")),
      el("div", { class: "mini" }, el("div", { class: "lbl" }, k.yoyOrigLabel), el("div", { class: "num", style: `color:${k.yoyOrigRaw >= 0 ? COLORS.GREEN : COLORS.CRIMSON}` }, k.yoyOrigText), el("div", { class: "sub" }, "Cifras originales")),
      k.ytdRaw != null ? el("div", { class: "mini" }, el("div", { class: "lbl" }, k.ytdLabel), el("div", { class: "num", style: `color:${k.ytdRaw >= 0 ? COLORS.GREEN : COLORS.CRIMSON}` }, k.ytdText), el("div", { class: "sub" }, "Variación acumulada")) : null,
      ind.proxima_publicacion && typeof ind.proxima_publicacion === "object"
        ? el("div", { class: "mini" }, el("div", { class: "lbl" }, "Próxima publicación"), el("div", { class: "num" }, ind.proxima_publicacion.fecha_publicacion), el("div", { class: "sub" }, ind.proxima_publicacion.periodo_referencia))
        : null,
    );
  } else if (ind.key === "PIBSEC" && k.cards) {
    mini = el("div", { class: "mini-kpis" },
      ...k.cards.map((c, i) => el("div", { class: `mini${i === 0 ? " dark" : ""}` },
        el("div", { class: "lbl" }, c.name),
        el("div", { class: "num" }, c.nivelText),
        el("div", { class: "sub" }, `${c.qoqText} trim. · ${c.yoyText} anual`)
      ))
    );
  } else if (ind.key === "EMIM" && k.cards) {
    mini = el("div", { class: "mini-kpis" },
      ...k.cards.map((c, i) => el("div", { class: `mini${i === 0 ? " dark" : ""}` },
        el("div", { class: "lbl" }, c.name),
        el("div", { class: "num" }, c.idxText),
        el("div", { class: "sub" }, [c.origMomText, c.desestMomText].filter(Boolean).join(" · ")),
        el("div", { class: "sub" }, [c.origYoyText, c.desestYoyText].filter(Boolean).join(" · "))
      ))
    );
  } else if (ind.key === "IMAI" && k.cards) {
    mini = el("div", { class: "mini-kpis" },
      el("div", { class: "mini dark" }, el("div", { class: "lbl" }, cfg.mainLabel || "Cifra actual"), el("div", { class: "num" }, k.ultimoFmt), el("div", { class: "sub" }, `Periodo: ${k.ultimoP}`)),
      el("div", { class: "mini" }, el("div", { class: "lbl" }, cfg.varLabel), el("div", { class: "num", style: `color:${k.varColor}` }, k.varText), el("div", { class: "sub" }, cfg.comp)),
      yoy ? el("div", { class: "mini" }, el("div", { class: "lbl" }, yoy.label || "Variación anual"), el("div", { class: "num", style: `color:${yoy.pos ? COLORS.GREEN : COLORS.CRIMSON}` }, yoy.text), el("div", { class: "sub" }, "Frente al periodo de referencia")) : null,
      k.acumText ? el("div", { class: "mini" }, el("div", { class: "lbl" }, k.acumLabel || "Acumulado"), el("div", { class: "num", style: `color:${k.acumPos ? COLORS.GREEN : COLORS.CRIMSON}` }, k.acumText), el("div", { class: "sub" }, "Acumulado ene-mes, cifras originales")) : null,
    );
  } else if (ind.key === "BCMM" && k.cards) {
    mini = el("div", { class: "mini-kpis" },
      ...k.cards.map((c, i) => el("div", { class: `mini${i === 0 ? " dark" : ""}` },
        el("div", { class: "lbl" }, c.name),
        el("div", { class: "num", style: i === 0 ? null : `color:${c.yoyColor}` }, c.text),
        c.name !== "Var. anual exportaciones" ? el("div", { class: "sub" }, c.yoyText) : null
      ))
    );
  } else if (ind.key === "DESOCUP" && k.cards) {
    mini = el("div", { class: "mini-kpis" },
      ...k.cards.map((c, i) => el("div", { class: `mini${i === 0 ? " dark" : ""}` },
        el("div", { class: "lbl" }, c.name),
        el("div", { class: "num" }, c.nivelText),
        el("div", { class: "sub" }, `${c.momText} mensual · ${c.yoyText} anual`),
        el("div", { class: "sub" }, `Periodo: ${c.ultimoP}`)
      )),
      k.poblacion ? el("div", { class: "mini" },
        el("div", { class: "lbl" }, "Población ocupada"),
        el("div", { class: "num" }, k.poblacion.textMillones),
        el("div", { class: "sub" }, `Periodo: ${k.poblacion.periodo} (trimestral)`),
      ) : null,
    );
  } else if (ind.key === "IED") {
    const acColor = (k.varMag ?? 0) >= 0 ? COLORS.GREEN : COLORS.CRIMSON;
    const flColor = (ind.metrics?.flujo_trimestral?.variacion_anual_pct ?? 0) >= 0 ? COLORS.GREEN : COLORS.CRIMSON;
    mini = el("div", { class: "mini-kpis" },
      el("div", { class: "mini dark" }, el("div", { class: "lbl" }, "IED acumulada"), el("div", { class: "num" }, k.ultimoFmt), el("div", { class: "sub" }, `Periodo: ${k.ultimoP}`)),
      el("div", { class: "mini" }, el("div", { class: "lbl" }, "Var. anual del acumulado"), el("div", { class: "num", style: `color:${acColor}` }, k.varText), el("div", { class: "sub" }, cfg.comp)),
      el("div", { class: "mini" }, el("div", { class: "lbl" }, `Flujo ${k.flujoP || "del 2T"}`), el("div", { class: "num" }, k.flujoText || "—"), el("div", { class: "sub" }, ind.metrics?.flujo_trimestral?.periodo || "—")),
      el("div", { class: "mini" }, el("div", { class: "lbl" }, "Var. anual del flujo"), el("div", { class: "num", style: `color:${flColor}` }, (k.yoy && k.yoy.text) ? k.yoy.text : ((ind.metrics?.flujo_trimestral?.variacion_anual_pct != null ? (ind.metrics.flujo_trimestral.variacion_anual_pct >= 0 ? "+" : "") + (ind.metrics.flujo_trimestral.variacion_anual_pct * 100).toLocaleString("es-MX", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + "%" : "—"))), el("div", { class: "sub" }, "Frente al mismo trimestre del año previo")),
    );
  } else if (ind.key === "TASA") {
    const decisionColor = k.decisionRaw === "sin cambio" ? COLORS.INK : (k.varMag >= 0 ? COLORS.GREEN : COLORS.CRIMSON);
    mini = el("div", { class: "mini-kpis" },
      el("div", { class: "mini dark" }, el("div", { class: "lbl" }, "Tasa objetivo vigente"), el("div", { class: "num" }, k.ultimoFmt), el("div", { class: "sub" }, `Vigente desde: ${k.vigenteDesdeText}`)),
      el("div", { class: "mini" }, el("div", { class: "lbl" }, "Última decisión"), el("div", { class: "num", style: `color:${decisionColor}` }, k.decisionDisplay), el("div", { class: "sub" }, k.decisionText)),
      el("div", { class: "mini" }, el("div", { class: "lbl" }, k.varLabel), el("div", { class: "num", style: `color:${k.varColor}` }, k.varText), el("div", { class: "sub" }, k.yoyText)),
      k.nextDecisionP ? el("div", { class: "mini" }, el("div", { class: "lbl" }, k.nextDecisionLabel), el("div", { class: "num" }, k.nextDecisionText), el("div", { class: "sub" }, "Próxima decisión de política monetaria")) : null,
    );
  } else if (ind.key === "RESERVAS") {
    const semColor = (k.varMag ?? 0) >= 0 ? COLORS.GREEN : COLORS.CRIMSON;
    const anualColor = (k.yoyMag ?? 0) >= 0 ? COLORS.GREEN : COLORS.CRIMSON;
    const ytdColor = (k.acumMag ?? 0) >= 0 ? COLORS.GREEN : COLORS.CRIMSON;
    const periodo = ind.periodo_referencia || k.ultimoP || "—";
    mini = el("div", { class: "mini-kpis" },
      el("div", { class: "mini dark" }, el("div", { class: "lbl" }, "Saldo de reservas"), el("div", { class: "num" }, k.ultimoFmt), el("div", { class: "sub" }, periodo)),
      el("div", { class: "mini" }, el("div", { class: "lbl" }, "Cambio semanal"), el("div", { class: "num", style: `color:${semColor}` }, k.varText || "—"), el("div", { class: "sub" }, "Respecto a la semana previa")),
      k.yoy ? el("div", { class: "mini" }, el("div", { class: "lbl" }, k.yoyLabel || "Variación anual"), el("div", { class: "num", style: `color:${anualColor}` }, k.yoy.text), el("div", { class: "sub" }, "Frente a la misma semana del año previo")) : null,
      k.acumText ? el("div", { class: "mini" }, el("div", { class: "lbl" }, k.acumLabel || "Cambio YTD"), el("div", { class: "num", style: `color:${ytdColor}` }, k.acumText), el("div", { class: "sub" }, "Respecto al cierre del año previo")) : null,
    );
  } else if (ind.key === "SIC") {
    const c = k.coincidente || {};
    const a = k.adelantado || {};
    const dmColor = (x) => (x ?? 0) >= 0 ? COLORS.GREEN : COLORS.CRIMSON;
    mini = el("div", { class: "mini-kpis" },
      el("div", { class: "mini dark" }, el("div", { class: "lbl" }, "Indicador Coincidente"), el("div", { class: "num" }, c.valorFmt || k.ultimoFmt), el("div", { class: "sub" }, `Periodo: ${c.periodo || k.ultimoP}`)),
      el("div", { class: "mini" }, el("div", { class: "lbl" }, "Dif. mensual coincidente"), el("div", { class: "num", style: `color:${dmColor(c.difMensual)}` }, c.difMensualText || "—"), el("div", { class: "sub" }, "Respecto al mes inmediato anterior")),
      el("div", { class: "mini dark" }, el("div", { class: "lbl" }, "Indicador Adelantado"), el("div", { class: "num" }, a.valorFmt || "—"), el("div", { class: "sub" }, `Periodo: ${a.periodo || "—"}`)),
      el("div", { class: "mini" }, el("div", { class: "lbl" }, "Dif. mensual adelantado"), el("div", { class: "num", style: `color:${dmColor(a.difMensual)}` }, a.difMensualText || "—"), el("div", { class: "sub" }, "Respecto al mes inmediato anterior")),
      c.difAnual != null ? el("div", { class: "mini" }, el("div", { class: "lbl" }, "Dif. a 12 meses coincidente"), el("div", { class: "num", style: `color:${dmColor(c.difAnual)}` }, c.difAnualText), el("div", { class: "sub" }, "Respecto al mismo mes del año previo")) : null,
    );
  } else if (ind.key === "IMOAM") {
    const v = ind.observations[k.lastI].values;
    mini = el("div", { class: "mini-kpis" },
      el("div", { class: "mini" }, el("div", { class: "lbl" }, "Índice estimado"), el("div", { class: "num" }, fmtVal(v[0], "idx")), el("div", { class: "sub" }, "Base 2018=100; cifras originales")),
      el("div", { class: "mini" }, el("div", { class: "lbl" }, "Variación anual estimada"), el("div", { class: "num" }, fmtVal(v[3], "pct-frac")), el("div", { class: "sub" }, "Respecto al mismo mes del año anterior")),
      el("div", { class: "mini" }, el("div", { class: "lbl" }, "IC 95% del índice"), el("div", { class: "num" }, `${fmtVal(v[1], "idx")} a ${fmtVal(v[2], "idx")}`), el("div", { class: "sub" }, "Estimación experimental")),
      el("div", { class: "mini" }, el("div", { class: "lbl" }, "IC 95% anual"), el("div", { class: "num" }, `${fmtVal(v[4], "pct-frac")} a ${fmtVal(v[5], "pct-frac")}`), el("div", { class: "sub" }, "Intervalo de confianza"))
    );
  } else if (ind.key === "IOAE") {
    const monthlyColor = k.varColor;
    const errorColor = (k.latestErrorPP == null || Math.abs(k.latestErrorPP) <= 0.5) ? COLORS.GREEN : (Math.abs(k.latestErrorPP) <= 1.5 ? COLORS.GOLD : COLORS.CRIMSON);
    mini = el("div", { class: "mini-kpis" },
      el("div", { class: "mini dark" }, el("div", { class: "lbl" }, "Nowcast anual del IGAE"), el("div", { class: "num" }, k.ultimoFmt), el("div", { class: "sub" }, `Periodo: ${k.ultimoP}`)),
      el("div", { class: "mini" }, el("div", { class: "lbl" }, cfg.varLabel), el("div", { class: "num", style: `color:${monthlyColor}` }, k.varText), el("div", { class: "sub" }, cfg.comp)),
      k.icWidthText ? el("div", { class: "mini" }, el("div", { class: "lbl" }, "Amplitud del IC 95%"), el("div", { class: "num" }, k.icWidthText), el("div", { class: "sub" }, `Límite inferior · superior`)) : null,
      k.latestObservedText ? el("div", { class: "mini" }, el("div", { class: "lbl" }, "IGAE observado"), el("div", { class: "num" }, k.latestObservedText), el("div", { class: "sub" }, `Publicado: ${k.latestObservedP}`)) : null,
      k.latestErrorText ? el("div", { class: "mini" }, el("div", { class: "lbl" }, "Error vs. observado"), el("div", { class: "num", style: `color:${errorColor}` }, k.latestErrorText), el("div", { class: "sub" }, `Diferencia en puntos porcentuales`)) : null,
      k.rmseText ? el("div", { class: "mini" }, el("div", { class: "lbl" }, "RMSE"), el("div", { class: "num" }, k.rmseText), el("div", { class: "sub" }, `${k.rmseN} meses con observado`)) : null,
    );
  } else {
    mini = el("div", { class: "mini-kpis" },
      el("div", { class: "mini dark" }, el("div", { class: "lbl" }, cfg.mainLabel || "Cifra actual"), el("div", { class: "num" }, k.ultimoFmt), el("div", { class: "sub" }, `Periodo: ${k.ultimoP}`)),
      el("div", { class: "mini" }, el("div", { class: "lbl" }, cfg.varLabel), el("div", { class: "num", style: `color:${k.varColor}` }, k.varText), el("div", { class: "sub" }, cfg.comp)),
      yoy ? el("div", { class: "mini" }, el("div", { class: "lbl" }, yoy.label || "Variación anual"), el("div", { class: "num", style: `color:${yoy.pos ? COLORS.GREEN : COLORS.CRIMSON}` }, yoy.text), el("div", { class: "sub" }, "Frente al periodo de referencia")) : null,
      k.acumText ? el("div", { class: "mini" }, el("div", { class: "lbl" }, k.acumLabel || "Acumulado"), el("div", { class: "num", style: `color:${k.acumPos ? COLORS.GREEN : COLORS.CRIMSON}` }, k.acumText), el("div", { class: "sub" }, "Acumulado ene-mes, cifras originales")) : null,
      el("div", { class: "mini" }, el("div", { class: "lbl" }, "Máximo de la serie"), el("div", { class: "num", style: `color:${COLORS.GREEN}` }, k.maxFmt), el("div", { class: "sub" }, `Periodo: ${k.maxP}`)),
      el("div", { class: "mini" }, el("div", { class: "lbl" }, "Mínimo de la serie"), el("div", { class: "num", style: `color:${COLORS.CRIMSON}` }, k.minFmt), el("div", { class: "sub" }, `Periodo: ${k.minP}`)),
    );
  }
  refineMetricCards(mini, ind, k);
  const extremes=[...mini.querySelectorAll(".mini")].filter(card=>/^(Máximo|Mínimo) de la serie$/.test(card.querySelector(".lbl")?.textContent || ""));
  const extremesDetails=extremes.length ? el("details",{class:"indicator-extra historical-metrics"},
    el("summary",{},"Extremos de la serie disponible"),el("div",{class:"mini-kpis"},...extremes)) : null;
  panel.append(mini);

  // window toggle + chart
  panel.append(el("div", { class: "chart-caption", id: `caption-${ind.key}` }, indicatorCaption(ind)));
  const chartMain = el("div", { class: "chart-main" });
  const emimMulti = ind.key === "EMIM" && (k.cards || (ind.columns && ind.columns.length > 15));
  const imfbcfMulti = ind.key === "IMFBCF" && (ind.columns && ind.columns.length > 15);
  if (ind.key === "PIBSEC" || ind.key === "IGAE" || ind.key === "IMAI" || ind.key === "BCMM" || emimMulti || imfbcfMulti) {
    chartMain.classList.add("pibsec-charts");
    const levels = el("div", { class: "pibsec-section" });
    levels.append(el("h3", { class: "block-sub" }, ind.key === "IGAE" ? "Niveles del IGAE y actividades económicas" : ind.key === "IMAI" ? "Niveles del IMAI y sectores industriales" : ind.key === "EMIM" ? "Niveles de la EMIM" : ind.key === "BCMM" ? "Niveles del comercio exterior" : ind.key === "IMFBCF" ? "Niveles del IMFBCF y componentes" : "Evolución del PIB y grandes actividades económicas"));
    levels.append(buildWinToggle(ind, winId));
    levels.append(el("div", { class: `chart-box ${ind.key === "IMAI" ? "imai-levels" : ind.key === "EMIM" ? "emim-levels" : ind.key === "BCMM" ? "bcmm-levels" : ind.key === "IMFBCF" ? "imfbcf-levels" : "pibsec-levels"}`, id: `chart-${ind.key}-levels`, role: "img", "aria-label": "Niveles del indicador y actividades económicas" }));
    chartMain.append(levels);
    const vars = el("div", { class: "pibsec-section" });
    vars.append(el("h3", { class: "block-sub" }, ind.key === "IGAE" ? "Variación anual del IGAE y actividades económicas" : ind.key === "IMAI" ? "Variaciones mensuales y anuales del IMAI y sectores industriales" : ind.key === "EMIM" ? "Variaciones anuales originales" : ind.key === "BCMM" ? "Variaciones anuales del comercio exterior" : ind.key === "IMFBCF" ? "Variaciones mensuales y anuales desestacionalizadas" : "Variación trimestral y anual del PIB y actividades económicas"));
    vars.append(buildWinToggle(ind, winId));
    vars.append(el("div", { class: `chart-box pibsec-variation ${ind.key === "EMIM" ? "emim-variation" : ""} ${ind.key === "BCMM" ? "bcmm-variation" : ""} ${ind.key === "IMFBCF" ? "imfbcf-variation" : ""}`, id: `chart-${ind.key}-variation`, role: "img", "aria-label": "Variaciones del indicador y actividades económicas" }));
    chartMain.append(vars);
    chartMain.append(el("div", { class: "range-wrap", id: `range-${ind.key}` }));
  } else if (ind.key === "DESOCUP") {
    chartMain.classList.add("pibsec-charts");
    const rates = el("div", { class: "pibsec-section" });
    rates.append(el("h3", { class: "block-sub" }, "Indicadores del mercado laboral"));
    rates.append(buildWinToggle(ind, winId));
    rates.append(el("div", { class: "chart-box desocup-rates", id: `chart-${ind.key}-rates`, role: "img", "aria-label": "Tasas laborales" }));
    chartMain.append(rates);
    const pob = el("div", { class: "pibsec-section" });
    pob.append(el("h3", { class: "block-sub" }, "Población ocupada"));
    pob.append(buildPobWinToggle(ind));
    pob.append(el("div", { class: "chart-box desocup-pob", id: `chart-${ind.key}-pob`, role: "img", "aria-label": "Población ocupada" }));
    chartMain.append(pob);
    chartMain.append(el("div", { class: "range-wrap", id: `range-${ind.key}` }));
  } else if (ind.key === "IED") {
    chartMain.classList.add("pibsec-charts");
    const ac = el("div", { class: "pibsec-section" });
    ac.append(el("h3", { class: "block-sub" }, `IED acumulada al mismo corte de cada año (${ind.metrics?.acumulado?.corte?.toLowerCase() || "ene-jun"})`));
    ac.append(buildWinToggleForObservations(ind, winId, "acumulado"));
    ac.append(el("div", { class: "chart-box ied-acumulado", id: `chart-${ind.key}-acumulado`, role: "img", "aria-label": "IED acumulada comparable por año" }));
    chartMain.append(ac);
    const fl = el("div", { class: "pibsec-section" });
    fl.append(el("h3", { class: "block-sub" }, "Flujo trimestral de IED"));
    fl.append(buildWinToggleForObservations(ind, state.windows[`${ind.key}_flujo`] || "max", "flujo"));
    fl.append(el("div", { class: "chart-box ied-flujo", id: `chart-${ind.key}-flujo`, role: "img", "aria-label": "Flujo trimestral de IED" }));
    chartMain.append(fl);
    chartMain.append(el("div", { class: "range-wrap", id: `range-${ind.key}` }));
  } else if (ind.key === "EMOE") {
    chartMain.classList.add("pibsec-charts");
    const main = el("div", { class: "pibsec-section" });
    main.append(el("h3", { class: "block-sub" }, "Indicador Global de Opinión Empresarial de Confianza (IGOEC)"));
    main.append(buildWinToggle(ind, winId));
    main.append(el("div", { class: "chart-box emoe-main", id: `chart-${ind.key}`, role: "img", "aria-label": "IGOEC y línea de referencia a 50 puntos" }));
    chartMain.append(main);
    const sect = el("div", { class: "pibsec-section" });
    sect.append(el("h3", { class: "block-sub" }, "Indicadores de Confianza Empresarial por sector"));
    sect.append(buildWinToggle(ind, winId));
    sect.append(el("div", { class: "chart-box emoe-sectors", id: `chart-${ind.key}-sectors`, role: "img", "aria-label": "ICE por sector: manufacturas, construcción, comercio y servicios" }));
    chartMain.append(sect);
    chartMain.append(el("div", { class: "range-wrap", id: `range-${ind.key}` }));
  } else if (ind.key === "SIC") {
    chartMain.classList.add("pibsec-charts");
    const main = el("div", { class: "pibsec-section" });
    main.append(el("h3", { class: "block-sub" }, "Indicadores Coincidente y Adelantado"));
    main.append(buildWinToggle(ind, winId));
    main.append(el("div", { class: "chart-box sic-main", id: `chart-${ind.key}`, role: "img", "aria-label": "Indicadores Coincidente y Adelantado; la línea en 100 puntos representa la tendencia de largo plazo" }));
    chartMain.append(main);
    const coinc = el("div", { class: "pibsec-section" });
    coinc.append(el("h3", { class: "block-sub" }, "Componentes cíclicos del Indicador Coincidente"));
    coinc.append(buildWinToggle(ind, winId));
    coinc.append(el("div", { class: "chart-box sic-comps", id: `chart-${ind.key}-coinc`, role: "img", "aria-label": "Componentes del Indicador Coincidente" }));
    chartMain.append(coinc);
    const adel = el("div", { class: "pibsec-section" });
    adel.append(el("h3", { class: "block-sub" }, "Componentes cíclicos del Indicador Adelantado"));
    adel.append(buildWinToggle(ind, winId));
    adel.append(el("div", { class: "chart-box sic-comps", id: `chart-${ind.key}-adel`, role: "img", "aria-label": "Componentes del Indicador Adelantado" }));
    chartMain.append(adel);
    chartMain.append(el("div", { class: "range-wrap", id: `range-${ind.key}` }));
  } else if (ind.key === "RESERVAS") {
    chartMain.classList.add("pibsec-charts");
    const level = el("div", { class: "pibsec-section" });
    level.append(el("h3", { class: "block-sub" }, "Evolución de la reserva internacional"));
    level.append(buildWinToggle(ind, winId));
    level.append(el("div", { class: "chart-box reservas-level", id: `chart-${ind.key}`, role: "img", "aria-label": "Reservas internacionales (mdd)" }));
    chartMain.append(level);
    const change = el("div", { class: "pibsec-section" });
    change.append(el("h3", { class: "block-sub" }, "Cambio semanal de la reserva internacional"));
    change.append(buildWinToggle(ind, winId));
    change.append(el("div", { class: "chart-box reservas-change", id: `chart-${ind.key}-change`, role: "img", "aria-label": "Cambio semanal de reservas internacionales (mdd)" }));
    chartMain.append(change);
    chartMain.append(el("div", { class: "range-wrap", id: `range-${ind.key}` }));
  } else {
    chartMain.append(buildWinToggle(ind, winId));
    chartMain.append(el("div", { class: "chart-box", id: `chart-${ind.key}`, role: "img", "aria-label": `Gráfica de ${ind.nombre}` }));
    chartMain.append(el("div", { class: "range-wrap", id: `range-${ind.key}` }));
  }
  panel.append(chartMain);

  // Cuadro comparativo (impresión, estilo Nota) — página 1.
  if (ind.key !== "PIBSEC") {
    panel.append(fichaCompareTable(ind, k, cfg, yoy));
  }

  // Una lectura única; omitir frases automáticas que no añaden información.
  const readings = [...new Set(resumen)].filter(text=>
    !/^La variación (se clasifica|no tiene)|^En la serie mostrada,/.test(text))
    .map(text=>text.replace(/contra [a-záéíóú]+ de \d{4} del año previo/g,"contra el mismo mes del año previo"));
  // PIBT ya presenta estas mismas cifras en las tarjetas y el desglose.
  const page2 = el("div", { class: "ficha-page2" });
  if(ind.key === "PIBSEC" && k.cards?.length > 1) {
    const sectors=k.cards.slice(1).filter(card=>card.qoqRaw != null && card.yoyRaw != null);
    if(sectors.length) {
      const quarterly=[...sectors].sort((a,b)=>b.qoqRaw-a.qoqRaw)[0];
      const annual=[...sectors].sort((a,b)=>b.yoyRaw-a.yoyRaw)[0];
      const box=el("div",{class:"ficha-block indicator-reading"},el("h3",{class:"block-sub"},"Lectura del indicador"));
      const reading=el("p",{class:"prose"},"Las ",el("strong",{},quarterly.full.toLowerCase()));
      if(quarterly === annual) reading.append(" registran la mayor variación trimestral y anual entre las grandes actividades.");
      else reading.append(" registran la mayor variación trimestral; las ",el("strong",{},annual.full.toLowerCase()),", la mayor variación anual.");
      box.append(reading);
      page2.append(box);
    }
  } else if(readings.length) {
    const syn=el("div",{class:"ficha-block indicator-reading"},el("h3",{class:"block-sub"},"Lectura del indicador"));
    const ul=el("ul",{class:"reading-bullets"});
    readings.forEach(text=>{
      const li=el("li");
      // Un solo énfasis numérico por conclusión; texto siempre escapado.
      const match=text.match(/[+−-]?\d[\d,.]*\s*(?:%|p\.p\.|puntos|mdd|millones|billones|pb)\b|[+−-]?\d[\d,.]*%/);
      if(match) li.append(text.slice(0,match.index),el("strong",{},match[0]),text.slice(match.index+match[0].length));
      else li.append(text);
      ul.append(li);
    });
    syn.append(ul); page2.append(syn);
  }

  // Desglose (breakdown) por componentes cuando aplica
  const bd = (ind.key === "PIBSEC") ? pibsecActivityBlock(ind, k) : breakdown(ind, k);
  if (bd) page2.append(bd);

  if(extremesDetails) page2.append(extremesDetails);

  // Tabla
  const tbl = el("div", { class: "ficha-block" });
  tbl.append(el("h3", { class: "block-sub" }, "Tabla de datos"));
  tbl.append(renderTable(ind, k));
  page2.append(tbl);

  // Bloques exclusivos de la ficha del PIB Oportuno.
  if (ind.key === "PIB") {
    const history=el("details",{class:"indicator-extra"},el("summary",{},"Cobertura histórica y nivel tradicional del PIB"),pibHistoryBlock(ind));
    const pibt = pibtBlock(ind);
    if(pibt) history.append(pibt);
    history.addEventListener("toggle",()=>{if(history.open) state.charts.pibt?.resize();});
    page2.append(history);
  }

  panel.append(page2);

  // Fuente y notas
  const src = el("div", { class: "notes" });
  if (ind.notas && ind.notas.length) src.append(el("div", {}, ind.notas.join("  ·  ")));
  src.append(el("div", {}, `Fuente: ${ind.fuente?.nombre || "—"} · Unidad: ${ind.unidad || "—"} · Ajuste: ${ind.ajuste_estacional || "—"}`, ind.fuente?.link ? el("span", {}, " · ", el("a", { href: ind.fuente.link, target: "_blank", rel: "noopener" }, "serie oficial ↗")) : null));
  panel.append(src);

  sec.append(panel);
}

function breakdown(ind, k) {
  const last = ind.observations[k.lastI];
  if (!last) return null;
  if (ind.key === "PIB" && ind.sectores) {
    const box = el("div", { class: "ficha-block pib-sectors" });
    box.append(el("h3", { class: "block-sub" }, "Variación trimestral por actividad económica"));
    box.append(el("p", { class: "prose", style: "font-size:12.5px;color:var(--muted);margin-top:-4px;margin-bottom:12px;text-align:left;" }, "Cambio real respecto al trimestre inmediato anterior, cifras desestacionalizadas."));
    const grid = el("div", { class: "breakdown" });
    const order = [["primarias", "Actividades primarias"], ["secundarias", "Actividades secundarias"], ["terciarias", "Actividades terciarias"]];
    order.forEach(([key, label]) => {
      const s = ind.sectores[key];
      if (!s || s.qoq == null) return;
      const color = s.qoq >= 0 ? COLORS.GREEN : COLORS.CRIMSON;
      const annual = s.yoy != null ? el("div", { class: "bd-annual", style: "font-size:11px;color:var(--muted);margin-top:3px;" }, `${signedPct(s.yoy)} anual`) : null;
      grid.append(el("div", { class: "bd-item" },
        el("div", { class: "bd-lbl" }, label),
        el("div", { class: "bd-val", style: `color:${color}` }, signedPct(s.qoq)),
        el("div", { class: "bd-sub", style: "font-size:11px;color:var(--muted);margin-top:4px;" }, "vs. trimestre anterior"),
        annual,
      ));
    });
    box.append(grid);
    return box;
  }
  if (ind.key === "IGAE" && last) {
    const box = el("div", { class: "ficha-block pibsec-activity" });
    box.append(el("h3", { class: "block-sub" }, "Desempeño por actividad"));
    const grid = el("div", { class: "breakdown" });
    const comps = [
      { key: "IGAE", idxCol: 0, yoyCol: 2, label: "IGAE" },
      { key: "Primarias", idxCol: 3, yoyCol: 4, label: "Actividades primarias" },
      { key: "Secundarias", idxCol: 5, yoyCol: 6, label: "Actividades secundarias" },
      { key: "Terciarias", idxCol: 7, yoyCol: 8, label: "Actividades terciarias" },
    ];
    comps.forEach((c) => {
      const idx = last.values[c.idxCol];
      const yoy = last.values[c.yoyCol];
      const yoyColor = (yoy != null ? (yoy >= 0 ? COLORS.GREEN : COLORS.CRIMSON) : COLORS.GRAY);
      grid.append(el("div", { class: "bd-item" },
        el("div", { class: "bd-lbl" }, c.label),
        el("div", { class: "bd-val" }, fmtVal(idx, "idx")),
        el("div", { class: "bd-sub" }, `Anual: `, el("span", { style: `color:${yoyColor}` }, signedPct(yoy)))
      ));
    });
    box.append(grid);
    return box;
  }
  if (ind.key === "IMAI" && last) {
    const box = el("div", { class: "ficha-block pibsec-activity" });
    box.append(el("h3", { class: "block-sub" }, "Desempeño por sector industrial"));
    const grid = el("div", { class: "breakdown" });
    const comps = [
      { idxCol: 0, momCol: 1, yoyCol: 2, label: "IMAI" },
      { idxCol: 6, momCol: 14, yoyCol: 10, label: "Minería" },
      { idxCol: 7, momCol: 15, yoyCol: 11, label: "Energía, agua y gas" },
      { idxCol: 8, momCol: 16, yoyCol: 12, label: "Construcción" },
      { idxCol: 9, momCol: 17, yoyCol: 13, label: "Industrias manufactureras" },
    ];
    comps.forEach((c) => {
      const idx = last.values[c.idxCol];
      const mom = last.values[c.momCol];
      const yoy = last.values[c.yoyCol];
      const momColor = (mom != null ? (mom >= 0 ? COLORS.GREEN : COLORS.CRIMSON) : COLORS.GRAY);
      const yoyColor = (yoy != null ? (yoy >= 0 ? COLORS.GREEN : COLORS.CRIMSON) : COLORS.GRAY);
      grid.append(el("div", { class: "bd-item" },
        el("div", { class: "bd-lbl" }, c.label),
        el("div", { class: "bd-val" }, fmtVal(idx, "idx")),
        el("div", { class: "bd-sub" }, `Mensual: `, el("span", { style: `color:${momColor}` }, signedPct(mom))),
        el("div", { class: "bd-sub" }, `Anual: `, el("span", { style: `color:${yoyColor}` }, signedPct(yoy)))
      ));
    });
    box.append(grid);
    return box;
  }
  if (ind.key === "CONSUMO" && last) {
    const box = el("div", { class: "ficha-block pibsec-activity" });
    box.append(el("h3", { class: "block-sub" }, "Desempeño por origen y durabilidad"));
    const grid = el("div", { class: "breakdown" });
    const comps = [
      { momCol: 5, yoyCol: 6, label: "Nacional" },
      { momCol: 7, yoyCol: 8, label: "Bienes nacionales" },
      { momCol: 9, yoyCol: 10, label: "Servicios nacionales" },
      { momCol: 11, yoyCol: 12, label: "Importado" },
      { momCol: 13, yoyCol: 14, label: "Bienes importados" },
      { yoyCol: 25, acumCol: 26, label: "Bienes duraderos nacionales" },
      { yoyCol: 27, acumCol: 28, label: "Bienes semi duraderos nacionales" },
      { yoyCol: 29, acumCol: 30, label: "Bienes no duraderos nacionales" },
      { yoyCol: 31, acumCol: 32, label: "Bienes duraderos importados" },
      { yoyCol: 33, acumCol: 34, label: "Bienes semi duraderos importados" },
      { yoyCol: 35, acumCol: 36, label: "Bienes no duraderos importados" },
    ];
    comps.forEach((c) => {
      const mom = c.momCol != null ? last.values[c.momCol] : null;
      const yoy = last.values[c.yoyCol];
      const acum = c.acumCol != null ? last.values[c.acumCol] : null;
      const momColor = (mom != null ? (mom >= 0 ? COLORS.GREEN : COLORS.CRIMSON) : COLORS.GRAY);
      const yoyColor = (yoy != null ? (yoy >= 0 ? COLORS.GREEN : COLORS.CRIMSON) : COLORS.GRAY);
      const acumColor = (acum != null ? (acum >= 0 ? COLORS.GREEN : COLORS.CRIMSON) : COLORS.GRAY);
      const subs = [];
      if (mom != null) subs.push(el("div", { class: "bd-sub" }, `Mensual desest.: `, el("span", { style: `color:${momColor}` }, signedPct(mom))));
      subs.push(el("div", { class: "bd-sub" }, `Anual: `, el("span", { style: `color:${yoyColor}` }, signedPct(yoy))));
      if (acum != null) subs.push(el("div", { class: "bd-sub" }, `Acumulado ene-mes: `, el("span", { style: `color:${acumColor}` }, signedPct(acum))));
      grid.append(el("div", { class: "bd-item" },
        el("div", { class: "bd-lbl" }, c.label),
        ...subs
      ));
    });
    box.append(grid);
    return box;
  }
  if (ind.key === "EMIM" && last && (k.cards || (ind.columns && ind.columns.length > 15))) {
    const box = el("div", { class: "ficha-block pibsec-activity" });
    box.append(el("h3", { class: "block-sub" }, "Desempeño por variable"));
    const grid = el("div", { class: "breakdown" });
    const comps = k.cards || [
      { name: "Producción", idxCol: 0, yoyCol: 2 },
      { name: "Personal ocupado", idxCol: 5, yoyCol: 7 },
      { name: "Horas trabajadas", idxCol: 10, yoyCol: 12 },
      { name: "Remuneraciones medias reales", idxCol: 15, yoyCol: 17 },
    ];
    comps.forEach((c) => {
      const idxRaw = c.idxRaw != null ? c.idxRaw : last.values[c.idxCol];
      const yoyRaw = c.origYoyRaw != null ? c.origYoyRaw : (c.desestYoyRaw != null ? c.desestYoyRaw : last.values[c.yoyCol]);
      const yoyColor = (yoyRaw != null ? (yoyRaw >= 0 ? COLORS.GREEN : COLORS.CRIMSON) : COLORS.GRAY);
      grid.append(el("div", { class: "bd-item" },
        el("div", { class: "bd-lbl" }, c.name),
        el("div", { class: "bd-val" }, fmtVal(idxRaw, "idx")),
        el("div", { class: "bd-sub" }, `Anual: `, el("span", { style: `color:${yoyColor}` }, signedPct(yoyRaw)))
      ));
    });
    box.append(grid);

    const subsectores = ind.subsectores || ind.sectores;
    if (subsectores && Object.keys(subsectores).length) {
      const entries = Object.entries(subsectores)
        .filter(([label]) => !label.toLowerCase().startsWith("emim") && !label.toLowerCase().includes("manufacturera"))
        .sort((a, b) => b[1] - a[1]);
      if (entries.length) {
        box.append(el("h3", { class: "block-sub", style: "margin-top:18px;" }, "Variación anual por subsector"));
        const top = entries.slice(0, 3);
        const bottom = entries.slice(-3);
        const col = (title, items, color) => el("div", { class: "pibsec-sector-col" },
          el("div", { class: "pibsec-sector-title", style: `color:${color}` }, title),
          ...items.map(([label, v]) => {
            const short = label.replace(/^\d+\s+/, "").split(",")[0].split(" y ")[0];
            return el("div", { class: "pibsec-sector-item" },
              el("span", { class: "pibsec-sector-name" }, short),
              el("span", { class: "pibsec-sector-pct", style: `color:${v >= 0 ? COLORS.GREEN : COLORS.CRIMSON}` }, signedPct(v))
            );
          })
        );
        const wrap = el("div", { class: "pibsec-sectors" });
        wrap.append(col("Al alza", top, COLORS.GREEN), col("A la baja", bottom, COLORS.CRIMSON));
        box.append(wrap);
      }
    }
    return box;
  }
  if (ind.key === "EMOE" && last) {
    const box = el("div", { class: "ficha-block pibsec-activity" });
    box.append(el("h3", { class: "block-sub" }, "Lectura respecto al umbral de 50 puntos"));
    const umbral = ind.umbral ?? 50;
    const nivel = last.values[0];
    const diff = nivel != null ? nivel - umbral : null;
    const sentido = diff == null ? "—" : (diff > 0 ? "optimista" : (diff < 0 ? "pesimista" : "neutro"));
    const color = diff == null ? COLORS.GRAY : (diff > 0 ? COLORS.GREEN : (diff < 0 ? COLORS.CRIMSON : COLORS.INK));
    const grid = el("div", { class: "breakdown" });
    grid.append(el("div", { class: "bd-item" },
      el("div", { class: "bd-lbl" }, "IGOEC"),
      el("div", { class: "bd-val" }, `${fmtVal(nivel, "idx")} puntos`),
      el("div", { class: "bd-sub" }, `Umbral: ${umbral} puntos · diferencia: `, el("span", { style: `color:${color}` }, diff != null ? (diff > 0 ? "+" : "") + diff.toLocaleString("es-MX", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " puntos" : "—"), ` · sesgo: ${sentido}`)
    ));
    const sectores = [
      { col: 3, label: "Manufacturas" },
      { col: 4, label: "Construcción" },
      { col: 5, label: "Comercio" },
      { col: 6, label: "Servicios privados no financieros" },
    ];
    const haySectores = sectores.some((s) => last.values[s.col] != null);
    if (haySectores) {
      box.append(el("p", { class: "prose", style: "font-size:12.5px;color:var(--muted);margin-top:-4px;margin-bottom:12px;text-align:left;" }, "Valores de los Indicadores de Confianza Empresarial (ICE) por sector. Un ICE superior a 50 puntos indica optimismo; inferior, pesimismo."));
      sectores.forEach((s) => {
        const v = last.values[s.col];
        if (v == null) return;
        const d = v - umbral;
        const c = d > 0 ? COLORS.GREEN : (d < 0 ? COLORS.CRIMSON : COLORS.INK);
        grid.append(el("div", { class: "bd-item" },
          el("div", { class: "bd-lbl" }, s.label),
          el("div", { class: "bd-val" }, `${fmtVal(v, "idx")} puntos`),
          el("div", { class: "bd-sub" }, `vs. umbral: `, el("span", { style: `color:${c}` }, (d > 0 ? "+" : "") + d.toLocaleString("es-MX", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " puntos"))
        ));
      });
    } else {
      box.append(el("p", { class: "prose", style: "font-size:12.5px;color:var(--muted);margin-top:-4px;margin-bottom:12px;text-align:left;" }, "Los sectores se obtienen de las series BIE del ICE (701401, 701570, 701407, 701826, 701975)."));
    }
    box.append(grid);
    return box;
  }
  const rowsFor = () => {
    if (ind.key === "PIBSEC") return [["Primarias", last.values[0], "num"], ["Secundarias", last.values[1], "num"], ["Terciarias", last.values[2], "num"]];
    if (ind.key === "IGAE") return null;
    if (ind.key === "IED") {
      const m = ind.metrics || {};
      const ac = ind.observations_acumulado ? ind.observations_acumulado[ind.observations_acumulado.length - 1] : null;
      const lastAc = ac ? ac.values : [null, null, null, null, null];
      const flujo = m.flujo_trimestral && m.flujo_trimestral.valor != null ? m.flujo_trimestral.valor : null;
      return [
        ["IED acumulada", lastAc[0], "usd"],
        ["Flujo del 2T", flujo, "usd"],
        ["Nuevas inversiones", lastAc[1], "usd"],
        ["Reinversión de utilidades", lastAc[2], "usd"],
        ["Cuentas entre compañías", lastAc[3], "usd"],
      ];
    }
    if (ind.key === "INPC") return [["General", last.values[2], "pct-raw"], ["Subyacente", last.values[5], "pct-raw"], ["No subyacente", last.values[11], "pct-raw"]];
    if (ind.key === "INPP") return [["INPP con petróleo", last.values[2], "pct-raw"], ["INPP sin petróleo", last.values[6], "pct-raw"], ["Bienes intermedios", last.values[8], "pct-raw"]];
    if (ind.key === "BALANZA") return [["Exportaciones", last.values[0], "usd"], ["Importaciones", last.values[1], "usd"], ["Saldo (X − M)", (last.values[0] != null && last.values[1] != null) ? last.values[0] - last.values[1] : null, "usd"]];
    return null;
  };
  const rows = rowsFor();
  if (!rows) return null;
  const box = el("div", { class: "ficha-block" });
  box.append(el("h3", { class: "block-sub" }, ind.key === "BALANZA" ? "Componentes del saldo" : ind.key === "INPC" ? "Desagregación de la inflación" : ind.key === "INPP" ? "Desagregación de precios productor" : "Desempeño por componentes"));
  const g = el("div", { class: "breakdown" });
  rows.forEach(([lbl, val, fmt]) => g.append(el("div", { class: "bd-item" }, el("div", { class: "bd-lbl" }, lbl), el("div", { class: "bd-val" }, fmtVal(val, fmt)))));
  box.append(g);
  return box;
}

// ---------------- Bloques exclusivos de la ficha del PIB ----------------
function pibsecActivityBlock(ind, k) {
  const box = el("div", { class: "ficha-block pibsec-activity" });
  const subsectores = ind.subsectores || {};
  const hasSubs = Object.keys(subsectores).some((s) => !s.toLowerCase().startsWith("pib") && !s.toLowerCase().includes("actividades"));
  box.append(el("h3", { class: "block-sub" }, hasSubs ? "Variación anual por subsector" : "Desempeño por actividad"));

  if (hasSubs) {
    const entries = Object.entries(subsectores)
      .filter(([label]) => !label.toLowerCase().startsWith("pib") && !label.toLowerCase().includes("actividades"))
      .sort((a, b) => b[1] - a[1]);
    const top = entries.slice(0, 3);
    const bottom = entries.slice(-3);
    const col = (title, items, color) => el("div", { class: "pibsec-sector-col" },
      el("div", { class: "pibsec-sector-title", style: `color:${color}` }, title),
      ...items.map(([label, v]) => {
        const short = label.replace(/^\d+\s+/, "").split(",")[0].split(" y ")[0];
        return el("div", { class: "pibsec-sector-item" },
          el("span", { class: "pibsec-sector-name" }, short),
          el("span", { class: "pibsec-sector-pct", style: `color:${v >= 0 ? COLORS.GREEN : COLORS.CRIMSON}` }, signedPct(v))
        );
      })
    );
    const wrap = el("div", { class: "pibsec-sectors" });
    wrap.append(col("Al alza", top, COLORS.GREEN), col("A la baja", bottom, COLORS.CRIMSON));
    box.append(wrap);
    return box;
  }

  if (!k.cards) return null;
  const grid = el("div", { class: "breakdown" });
  k.cards.forEach((c) => {
    const qoqColor = (c.qoqRaw != null ? (c.qoqRaw >= 0 ? COLORS.GREEN : COLORS.CRIMSON) : COLORS.GRAY);
    const yoyColor = (c.yoyRaw != null ? (c.yoyRaw >= 0 ? COLORS.GREEN : COLORS.CRIMSON) : COLORS.GRAY);
    grid.append(el("div", { class: "bd-item" },
      el("div", { class: "bd-lbl" }, c.full),
      el("div", { class: "bd-val" }, c.nivelText),
      el("div", { class: "bd-sub" }, `Trim. `, el("span", { style: `color:${qoqColor}` }, c.qoqText)),
      el("div", { class: "bd-sub" }, `Anual `, el("span", { style: `color:${yoyColor}` }, c.yoyText))
    ));
  });
  box.append(grid);
  return box;
}


function pibHistoryBlock(ind) {
  const start = (ind.observations[0] && ind.observations[0].period) || "—";
  const end = (ind.observations[ind.observations.length - 1] && ind.observations[ind.observations.length - 1].period) || "—";
  const total = ind.observations.length;
  const box = el("div", { class: "ficha-block" });
  box.append(el("h3", { class: "block-sub" }, "Historial del indicador"));
  const grid = el("div", { class: "pib-history" });
  grid.append(el("div", { class: "ph-item" },
    el("div", { class: "ph-lbl" }, "Periodo inicial"),
    el("div", { class: "ph-val" }, start)));
  grid.append(el("div", { class: "ph-item" },
    el("div", { class: "ph-lbl" }, "Periodo final"),
    el("div", { class: "ph-val" }, end)));
  grid.append(el("div", { class: "ph-item" },
    el("div", { class: "ph-lbl" }, "Observaciones"),
    el("div", { class: "ph-val" }, String(total))));
  box.append(grid);
  return box;
}

function pibtBlock(ind) {
  const pibt = ind.pibt;
  if (!pibt || !pibt.observations || !pibt.observations.length) return null;
  const obs = pibt.observations.filter((o) => o.values[0] != null);
  if (!obs.length) return null;
  const last = obs[obs.length - 1];
  const src = pibt.fuente || {};

  const box = el("div", { class: "ficha-block pibt-block" });
  box.append(el("h3", { class: "block-sub" }, "Nivel tradicional del PIB"));

  const head = el("div", { class: "pibt-head" });
  head.append(el("div", { class: "pibt-main" },
    el("div", { class: "pibt-lbl" }, "Último nivel disponible"),
    el("div", { class: "pibt-val" }, fmtVal(last.values[0], "bill")),
    el("div", { class: "pibt-sub" }, `Periodo: ${last.period}`)));

  const meta = el("div", { class: "pibt-meta" });
  [
    ["Fuente", src.nombre || "INEGI"],
    ["Serie", src.serie || "—"],
    ["Frecuencia", pibt.frecuencia || "Trimestral"],
    ["Unidad", pibt.unidad || "Millones de pesos (a precios de 2018)"],
  ].forEach(([k, v]) => {
    meta.append(el("div", { class: "pibt-meta-row" },
      el("span", { class: "k" }, k),
      el("span", { class: "v" }, v)));
  });
  head.append(meta);
  box.append(head);

  const chartWrap = el("div", { class: "chart-main pibt-chart" });
  chartWrap.append(el("div", {
    class: "chart-box",
    id: "chart-pibt",
    role: "img",
    "aria-label": "Nivel del PIB a precios constantes de 2018",
  }));
  box.append(chartWrap);
  return box;
}

function mountPibtChart(pibt) {
  const dom = document.getElementById("chart-pibt");
  if (!dom || typeof echarts === "undefined") return;
  let chart = state.charts.pibt;
  if (!chart) {
    chart = echarts.init(dom, null, { renderer: "canvas" });
    state.charts.pibt = chart;
  }
  const obs = (pibt.observations || []).filter((o) => o.values[0] != null);
  const periods = obs.map((o) => o.period);
  const values = obs.map((o) => o.values[0]);
  chart.setOption({
    animation: false,
    color: [COLORS.GREEN],
    grid: { left: 62, right: 18, top: 30, bottom: 44 },
    legend: { show: false },
    tooltip: {
      trigger: "axis",
      backgroundColor: "#fff",
      borderColor: "#ddd7c6",
      borderWidth: 1,
      textStyle: { color: COLORS.INK, fontFamily: FONT, fontSize: 12 },
      extraCssText: "box-shadow:0 5px 16px rgba(0,0,0,.13);border-radius:9px;",
      formatter: (params) => {
        if (!params || !params.length) return "";
        const p = params[0];
        return `<div style="font-family:'Noto Sans',sans-serif;font-weight:600;color:#002f2a;margin-bottom:5px">${p.axisValue}</div>`
          + `<div style="display:flex;align-items:center;gap:8px;margin:2px 0">${p.marker}<span style="flex:1;color:#5c5f5a;font-size:11px">Nivel del PIB</span>`
          + `<span style="font-family:'Noto Sans',sans-serif;font-weight:600">${fmtVal(p.value, "bill")}</span></div>`;
      },
    },
    toolbox: {
      right: 4, top: 2, itemSize: 14,
      feature: { saveAsImage: { title: "Guardar imagen", name: "PIBT", pixelRatio: 2, backgroundColor: "#fff" } },
      iconStyle: { borderColor: "#8a8d86" },
    },
    xAxis: {
      type: "category",
      data: periods,
      axisLabel: { color: "#8a8d86", fontFamily: FONT, fontSize: periods.length > 16 ? 9 : 10, rotate: periods.length > 16 ? 42 : 0, interval: periods.length > 24 ? "auto" : 0 },
      axisLine: { lineStyle: { color: "#c9c2b2" } },
      axisTick: { show: false },
    },
    yAxis: {
      type: "value",
      name: "Billones de pesos de 2018",
      nameLocation: "middle",
      nameGap: 42,
      nameTextStyle: { color: "#6c6f6a", fontFamily: FONT, fontSize: 11, fontWeight: 500 },
      axisLabel: { color: "#8a8d86", fontFamily: FONT, fontSize: 11, formatter: (v) => (v / 1e6).toLocaleString("es-MX", { notation: "compact", maximumFractionDigits: 1 }) },
      splitLine: { lineStyle: { color: "#ece7da" } },
      axisLine: { show: false },
      axisTick: { show: false },
      scale: false,
    },
    series: [{
      name: "Nivel del PIB",
      type: "line",
      data: values,
      smooth: false,
      symbol: "circle",
      symbolSize: 4,
      lineStyle: { color: COLORS.GREEN, width: 2.4 },
      itemStyle: { color: COLORS.GREEN },
      areaStyle: { color: "rgba(30,91,79,0.08)" },
    }],
  }, true);
}

function renderTable(ind, k) {
  const wrap = el("div", { class: "table-wrap" });
  const table = el("table");
  // TASA: tabla de decisiones de política monetaria.
  if (ind.key === "TASA") {
    const decisions = ind.policy_decisions || [];
    table.append(el("thead", {}, el("tr", {}, ...["Fecha anuncio", "Vigencia", "Decisión", "Cambio", "Tasa previa", "Nueva tasa", "Comunicado"].map((h) => el("th", {}, h)))));
    const tbody = el("tbody");
    [...decisions].reverse().forEach((d) => {
      const decisionText = d.decision === "sin cambio" ? "Sin cambio" : d.decision === "alza" ? "Alza" : "Recorte";
      const changeText = d.decision === "sin cambio" ? "0 pb" : fmtVal(d.change_bp, "bp");
      const link = d.comunicado_url ? el("a", { href: d.comunicado_url, target: "_blank", rel: "noopener" }, "Ver comunicado") : "—";
      tbody.append(el("tr", {},
        el("td", {}, perShort(d.announcement_date)),
        el("td", {}, perShort(d.effective_date)),
        el("td", {}, decisionText),
        el("td", {}, changeText),
        el("td", {}, d.previous_rate != null ? fmtVal(d.previous_rate, "pct-raw") : "—"),
        el("td", {}, fmtVal(d.new_rate, "pct-raw")),
        el("td", {}, link)
      ));
    });
    table.append(tbody);
    wrap.append(table);
    return historyControls(wrap,table,ind.key);
  }
  table.append(el("thead", {}, el("tr", {}, el("th", {}, "Periodo"), ...ind.columns.map((c) => el("th", {}, c.label)))));
  const series = k ? k.series : [];
  const idxs = series.map((v, i) => (v == null ? -1 : i)).filter((i) => i >= 0);
  let maxI = -1, minI = -1;
  if (ind.key !== "PIB" && idxs.length) {
    maxI = idxs[0]; minI = idxs[0];
    idxs.forEach((i) => { if (series[i] > series[maxI]) maxI = i; if (series[i] < series[minI]) minI = i; });
  }
  const tbody = el("tbody");
  const obsRows = [...ind.observations].reverse();
  obsRows.forEach((o, ri) => {
    const originalI = ind.observations.length - 1 - ri;
    const cls = originalI === maxI ? "max" : (originalI === minI ? "min" : "");
    tbody.append(el("tr", { class: cls }, el("td", {}, o.period), ...ind.columns.map((c) => el("td", {}, fmtVal(o.values[c.index], c.fmt)))));
  });
  table.append(tbody);
  wrap.append(table);
  return historyControls(wrap,table,ind.key);
}

function historyControls(wrap,table,key) {
  const rows=[...table.querySelectorAll("tbody tr")];
  const box=el("div",{class:"history-data"});
  const info=el("span",{class:"muted"});
  const toolbar=el("div",{class:"history-toolbar"},info);
  let expanded=!!state.openTables[key];
  wrap.id=`history-${key}`;
  const update=()=>{
    rows.forEach((row,i)=>{ row.hidden=!expanded && i>=12; });
    info.textContent=expanded || rows.length<=12 ? `${rows.length} observaciones · más recientes primero` : `12 de ${rows.length} observaciones · más recientes primero`;
    if(button) {button.textContent=expanded ? "Ver solo recientes" : "Ver serie completa";button.setAttribute("aria-expanded",String(expanded));}
  };
  const button=rows.length>12 ? el("button",{class:"btn btn-ghost",type:"button","aria-controls":wrap.id,onclick:()=>{expanded=!expanded;state.openTables[key]=expanded;update();}},"Ver serie completa") : null;
  if(button) toolbar.append(button);
  update();box.append(toolbar,wrap);return box;
}

// ---------------- Entorno financiero (complementarios) ----------------
function renderEntorno() {
  const sec = $("#view-entorno");
  sec.innerHTML = "";
  sec.append(el("div", { class: "section-title" }, "Entorno financiero"));

  const grid = el("div", { class: "matrix" });
  COMPLEMENTARIOS.map(getInd).filter(Boolean).forEach((ind) => grid.append(panoramaCard(ind)));
  sec.append(grid);
}

// ---------------- Calendar (logica en calendar.js) ----------------

// ---------------- Methodology ----------------
function renderMethodology() {
  const sec = $("#view-metodologia");
  sec.innerHTML = "";
  sec.append(el("div", { class: "section-title" }, "Fuentes y metodología"));
  sec.append(el("div", { class: "section-sub" }, "Cobertura de las series y estado de actualización por indicador."));
  const table = el("table");
  table.append(el("thead", {}, el("tr", {}, ...["Indicador", "Fuente", "Frecuencia", "Consulta de la fuente", "Última observación", "Estado"].map((h) => el("th", {}, h)))));
  const tb = el("tbody");
  ORDER.map(getInd).filter(Boolean).forEach((ind) => {
    tb.append(el("tr", {},
      el("td", {}, el("a",{href:`#${ind.key}`},ind.nombre)), el("td", {title:ind.fuente?.nombre || ""},sourceInstitution(ind.fuente?.nombre || "—")),
      el("td", {}, ind.frecuencia || "—"), el("td", {}, ind.fecha_consulta || ind.last_updated || "—"),
      el("td", {}, ind.last_observation || "—"), el("td", {}, estadoBadge(ind))));
  });
  table.append(tb);
  sec.append(el("div", { class: "panel", style: "padding:0;overflow:hidden" }, el("div", { class: "table-wrap", style: "max-height:none;border:none" }, table)));
  const topics=[
    ["Series, unidades y comparaciones",[
      "Series originales (sin ajuste estacional) salvo indicación en contrario. Las variaciones mensuales de series originales pueden incorporar efectos de calendario.",
      "Los periodos de referencia pertenecen a cada indicador. La fecha de actualización del dashboard no corresponde al periodo de todas las series.",
      "Los extremos del rango seleccionado no equivalen necesariamente a récords históricos."]],
    ["Interpretación de los movimientos",[
      "Una variación positiva no siempre es favorable. La clasificación utiliza el criterio económico de cada indicador; las variables sin interpretación inequívoca se mantienen neutrales.",
      "El saldo comercial es exportaciones menos importaciones; el cambio del saldo no es el nivel del saldo.",
      "La inflación se reporta como variación anual del INPC. Una reducción no se clasifica automáticamente como mejora sin considerar el objetivo del Banco de México.",
      "El INPP mide precios de producción y el INPC precios al consumidor; reflejan etapas distintas de la cadena de valor."]],
    ["Actualización y disponibilidad",[
      "Cuando la fuente no está disponible o la serie no está confirmada, se conserva el último dato validado y se señala su estado.",
      "Una fecha transcurrida del calendario no confirma por sí sola que el boletín o la nota estén disponibles."]]
  ];
  const methods=el("div",{class:"method-topics"});
  topics.forEach(([title,paragraphs])=>methods.append(el("details",{class:"method-topic"},el("summary",{},title),...paragraphs.map(text=>el("p",{},text)))));
  const technical=el("details",{class:"method-topic"},el("summary",{},"Detalle técnico de las series"));
  const seriesTable=el("table",{},el("thead",{},el("tr",{},el("th",{},"Indicador"),el("th",{},"Fuente"),el("th",{},"Serie"))));
  const seriesBody=el("tbody");
  ORDER.map(getInd).filter(Boolean).forEach(ind=>seriesBody.append(el("tr",{},el("td",{},SIGLA[ind.key] || ind.key),el("td",{},ind.fuente?.nombre || "—"),el("td",{},ind.fuente?.serie || (ind.serie_confirmada ? "—" : "Por confirmar")))));
  seriesTable.append(seriesBody);technical.append(el("div",{class:"table-wrap"},seriesTable));methods.append(technical);
  sec.append(methods);
}

// ---------------- Downloads ----------------
function renderDownloads() {
  const sec = $("#view-descargas");
  sec.innerHTML = "";
  sec.append(el("div", { class: "section-title" }, "Descargas"));
  sec.append(el("div", { class: "section-sub" }, "Última versión validada de los datos y la documentación."));
  sec.append(el("div",{class:"download-feature"},
    el("div",{},el("span",{class:"download-format"},"XLSX · Editable"),el("h3",{},"Base de indicadores"),el("p",{},"Series históricas, fórmulas y gráficas editables.")),
    el("a",{class:"btn btn-primary",href:"downloads/Indicadores_Macroeconomicos_Mexico_Actualizado.xlsx",download:"Indicadores_Macroeconomicos_Mexico_Actualizado.xlsx"},"↓ Descargar Excel")));
  const technical=el("details",{class:"technical-downloads"},el("summary",{},"Datos y documentación técnica"));
  const grid=el("div",{class:"dl-grid"});
  const items=[
    ["Datos JSON","Base normalizada del dashboard.","data/indicadores.json","Ver JSON"],
    ["Control de actualización","Estado y última observación por indicador.","data/manifest.json","Ver control"],
    ["Documentación de fuentes","Referencias oficiales y método de actualización.","DATA_SOURCES.md","Ver documento"]
  ];
  items.forEach(([title,description,href,cta])=>grid.append(el("div",{class:"dl-card"},el("h4",{},title),el("p",{},description),el("a",{class:"acceso-link",href,target:"_blank",rel:"noopener noreferrer"},cta+" ↗"))));
  const csv=el("details",{class:"csv-downloads"},el("summary",{},"CSV por indicador"));
  ORDER.map(getInd).filter(Boolean).forEach(ind=>csv.append(el("a",{href:`data/csv/${ind.key}.csv`,download:`${ind.key}.csv`},SIGLA[ind.key] || ind.key)));
  technical.append(grid,csv);sec.append(technical);
}

// ---------------- Rango visible ----------------
function buildRangeCard(ind, winId) {
  const obs = applyWindow(ind, winId);
  const st = rangeStats(ind, obs);
  const wrap = el("details", { class: "range-card" });
  wrap.append(el("summary",{},"Estadísticas del rango seleccionado"));
  const table = el("table", { class: "range-table" });
  const thead = el("thead", {}, el("tr", {},
    el("th", {}, "Periodo"),
    el("th", {}, "Último"),
    el("th", {}, "Máximo"),
    el("th", {}, "Mínimo")
  ));
  const tbody = el("tbody");
  if (st) {
    tbody.append(el("tr", {},
      el("td", { class: "range-period" }, st.lastP),
      el("td", { class: "range-last" }, st.lastV),
      el("td", { class: "range-max" }, `${st.maxV} (${st.maxP})`),
      el("td", { class: "range-min" }, `${st.minV} (${st.minP})`)
    ));
  } else {
    tbody.append(el("tr", {}, el("td", { colspan: 4, class: "muted" }, "Sin observaciones en el rango")));
  }
  table.append(thead, tbody);
  wrap.append(table);
  return wrap;
}

// ---------------- Charts lifecycle ----------------
function mountPibsecCharts(ind) {
  if (typeof echarts === "undefined" || !hasData(ind)) return;
  const winId = state.windows[ind.key] || state.data.meta?.default_window || "5a";
  const obs = applyWindow(ind, winId);
  const domLevels = document.getElementById(`chart-${ind.key}-levels`);
  const domVars = document.getElementById(`chart-${ind.key}-variation`);
  if (!domLevels || !domVars) return;
  let levelsChart = state.charts[`${ind.key}-levels`];
  if (!levelsChart) { levelsChart = echarts.init(domLevels, null, { renderer: "canvas" }); state.charts[`${ind.key}-levels`] = levelsChart; }
  let varChart = state.charts[`${ind.key}-variation`];
  if (!varChart) { varChart = echarts.init(domVars, null, { renderer: "canvas" }); state.charts[`${ind.key}-variation`] = varChart; }
  levelsChart.setOption(buildPibsecLevels(obs), true);
  varChart.setOption(buildPibsecVariations(obs), true);

  // Tarjeta de rango visible.
  const rangeCard = document.getElementById(`range-${ind.key}`);
  if (rangeCard) {
    rangeCard.innerHTML = "";
    rangeCard.append(buildRangeCard(ind, winId));
  }
  const cap = document.getElementById(`caption-${ind.key}`);
  if (cap) {
    const last = obs.length ? obs[obs.length - 1].period : (ind.last_observation || "—");
    cap.textContent = indicatorCaption(ind, last);
  }
}

function mountIgaeCharts(ind) {
  if (typeof echarts === "undefined" || !hasData(ind)) return;
  const winId = state.windows[ind.key] || state.data.meta?.default_window || "5a";
  const obs = applyWindow(ind, winId);
  const domLevels = document.getElementById(`chart-${ind.key}-levels`);
  const domVars = document.getElementById(`chart-${ind.key}-variation`);
  if (!domLevels || !domVars) return;
  let levelsChart = state.charts[`${ind.key}-levels`];
  if (!levelsChart) { levelsChart = echarts.init(domLevels, null, { renderer: "canvas" }); state.charts[`${ind.key}-levels`] = levelsChart; }
  let varChart = state.charts[`${ind.key}-variation`];
  if (!varChart) { varChart = echarts.init(domVars, null, { renderer: "canvas" }); state.charts[`${ind.key}-variation`] = varChart; }
  levelsChart.setOption(buildIgaeLevels(obs), true);
  varChart.setOption(buildIgaeVariations(obs), true);

  // Tarjeta de rango visible.
  const rangeCard = document.getElementById(`range-${ind.key}`);
  if (rangeCard) {
    rangeCard.innerHTML = "";
    rangeCard.append(buildRangeCard(ind, winId));
  }
  const cap = document.getElementById(`caption-${ind.key}`);
  if (cap) {
    const last = obs.length ? obs[obs.length - 1].period : (ind.last_observation || "—");
    cap.textContent = indicatorCaption(ind, last);
  }
}

function mountImaiCharts(ind) {
  if (typeof echarts === "undefined" || !hasData(ind)) return;
  const winId = state.windows[ind.key] || state.data.meta?.default_window || "5a";
  const obs = applyWindow(ind, winId);
  const domLevels = document.getElementById(`chart-${ind.key}-levels`);
  const domVars = document.getElementById(`chart-${ind.key}-variation`);
  if (!domLevels || !domVars) return;
  let levelsChart = state.charts[`${ind.key}-levels`];
  if (!levelsChart) { levelsChart = echarts.init(domLevels, null, { renderer: "canvas" }); state.charts[`${ind.key}-levels`] = levelsChart; }
  let varChart = state.charts[`${ind.key}-variation`];
  if (!varChart) { varChart = echarts.init(domVars, null, { renderer: "canvas" }); state.charts[`${ind.key}-variation`] = varChart; }
  levelsChart.setOption(buildImaiLevels(obs), true);
  varChart.setOption(buildImaiVariations(obs), true);

  // Tarjeta de rango visible.
  const rangeCard = document.getElementById(`range-${ind.key}`);
  if (rangeCard) {
    rangeCard.innerHTML = "";
    rangeCard.append(buildRangeCard(ind, winId));
  }
  const cap = document.getElementById(`caption-${ind.key}`);
  if (cap) {
    const last = obs.length ? obs[obs.length - 1].period : (ind.last_observation || "—");
    cap.textContent = indicatorCaption(ind, last);
  }
}

function mountEmimCharts(ind) {
  if (typeof echarts === "undefined" || !hasData(ind)) return;
  const winId = state.windows[ind.key] || state.data.meta?.default_window || "5a";
  const obs = applyWindow(ind, winId);
  const domLevels = document.getElementById(`chart-${ind.key}-levels`);
  const domVars = document.getElementById(`chart-${ind.key}-variation`);
  if (!domLevels || !domVars) return;
  let levelsChart = state.charts[`${ind.key}-levels`];
  if (!levelsChart) { levelsChart = echarts.init(domLevels, null, { renderer: "canvas" }); state.charts[`${ind.key}-levels`] = levelsChart; }
  let varChart = state.charts[`${ind.key}-variation`];
  if (!varChart) { varChart = echarts.init(domVars, null, { renderer: "canvas" }); state.charts[`${ind.key}-variation`] = varChart; }
  levelsChart.setOption(buildEmimLevels(obs), true);
  varChart.setOption(buildEmimVariations(obs), true);

  // Tarjeta de rango visible.
  const rangeCard = document.getElementById(`range-${ind.key}`);
  if (rangeCard) {
    rangeCard.innerHTML = "";
    rangeCard.append(buildRangeCard(ind, winId));
  }
  const cap = document.getElementById(`caption-${ind.key}`);
  if (cap) {
    const last = obs.length ? obs[obs.length - 1].period : (ind.last_observation || "—");
    cap.textContent = indicatorCaption(ind, last);
  }
}

function mountEmoeCharts(ind) {
  if (typeof echarts === "undefined" || !hasData(ind)) return;
  const winId = state.windows[ind.key] || state.data.meta?.default_window || "5a";
  const obs = applyWindow(ind, winId);
  const domMain = document.getElementById(`chart-${ind.key}`);
  const domSectors = document.getElementById(`chart-${ind.key}-sectors`);
  if (!domMain || !domSectors) return;
  let mainChart = state.charts[ind.key];
  if (!mainChart) { mainChart = echarts.init(domMain, null, { renderer: "canvas" }); state.charts[ind.key] = mainChart; }
  mainChart.setOption(buildOption(ind, winId), true);

  let sectorsChart = state.charts[`${ind.key}-sectors`];
  if (!sectorsChart) { sectorsChart = echarts.init(domSectors, null, { renderer: "canvas" }); state.charts[`${ind.key}-sectors`] = sectorsChart; }
  sectorsChart.setOption(buildEmoeSectors(obs), true);

  const rangeCard = document.getElementById(`range-${ind.key}`);
  if (rangeCard) {
    rangeCard.innerHTML = "";
    rangeCard.append(buildRangeCard(ind, winId));
  }
  const cap = document.getElementById(`caption-${ind.key}`);
  if (cap) {
    const last = obs.length ? obs[obs.length - 1].period : (ind.last_observation || "—");
    cap.textContent = indicatorCaption(ind, last);
  }
}

function mountSicCharts(ind) {
  if (typeof echarts === "undefined" || !hasData(ind)) return;
  const winId = state.windows[ind.key] || state.data.meta?.default_window || "5a";
  const obs = applyWindow(ind, winId);
  const domMain = document.getElementById(`chart-${ind.key}`);
  const domCoinc = document.getElementById(`chart-${ind.key}-coinc`);
  const domAdel = document.getElementById(`chart-${ind.key}-adel`);
  if (!domMain || !domCoinc || !domAdel) return;
  let mainChart = state.charts[ind.key];
  if (!mainChart) { mainChart = echarts.init(domMain, null, { renderer: "canvas" }); state.charts[ind.key] = mainChart; }
  mainChart.setOption(buildOption(ind, winId), true);

  let coincChart = state.charts[`${ind.key}-coinc`];
  if (!coincChart) { coincChart = echarts.init(domCoinc, null, { renderer: "canvas" }); state.charts[`${ind.key}-coinc`] = coincChart; }
  coincChart.setOption(buildSicComponents(obs, "coincidente"), true);

  let adelChart = state.charts[`${ind.key}-adel`];
  if (!adelChart) { adelChart = echarts.init(domAdel, null, { renderer: "canvas" }); state.charts[`${ind.key}-adel`] = adelChart; }
  adelChart.setOption(buildSicComponents(obs, "adelantado"), true);

  const rangeCard = document.getElementById(`range-${ind.key}`);
  if (rangeCard) {
    rangeCard.innerHTML = "";
    rangeCard.append(buildRangeCard(ind, winId));
  }
  const cap = document.getElementById(`caption-${ind.key}`);
  if (cap) {
    const last = obs.length ? obs[obs.length - 1].period : (ind.last_observation || "—");
    cap.textContent = indicatorCaption(ind, last);
  }
}

function mountReservasCharts(ind) {
  if (typeof echarts === "undefined" || !hasData(ind)) return;
  const winId = state.windows[ind.key] || state.data.meta?.default_window || "5a";
  const obs = applyWindow(ind, winId);
  const domLevel = document.getElementById(`chart-${ind.key}`);
  const domChange = document.getElementById(`chart-${ind.key}-change`);
  if (!domLevel || !domChange) return;
  let levelChart = state.charts[ind.key];
  if (!levelChart) { levelChart = echarts.init(domLevel, null, { renderer: "canvas" }); state.charts[ind.key] = levelChart; }
  levelChart.setOption(buildReservasLevel(obs), true);

  let changeChart = state.charts[`${ind.key}-change`];
  if (!changeChart) { changeChart = echarts.init(domChange, null, { renderer: "canvas" }); state.charts[`${ind.key}-change`] = changeChart; }
  changeChart.setOption(buildReservasChange(obs), true);

  const rangeCard = document.getElementById(`range-${ind.key}`);
  if (rangeCard) {
    rangeCard.innerHTML = "";
    rangeCard.append(buildRangeCard(ind, winId));
  }
  const cap = document.getElementById(`caption-${ind.key}`);
  if (cap) {
    const last = obs.length ? obs[obs.length - 1].period : (ind.last_observation || "—");
    cap.textContent = indicatorCaption(ind, last);
  }
}

function mountBcmmCharts(ind) {
  if (typeof echarts === "undefined" || !hasData(ind)) return;
  const winId = state.windows[ind.key] || state.data.meta?.default_window || "5a";
  const obs = applyWindow(ind, winId);
  const domLevels = document.getElementById(`chart-${ind.key}-levels`);
  const domVars = document.getElementById(`chart-${ind.key}-variation`);
  if (!domLevels || !domVars) return;
  let levelsChart = state.charts[`${ind.key}-levels`];
  if (!levelsChart) { levelsChart = echarts.init(domLevels, null, { renderer: "canvas" }); state.charts[`${ind.key}-levels`] = levelsChart; }
  let varChart = state.charts[`${ind.key}-variation`];
  if (!varChart) { varChart = echarts.init(domVars, null, { renderer: "canvas" }); state.charts[`${ind.key}-variation`] = varChart; }
  levelsChart.setOption(buildBcmmLevels(obs), true);
  varChart.setOption(buildBcmmVariations(obs), true);

  const rangeCard = document.getElementById(`range-${ind.key}`);
  if (rangeCard) {
    rangeCard.innerHTML = "";
    rangeCard.append(buildRangeCard(ind, winId));
  }
  const cap = document.getElementById(`caption-${ind.key}`);
  if (cap) {
    const last = obs.length ? obs[obs.length - 1].period : (ind.last_observation || "—");
    cap.textContent = indicatorCaption(ind, last);
  }
}

function mountDesocupCharts(ind) {
  if (typeof echarts === "undefined" || !hasData(ind)) return;

  const ratesWinId = state.windows[ind.key] || state.data.meta?.default_window || "5a";
  const ratesObs = applyWindow(ind, ratesWinId);

  const domRates = document.getElementById(`chart-${ind.key}-rates`);
  const domPob = document.getElementById(`chart-${ind.key}-pob`);
  if (!domRates || !domPob) return;

  let ratesChart = state.charts[`${ind.key}-rates`];
  if (!ratesChart) { ratesChart = echarts.init(domRates, null, { renderer: "canvas" }); state.charts[`${ind.key}-rates`] = ratesChart; }
  ratesChart.setOption(buildDesocupRates(ind, ratesObs), true);

  let pobChart = state.charts[`${ind.key}-pob`];
  if (!pobChart) { pobChart = echarts.init(domPob, null, { renderer: "canvas" }); state.charts[`${ind.key}-pob`] = pobChart; }
  const pobWinId = state.windows[`${ind.key}_POB`] || "max";
  const pobObs = applyPobWindow(ind, pobWinId);
  pobChart.setOption(buildDesocupPoblacion(ind, pobObs), true);

  const rangeCard = document.getElementById(`range-${ind.key}`);
  if (rangeCard) {
    rangeCard.innerHTML = "";
    rangeCard.append(buildRangeCard(ind, ratesWinId));
  }
  const cap = document.getElementById(`caption-${ind.key}`);
  if (cap) {
    const last = ratesObs.length ? ratesObs[ratesObs.length - 1].period : (ind.last_observation || "—");
    cap.textContent = indicatorCaption(ind, last);
  }
}

function mountImfbcfCharts(ind) {
  if (typeof echarts === "undefined" || !hasData(ind)) return;
  const winId = state.windows[ind.key] || state.data.meta?.default_window || "5a";
  const obs = applyWindow(ind, winId);
  const domLevels = document.getElementById(`chart-${ind.key}-levels`);
  const domVars = document.getElementById(`chart-${ind.key}-variation`);
  if (!domLevels || !domVars) return;
  let levelsChart = state.charts[`${ind.key}-levels`];
  if (!levelsChart) { levelsChart = echarts.init(domLevels, null, { renderer: "canvas" }); state.charts[`${ind.key}-levels`] = levelsChart; }
  let varChart = state.charts[`${ind.key}-variation`];
  if (!varChart) { varChart = echarts.init(domVars, null, { renderer: "canvas" }); state.charts[`${ind.key}-variation`] = varChart; }
  levelsChart.setOption(buildImfbcfLevels(obs), true);
  varChart.setOption(buildImfbcfVariations(obs), true);
  const rangeCard = document.getElementById(`range-${ind.key}`);
  if (rangeCard) {
    rangeCard.innerHTML = "";
    rangeCard.append(buildRangeCard(ind, winId));
  }
  const cap = document.getElementById(`caption-${ind.key}`);
  if (cap) {
    const last = obs.length ? obs[obs.length - 1].period : (ind.last_observation || "—");
    cap.textContent = indicatorCaption(ind, last);
  }
}

function applyWindowForList(obs, winId, wins) {
  if (!obs || !obs.length) return [];
  if (winId === "max" || !wins) return obs.slice();
  const w = wins.find((x) => x.id === winId);
  if (w && w.count != null && w.count < obs.length) return obs.slice(-w.count);
  if (w && w.count != null && w.count >= obs.length) return obs.slice();
  return obs.slice();
}

function mountIedCharts(ind) {
  if (typeof echarts === "undefined" || !hasData(ind)) return;

  const acWinId = state.windows[`${ind.key}_acumulado`] || state.windows[ind.key] || "5a";
  const flWinId = state.windows[`${ind.key}_flujo`] || "5a";

  const acObs = applyWindowForList(ind.observations_acumulado || [], acWinId, IED_WINDOWS);
  const flObs = applyWindowForList(ind.observations || [], flWinId, IED_WINDOWS_FLUJO);

  // Gráfica 1: acumulado comparable (barras)
  const domAc = document.getElementById(`chart-${ind.key}-acumulado`);
  if (domAc) {
    let chartAc = state.charts[`${ind.key}-acumulado`];
    if (!chartAc) { chartAc = echarts.init(domAc, null, { renderer: "canvas" }); state.charts[`${ind.key}-acumulado`] = chartAc; }
    const corte = ind.metrics?.acumulado?.corte || "Ene-Jun";
    const optionAc = {
      title: { text: `Acumulado ${corte.toLowerCase()}`, left: "center", textStyle: { fontSize: 12, color: "#6c6f6a" } },
      tooltip: { trigger: "axis", formatter: (params) => {
        const p = params[0];
        const o = acObs[p.dataIndex];
        const vals = o ? o.values : [];
        const varTxt = vals[4] != null ? `<br/>Var. anual: ${(vals[4] >= 0 ? "+" : "") + (vals[4] * 100).toLocaleString("es-MX", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%` : "";
        return `${o?.period || p.name}<br/>${p.seriesName}: ${fmtVal(p.value, "usd")} mdd${varTxt}`;
      }},
      grid: { left: 52, right: 24, top: 48, bottom: 28 },
      xAxis: { type: "category", data: acObs.map((o) => o.period), axisLabel: { color: "#6c6f6a" } },
      yAxis: { type: "value", name: "Millones de dólares", nameLocation: "middle", nameGap: 40, axisLabel: { formatter: (v) => fmtVal(v, "compact") }, splitLine: { lineStyle: { color: "#ece7da" } } },
      series: [{ name: "IED acumulada", type: "bar", data: acObs.map((o) => o.values[0]), itemStyle: { color: COLORS.GREEN }, label: { show: false } }],
    };
    chartAc.setOption(optionAc, true);
  }

  // Gráfica 2: flujo trimestral
  const domFl = document.getElementById(`chart-${ind.key}-flujo`);
  if (domFl) {
    let chartFl = state.charts[`${ind.key}-flujo`];
    if (!chartFl) { chartFl = echarts.init(domFl, null, { renderer: "canvas" }); state.charts[`${ind.key}-flujo`] = chartFl; }
    const optionFl = {
      title: { text: "Flujo trimestral", left: "center", textStyle: { fontSize: 12, color: "#6c6f6a" } },
      tooltip: { trigger: "axis", formatter: (params) => {
        const p = params[0];
        const o = flObs[p.dataIndex];
        const vals = o ? o.values : [];
        const varTxt = vals[4] != null ? `<br/>Var. anual: ${(vals[4] >= 0 ? "+" : "") + (vals[4] * 100).toLocaleString("es-MX", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%` : "";
        return `${o?.period || p.name}<br/>${p.seriesName}: ${fmtVal(p.value, "usd")} mdd${varTxt}`;
      }},
      grid: { left: 52, right: 24, top: 48, bottom: 28 },
      xAxis: { type: "category", data: flObs.map((o) => o.period), axisLabel: { color: "#6c6f6a" } },
      yAxis: { type: "value", name: "Millones de dólares", nameLocation: "middle", nameGap: 40, axisLabel: { formatter: (v) => fmtVal(v, "compact") }, splitLine: { lineStyle: { color: "#ece7da" } } },
      series: [{ name: "Flujo trimestral", type: "bar", data: flObs.map((o) => o.values[0]), itemStyle: { color: COLORS.GOLD }, label: { show: false } }],
    };
    chartFl.setOption(optionFl, true);
  }

  // Caption
  const cap = document.getElementById(`caption-${ind.key}`);
  if (cap) {
    const lastAc = acObs.length ? acObs[acObs.length - 1].period : (ind.last_observation || "—");
    cap.textContent = `${CAPTIONS[ind.key] || ""} Acumulado comparable hasta ${lastAc}; flujo hasta ${flObs.length ? flObs[flObs.length - 1].period : ind.last_observation || "—"}.`.trim();
  }
}

function mountChart(ind) {
  if (ind.key === "IED") { mountIedCharts(ind); return; }
  if (ind.key === "PIBSEC") { mountPibsecCharts(ind); return; }
  if (ind.key === "IGAE") { mountIgaeCharts(ind); return; }
  if (ind.key === "IMAI") { mountImaiCharts(ind); return; }
  if (ind.key === "DESOCUP") { mountDesocupCharts(ind); return; }
  if (ind.key === "SIC") { mountSicCharts(ind); return; }
  if (ind.key === "EMOE") { mountEmoeCharts(ind); return; }
  if (ind.key === "RESERVAS") { mountReservasCharts(ind); return; }
  if (ind.key === "BCMM" && (ind.metrics?.kpi?.cards || (ind.columns && ind.columns.length > 25))) { mountBcmmCharts(ind); return; }
  if (ind.key === "EMIM" && (ind.metrics?.kpi?.cards || (ind.columns && ind.columns.length > 15))) { mountEmimCharts(ind); return; }
  if (ind.key === "IMFBCF" && (ind.columns && ind.columns.length > 15)) { mountImfbcfCharts(ind); return; }
  const dom = document.getElementById(`chart-${ind.key}`);
  if (!dom || typeof echarts === "undefined" || !hasData(ind)) return;
  // Usa granularidad original cuando la ficha del indicador es la vista activa.
  ind._useOriginal = (state.active === ind.key) && !!(ind.observations_original && ind.observations_original.length);
  let chart = state.charts[ind.key];
  if (!chart) { chart = echarts.init(dom, null, { renderer: "canvas" }); state.charts[ind.key] = chart; }
  const winId = state.windows[ind.key] || state.data.meta?.default_window || "5a";
  chart.setOption(buildOption(ind, winId), true);

  // Gráfica independiente del nivel tradicional del PIB (PIBT).
  if (ind.key === "PIB" && ind.pibt) mountPibtChart(ind.pibt);

  // Actualiza tarjeta de rango visible y leyenda del periodo.
  const rangeCard = document.getElementById(`range-${ind.key}`);
  if (rangeCard) {
    rangeCard.innerHTML = "";
    rangeCard.append(buildRangeCard(ind, winId));
  }
  const cap = document.getElementById(`caption-${ind.key}`);
  if (cap) {
    const obs = applyWindow(ind, winId);
    const last = obs.length ? obs[obs.length - 1].period : (ind.last_observation || "—");
    cap.textContent = indicatorCaption(ind, last);
  }
}
function mountAllCharts() { ORDER.map(getInd).filter(Boolean).forEach((ind) => { if (KPICFG[ind.key] && hasData(ind)) mountChart(ind); }); }
function resizeVisibleCharts() { Object.entries(state.charts).forEach(([key, c]) => { const dom = document.getElementById(`chart-${key}`); if (dom && dom.offsetParent !== null) c.resize(); }); }

// ---------------- Body ----------------
function buildViewShells() {
  const host = $("#sections");
  host.innerHTML = "";
  VIEWS.forEach((v) => host.append(el("section", { class: `view${v.id === state.active ? " active" : ""}`, id: `view-${v.id}`, role: "tabpanel", "aria-labelledby": `tab-${PRINCIPAL.includes(v.id) ? "panorama" : COMPLEMENTARIOS.includes(v.id) ? "entorno" : v.id}` })));
}

function renderAll() {
  renderPanorama();
  VIEWS.filter((v) => v.type === "indicator").forEach((v) => renderIndicatorView(v.key));
  renderEntorno();
  renderCalendar();
  renderMethodology();
  renderDownloads();
  mountAllCharts();
  resizeVisibleCharts();
}

function downloadExcel() { window.location.href = "downloads/Indicadores_Macroeconomicos_Mexico_Actualizado.xlsx"; }

// Pie de página institucional dinámico para impresión de fichas.
function updatePrintFooter() {
  const foot = document.querySelector(".print-footer");
  if (!foot) return;
  const ind = getInd(state.active);
  if (ind && ORDER.includes(state.active)) {
    const np = nextPublication(state.active);
    const sg = SIGLA[state.active];
    const nombreSigla = ind.nombre.includes(`(${sg})`) ? ind.nombre : `${ind.nombre} (${sg})`;
    const parts = [
      nombreSigla,
      `Fuente: ${ind.fuente?.nombre || "INEGI"}`,
      `Periodo de referencia: ${ind.periodo_referencia || ind.last_observation || "—"}`,
      np ? `Próxima publicación: ${np.fecha_publicacion}` : null,
      "Documento de trabajo para consulta y seguimiento estadístico.",
    ].filter(Boolean);
    foot.textContent = parts.join("  ·  ");
  } else {
    foot.textContent = "Documento de trabajo para consulta y seguimiento estadístico.";
  }
}

async function init() {
  try {
    state.data = await loadJSON("data/indicadores.json");
    state.manifest = await loadJSON("data/manifest.json", true);
    state.noticias = await loadJSON("data/noticias.json", true);
    state.calendario = await loadJSON("data/calendario.json", true) || await loadJSON("data/calendario_publicaciones.json", true);
  } catch (e) {
    $("#status").textContent = "No se pudieron cargar los datos (data/indicadores.json).";
    return;
  }
  $("#status").style.display = "none";
  renderHeader();
  renderNav();
  buildViewShells();
  renderAll();
  const initial = (window.location.hash || "").replace(/^#/, "");
  setView(validView(initial) ? initial : state.active);
  window.addEventListener("hashchange", () => { const h = (window.location.hash || "").replace(/^#/, ""); if (validView(h) && h !== state.active) setView(h); });
  window.addEventListener("beforeprint", updatePrintFooter);
  window.addEventListener("resize", () => resizeVisibleCharts());
  $("#btn-excel").addEventListener("click", downloadExcel);
}

document.addEventListener("DOMContentLoaded", init);
