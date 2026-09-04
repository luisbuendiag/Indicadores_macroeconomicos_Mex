// assets/js/calendar.js - Modulo de calendario de publicaciones (ES)
// UI/UX redisenada para data/calendario.json; compatible con data/calendario_publicaciones.json
import { ORDER, LABELS, SIGLA } from "./config.js";


const MES_NOMBRES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
const MES_CORTOS = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"];
const DIA_CORTOS = ["dom", "lun", "mar", "mié", "jue", "vie", "sáb"];

const FILE_ICON = (letter) => `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false" role="img"><title>${letter}</title><path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><polyline points="13 2 13 9 20 9"/><text x="12" y="17" font-size="8" font-family="sans-serif" font-weight="700" text-anchor="middle" fill="currentColor">${letter}</text></svg>`;

const DEFAULT_CATEGORIES = {
  "Actividad económica": "#0d47a1",
  "Precios": "#b71c1c",
  "Consumo e inversión": "#1b5e20",
  "Mercado laboral": "#e65100",
  "Sector externo": "#4a148c",
  "Financiero": "#006064",
};

// Mapa de respaldo por clave cuando el evento no trae categoria
const CATEGORY_BY_CLAVE = {
  PIB: "Actividad económica",
  PIBSEC: "Actividad económica",
  IGAE: "Actividad económica",
  IMAI: "Actividad económica",
  IOAE: "Actividad económica",
  EMOE: "Actividad económica",
  INPC: "Precios",
  INPP: "Precios",
  CONSUMO: "Consumo e inversión",
  IMFBCF: "Consumo e inversión",
  DESOCUP: "Mercado laboral",
  BCMM: "Sector externo",
  BALANZA: "Sector externo",
  IED: "Sector externo",
  TIPOCAMBIO: "Financiero",
  TASA: "Financiero",
  RESERVAS: "Financiero",
};

const calState = {
  category: "",
  source: "",
  frequency: "",
  indicator: "",
  mode: "mensual",
  months: 1,
  sort: { col: "fecha", dir: 1 },
  current: null,
};

// ---------- Helpers de fecha ----------
export function parseIso(iso) {
  if (!iso) return null;
  const m = String(iso).match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (m) return new Date(parseInt(m[1], 10), parseInt(m[2], 10) - 1, parseInt(m[3], 10));
  const d = new Date(iso);
  if (!isNaN(d.getTime())) return d;
  return null;
}

export function displayDate(iso) {
  const d = parseIso(iso);
  if (!d) return iso || "—";
  return `${d.getDate()} de ${MES_NOMBRES[d.getMonth()]} de ${d.getFullYear()}`;
}

export function shortDate(iso) {
  const d = parseIso(iso);
  if (!d) return iso || "—";
  return `${String(d.getDate()).padStart(2, "0")} ${MES_CORTOS[d.getMonth()]} ${String(d.getFullYear()).slice(-2)}`;
}

// Para comparaciones sin problemas de zona horaria
function compareDate(iso) {
  return iso ? new Date(`${iso}T00:00:00`) : null;
}

function monthKey(year, month) {
  return `${year}-${String(month).padStart(2, "0")}`;
}

function isSameMonth(d, year, month) {
  return d && d.getFullYear() === year && d.getMonth() + 1 === month;
}

function addMonths(year, month, delta) {
  const d = new Date(year, month - 1 + delta, 1);
  return { year: d.getFullYear(), month: d.getMonth() + 1 };
}

// ---------- Estado y normalizacion ----------
function getCal(ctx) {
  return ctx.state.calendario || {};
}

function rawEvents(ctx) {
  const cal = getCal(ctx);
  if (Array.isArray(cal.events)) return cal.events;
  if (Array.isArray(cal.items)) return cal.items;
  return [];
}

function rawRules(ctx) {
  const cal = getCal(ctx);
  if (Array.isArray(cal.rules)) return cal.rules;
  // El esquema antiguo incluye reglas dentro de items
  if (Array.isArray(cal.items)) return cal.items.filter((it) => (it.estatus || it.type) === "regla");
  return [];
}

