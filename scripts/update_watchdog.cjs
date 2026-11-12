// Ejecutado solo desde main con GITHUB_TOKEN limitado al repositorio.
const fs = require('node:fs');
const {pathToFileURL} = require('node:url');
const path = require('node:path');

async function retryRead(read, wait = ms => new Promise(resolve => setTimeout(resolve, ms))) {
  for (let attempt = 0; attempt < 3; attempt++) {
    try { return await read(); }
    catch (error) {
      if (attempt === 2 || ![408,429,500,502,503,504].includes(error.status)) throw error;
      await wait(2000 * (attempt + 1));
    }
  }
}

async function readPublic(url) {
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      const res = await fetch(`${url}?health=${Date.now()}`, {signal: AbortSignal.timeout(20000)});
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (error) {
      if (attempt === 2) throw error;
      await new Promise(resolve => setTimeout(resolve, 2000 * (attempt + 1)));
    }
  }
}

// Una ejecución en cola puede quedar huérfana aunque otra ejecución del mismo
// workflow ya haya terminado correctamente. No bloquear recuperaciones por colas
// superadas; sí vigilar ejecuciones en progreso y colas sin sucesor exitoso.
function relevantActiveRuns(runs) {
  const key = run => run.workflow_id ?? run.path ?? null;
  return runs.filter(run => {
    if (run.status === 'completed') return false;
    if (!['queued', 'waiting', 'pending'].includes(run.status)) return true;
    const created = Date.parse(run.created_at);
    const identity = key(run);
    if (!identity || !Number.isFinite(created)) return true;
    const superseded = runs.some(other => {
      if (key(other) !== identity || other.conclusion !== 'success') return false;
      const done = Date.parse(other.updated_at);
      return Number.isFinite(done) && done > created;
    });
    return !superseded;
  });
}

async function watchdog({github, context, core}) {
  const policy = JSON.parse(fs.readFileSync('config/update_policy.json', 'utf8'));
  const {assessHealth} = await import(pathToFileURL(path.resolve('assets/js/update_health.mjs')));
  const repoHealth = JSON.parse(fs.readFileSync('data/update_health.json', 'utf8'));
  const base = `https://${context.repo.owner}.github.io/${context.repo.repo}`;
  let publicHealth;
  try { publicHealth = await readPublic(`${base}/data/update_health.json`); }
  catch { publicHealth = null; }
  const now = new Date();
  const check = assessHealth(publicHealth, policy, now);
  const source = assessHealth(repoHealth, policy, now);
  const summary = core.summary.addHeading('Vigilancia de actualizaciones');
  const runLists = await Promise.all(['update-data.yml', 'deploy-pages.yml'].map(workflow_id =>
    retryRead(() => github.rest.actions.listWorkflowRuns({...context.repo, workflow_id, branch: 'main', per_page: 100}))));
  const runs = runLists.flatMap(r => r.data.workflow_runs);
  const active = relevantActiveRuns(runs);
  // No competir con una corrida válida ni publicar encima de otra.
  const running = active.some(r => now - new Date(r.created_at) < policy.max_run_minutes * 60000);
  const stuck = active.some(r => now - new Date(r.created_at) >= policy.max_run_minutes * 60000);
  const problems = check.message || (stuck ? 'Una ejecución excedió el tiempo esperado.' : '');
  const failedEvent = context.payload.workflow_run && ['failure', 'timed_out'].includes(context.payload.workflow_run.conclusion);
  // Una publicación recién terminada puede tardar unos minutos en propagarse.
  const propagating = runs.some(r => r.conclusion === 'success' && now - new Date(r.updated_at) < 10 * 60000);
  if (!problems && !failedEvent) {
    await summary.addRaw('Consulta y productos al corriente.').write();
    return;
  }
  if (running || (check.stale && propagating && !failedEvent)) {
    await summary.addRaw('Actualización o propagación en curso; no se inicia otra corrida.').write();
    return;
  }
  let recovery = 'Sin reintento: el pendiente requiere revisión del producto.';
  const slot = check.slot;
  const prefix = `Recuperación ${slot}`;
  const attempts = runs.filter(r => r.event === 'workflow_dispatch' && r.display_title?.startsWith(prefix)).length;
  // No cancelar por antigüedad: se alerta y se conserva el último sitio válido.
  if ((check.recoverable || failedEvent) && !stuck && attempts < policy.max_recoveries_per_slot) {
    const workflow_id = !source.recoverable && !failedEvent ? 'deploy-pages.yml' : 'update-data.yml';
    await github.rest.actions.createWorkflowDispatch({...context.repo, workflow_id, ref: 'main', inputs: {recovery_slot: slot}});
    recovery = `Recuperación solicitada (${attempts + 1}/${policy.max_recoveries_per_slot}): ${workflow_id}.`;
  } else if (stuck || attempts >= policy.max_recoveries_per_slot) {
    recovery = 'Límite de recuperación alcanzado o ejecución detenida; revisar Actions.';
  }
  const body = `${problems || 'Falló la ejecución de actualización.'}\n\n${recovery}\n\nCorte esperado: ${slot}.`;
  core.warning(body);
  if (stuck || ((check.recoverable || failedEvent) && attempts >= policy.max_recoveries_per_slot)) {
    core.setFailed('La actualización requiere intervención; se conserva el último sitio válido.');
  }
  await summary.addRaw(body).write();
}
module.exports = {watchdog, retryRead, relevantActiveRuns};
