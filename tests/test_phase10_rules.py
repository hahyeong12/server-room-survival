"""Phase 10 operating rules: one deadline formula, all affected customers, explicit handoff, rolled-back forecast.

Every rule applies to new saves (`ops_rules` stamp). Saves written before Phase 10 keep the published rules; the
tests build such a save with tests.phase10_support.legacy and check the old judgement is unchanged.
"""
import unittest

from game import MODE_SPEEDS
from result_summary import outcome_key
from aidc.incidents import phase10
from aidc.incidents.session import IncidentSession, FINAL
from aidc.incidents.operating_rules import OperatingRules, ceil10
from aidc.global_ops.free_session import FreeShiftSession
from aidc.learning.career import assess
from tests.incident_support import Temp, C, start_open, diagnose, fix, finish, observe, where
from tests.phase10_support import legacy, payload_bytes

TYPES = ('dns', 'tor_uplink', 'congestion', 'gpu_health', 'gpu_oom', 'storage_full', 'storage_latency', 'crashloop', 'cooling', 'ups')


class Phase9Practice(OperatingRules, IncidentSession):
    """The production Phase 9 overlay (free shifts / senior) on an isolated practice case."""


def triggered(s):
    if not s.global_.briefed:
        s.confirm_shift_briefing()
    start_open(s)
    rec = s.incident.records[0]
    for _ in range(60):
        if rec.state != 'armed':
            break
        s.advance_time(10)
    assert rec.state == 'alert', rec.state
    return rec


def practice(temp, cause, cls=IncidentSession, name=None):
    return cls(temp.db(name or f'{cls.__name__}-{cause}-{len(temp.dbs)}.db'), practice=cause, seed=5)


class DeadlineTests(unittest.TestCase):
    def setUp(self):
        self.temp = Temp()
        self.addCleanup(self.temp.cleanup)

    def _oom(self, s, minutes_at_08):
        rec = triggered(s)
        run, st = s.runs[rec.rid], s.runs[rec.rid].state
        diagnose(s, rec)
        st.work_done = st.work_total - minutes_at_08 * MODE_SPEEDS[st.plan] * 0.8
        return rec, run, st

    def test_legacy_floor_approved_a_late_batch_change_and_phase10_does_not(self):
        """Reproduction: 0.625 minutes of 0.8x work floored to 0 under the published Phase 7 formula, so the customer
        agreed to a due time the job then missed by 10 minutes. The Phase 10 save uses the 10-minute ceiling."""
        old = legacy(self.temp, lambda db: IncidentSession(db, practice='gpu_oom', seed=5), 'legacy-oom.db')
        rec, run, st = self._oom(old, 0.625)
        run.terms['due'] = old.minute + 10
        self.assertEqual(old._consent_finish(run), old.minute + 10, 'published Phase 7 estimate kept for old saves')
        self.assertEqual(old.incident_act(rec.id, 'ask_consent')['consent'], 'accepted')
        self.assertEqual(old.incident_act(rec.id, 'reduce_batch')['result'], 'fix')
        while st.phase != 'finished':
            old.advance_time(10)
        self.assertEqual(outcome_key(run), 'late', 'the old formula promised a time the clock could not meet')

        new = practice(self.temp, 'gpu_oom')
        self.assertTrue(new.rules10)
        rec, run, st = self._oom(new, 0.625)
        run.terms['due'] = new.minute + 10
        self.assertEqual(new._consent_finish(run), new.minute + 20)
        self.assertEqual(new.incident_act(rec.id, 'ask_consent')['consent'], 'rejected')

    def test_same_state_same_estimate_in_every_mode(self):
        values = (0.5, 0.625, 10, 60, 60.000000001, 60.5, 61, 99.9)
        for x in values:
            estimates = set()
            for cls in (IncidentSession, Phase9Practice):
                s = practice(self.temp, 'gpu_oom', cls)
                rec, run, st = self._oom(s, x)
                estimates.add(s._consent_finish(run) - s.minute)
            with self.subTest(x=x):
                self.assertEqual(estimates, {10 + ceil10(x)})

    def test_finishing_exactly_at_the_due_minute_is_accepted_and_on_time(self):
        s = practice(self.temp, 'gpu_oom', Phase9Practice)
        rec, run, st = self._oom(s, 60)
        run.terms['due'] = s.minute + 10 + 60
        self.assertEqual(s.incident_act(rec.id, 'ask_consent')['consent'], 'accepted')
        self.assertEqual(s.incident_act(rec.id, 'reduce_batch')['result'], 'fix')
        while st.phase != 'finished':
            s.advance_time(10)
        self.assertEqual(run.terms['completed'], run.terms['due'])
        self.assertEqual(outcome_key(run), 'on_time')
        s2 = practice(self.temp, 'gpu_oom', Phase9Practice)
        rec2, run2, _ = self._oom(s2, 60)
        run2.terms['due'] = s2.minute + 10 + 50
        self.assertEqual(s2.incident_act(rec2.id, 'ask_consent')['consent'], 'rejected', 'one tick late is refused')

    def test_phase7_session_rechecks_the_deadline_when_the_batch_change_starts(self):
        s = practice(self.temp, 'gpu_oom')
        rec, run, st = self._oom(s, 40)
        run.terms['due'] = s.minute + 10 + 40
        self.assertEqual(s.incident_act(rec.id, 'ask_consent')['consent'], 'accepted')
        s.advance_time(10)
        entry = s.incident_act(rec.id, 'reduce_batch')
        self.assertEqual(entry['result'], 'refused')
        self.assertTrue(entry.get('condition'))
        self.assertFalse(assess(s)['unsafe'])