function normalizeEvent(e) {
  const clave = (e.clave || e.sigla || e.indicator || "").toString().trim();
  const isRule = (e.type === "rule" || e.estatus === "regla");
  const fechaIso = e.fecha_iso || e.publication_date || e.fecha || null;
  let anio = e.anio;
  let mes = e.mes;
  if (fechaIso && (!anio || !mes)) {
    const d = parseIso(fechaIso);
    if (d) { anio = d.getFullYear(); mes = d.getMonth() + 1; }
  }
  const cat = e.categoria || e.category || CATEGORY_BY_CLAVE[clave] || "";
  const src = e.source || e.fuente || e.institucion || e.institution || "";
  return {
    clave,
    indicador: e.indicador || e.product || e.producto || e.name || e.program || clave,
    producto: e.producto || e.product || e.name || e.indicador || clave,
    program: e.program || e.programa || "",
    fecha_publicacion: e.fecha_publicacion || e.publication_date_display || displayDate(fechaIso),
    fecha_iso: fechaIso,
    anio,
    mes,
    periodo_referencia: e.periodo_referencia || e.reference_period || e.period || "",
    frecuencia: e.frecuencia || e.frequency || "",
    estatus: e.estatus || e.status || "",
    source: src,
    institucion: e.institucion || e.institution || src,
    categoria: cat,
    url_boletin: e.url_boletin || e.url || "",
    comentario: e.comentario || e.notes || "",
    deliverables: Array.isArray(e.deliverables) ? e.deliverables : [],
    type: isRule ? "rule" : (e.type || "event"),
    raw: e,
  };
}

function normalizeRule(r) {
  const clave = (r.indicator || r.clave || r.sigla || "").toString().trim();
  return {
    clave,
    indicador: r.name || r.product || r.producto || r.indicador || clave,
    producto: r.product || r.producto || r.name || clave,
    regla_publicacion: r.rule_text || r.regla_publicacion || "",
    frecuencia: r.frequency || r.frecuencia || "",
    institucion: r.institution || r.institucion || r.source || "",
    categoria: r.category || r.categoria || CATEGORY_BY_CLAVE[clave] || "",
    url: r.url || r.url_boletin || "",
    type: "rule",
    raw: r,
  };
}

function getEvents(ctx) {
  return rawEvents(ctx).filter((e) => (e.type || e.estatus) !== "regla").map(normalizeEvent);
}

function getRules(ctx) {
  return rawRules(ctx).map(normalizeRule);
}

function getRulesForKey(ctx, key) {
  return getRules(ctx).filter((r) => r.clave === key);
}

function getEventsForKey(ctx, key) {
  return getEvents(ctx).filter((e) => e.clave === key).sort((a, b) => (b.fecha_iso || "").localeCompare(a.fecha_iso || ""));
}

function asOfIso(ctx) {
  return getCal(ctx).as_of || getCal(ctx).actualizado || null;
}

function asOfDate(ctx) {
  const iso = asOfIso(ctx);
  return iso ? compareDate(iso) : new Date();
}

function getCategoriesMap(ctx) {
  return getCal(ctx).categories || DEFAULT_CATEGORIES;
}

// ---------- Estatus y color ----------
export function statusLabel(st) {
  if (st === "publicado") return "Publicado";
  if (st === "proximo" || st === "próximo") return "Próxima publicación";
  if (st === "pendiente") return "Pendiente";
  if (st === "no_anunciada") return "Fecha oficial no anunciada";
  if (st === "evento") return "Decisión / anuncio";
  if (st === "reprogramado") return "Reprogramado";
  if (st === "regla") return "Regla de publicación";
  return st || "—";
}

export function statusClass(st) {
  const s = (st || "").toString().toLowerCase().trim();
  if (["publicado"].includes(s)) return "publicado";
  if (["proximo", "próximo", "pendiente"].includes(s)) return "próximo";
  if (["no_anunciada"].includes(s)) return "no_anunciada";
  if (["evento"].includes(s)) return "evento";
  if (["reprogramado"].includes(s)) return "reprogramado";
  return s || "na";
}

function statusChip(st) {
  const cls = statusClass(st);
  return el("span", { class: `cal-status ${cls}` }, statusLabel(st));
}

function sourceDotClass(status) {
  const s = (status || "").toString().toLowerCase().trim();
  if (s === "ok") return "ok";
  if (["warning", "warn"].includes(s)) return "warn";
  if (["error", "fail"].includes(s)) return "error";
  return "ok";
}

export function categoryColor(ctx, category) {
  const map = getCategoriesMap(ctx);
  if (category && map[category]) return map[category];
  return DEFAULT_CATEGORIES[category] || "#5c5f6a";
}

function shortSource(ev) {
  const s = (ev.source || ev.institucion || ev.institution || "").toString().toLowerCase();
  if (/inegi/.test(s)) return "INEGI";
  if (/banxico/.test(s)) return "Banxico";
  if (/secretar[ií]a de econom[ií]a|direccion general de inversion|se/.test(s)) return "SE";
  if (/banco de méxico|banco de mexico/.test(s)) return "Banxico";
  return ev.source || ev.institucion || ev.institution || "";
}

// ---------- Wrappers de compatibilidad con app.js ----------
export function nextPublication(ctx, key) {
  const asOf = asOfDate(ctx);
  const events = getEventsForKey(ctx, key).filter((c) => {
    if (["próximo", "no_anunciada"].includes(c.estatus)) return true;
    if (c.estatus === "evento" && c.fecha_iso) {
      const d = compareDate(c.fecha_iso);
      return d && d > asOf;
    }
    return c.estatus === "próximo";
  });
  events.sort((a, b) => (a.fecha_iso || "9999-12-31").localeCompare(b.fecha_iso || "9999-12-31"));
  return events[0] || null;
}

