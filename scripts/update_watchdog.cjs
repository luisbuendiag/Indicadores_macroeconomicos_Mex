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
  const workflows = ['update-data.yml', 'deploy-pages.yml'];
  const runLists = await Promise.all(workflows.map(workflow_id =>
    retryRead(() => github.rest.actions.listWorkflowRuns({...context.repo, workflow_id, branch: 'main', per_page: 100}))));
  // Conservar el origen: la comparación de corridas supersedidas debe ser
  // dentro del MISMO workflow, no entre un deploy y una actualización.
  const runs = runLists.flatMap((result, index) =>
    (result.data.workflow_runs || []).map(run => ({...run, monitored_workflow: workflows[index]})));
  const supersededQueued = run => run.status === 'queued' &&
    Number.isFinite(new Date(run.created_at).getTime()) &&
    runs.some(later => later.monitored_workflow === run.monitored_workflow &&
      later.conclusion === 'success' && later.status === 'completed' &&
      new Date(later.created_at).getTime() > new Date(run.created_at).getTime() &&
      Number.isFinite(new Date(later.updated_at).getTime()));
  // GitHub puede conservar entradas queued antiguas aunque una nueva corrida
  // de ese mismo workflow ya haya concluido con éxito. No marcar como "atasco"
  // ese trabajo supersedido; sí vigilar colas nuevas y trabajos in_progress.
  const active = runs.filter(r => r.status !== 'completed' && !supersededQueued(r));
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
module.exports = {watchdog, retryRead};
