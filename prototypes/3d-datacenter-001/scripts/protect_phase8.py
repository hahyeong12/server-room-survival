"""Read-only protection audit, includes all pre-existing saves and QA evidence."""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'docs/3d-world-expansion/qa/phase8'

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def files():
    paths = {p for p in ROOT.glob('aidc*') if p.is_file()}
    for directory in ('artifacts', 'docs/qa', 'prototypes/3d-datacenter-001/saves',
                      'docs/3d-world-expansion/qa'):
        paths.update(p for p in (ROOT / directory).rglob('*') if p.is_file() and OUT not in p.parents)
    return {p.relative_to(ROOT).as_posix(): digest(p) for p in sorted(paths)}

if __name__ == '__main__':
    phase = sys.argv[1]
    OUT.mkdir(parents=True, exist_ok=True)
    baseline = OUT / 'protected-before.json'
    current = files()
    if phase == 'before':
        with baseline.open('x', encoding='utf-8') as f:
            json.dump(current, f, ensure_ascii=False, indent=2)
        print(f'Protected {len(current)} existing files')
    elif phase == 'after':
        previous = json.loads(baseline.read_text(encoding='utf-8'))
        changed = [p for p in previous if current.get(p) != previous[p]]
        result = {'protected': len(previous), 'changed': changed, 'unchanged': not changed}
        (OUT / 'protection-result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(json.dumps(result))
        raise SystemExit(bool(changed))
    else:
        raise SystemExit('before|after')
