"""Phase 5 (Issue #6) campaign tests through the 3D adapter only (the same actions the browser sends).

Chapters 1 -> 5 of the regular story, one failure path per chapter, chapter retry into a new slot, chapter
practice, resume after closing the host, corrupted / missing-checkpoint saves. Temporary folders only.
Run from prototypes/3d-datacenter-001:  python -m unittest discover -s engine/tests -t . -v
"""
import json
import shutil
import sqlite3
import unittest
from pathlib import Path

from engine.adapter import GameHost
from engine.tests.test_adapter import Base, sha


def req(game, rid):
    return next(r for r in game.snapshot()['requests'] if r['id'] == rid)


class Driver:
    """Real 3D action sequences (monitor tabs, hall rack, time buttons). Each call asserts the engine accepted it."""

    def __init__(self, test, game):
        self.t, self.game = test, game

    def ok(self, **action):
        r = self.t.act(self.game, **action)
        self.t.assertTrue(r['ok'], (action, r))
        return r

    def no(self, **action):
        before = self.game.snapshot()
        r = self.t.act(self.game, **action)
        self.t.assertFalse(r['ok'], (action, r))
        after = self.game.snapshot()
        for key in ('clock', 'requests', 'servers', 'datacenter'):
            self.t.assertEqual(before[key], after[key], f'{action} changed {key}')
        return r

    def snap(self):
        return self.game.snapshot()

    def story(self):
        return self.snap()['story']

    def read_dialogue(self):
        d = self.story()['dialogue']
        if not d['seen'] and d['pages']:
            self.ok(type='mark_dialogue', event=d['event'])

    def start(self, rid, mode, index=0, shown=None):
        self.ok(type='read_request', rid=rid)
        plans = self.ok(type='view_plans', rid=rid)['plans']
        option = plans[mode]['options'][index] if shown is None else shown
        self.ok(type='select_plan', rid=rid, mode=mode, index=index, slices=option)
        rack = option[0]['rack']
        self.ok(type='navigate', route='hall', via='tab')
        self.ok(type='inspect_rack', rack=rack)
        self.ok(type='start_job', rid=rid, rack=rack)
        self.ok(type='navigate', route='noc', via='tab')

    def advance_until(self, done, step=10, limit=60):
        for _ in range(limit):
            if done():
                return
            self.ok(type='advance_time', minutes=step)
        self.t.fail('time did not reach the expected state')

    def chapter1(self):
        self.ok(type='confirm_briefing')
        for _ in range(3):
            snap = self.snap()
            rid = next(r['id'] for r in snap['requests'] if r['stage'] == 'incoming')
            self.start(rid, req(self.game, rid)['conditions']['requestedMode'])
            self.advance_until(lambda: req(self.game, rid)['stage'] == 'done')
        self.t.assertEqual(self.story()['chapter']['state'], 'cleared')

    def next_chapter(self, key):
        r = self.ok(type='start_next_chapter', chapter=key)
        self.t.assertIn('checkpoint', r, r)
        self.t.assertEqual(str(self.story()['chapterKey']), key)
        return r

    def chapter2_success(self):
        self.read_dialogue()
        self.ok(type='confirm_briefing')
        jp, us = self.story()['chapter2']['requestIds']
        for rid in (jp, us):
            self.ok(type='read_request', rid=rid)
        plans = self.ok(type='view_plans', rid=jp)['plans']
        self.t.assertTrue(plans['performance']['impacts'][0], 'impact lines for the other customer')
        self.start(jp, 'performance', 0)
        self.start(us, 'economy', 0)
        self.advance_until(lambda: self.story()['done'], step=30)

    def incident(self, rid, wrong, right):
        mode = req(self.game, rid)['conditions']['requestedMode']
        self.start(rid, mode, 0)
        self.advance_until(lambda: req(self.game, rid)['stage'] == 'net_fault')
        path = next(p for p in self.snap()['world']['paths'] if p['rid'] == rid)
        self.t.assertEqual(path['link'], 'symptom', 'before a diagnosis the transit shows a symptom, no cause')
        self.t.assertEqual(path['segments']['aidc'], 'ok', 'a network incident never marks the server building')
        r = self.no(type='respond', rid=rid, key=right)
        self.t.assertIn('네트워크 진단', r['message'])
        d = self.ok(type='diagnose', rid=rid)['diagnosis']
        self.t.assertEqual(d['networkDiagnosis']['kind'], self.game.session.runs[rid].state.incident_kind)
        self.t.assertNotIn('incident_kind', json.dumps(req(self.game, rid)), 'the cause is not in the request snapshot')
        self.t.assertIn(self.snap()['world']['paths'][0]['link'], ('primary_down', 'congested'))
        self.ok(type='respond', rid=rid, key=wrong)
        self.t.assertEqual(req(self.game, rid)['phase'], 'paused')
        self.ack_pending()
        self.ok(type='respond', rid=rid, key=right)
        self.t.assertEqual(req(self.game, rid)['stage'], 'recovering')
        self.ack_pending()
        self.advance_until(lambda: req(self.game, rid)['stage'] == 'done', step=30)

    def ack_pending(self):
        st = self.story()
        for kind in ('chapter3', 'chapter3b'):
            pending = (st.get(kind) or {}).get('pending')
            if pending:
                self.ok(type='ack_feedback', kind=kind, key=pending['key'])

    def chapter3_success(self):
        self.read_dialogue()
        self.ok(type='confirm_briefing')
        a = self.story()['chapter3']['requestIds'][0]
        self.incident(a, 'compress', 'reroute')
        b = self.story()['chapter3']['requestIds'][1]
        self.incident(b, 'reroute', 'compress')
        self.t.assertEqual(self.story()['result']['mission'], 'success')

    def hardware(self, rid, choice):
        mode = req(self.game, rid)['conditions']['requestedMode']
        self.start(rid, mode, 0)
        self.advance_until(lambda: req(self.game, rid)['stage'] == 'hw_fault')
        server = next(s['key'] for s in self.snap()['servers'] if s['state'] == 'FAULT')
        self.t.assertIn('장비 진단', self.no(type='begin_repair', rid=rid, server=server)['message'])
        self.t.assertIn('장비 진단', self.no(type='migrate', rid=rid, index=0)['message'])
        d = self.ok(type='diagnose', rid=rid)['diagnosis']['hardwareDiagnosis']
        if choice == 'migrate':
            self.t.assertTrue(d['migrate_possible'])
            self.ok(type='migrate', rid=rid, index=0)
        else:
            if not d['migrate_possible']:
                r = self.no(type='migrate', rid=rid, index=0)
                self.t.assertIn('GPU', r['message'])
            self.ok(type='begin_repair', rid=rid, server=server)
        self.ack_pending()
        self.advance_until(lambda: req(self.game, rid)['stage'] in ('done', 'failed'))
        self.ack_pending()
        return d

    def chapter3b_success(self):
        self.read_dialogue()
        self.ok(type='confirm_briefing')
        jp = self.story()['chapter3b']['requestIds'][0]
        d = self.hardware(jp, 'migrate')
        self.t.assertTrue(d['migrate_on_time'] and not d['repair_on_time'])
        sg = self.story()['chapter3b']['requestIds'][1]
        d = self.hardware(sg, 'repair')
        self.t.assertFalse(d['migrate_possible'])
        self.t.assertEqual(self.story()['result']['mission'], 'success')

    def chapter5(self):
        self.read_dialogue()
        t = self.story()['training']
        rid = t['status']['rid']
        self.no(type='lab_next_stage')                                    # Stage 1 not passed yet
        self.start(rid, req(self.game, rid)['conditions']['requestedMode'])
        self.advance_until(lambda: req(self.game, rid)['stage'] == 'net_fault')
        self.t.assertIn('Stage 5', self.no(type='respond', rid=rid, key='reroute')['message'])
        self.t.assertTrue(req(self.game, rid)['network']['hidden'] and req(self.game, rid)['network']['available'] is None)
        self.t.assertTrue(all(v is None for v in self.story()['training']['network']['segments'].values()),
                          'the structure map hides the fault before Stage 1')
        wrong = self.ok(type='lab_segment', segment='edge-primary')['lab']
        self.t.assertFalse(wrong['correct'])
        self.t.assertTrue(self.ok(type='lab_segment', segment='primary-wan')['lab']['correct'])
        self.ok(type='lab_answer', stage='structure', question='impact', answer='blocked')
        self.ok(type='lab_next_stage')
        self.ok(type='lab_command', source='choice', stage='tool', payload='ping')
        self.ok(type='lab_answer', stage='tool', question='limit', answer='icmp')
        self.ok(type='lab_next_stage')
        self.no(type='lab_command', source='terminal', stage='assemble', payload='ping 10.0.0.20')   # wrong input type
        out = self.ok(type='lab_command', source='blocks', stage='assemble', payload=['ping', '-c 3', '10.0.0.20'])['lab']
        self.t.assertEqual(out['facts']['received'], 0)
        self.ok(type='lab_answer', stage='assemble', question='received', answer=out['facts']['received'])
        self.ok(type='lab_next_stage')
        bad = self.ok(type='lab_command', source='terminal', stage='terminal', payload='rm -rf /')['lab']
        self.t.assertFalse(bad['ok'])
        for line in ('ping -c 2 192.168.10.1', 'ping -c 2 10.0.0.20', 'ip route'):
            self.t.assertTrue(self.ok(type='lab_command', source='terminal', stage='terminal', payload=line)['lab']['ok'])
        statements = self.story()['training']['status']['statements']
        truth = {'near': 'confirmed', 'remote': 'confirmed', 'route': 'confirmed', 'line_cut': 'unknown', 'server_down': 'unknown'}
        self.ok(type='lab_answer', stage='terminal', question='facts', answer={k: truth[k] for k, _ in statements})
        self.ok(type='lab_next_stage')
        for line in ('ping -c 2 10.0.0.20', 'ip route'):
            self.ok(type='lab_command', source='terminal', stage='independent', payload=line)
        wrong = self.ok(type='lab_answer', stage='independent', question='cause', answer='server')['lab']
        self.t.assertFalse(wrong['correct'])
        locked = self.no(type='respond', rid=rid, key='reroute')['message']
        self.t.assertIn('Stage 5', locked)
        self.t.assertNotIn('Engineering Lab', locked, 'engine refusals are shown with the 3D place names')
        self.t.assertIn('[연수 · Lab] 탭', locked)
        self.ok(type='lab_answer', stage='independent', question='cause', answer='path_down')
        self.ok(type='respond', rid=rid, key='reroute')
        self.t.assertFalse(self.story()['done'], 'acting is not verifying')
        self.ok(type='lab_command', source='terminal', stage='independent', payload='ping -c 2 10.0.0.20')
        self.t.assertTrue(self.story()['done'])