class SharedIncidentTests(unittest.TestCase):
    def setUp(self):
        self.temp = Temp()
        self.addCleanup(self.temp.cleanup)

    def _two_jobs(self, s, cause):
        """Practice case plus a second customer on the same cooling zone / UPS feed (white-box second arrival)."""
        s.confirm_shift_briefing()
        start_open(s)
        first = s.runs[next(iter(s.runs))]
        feed = C.topology['coolingZones' if cause == 'cooling' else 'upsFeeds']
        group = next(m for m in feed.values() if set(m) & {p.server_id for p in s._alloc(first).slices})
        tid = 'ams-polder-eval'      # small enough for the free part of the same zone/feed
        with s._atomic():
            rid = s._receive(s.global_.missions[tid], f'test-second:{tid}')
        run = s.runs[rid]
        s.select(rid)
        s.read_conversation(rid)
        for mode in run.conditions['allowed_modes']:
            opts = [o for o in s.allocation_options(run, mode)['options'] if {p.server_id for p in o} <= set(group)]
            if opts:
                s.choose_plan(mode, opts[0])
                break
        self.assertTrue(run.state.allocated, 'second job placed on the same shared facility')
        rec = s.incident.records[0]
        for _ in range(60):
            if rec.state != 'armed':
                break
            s.advance_time(10)
        return rec, rid

    def test_notice_reaches_every_affected_customer_and_counts_for_each(self):
        s = practice(self.temp, 'cooling')
        rec, second = self._two_jobs(s, 'cooling')
        if second not in s._affected(rec):
            self.skipTest('the second job was not placed in the cooling zone of the primary server')
        self.assertEqual(rec.impacted, sorted({rec.rid, second}))
        s.incident_ack(rec.id)
        entry = s.incident_act(rec.id, 'notify_customer')
        self.assertIn('영향 고객 2곳', entry['text'])
        rows = s.customer_notices(rec)
        self.assertEqual({r['rid'] for r in rows if r['notified']}, {rec.rid, second})
        self.assertTrue(s.notified_before_recovery(rec))
        self.assertTrue(s.runs[second].last_feedback, 'the second customer received the notice too')

    def test_one_notice_to_the_primary_only_does_not_count_for_a_shared_incident(self):
        s = practice(self.temp, 'ups')
        rec, second = self._two_jobs(s, 'ups')
        if second not in s._affected(rec):
            self.skipTest('the second job was not placed on the UPS feed of the primary server')
        s.incident_ack(rec.id)
        rec.notices.append([s.minute, rec.rid])     # a notice that reached only the incident's own customer
        rec.notified.append(s.minute)
        self.assertFalse(s.notified_before_recovery(rec))
        self.assertEqual([c['rid'] for c in s.customer_notices(rec) if not c['notified']], [second])

    def test_post_recovery_window_waits_while_any_affected_job_runs(self):
        s = practice(self.temp, 'cooling')
        rec, second = self._two_jobs(s, 'cooling')
        if second not in s._affected(rec):
            self.skipTest('no shared placement')
        rec.recovered = s.minute
        s.runs[rec.rid].state.phase = 'finished'      # white-box: the incident's own job is done, the other still runs
        self.assertEqual(s.post_since(rec), rec.recovered + 10)
        old = legacy(self.temp, lambda db: IncidentSession(db, practice='cooling', seed=5), 'legacy-cool.db')
        rec2 = old.incident.records[0]
        rec2.recovered = old.minute
        old.runs[rec2.rid].state.phase = 'finished'
        self.assertEqual(old.post_since(rec2), rec2.recovered, 'published rule: the own request only')

    def test_legacy_save_keeps_the_primary_only_rule_and_record_shape(self):
        old = legacy(self.temp, lambda db: IncidentSession(db, practice='dns', seed=5), 'legacy-dns.db')
        rec = triggered(old)
        old.incident_ack(rec.id)
        old.incident_act(rec.id, 'notify_customer')
        saved = old.db.get_simulation()
        self.assertNotIn('ops_rules', saved)
        self.assertNotIn('impacted', saved['incident']['records'][0])
        self.assertTrue(old.notified_before_recovery(rec))


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = Temp()
        self.addCleanup(self.temp.cleanup)

    def test_unresolved_incident_used_to_hold_the_shift_forever(self):
        """Reproduction of the stuck rule: before Phase 10 an unresolved blocking incident never ends the work."""
        old = legacy(self.temp, lambda db: IncidentSession(db, practice='dns', seed=5), 'stuck.db')
        rec = triggered(old)
        for _ in range(60):
            old.advance_time(60)
        self.assertIsNone(old.global_.result)
        self.assertNotEqual(old.runs[rec.rid].state.phase, 'finished')
        self.assertIsNone(old.handoff_view())
        with self.assertRaises(ValueError):
            old.handoff_shift()

    def test_responsible_handoff_ends_the_shift_but_is_never_a_resolution(self):
        s = practice(self.temp, 'dns', name='handoff.db')
        rec = triggered(s)
        s.incident_ack(rec.id)
        s.incident_act(rec.id, 'notify_customer')
        view = s.handoff_view()
        self.assertTrue(view['available'], view['reason'])
        self.assertEqual([x['class'] for x in view['incidents']], ['handover'])
        result = s.handoff_shift()
        self.assertFalse(result['cleared'])
        self.assertEqual(result['resolved'], 0)
        self.assertEqual(result['handoff']['handedOver'], 1)
        self.assertNotIn(s.record(rec.id).state, FINAL, 'the incident stays unresolved, not hidden')
        self.assertEqual(assess(s)['operations']['items']['recovery'], 0)
        self.assertEqual(assess(s)['handedOver'], [rec.id])
        before = payload_bytes(s)
        for call in (lambda: s.advance_time(10), lambda: s.incident_act(rec.id, 'dns_failover'),
                     lambda: s.incident_observe(rec.id, 'dns', where('dns')), lambda: s.handoff_shift()):
            with self.assertRaises(ValueError):
                call()
        self.assertEqual(before, payload_bytes(s))
        s.db.close()
        again = IncidentSession(self.temp.db('handoff.db'))
        self.assertTrue(again.handed_off())
        self.assertEqual(again.global_.result['handoff']['handedOver'], 1)
        with self.assertRaises(ValueError):
            again.advance_time(10)

    def test_handoff_without_telling_the_customer_is_recorded_as_neglect(self):
        s = practice(self.temp, 'storage_full')
        rec = triggered(s)
        view = s.handoff_view()
        self.assertEqual(view['incidents'][0]['class'], 'neglect')
        self.assertIn('범위 확인 안 함', view['incidents'][0]['missing'])
        result = s.handoff_shift()
        self.assertEqual(result['handoff']['neglected'], 1)
        self.assertTrue(any('방치' in line for line in result['feedback']))
        self.assertEqual(assess(s)['neglected'], [rec.id])
        self.assertEqual(assess(s)['operations']['items']['communication'], 0)

    def test_handoff_waits_for_the_scheduled_arrivals(self):
        s = IncidentSession(self.temp.db('shift1.db'), shift=1, seed=5)
        s.confirm_shift_briefing()
        self.assertIn('도착 예정', s.handoff_view()['reason'])
        with self.assertRaises(ValueError):
            s.handoff_shift()

    def test_handoff_needs_an_open_incident(self):
        s = practice(self.temp, 'dns')
        s.confirm_shift_briefing()
        start_open(s)
        self.assertIn('미해결 사건이 없습니다', s.handoff_view()['reason'])
        with self.assertRaises(ValueError):
            s.handoff_shift()
        self.assertIsNone(s.global_.result)

    def test_free_shift_handoff_stops_intake_and_fixes_the_result(self):
        s = FreeShiftSession(self.temp.db('free.db'), seed=91, difficulty='challenge')
        s.confirm_shift_briefing()
        for _ in range(40):
            start_open(s)
            if any(r.state == 'alert' for r in s.incident.records):
                break
            s.advance_time(10)
        rec = next(r for r in s.incident.records if r.state == 'alert')
        s.incident_ack(rec.id)
        s.incident_act(rec.id, 'notify_customer')
        result = s.handoff_shift()
        self.assertTrue(s.free_incidents['closing'])
        self.assertTrue(result['handoff']['incidents'])
        with self.assertRaises(ValueError):
            s.advance_time(10)
        s.db.close()
        again = FreeShiftSession(self.temp.db('free.db'))
        self.assertTrue(again.handed_off())


