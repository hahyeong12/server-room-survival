"""Phase 7 (Issue #8): 사건 대응 엔진 — 콘텐츠·상태 기계·근거 판정·조치 효과·원장 일관성·저장/이어하기·교대 결과.

모든 판정은 IncidentSession(엔진) 메서드로만 진행합니다. 화면·브라우저 없이 실행됩니다.
"""
import json
import unittest
from copy import deepcopy
from pathlib import Path

from database import Database
from session import GameSession
from aidc.global_ops.session import GlobalSession
from aidc.global_ops.catalog import load as load_catalog
from aidc.incidents import content as content_mod
from aidc.incidents.content import load, Content, ContentError, type_fingerprint
from aidc.incidents.session import IncidentSession, FINAL
from tests.incident_support import C, FIX, Temp, where, observe, diagnose, fix, finish, start_open, play_shift, new_session


def started(t, itype, mode='performance', pick=None, seed=5):
    """연습 저장 하나: 브리핑 → 요청 읽기 → 배정 → 사건 경보까지 시간 진행."""
    s = new_session(t, practice=itype, seed=seed)
    s.confirm_shift_briefing()
    rid = next(iter(s.runs))
    s.select(rid)
    s.read_conversation(rid)
    opts = s.allocation_options(s.runs[rid], mode)['options']
    s.choose_plan(mode, pick(opts) if pick else opts[0])
    for _ in range(30):
        s.advance_time(10)
        if s.incident.records[0].state != 'armed':
            break
    return s, s.incident.records[0]


def primary_of(plan):
    return max(plan, key=lambda p: (p.gpu, -ord(p.server_id))).server_id


class Content10(unittest.TestCase):
    def test_ten_causes_five_domains_each_with_two_routes_and_distinct_evidence(self):
        self.assertGreaterEqual(len(C.types), 10)
        self.assertEqual({C.causes[t]['domain'] for t in C.types}, {'network', 'gpu', 'storage', 'facility', 'platform'})
        signatures = set()
        for tid, t in C.types.items():
            routes = [a for a, x in t['actions'].items() if x['result'] in ('fix', 'move', 'pause', 'isolate_move', 'isolate_repair')]
            self.assertGreaterEqual(len(routes), 2, tid)
            bad = tuple(sorted(p for p, r in t['readings'].items() if r['status'] == 'bad'))
            self.assertTrue(bad, tid)
            signatures.add((bad, t['effect']))
        self.assertEqual(len(signatures), len(C.types), 'every cause shows a different set of abnormal readings')

    def test_similar_symptoms_have_different_causes(self):
        by_symptom = {}
        for tid, t in C.types.items():
            by_symptom.setdefault(t['effect'], []).append(tid)
        self.assertGreaterEqual(len(by_symptom['blocked']), 3)
        self.assertGreaterEqual(len(by_symptom['slow']), 3)
        shift3 = [x[2] for x in C.shifts['3']['arrivals']]
        self.assertIn('congestion', shift3)
        self.assertIn('storage_latency', shift3)

    def test_three_shifts_cover_all_ten_and_v1_catalog_is_unchanged(self):
        used = [x[2] for s in C.shifts.values() for x in s['arrivals'] if x[2]]
        self.assertEqual(sorted(used), sorted(C.types))
        self.assertEqual([len([x for x in C.shifts[k]['arrivals'] if x[2]]) for k in '123'], [3, 3, 4])
        self.assertEqual([C.shifts[k]['coaching'] for k in '123'], ['full', 'short', 'none'])
        frozen = json.loads(Path('tests/global_catalog_v1_fingerprints.json').read_text(encoding='utf-8'))
        from aidc.global_ops.catalog import template_fingerprint
        cat = load_catalog()
        self.assertTrue(frozen)
        for tid, fp in (frozen.get('templates', frozen)).items():
            self.assertEqual(template_fingerprint(cat.templates[tid]), fp, tid)

    def test_invalid_content_is_refused(self):
        data = deepcopy(C.data)
        del data['types']['dns']['actions']['dns_failover']
        with self.assertRaises(ContentError):
            Content(data)
        data = deepcopy(C.data)
        data['shifts']['1']['arrivals'][0][2] = 'meteor'
        with self.assertRaises(ContentError):
            Content(data)
        data = deepcopy(C.data)
        data['types']['ups']['readings']['ups']['status'] = 'ok'
        with self.assertRaises(ContentError):
            Content(data)

    def test_fingerprint_changes_with_rules(self):
        data = deepcopy(C.data)
        before = type_fingerprint(data, 'cooling')
        data['types']['cooling']['limit'] = 50
        self.assertNotEqual(type_fingerprint(data, 'cooling'), before)


