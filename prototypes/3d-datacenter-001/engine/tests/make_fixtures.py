"""Write real engine snapshots for the JS view tests (tests/fixtures/snapshots.json).

Run from prototypes/3d-datacenter-001:  python -m engine.tests.make_fixtures
Uses a temporary save folder; the snapshots come from the unmodified Python engine.
"""
import json
import tempfile
from pathlib import Path

from engine.adapter import GameHost

OUT = Path(__file__).resolve().parents[2] / 'tests' / 'fixtures' / 'snapshots.json'


def campaign(host, shots):
    """Phase 5: chapter snapshots from real adapter actions (same sequences as test_campaign.Driver)."""
    from engine.tests.seed_campaign import _Shim
    from engine.tests.test_campaign import Driver, req
    g = host.new_game('story')
    d = Driver(_Shim(), g)
    d.chapter1()
    shots['ch1_clear'] = g.snapshot()
    d.next_chapter('2')
    shots['ch2_briefing'] = g.snapshot()
    d.chapter2_success()
    shots['ch2_clear'] = g.snapshot()
    d.next_chapter('3')
    d.read_dialogue(); d.ok(type='confirm_briefing')
    a = d.story()['chapter3']['requestIds'][0]
    d.start(a, 'performance')
    d.advance_until(lambda: req(g, a)['stage'] == 'net_fault')
    shots['ch3_symptom'] = g.snapshot()
    d.ok(type='diagnose', rid=a)
    shots['ch3_diagnosed'] = g.snapshot()
    p = host.new_game('practice', 'lab')
    shots['lab_practice'] = p.snapshot()
    f = host.new_game('practice', 2)
    fd = Driver(_Shim(), f)
    fd.read_dialogue(); fd.ok(type='confirm_briefing')
    jp, us = fd.story()['chapter2']['requestIds']
    fd.start(jp, 'performance')
    fd.advance_until(lambda: req(f, jp)['stage'] == 'done')
    fd.start(us, 'performance')
    fd.advance_until(lambda: fd.story()['chapter2']['failure'] is not None)
    shots['ch2_failure'] = f.snapshot()
    fd.ok(type='ack_feedback', kind='chapter2')
    fd.advance_until(lambda: fd.story()['done'], step=30)
    shots['ch2_failed_done'] = f.snapshot()


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
            campaign(host, shots)
        finally:
            host.close()
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(shots, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'wrote {OUT} ({len(shots)} snapshots)')


if __name__ == '__main__':
    main()