class CampaignTests(Base):
    def setUp(self):
        super().setUp()
        self.dir = Path(self.tmp.name)

    def test_v2_snapshot_keeps_chapter1_fields_and_lists_the_campaign(self):
        story = self.host.new_game('story').snapshot()
        self.assertEqual((story['api'], story['apiCompat']), (2, [1]))
        st = story['story']
        self.assertEqual((st['chapterKey'], st['chapter']['label'], st['step'], st['jobsTotal']), (1, '제1장', 'arrival', 3))
        self.assertEqual([c['state'] for c in st['campaign']], ['in_progress', 'locked', 'locked', 'locked', 'locked'])
        self.assertEqual([c['label'] for c in st['campaign']], ['제1장', '제2장', '제3장', '제4장', '제5장'])
        self.assertTrue(st['retry']['available'])
        tutorial = self.host.new_game('tutorial').snapshot()['story']
        self.assertEqual(tutorial['chapter']['key'], 'tutorial')
        self.assertEqual(tutorial['campaign'], [])

    def test_next_chapter_is_refused_until_the_engine_says_so(self):
        game = self.host.new_game('story')
        d = Driver(self, game)
        d.no(type='start_next_chapter', chapter='2')
        tutorial = self.host.new_game('tutorial')
        self.assertFalse(self.act(tutorial, type='start_next_chapter', chapter='2')['ok'])
        d.chapter1()
        self.assertEqual(d.story()['next']['key'], 2)
        self.assertTrue(d.story()['next']['available'])
        d.no(type='start_next_chapter', chapter='3')                    # stale / wrong chapter
        d.next_chapter('2')
        d.no(type='start_next_chapter', chapter='2')                    # double click

    def test_full_regular_campaign_chapters_1_to_5(self):
        game = self.host.new_game('story')
        d = Driver(self, game)
        d.chapter1()
        d.next_chapter('2')
        d.chapter2_success()
        self.assertEqual(d.story()['result']['mission'], 'success')
        d.next_chapter('3')
        d.chapter3_success()
        d.next_chapter('3b')
        d.chapter3b_success()
        d.next_chapter('lab')
        d.chapter5()
        st = d.story()
        self.assertEqual(st['chapter']['state'], 'cleared')
        self.assertEqual([c['state'] for c in st['campaign']], ['cleared'] * 5)
        self.assertEqual(st['graduation']['title'], '운영 엔지니어 수료')
        self.assertEqual(len(st['graduation']['rows']), 5)
        self.assertIsNone(st['next'])
        for key in ('1', '2', '3', '3b', 'lab'):
            self.assertTrue((self.dir / f'aidc_checkpoint_{game.id}_ch{key}.db').is_file(), key)
        listing = next(s for s in self.host.saves() if s['id'] == game.id)
        self.assertEqual(listing['chapter']['number'], 5)
        self.assertEqual(listing['checkpoints'], ['1', '2', '3', '3b', 'lab'])

    def test_chapter2_failure_then_retry_in_a_new_slot(self):
        game = self.host.new_game('story')
        d = Driver(self, game)
        d.chapter1()
        d.next_chapter('2')
        d.read_dialogue()
        d.ok(type='confirm_briefing')
        jp, us = d.story()['chapter2']['requestIds']
        start_clock = d.snap()['clock']
        # Original conditions in a row: Japan high performance, then the US high performance after it.
        d.start(jp, 'performance', 0)
        r = d.no(type='select_plan', rid=us, mode='performance', index=0)
        self.assertIn('지금 시작할 수 없습니다', r['message'])
        d.advance_until(lambda: req(game, jp)['stage'] == 'done')
        d.start(us, 'performance', 0)
        d.advance_until(lambda: d.story()['chapter2']['failure'] is not None)
        st = d.story()
        self.assertEqual(st['chapter2']['failure']['reason'], 'late')
        self.assertTrue(st['chapter2']['failurePending'] and st['chapter2']['failurePages'])
        d.ok(type='ack_feedback', kind='chapter2')
        self.assertFalse(d.story()['chapter2']['failurePending'])
        d.advance_until(lambda: d.story()['done'], step=30)
        self.assertEqual(d.story()['chapter']['state'], 'failed')
        self.assertIsNone(d.story()['next'])
        game.session.save()
        original = sha(game.path)
        new = self.host.retry(game.id)
        self.assertNotEqual(new.id, game.id)
        self.assertEqual(sha(game.path), original, 'retry never touches the current slot')
        st = new.snapshot()['story']
        self.assertEqual((st['chapterKey'], st['uiStep']), (2, 'c2_briefing'))
        self.assertEqual(new.snapshot()['clock'], start_clock)
        self.assertEqual(st['campaign'][0]['state'], 'cleared', 'chapter 1 record kept in the copy')
        self.assertEqual(new.journey.data['origin'], {'source': game.id, 'chapter': '2'})
        self.assertTrue((self.dir / f'aidc_checkpoint_{new.id}_ch2.db').is_file(), 'the new slot can be retried again')

    def test_chapter3_three_wrong_responses_fail_and_offer_a_retry(self):
        game = self.host.new_game('story')
        d = Driver(self, game)
        d.chapter1(); d.next_chapter('2'); d.chapter2_success(); d.next_chapter('3')
        d.read_dialogue(); d.ok(type='confirm_briefing')
        a = d.story()['chapter3']['requestIds'][0]
        d.start(a, 'performance')
        d.advance_until(lambda: req(game, a)['stage'] == 'net_fault')
        d.ok(type='diagnose', rid=a)
        for _ in range(3):
            if req(game, a)['phase'] == 'finished':
                break
            d.ok(type='respond', rid=a, key='ignore')
            d.ack_pending()
            if req(game, a)['phase'] in ('incident', 'paused'):
                continue
            d.advance_until(lambda: req(game, a)['phase'] in ('finished', 'paused', 'incident'))
        d.advance_until(lambda: req(game, a)['phase'] == 'finished', step=30)
        card = d.story()['chapter3']['cards'][str(a)]
        self.assertTrue(card['can_retry'])
        self.assertTrue(d.story()['chapter3']['retryAvailable'])
        new = self.host.retry(game.id)
        self.assertEqual(new.snapshot()['story']['uiStep'], 'c3_briefing')

    def test_chapter3b_repair_on_the_tight_deadline_fails(self):
        game = self.host.new_game('story')
        d = Driver(self, game)
        d.chapter1(); d.next_chapter('2'); d.chapter2_success(); d.next_chapter('3'); d.chapter3_success()
        d.next_chapter('3b'); d.read_dialogue(); d.ok(type='confirm_briefing')
        jp = d.story()['chapter3b']['requestIds'][0]
        diagnosis = d.hardware(jp, 'repair')
        self.assertFalse(diagnosis['repair_on_time'])
        self.assertEqual(req(game, jp)['summary']['key'], 'late')
        sg = d.story()['chapter3b']['requestIds'][1]
        d.hardware(sg, 'repair')
        self.assertEqual(d.story()['result']['mission'], 'failed')
        self.assertIsNone(d.story()['next'], 'a failed chapter never unlocks the next one')
        self.assertTrue(d.story()['retry']['available'])

    def test_practice_saves_are_not_promotion_records(self):
        game = self.host.new_game('practice', '3b')
        snap = game.snapshot()
        self.assertEqual((snap['kind'], snap['story']['practice'], snap['story']['chapterKey']), ('practice', True, '3b'))
        self.assertEqual(snap['story']['campaign'], [])
        self.assertIn('제4장', snap['story']['chapter']['heading'])
        self.assertFalse(self.act(game, type='start_next_chapter', chapter='lab')['ok'])
        lab = self.host.new_game('practice', 'lab')
        self.assertEqual(lab.snapshot()['story']['training']['status']['practice'], True)
        self.assertFalse(Path(self.dir / f'aidc_checkpoint_{lab.id}_chlab.db').exists(), 'practice keeps no checkpoint')
        retry = self.host.retry(lab.id)
        self.assertEqual((retry.kind, retry.snapshot()['story']['chapterKey']), ('practice', 'lab'))
        with self.assertRaises(ValueError):
            self.host.new_game('practice', 1)

    def test_resume_after_closing_the_host_keeps_chapter_state(self):
        game = self.host.new_game('story')
        d = Driver(self, game)
        d.chapter1(); d.next_chapter('2'); d.read_dialogue(); d.ok(type='confirm_briefing')
        jp, us = d.story()['chapter2']['requestIds']
        d.start(jp, 'performance')
        d.ok(type='advance_time', minutes=10)
        before = game.snapshot()
        self.host.close()
        host = GameHost(self.dir)
        self.addCleanup(host.close)
        again = host.get(game.id).snapshot()
        self.assertEqual(json.dumps(before, sort_keys=True), json.dumps(again, sort_keys=True))

    def test_missing_checkpoint_and_corrupted_slot_are_reported_without_changes(self):
        game = self.host.new_game('story')
        checkpoint = self.dir / f'aidc_checkpoint_{game.id}_ch1.db'
        checkpoint.unlink()
        with self.assertRaises(ValueError) as ctx:
            self.host.retry(game.id)
        self.assertIn('체크포인트', str(ctx.exception))
        self.assertFalse(game.snapshot()['story']['retry']['available'])
        # A damaged slot: copy it, break the payload, try to open — the error is reported and the file is unchanged.
        self.host.close(game.id)
        broken = self.dir / 'aidc_story_slot_900.db'
        shutil.copy(game.path, broken)
        shutil.copy(self.dir / f'{game.id}.3d.json', self.dir / 'aidc_story_slot_900.3d.json')
        with sqlite3.connect(broken) as c:
            c.execute("UPDATE simulation_state SET payload='{\"mode\":\"story\",\"story\":{\"request_id\":999}}' WHERE id=1")
        c.close()
        digest = sha(broken)
        with self.assertRaises(ValueError):
            self.host.get('aidc_story_slot_900')
        self.assertEqual(sha(broken), digest)
        self.assertNotIn('aidc_story_slot_900', self.host.games)

    def test_lock_prevents_a_second_host_and_a_checkpoint_start_leaves_the_source(self):
        game = self.host.new_game('story')
        other = GameHost(self.dir)
        self.addCleanup(other.close)
        with self.assertRaises(Exception):
            other.get(game.id)
        digest = sha(game.path)
        copy = self.host.start_checkpoint(game.id, '1')
        self.assertNotEqual(copy.id, game.id)
        self.assertEqual(sha(game.path), digest)
        with self.assertRaises(ValueError):
            self.host.start_checkpoint(game.id, '2')


if __name__ == '__main__':
    unittest.main()