class EveryCause(unittest.TestCase):
    def setUp(self):
        self.t = Temp()

    def tearDown(self):
        self.t.cleanup()

    def test_each_cause_correct_path_evidence_cause_fix_verify_report(self):
        for itype in C.types:
            with self.subTest(itype):
                pick = None
                if itype == 'tor_uplink':
                    pick = lambda o: next(p for p in o if primary_of(p) in 'AB')
                s, rec = started(self.t, itype, pick=pick)
                self.assertEqual(rec.state, 'alert')
                rid = rec.rid
                view = s.incident_view(rec)
                self.assertIsNone(view['cause'])
                self.assertNotIn(C.causes[itype]['label'], json.dumps(view, ensure_ascii=False), 'no cause before diagnosis')
                self.assertEqual(diagnose(s, rec)['verdict'], 'confirmed')
                self.assertEqual(s.incident_view(rec)['causeLabel'], C.causes[itype]['label'])
                if itype == 'ups':
                    out = fix(s, rec)
                else:
                    out = fix(s, rec)
                self.assertFalse([o for o in out if o['result'] in ('none', 'refused')], out)
                report = finish(s, rec)
                self.assertIn(C.causes[itype]['label'], report['report'])
                self.assertEqual(s.record(rec.id).state, 'closed')
                for _ in range(30):
                    if s.global_.result:
                        break
                    s.advance_time(10)
                self.assertTrue(s.global_.result['cleared'])
                self.assertEqual(s.global_.result['incidents'][0]['outcome'], 'resolved')
                self.assertEqual(s.runs[rid].request['status'], 'completed')
                self.assertEqual(s.center.gpu_used, 0, 'resources returned')

    def test_trigger_is_deterministic_and_once(self):
        a, ra = started(self.t, 'dns', seed=1)
        b, rb = started(self.t, 'dns', seed=99)
        self.assertEqual(ra.detected, rb.detected)
        self.assertEqual(len(a.incident.records), 1)


