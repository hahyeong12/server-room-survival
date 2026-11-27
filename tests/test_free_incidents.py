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

    def test_optional_cli_shares_incident_without_advancing_or_fixing(self):
        s = self.make(7, name='cli.db')
        s.confirm_shift_briefing()
        for _ in range(20):
            start_open(s)
            s.advance_time(10)
            if s.incident.records:
                break
        rec = s.incident.records[0]
        s.incident_ack(rec.id)
        before = (s.minute, s.free_incidents['cursor'], rec.state, rec.cause_active, s.runs[rec.rid].state.work_done)
        o = s.cli(rec.id, 'ip route', 'noc', s.token(rec))
        self.assertEqual(o['command_id'], 'ip_route')
        self.assertEqual(before, (s.minute, s.free_incidents['cursor'], rec.state, rec.cause_active, s.runs[rec.rid].state.work_done))
        self.assertTrue(s.learning_view()['optional'])
        self.assertNotIn('eligible', o)
        saved = deepcopy(s.db.get_simulation())
        s.db.close()
        restored = FreeShiftSession(self.temp.db('cli.db'))
        self.assertEqual(saved, restored.db.get_simulation())
        self.assertEqual(restored.linux, s.linux)


    def test_optional_cli_scores_per_incident_source(self):
        """Using the optional terminal for one incident must not zero the GUI-diagnosed incidents."""
        from aidc.learning.career import assess
        s = self.make(7, 'challenge')
        s.confirm_shift_briefing()
        for _ in range(30):
            start_open(s)
            s.advance_time(10)
            if s.incident.records and all(r.state == 'alert' for r in s.incident.records):
                break
        rec = s.incident.records[0]
        diagnose(s, rec)
        before = assess(s)['learning']
        s.cli(rec.id, 'ip route', 'noc', s.token(rec))
        after = assess(s)['learning']
        self.assertEqual(before['items']['interpretation'], 35)
        self.assertEqual(after['items']['interpretation'], 0, 'a used-but-unanswered CLI reading still scores 0')
        others = [r for r in s.incident.records if r is not rec]
        if others:
            diagnose(s, others[0])
            self.assertGreater(assess(s)['learning']['items']['interpretation'], 0)

    def _first_alert(self, seed=7):
        s = self.make(seed, 'challenge')
        s.confirm_shift_briefing()
        while not s.incident.records:
            start_open(s)
            s.advance_time(10)
        rec = s.incident.records[0]
        s.incident_ack(rec.id)
        observe(s, rec.id, list(C.probes))
        return s, rec

    def _cli_answer(self, s, rec, correct=True):
        from aidc.learning import linux_catalog as catalog
        o = s.cli(rec.id, 'ip route', 'noc', s.token(rec))
        spec = catalog.BY_ID[o['command_id']]
        obs = next(x for x in s.linux['observations'] if x['seq'] == o['seq'])
        pick = next(c['id'] for c in s.choices(obs) if (c['text'] == spec.correct) == correct)
        return s.interpret(rec.id, o['seq'], pick, s.token(rec))

    def test_wrong_first_answer_cannot_be_replaced_from_the_other_source(self):
        """Review 4B: a refuted first hypothesis followed by one right CLI answer used to score full interpretation."""
        from aidc.learning.career import assess
        s, rec = self._first_alert()
        wrong = next(c for c in C.causes if c != rec.type)
        self.assertEqual(s.incident_hypothesis(rec.id, wrong)['verdict'], 'refuted')
        self.assertEqual(s.incident_hypothesis(rec.id, rec.type)['verdict'], 'confirmed')
        self.assertEqual(assess(s)['learning']['items']['interpretation'], 0)
        self.assertTrue(self._cli_answer(s, rec)['correct'])
        self.assertEqual(assess(s)['learning']['items']['interpretation'], 0, 'the wrong first GUI answer still counts')
        # The other way round: a wrong first CLI reading is not rescued by a right hypothesis.
        s, rec = self._first_alert(seed=11)
        self.assertFalse(self._cli_answer(s, rec, correct=False)['correct'])
        self.assertEqual(s.incident_hypothesis(rec.id, rec.type)['verdict'], 'confirmed')
        self.assertEqual(assess(s)['learning']['items']['interpretation'], 0)
        # Both sources right on the first try: full credit.
        s, rec = self._first_alert(seed=13)
        self.assertTrue(self._cli_answer(s, rec)['correct'])
        self.assertEqual(s.incident_hypothesis(rec.id, rec.type)['verdict'], 'confirmed')
        self.assertEqual(assess(s)['learning']['items']['interpretation'], 35)

    def test_asking_consent_is_never_a_safety_violation(self):
        """Review 4A: ask_consent where no condition change is needed is refused, but asking is the safe action."""
        from aidc.learning.career import assess, _unsafe_refusal
        for seed in range(1, 40):
            s, rec = self._first_alert(seed)
            if rec.type != 'gpu_oom':
                break
        self.assertEqual(s.incident_hypothesis(rec.id, rec.type)['verdict'], 'confirmed')
        e = s.incident_act(rec.id, 'ask_consent')
        self.assertEqual(e['result'], 'refused')
        self.assertFalse(_unsafe_refusal(s, rec, e))
        self.assertEqual(assess(s)['operations']['items']['safety'], 20)
        bad = s.incident_act(rec.id, 'delete_data')
        self.assertTrue(_unsafe_refusal(s, rec, bad), 'policy refusals still count')
        self.assertEqual(assess(s)['operations']['items']['safety'], 0)
        self.assertEqual(assess(s)['unsafe'], ['delete_data'])

    def test_outdated_rule_save_is_refused_with_a_clear_reason(self):
        s = self.make(3, 'standard', name='old-rules.db')
        s.confirm_shift_briefing()
        payload = s.db.get_simulation()
        payload['free_incidents']['rules'] = 'old-phase9-rules'
        s.db.save_simulation(payload)
        s.db.close()
        with self.assertRaisesRegex(ValueError, '이전 버전의 Phase 9 운영·평가 규칙'):
            FreeShiftSession(self.temp.db('old-rules.db'))


if __name__ == '__main__':
    unittest.main()
