"""Phase 7 (Issue #8) protection audit: read-only hashes, never opens a SQLite connection.

Two groups are compared separately:
  * user data  - the Python game's own saves and records in the project root (aidc*.db, *.lock, checkpoints),
                 artifacts/ and docs/qa/ (earlier QA evidence). These must not change at all.
  * source     - every other git-tracked file outside prototypes/3d-datacenter-001 and docs/3d-world-expansion.
                 Phase 7 is allowed a minimal, listed, backward-compatible change here; the list is reported.

    python scripts/protect_phase7.py before   # refuses to replace an existing baseline
    python scripts/protect_phase7.py after
"""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'docs/3d-world-expansion/qa/phase7'
BASE = ROOT / 'docs/qa/desktop-start-2026-11-20'


def record(path):
    return {'path': path.relative_to(ROOT).as_posix(), 'bytes': path.stat().st_size,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def user_data():
    paths = {p for p in ROOT.glob('aidc*') if p.is_file()}
    for folder in ('artifacts', 'docs/qa'):
        paths.update(p for p in (ROOT / folder).rglob('*') if p.is_file())
    return [record(p) for p in sorted(paths)]


def source():
    tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
    skip = ('prototypes/3d-datacenter-001/', 'docs/3d-world-expansion/', 'artifacts/', 'docs/qa/')
    paths = {ROOT / p for p in tracked if p and not p.startswith(skip) and not p.startswith('aidc_')}
    return [record(p) for p in sorted(paths) if p.is_file()]


def previous_changes(filename, name_key):
    changes = []
    rows = json.loads((BASE / filename).read_text(encoding='utf-8-sig'))
    for row in rows:
        path = ROOT / row[name_key]
        if (not path.is_file() or path.stat().st_size != row['bytes']
                or hashlib.sha256(path.read_bytes()).hexdigest().upper() != row['sha256'].upper()):
            changes.append(row[name_key])
    return {'count': len(rows), 'changed': changes}


def diff(old, new):
    a, b = {r['path']: r for r in old}, {r['path']: r for r in new}
    return sorted(p for p in a.keys() | b.keys() if a.get(p) != b.get(p))


phase = sys.argv[1] if len(sys.argv) > 1 else ''
if phase not in ('before', 'after'):
    raise SystemExit('usage: protect_phase7.py before|after')
OUT.mkdir(parents=True, exist_ok=True)
now = {'user_data': user_data(), 'source': source()}
target = OUT / f'protected-{phase}.json'
if phase == 'before' and target.exists():
    raise SystemExit('Refusing to replace the Phase 7 baseline')
target.write_text(json.dumps(now, ensure_ascii=False, indent=2), encoding='utf-8')
result = {'phase': phase, 'user_data_files': len(now['user_data']), 'source_files': len(now['source']),
          'original_user_baseline': previous_changes('user-data-before.json', 'name'),
          'original_qa_baseline': previous_changes('existing-qa-before.json', 'path')}
if phase == 'after':
    before = json.loads((OUT / 'protected-before.json').read_text(encoding='utf-8'))
    result['user_data_changed'] = diff(before['user_data'], now['user_data'])
    result['source_changed'] = diff(before['source'], now['source'])
    result['user_data_identical'] = not result['user_data_changed']
    (OUT / 'protection-result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(result, ensure_ascii=False))
if result['original_user_baseline']['changed'] or result['original_qa_baseline']['changed'] or result.get('user_data_changed'):
    raise SystemExit(1)
