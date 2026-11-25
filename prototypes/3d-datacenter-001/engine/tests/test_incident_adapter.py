"""Phase 7 (Issue #8): incident-response saves through the 3D adapter (GameHost / Game.act), engine judgements only.

Saves live in a temporary folder. Global shift 3 is cleared with the engine methods (tests.test_global_shifts.PLANS)
only to unlock the incident shifts; everything about incidents goes through the adapter actions.
"""
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from engine.adapter import GameHost, ActionError, ROOT   # puts the project root on sys.path
from database import Database
from aidc.global_ops.session import GlobalSession
from aidc.incidents.content import load

_spec = importlib.util.spec_from_file_location('root_test_global_shifts', ROOT / 'tests' / 'test_global_shifts.py')
_shifts = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_shifts)
PLANS, play = _shifts.PLANS, _shifts.play

C = load()


class IncidentAdapterTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix='srs3d-inc-'))
        self.host = GameHost(self.dir)

    def tearDown(self):
        self.host.shutdown()
        shutil.rmtree(self.dir, ignore_errors=True)

    def act(self, game, **action):
        try:
            return {'ok': True, **game.act(action)}
        except ValueError as exc:
            return {'ok': False, 'message': str(exc), 'hint': getattr(exc, 'hint', '')}

    def ok(self, game, **action):
        out = self.act(game, **action)
        self.assertTrue(out['ok'], out)
        return out

    def clear_global_shift3(self):
        db = Database(self.dir / 'aidc_3d_global_001.db')
        s = GlobalSession(db, kind='shift', shift=1, seed=11)
        for number in (1, 2, 3):
            result = play(self, s, PLANS[number])
            self.assertTrue(result['cleared'])
            if number < 3:
                s.start_next_shift()
        s.close()

    def incident(self, game):
        snap = game.snapshot()
        return snap, (snap['incident']['records'] or [None])[0]

    def start_practice(self, itype, rack=None):
        game = self.host.new_game('incident_practice', itype)
        self.ok(game, type='confirm_briefing')
        rid = game.snapshot()['requests'][0]['id']
        self.ok(game, type='read_request', rid=rid)
        plans = self.ok(game, type='view_plans', rid=rid)['plans']
        opts = plans['performance']['options']
        index = next((i for i, o in enumerate(opts) if o[0]['rack'] == rack), 0) if rack else 0
        self.ok(game, type='select_plan', rid=rid, mode='performance', index=index, slices=opts[index])
        self.ok(game, type='navigate', route='hall', via='tab')
        self.ok(game, type='start_job', rid=rid, rack=opts[index][0]['rack'])
        for _ in range(20):
            self.ok(game, type='advance_time', minutes=10)
            if self.incident(game)[1]['state'] != 'armed':
                break
        return game, rid

    def test_incident_shifts_locked_until_global_shift3_cleared(self):
        unlocks = self.host.unlocks()
        self.assertFalse(unlocks['incident']['available'])
        self.assertTrue(unlocks['incidentPractice']['available'])
        with self.assertRaises(ActionError):
            self.host.new_game('incident')
        self.clear_global_shift3()
        self.assertEqual(self.host.unlocks()['incident']['proof'], ['aidc_3d_global_001'])
        game = self.host.new_game('incident')
        snap = game.snapshot()
        self.assertEqual((snap['mode'], snap['kind'], snap['incident']['code']), ('incident', 'incident', 'A'))
        self.assertFalse(snap['canAdvance'], 'briefing first')
        self.assertFalse(self.act(game, type='advance_time', minutes=10)['ok'])

    def test_cooling_practice_on_site_evidence_and_no_answer_before_diagnosis(self):
        game, rid = self.start_practice('cooling')
        snap, rec = self.incident(game)
        self.assertEqual(rec['state'], 'alert')
        req = next(r for r in snap['requests'] if r['id'] == rid)
        self.assertEqual(req['stage'], 'incident')
        text = json.dumps({k: v for k, v in snap.items() if k != 'incident'} | {'records': snap['incident']['records']}, ensure_ascii=False)
        self.assertNotIn(C.causes['cooling']['label'], text, 'cause label hidden before diagnosis')
        path = next(p for p in snap['world']['paths'] if p['rid'] == rid)
        self.assertEqual((path['link'], set(path['segments'].values())), ('incident', {'ok'}), 'no hop blamed, subsea never red')
        iid = rec['id']
        self.assertFalse(self.act(game, type='incident_observe', incident=iid, probe='cooling')['ok'], 'scope first')
        self.ok(game, type='incident_ack', incident=iid)
        refused = self.act(game, type='incident_observe', incident=iid, probe='cooling')
        self.assertFalse(refused['ok'])
        self.assertIn('냉각 플랜트', refused['message'])
        self.ok(game, type='navigate', route='campus', via='tab')
        self.ok(game, type='navigate', route='room', via='button', building='COOLING')
        ev = self.ok(game, type='incident_observe', incident=iid, probe='cooling')['incident']['evidence']
        self.assertEqual(ev['status'], 'bad')
        self.assertEqual(game.snapshot()['incident']['facilities']['cooling'][self.incident(game)[1]['servers'] and
                                                                         ('Z1' if self.incident(game)[1]['servers'][0] in 'AB' else 'Z2')]['pumps']['P-2'], 'WARN')
        wrong = self.ok(game, type='incident_hypothesis', incident=iid, cause='gpu_health')
        self.assertIn('근거 부족', wrong['hint'])
        right = self.ok(game, type='incident_hypothesis', incident=iid, cause='cooling')
        self.assertIn('원인 확정', right['info'])
        path = next(p for p in game.snapshot()['world']['paths'] if p['rid'] == rid)
        self.assertEqual((path['link'], path['segments']['sea'], path['segments']['aidc']), ('internal', 'ok', 'incident'))
        self.assertIn('hint', self.ok(game, type='incident_act', incident=iid, action='standby_pump'), 'approval first')
        self.ok(game, type='incident_act', incident=iid, action='escalate_facility')
        self.ok(game, type='advance_time', minutes=10)
        self.ok(game, type='incident_act', incident=iid, action='standby_pump')
        self.assertEqual(game.snapshot()['incident']['facilities']['cooling'][('Z1' if self.incident(game)[1]['servers'][0] in 'AB' else 'Z2')]['pumps']['P-3'], 'ON')
        for _ in range(2):
            self.ok(game, type='advance_time', minutes=10)
        self.assertEqual(self.incident(game)[1]['state'], 'monitoring')
        self.assertFalse(self.ok(game, type='advance_time', minutes=10) is None)
        self.ok(game, type='incident_observe', incident=iid, probe='cooling')
        early = self.act(game, type='incident_verify', incident=iid)
        self.assertFalse(early['ok'])
        self.assertIn('GPU 건강 검사', early['message'])
        self.ok(game, type='navigate', route='hall', via='tab')
        self.ok(game, type='incident_observe', incident=iid, probe='dcgm')
        self.ok(game, type='incident_verify', incident=iid)
        self.ok(game, type='incident_report', incident=iid)
        snap, rec = self.incident(game)
        self.assertEqual((rec['state'], rec['outcome']), ('closed', 'resolved'))
        self.assertTrue(rec['postmortem']['field'])

    def test_resume_after_host_restart_is_identical_and_retry_is_a_new_slot(self):
        game, rid = self.start_practice('dns')
        _, rec = self.incident(game)
        self.ok(game, type='incident_ack', incident=rec['id'])
        self.ok(game, type='navigate', route='noc', via='tab')
        self.ok(game, type='incident_observe', incident=rec['id'], probe='ping')
        before = game.snapshot()
        gid = game.id
        self.host.shutdown()
        self.host = GameHost(self.dir)
        again = self.host.get(gid)
        after = again.snapshot()
        for key in ('clock', 'requests', 'servers', 'datacenter', 'incident', 'world'):
            self.assertEqual(after[key], before[key], key)
        source = (self.dir / f'{gid}.db').read_bytes()
        new = self.host.retry(gid)
        self.assertNotEqual(new.id, gid)
        self.assertEqual((new.kind, new.session.incident.practice), ('incident_practice', 'dns'))
        self.assertEqual((self.dir / f'{gid}.db').read_bytes(), source, 'retry never changes the source save')
        listed = {s['id']: s for s in self.host.saves()}
        self.assertEqual(listed[gid]['kind'], 'incident_practice')
        self.assertIn('사건 연습', listed[gid]['describe'])

    def test_bad_inputs_are_refused_without_change(self):
        game, rid = self.start_practice('storage_full')
        _, rec = self.incident(game)
        before = game.snapshot()['incident']
        for action in ({'type': 'incident_ack', 'incident': 7}, {'type': 'incident_act', 'incident': rec['id'], 'action': 'meteor'},
                       {'type': 'incident_hypothesis', 'incident': rec['id'], 'cause': ['dns']},
                       {'type': 'incident_act', 'incident': rec['id'], 'action': 'cleanup_temp', 'rid': '1'}):
            self.assertFalse(self.act(game, **action)['ok'], action)
        self.assertEqual(game.snapshot()['incident']['records'], before['records'])
        with self.assertRaises(ActionError):
            self.host.new_game('incident_practice', 'meteor')


if __name__ == '__main__':
    unittest.main()
