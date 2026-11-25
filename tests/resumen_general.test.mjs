import test from "node:test";
import assert from "node:assert/strict";
import { PRINCIPAL } from "../assets/js/config.js";
import { computeKPI } from "../assets/js/metrics.js";
import { buildResumen } from "../assets/js/resumen-general.mjs";

const ind = (key, rows, frecuencia = "Mensual") => ({
  key, frecuencia, observations: rows.map(([period, values]) => ({ period, values })),
});

test("Resumen usa los mismos movimientos y clasificaciones de las fichas", () => {
  const indicators = {
    SIC: ind("SIC", [
      ["Jun 26", [99.9, 100.5, 0.08, null, 0.08]], ["Jul 26", [100.05, 100.6, 0.15, null, 0.06]],
      ["Ago 26", [100.17, 100.7, 0.12, null, 0.04]], ["Sep 26", [null, 100.71, null, null, 0.01]],
    ]),
    DESOCUP: ind("DESOCUP", [["Ago 25", [3.1]], ["Sep 25", [3.0]], ["Oct 25", [2.82]],
      ["Ago 26", [3.05]], ["Sep 26", [2.8]], ["Oct 26", [2.82]]]),
    INPC: ind("INPC", [["Sep 26", [146, 0.42, 3.45]], ["Oct 26", [147, 0.65, 3.75]]]),
    PIBSEC: ind("PIBSEC", [["3T-26", [900000, 8000000, 16000000, 0.02, 0.03, 26000000, 0.02, 0.033]]], "Trimestral"),
    EMOE: ind("EMOE", [["Sep 26", [48.33, 0.10]], ["Oct 26", [48.18, -0.15]]]),
    BCMM: ind("BCMM", [["Sep 26", [77797, 78403, -606, 0.379, 0.331]]]),
  };
  const model = buildResumen(indicators);
  const rows = model.groups.flatMap((group) => group.rows);
  assert.deepEqual(rows.map((row) => row.key).sort(), [...PRINCIPAL].sort());
  const kpiFor = (key, month) => rows.find((row) => row.key === key).cells.get(2026 * 12 + month - 1);
  for (const [key, cutoff, month] of [["SIC", 3, 8], ["DESOCUP", 5, 9], ["INPC", 2, 10], ["EMOE", 2, 10], ["BCMM", 1, 9]]) {
    const indicator = indicators[key];
    const onDate = computeKPI({ ...indicator, observations: indicator.observations.slice(0, cutoff) });
    const cell = kpiFor(key, month);
    assert.equal(cell.varText, onDate.varText, key);
    assert.equal(cell.assessment, onDate.assessment, key);
  }
  assert.equal(kpiFor("SIC", 9), undefined, "un mes con solo Adelantado no tiene movimiento Coincidente");
  assert.equal(kpiFor("PIBSEC", 9).ultimoP, "3T-26");
  assert.equal(kpiFor("PIBSEC", 8), undefined);
  assert.equal(rows.find((row) => row.key === "PIBSEC").quarterly, true);
  assert.deepEqual(model.counts, { favorable: 2, adverso: 0, neutral: 4 });
  assert.equal(model.months.at(-1), 2026 * 12 + 9);
  assert.equal(model.months.length, 12);
  assert.equal(model.cycle.currentPhase, "expansion");
  assert.equal(model.cycle.duration, 2);
  assert.equal(model.cycle.current.period, "Ago 26");
  assert.equal(model.cycle.leading.period, "Sep 26");
  assert.equal(model.cycle.smallerLeadingGains, true);
});

test("Resumen conserva la estructura con indicadores ausentes", () => {
  const model = buildResumen({});
  assert.deepEqual(model.months, []);
  assert.deepEqual(model.counts, { favorable: 0, adverso: 0, neutral: 0 });
  assert.deepEqual(model.cycle.coincident, []);
  assert.equal(model.cycle.leading, undefined);
  assert.equal(model.groups.flatMap((g) => g.rows).length, PRINCIPAL.length);
});

test("ENOE presenta el cambio anual original y reserva el mensual para la serie ajustada", () => {
  const indicator = ind("DESOCUP", [
    ["Sep 25", [3.0, 59.6, 54.9, 7.3]],
    ["Abr 26", [3.0, 59.0, 55, 7, 60.04, 60040094]],
    ["Ago 26", [3.0, 59.4, 55.1, 7.5]],
    ["Sep 26", [2.8, 58.5, 54.3, 6.7]],
  ]);
  const before = computeKPI(indicator);
  assert.equal(before.varRaw, -0.2);
  assert.equal(before.cards[0].momRaw, null);
  assert.equal(before.poblacion, null);

  indicator.enoe_mensual = {periodo: "Sep 26", ocupados: 59977049,
    tasas: {unemployment: {nivel_desest: 2.6, mensual_desest_pp: -0.1, anual_original_pp: -0.1}}};
  const after = computeKPI(indicator);
  assert.equal(after.ultimoRaw, 2.8);
  assert.equal(after.varLabel, "Cambio anual original");
  assert.equal(after.varRaw, -0.1);
  assert.equal(after.cards[0].momRaw, -0.1);
  assert.equal(after.cards[0].nivelDesest, 2.6);
  assert.equal(after.poblacion.personas, 59977049);
  assert.equal(after.poblacion.frecuencia, "mensual");

  const earlier = computeKPI({...indicator, observations: indicator.observations.slice(0, 3)});
  assert.equal(earlier.cards[0].momRaw, null);
  assert.equal(earlier.poblacion, null);
});
