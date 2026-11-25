"""Phase 6 (Issue #7) global shifts through the 3D adapter only (the same actions the browser sends).

Graduation gate, snapshot fields (site / client / job per request, world paths per city), a city click that
selects that city's request, the three shifts in one save, a shift retry into a new slot (source unchanged),
resume after closing the host, and damaged / foreign saves. Temporary folders only.
"""
import sqlite3
import unittest
from pathlib import Path

from engine.adapter import GameHost
from engine.tests.test_adapter import Base, sha
from engine.tests.test_campaign import Driver

ORDER = {   # same decisions as tests/test_global_shifts.PLANS, expressed as 3D actions
    1: [(0, [('start', 'KR-SEL', 'performance'), ('start', 'US-SFO', 'performance')]), (30, [('start', 'DE-FRA', 'performance')]),
        (40, [('wait', 'US-SEA', None)]), (60, [('start', 'JP-OSA', 'performance')]), (70, [('start', 'US-SEA', 'performance')])],
    2: [(0, [('propose', 'US-IAD', False), ('propose', 'IN-BLR', True), ('start', 'US-IAD', 'performance'), ('start', 'IN-BLR', 'economy')]),
        (20, [('wait', 'KR-PUS', None)]), (50, [('wait', 'GB-LON', None)]),
        (80, [('start', 'GB-LON', 'performance'), ('start', 'NL-AMS', 'performance')]), (90, [('wait', 'TW-TPE', None)]),
        (100, [('start', 'TW-TPE', 'performance')]), (120, [('start', 'KR-PUS', 'performance')])],
    3: [(0, [('propose', 'KR-DJN', True), ('propose', 'AU-SYD', True), ('start', 'KR-DJN', 'economy'), ('start', 'AU-SYD', 'economy')]),
        (20, [('start', 'SG-SIN', 'performance')]), (40, [('wait', 'IN-BOM', None)]), (60, [('start', 'US-NYC', 'economy')]),
        (90, [('start', 'FR-PAR', 'performance')]), (120, [('start', 'IN-BOM', 'performance')])],
}


class GlobalBase(Base):
    def graduate(self):
        game = self.host.new_game('story')
        d = Driver(self, game)
        d.chapter1(); d.next_chapter('2'); d.chapter2_success(); d.next_chapter('3'); d.chapter3_success()
        d.next_chapter('3b'); d.chapter3b_success(); d.next_chapter('lab'); d.chapter5()
        self.assertTrue(game.snapshot()['story']['graduation'])
        return game

    def rid(self, game, site):
        g = game.snapshot()
        ids = g['global']['requestIds'] if g['global']['kind'] == 'shift' else [r['id'] for r in g['requests']]
        return next(r['id'] for r in g['requests'] if r['code'] == site and r['id'] in ids)

    def play_shift(self, game, number):
        d = Driver(self, game)
        snap = game.snapshot()
        self.assertEqual(snap['global']['shift'], number)
        d.ok(type='confirm_briefing')
        start = snap['clock']['minute']
        for _ in range(40):
            t = game.snapshot()['clock']['minute'] - start
            for at, acts in ORDER[number]:
                if at != t:
                    continue
                for kind, site, arg in acts:
                    rid = self.rid(game, site)
                    if kind == 'start':
                        d.start(rid, arg)
                    elif kind == 'wait':
                        d.ok(type='wait_request', rid=rid)
                    elif kind == 'propose':
                        d.ok(type='propose_alternative', rid=rid)
                        reply = d.ok(type='check_reply', rid=rid)
                        self.assertIn('동의' if arg else '거절', reply['info'])
            if game.snapshot()['global']['done']:
                break
            d.ok(type='advance_time', minutes=10)
        result = game.snapshot()['global']['result']
        self.assertIsNotNone(result)
        return result


