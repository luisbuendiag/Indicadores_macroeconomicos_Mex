// N-040 · Panorama Estatal: mapa de los 32 estados, tabla ordenable y ficha por estado.
// Lee data/estados.json (contrato de N-039) y assets/geo/mexico_estados.json.
// Módulo autónomo: no depende de app.js; recibe la raíz donde se dibuja.

const NS = "http://www.w3.org/2000/svg";
const PAL = {
  ink: "#161A1D", muted: "#545454", line: "#DCE4E0", cafe: "#10312B", none: "#F2F2F0",
  // Divergente (crecimiento): vino ← gris → verde. Punto medio neutro.
  div: ["#9B2247", "#C17A80", "#E8C9C8", "#E9E5E0", "#C9DDCF", "#7FA894", "#2F6B4F"],
  divCuts: [-4, -2, -0.5, 0.5, 2, 4],
  // Secuencial (montos): un solo tono café, claro → oscuro.
  seq: ["#E8F0EC", "#BFD3CA", "#7FA394", "#3F7A68", "#10312B"],
};

const h = (tag, attrs = {}, ...kids) => {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === "class") n.className = v;
    else if (k.startsWith("on") && typeof v === "function") n.addEventListener(k.slice(2), v);
    else n.setAttribute(k, v === true ? "" : v);
  }
  for (const c of kids.flat()) if (c != null) n.append(c.nodeType ? c : document.createTextNode(c));
  return n;
};
const s = (tag, attrs = {}) => { const n = document.createElementNS(NS, tag); for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v); return n; };

const nf = (d) => new Intl.NumberFormat("es-MX", { minimumFractionDigits: d, maximumFractionDigits: d });
// Signo tipográfico y flecha: el color no basta para distinguir alzas y bajas (daltonismo, impresión).
const conSigno = (v, d = 1) => {
  const r = Math.round(Math.abs(v) * 10 ** d) === 0 ? 0 : v;
  const t = nf(d).format(Math.abs(r));
  return r > 0 ? `▲ +${t}` : r < 0 ? `▼ −${t}` : t;
};
// El PIB estatal llega en millones de pesos; se lee mejor en miles de millones.
const milesMdp = (v) => nf(0).format(Math.round(v / 1000));
const fmt = {
  pct: (v) => v == null ? "—" : `${conSigno(v)} %`,
  pctPlain: (v) => v == null ? "—" : `${nf(1).format(v)} %`,
  mdd: (v) => v == null ? "—" : `${nf(1).format(v)} mdd`,
  mdp: (v) => v == null ? "—" : `${milesMdp(v)} mil mdp`,
  num: (v) => v == null ? "—" : nf(0).format(v),
};
const fmtVal = (ind, v) => (ind.clave === "ENOE" ? fmt.pctPlain : fmt[ind.formato] || fmt.num)(v);
const fmtCelda = (ind, v) => v == null ? "—" : ind.formato === "mdp" ? milesMdp(v)
  : ind.formato === "mdd" ? nf(1).format(v) : fmtVal(ind, v);
const labelValue = (ind) => ({pct: ind.clave === "ENOE" ? "Tasa %" : "Var. %", mdp: "Miles de mdp",
  mdd: "mdd", num: "Puestos"})[ind.formato];
const months = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];
function displayPeriod(ind) {
  const period = ind.periodo || "";
  const match = ind.clave === "IMSS" && /^(\d{4})-(0[1-9]|1[0-2])$/.exec(period);
  return match ? `${months[Number(match[2]) - 1]} ${match[1]}` : period;
}
const ord = (n) => n == null ? "—" : `${n}°`;

function colorFor(ind, v, cuts) {
  if (v == null) return PAL.none;
  if (ind.escala === "divergente") {
    const i = PAL.divCuts.findIndex((c) => v < c);
    return PAL.div[i === -1 ? PAL.div.length - 1 : i];
  }
  const i = cuts.findIndex((c) => v < c);
  return PAL.seq[i === -1 ? PAL.seq.length - 1 : i];
}
// Cortes secuenciales por quintiles, para que los estados chicos no queden todos en blanco.
function quintiles(vals) {
  const v = vals.filter((x) => x != null).sort((a, b) => a - b);
  if (!v.length) return [];
  return [0.2, 0.4, 0.6, 0.8].map((q) => v[Math.floor(q * (v.length - 1))]);
}

