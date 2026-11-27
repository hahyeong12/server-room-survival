"""A/B operating strategies must differ in the real Python ledger, not in UI wording."""
import unittest
from aidc.incidents.session import IncidentSession
from aidc.incidents.operating_rules import OperatingRules
from tests.incident_support import Temp, start_open, diagnose, fix, finish

PATHS = {
    'dns': (['dns_failover'], ['escalate_network']),
    'tor_uplink': (['reroute_uplink'], ['escalate_network']),
    'congestion': (['qos_adjust'], ['escalate_network']),
    'gpu_health': (['isolate_migrate'], ['gpu_repair']),
    'gpu_oom': (['ask_consent', 'reduce_batch'], ['escalate_platform', '+10', 'memory_saving']),
    'storage_full': (['cleanup_temp'], ['escalate_platform', '+10', 'expand_storage']),
    'storage_latency': (['storage_path'], ['escalate_platform']),
    'crashloop': (['escalate_platform', '+10', 'rollback_deploy'], ['escalate_platform', '+10', 'config_fix']),
}


class Phase9Practice(OperatingRules, IncidentSession):
    """Test the exact production Phase9 rule overlay on isolated individual cases."""


class OperatingBranchesTests(unittest.TestCase):
    def test_eight_legal_ab_paths_change_time_or_resources_and_persist(self):
        temp = Temp()
        self.addCleanup(temp.cleanup)
        for cause, paths in PATHS.items():
            states = []
            for i, path in enumerate(paths):
                with self.subTest(cause=cause, path=i):
                    name = f'{cause}-{i}.db'
                    s = Phase9Practice(temp.db(name), practice=cause, seed=5)
                    s.confirm_shift_briefing()
                    start_open(s)
                    rec = s.incident.records[0]
                    while rec.state == 'armed':
                        s.advance_time(10)
                    diagnose(s, rec)
                    s.incident_act(rec.id, 'notify_customer')
                    entries = fix(s, rec, path)
                    self.assertFalse(any(e['result'] in ('none', 'refused') for e in entries), entries)
                    finish(s, rec)
                    self.assertEqual(rec.state, 'closed')
                    run = s.runs[rec.rid]
                    states.append((rec.recovered, rec.downtime, rec.slow_minutes,
                                   [a.payload() if hasattr(a, 'payload') else str(a) for a in run.server_allocations]))
                    saved = s.db.get_simulation()
                    s.db.close()
                    restored = Phase9Practice(temp.db(name))
                    self.assertEqual(saved, restored.db.get_simulation())
                    self.assertEqual(restored.record(rec.id).state, 'closed')
            self.assertNotEqual(states[0], states[1], cause)

    def _finish_minute(self, cause, path, remaining=None):
        """Play one practice case to job completion. remaining: set remaining normal-speed minutes at diagnosis (white-box)."""
        from game import MODE_SPEEDS
        temp = Temp()
        self.addCleanup(temp.cleanup)
        s = Phase9Practice(temp.db('x.db'), practice=cause, seed=5)
        s.confirm_shift_briefing()
        start_open(s)
        rec = s.incident.records[0]
        while rec.state == 'armed':
            s.advance_time(10)
        run = s.runs[rec.rid]
        if remaining is not None:
            # Emulate a shorter/longer remaining job of the same customer at the moment of diagnosis.
            st = run.state
            st.work_done = st.work_total - remaining * MODE_SPEEDS[st.plan]   # may be < 0: a longer job of the same customer
        diagnose(s, rec)
        fix(s, rec, path)
        for _ in range(60):
            if run.state.phase == 'finished':
                break
            s.advance_time(10)
        self.assertEqual(run.state.phase, 'finished')
        self.assertTrue(run.state.succeeded)
        return s.minute, rec

    def test_workaround_vs_root_fix_depends_on_remaining_work(self):
        """Neither path dominates at remaining work the game produces (free eligibility needs >= 20 min):
        the quick workaround wins with little work left, the root-cause fix with much work left."""
        cases = {'dns': (['dns_failover'], ['escalate_network']),
                 'tor_uplink': (['reroute_uplink'], ['escalate_network']),
                 'congestion': (['qos_adjust'], ['escalate_network']),
                 'crashloop': (['escalate_platform', '+10', 'rollback_deploy'], ['escalate_platform', '+10', 'config_fix']),
                 'storage_full': (['cleanup_temp'], ['escalate_platform', '+10', 'expand_storage']),
                 'storage_latency': (['storage_path'], ['escalate_platform']),
                 'gpu_oom': (['ask_consent', 'reduce_batch'], ['escalate_platform', '+10', 'memory_saving'])}
        for cause, (quick, root) in cases.items():
            with self.subTest(cause=cause):
                short_q, _ = self._finish_minute(cause, quick, remaining=20)
                short_r, _ = self._finish_minute(cause, root, remaining=20)
                long_q, lq = self._finish_minute(cause, quick, remaining=100)
                long_r, lr = self._finish_minute(cause, root, remaining=100)
                self.assertLess(short_q, short_r, 'little work left: quick workaround finishes first')
                self.assertGreater(long_q, long_r, 'much work left: root-cause fix finishes first')
                self.assertGreater(lq.slow_minutes, lr.slow_minutes, 'degraded running is recorded in the ledger')

    def test_residual_window_matches_displayed_minutes(self):
        _, rec = self._finish_minute('dns', ['dns_failover'], remaining=200)
        self.assertEqual(rec.slow_minutes, 90, 'the 90-minute window shown on screen is the window applied')

    def test_residual_follows_the_job_location_not_the_request_number(self):
        temp = Temp()
        self.addCleanup(temp.cleanup)
        s = Phase9Practice(temp.db('t.db'), practice='tor_uplink', seed=5)
        s.confirm_shift_briefing()
        start_open(s)
        rec = s.incident.records[0]
        while rec.state == 'armed':
            s.advance_time(10)
        run = s.runs[rec.rid]
        diagnose(s, rec)
        self.assertEqual(s.incident_act(rec.id, 'load_shed')['result'], 'move')
        s.advance_time(10)
        self.assertEqual(s.incident_act(rec.id, 'reroute_uplink')['result'], 'fix')
        while rec.state != 'monitoring':
            s.advance_time(10)
        self.assertFalse(set(s._job_servers(run)) & set(rec.servers))
        self.assertIsNone(s._job_hold(run), 'a job moved off the rerouted rack is not slowed')
        self.assertIsNone(s.incident_view(rec)['residual'])

    def test_reduce_batch_rechecks_deadline_after_consent(self):
        from game import MODE_SPEEDS
        from result_summary import outcome_key
        temp = Temp()
        self.addCleanup(temp.cleanup)
        s = Phase9Practice(temp.db('o.db'), practice='gpu_oom', seed=5)
        s.confirm_shift_briefing()
        start_open(s)
        rec = s.incident.records[0]
        while rec.state == 'armed':
            s.advance_time(10)
        run, st = s.runs[rec.rid], s.runs[rec.rid].state
        diagnose(s, rec)
        rem = st.work_total - st.work_done
        from aidc.incidents.operating_rules import ceil10
        run.terms['due'] = s.minute + 10 + ceil10(rem / (MODE_SPEEDS[st.plan] * 0.8))   # white-box: no slack
        self.assertEqual(s.incident_act(rec.id, 'ask_consent')['consent'], 'accepted')
        s.advance_time(10)
        refused = s.incident_act(rec.id, 'reduce_batch')
        self.assertEqual((refused['result'], refused.get('condition')), ('refused', True))
        self.assertEqual(s.incident_act(rec.id, 'reduce_batch')['seq'], refused['seq'], 'same-minute repeat is one record')
        from aidc.learning.career import _unsafe_refusal
        self.assertFalse(_unsafe_refusal(s, rec, refused), 'a deadline condition check is not a safety violation')
        # A different legal route still finishes the job.
        fix(s, rec, ['escalate_platform', '+10', 'memory_saving'])
        while st.phase != 'finished':
            s.advance_time(10)
        self.assertTrue(st.succeeded)

    def _oom_at(self, minutes, name):
        """gpu_oom practice under the Phase9 overlay with `minutes` of 0.8x work left (white-box remaining work)."""
        from game import MODE_SPEEDS
        temp = Temp()
        self.addCleanup(temp.cleanup)
        s = Phase9Practice(temp.db(name), practice='gpu_oom', seed=5)
        s.confirm_shift_briefing()
        start_open(s)
        rec = s.incident.records[0]
        while rec.state == 'armed':
            s.advance_time(10)
        run, st = s.runs[rec.rid], s.runs[rec.rid].state
        diagnose(s, rec)
        st.work_done = st.work_total - minutes * MODE_SPEEDS[st.plan] * 0.8
        return s, rec, run, st

    def test_consent_and_reduce_batch_use_the_real_10_minute_ceiling(self):
        """Review 3: int(x + 9) // 10 * 10 floored 60.5 minutes to 60, so an accepted batch change finished late."""
        from result_summary import outcome_key
        from aidc.incidents.operating_rules import ceil10
        self.assertEqual([ceil10(x) for x in (60.0, 60.000000001, 60.5, 60.99, 61, 0)], [60, 60, 70, 70, 70, 0])
        s, rec, run, st = self._oom_at(60.5, 'ceil-late.db')
        run.terms['due'] = s.minute + 10 + 60        # what the floored estimate promised
        self.assertEqual(s.incident_act(rec.id, 'ask_consent')['consent'], 'rejected', 'no promise of a late finish')
        s, rec, run, st = self._oom_at(60.5, 'ceil-ok.db')
        run.terms['due'] = s.minute + 10 + 70        # the time the 10-minute clock really needs
        self.assertEqual(s.incident_act(rec.id, 'ask_consent')['consent'], 'accepted')
        self.assertEqual(s.incident_act(rec.id, 'reduce_batch')['result'], 'fix')
        while st.phase != 'finished':
            s.advance_time(10)
        self.assertEqual(outcome_key(run), 'on_time')

    def test_legacy_incident_consent_estimate_is_unchanged(self):
        """The fix lives in the Phase9 overlay; published Phase 7 incident/Linux saves keep their consent estimate."""
        from game import MODE_SPEEDS
        temp = Temp()
        self.addCleanup(temp.cleanup)
        s = IncidentSession(temp.db('legacy.db'), practice='gpu_oom', seed=5)
        s.confirm_shift_briefing()
        start_open(s)
        rec = s.incident.records[0]
        while rec.state == 'armed':
            s.advance_time(10)
        run, st = s.runs[rec.rid], s.runs[rec.rid].state
        st.work_done = st.work_total - 60.5 * MODE_SPEEDS[st.plan] * 0.8
        self.assertEqual(s._consent_finish(run), s.minute + 10 + 60)

    def test_residual_is_visible_and_saved(self):
        temp = Temp()
        self.addCleanup(temp.cleanup)
        s = Phase9Practice(temp.db('r.db'), practice='dns', seed=5)
        s.confirm_shift_briefing()
        start_open(s)
        rec = s.incident.records[0]
        while rec.state == 'armed':
            s.advance_time(10)
        self.assertIsNone(s.incident_view(rec)['residual'])
        self.assertEqual(s.incident_view(rec)['actionNotes'], {}, 'no per-incident cost hints before the diagnosis')
        diagnose(s, rec)
        self.assertIn('임시 우회', s.incident_view(rec)['actionNotes']['dns_failover'])
        self.assertEqual(set(s.incident_view(rec)['actionNotes']), {'dns_failover'})
        fix(s, rec, ['dns_failover'])
        while rec.state != 'monitoring':
            s.advance_time(10)
        view = s.incident_view(rec)
        self.assertEqual(view['residual']['factor'], 0.7)
        self.assertIn('임시 우회 운전 중', s.reading(rec, 'dns')['lines'][-1], 'readings agree with the degraded state')
        self.assertEqual(s._job_hold(s.runs[rec.rid]), 0.7)
        saved = s.db.get_simulation()
        s.db.close()
        restored = Phase9Practice(temp.db('r.db'))
        self.assertEqual(restored._job_hold(restored.runs[rec.rid]), 0.7)
        self.assertEqual(saved, restored.db.get_simulation())
        for _ in range(10):
            restored.advance_time(10)
        self.assertIsNone(restored.incident_view(restored.record(rec.id))['residual'])

    def test_legacy_incident_session_has_no_residual(self):
        temp = Temp()
        self.addCleanup(temp.cleanup)
        s = IncidentSession(temp.db('l.db'), practice='dns', seed=5)
        s.confirm_shift_briefing()
        start_open(s)
        rec = s.incident.records[0]
        while rec.state == 'armed':
            s.advance_time(10)
        diagnose(s, rec)
        fix(s, rec, ['dns_failover'])
        while rec.state != 'monitoring':
            s.advance_time(10)
        self.assertIsNone(s._job_hold(s.runs[rec.rid]))
        self.assertNotIn('residual', s.incident_view(rec))


if __name__ == '__main__':
    unittest.main()