class NoShortcut(unittest.TestCase):
    def setUp(self):
        self.t = Temp()

    def tearDown(self):
        self.t.cleanup()

    def test_actions_before_scope_and_diagnosis_are_blocked(self):
        s, rec = started(self.t, 'dns')
        with self.assertRaisesRegex(ValueError, '범위 확인'):
            s.incident_observe(rec.id, 'dns', 'noc')
        s.incident_ack(rec.id)
        before = s.minute
        with self.assertRaisesRegex(ValueError, '원인을 판단하기 전'):
            s.incident_act(rec.id, 'dns_failover')
        self.assertEqual((s.minute, s.record(rec.id).state), (before, 'investigating'))
        self.assertEqual(s.incident_act(rec.id, 'notify_customer')['result'], 'notice', 'customer updates are allowed any time')

    def test_observation_needs_the_right_place(self):
        s, rec = started(self.t, 'cooling')
        s.incident_ack(rec.id)
        with self.assertRaisesRegex(ValueError, '냉각 플랜트'):
            s.incident_observe(rec.id, 'cooling', 'noc')
        first = s.incident_observe(rec.id, 'cooling', 'COOLING')
        again = s.incident_observe(rec.id, 'cooling', 'COOLING')
        self.assertEqual(first['seq'], again['seq'], 'double click at the same minute records once')
        self.assertEqual(len(s.record(rec.id).evidence), 1)

    def test_hypothesis_needs_its_own_evidence_and_refutes_with_observed_values(self):
        s, rec = started(self.t, 'dns')
        s.incident_ack(rec.id)
        right = s.incident_hypothesis(rec.id, 'dns')
        wrong = s.incident_hypothesis(rec.id, 'transit')
        self.assertEqual((right['verdict'], wrong['verdict']), ('insufficient', 'insufficient'))
        self.assertEqual(right['reason'].split(':')[0], wrong['reason'].split(':')[0], 'same wording whatever the truth')
        observe(s, rec.id, ['ping'])
        self.assertEqual(s.incident_hypothesis(rec.id, 'dns')['verdict'], 'insufficient', 'ping alone does not prove DNS is fine or broken')
        observe(s, rec.id, ['link_stats'] if False else [])
        s.incident_observe(rec.id, 'link_stats', 'NETWORK')
        refuted = s.incident_hypothesis(rec.id, 'transit')
        self.assertEqual(refuted['verdict'], 'refuted')
        self.assertIn('IP 응답 3/3', refuted['reason'])
        s.incident_observe(rec.id, 'dns', 'noc')
        self.assertEqual(s.incident_hypothesis(rec.id, 'dns')['verdict'], 'confirmed')
        v = s.incident_view(s.record(rec.id))
        self.assertEqual(v['wrongHypotheses'], 1)
        with self.assertRaisesRegex(ValueError, '이미 확정'):
            s.incident_hypothesis(rec.id, 'crashloop')

    def test_wrong_action_costs_time_and_policy_refusals_are_recorded(self):
        s, rec = started(self.t, 'crashloop')
        diagnose(s, rec)
        out = s.incident_act(rec.id, 'restart_service')
        self.assertEqual(out['result'], 'none')
        with self.assertRaisesRegex(ValueError, '직전 조치 결과'):
            s.incident_act(rec.id, 'rollback_deploy')
        s.advance_time(10)
        self.assertEqual(s.incident_act(rec.id, 'rollback_deploy')['result'], 'refused', 'approval needed first')
        s.incident_act(rec.id, 'escalate_platform')
        self.assertIn('승인 대기', s.incident_act(rec.id, 'rollback_deploy')['text'])
        self.assertEqual(s.incident_act(rec.id, 'delete_data')['result'], 'refused')
        s.advance_time(10)
        self.assertEqual(s.incident_act(rec.id, 'rollback_deploy')['result'], 'fix')
        r = s.record(rec.id)
        self.assertEqual([a['result'] for a in r.actions], ['none', 'refused', 'call', 'refused', 'refused', 'fix'])
        self.assertGreater(r.downtime, 10, 'the wrong restart cost virtual time while the job stayed stopped')

    def test_verify_needs_recovery_a_quiet_window_and_re_observation_then_report(self):
        s, rec = started(self.t, 'storage_full')
        diagnose(s, rec)
        with self.assertRaisesRegex(ValueError, '아직 조치'):
            s.incident_verify(rec.id)
        fix(s, rec)
        with self.assertRaisesRegex(ValueError, '복구가 아직'):
            s.incident_verify(rec.id)
        s.advance_time(10)
        self.assertEqual(s.record(rec.id).state, 'monitoring')
        with self.assertRaisesRegex(ValueError, '10분'):
            s.incident_verify(rec.id)
        with self.assertRaisesRegex(ValueError, '사후 확인'):
            s.incident_report(rec.id)
        s.advance_time(10)
        with self.assertRaisesRegex(ValueError, '다시 관측'):
            s.incident_verify(rec.id)
        observe(s, rec.id, C.types['storage_full']['verify'])
        self.assertTrue(all(e['status'] == 'ok' and e['after'] for e in s.record(rec.id).evidence[-2:]))
        s.incident_verify(rec.id)
        s.incident_report(rec.id)
        self.assertEqual(s.record(rec.id).state, 'closed')