export function upcomingPublications(ctx, n = 8) {
  const asOf = asOfDate(ctx);
  const events = getEvents(ctx).filter((c) => {
    if (["próximo", "pendiente", "no_anunciada"].includes(c.estatus)) return true;
    if (c.estatus === "evento" && c.fecha_iso) {
      const d = compareDate(c.fecha_iso);
      return d && d >= asOf;
    }
    return false;
  });
  events.sort((a, b) => (a.fecha_iso || "9999-12-31").localeCompare(b.fecha_iso || "9999-12-31"));
  return events.slice(0, n);
}

export function calendarioDisponible(ctx, ind) {
  if (!ind) return false;
  if (ind.regla_publicacion) return true;
  if (ind.proxima_publicacion) return true;
  if (ind.observations_original && ind.observations_original.length) return true;
  if (getEventsForKey(ctx, ind.key).some((c) => c.fecha_iso || c.url_boletin)) return true;
  if (getRulesForKey(ctx, ind.key).length) return true;
  return false;
}

export function openCalendarioFiltro(ctx, ind) {
  ctx.openModal(`Calendario de publicaciones · ${ind.nombre}`, buildCalendarioPanel(ctx, ind));
}

export function buildCalendarioPanel(ctx, ind) {
  const all = getEventsForKey(ctx, ind.key).filter((c) => c.type !== "rule");
  const rule = getRulesForKey(ctx, ind.key)[0];
  const asOf = asOfDate(ctx);

  const isFuture = (c) => c.fecha_iso && compareDate(c.fecha_iso) > asOf;
  const latest = all.find((c) => c.estatus === "publicado" || (c.estatus === "evento" && !isFuture(c)));
  const nextCandidates = all.filter((c) =>
    ["próximo", "no_anunciada"].includes(c.estatus) || (c.estatus === "evento" && isFuture(c))
  );
  const next = nextCandidates.sort((a, b) => (a.fecha_iso || "9999-12-31").localeCompare(b.fecha_iso || "9999-12-31"))[0];

  const wrap = el("div", { class: "ind-cal" });

  const hero = el("div", { class: "cal-hero" });
  hero.append(el("div", { class: "cal-hero-lbl" }, ind.nombre));
  if (latest) {
    hero.append(el("div", { class: "cal-hero-date" }, latest.fecha_publicacion));
    const lbl = latest.estatus === "evento" ? "Última decisión" : "Última publicación";
    hero.append(el("div", {}, `${lbl}: ${latest.periodo_referencia} · ${statusLabel(latest.estatus)}`));
    if (latest.url_boletin) {
      hero.append(el("a", { href: latest.url_boletin, target: "_blank", rel: "noopener" }, "Comunicado / boletín oficial"));
    }
  }
  if (next) {
    if (next.estatus === "no_anunciada") {
      hero.append(el("div", { class: "cal-hero-ind" }, `Próxima publicación: ${next.periodo_referencia}`));
      hero.append(el("div", { class: "cal-hero-src" }, next.comentario || "Próxima fecha oficial no anunciada"));
    } else if (next.estatus === "evento") {
      hero.append(el("div", { class: "cal-hero-ind" }, `Próxima decisión: ${next.fecha_publicacion} · ${next.periodo_referencia}`));
      hero.append(el("div", { class: "cal-hero-src" }, `${next.producto} — ${next.institucion}`));
    } else {
      hero.append(el("div", { class: "cal-hero-ind" }, `Próxima publicación: ${next.fecha_publicacion} · ${next.periodo_referencia}`));
      hero.append(el("div", { class: "cal-hero-src" }, `${next.producto} — ${next.institucion}`));
    }
  } else if (!latest) {
    hero.append(el("div", { class: "muted" }, "Sin fechas registradas para este indicador."));
  }

  if (rule || ind.regla_publicacion) {
    hero.append(el("div", { class: "cal-hero-rule" }, `Frecuencia: ${ind.frecuencia_original || ind.frecuencia} · ${rule?.regla_publicacion || ind.regla_publicacion}`));
  }
  if (ind.fecha_ultima_observacion) {
    hero.append(el("div", { class: "cal-hero-src" }, `Última observación disponible: ${ind.fecha_ultima_observacion}`));
  }
  const url = ind.url_fuente_oficial || ind.url_boletin_oficial || (ind.fuente && ind.fuente.link) || null;
  if (url) {
    hero.append(el("a", { href: url, target: "_blank", rel: "noopener" }, "Consultar fuente oficial"));
  }
  wrap.append(hero);

  const histWrap = el("div", { class: "panel cal-hist" });
  histWrap.append(el("h3", {}, "Histórico reciente"));
  if (all.length) {
    const ul = el("ul", { class: "cal-list" });
    all.slice(0, 12).forEach((c) => {
      const li = el("li", {},
        el("span", { class: "cal-list-date" }, c.fecha_publicacion || "—"),
        el("span", {}, ` · ${c.periodo_referencia} · ${statusLabel(c.estatus)}`)
      );
      if (c.clave && ctx.getInd(c.clave)) {
        li.classList.add("clickable");
        li.addEventListener("click", () => { ctx.closeModal(); ctx.setView(c.clave); });
      }
      ul.append(li);
    });
    histWrap.append(ul);
  } else if (ind.observations_original) {
    const recent = [...ind.observations_original].reverse().slice(0, 12);
    const ul = el("ul", { class: "cal-list" });
    recent.forEach((o) => {
      ul.append(el("li", {},
        el("span", { class: "cal-list-date" }, o.period),
        el("span", {}, ` · Valor: ${o.values[0]}`)
      ));
    });
    histWrap.append(ul);
  } else {
    histWrap.append(el("div", { class: "muted" }, "No hay publicaciones registradas."));
  }
  wrap.append(histWrap);

  return wrap;
}

