"""Hash-only audit. Never connect to a protected SQLite database."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'docs/3d-world-expansion/qa/phase9'


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None


if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    baseline = OUT / 'protected-before.json'
    if sys.argv[1] == 'before':
        old = json.loads((OUT.parent / 'phase8/protected-before.json').read_text(encoding='utf8'))
        paths = {ROOT / p for p in old}
        for directory in ('artifacts', 'docs/qa', 'prototypes/3d-datacenter-001/saves', 'docs/3d-world-expansion/qa'):
            paths.update(p for p in (ROOT / directory).rglob('*') if p.is_file() and OUT not in p.parents)
        paths.update(p for p in ROOT.glob('aidc*') if p.is_file())
        hashes = {p.relative_to(ROOT).as_posix(): digest(p) for p in sorted(paths)}
        with baseline.open('x', encoding='utf8') as f:
            json.dump(hashes, f, ensure_ascii=False, indent=2)
        info = {'protected': len(hashes), 'phase8Baseline': len(old),
                'phase8DifferencesAtStart': [p for p, h in old.items() if hashes.get(p) != h],
                'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip(),
                'status': subprocess.check_output(['git', 'status', '--short'], cwd=ROOT).decode()}
        (OUT / 'baseline.json').write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding='utf8')
        print({k: v for k, v in info.items() if k != 'status'})
    elif sys.argv[1] == 'after':
        old = json.loads(baseline.read_text(encoding='utf8'))
        changed = [p for p, h in old.items() if digest(ROOT / p) != h]
        info = {'protected': len(old), 'changed': changed, 'unchanged': not changed}
        (OUT / 'protection-result.json').write_text(json.dumps(info, indent=2), encoding='utf8')
        print(info)
        raise SystemExit(bool(changed))
    else:
        raise SystemExit('before|after')