class Branches(unittest.TestCase):
    def setUp(self):
        self.t = Temp()

    def tearDown(self):
        self.t.cleanup()

    def test_tor_single_homed_rack_refuses_reroute_needs_network_team_or_move(self):
        # Economy (GPU 3) fits on C·D, whose ToR has a single uplink in the virtual layout.
        from aidc.core.server_resources import ServerSlice
        cd = (ServerSlice('C', (0, 1), 2), ServerSlice('D', (0,), 1))   # an explicit, valid plan (the engine re-validates it)
        s, rec = started(self.t, 'tor_uplink', mode='economy', pick=lambda o: cd)
        self.assertIn(rec.primary, 'CD')
        diagnose(s, rec)
        out = s.incident_act(rec.id, 'reroute_uplink')
        self.assertEqual(out['result'], 'refused')
        self.assertIn('업링크가 하나뿐', out['text'])
        moved = s.incident_act(rec.id, 'load_shed')
        self.assertEqual(moved['result'], 'move', 'moving the job off the isolated rack is a real alternative')
        self.assertTrue(set(moved['servers']) <= {'A', 'B'})
        self.assertEqual(s.record(rec.id).state, 'diagnosed', 'the port itself is still down: only mitigated')
        s.incident_act(rec.id, 'escalate_network')
        for _ in range(3):
            s.advance_time(10)
        self.assertEqual(s.record(rec.id).state, 'monitoring')

    def test_tor_dual_homed_reroute_vs_single_homed_move(self):
        s, rec = started(self.t, 'tor_uplink', pick=lambda o: next(p for p in o if primary_of(p) in 'AB'))
        diagnose(s, rec)
        self.assertEqual(s.incident_act(rec.id, 'reroute_uplink')['result'], 'fix')

    def test_oom_consent_accept_and_reject_paths(self):
        s, rec = started(self.t, 'gpu_oom')
        diagnose(s, rec)
        self.assertEqual(s.incident_act(rec.id, 'reduce_batch')['result'], 'refused', 'condition change needs consent')
        self.assertEqual(s.incident_act(rec.id, 'gpu_repair')['result'], 'none', 'GPU is healthy (DCGM PASS)')
        s.advance_time(10)
        consent = s.incident_act(rec.id, 'ask_consent')
        self.assertIn(consent['consent'], ('accepted', 'rejected'))
        r = s.record(rec.id)
        r.consent = 'rejected'   # the customer's other answer: the condition stays, platform memory saving is the way
        self.assertEqual(s.incident_act(rec.id, 'reduce_batch')['result'], 'refused')
        s.incident_act(rec.id, 'escalate_platform')
        s.advance_time(10)
        self.assertEqual(s.incident_act(rec.id, 'memory_saving')['result'], 'fix')

    def test_gpu_isolation_uses_the_existing_fault_and_repair_ledger(self):
        s, rec = started(self.t, 'gpu_health')
        diagnose(s, rec)
        server = rec.primary
        self.assertEqual(s.servers.hardware[server].state, 'HEALTHY', 'not isolated before the operator decides')
        self.assertNotIn(server, {p.server_id for o in s.allocation_options(s.runs[rec.rid], 'performance')['options'] for p in o}
                         if s.runs[rec.rid].request['status'] != 'operating' else set())
        s.incident_act(rec.id, 'gpu_repair')
        self.assertEqual(s.servers.hardware[server].state, 'REPAIRING')
        self.assertEqual(s.hardware_servers(s.runs[rec.rid]), (server,))
        s.advance_time(10)
        s.advance_time(10)
        self.assertEqual(s.servers.hardware[server].state, 'HEALTHY')
        self.assertEqual(s.record(rec.id).state, 'monitoring')

    def test_gpu_move_impossible_without_capacity_is_refused(self):
        s, rec = started(self.t, 'gpu_health')
        diagnose(s, rec)
        # Another (game-internal) job fills every other server so nothing is free outside the suspect server.
        others = [k for k in 'ABCD' if k != rec.primary]
        with s._atomic():
            for k in others:
                s.servers.hardware[k] = s.servers.hardware[k].__class__('FAULT', reason='test: capacity gone')
        out = s.incident_act(rec.id, 'isolate_migrate')
        self.assertEqual(out['result'], 'refused')
        self.assertIn('이전 불가', out['text'])
        self.assertEqual(s.servers.hardware[rec.primary].state, 'HEALTHY', 'a refused isolation changes nothing')

    def test_ups_unmitigated_battery_runs_out_and_the_job_fails(self):
        s, rec = started(self.t, 'ups')
        diagnose(s, rec)
        s.incident_act(rec.id, 'escalate_facility')
        for _ in range(3):
            s.advance_time(10)
        r = s.record(rec.id)
        self.assertEqual(r.state, 'failed')
        self.assertEqual(s.runs[rec.rid].state.succeeded, False)
        self.assertIn('UPS', s.runs[rec.rid].state.result_text)
        for _ in range(5):
            if s.global_.result:
                break
            s.advance_time(10)
        if not s.global_.result:
            s.select(rec.rid)
            s.report_failure()
        self.assertFalse(s.global_.result['cleared'])

    def test_ups_economy_on_second_feed_can_be_transferred(self):
        s, rec = started(self.t, 'ups', mode='economy', pick=lambda o: next((p for p in o if primary_of(p) in 'CD'), o[0]))
        if rec.ups != 'UPS-02':
            self.skipTest('no option on the second feed')
        diagnose(s, rec)
        s.incident_act(rec.id, 'escalate_facility')
        out = s.incident_act(rec.id, 'load_shed')
        self.assertEqual(out['result'], 'move')
        self.assertTrue(set(out['servers']) <= {'A', 'B'})
        self.assertEqual(s.runs[rec.rid].migration_left, 10)

    def test_cooling_limit_without_action_fails(self):
        s, rec = started(self.t, 'cooling')
        s.incident_ack(rec.id)
        for _ in range(4):
            s.advance_time(10)
        self.assertEqual(s.record(rec.id).state, 'failed')
        self.assertIn('열 보호', s.runs[rec.rid].state.result_text)

    def test_held_servers_are_not_offered_for_new_work(self):
        s = new_session(self.t, shift=2)
        s.confirm_shift_briefing()
        osa = next(rid for rid, r in s.runs.items() if r.conditions['catalog']['site'] == 'JP-OSA')
        s.select(osa)
        opts = s.allocation_options(s.runs[osa], 'performance')['options']
        s.choose_plan('performance', next(p for p in opts if primary_of(p) in 'AB'))
        for _ in range(10):
            s.advance_time(10)
            if s.shift_records()[0].state == 'alert':
                break
        rec = s.shift_records()[0]
        self.assertEqual(rec.type, 'tor_uplink')
        nyc = next(rid for rid, r in s.runs.items() if r.conditions['catalog']['site'] == 'US-NYC')
        for plan in s.allocation_options(s.runs[nyc], 'performance')['options']:
            self.assertNotIn(rec.primary, {p.server_id for p in plan})
        from aidc.core.server_resources import ServerSlice
        free = [i for i in range(4 if rec.primary == 'A' else 3)]
        s.select(nyc)
        with self.assertRaisesRegex(ValueError, '사건 영향 범위'):
            s.choose_plan('performance', (ServerSlice(rec.primary, (free[-1],), 1),))


