import test from "node:test";
import assert from "node:assert/strict";
import { applyWindow, buildOption } from "../assets/js/charts.js";

const obs = (period, value) => ({ period, values: [value] });
const tasa = {
  key: "TASA",
  last_observation: "2026-02-28",
  windows: [{ id: "1a", count: 252 }, { id: "5a", count: 1260 }, { id: "max" }],
  regimen: [obs("2020-01-20", 4), obs("2022-06-24", 7.75), obs("2026-02-05", 7)],
};

test("TASA recorta por fecha y mantiene el nivel vigente en los extremos", () => {
  assert.deepEqual(applyWindow(tasa, "5a"), [
    obs("2021-02-28", 4), ...tasa.regimen.slice(1), obs("2026-02-28", 7),
  ]);
  assert.deepEqual(applyWindow(tasa, "1a"), [
    obs("2025-02-28", 7.75), tasa.regimen[2], obs("2026-02-28", 7),
  ]);
  assert.deepEqual(applyWindow(tasa, "max"), [...tasa.regimen, obs("2026-02-28", 7)]);
  assert.equal(tasa.regimen.length, 3);
});

test("TASA muestra un tramo plano cuando no hubo cambios en la ventana", () => {
  assert.deepEqual(applyWindow({ ...tasa, regimen: tasa.regimen.slice(0, 2) }, "1a"), [
    obs("2025-02-28", 7.75), obs("2026-02-28", 7.75),
  ]);
});

test("TASA respeta el límite del historial y el aniversario bisiesto", () => {
  const leap = { ...tasa, last_observation: "2024-02-29" };
  assert.equal(applyWindow(leap, "5a")[0].period, "2020-01-20");
  assert.equal(applyWindow(leap, "1a")[0].period, "2023-02-28");
  const exact = { ...tasa, regimen: [...tasa.regimen.slice(0, 2), obs("2025-02-28", 7.5), tasa.regimen[2]] };
  assert.deepEqual(applyWindow(exact, "1a"), [
    obs("2025-02-28", 7.5), tasa.regimen[2], obs("2026-02-28", 7),
  ]);
});

test("TASA se limita a la fecha de México y omite cambios con vigencia futura", () => {
  const today = new Intl.DateTimeFormat("sv-SE", { timeZone: "America/Mexico_City" }).format();
  assert.deepEqual(applyWindow({
    ...tasa,
    last_observation: "2099-01-02",
    regimen: [...tasa.regimen, obs("2099-01-02", 20)],
  }, "max"), [...tasa.regimen, obs(today, 7)]);
});

test("La gráfica TASA usa fechas proporcionales y cambia de nivel en la fecha efectiva", () => {
  const option = buildOption(tasa, "5a");
  const series = option.series[0];
  assert.equal(option.xAxis.type, "time");
  assert.equal(series.step, "end");
  assert.deepEqual(series.data[0], [Date.parse("2021-02-28"), 4]);
  assert.deepEqual(series.data.at(-1), [Date.parse("2026-02-28"), 7]);
  const detail = option.tooltip.formatter([{ marker: "", seriesName: series.name, value: series.data[1] }]);
  assert.match(detail, /2022-06-24/);
  assert.match(detail, /7\.75%/);
});

test("El conteo de otras series diarias se conserva", () => {
  const fix = { key: "TIPOCAMBIO", windows: [{ id: "1a", count: 2 }], observations: tasa.regimen };
  assert.deepEqual(applyWindow(fix, "1a"), tasa.regimen.slice(-2));
});
