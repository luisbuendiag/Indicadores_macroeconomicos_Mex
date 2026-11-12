import test from 'node:test';
import assert from 'node:assert/strict';
import {expectedSlot, assessHealth} from '../assets/js/update_health.mjs';
import {createRequire} from 'node:module';
import fs from 'node:fs';
const require = createRequire(import.meta.url);
const {watchdog, retryRead} = require('../scripts/update_watchdog.cjs');
const policy = JSON.parse(fs.readFileSync(new URL('../config/update_policy.json', import.meta.url)));
const date = s => new Date(s);

test('gracia, lunes y fin de semana conservan el corte hábil correcto', () => {
  assert.equal(expectedSlot(policy, date('2026-11-09T07:30:00Z')).toISOString(), '2026-11-06T19:17:00.000Z');
  assert.equal(expectedSlot(policy, date('2026-11-09T08:17:00Z')).toISOString(), '2026-11-09T07:17:00.000Z');
  assert.equal(expectedSlot(policy, date('2026-11-08T18:00:00Z')).toISOString(), '2026-11-06T19:17:00.000Z');
});

test('datos recientes no ocultan Word pendiente; fecha inválida nunca se considera vigente', () => {
  const now = date('2026-11-09T14:30:00Z');
  const result = assessHealth({data_checked_at:'2026-11-09T14:00:00Z', pending_notes:['INPC']}, policy, now);
  assert.equal(result.stale, false); assert.equal(result.recoverable, false);
  assert.match(result.message, /Notas pendientes: INPC/);
  assert.equal(assessHealth({}, policy, now).stale, true);
});

async function runWatchdog(t, {health, runs = [], repoHealth = health, conclusion = null}) {
  const calls = [];
  t.mock.method(fs, 'readFileSync', (original => (file, ...args) => file === 'data/update_health.json' ? JSON.stringify(repoHealth) : original(file, ...args))(fs.readFileSync));
  t.mock.method(globalThis, 'fetch', async () => ({ok:true, json:async () => health}));
  const github = {rest:{actions:{
    listWorkflowRuns:async ({workflow_id}) => ({data:{workflow_runs:workflow_id === 'update-data.yml' ? runs : []}}),
    createWorkflowDispatch:async args => calls.push(['dispatch', args])},
    }};
  const summary = {addHeading(){return this;}, addRaw(){return this;}, async write(){}};
  await watchdog({github, core:{summary,warning:message=>calls.push(['warning',message]),setFailed:message=>calls.push(['failure',message])}, context:{repo:{owner:'example',repo:'dashboard'}, payload:conclusion ? {workflow_run:{conclusion}} : {}}});
  return calls;
}
const fresh = () => ({data_checked_at:new Date().toISOString(), pending_data:[], pending_notes:[]});

test('watchdog no repite corrida activa y limita recuperaciones por corte', async t => {
  const stale = {data_checked_at:'2020-01-01T00:00:00Z'};
  const slot = expectedSlot(policy).toISOString();
  const calls = await runWatchdog(t, {health:stale, runs:[1,2].map(id => ({id,status:'completed',event:'workflow_dispatch',display_title:`Recuperación ${slot}`}))});
  assert.equal(calls.filter(x=>x[0]==='dispatch').length,0);
  assert.equal(calls.filter(x=>x[0]==='failure').length,1);
});
test('watchdog espera una ejecución activa', async t => {
  const calls = await runWatchdog(t, {health:{}, runs:[{status:'in_progress',created_at:new Date().toISOString()}]});
  assert.equal(calls.length,0);
});
test('publicación omitida recupera solo despliegue si el repositorio está al día', async t => {
  const calls = await runWatchdog(t, {health:{},repoHealth:fresh()});
  assert.equal(calls.find(x=>x[0]==='dispatch')[1].workflow_id,'deploy-pages.yml');
});
test('fuente desactualizada recupera el pipeline; Word pendiente solo alerta', async t => {
  const stale = {data_checked_at:'2020-01-01T00:00:00Z'};
  const calls = await runWatchdog(t, {health:stale});
  assert.equal(calls.find(x=>x[0]==='dispatch')[1].workflow_id,'update-data.yml');
});
test('Word con cambio de estructura no provoca bucle de reintentos', async t => {
  const calls = await runWatchdog(t, {health:{...fresh(),pending_notes:['INPC']}});
  assert.equal(calls.some(x=>x[0]==='dispatch'), false);
  assert.equal(calls.some(x=>x[0]==='warning'), true);
});
test('una consulta al corriente termina sin alertas', async t => {
  const calls = await runWatchdog(t, {health:fresh()});
  assert.equal(calls.length,0);
});

test('cola antigua superada por ejecución exitosa no genera alarma falsa', async t => {
  const now = Date.now();
  const runs = [
    {id: 1, workflow_id: 100, status:'queued',
      created_at:new Date(now-3*3600000).toISOString()},
    {id: 2, workflow_id: 100, status:'completed', conclusion:'success',
      created_at:new Date(now-40*60000).toISOString(),
      updated_at:new Date(now-10*60000).toISOString()},
  ];
  const calls = await runWatchdog(t, {health:fresh(),runs});
  assert.deepEqual(calls, []);
});

test('cola antigua sin éxito posterior sí requiere atención', async t => {
  const now = Date.now();
  const runs = [{id: 9, workflow_id:100, status:'queued',
    created_at:new Date(now-3*3600000).toISOString()}];
  const calls = await runWatchdog(t, {health:fresh(),runs});
  assert.equal(calls.some(row=>row[0] === 'failure'),true);
  assert.equal(calls.some(row=>row[0] === 'dispatch'),false);
});

test('la vigilancia reintenta lecturas de GitHub con error 500, sin repetir escrituras', async()=>{
 let calls=0;const result=await retryRead(async()=>{if(++calls===1)throw Object.assign(new Error('Server Error'),{status:500});return 'ok';},async()=>{});
 assert.equal(result,'ok');assert.equal(calls,2);
 calls=0;await assert.rejects(retryRead(async()=>{calls++;throw Object.assign(new Error('Forbidden'),{status:403});},async()=>{}));assert.equal(calls,1);
});