// ---------- Render del calendario completo ----------
export function renderCalendar(ctx) {
  const sec = ctx.$("#view-calendario");
  if (!sec) return;
  sec.innerHTML = "";
  sec.append(el("div", { class: "section-title" }, "Calendario de publicaciones"));

  const cal = getCal(ctx);
  const events = getEvents(ctx);

  if (!cal || (!events.length && !Object.keys(cal).length)) {
    sec.append(el("div", { class: "notice" }, "El calendario oficial se integra a partir de data/calendario.json. Mientras tanto se muestran las próximas fechas indicativas de cada indicador."));
    const panel = el("div", { class: "panel" });
    const fallback = (ctx.state.data?.indicators ? Object.values(ctx.state.data.indicators) : [])
      .filter((ind) => ind && (ind.proximo || ind.fecha_publicacion));
    fallback.forEach((ind) => {
      panel.append(el("div", { class: "cal-item" },
        el("span", { class: "date" }, ind.proximo || ind.fecha_publicacion),
        el("span", {}, `${LABELS[ind.key] || ind.nombre} · ${ind.fuente?.nombre || ""} · ${ind.frecuencia || ""}`)
      ));
    });
    if (!panel.children.length) panel.append(el("div", { class: "muted" }, "Sin fechas confirmadas."));
    sec.append(panel);
    return;
  }

  renderHeaderAndLegend(ctx, sec);
  sec.append(renderHighlights(ctx));
  sec.append(renderControls(ctx));
  sec.append(el("div", { id: "cal-body" }));
  drawCalBody(ctx);
}

function renderHeaderAndLegend(ctx, sec) {
  const cal = getCal(ctx);
  const sourceMap = cal.sources || {};
  const asOf = asOfIso(ctx);
  const generated = cal.generated_at || cal.actualizado || null;

  const generatedText = generated
    ? new Date(generated).toLocaleString("es-MX", { timeZone: "America/Mexico_City" })
    : "—";
  const asOfText = asOf ? displayDate(asOf) : "—";

  const sub = el("div", { class: "section-sub" },
    `Fuente: ${cal.fuente || "Calendario oficial de difusión"} · actualizado el ${generatedText} · as_of ${asOfText}.`
  );

  const srcChips = el("div", { class: "cal-legend" });
  Object.entries(sourceMap).forEach(([name, info]) => {
    const dotCls = sourceDotClass(info.status);
    const chip = el("span", { class: "cal-leg-item", title: info.message || `${name}: ${info.status || "ok"}` },
      el("span", { class: `cal-src-dot ${dotCls}` }),
      `${name}${info.count ? ` (${info.count})` : ""}`
    );
    srcChips.append(chip);
  });

  sec.append(sub, srcChips);
}

