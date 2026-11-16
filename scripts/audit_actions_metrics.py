"""Lectura read-only de metadatos GitHub Actions institucionales (QA).

No consulta logs, artefactos, secretos, contenidos de workflows ni datos de usuarios.
Acceso a GitHub API con token efímero entregado en entorno; ninguna acción de escritura.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API_ROOT = "https://api.github.com"
REPO = "luisbuendiag/Indicadores_macroeconomicos_Mex"
VALID_WORKFLOWS = frozenset({
    ".github/workflows/update-data.yml",
    ".github/workflows/update-watchdog.yml",
    ".github/workflows/deploy-pages.yml",
})
MAX_RUNS = 10
MAX_BYTES = 1024 * 1024


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError("fecha ausente")
    d = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if d.utcoffset() is None:
        raise ValueError("fecha sin zona")
    return d.astimezone(timezone.utc)


def api_read(path: str, *, token: str) -> dict:
    if not path.startswith(f"/repos/{REPO}/actions/") or not re.fullmatch(r"/[A-Za-z0-9_/?=&.\-]+", path):
        raise ValueError("ruta fuera de la lista permitida")
    if not token or len(token) > 1024:
        raise ValueError("token de lectura ausente")
    req = Request(API_ROOT + path, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "sistema-agentes-auditor-readonly",
    })
    try:
        with urlopen(req, timeout=12) as response:
            if response.status != 200:
                raise RuntimeError("github_api_unavailable")
            payload = response.read(MAX_BYTES + 1)
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError("github_api_unavailable") from None
    if len(payload) > MAX_BYTES:
        raise ValueError("respuesta demasiado grande")
    parsed = json.loads(payload)
    if not isinstance(parsed, dict):
        raise ValueError("formato de API inesperado")
    return parsed


def summarize_runs(runs: list[dict], jobs_by_run: dict[int, list[dict]],
                   *, limit: int = MAX_RUNS) -> dict:
    if not isinstance(runs, list) or not isinstance(jobs_by_run, dict):
        raise ValueError("entrada inválida")
    if type(limit) is not int or not 1 <= limit <= MAX_RUNS:
        raise ValueError("límite inválido")
    samples = []
    seen = set()
    for run in runs:
        if len(samples) >= limit:
            break
        if not isinstance(run, dict):
            raise ValueError("ejecución inválida")
        path = run.get("path")
        if path not in VALID_WORKFLOWS or run.get("status") != "completed":
            continue
        if run.get("conclusion") not in ("success", "failure", "cancelled", "timed_out"):
            continue
        rid, attempt = run.get("id"), run.get("run_attempt")
        if type(rid) is not int or rid < 1 or rid in seen:
            raise ValueError("ID de ejecución inválido/duplicado")
        if type(attempt) is not int or attempt < 1:
            raise ValueError("número de intento inválido")
        seen.add(rid)
        if rid not in jobs_by_run or not isinstance(jobs_by_run[rid], list):
            raise ValueError("metadatos de jobs faltantes")
        raw_jobs = jobs_by_run[rid]
        if not raw_jobs:
            raise ValueError("ejecución sin jobs")
        elapsed = 0.0
        for job in raw_jobs:
            if not isinstance(job, dict) or job.get("status") != "completed":
                raise ValueError("job incompleto")
            start, end = timestamp(job.get("started_at")), timestamp(job.get("completed_at"))
            seconds = (end - start).total_seconds()
            if seconds < 0:
                raise ValueError("duración negativa")
            elapsed += seconds
        samples.append({
            "run_id": rid, "workflow": path, "outcome": run["conclusion"],
            "attempts": attempt, "job_compute_seconds": round(elapsed, 2),
            "finished_at": timestamp(run.get("updated_at")).isoformat(),
        })
    return {
        "schema_version": "0.6",
        "source": "github_actions_api_readonly",
        "repository": REPO,
        "runs": sorted(samples, key=lambda x: (x["finished_at"], x["run_id"])),
        "runs_count": len(samples),
        "failed_runs": sum(x["outcome"] in ("failure", "timed_out") for x in samples),
        "retry_attempts": sum(x["attempts"] - 1 for x in samples),
        "total_job_compute_seconds": round(sum(x["job_compute_seconds"] for x in samples), 2),
        "limitations": [
            "Duraciones suman tiempo de jobs; no son tiempo transcurrido total ni coste de facturación.",
            "El número de intento no revela intentos individuales de jobs.",
            "La muestra de últimas ejecuciones no representa por sí sola un antes/después.",
            "No se observaron tokens, costos, métricas clínicas o datos financieros.",
        ],
    }


def collect(token: str, *, limit: int = MAX_RUNS) -> dict:
    if type(limit) is not int or not 1 <= limit <= MAX_RUNS:
        raise ValueError("límite inválido")
    data = api_read(f"/repos/{REPO}/actions/runs?per_page=30", token=token)
    runs = data.get("workflow_runs")
    if not isinstance(runs, list):
        raise ValueError("listado de GitHub inválido")
    selected = []
    for r in runs:
        if not isinstance(r, dict):
            raise ValueError("elemento inválido")
        if r.get("path") in VALID_WORKFLOWS and r.get("status") == "completed" and r.get("conclusion") in (
            "success", "failure", "cancelled", "timed_out"):
            selected.append(r)
        if len(selected) >= limit:
            break
    jobs = {}
    for r in selected:
        rid = r.get("id")
        if type(rid) is not int or rid < 1:
            raise ValueError("run_id inválido")
        response = api_read(f"/repos/{REPO}/actions/runs/{rid}/jobs?per_page=100", token=token)
        items = response.get("jobs")
        if not isinstance(items, list) or type(response.get("total_count")) is not int:
            raise ValueError("jobs incompletos")
        if len(items) != response["total_count"]:
            raise ValueError("lista de jobs truncada")
        jobs[rid] = items
    return summarize_runs(selected, jobs, limit=limit)


def main() -> None:
    p = argparse.ArgumentParser(description="GitHub Actions read-only para métricas agregadas")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--limit", type=int, default=8)
    args = p.parse_args()
    report = collect(os.environ.get("GITHUB_TOKEN", ""), limit=args.limit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "runs_count": report["runs_count"],
                      "source": report["source"]}))


if __name__ == "__main__":
    main()
