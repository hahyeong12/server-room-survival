"""Phase 4 engine adapter tests. Temporary save folders only; the user's Python saves are never opened.

Run from prototypes/3d-datacenter-001:  python -m unittest discover -s engine/tests -t . -v
"""
import hashlib
import json
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

from engine.adapter import GameHost, ROOT, SERVER_RACKS
from engine.journey import STEP_IDS


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.host = GameHost(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(self.host.close)

    def act(self, game, **action):
        """Like the HTTP API: an engine/adapter rejection returns ok=False and changes nothing."""
        try:
            result = game.act(action)
            return {'ok': True, **result}
        except ValueError as exc:
            return {'ok': False, 'message': str(exc), 'hint': getattr(exc, 'hint', '')}

    def current(self, game):
        cur = game.snapshot()['journey']['current']
        return cur['id'] if cur else None


def play_tutorial_until(test, game, stop=None):
    """Real action sequence the 3D UI sends. Returns after the step `stop` becomes current."""
    rid = game.snapshot()['requests'][0]['id']
    plan = {}

    def step(expected, *actions):
        if stop == expected:
            raise StopIteration
        test.assertEqual(test.current(game), expected)
        for action in actions:
            r = test.act(game, **action)
            test.assertTrue(r['ok'], (expected, action, r))

    try:
        step('briefing', {'type': 'confirm_briefing'})
        step('campus-info', {'type': 'navigate', 'route': 'campus', 'via': 'tab'},
             {'type': 'select_facility', 'id': 'COOLING', 'via': 'pick'})
        step('enter', {'type': 'navigate', 'route': 'room', 'via': 'dblclick', 'building': 'COOLING'})
        step('back', {'type': 'navigate', 'route': 'campus', 'via': 'back'})
        step('world', {'type': 'navigate', 'route': 'world', 'via': 'tab'})
        step('origin', {'type': 'select_country', 'id': 'SG'})
        step('read', {'type': 'navigate', 'route': 'noc', 'via': 'tab'}, {'type': 'read_request', 'rid': rid})
        step('compare', {'type': 'view_plans', 'rid': rid})
        step('choose', {'type': 'select_plan', 'rid': rid, 'mode': 'performance', 'index': 1})
        plan.update(game.snapshot()['requests'][0]['selection'])
        step('hall', {'type': 'navigate', 'route': 'hall', 'via': 'tab'})
        rack = plan['slices'][0]['rack']
        step('rack', {'type': 'inspect_rack', 'rack': rack})
        step('start', {'type': 'start_job', 'rid': rid, 'rack': rack})
        step('time', {'type': 'advance_time', 'minutes': 10})
        fault = game.journey.data['fault']
        step('diagnose', {'type': 'navigate', 'route': 'noc', 'via': 'tab'}, {'type': 'diagnose', 'rid': rid})
        step('respond', {'type': 'begin_repair', 'rid': rid, 'server': fault['server']})
        step('recover', {'type': 'advance_time', 'minutes': 10}, {'type': 'advance_time', 'minutes': 10})
        step('verify', {'type': 'navigate', 'route': 'hall', 'via': 'tab'}, {'type': 'inspect_rack', 'rack': fault['rack']},
             {'type': 'verify', 'rid': rid, 'rack': fault['rack']})
        step('finish', {'type': 'advance_time', 'minutes': 10})
        step('report', {'type': 'navigate', 'route': 'noc', 'via': 'tab'}, {'type': 'report', 'rid': rid})
    except StopIteration:
        pass
    return rid


class SaveIsolationTests(Base):
    def test_refuses_project_root_as_save_folder(self):
        with self.assertRaises(ValueError):
            GameHost(ROOT)

    def test_new_games_create_new_files_only_in_the_3d_folder(self):
        root_dbs = {p.name: sha(p) for p in ROOT.glob('aidc*.db')}
        a = self.host.new_game('tutorial')
        b = self.host.new_game('story')
        c = self.host.new_game('free')
        self.assertEqual({a.id, b.id, c.id}, {'aidc_story_slot_001', 'aidc_story_slot_002', 'aidc_3d_free_001'})
        for g in (a, b, c):
            self.assertEqual(g.path.parent, Path(self.tmp.name).resolve())
        self.assertTrue((Path(self.tmp.name) / 'aidc_checkpoint_aidc_story_slot_002_ch1.db').is_file())
        self.assertEqual(root_dbs, {p.name: sha(p) for p in ROOT.glob('aidc*.db')})

    def test_snapshot_is_read_only(self):
        game = self.host.new_game('tutorial')
        before = (sha(game.path), game.journey.path.read_text(encoding='utf-8'))
        one, two = game.snapshot(), game.snapshot()
        self.assertEqual(json.dumps(one, sort_keys=True), json.dumps(two, sort_keys=True))
        self.assertEqual(before, (sha(game.path), game.journey.path.read_text(encoding='utf-8')))


class TutorialTests(Base):
    def test_full_tutorial_uses_only_real_actions(self):
        game = self.host.new_game('tutorial')
        snap = game.snapshot()
        self.assertEqual(snap['mode'], 'tutorial')
        self.assertEqual([r['code'] for r in snap['requests']], ['SG'])
        self.assertEqual(snap['world']['paths'][0]['tone'], 'incoming')
        rid = play_tutorial_until(self, game)
        snap = game.snapshot()
        j = snap['journey']
        self.assertTrue(j['completed'])
        self.assertEqual(j['doneSteps'], len(STEP_IDS))
        self.assertEqual(j['misclicks'], 0)
        self.assertTrue(snap['story']['done'])
        req = snap['requests'][0]
        self.assertEqual((req['status'], req['stage'], req['progress']), ('completed', 'done', 100))
        self.assertEqual(snap['datacenter']['gpuUsed'], 0)   # engine returned the resources
        self.assertEqual(snap['story']['result']['request_id'], rid)
        self.assertTrue(all(s['state'] == 'HEALTHY' for s in snap['servers']))
        self.assertEqual(snap['world']['paths'], [])   # finished request: path no longer lit

    def test_dialogue_skip_and_wrong_clicks_never_complete_steps(self):
        game = self.host.new_game('tutorial')
        rid = game.snapshot()['requests'][0]['id']
        # navigation before the briefing is not counted for later steps either
        self.act(game, type='navigate', route='campus')
        self.act(game, type='select_facility', id='POWER', via='pick')
        self.assertEqual(self.current(game), 'briefing')
        play_tutorial_until(self, game, stop='origin')
        r = self.act(game, type='select_country', id='JP')
        self.assertTrue(r['ok'])
        self.assertIn('도착한 요청이 없습니다', r['hint'])
        self.assertEqual(self.current(game), 'origin')
        r = self.act(game, type='skip_tutorial')
        snap = game.snapshot()
        self.assertTrue(snap['journey']['skipped'])
        self.assertFalse(snap['journey']['completed'])
        self.assertEqual(snap['requests'][0]['status'], 'new')
        self.assertEqual(snap['datacenter']['gpuUsed'], 0)
        self.assertGreaterEqual(snap['journey']['misclicks'], 1)

    def test_customer_conditions_racks_and_location_are_enforced_by_the_engine(self):
        game = self.host.new_game('tutorial')
        rid = play_tutorial_until(self, game, stop='choose')
        r = self.act(game, type='select_plan', rid=rid, mode='economy', index=0)
        self.assertFalse(r['ok'])
        self.assertIn('고객 동의', r['message'])
        self.assertEqual(self.current(game), 'choose')
        self.assertTrue(self.act(game, type='select_plan', rid=rid, mode='performance', index=0)['ok'])
        plan = game.snapshot()['requests'][0]['selection']
        rack = plan['slices'][0]['rack']
        r = self.act(game, type='start_job', rid=rid, rack=rack)          # still at my desk
        self.assertFalse(r['ok'])
        self.assertIn('서버동', r['message'])
        self.act(game, type='navigate', route='hall')
        r = self.act(game, type='inspect_rack', rack='B-04')               # decoration rack
        self.assertIn('장식', r['hint'])
        self.assertEqual(self.current(game), 'rack')
        unused = next(k for k in 'ABCD' if k not in [p['server'] for p in plan['slices']])
        r = self.act(game, type='inspect_rack', rack=SERVER_RACKS[unused])
        self.assertIn('배정안에 없습니다', r['hint'])
        r = self.act(game, type='start_job', rid=rid, rack=SERVER_RACKS[unused])
        self.assertFalse(r['ok'])
        self.assertEqual(game.snapshot()['datacenter']['gpuUsed'], 0)
        self.assertTrue(self.act(game, type='inspect_rack', rack=rack)['ok'])
        self.assertTrue(self.act(game, type='start_job', rid=rid, rack=rack)['ok'])
        snap = game.snapshot()
        self.assertEqual(snap['datacenter']['gpuUsed'], 7)
        self.assertEqual(snap['requests'][0]['allocation'], plan['slices'])  # exactly the chosen GPU slots

    def test_misdiagnosis_and_premature_verification_change_nothing(self):
        game = self.host.new_game('tutorial')
        rid = play_tutorial_until(self, game, stop='diagnose')
        fault = game.journey.data['fault']
        before = game.snapshot()
        self.assertEqual(before['requests'][0]['stage'], 'hw_fault')
        self.assertEqual(before['requests'][0]['progress'], 0)
        r = self.act(game, type='begin_repair', rid=rid, server=fault['server'])
        self.assertFalse(r['ok'])
        self.assertIn('장비 진단', r['message'])
        self.assertTrue(self.act(game, type='diagnose', rid=rid)['ok'])
        diag = game.act({'type': 'diagnose', 'rid': rid})['diagnosis']
        self.assertFalse(diag['migration']['allowed'])    # SG GPU 7 > healthy GPU 6: the engine says no
        r = self.act(game, type='respond', rid=rid, key='reroute')
        self.assertFalse(r['ok'])
        self.assertIn('네트워크가 아니라 서버', r['hint'])
        r = self.act(game, type='migrate', rid=rid, index=0)
        self.assertFalse(r['ok'])
        other = next(k for k in 'ABCD' if k != fault['server'])
        self.assertFalse(self.act(game, type='begin_repair', rid=rid, server=other)['ok'])
        after = game.snapshot()
        self.assertEqual(before['servers'], after['servers'])
        self.assertEqual(before['clock'], after['clock'])
        self.assertEqual(self.current(game), 'respond')
        self.assertTrue(self.act(game, type='begin_repair', rid=rid, server=fault['server'])['ok'])
        self.assertEqual(self.current(game), 'recover')
        self.act(game, type='advance_time', minutes=10)                     # 10 of 20 minutes
        self.assertEqual(self.current(game), 'recover')
        self.act(game, type='advance_time', minutes=10)
        self.assertEqual(self.current(game), 'verify')
        r = self.act(game, type='verify', rid=rid, rack=SERVER_RACKS[other])
        self.assertIn('장애가 났던 서버', r['hint'])
        self.assertEqual(self.current(game), 'verify')
        self.assertFalse(self.act(game, type='report', rid=rid)['ok'])     # not finished yet

    def test_reload_keeps_engine_state_and_journey(self):
        game = self.host.new_game('tutorial')
        play_tutorial_until(self, game, stop='respond')
        snap = game.snapshot()
        self.host.close(game.id)
        host2 = GameHost(self.tmp.name)
        self.addCleanup(host2.close)
        again = host2.get(game.id).snapshot()
        self.assertEqual(json.dumps(snap, sort_keys=True), json.dumps(again, sort_keys=True))

    def test_same_file_cannot_be_opened_twice(self):
        game = self.host.new_game('tutorial')
        host2 = GameHost(self.tmp.name)
        self.addCleanup(host2.close)
        with self.assertRaises(Exception):
            host2.get(game.id)


class StoryAndFreeTests(Base):
    def test_story_first_job_runs_on_the_engine_and_next_request_arrives(self):
        tutorial = self.host.new_game('tutorial')
        play_tutorial_until(self, tutorial)
        tutorial_hash = sha(tutorial.path)
        story = self.host.new_game('story')
        snap = story.snapshot()
        self.assertEqual((snap['mode'], snap['journey']['kind']), ('story', 'story'))
        self.assertEqual(snap['story']['chapter']['label'], '제1장')
        rid = snap['requests'][0]['id']
        steps = [dict(type='confirm_briefing'), dict(type='read_request', rid=rid), dict(type='view_plans', rid=rid),
                 dict(type='select_plan', rid=rid, mode='performance', index=0)]
        for a in steps:
            self.assertTrue(self.act(story, **a)['ok'], a)
        rack = story.snapshot()['requests'][0]['selection']['slices'][0]['rack']
        self.act(story, type='navigate', route='hall')
        self.act(story, type='inspect_rack', rack=rack)
        self.assertTrue(self.act(story, type='start_job', rid=rid, rack=rack)['ok'])
        for _ in range(3):
            self.assertTrue(self.act(story, type='advance_time', minutes=10)['ok'])
        snap = story.snapshot()
        first = next(r for r in snap['requests'] if r['id'] == rid)
        self.assertEqual((first['status'], first['stage']), ('completed', 'done'))
        self.assertTrue(all(s['state'] == 'HEALTHY' for s in snap['servers']))   # no tutorial fault in story
        self.assertEqual(snap['story']['jobsDone'], 1)
        self.assertEqual([r['code'] for r in snap['requests']], ['SG', 'JP'])   # the engine sent the next job
        self.assertEqual(snap['story']['chapter']['state'], 'in_progress')
        self.assertTrue(self.act(story, type='report', rid=rid)['ok'])
        self.assertEqual(sha(tutorial.path), tutorial_hash)
        self.assertEqual(snap['world']['paths'][0]['code'], 'JP')

    def test_free_mode_runs_the_existing_free_rules(self):
        free = self.host.new_game('free')
        snap = free.snapshot()
        self.assertEqual(snap['mode'], 'free')
        self.assertIsNone(snap['story'])
        self.assertEqual(len(snap['requests']), 1)
        self.assertTrue(self.act(free, type='advance_time', minutes=30)['ok'])
        self.assertGreaterEqual(len(free.snapshot()['requests']), 1)
        self.assertEqual(free.snapshot()['clock']['label'], 'D1 09:30')

    def test_saves_listing(self):
        self.host.new_game('tutorial')
        self.host.new_game('story')
        kinds = sorted(s['kind'] for s in self.host.saves())
        self.assertEqual(kinds, ['story', 'tutorial'])


class HttpTests(Base):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.host = GameHost(self.tmp.name, worker=True)   # same threading model as engine/server.py
        self.addCleanup(self.host.shutdown)
        from http.server import ThreadingHTTPServer
        from engine.server import make_handler
        self.httpd = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(self.host))
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)
        self.base = f'http://127.0.0.1:{self.httpd.server_address[1]}'

    def call(self, path, body=None, headers=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, headers={'Content-Type': 'application/json', **(headers or {})})
        try:
            with urllib.request.urlopen(req, timeout=10) as res:
                return res.status, json.loads(res.read())
        except urllib.error.HTTPError as err:
            return err.code, json.loads(err.read())

    def test_round_trip(self):
        status, health = self.call('/api/health')
        self.assertEqual((status, health['ok']), (200, True))
        status, created = self.call('/api/games', {'mode': 'tutorial'})
        gid = created['game']['id']
        status, res = self.call(f'/api/games/{gid}/actions', {'type': 'advance_time', 'minutes': 10})
        self.assertEqual(status, 200)
        self.assertFalse(res['ok'])                  # no job yet: refused, snapshot returned unchanged
        self.assertEqual(res['game']['clock']['label'], 'D1 09:00')
        status, res = self.call(f'/api/games/{gid}/actions', {'type': 'confirm_briefing'})
        self.assertTrue(res['ok'])
        status, got = self.call(f'/api/games/{gid}')
        self.assertEqual(got['game']['journey']['current']['id'], 'campus-info')
        self.assertEqual(self.call('/api/games/../../etc')[0], 404)

    def test_negative_content_length_is_refused(self):
        req = urllib.request.Request(self.base + '/api/games', data=b'', method='POST',
                                     headers={'Content-Type': 'application/json', 'Content-Length': '-1'})
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(req, timeout=5)
        self.assertEqual(caught.exception.code, 400)
        caught.exception.close()

    def test_cross_origin_requests_are_refused(self):
        status, _ = self.call('/api/games', {'mode': 'tutorial'}, {'Origin': 'http://evil.example'})
        self.assertEqual(status, 403)
        self.assertEqual(self.host.run(self.host.saves), [])


if __name__ == '__main__':
    unittest.main()