function renderHighlights(ctx) {
  const wrap = el("div", { class: "cal-highlights" });

  // Próximas publicaciones
  const left = el("div", { class: "panel cal-upcoming" });
  left.append(el("h3", {}, "Próximas publicaciones"));
  const upcoming = upcomingPublications(ctx, 8);
  const nextOne = upcoming[0];

  // Hero compacto de la siguiente publicación
  if (nextOne) {
    const hero = el("div", { class: "cal-hero-sm" });
    hero.append(el("div", { class: "cal-hero-sm-label" }, "Próxima publicación"));
    hero.append(el("div", { class: "cal-hero-sm-date" }, nextOne.fecha_publicacion));
    hero.append(el("div", { class: "cal-hero-sm-main" }, `${nextOne.indicador} · ${nextOne.periodo_referencia}`));
    hero.append(el("div", { class: "cal-hero-sm-src" }, `${nextOne.producto} — ${nextOne.institucion}`));
    hero.append(statusChip(nextOne.estatus));
    left.append(hero);
  } else {
    left.append(el("div", { class: "muted" }, "Sin próximas publicaciones registradas."));
  }

  const upcomingList = el("div", { class: "cal-upcoming-list" });
  upcoming.slice(1).forEach((c) => {
    const src = shortSource(c);
    const row = el("div", { class: "cal-list-row" },
      el("span", { class: "cal-row-date" }, shortDate(c.fecha_iso)),
      el("div", { class: "cal-row-main" },
        el("span", { class: "cal-row-title" }, c.indicador),
        c.periodo_referencia ? el("span", { class: "cal-row-period" }, c.periodo_referencia) : null
      ),
      src ? el("span", { class: "cal-row-source" }, src) : null
    );
    if (c.clave && ctx.getInd(c.clave)) {
      row.classList.add("clickable");
      row.addEventListener("click", () => ctx.setView(c.clave));
    }
    upcomingList.append(row);
  });
  left.append(upcomingList);
  wrap.append(left);

  // Últimas publicaciones
  const right = el("div", { class: "panel cal-recent" });
  right.append(el("h3", {}, "Últimas publicaciones"));
  const recent = recentPublications(ctx, 8);
  const recentList = el("div", { class: "cal-recent-list" });
  if (recent.length) {
    recent.forEach((c) => {
      let actions = null;
      if (c.deliverables?.length) {
        actions = el("div", { class: "cal-row-actions" });
        c.deliverables.forEach((d) => actions.append(deliverableBtn(d)));
      }
      const row = el("div", { class: "cal-list-row" },
        el("span", { class: "cal-row-date" }, shortDate(c.fecha_iso)),
        el("div", { class: "cal-row-main" },
          el("span", { class: "cal-row-title" }, c.indicador),
          c.periodo_referencia ? el("span", { class: "cal-row-period" }, c.periodo_referencia) : null
        ),
        actions
      );
      row.classList.add("clickable");
      row.addEventListener("click", () => openCalEvent(ctx, c));
      recentList.append(row);
    });
  } else {
    recentList.append(el("div", { class: "muted" }, "Sin publicaciones recientes."));
  }
  right.append(recentList);
  wrap.append(right);

  return wrap;
}

function recentPublications(ctx, n = 8) {
  const cal = getCal(ctx);
  if (Array.isArray(cal.recent) && cal.recent.length && cal.recent[0].product) {
    return cal.recent.slice(0, n).map(normalizeEvent);
  }
  return getEvents(ctx)
    .filter((c) => c.estatus === "publicado" || c.estatus === "evento")
    .sort((a, b) => (b.fecha_iso || "").localeCompare(a.fecha_iso || ""))
    .slice(0, n);
}

function deliverableBar(list) {
  if (!list || !list.length) return el("span", { class: "muted" }, "—");
  const wrap = el("span", { class: "cal-event-actions" });
  list.forEach((d) => wrap.append(deliverableBtn(d)));
  return wrap;
}

function deliverableBtn(d) {
  const fmt = (d.format || d.type || "enlace").toString().toLowerCase();
  let kind = "Enlace";
  let cls = "cal-dl-link";
  let letter = "↗";
  if (fmt.includes("pdf")) { kind = "PDF"; cls = "cal-dl-pdf"; letter = "P"; }
  else if (fmt.includes("doc") || fmt.includes("word")) { kind = "Word"; cls = "cal-dl-word"; letter = "W"; }
  else if (fmt.includes("xls") || fmt.includes("excel")) { kind = "Excel"; cls = "cal-dl-excel"; letter = "E"; }
  const label = d.label || d.name || kind;
  return el("a", {
    class: `cal-dl-btn ${cls}`,
    href: d.url || "#",
    target: "_blank",
    rel: "noopener",
    title: `${label}${d.size ? ` · ${d.size}` : ""}`,
    onclick: (e) => { e.stopPropagation(); },
  },
    el("span", { class: "cal-dl-icon", html: FILE_ICON(letter) }),
    el("span", { class: "cal-dl-kind" }, kind),
    d.size ? el("span", { class: "cal-dl-size" }, d.size) : null
  );
}

