"""Hash-only protection audit for Issue #1. No SQLite connections or writes."""
from pathlib import Path
import hashlib, json, subprocess, sys

ROOT = Path(__file__).resolve().parents[2]
PROTO = ROOT / 'prototypes/3d-datacenter-001'
# Optional 2nd argument: a phase sub-folder (e.g. `phase4`) so a new baseline never replaces an earlier one.
OUT = Path(__file__).resolve().parent / 'qa' / (sys.argv[2] if len(sys.argv) > 2 else '')
OUT.mkdir(parents=True, exist_ok=True)
def snapshot():
    names = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
    paths = {ROOT / n for n in names if n and not n.startswith(('prototypes/3d-datacenter-001/', 'docs/3d-world-expansion/'))}
    paths.update(p for p in ROOT.glob('aidc*') if p.is_file())
    for folder in [ROOT/'artifacts', ROOT/'docs/qa', PROTO/'qa']:
        paths.update(p for p in folder.rglob('*') if p.is_file())
    return [{'path':p.relative_to(ROOT).as_posix(), 'bytes':p.stat().st_size,
             'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(paths) if p.is_file()]

phase = sys.argv[1]
if phase not in ('before', 'after'): raise SystemExit('before or after required')
rows = snapshot()
if phase == 'before' and (OUT/'protected-before.json').exists(): raise SystemExit('Refusing to replace baseline')
(OUT/f'protected-{phase}.json').write_text(json.dumps(rows,indent=2),encoding='utf8')
result = {'phase':phase, 'count':len(rows)}
if phase == 'after':
    old = json.loads((OUT/'protected-before.json').read_text(encoding='utf8'))
    result['identical'] = old == rows
    before, after = {r['path']:r for r in old}, {r['path']:r for r in rows}
    result['differences'] = [p for p in before.keys() | after.keys() if before.get(p) != after.get(p)]
    (OUT/'protection-result.json').write_text(json.dumps(result,indent=2),encoding='utf8')
print(json.dumps(result))
if result.get('differences'): raise SystemExit(1)
