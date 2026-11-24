"""Write real engine snapshots for the JS view tests (tests/fixtures/snapshots.json).

Run from prototypes/3d-datacenter-001:  python -m engine.tests.make_fixtures
Uses a temporary save folder; the snapshots come from the unmodified Python engine.
"""
import json
import tempfile
from pathlib import Path

from engine.adapter import GameHost

OUT = Path(__file__).resolve().parents[2] / 'tests' / 'fixtures' / 'snapshots.json'


def main():
    shots = {}
    with tempfile.TemporaryDirectory() as tmp:
        host = GameHost(tmp)
        try:
            g = host.new_game('tutorial')
            rid = g.snapshot()['requests'][0]['id']
            shots['tutorial_new'] = g.snapshot()
            for a in ({'type': 'confirm_briefing'}, {'type': 'read_request', 'rid': rid},
                      {'type': 'select_plan', 'rid': rid, 'mode': 'performance', 'index': 0}):
                g.act(a)
            shots['tutorial_selected'] = g.snapshot()
            rack = shots['tutorial_selected']['requests'][0]['selection']['slices'][0]['rack']
            g.act({'type': 'navigate', 'route': 'hall'})
            g.act({'type': 'start_job', 'rid': rid, 'rack': rack})
            shots['tutorial_running'] = g.snapshot()
            g.act({'type': 'advance_time', 'minutes': 10})
            shots['tutorial_hw_fault'] = g.snapshot()
            g.act({'type': 'diagnose', 'rid': rid})
            g.act({'type': 'begin_repair', 'rid': rid, 'server': g.journey.data['fault']['server']})
            shots['tutorial_hw_repair'] = g.snapshot()
            for _ in range(3):
                g.act({'type': 'advance_time', 'minutes': 10})
            shots['tutorial_done'] = g.snapshot()
            s = host.new_game('story')
            shots['story_new'] = s.snapshot()
            f = host.new_game('free')
            shots['free_new'] = f.snapshot()
        finally:
            host.close()
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(shots, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'wrote {OUT} ({len(shots)} snapshots)')


if __name__ == '__main__':
    main()