function renderControls(ctx) {
  const events = getEvents(ctx);
  const wrap = el("div", { class: "cal-controls no-print" });

  const filters = el("div", { class: "cal-filters" });

  // Categoria
  const cats = Object.keys(getCategoriesMap(ctx));
  const catSel = el("select", { onchange: (e) => { calState.category = e.target.value; drawCalBody(ctx); } },
    el("option", { value: "" }, "Todas las categorías"),
    ...cats.map((c) => el("option", { value: c, selected: calState.category === c ? "" : null }, c))
  );
  filters.append(filterGroup("Categoría", catSel));

  // Fuente
  const srcSet = [...new Set(events.map(shortSource))].sort();
  const srcSel = el("select", { onchange: (e) => { calState.source = e.target.value; drawCalBody(ctx); } },
    el("option", { value: "" }, "Todas las fuentes"),
    ...["INEGI", "Banxico", "SE", ...srcSet].filter((v, i, a) => a.indexOf(v) === i).map((s) =>
      el("option", { value: s, selected: calState.source === s ? "" : null }, s)
    )
  );
  filters.append(filterGroup("Fuente", srcSel));

  // Frecuencia
  const freqSet = [...new Set(events.map((e) => e.frecuencia).filter(Boolean))].sort();
  const freqSel = el("select", { onchange: (e) => { calState.frequency = e.target.value; drawCalBody(ctx); } },
    el("option", { value: "" }, "Todas las frecuencias"),
    ...freqSet.map((f) => el("option", { value: f, selected: calState.frequency === f ? "" : null }, f))
  );
  filters.append(filterGroup("Frecuencia", freqSel));

  // Indicador
  const indSel = el("select", { onchange: (e) => { calState.indicator = e.target.value; drawCalBody(ctx); } },
    el("option", { value: "" }, "Todos los indicadores")
  );
  ORDER.forEach((k) => {
    indSel.append(el("option", { value: k, selected: calState.indicator === k ? "" : null }, LABELS[k] || k));
  });
  filters.append(filterGroup("Indicador", indSel));

  // Vista mensual / tabular
  const viewToggle = el("div", { class: "cal-view-toggle", role: "group", "aria-label": "Vista del calendario" });
  [["mensual", "Vista mensual"], ["tabla", "Vista tabular"]].forEach(([m, lbl]) => {
    viewToggle.append(el("button", {
      class: "win-btn", type: "button", "aria-pressed": String(calState.mode === m),
      onclick: () => { calState.mode = m; drawCalBody(ctx); },
    }, lbl));
  });

  // Rango 1 / 3 meses
  const rangeToggle = el("div", { class: "cal-view-toggle", role: "group", "aria-label": "Meses visibles" });
  [[1, "1 mes"], [3, "3 meses"]].forEach(([n, lbl]) => {
    rangeToggle.append(el("button", {
      class: "win-btn", type: "button", "aria-pressed": String(calState.months === n),
      onclick: () => { calState.months = n; drawCalBody(ctx); },
    }, lbl));
  });

  // Navegacion
  const nav = el("div", { class: "cal-view-toggle" });
  nav.append(
    el("button", { class: "win-btn", type: "button", onclick: () => shiftCurrent(ctx, -1) }, "← Mes anterior"),
    el("button", { class: "win-btn", type: "button", onclick: () => resetCurrent(ctx) }, "Hoy"),
    el("button", { class: "win-btn", type: "button", onclick: () => shiftCurrent(ctx, 1) }, "Mes siguiente →")
  );

  wrap.append(filters, el("div", { class: "cal-view-row" }, viewToggle, rangeToggle, nav));
  return wrap;
}

function filterGroup(label, select) {
  return el("div", { class: "cal-filter-group" },
    el("label", {}, label),
    select
  );
}

function ensureCurrent(ctx) {
  if (!calState.current) {
    const asOf = asOfDate(ctx);
    calState.current = new Date(asOf.getFullYear(), asOf.getMonth(), 1);
  }
  return calState.current;
}

function resetCurrent(ctx) {
  const asOf = asOfDate(ctx);
  calState.current = new Date(asOf.getFullYear(), asOf.getMonth(), 1);
  drawCalBody(ctx);
}

function shiftCurrent(ctx, delta) {
  const cur = ensureCurrent(ctx);
  calState.current = new Date(cur.getFullYear(), cur.getMonth() + delta, 1);
  drawCalBody(ctx);
}

function drawCalBody(ctx) {
  const host = document.getElementById("cal-body");
  if (!host) return;
  host.innerHTML = "";
  if (calState.mode === "tabla") drawCalTable(ctx, host);
  else drawCalMonths(ctx, host);
}

function filterEvents(events) {
  return events.filter((e) => {
    if (calState.category && e.categoria !== calState.category) return false;
    if (calState.source && shortSource(e) !== calState.source) return false;
    if (calState.frequency && e.frecuencia !== calState.frequency) return false;
    if (calState.indicator && e.clave !== calState.indicator) return false;
    return true;
  });
}

function drawCalMonths(ctx, host) {
  const events = filterEvents(getEvents(ctx));
  if (!events.length) { host.append(el("div", { class: "panel muted" }, "Sin publicaciones para el filtro seleccionado.")); return; }

  const cur = ensureCurrent(ctx);
  const months = [];
  for (let i = 0; i < calState.months; i++) {
    const { year, month } = addMonths(cur.getFullYear(), cur.getMonth() + 1, i);
    months.push({ year, month });
  }

  // Leyenda de categorias presentes
  const presentCats = [...new Set(events.map((e) => e.categoria).filter(Boolean))];
  const legend = el("div", { class: "cal-legend" });
  presentCats.forEach((cat) => {
    legend.append(el("span", { class: "cal-leg-item" },
      el("span", { class: "cal-leg-dot", style: `background:${categoryColor(ctx, cat)}` }),
      cat
    ));
  });
  host.append(legend);

  const grid = el("div", { class: `cal-months ${calState.months === 3 ? "three" : ""}` });
  months.forEach(({ year, month }) => {
    const monthEvents = events.filter((e) => e.anio === year && e.mes === month);
    grid.append(monthCard(ctx, year, month, monthEvents));
  });
  host.append(grid);
}