class SaveResume(unittest.TestCase):
    def setUp(self):
        self.t = Temp()

    def tearDown(self):
        self.t.cleanup()

    def test_resume_mid_incident_keeps_cause_evidence_timers_and_ledger(self):
        s, rec = started(self.t, 'cooling')
        path = Path(s.db.path if hasattr(s.db, 'path') else self.t.dir / self.t.dbs[-1].__dict__.get('path', ''))
        diagnose(s, rec)
        s.incident_act(rec.id, 'escalate_facility')
        s.advance_time(10)
        s.incident_act(rec.id, 'standby_pump')
        before = (s.minute, deepcopy(s.incident.payload()), {k: v.state for k, v in s.servers.hardware.items()},
                  s.runs[rec.rid].state.work_done, s.center.gpu_used)
        name = [p for p in self.t.dir.iterdir() if p.suffix == '.db'][-1]
        s.close()
        again = IncidentSession(Database(name))
        self.t.dbs.append(again.db)
        after = (again.minute, again.incident.payload(), {k: v.state for k, v in again.servers.hardware.items()},
                 again.runs[rec.rid].state.work_done, again.center.gpu_used)
        self.assertEqual(before, after)
        self.assertEqual(len(again.incident.records), 1, 'no second incident after resume')
        r = again.record(rec.id)
        for _ in range(3):
            again.advance_time(10)
        self.assertEqual(again.record(rec.id).state, 'monitoring')

    def test_other_modes_refuse_incident_saves_and_changed_content_is_refused(self):
        s, rec = started(self.t, 'dns')
        name = [p for p in self.t.dir.iterdir() if p.suffix == '.db'][-1]
        s.close()
        for opener in (lambda db: GlobalSession(db), lambda db: GameSession(db, mode='free')):
            db = Database(name)
            self.t.dbs.append(db)
            with self.assertRaises(ValueError):
                opener(db)
            db.close()
        db = Database(name)
        self.t.dbs.append(db)
        payload = db.get_simulation()
        payload['incident']['records'][0]['fingerprint'] = 'changed'
        db.save_simulation(payload)
        with self.assertRaisesRegex(ValueError, '소급 재해석'):
            IncidentSession(db)

    def test_incident_session_refuses_a_global_save(self):
        db = self.t.db('global.db')
        g = GlobalSession(db, kind='shift', shift=1, seed=3)
        g.close()
        db2 = self.t.db('global.db')
        with self.assertRaises(ValueError):
            IncidentSession(db2)

    def test_failed_action_rolls_back_everything(self):
        s, rec = started(self.t, 'storage_full')
        diagnose(s, rec)
        snapshot = deepcopy(s.incident.payload())
        original = s._persist
        s._persist = lambda: (_ for _ in ()).throw(RuntimeError('disk full (test)'))
        with self.assertRaises(RuntimeError):
            s.incident_act(rec.id, 'cleanup_temp')
        s._persist = original
        self.assertEqual(s.incident.payload(), snapshot)


