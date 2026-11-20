"""Read-only hashes of the existing project; never opens SQLite connections."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1] / 'qa'
BASE = ROOT / 'docs/qa/desktop-start-2026-11-20'

def record(path):
    return {'path': path.relative_to(ROOT).as_posix(), 'bytes': path.stat().st_size,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

def snapshot():
    tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
    paths = {ROOT / p for p in tracked if p and not p.startswith('prototypes/3d-datacenter-001/')}
    paths.update(p for p in ROOT.glob('aidc*') if p.is_file())
    for folder in ('artifacts', 'docs/qa'):
        paths.update(p for p in (ROOT / folder).rglob('*') if p.is_file())
    return [record(p) for p in sorted(paths) if p.is_file()]

def previous_changes(filename, name_key):
    changes = []
    rows = json.loads((BASE / filename).read_text(encoding='utf-8-sig'))
    for row in rows:
        path = ROOT / row[name_key]
        if not path.is_file() or path.stat().st_size != row['bytes'] or hashlib.sha256(path.read_bytes()).hexdigest().upper() != row['sha256'].upper():
            changes.append(row[name_key])
    return {'count': len(rows), 'changed': changes}

OUT.mkdir(exist_ok=True)
phase = sys.argv[1]
now = snapshot()
(OUT / f'protected-{phase}.json').write_text(json.dumps(now, ensure_ascii=False, indent=2), encoding='utf-8')
result = {'phase': phase, 'protected_files': len(now),
          'original_user_baseline': previous_changes('user-data-before.json', 'name'),
          'original_qa_baseline': previous_changes('existing-qa-before.json', 'path')}
if phase == 'after':
    before = json.loads((OUT / 'protected-before.json').read_text(encoding='utf-8'))
    result['all_existing_files_identical'] = before == now
    old = {r['path']: r for r in before}
    new = {r['path']: r for r in now}
    result['differences'] = [p for p in old.keys() | new.keys() if old.get(p) != new.get(p)]
    (OUT / 'protection-result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result, ensure_ascii=False))
if result['original_user_baseline']['changed'] or result['original_qa_baseline']['changed'] or result.get('differences'):
    raise SystemExit(1)