function monthCard(ctx, year, month, events) {
  const card = el("div", { class: "panel cal-month" });
  card.append(el("div", { class: "cal-month-title" }, `${MES_NOMBRES[month - 1]} ${year}`));

  const byDay = new Map();
  events.forEach((p) => {
    const d = parseIso(p.fecha_iso);
    const day = d ? d.getDate() : null;
    if (day) {
      if (!byDay.has(day)) byDay.set(day, []);
      byDay.get(day).push(p);
    }
  });

  const isMobile = typeof window !== "undefined" && window.innerWidth <= 600;

  if (isMobile) {
    const list = el("div", { class: "cal-mobile-list" });
    const days = [...byDay.keys()].sort((a, b) => a - b);
    if (!days.length) list.append(el("div", { class: "muted" }, "Sin publicaciones este mes."));
    days.forEach((day) => {
      const dayEvents = byDay.get(day);
      const dayItem = el("div", { class: "cal-mobile-day" },
        el("div", { class: "cal-mobile-daynum" }, String(day))
      );
      const chips = el("div", { class: "chips" });
      dayEvents.forEach((ev) => chips.append(renderChip(ctx, ev, { stacked: true })));
      dayItem.append(chips);
      list.append(dayItem);
    });
    card.append(list);
    return card;
  }

  const table = el("table", { class: "cal-grid" });
  table.append(el("thead", {}, el("tr", {}, ...DIA_CORTOS.map((d) => el("th", {}, d)))));
  const first = new Date(year, month - 1, 1);
  const startDow = first.getDay();
  const daysIn = new Date(year, month, 0).getDate();
  const tb = el("tbody");
  let day = 1 - startDow;
  while (day <= daysIn) {
    const tr = el("tr", {});
    for (let i = 0; i < 7; i++, day++) {
      if (day < 1 || day > daysIn) { tr.append(el("td", { class: "cal-cell empty" })); continue; }
      const dayEvents = byDay.get(day) || [];
      const cell = el("td", { class: "cal-cell" });
      const num = el("div", { class: "cal-daynum" }, String(day));
      const chips = el("div", { class: "chips" });
      const visible = dayEvents.slice(0, 3);
      const hidden = dayEvents.slice(3);
      visible.forEach((ev) => chips.append(renderChip(ctx, ev)));
      if (hidden.length) {
        const more = el("div", { class: "cal-more", title: `${hidden.length} más` }, `+${hidden.length} más`);
        more.addEventListener("click", (evClick) => {
          evClick.stopPropagation();
          openCalDay(ctx, `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`, dayEvents);
        });
        chips.append(more);
      }
      cell.append(num, chips);
      tr.append(cell);
    }
    tb.append(tr);
  }
  table.append(tb);
  card.append(el("div", { class: "table-wrap", style: "max-height:none;border:none;overflow:visible" }, table));
  return card;
}

function renderChip(ctx, ev, { stacked = false } = {}) {
  const color = categoryColor(ctx, ev.categoria);
  const sigla = SIGLA[ev.clave] || ev.sigla || ev.clave;
  const chip = el("div", {
    class: "cal-chip",
    style: `background:${color};color:#fff`,
    title: `${ev.indicador} · ${ev.periodo_referencia}`,
  }, sigla);
  chip.addEventListener("click", (e) => { e.stopPropagation(); openCalEvent(ctx, ev); });
  return chip;
}

function drawCalTable(ctx, host) {
  let items = filterEvents(getEvents(ctx));
  items = sortTable(items, calState.sort);

  const table = el("table");
  const headers = ["Fecha", "Hora", "Indicador", "Producto", "Periodo", "Frecuencia", "Fuente", "Estatus", "Descargas"];
  const thead = el("thead", {}, el("tr", {},
    ...headers.map((h, i) => el("th", { class: "sortable", onclick: () => toggleSort(ctx, i) }, h))
  ));
  table.append(thead);

  const tb = el("tbody");
  items.forEach((c) => {
    const tr = el("tr", { class: "clickable" });
    tr.append(
      el("td", {}, c.fecha_publicacion || "—"),
      el("td", {}, "—"),
      el("td", {}, SIGLA[c.clave] || c.clave || "—"),
      el("td", {}, c.producto || "—"),
      el("td", {}, c.periodo_referencia || "—"),
      el("td", {}, c.frecuencia || "—"),
      el("td", {}, shortSource(c) || c.institucion || "—"),
      el("td", {}, statusChip(c.estatus)),
      el("td", {}, deliverableBar(c.deliverables))
    );
    tr.addEventListener("click", () => openCalEvent(ctx, c));
    tb.append(tr);
  });
  table.append(tb);
  host.append(el("div", { class: "panel", style: "padding:0;overflow:hidden" },
    el("div", { class: "table-wrap", style: "max-height:none;border:none" }, table)
  ));
}