class GlobalAdapterTests(GlobalBase):
    def test_gate_then_three_shifts_in_one_save(self):
        r = self.act_host('global')
        self.assertFalse(r['ok'])
        self.assertIn('제5장', r['message'])
        self.assertFalse(self.host.unlocks()['global']['available'])
        self.graduate()
        self.assertTrue(self.host.unlocks()['global']['available'])
        game = self.host.new_game('global')
        snap = game.snapshot()
        self.assertEqual((snap['mode'], snap['kind'], snap['modeLabel']), ('global', 'global', '글로벌 교대 근무'))
        self.assertEqual(snap['api'], 2)
        self.assertIn('global', snap['features'])
        self.assertFalse(snap['canAdvance'], 'time waits for the shift briefing')
        r0 = snap['requests'][0]
        for key in ('site', 'client', 'job', 'catalog'):
            self.assertIn(key, r0)
        self.assertEqual({p['code'] for p in snap['world']['paths']}, {r['code'] for r in snap['requests']})
        for number in (1, 2, 3):
            result = self.play_shift(game, number)
            self.assertTrue(result['cleared'], result['feedback'])
            if number < 3:
                stale = self.act(game, type='start_next_shift', shift=number + 2)
                self.assertFalse(stale['ok'])
                Driver(self, game).ok(type='start_next_shift', shift=number + 1)
        g = game.snapshot()['global']
        self.assertEqual(len(g['history']), 2)
        self.assertEqual(g['nextReason'], '마지막 교대입니다.')
        row = next(x for x in self.host.saves() if x['id'] == game.id)
        self.assertEqual((row['kind'], row['describe']), ('global', '교대 3 · 독립 교대 · 클리어'))

    def act_host(self, mode):
        try:
            return {'ok': True, 'game': self.host.new_game(mode)}
        except ValueError as exc:
            return {'ok': False, 'message': str(exc)}

    def test_city_click_selects_that_city_and_cycles_two_requests(self):
        game = self.host.new_game('global_free')
        s = game.session
        # Two different customers in the same city (San Francisco): both are real engine requests.
        with s._atomic():
            for tid in ('sfo-bayfog-video', 'sfo-goldengate-finetune'):
                if not any(r.conditions['catalog']['template'] == tid for r in s.runs.values()):
                    s._receive(s.global_.missions[tid], f'test:{tid}')
        sfo = sorted(r['id'] for r in game.snapshot()['requests'] if r['code'] == 'US-SFO')
        self.assertEqual(len(sfo), 2)
        first = self.act(game, type='select_country', id='US-SFO')
        second = self.act(game, type='select_country', id='US-SFO')
        self.assertEqual({first['rid'], second['rid']}, set(sfo))
        self.assertIn('2건', first['info'])
        self.assertEqual(game.snapshot()['focus'], second['rid'])
        none = self.act(game, type='select_country', id='GB-LON')
        self.assertIn('없습니다', none['hint'])
        self.assertFalse(self.act(game, type='select_country', id='XX-XXX')['ok'])
        lit = [p['code'] for p in game.snapshot()['world']['paths']]
        self.assertEqual(lit.count('US-SFO'), 2, 'one path entry per request; the client groups them per city')
        self.assertNotIn('US', lit, 'never a single country pin for a city request')

    def test_retry_is_a_new_slot_and_resume_after_host_restart(self):
        self.graduate()
        game = self.host.new_game('global')
        d = Driver(self, game)
        d.ok(type='confirm_briefing')
        rid = self.rid(game, 'KR-SEL')
        d.start(rid, 'performance')
        d.ok(type='advance_time', minutes=30)
        before = game.snapshot()
        source = Path(game.path)
        digest = sha(source)
        new = self.host.retry(game.id)
        self.assertNotEqual(new.id, game.id)
        self.assertEqual(new.snapshot()['global']['shift'], 1)
        self.assertEqual(new.snapshot()['clock']['minute'], 540)
        self.assertEqual(new.journey.data['origin'], {'source': game.id, 'shift': 1})
        self.assertEqual(sha(source), digest, 'the retried save is untouched')
        gid = game.id
        self.host.close()
        host = GameHost(self.tmp.name)
        self.addCleanup(host.close)
        again = host.get(gid).snapshot()
        for key in ('clock', 'requests', 'servers', 'datacenter', 'global'):
            self.assertEqual(again[key], before[key], key)
        # The engine does not save which request was selected (same as every existing mode); only focus may differ.
        strip = lambda w: [{k: v for k, v in p.items() if k != 'focus'} for p in w['paths']]
        self.assertEqual(strip(again['world']), strip(before['world']))

    def test_kind_comes_from_the_save_and_free_ops_retry_is_not_a_shift(self):
        game = self.host.new_game('global_free')
        gid = game.id
        self.host.close(gid)
        self.host._kind = lambda path: 'global'          # a failed payload peek must not turn free ops into a shift save
        again = self.host.get(gid)
        self.assertEqual(again.kind, 'global_free')
        self.assertEqual(again.snapshot()['modeLabel'], '글로벌 자유 운영')
        retry = self.host.retry(gid)
        self.assertEqual(retry.kind, 'global_free', 'retrying free ops never opens a shift save without the gate')
        self.assertFalse(self.act(again, type='mark_shift_seen', key='shift1')['ok'])

    def test_damaged_and_foreign_saves_are_refused_without_change(self):
        game = self.host.new_game('global_free')
        path = Path(game.path)
        self.host.close(game.id)
        con = sqlite3.connect(path)
        con.execute("UPDATE simulation_state SET payload=json_set(payload,'$.global.version',99)")
        con.commit(); con.close()
        digest = sha(path)
        with self.assertRaises(ValueError):
            self.host.get(game.id)
        self.assertEqual(sha(path), digest)


if __name__ == '__main__':
    unittest.main()
