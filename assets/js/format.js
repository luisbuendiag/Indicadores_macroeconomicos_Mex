// Utilidades de formato compartidas (es-MX). Módulo ES.
export const MESES = {
  ene: "enero", feb: "febrero", mar: "marzo", abr: "abril", may: "mayo",
  jun: "junio", jul: "julio", ago: "agosto", sep: "septiembre",
  oct: "octubre", nov: "noviembre", dic: "diciembre",
};
const ORD = { "1": "primer", "2": "segundo", "3": "tercer", "4": "cuarto" };

export function fmtVal(v, fmt) {
  if (v === null || v === undefined || (typeof v === "number" && isNaN(v))) return "—";
  switch (fmt) {
    case "num":
    case "usd":
      return Math.round(v).toLocaleString("es-MX");
    case "idx":
      return v.toLocaleString("es-MX", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
    case "fx":
      return "$" + v.toLocaleString("es-MX", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    case "pct-frac":
      return (v * 100).toLocaleString("es-MX", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + "%";
    case "pct-raw":
      return v.toLocaleString("es-MX", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + "%";
    default:
      return String(v);
  }
}

export function tick(v, kind) {
  if (kind === "pct") return (Math.round(v * 10) / 10).toLocaleString("es-MX") + "%";
  if (kind === "idx") return (Math.round(v * 10) / 10).toLocaleString("es-MX");
  if (kind === "compact") return v.toLocaleString("es-MX", { notation: "compact", maximumFractionDigits: 1 });
  return Math.round(v).toLocaleString("es-MX");
}

export function isTrim(p) { return /^[1-4]T-/.test(p || ""); }

export function perLong(p) {
  if (!p) return "";
  const q = p.match(/^([1-4])T-(\d{2})/);
  if (q) return `${ORD[q[1]]} trimestre de 20${q[2]}`;
  const mo = p.match(/^([A-Za-zÁÉÍÓÚáéíóú]{3})\s*(\d{2})/);
  if (mo) { const m = MESES[mo[1].toLowerCase()]; if (m) return `${m} de 20${mo[2]}`; }
  return p;
}

export function enFrase(p) { return (isTrim(p) ? "el " : "") + perLong(p); }
export function respFrase(p) { return (isTrim(p) ? "al " : "a ") + perLong(p); }

// Convierte un periodo a una fecha aproximada (para filtrar ventanas temporales).
export function periodToDate(p) {
  if (!p) return null;
  const q = p.match(/^([1-4])T-(\d{2})/);
  if (q) { const month = (parseInt(q[1], 10) - 1) * 3; return new Date(2000 + parseInt(q[2], 10), month, 1); }
  const mo = p.match(/^([A-Za-zÁÉÍÓÚáéíóú]{3})\s*(\d{2})/);
  if (mo) {
    const idx = Object.keys(MESES).indexOf(mo[1].toLowerCase());
    if (idx >= 0) return new Date(2000 + parseInt(mo[2], 10), idx, 1);
  }
  return null;
}