// Línea "detalle" de un indicador para tarjeta y ficha.
function detalle(ind, d, nac) {
  if (!d) return "";
  const parts = [];
  if (d.var != null && ind.clave !== "ITAEE") parts.push(`${fmt.pct(d.var)} anual`);
  if (ind.clave === "IED" && d.comparable != null) {
    const change = d.cambio == null ? "" : ` · ${conSigno(d.cambio)} mdd`;
    parts.push(`Base: ${fmt.mdd(d.comparable)} (${d.periodo_comparable})${change}`);
  }
  if (d.part != null) parts.push(`${fmt.pctPlain(d.part)} del total nacional`);
  if (ind.clave === "ITAEE" && nac?.valor != null) parts.push(`México: ${fmt.pct(nac.valor)}`);
  if (ind.clave === "ENOE" && nac?.valor != null) parts.push(`México: ${fmt.pctPlain(nac.valor)}`);
  return parts.join(" · ");
}

// Fuentes del subtítulo: las de los indicadores con datos, sin el detalle entre paréntesis.
export function fuentesDe(indicadores) {
  const nombres = [...new Set(indicadores.map((i) => String(i.fuente || "").replace(/\s*\(.*\)\s*$/, "").trim()).filter(Boolean))];
  return nombres.length > 1 ? `${nombres.slice(0, -1).join(", ")} y ${nombres.at(-1)}` : (nombres[0] || "");
}

