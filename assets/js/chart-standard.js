/* F-014 · Gráficas (docs/coordination/F-014_especificacion.md y F-014_revision_fichas.md), versión 3; incluye el arreglo F-018 de series diarias.
   Respeta los colores originales del sitio (verde/guinda/dorado) y aplica:
   - mejoras de estructura en todas: años sin girar, ejes con números redondos, ventana inicial de 5 años;
   - ajustes puntuales por indicador (AJUSTES), decididos ficha por ficha.
   No cambia datos ni cálculos. Para revertir, quitar su <script> de index.html. */
(function () {
  "use strict";
  if (!window.echarts || window.echarts.__f014) return;

  var VERDE = "#1E5B4F", GUINDA = "#9B2247", DORADO = "#A57F2C", GRIS = "#8A8A8A", AZUL = "#5B7186", TEXTO = "#545454";
  function arr(x) { return x == null ? [] : (Array.isArray(x) ? x : [x]); }
  function pct(v) { var m = /^(-?\d+(?:\.\d+)?)%$/.exec(String(v == null ? "" : v).trim()); return m ? +m[1] : null; }

  // Año a partir de etiquetas "Ene 18", "1T-15 P", "2018-01", "2018-01-02".
  function yearOf(lbl) {
    var s = String(lbl == null ? "" : lbl), m;
    if ((m = s.match(/^(\d{4})-\d{2}/))) return +m[1];
    if ((m = s.match(/^[1-4]T-(\d{2})/))) return 2000 + (+m[1] > 70 ? +m[1] - 100 : +m[1]);
    if ((m = s.match(/^[A-Za-zÁÉÍÓÚáéíóú]{3}\.?\s+(\d{2})\b/))) return 2000 + (+m[1] > 70 ? +m[1] - 100 : +m[1]);
    if ((m = s.match(/^(\d{4})$/))) return +m[1];
    return null;
  }
  function inicioAnio(v) { return /^(Ene|1T-|\d{4}-01)/.test(String(v)) || /^\d{4}$/.test(String(v)); }

  function fixXAxis(ax) {
    if (!ax || ax.type === "value" || ax.type === "time") return;
    var data = arr(ax.data).map(function (d) { return d && typeof d === "object" ? d.value : d; });
    ax.axisLabel = Object.assign({}, ax.axisLabel, { rotate: 0, hideOverlap: true, color: TEXTO });
    if (data.length < 2) return;
    var years = data.map(yearOf);
    if (years.some(function (y) { return y == null; })) return;
    var span = years[years.length - 1] - years[0];
    if (span < 2) return; // un año o menos: etiquetas de periodo, sin girar
    var step = Math.max(1, Math.ceil((span + 1) / 8));
    var show = years.map(function (y, i) { return (i === 0 ? inicioAnio(data[0]) : y !== years[i - 1]) && (y % step === 0); });
    ax.axisLabel.interval = function (i) { return !!show[i]; };
    ax.axisLabel.formatter = function (v) { var y = yearOf(v); return y == null ? "" : String(y); };
    ax.axisTick = Object.assign({}, ax.axisTick, { alignWithLabel: true, interval: function (i) { return !!show[i]; } });
  }

  // Eje Y con pasos 1-2-5 calculados de los datos visibles (incluye líneas de referencia como 0, 50 o 100).
  function paso(r) { if (!(r > 0)) return 1; var raw = r / 4, mag = Math.pow(10, Math.floor(Math.log10(raw))), n = raw / mag; return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * mag; }
  function valor(d) { if (d && typeof d === "object" && !Array.isArray(d)) d = d.value; if (Array.isArray(d)) d = d[d.length - 1]; if (d == null || d === "" || d === "-") return null; d = +d; return isFinite(d) ? d : null; }
  function fixYAxes(opt) {
    var axes = arr(opt.yAxis), vals = axes.map(function () { return []; });
    var oculto = {};
    arr(opt.legend).forEach(function (lg) { for (var k in (lg.selected || {})) if (lg.selected[k] === false) oculto[k] = true; });
    arr(opt.series).forEach(function (s) {
      var i = s.yAxisIndex || 0; if (!vals[i] || oculto[s.name]) return;
      arr(s.data).forEach(function (d) { var v = valor(d); if (v != null) vals[i].push(v); });
      if (s.markLine) arr(s.markLine.data).forEach(function (d) { var v = d && d.yAxis != null ? +d.yAxis : null; if (v != null && isFinite(v)) vals[i].push(v); });
    });
    axes.forEach(function (ax, i) {
      if (!ax || (ax.type && ax.type !== "value")) return;
      ax.axisLabel = Object.assign({}, ax.axisLabel, { color: TEXTO, showMinLabel: true, showMaxLabel: true });
      var v = vals[i];
      if (!v || !v.length) { if (axes.length > 1 && !arr(opt.grid)[1]) ax.show = false; return; } // eje cuyas series están apagadas
      if (v.length < 2) return;
      var lo = Math.min.apply(null, v), hi = Math.max.apply(null, v);
      if (ax.min === 0 && lo > 0) lo = 0;
      if (lo === hi) { lo -= 1; hi += 1; }
      var st = paso(hi - lo), mn = Math.floor(lo / st) * st, mx = Math.ceil(hi / st) * st;
      if (mx - mn < st * 2) mx = mn + st * 2;
      ax.min = +mn.toFixed(10); ax.max = +mx.toFixed(10); ax.interval = +st.toFixed(10); ax.scale = false;
      delete ax.splitNumber;
    });
  }

  // Títulos de paneles centrados sobre su panel y más legibles.
  function centerTitles(opt) {
    var grids = arr(opt.grid), titles = arr(opt.title);
    if (grids.length < 2 || !titles.length) return;
    var conLeyenda = arr(opt.legend).some(function (lg) { return lg && lg.show !== false; });
    if (conLeyenda) return; // con leyenda arriba, centrar los títulos los encima (caso BCMM)
    titles.forEach(function (t, i) {
      var g = grids[i]; if (!t || !g) return;
      var l = pct(g.left), w = pct(g.width), r = pct(g.right), c = null;
      if (l != null && w != null) c = l + w / 2; else if (l != null && r != null) c = (l + 100 - r) / 2;
      if (c != null) { t.left = c + "%"; t.textAlign = "center"; }
      t.textStyle = Object.assign({}, t.textStyle, { fontSize: 14, fontWeight: 600, color: "#161A1D" });
    });
  }

  function colorPorNombre(opt, mapa) {
    arr(opt.series).forEach(function (s) {
      for (var patron in mapa) {
        if (new RegExp(patron, "i").test(s.name || "")) {
          var c = mapa[patron];
          s.itemStyle = Object.assign({}, s.itemStyle, { color: c });
          if (s.type === "line") s.lineStyle = Object.assign({}, s.lineStyle, { color: c });
          break;
        }
      }
    });
  }
  function ocultar(opt, patron) {
    var sel = {};
    arr(opt.series).forEach(function (s) { if (s.name && new RegExp(patron, "i").test(s.name)) sel[s.name] = false; });
    arr(opt.legend).forEach(function (lg) { lg.selected = Object.assign({}, lg.selected, sel); });
    if (!opt.legend) opt.legend = { selected: sel };
  }

  // Ajustes puntuales por indicador (clave = id de la vista, p. ej. "PIBSEC").
  var AJUSTES = {
    PIBSEC: function (opt) {
      // Cuatro series por trimestre: cada actividad con su propio color.
      colorPorNombre(opt, { "^PIB": VERDE, "Primarias": DORADO, "Secundarias": GUINDA, "Terciarias": AZUL });
    },
    SIC: function (opt) {
      colorPorNombre(opt, { "Coincidente": VERDE, "Adelantado": GUINDA });
    },
    IGAE: function (opt) {
      if (arr(opt.grid).length > 1) return; // paneles de niveles: se quedan como están
      // Barras de variación: 4 series × 60 meses no se leen juntas. Se ve el IGAE total; las actividades, en la leyenda.
      colorPorNombre(opt, { "^IGAE": VERDE, "Primarias": DORADO, "Secundarias": GUINDA, "Terciarias": AZUL });
      ocultar(opt, "^(Primarias|Secundarias|Terciarias)$");
    },
    IMAI: function (opt) {
      if (!arr(opt.series).some(function (s) { return s.type === "bar"; })) return;
      colorPorNombre(opt, { "^IMAI": VERDE, "Miner": DORADO, "Energ": AZUL, "Construcci": GUINDA, "Manufact": GRIS });
      ocultar(opt, "^(Minería|Energía|Construcción|Manufacturas)$");
    },
    IMFBCF: function (opt) {
      if (!arr(opt.series).some(function (s) { return s.type === "bar"; })) return;
      colorPorNombre(opt, { "^IMFBCF": VERDE, "^Construcci": GUINDA, "^Maquinaria": DORADO, "Residencial": AZUL, "Importado": GRIS });
      ocultar(opt, "^(Construcción|Maquinaria y equipo|Residencial|No residencial|Importado)$");
    },
    EMIM: function (opt) {
      if (!arr(opt.series).some(function (s) { return s.type === "bar"; })) return;
      // Producción (barras) y su serie desestacionalizada (línea); el resto, en la leyenda.
      colorPorNombre(opt, { "^Producción \\(desest": GUINDA, "^Producción": VERDE });
      ocultar(opt, "Personal|Horas|Remuneraciones");
      // F-015 · La serie desestacionalizada solo trae el mes más reciente (sale del boletín); con menos de
      // 12 puntos se oculta para no dibujar un punto suelto. Vuelve sola cuando el proceso cargue el histórico.
      arr(opt.series).forEach(function (s) {
        if (!/^Producción \(desest/.test(s.name || "")) return;
        var n = arr(s.data).filter(function (x) { return valor(x) !== null; }).length;
        if (n < 12) ocultar(opt, "^Producción \\(desest");
      });
    },
    IMOAM: function (opt) {
      colorPorNombre(opt, { "^Índice estimado": VERDE, "IC95": "#9AA39D", "^Var\\. anual": GUINDA });
      ocultar(opt, "anual");
    },
    CONSUMO: function (opt) {
      colorPorNombre(opt, { "volumen": VERDE, "anual": DORADO });
      ocultar(opt, "mensual|Acumulado");
    },
    INPC: function (opt) {
      var general = arr(opt.series).filter(function (s) { return /Inflación general/i.test(s.name || ""); })[0];
      if (!general) return;
      general.markArea = { silent: true, itemStyle: { color: "rgba(71,116,91,0.08)" }, label: { show: true, position: "insideTopRight", color: TEXTO, fontSize: 11, formatter: "Meta Banxico 3 % ± 1" }, data: [[{ yAxis: 2 }, { yAxis: 4 }]] };
    },
    TASA: function (opt) {
      // La tasa cambia por decisión: se dibuja en escalones, no como pendiente.
      arr(opt.series).forEach(function (s) { if (s.type === "line") { s.step = "end"; delete s.markLine; } }); // la línea en 0 % no aporta y aplastaba la escala
      arr(opt.yAxis).forEach(function (a) { if (a && a.min === 0) delete a.min; }); // 0 % comprimía la trayectoria
    },
    IOAE: function (opt) {
      // De 7 líneas a lo esencial: nowcast del IGAE, su intervalo y el IGAE observado. El resto queda en la leyenda.
      colorPorNombre(opt, { "Nowcast anual IGAE": VERDE, "IC 95": "#9AA39D", "IGAE observado": GUINDA });
      ocultar(opt, "secundarias|terciarias|mensual");
    }
  };

  function vistaDe(dom) {
    var v = dom && dom.closest && dom.closest('[id^="view-"]');
    return v ? v.id.replace(/^view-/, "") : "";
  }

  function normalize(opt, vista) {
    if (!opt || typeof opt !== "object" || !arr(opt.series).length) return opt;
    arr(opt.series).forEach(function (s) { if (s && s.type === "line") s.smooth = false; });
    if (AJUSTES[vista]) AJUSTES[vista](opt);
    arr(opt.xAxis).forEach(fixXAxis);
    fixYAxes(opt);
    centerTitles(opt);
    return opt;
  }

  var origInit = window.echarts.init;
  window.echarts.init = function (dom) {
    var chart = origInit.apply(this, arguments);
    var origSet = chart.setOption;
    chart.setOption = function (opt) {
      try { normalize(opt, vistaDe(dom)); } catch (e) { if (window.console) console.warn("F-014: opción sin normalizar", e); }
      return origSet.apply(this, arguments);
    };
    return chart;
  };
  window.echarts.__f014 = true;

  // F-015 · Correcciones de datos de cabecera mientras se corrige el proceso (ver tablero).
  var MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
  function fechaES(txt) {
    var m = /^(\d{1,2}) de ([a-záéíóú]+) de (\d{4})$/i.exec(String(txt || "").trim());
    if (!m) return null;
    var mes = MESES.indexOf(m[2].toLowerCase());
    return mes < 0 ? null : new Date(+m[3], mes, +m[1]);
  }
  function corregirCabeceras(d) {
    try {
      var I = (d && d.indicators) || {}, gen = d && d.meta && d.meta.generated_at;
      var hoy = gen ? new Date(String(gen).slice(0, 10) + "T00:00:00") : new Date();
      Object.keys(I).forEach(function (k) {
        var ind = I[k];
        // Próxima publicación ya pasada: se descarta y la ficha usa el calendario (salvaguarda general; el PIB ya llega bien desde el PR #49).
        var np = ind.proxima_publicacion, f = np && fechaES(np.fecha_publicacion);
        if (f && f < hoy) delete ind.proxima_publicacion;
        // Fecha de publicación en formato ISO (SIC: "2026-11-04") → "4 de noviembre de 2026".
        var iso = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(ind.fecha_publicacion || ""));
        if (iso) ind.fecha_publicacion = (+iso[3]) + " de " + MESES[+iso[2] - 1] + " de " + iso[1];
      });
      // F-019 · Acentos en el nombre de la tasa ("Tasa de Interes Interbancaria a un dia").
      if (I.TASA && I.TASA.nombre) I.TASA.nombre = String(I.TASA.nombre).replace(/\bInteres\b/g, "Interés").replace(/\bdia\b/g, "día");
      // SIC: el periodo de la cabecera debe ser el último dato de cada indicador (Coincidente y Adelantado).
      var S = I.SIC;
      if (S && S.observations && S.columns) {
        var col = function (re) { var c = arr(S.columns).filter(function (c) { return re.test(c.label || ""); })[0]; return c ? c.index : -1; };
        var ultimo = function (j) {
          if (j < 0) return null;
          for (var i = S.observations.length - 1; i >= 0; i--) { var v = arr(S.observations[i].values)[j]; if (v !== null && v !== undefined) return S.observations[i].label || S.observations[i].period; }
          return null;
        };
        var c = ultimo(col(/^Indicador Coincidente/)), a = ultimo(col(/^Indicador Adelantado/));
        if (c && a) S.periodo_referencia = c === a ? c : c + " · " + a;
      }
    } catch (e) { if (window.console) console.warn("F-015: no se corrigieron las cabeceras", e); }
    return d;
  }

  if (window.fetch) {
    var origFetch = window.fetch;
    window.fetch = function (input) {
      var url = typeof input === "string" ? input : (input && input.url) || "";
      var p = origFetch.apply(window, arguments);
      if (!/data\/indicadores\.json(\?|$)/.test(url)) return p;
      return p.then(function (r) { var j = r.json.bind(r); r.json = function () { return j().then(corregirCabeceras); }; return r; });
    };
  }

  // Ventana inicial de 5 años (una vez por indicador; después manda el usuario).
  var hechos = {};
  function ventanaInicial() {
    document.querySelectorAll('.win-btn[data-win-id="5a"]').forEach(function (b) {
      var ind = b.getAttribute("data-ind"), tipo = b.getAttribute("data-tipo") || "";
      if (!ind || tipo || ind === "IED" || hechos[ind]) return;
      var activo = b.parentElement && b.parentElement.querySelector('.win-btn[aria-pressed="true"]');
      hechos[ind] = true;
      if (activo && activo.getAttribute("data-win-id") === "max") setTimeout(function () { b.click(); }, 0);
    });
  }
  function arrancar() {
    ventanaInicial();
    new MutationObserver(ventanaInicial).observe(document.body, { childList: true, subtree: true });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", arrancar);
  else arrancar();
})();
