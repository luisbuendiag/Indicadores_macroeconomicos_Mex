"""Control de consulta y productos, separado del periodo estadístico publicado."""
from __future__ import annotations
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: Path, default):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def build(root: Path = ROOT) -> dict:
    log = read(root / 'data/update_log.json', {})
    manifest = read(root / 'data/manifest.json', {})
    notes = read(root / 'data/notas/estado.json', {})
    valid = log.get('mode') == 'online' and log.get('network_calls') and not log.get('critical')
    pending = [row['clave'] for row in manifest.get('indicadores', [])
               if row.get('estado') in {'ERROR DE FUENTE', 'REZAGADO', 'PUBLICACIÓN PENDIENTE'}]
    return {
        'checked_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'data_checked_at': log.get('finished_at') if valid else None,
        'data_error': not bool(valid),
        'pending_data': sorted(pending),
        'pending_notes': sorted(key for key, note in notes.items()
                                if note.get('status') != 'vigente'
                                or note.get('target_period') != note.get('published', {}).get('periodo')),
        'run_url': (f"https://github.com/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
                    if os.environ.get('GITHUB_RUN_ID') and os.environ.get('GITHUB_REPOSITORY') else None),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    target = args.root / 'data/update_health.json'
    target.write_text(json.dumps(build(args.root), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