export function renderEstatal(root, data, geo, opts = {}) {
  const st = { ind: (data.indicadores.find((i) => i.estatus !== "pendiente") || data.indicadores[0]).clave, abierta: opts.clave || null, sortAsc: false };
  const byClave = Object.fromEntries(data.entidades.map((e) => [e.clave, e]));
  const indOf = (k) => data.indicadores.find((i) => i.clave === k);
  const activos = data.indicadores.filter((i) => i.estatus !== "pendiente");
  const pendientes = data.indicadores.filter((i) => i.estatus === "pendiente");

  root.innerHTML = "";
  root.classList.add("pe-root");
  const head = h("div", { class: "pe-head" },
    h("h2", { class: "pe-title" }, "Panorama Estatal"),
    h("p", { class: "pe-caption" }, `32 entidades federativas · ${fuentesDe(activos)}`));
  const aviso = data.estado === "prueba" ? h("p", { class: "pe-aviso", role: "note" }, h("strong", {}, "Vista de prueba. "), data.nota || "") : null;
  const body = h("div", { class: "pe-body" });
  root.append(head, aviso || "", body);

  const tip = h("div", { class: "pe-tip", role: "tooltip", hidden: true });
  document.body.append(tip);

  function openFicha(clave, push = true) {
    st.abierta = clave; hideTip();
    if (push && opts.onRoute) opts.onRoute(clave);
    draw();
    root.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  function closeFicha() { st.abierta = null; if (opts.onRoute) opts.onRoute(null); draw(); }

  // ---- Tarjeta flotante ----
  function tipContent(e) {
    const rows = data.indicadores.map((ind) => {
      const d = e.ind[ind.clave];
      if (ind.estatus === "pendiente" || !d) return h("div", { class: "pe-tip-row pend" }, h("span", { class: "k" }, ind.nombre), h("span", { class: "v" }, "Por conectar"));
      const lugar = d.lugar ? ` · ${ord(d.lugar)}` : "";
      return h("div", { class: `pe-tip-row${ind.clave === st.ind ? " sel" : ""}` },
        h("span", { class: "k" }, `${ind.nombre} `, h("span", { class: "per" }, displayPeriod(ind))),
        h("span", { class: "v" }, `${fmtVal(ind, d.valor)}${lugar}`));
    });
    return [h("div", { class: "pe-tip-name" }, e.nombre), ...rows,
      h("div", { class: "pe-tip-foot" }, "Clic para abrir la ficha del estado")];
  }
  function showTip(e, x, y) {
    tip.replaceChildren(...tipContent(e)); tip.hidden = false;
    const r = tip.getBoundingClientRect();
    let left = x + 16, top = y + 16;
    if (left + r.width > window.innerWidth - 8) left = x - r.width - 16;
    if (top + r.height > window.innerHeight - 8) top = Math.max(8, window.innerHeight - r.height - 8);
    tip.style.left = `${left + window.scrollX}px`; tip.style.top = `${top + window.scrollY}px`;
  }
  function hideTip() { tip.hidden = true; }

  // ---- Vista del mapa ----
  function drawMapa() {
    const ind = indOf(st.ind);
    const vals = data.entidades.map((e) => e.ind[ind.clave]?.valor ?? null);
    const cuts = quintiles(vals);

    const selector = h("div", { class: "pe-selector", role: "radiogroup", "aria-label": "Indicador para colorear el mapa" },
      ...activos.map((i) => h("button", { type: "button", role: "radio", class: "pe-chip", "aria-checked": String(i.clave === st.ind), onclick: () => { st.ind = i.clave; draw(); } }, i.nombre)),
      pendientes.length ? h("span", { class: "pe-pend" }, `Por conectar: ${pendientes.map((i) => i.nombre).join(" · ")}`) : null);

    const svg = s("svg", { viewBox: geo.viewBox, class: "pe-map", role: "group", "aria-label": `Mapa de México coloreado por ${ind.nombre.toLowerCase()}` });
    const touch = window.matchMedia("(hover: none)").matches;
    data.entidades.forEach((e) => {
      const d = e.ind[ind.clave];
      const p = s("path", { d: geo.estados[e.svg], fill: colorFor(ind, d?.valor, cuts), class: "pe-state", tabindex: "0", role: "button",
        "aria-label": `${e.nombre}: ${ind.nombre} ${fmtVal(ind, d?.valor)}${d?.lugar ? `, lugar ${d.lugar}` : ""}. Abrir ficha.` });
      p.addEventListener("mousemove", (ev) => { if (!touch) showTip(e, ev.clientX, ev.clientY); });
      p.addEventListener("mouseleave", hideTip);
      p.addEventListener("focus", () => { const b = p.getBoundingClientRect(); showTip(e, b.right, b.top); });
      p.addEventListener("blur", hideTip);
      p.addEventListener("keydown", (ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); openFicha(e.clave); } });
      p.addEventListener("click", () => { if (touch) { sheet(e); } else openFicha(e.clave); });
      svg.append(p);
    });

    // Leyenda
    let legend;
    if (ind.escala === "divergente") {
      const labels = ["< −4", "−4 a −2", "−2 a −0.5", "±0.5", "0.5 a 2", "2 a 4", "> 4"];
      legend = h("div", { class: "pe-legend" }, h("span", { class: "pe-leg-t" }, `${ind.medida} (%)`),
        h("div", { class: "pe-leg-row" }, ...PAL.div.map((c, i) => h("span", { class: "pe-leg-i" }, h("i", { style: `background:${c}` }), labels[i]))));
    } else {
      const f = (v) => ind.formato === "mdp" ? milesMdp(v) + " mil" : nf(0).format(v);
      const edges = [Math.min(...vals.filter((v) => v != null)), ...cuts];
      legend = h("div", { class: "pe-legend" }, h("span", { class: "pe-leg-t" }, `${ind.medida} · quintiles`),
        h("div", { class: "pe-leg-row" }, ...PAL.seq.map((c, i) => h("span", { class: "pe-leg-i" }, h("i", { style: `background:${c}` }), i === 4 ? `≥ ${f(cuts[3])}` : `${f(edges[i])}–${f(cuts[i])}`))));
    }

    // Tabla de 32
    const rows = data.entidades.map((e) => ({ e, d: e.ind[ind.clave] || {} }));
    rows.sort((a, b) => (a.d.lugar ?? 99) - (b.d.lugar ?? 99));
    if (st.sortAsc) rows.reverse();
    const nac = data.nacional?.[ind.clave];
    const hasShare = rows.some(({ d }) => d.part != null);
    const table = h("table", { class: "pe-table" },
      h("caption", {}, `${ind.nombre} · ${displayPeriod(ind)}`),
      h("thead", {}, h("tr", {},
        h("th", { scope: "col" }, h("button", { type: "button", class: "pe-sort", onclick: () => { st.sortAsc = !st.sortAsc; draw(); }, "aria-label": "Invertir orden" }, `Lugar ${st.sortAsc ? "↑" : "↓"}`)),
        h("th", { scope: "col" }, "Entidad"),
        h("th", { scope: "col", class: "num" }, labelValue(ind)),
        hasShare ? h("th", { scope: "col", class: "num" }, "% nal.") : null)),
      h("tbody", {}, ...rows.map(({ e, d }) => h("tr", { tabindex: "0", onclick: () => openFicha(e.clave), onkeydown: (ev) => { if (ev.key === "Enter") openFicha(e.clave); } },
        h("td", { class: "num" }, ord(d.lugar)), h("td", {}, e.nombre),
        h("td", { class: "num" }, fmtCelda(ind, d.valor)),
        hasShare ? h("td", { class: "num" }, d.part == null ? "—" : nf(1).format(d.part)) : null))),
      nac ? h("tfoot", {}, h("tr", {}, h("td", {}), h("td", {}, "Nacional"), h("td", { class: "num" }, fmtCelda(ind, nac.valor)), hasShare ? h("td", { class: "num" }, "100.0") : null)) : null);

    const ranking = ind.clave === "ENOE"
      ? "La primera posición corresponde a la mayor desocupación."
      : `Lugar por ${ind.lugar_por}.`;
    const src = h("p", { class: "pe-src" }, `Fuente: ${ind.fuente}. ${ind.medida}, ${displayPeriod(ind)}. ${ranking} ${geo.fuente}.`);
    const imssNote = ind.clave === "IMSS"
      ? h("p", { class: "pe-src" }, `Último cuadro disponible del IMSS: ${displayPeriod(ind)}.`)
      : null;
    body.replaceChildren(selector, h("div", { class: "pe-grid" },
      h("div", { class: "pe-mapwrap" }, svg, legend, src),
      h("div", { class: "pe-tablewrap" }, table, imssNote)));
  }

  // Hoja inferior para pantallas táctiles.
  function sheet(e) {
    const close = () => sh.remove();
    const sh = h("div", { class: "pe-sheet", role: "dialog", "aria-label": e.nombre },
      ...tipContent(e).slice(0, -1),
      h("div", { class: "pe-sheet-btns" }, h("button", { type: "button", class: "pe-btn", onclick: () => { close(); openFicha(e.clave); } }, "Ver ficha"), h("button", { type: "button", class: "pe-btn ghost", onclick: close }, "Cerrar")));
    document.querySelectorAll(".pe-sheet").forEach((n) => n.remove());
    document.body.append(sh);
  }

  // ---- Ficha del estado ----
  function drawFicha(clave) {
    const e = byClave[clave];
    if (!e) { st.abierta = null; return drawMapa(); }
    const pib = e.ind.PIB, idx = data.entidades.findIndex((x) => x.clave === clave);
    const pibInd = indOf("PIB");
    const nav = (k) => data.entidades[(idx + k + 32) % 32];
    const top = h("div", { class: "pe-f-top" },
      h("button", { type: "button", class: "pe-back", onclick: closeFicha }, "← Mapa de los 32 estados"),
      h("div", { class: "pe-f-nav" },
        h("button", { type: "button", class: "pe-back", onclick: () => openFicha(nav(-1).clave), "aria-label": `Anterior: ${nav(-1).nombre}` }, `‹ ${nav(-1).nombre}`),
        h("button", { type: "button", class: "pe-back", onclick: () => openFicha(nav(1).clave), "aria-label": `Siguiente: ${nav(1).nombre}` }, `${nav(1).nombre} ›`)));
    const title = h("div", { class: "pe-f-head" },
      h("h3", { class: "pe-f-name" }, e.nombre),
      h("p", { class: "pe-f-sub" }, pib ? `${ord(pib.lugar)} economía del país · ${fmt.pctPlain(pib.part)} del PIB nacional (${pibInd?.periodo || "2024"})` : "",
        e.nombre_oficial !== e.nombre ? ` · ${e.nombre_oficial}` : ""));

    const trs = data.indicadores.map((ind) => {
      const d = e.ind[ind.clave];
      if (ind.estatus === "pendiente" || !d) return h("tr", { class: "pend" }, h("th", { scope: "row" }, ind.nombre, h("span", { class: "per" }, ind.fuente)), h("td", { colspan: "3" }, "Por conectar (N-039)"));
      return h("tr", {},
        h("th", { scope: "row" }, ind.nombre, h("span", { class: "per" }, `${displayPeriod(ind)} · ${ind.medida}`)),
        h("td", { class: "num strong" }, fmtVal(ind, d.valor)),
        h("td", {}, detalle(ind, d, data.nacional?.[ind.clave])),
        h("td", { class: "num" }, ord(d.lugar)));
    });
    const main = h("table", { class: "pe-ftable" },
      h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Indicador y periodo"), h("th", { scope: "col", class: "num" }, "Último dato"), h("th", { scope: "col" }, "Variación o participación"), h("th", { scope: "col", class: "num" }, "Lugar"))),
      h("tbody", {}, ...trs));

    const products = data.descargas?.[clave];
    const downloads = products && h("div", { class: "pe-f-nav pe-downloads" },
      h("a", { class: "pe-btn", href: products.pdf, download: true }, "Descargar PDF"),
      h("a", { class: "pe-btn ghost", href: products.xlsx, download: true }, "Descargar Excel"));
    const blocks = [top, title, downloads, main, h("p", { class: "pe-src" },
      "Lugar entre 32 entidades, de mayor a menor. En desocupación, el primer lugar corresponde a la tasa más alta.")];
    const rates = e.ind.ENOE?.tasas;
    if (rates) blocks.push(h("h4", { class: "pe-f-h4" }, `Mercado laboral · ${indOf("ENOE").periodo}`),
      h("table", { class: "pe-ftable" },
        h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Tasa ENOE"),
          h("th", { scope: "col", class: "num" }, e.nombre), h("th", { scope: "col", class: "num" }, "México"))),
        h("tbody", {}, ...Object.entries(rates).filter(([name]) => name !== "Desocupación")
          .map(([name, values]) => h("tr", {}, h("th", { scope: "row" }, name),
            ...values.map((value) => h("td", { class: "num" }, fmt.pctPlain(value))))))));
    const serie = e.ind.ETEF?.serie;
    if (serie?.length) blocks.push(h("h4", { class: "pe-f-h4" }, "Exportaciones trimestrales · millones de dólares"), barChart(serie), h("p", { class: "pe-src" }, "Fuente: INEGI, Exportaciones Trimestrales por Entidad Federativa (ETEF)."));
    body.replaceChildren(...blocks);
  }

  // Barras de exportaciones con su tarjeta al pasar el cursor.
  function barChart(serie) {
    const W = 640, H = 200, pad = { l: 8, r: 8, t: 22, b: 26 };
    const max = Math.max(...serie.map((x) => x[1]));
    const bw = (W - pad.l - pad.r) / serie.length;
    const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, class: "pe-bars", role: "img", "aria-label": "Exportaciones trimestrales" });
    svg.append(s("line", { x1: pad.l, x2: W - pad.r, y1: H - pad.b, y2: H - pad.b, stroke: PAL.line }));
    serie.forEach(([per, v], i) => {
      const bh = (v / max) * (H - pad.t - pad.b), x = pad.l + i * bw + 3, y = H - pad.b - bh, last = i === serie.length - 1;
      const r = s("rect", { x, y, width: bw - 6, height: bh, rx: 3, fill: last ? PAL.cafe : "#7FA394" });
      const t = s("title", {}); t.textContent = `${per}: ${nf(1).format(v)} mdd`; r.append(t);
      svg.append(r);
      const lab = s("text", { x: x + (bw - 6) / 2, y: H - 8, "text-anchor": "middle", class: "pe-bar-x" }); lab.textContent = per.replace("-20", "-"); svg.append(lab);
      if (last || i === 0) { const vl = s("text", { x: x + (bw - 6) / 2, y: y - 6, "text-anchor": "middle", class: "pe-bar-v" }); vl.textContent = nf(0).format(v); svg.append(vl); }
    });
    return svg;
  }

  function draw() { hideTip(); if (st.abierta) drawFicha(st.abierta); else drawMapa(); }
  draw();
  return { open: (c) => openFicha(c, false), close: () => { st.abierta = null; draw(); } };
}
