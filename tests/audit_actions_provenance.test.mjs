import {test} from 'node:test';
import assert from 'node:assert/strict';
import {joinEvidence} from '../scripts/audit_actions_provenance.mjs';
const repository='luisbuendiag/Indicadores_macroeconomicos_Mex';
const workflow='.github/workflows/update-data.yml';
const sha='abcde12345'.repeat(4);
const receipt={run_url:'https://github.com/'+repository+'/actions/runs/1',
  data_checked_at:'2026-11-27T07:25:00Z',checked_at:'2026-11-27T07:30:00Z'};
const policy={utc_hours:[7,13],minute:17,grace_minutes:10};
const now='2026-11-27T08:00:00Z';
const sample={run_id:1,workflow,outcome:'success',attempts:1,finished_at:'2026-11-27T07:35:00Z'};
const report={repository,runs:[sample]};
const witness={id:1,updated_at:sample.finished_at,path:workflow,head_sha:sha,
  conclusion:'success',status:'completed',run_attempt:1};
test('current data and provenance have explicit evidence', () => {
  const x=joinEvidence(report,[witness],receipt,policy,now);
  assert.equal(x.runs[0].head_sha,sha);
  assert.equal(x.data_freshness.state,'current');
  assert.equal(x.data_freshness.expected_slot,'2026-11-27T07:17:00.000Z');
});
test('a green run does not keep data current after another cut', () => {
  const x=joinEvidence(report,[witness],receipt,policy,'2026-11-27T14:00:00Z');
  assert.equal(x.runs[0].outcome,'success');
  assert.equal(x.data_freshness.state,'stale');
});
test('wrong run, attempt, time and SHA fail closed', () => {
  for(const bad of [{id:2},{run_attempt:2},{updated_at:'2026-11-27T07:34:00Z'},{head_sha:sha.slice(1)}])
    assert.throws(()=>joinEvidence(report,[{...witness,...bad}],receipt,policy,now),/Procedencia no|Procedencia sin/);
});
test('unrelated health and future health fail closed', () => {
  for(const bad of [{checked_at:'2026-11-27T08:00:01Z'},{run_url:receipt.run_url+'2'}])
    assert.throws(()=>joinEvidence(report,[witness],{...receipt,...bad},policy,now),/Salud sin corrida/);
});
test('invalid repository and duplicate runs fail closed', () => {
  assert.throws(()=>joinEvidence({...report,repository:'otro/proyecto'},[witness],receipt,policy,now),/Repositorio/);
  assert.throws(()=>joinEvidence({...report,runs:[sample,sample]},[witness],receipt,policy,now),/duplicada/);
});
