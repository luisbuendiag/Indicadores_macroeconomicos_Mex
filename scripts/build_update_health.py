"""Control de consulta y productos, separado del periodo estadístico publicado."""
from __future__ import annotations
import argparse
import json
import os
from calendar import monthrange
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]


def read(path: Path, default):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def imss_state_warning(snapshot, today):
    if not isinstance(snapshot, dict) or snapshot.get('estado') != 'oficial':
        return None
    for item in snapshot.get('indicadores', []):
        if item.get('clave') == 'IMSS' and item.get('estatus') == 'oficial':
            period = item.get('periodo')
            try:
                year, month = map(int, period.split('-'))
                cutoff = date(year, month, monthrange(year, month)[1])
            except (AttributeError, TypeError, ValueError):
                return None
            days = (today - cutoff).days
            if days > 45:
                return {'indicator': 'IMSS', 'period': period, 'age_days': days}
    return None


def build(root: Path = ROOT, *, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    log = read(root / 'data/update_log.json', {})
    manifest = read(root / 'data/manifest.json', {})
    notes = read(root / 'data/notas/estado.json', {})
    queried = sorted({row['indicador'] for row in log.get('consultas', [])
                      if row.get('indicador')})
    valid = (log.get('mode') == 'online' and bool(queried)
             and not log.get('critical') and log.get('result') == 'OK')
    isolated = log.get('isolated_failures', {})
    pending = {row['clave'] for row in manifest.get('indicadores', [])
               if row.get('estado') in {'ERROR DE FUENTE', 'REZAGADO', 'PUBLICACIÓN PENDIENTE'}}
    pending.update(key for key, failure in isolated.items() if failure['phase'] == 'data')
    pending_notes = {key for key, note in notes.items()
                     if note.get('status') != 'vigente'
                     or note.get('target_period') != note.get('published', {}).get('periodo')}
    pending_notes.update(key for key, failure in isolated.items() if failure['phase'] == 'note')
    health = {
        'checked_at': now.isoformat(timespec='seconds'),
        'data_checked_at': log.get('finished_at') if valid else None,
        'data_error': not bool(valid),
        'pending_data': sorted(pending),
        'queried_indicators': queried,
        'query_coverage': 'partial' if pending or isolated else ('valid' if valid else 'failed'),
        'pending_notes': sorted(pending_notes),
        'isolated_failures': isolated,
        'run_url': (f"https://github.com/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
                    if os.environ.get('GITHUB_RUN_ID') and os.environ.get('GITHUB_REPOSITORY') else None),
    }
    try:
        snapshot = read(root / 'data/estados.json', {})
    except (OSError, ValueError):
        snapshot = {}
    warning = imss_state_warning(snapshot, now.astimezone(ZoneInfo('America/Mexico_City')).date())
    if warning:
        health['state_warnings'] = [warning]
    if 'planned_indicators' in log:
        health['planned_indicators'] = log['planned_indicators']
        health['omitted_by_plan'] = log['omitted_by_plan']
    return health


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--refresh-products-metadata', action='store_true')
    args = parser.parse_args()
    if args.refresh_products_metadata:
        if args.root.resolve() != ROOT.resolve():
            parser.error('Run metadata refresh from the staged script root')
        import lib_data
        import build_data
        payload = read(ROOT / 'data/indicadores.json', {})
        log = read(ROOT / 'data/update_log.json', {})
        if log.get('isolated_failures') or 'planned_indicators' in log:
            payload['meta']['periodo_referencia_reciente'] = build_data._periodo_referencia_reciente(payload)
            lib_data.save_data(payload)
            lib_data.write_csvs(payload)
        lib_data.write_manifest(payload)
        build_data.build_summary(payload)
    target = args.root / 'data/update_health.json'
    health = build(args.root)
    for warning in health.get('state_warnings', []):
        print(f"AVISO IMSS estatal: {warning['period']} tiene {warning['age_days']} días desde el cierre del mes")
    target.write_text(json.dumps(health, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()