class Shifts(unittest.TestCase):
    def setUp(self):
        self.t = Temp()

    def tearDown(self):
        self.t.cleanup()

    def test_three_shifts_clear_with_evidence_based_play(self):
        s = new_session(self.t, shift=1)
        for number in (1, 2, 3):
            result = play_shift(s)
            self.assertTrue(result['cleared'], result['feedback'])
            self.assertEqual(result['resolved'], len(result['incidents']))
            if number < 3:
                s.start_next_shift()
        self.assertIsNone(s.next_shift())
        self.assertEqual([h['shift'] for h in s.global_.history], [1, 2])

    def test_shift_b_requires_notice_before_recovery(self):
        s = new_session(self.t, shift=2)
        result = play_shift(s, notify=False)
        self.assertFalse(result['cleared'])
        self.assertIn('안내하지 않은', ' '.join(result['feedback']))

    def test_shift_c_overlap_keeps_cause_and_scope_separate(self):
        s = new_session(self.t, shift=3)
        s.confirm_shift_briefing()
        for _ in range(6):
            start_open(s)
            s.advance_time(10)
            if all(r.state != 'armed' for r in s.shift_records()[:2]):
                break
        cong, lat = s.shift_records()[:2]
        self.assertEqual((cong.type, lat.type, cong.detected), ('congestion', 'storage_latency', lat.detected))
        s.incident_ack(cong.id)
        s.incident_ack(lat.id)
        self.assertNotEqual(s.incident_scope(cong)['jobs'][0]['rid'], s.incident_scope(lat)['jobs'][0]['rid'])
        cross = s.incident_observe(cong.id, 'storage_latency', 'hall')
        self.assertEqual(cross['status'], 'ok')
        self.assertTrue(any('무관' in line for line in cross['lines']), cross)
        s.incident_observe(cong.id, 'storage_space', 'hall')
        self.assertEqual(s.incident_hypothesis(cong.id, 'storage_latency')['verdict'], 'refuted')
        s.incident_observe(cong.id, 'link_stats', 'NETWORK')
        self.assertEqual(s.incident_hypothesis(cong.id, 'congestion')['verdict'], 'confirmed')
        self.assertEqual(s.record(lat.id).state, 'investigating', 'the other incident is untouched')

    def test_wrong_reroute_on_congestion_is_no_improvement(self):
        s, rec = started(self.t, 'congestion')
        diagnose(s, rec)
        self.assertEqual(s.incident_act(rec.id, 'reroute_backup')['result'], 'none')
        self.assertEqual(s.record(rec.id).state, 'diagnosed')


class BriefingLock(unittest.TestCase):
    """Phase 6 알려진 위험: 교대 브리핑 전에는 게임을 바꾸는 행동을 막고, 조회는 허용합니다."""

    def setUp(self):
        self.t = Temp()

    def tearDown(self):
        self.t.cleanup()

    def test_global_shift_before_briefing(self):
        s = GlobalSession(self.t.db('g.db'), kind='shift', shift=1, seed=4)
        rid = next(iter(s.runs))
        minute, used = s.minute, s.center.gpu_used
        s.select(rid)
        s.read_conversation(rid)
        s.allocation_options(s.runs[rid], 'performance')
        status = s.runs[rid].request['status']   # reading marks the request reviewed (a display fact)
        for call in (lambda: s.choose_plan('performance'), s.wait_request, lambda: s.reject_request('자원 부족'),
                     s.propose_alternative, lambda: s.advance_time(10)):
            with self.assertRaisesRegex(ValueError, '브리핑'):
                call()
        self.assertEqual((s.minute, s.center.gpu_used, s.runs[rid].request['status']), (minute, used, status))
        s.confirm_shift_briefing()
        s.choose_plan('performance')
        self.assertTrue(s.runs[rid].state.allocated)

    def test_incident_actions_wait_for_briefing(self):
        s = new_session(self.t, shift=1)
        with self.assertRaisesRegex(ValueError, '브리핑'):
            s.advance_time(10)

    def test_base_session_has_no_incident_hold(self):
        g = GameSession(self.t.db('free.db'), mode='free', seed=2, incident_chance=0)
        self.assertIsNone(g._job_hold(next(iter(g.runs.values()))))


if __name__ == '__main__':
    unittest.main()
