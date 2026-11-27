"""Seeded free shifts: real engine effects, persistence, deterministic sampling and guardrails."""
import unittest
from copy import deepcopy
from unittest.mock import patch

from aidc.global_ops.free_session import FreeShiftSession
from tests.incident_support import Temp, start_open, diagnose, observe, C, fix


def tick(s, ticks=1):
    for _ in range(ticks):
        start_open(s)
        for rec in s.shift_records():
            if rec.state == 'alert':
                diagnose(s, rec)
                s.incident_act(rec.id, 'notify_customer')
                actions = {'gpu_health': ['gpu_repair'],
                           'gpu_oom': ['escalate_platform', '+10', 'memory_saving'],
                           'tor_uplink': ['escalate_network']}.get(rec.type)
                fix(s, rec, actions)
                if rec.type == 'ups':
                    for rid in s._affected(rec):
                        if rid not in rec.paused:
                            s.incident_act(rec.id, 'planned_pause', rid=rid)
            if rec.state == 'monitoring' and s.minute >= rec.recovered + 10:
                observe(s, rec.id, C.types[rec.type]['verify'])
                s.incident_verify(rec.id)
                s.incident_report(rec.id)
        s.advance_time(10)


class FreeIncidentTests(unittest.TestCase):
    def setUp(self):
        self.temp = Temp()
        self.addCleanup(self.temp.cleanup)

    def make(self, seed=5, difficulty='challenge', name=None):
        return FreeShiftSession(self.temp.db(name or f'free-{len(self.temp.dbs)}.db'), seed=seed, difficulty=difficulty)

    def test_briefing_lock_all_mutations(self):
        s = self.make()
        before = s.db.get_simulation()
        for action in (lambda: s.advance_time(10), s.accept_request, s.wait_request,
                       lambda: s.reject_request('시설 작업 대기'), s.end_free_shift):
            with self.assertRaisesRegex(ValueError, '브리핑'):
                action()
        self.assertEqual(before, s.db.get_simulation())

    def test_same_seed_actions_equal_db_state(self):
        a, b = self.make(91), self.make(91)
        a.confirm_shift_briefing()
        b.confirm_shift_briefing()
        tick(a, 50)
        tick(b, 50)
        self.assertTrue(a.incident.records)
        self.assertEqual(a.db.get_simulation(), b.db.get_simulation())
        for table in ('customer_requests', 'playthroughs'):
            rows = lambda s: [dict(r) for r in s.db.conn.execute(f'SELECT * FROM {table}')]
            # SQLite wall-clock audit fields are volatile; virtual contract times remain in simulation JSON above.
            clean = lambda rs: [{k: v for k, v in r.items() if k not in
                                ('created_at', 'updated_at', 'received_at', 'started_at', 'finished_at')} for r in rs]
            self.assertEqual(clean(rows(a)), clean(rows(b)))

    def test_no_incidents_and_end_does_not_reward(self):
        s = self.make(difficulty='none')
        s.confirm_shift_briefing()
        tick(s, 8)
        self.assertEqual(s.incident.records, [])
        s.end_free_shift()
        count = len(s.runs)
        for _ in range(40):
            if s.global_.result:
                break
            tick(s)
        self.assertIsNotNone(s.global_.result)
        self.assertFalse(s.global_.result['regular'])
        self.assertEqual(len(s.runs), count)
        with self.assertRaisesRegex(ValueError, '마친 교대'):
            s.advance_time(10)

    def test_restart_keeps_schedule_and_effects(self):
        s = self.make(7, name='restart.db')
        s.confirm_shift_briefing()
        for _ in range(20):
            start_open(s)
            s.advance_time(10)
            if s.incident.records:
                break
        self.assertTrue(s.incident.records)
        before = deepcopy(s.db.get_simulation())
        s.db.close()
        restored = FreeShiftSession(self.temp.db('restart.db'))
        self.assertEqual(before, restored.db.get_simulation())
        self.assertEqual(restored.free_incidents, s.free_incidents)
        self.assertEqual(restored.incident.payload(), s.incident.payload())

    def test_ten_types_reachable_and_seeds_differ(self):
        found, layouts = set(), set()
        for seed in range(12):
            s = self.make(seed)
            s.confirm_shift_briefing()
            tick(s, 55)
            events = s.free_incidents['events']
            found.update(e['type'] for e in events)
            layouts.add(tuple((e['minute'], e['type'], e['rid']) for e in events))
            self.assertLessEqual(s.free_status()['openIncidents'], 2)
        self.assertEqual(found, set(C.types))
        self.assertGreater(len(layouts), 1)

    def test_cursor_atomic_rollback(self):
        s = self.make()
        s.confirm_shift_briefing()
        start_open(s)
        before = deepcopy(s.db.get_simulation())
        with patch.object(s.db, 'save_simulation', side_effect=OSError('disk')):
            with self.assertRaises(OSError):
                s.advance_time(60)
        self.assertEqual(before, s.db.get_simulation())
        self.assertEqual(before['free_incidents'], s.free_incidents)
        self.assertEqual(before['incident'], s.incident.payload())

    def test_natural_overlap_bounded_and_same_tick_cannot_duplicate(self):
        maximum = 0
        for seed in range(5):
            s = self.make(seed)
            s.confirm_shift_briefing()
            for _ in range(20):
                start_open(s)
                s.advance_time(10)
                count = s.free_status()['openIncidents']
                self.assertLessEqual(count, 2)
                maximum = max(maximum, count)
                events = deepcopy(s.free_incidents['events'])
                self.assertFalse(s._arm())
                self.assertEqual(events, s.free_incidents['events'])
        self.assertEqual(maximum, 2)

    def test_rejected_options_and_legacy_reader_protect_new_save(self):
        from aidc.global_ops.session import GlobalSession
        for seed, difficulty in ((True, 'standard'), (-1, 'standard'), (2**31, 'none'), (1, []), (1, 'unknown')):
            with self.assertRaises(ValueError):
                self.make(seed, difficulty)
        s = self.make()
        before = deepcopy(s.db.get_simulation())
        with self.assertRaisesRegex(ValueError, 'FreeShiftSession'):
            GlobalSession(s.db)
        self.assertEqual(before, s.db.get_simulation())

    def test_wrapup_stops_new_incidents_but_finishes_running_work(self):
        s = self.make()
        s.confirm_shift_briefing()
        start_open(s)
        self.assertTrue(s._eligible())
        s.end_free_shift()
        count = len(s.runs)
        for _ in range(25):
            if s.global_.result:
                break
            start_open(s)
            s.advance_time(10)
        self.assertTrue(s.global_.result)
        self.assertEqual(count, len(s.runs))
        self.assertEqual(s.free_incidents['events'], [])
        self.assertEqual(s.incident.records, [])
        s.mark_shift_seen('shiftfree')
        s.mark_shift_seen('shiftfree')
        self.assertEqual(s.global_.seen, ['shiftfree'])


if __name__ == '__main__':
    unittest.main()
