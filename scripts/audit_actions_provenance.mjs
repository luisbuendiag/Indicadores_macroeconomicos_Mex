import {readFileSync} from 'node:fs';
import {pathToFileURL} from 'node:url';
import {assessHealth} from '../assets/js/update_health.mjs';

const repo = 'luisbuendiag/Indicadores_macroeconomicos_Mex';
const base = `https://github.com/${repo}/actions/runs/`;
const inputDate = x => typeof x === 'string' && /(?:Z|[+-]\d\d:\d\d)$/.test(x) && Number.isFinite(Date.parse(x));

export function joinEvidence(report, runs, health, policy, checkedAt) {
  if (report?.repository !== repo || !inputDate(checkedAt) || !Array.isArray(report.runs) || !Array.isArray(runs)) {
    throw Error('Repositorio, metadatos o momento inválido');
  }
  const byId = new Map();
  for (const r of runs) {
    if (!Number.isSafeInteger(r.id) || byId.has(r.id)) throw Error('ID omitido o duplicado');
    byId.set(r.id, r);
  }
  const seen = new Set();
  const linked = report.runs.map(r => {
    if (!Number.isSafeInteger(r?.run_id) || seen.has(r.run_id)) throw Error('Corrida inválida o duplicada en informe');
    seen.add(r.run_id);
    const witness = byId.get(r.run_id);
    if (!witness || !inputDate(witness.updated_at) || !inputDate(r.finished_at) ||
        Date.parse(witness.updated_at) !== Date.parse(r.finished_at) ||
        Date.parse(r.finished_at) > Date.parse(checkedAt) ||
        witness.path !== r.workflow || witness.conclusion !== r.outcome ||
        witness.status !== 'completed' || witness.run_attempt !== r.attempts ||
        !/^[0-9a-f]{40}$/.test(witness.head_sha ?? '')) throw Error(`Procedencia sin verificar: ${r.run_id}`);
    return {...r, head_sha: witness.head_sha, run_url: base + r.run_id};
  });
  const healthRun = linked.find(r => r.run_url === health?.run_url &&
    r.workflow === '.github/workflows/update-data.yml' &&
    inputDate(health.data_checked_at) && inputDate(health.checked_at) &&
    Date.parse(health.data_checked_at) <= Date.parse(health.checked_at) &&
    Date.parse(health.checked_at) <= Date.parse(r.finished_at));
  if (!healthRun) throw Error('Salud sin corrida institucional vinculada');
  const freshness = assessHealth(health, policy, new Date(checkedAt));
  return {repository: repo, observed_at: checkedAt, runs: linked, data_freshness: {
    run_id: healthRun.run_id, head_sha: healthRun.head_sha, data_checked_at: health.data_checked_at,
    expected_slot: freshness.slot, state: freshness.slot === null ? 'not_scheduled' : freshness.stale ? 'stale' :
      freshness.message ? 'pending' : 'current', pending_data: freshness.data,
    pending_notes: freshness.notes, message: freshness.message,
  }};
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const [report, witness, health, policy] = process.argv.slice(2, 6)
    .map(p => JSON.parse(readFileSync(p, 'utf8')));
  console.log(JSON.stringify(joinEvidence(report, witness.runs, health, policy, process.argv[6]), null, 2));
}