class ForecastTests(unittest.TestCase):
    def setUp(self):
        self.temp = Temp()
        self.addCleanup(self.temp.cleanup)

    def _diagnosed(self, cause, cls):
        s = practice(self.temp, cause, cls)
        rec = triggered(s)
        diagnose(s, rec)
        s.incident_act(rec.id, 'notify_customer')
        return s, rec

    def test_forecast_is_the_engine_result_and_changes_nothing(self):
        for cls in (IncidentSession, Phase9Practice):
            for cause in TYPES:
                with self.subTest(cls=cls.__name__, cause=cause):
                    s, rec = self._diagnosed(cause, cls)
                    before, minute = payload_bytes(s), s.minute
                    forecast = s.incident_forecast(rec.id)
                    self.assertEqual((payload_bytes(s), s.minute), (before, minute), 'forecast rolled back completely')
                    self.assertTrue(forecast['options'])
                    for option in forecast['options']:
                        if not option['feasible']:
                            continue
                        twin, trec = self._diagnosed(cause, cls)
                        steps = []
                        plan = twin._tdef(trec)['actions'][option['action']]
                        need = plan.get('requires', '')
                        if need.startswith('approval:'):
                            team = need[9:]
                            steps += [next(a for a, spec in C.actions.items() if spec['group'] == 'escalate' and spec.get('team') == team), '+10']
                        if need == 'consent':
                            steps.append('ask_consent')
                        steps.append(option['action'])
                        fix(twin, trec, steps)
                        rid = trec.rid
                        run = twin.runs[rid]
                        for _ in range(phase10.FORECAST_CAP // 10):
                            if run.state.phase == 'finished':
                                break
                            twin.advance_time(10)
                        job = next(j for j in option['jobs'] if j['rid'] == rid)
                        if run.state.phase == 'finished' and run.state.succeeded:
                            self.assertEqual(job['finishMinute'], run.terms['completed'], option['label'])
                        elif run.state.phase == 'finished':
                            self.assertEqual(job['risk'], 'fail', option['label'])
                        else:
                            self.assertEqual(job['risk'], 'stuck', option['label'])

    def test_workaround_and_root_fix_costs_are_visible_and_ordered_by_remaining_work(self):
        s, rec = self._diagnosed('dns', Phase9Practice)
        f = s.incident_forecast(rec.id)
        kinds = {o['action']: o for o in f['options']}
        self.assertEqual(kinds['dns_failover']['kind'], 'workaround')
        self.assertEqual(kinds['escalate_network']['kind'], 'fix')
        self.assertIn('처리량 0.7배', kinds['dns_failover']['residual'])
        quick, root = kinds['dns_failover']['jobs'][0], kinds['escalate_network']['jobs'][0]
        self.assertLess(quick['stopMinutes'], root['stopMinutes'])
        self.assertGreater(quick['slowMinutes'], root['slowMinutes'])
        self.assertEqual(f['baseline']['jobs'][0]['risk'], 'stuck', 'doing nothing never ends a blocking incident')

    def test_forecast_needs_a_diagnosis_and_a_phase10_save(self):
        s = practice(self.temp, 'dns')
        rec = triggered(s)
        s.incident_ack(rec.id)
        with self.assertRaises(ValueError):
            s.incident_forecast(rec.id)
        old = legacy(self.temp, lambda db: IncidentSession(db, practice='dns', seed=5), 'legacy-f.db')
        orec = triggered(old)
        diagnose(old, orec)
        with self.assertRaises(ValueError):
            old.incident_forecast(orec.id)

    def test_forecast_never_shows_future_arrivals_or_incidents(self):
        s = IncidentSession(self.temp.db('shift-f.db'), shift=1, seed=5)
        s.confirm_shift_briefing()
        start_open(s)
        rec = s.incident.records[0]
        for _ in range(30):
            if rec.state == 'alert':
                break
            s.advance_time(10)
        diagnose(s, rec)
        runs, records = set(s.runs), [(r.id, r.state) for r in s.incident.records]
        f = s.incident_forecast(rec.id)
        self.assertEqual(set(s.runs), runs)
        self.assertEqual([(r.id, r.state) for r in s.incident.records], records)
        self.assertEqual({j['rid'] for o in f['options'] for j in o['jobs']}, {rec.rid})

    def test_ups_root_fix_alone_loses_the_job_and_the_forecast_says_so(self):
        s, rec = self._diagnosed('ups', IncidentSession)
        f = s.incident_forecast(rec.id)
        root = next(o for o in f['options'] if o['action'] == 'escalate_facility')
        self.assertEqual(root['jobs'][0]['risk'], 'fail', 'battery runs out before the 30-minute repair')
        self.assertEqual(root['incidentState'], 'failed', 'the forecast says the incident itself fails, not "no recovery yet"')


class SaveCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = Temp()
        self.addCleanup(self.temp.cleanup)

    def test_unknown_rule_stamp_is_refused_not_reinterpreted(self):
        db = self.temp.db('stamp.db')
        IncidentSession(db, practice='dns', seed=5)
        payload = db.get_simulation()
        payload['ops_rules'] = {'id': 'phase10-ops-v0', 'fingerprint': 'x'}
        with db.transaction():
            db.save_simulation(payload)
        with self.assertRaises(ValueError) as caught:
            IncidentSession(db)
        self.assertIn('다른 버전의 운영 규칙', str(caught.exception))

    def test_new_saves_carry_the_stamp_and_reopen(self):
        db = self.temp.db('new.db')
        s = IncidentSession(db, practice='dns', seed=5)
        self.assertEqual(db.get_simulation()['ops_rules'], phase10.stamp())
        rec = triggered(s)
        self.assertEqual(rec.impacted, [rec.rid])
        db.close()
        self.temp.dbs.remove(db)
        again = IncidentSession(self.temp.db('new.db'))
        self.assertTrue(again.rules10)
        self.assertEqual(again.record(rec.id).impacted, [rec.rid])


if __name__ == '__main__':
    unittest.main()