const SORT_COLS = ["fecha", "hora", "indicador", "producto", "periodo", "frecuencia", "fuente", "estatus", "descargas"];

function sortTable(items, sort) {
  const col = sort.col;
  const dir = sort.dir;
  const sorted = [...items];
  sorted.sort((a, b) => {
    let av, bv;
    switch (col) {
      case "fecha":
        av = a.fecha_iso || ""; bv = b.fecha_iso || ""; break;
      case "indicador":
        av = SIGLA[a.clave] || a.clave; bv = SIGLA[b.clave] || b.clave; break;
      case "estatus":
        av = a.estatus; bv = b.estatus; break;
      case "producto":
        av = a.producto; bv = b.producto; break;
      case "periodo":
        av = a.periodo_referencia; bv = b.periodo_referencia; break;
      case "frecuencia":
        av = a.frecuencia; bv = b.frecuencia; break;
      case "fuente":
        av = shortSource(a) || a.institucion; bv = shortSource(b) || b.institucion; break;
      default:
        av = a.fecha_iso || ""; bv = b.fecha_iso || "";
    }
    if (av == null) av = "";
    if (bv == null) bv = "";
    const cmp = String(av).localeCompare(String(bv), "es");
    return cmp * dir;
  });
  return sorted;
}

function toggleSort(ctx, index) {
  const col = SORT_COLS[index] || "fecha";
  if (calState.sort.col === col) calState.sort.dir *= -1;
  else calState.sort = { col, dir: 1 };
  drawCalBody(ctx);
}

// ---------- Modales ----------
function openCalEvent(ctx, ev) {
  const title = `${ev.producto} · ${ev.fecha_publicacion || displayDate(ev.fecha_iso)}`;
  const wrap = el("div", { class: "cal-event-modal" });

  wrap.append(el("h3", {}, ev.indicador));

  const meta = el("div", { class: "cal-event-meta" });
  [
    ["Indicador", ev.clave],
    ["Programa", ev.program],
    ["Periodo", ev.periodo_referencia],
    ["Frecuencia", ev.frecuencia],
    ["Fuente", shortSource(ev) || ev.source],
    ["Institución", ev.institucion],
    ["Categoría", ev.categoria],
    ["Estatus", statusChip(ev.estatus)],
  ].forEach(([k, v]) => meta.append(el("div", {}, el("strong", {}, `${k}:`), " ", v || "—")));
  wrap.append(meta);

  if (ev.deliverables && ev.deliverables.length) {
    wrap.append(el("h3", {}, "Descargas"));
    const actions = el("div", { class: "cal-event-actions" });
    ev.deliverables.forEach((d) => actions.append(deliverableBtn(d)));
    wrap.append(actions);
  }

  if (ev.comentario) {
    wrap.append(el("h3", {}, "Notas"));
    wrap.append(el("p", {}, ev.comentario));
  }

  const ind = ctx.getInd(ev.clave);
  if (ind) {
    wrap.append(el("button", {
      class: "btn btn-primary",
      type: "button",
      onclick: () => { ctx.closeModal(); ctx.setView(ev.clave); },
    }, "Ver ficha del indicador"));
  }

  ctx.openModal(title, wrap);
}

function openCalDay(ctx, iso, events) {
  const d = parseIso(iso);
  const title = `Publicaciones del ${displayDate(iso)}`;
  const wrap = el("div", { class: "cal-event-modal" });
  const list = el("div", {});
  events.forEach((ev) => {
    const row = el("div", { class: "cal-list-row clickable" },
      statusChip(ev.estatus),
      el("span", {}, `${ev.indicador} · ${ev.periodo_referencia} · ${ev.institucion}`)
    );
    row.addEventListener("click", () => openCalEvent(ctx, ev));
    list.append(row);
  });
  wrap.append(list);
  ctx.openModal(title, wrap);
}

// Helper local `el` para no depender de ctx.el cuando no se pasa
function el(tag, attrs = {}, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") n.className = v;
    else if (k === "html") n.innerHTML = v;
    else if (k.startsWith("on") && typeof v === "function") n.addEventListener(k.slice(2), v);
    else if (v !== null && v !== undefined) n.setAttribute(k, v);
  }
  for (const kid of kids) { if (kid == null) continue; n.append(kid.nodeType ? kid : document.createTextNode(kid)); }
  return n;
}
