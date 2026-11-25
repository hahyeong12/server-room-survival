"""Phase 6: 글로벌 교대 근무를 기존 엔진 규칙으로 처리합니다(창 없음, 임시 DB).

교대마다 '의도한 운영'(엔진 메서드만 사용)으로 클리어를 확인하고, 경합·조건 불허·협의 수락/거절·대기·만료·기한 초과,
저장 → 다시 열기, 원자성, 모드 분리를 검사합니다. 3D 화면 QA(scripts/phase6-qa.mjs)는 같은 흐름을 실제 클릭으로 수행합니다.
"""
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from database import Database
from session import GameSession
from aidc.global_ops.session import GlobalSession, GlobalProgress

# (교대 시작 후 분, [(행동, 사이트, 모드)]) — 배정안은 엔진 추천(첫 안)을 그대로 씁니다.
PLANS = {
    1: [(0, [('start', 'KR-SEL', 'performance'), ('start', 'US-SFO', 'performance')]),
        (30, [('start', 'DE-FRA', 'performance')]),
        (40, [('wait', 'US-SEA', None)]),
        (60, [('start', 'JP-OSA', 'performance')]),
        (70, [('start', 'US-SEA', 'performance')])],
    2: [(0, [('propose', 'US-IAD', False), ('propose', 'IN-BLR', True),
             ('start', 'US-IAD', 'performance'), ('start', 'IN-BLR', 'economy')]),
        (20, [('wait', 'KR-PUS', None)]),
        (50, [('wait', 'GB-LON', None)]),
        (80, [('start', 'GB-LON', 'performance'), ('start', 'NL-AMS', 'performance')]),
        (90, [('wait', 'TW-TPE', None)]),
        (100, [('start', 'TW-TPE', 'performance')]),
        (120, [('start', 'KR-PUS', 'performance')])],
    3: [(0, [('propose', 'KR-DJN', True), ('propose', 'AU-SYD', True),
             ('start', 'KR-DJN', 'economy'), ('start', 'AU-SYD', 'economy')]),
        (20, [('start', 'SG-SIN', 'performance')]),
        (40, [('wait', 'IN-BOM', None)]),
        (60, [('start', 'US-NYC', 'economy')]),
        (90, [('start', 'FR-PAR', 'performance')]),
        (120, [('start', 'IN-BOM', 'performance')])],
}


def rid_of(s, site):
    return next(r for r, x in s.runs.items() if x.conditions['catalog']['site'] == site and x.request['status'] != 'completed'
                or x.conditions['catalog']['site'] == site and r in s.shift_request_ids())


def play(test, s, plan, until_done=True):
    s.confirm_shift_briefing()
    start, t = s.minute, 0
    for _ in range(40):
        for at, acts in plan:
            if at != t:
                continue
            for kind, site, arg in acts:
                rid = rid_of(s, site)
                s.select(rid)
                if kind == 'start':
                    options = s.allocation_options(s.runs[rid], arg)
                    test.assertTrue(options['allowed'], f't{t} {site} {arg}: {options["reason"]}')
                    s.choose_plan(arg, options['options'][0])
                elif kind == 'propose':
                    s.propose_alternative()
                    test.assertEqual(s.review_alternative(), arg, f'{site} customer reply')
                elif kind == 'wait':
                    s.wait_request()
        if s.global_.result is not None or not until_done:
            break
        s.advance_time(10)
        t = s.minute - start
    return s.global_.result


class Shifts(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix='srs-global-'))
        self.path = self.dir / 'aidc_3d_global_001.db'

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def open(self, **kw):
        db = Database(self.path)
        return db, GlobalSession(db, **kw)

    def test_three_shifts_clear_in_one_save_with_engine_results(self):
        db, s = self.open(kind='shift', shift=1, seed=7)
        seen_sites = []
        for number in (1, 2, 3):
            self.assertEqual(s.global_.shift, number)
            result = play(self, s, PLANS[number])
            self.assertIsNotNone(result)
            self.assertTrue(result['cleared'], result['feedback'])
            self.assertEqual(result['success'], result['total'])
            seen_sites += [r['site'] for r in result['rows']]
            for row in result['rows']:
                run = s.runs[row['rid']]
                # 결과는 엔진 기록 그대로: 완료·자원 반환·점수.
                self.assertEqual(run.request['status'], 'completed')
                self.assertTrue(run.state.succeeded)
                self.assertEqual(row['score'], run.terms['evaluation'])
            self.assertEqual((s.center.gpu_used, s.center.power_used), (0, 0), 'all resources returned')
            if number < 3:
                s.start_next_shift()
        self.assertEqual(len(set(seen_sites)), 17)
        self.assertEqual(s.next_shift_reason(), '마지막 교대입니다.')
        self.assertEqual(len(s.global_.history), 2)
        db.close()

    def test_two_us_cities_and_domestic_customer_run_through_ulsan_servers(self):
        db, s = self.open(kind='shift', shift=1, seed=7)
        play(self, s, PLANS[1][:1], until_done=False)
        sel, sfo = rid_of(s, 'KR-SEL'), rid_of(s, 'US-SFO')
        self.assertEqual({s.runs[sel].state.phase, s.runs[sfo].state.phase}, {'running'})
        held = {p.server_id for rid in (sel, sfo) for p in s.servers.allocations[s.runs[rid].playthrough_id].slices}
        self.assertTrue(held <= {'A', 'B', 'C', 'D'})
        s.advance_time(30); s.advance_time(10)
        sites = {s.runs[r].conditions['catalog']['site'] for r in s.runs}
        self.assertTrue({'US-SFO', 'US-SEA'} <= sites, 'two different US cities in the same session')
        self.assertEqual(s.runs[rid_of(s, 'US-SEA')].conditions['catalog']['city'], '시애틀')
        db.close()

    def test_contention_refusal_and_consent_rules(self):
        db, s = self.open(kind='shift', shift=2, seed=7)
        s.confirm_shift_briefing()
        iad, blr = rid_of(s, 'US-IAD'), rid_of(s, 'IN-BLR')
        s.select(blr)
        with self.assertRaisesRegex(ValueError, '동의'):
            s.choose_plan('economy')            # 원래 조건을 몰래 바꿀 수 없습니다
        s.select(iad)
        s.choose_plan('performance')
        s.select(blr)
        with self.assertRaisesRegex(ValueError, '자원 부족'):
            s.choose_plan('performance')        # 6/6 + 5/5 > 10/10
        s.select(iad)
        with self.assertRaises(ValueError):
            s.propose_alternative()             # 이미 시작한 요청은 협의 대상이 아님
        s.select(blr)
        s.propose_alternative()
        self.assertTrue(s.review_alternative())
        self.assertEqual(s.runs[blr].proposals[-1]['status'], 'accepted')
        s.choose_plan('economy')
        self.assertEqual((s.center.gpu_used, s.center.power_used), (9, 9))
        db.close()

    def test_original_condition_impossible_on_servers_is_refused(self):
        db, s = self.open(kind='shift', shift=3, seed=7)
        djn = rid_of(s, 'KR-DJN')
        run = s.runs[djn]
        self.assertEqual(s.allocation_preview(run, 'performance')['reason'], '서버별 GPU·전력 조합 불가')
        s.select(djn)
        s.confirm_shift_briefing()   # Phase 7: game-changing actions wait for the shift briefing (tested separately)
        with self.assertRaisesRegex(ValueError, '조합'):
            s.choose_plan('performance')
        self.assertEqual(s.center.gpu_used, 0)
        db.close()

    def test_expiry_and_lateness_fail_the_intro_shift(self):
        db, s = self.open(kind='shift', shift=1, seed=7)
        plan = [step for step in PLANS[1] if step[0] != 60]       # 오사카 실시간 용량을 시작하지 않습니다
        plan = [(at, acts) if at != 30 else (50, acts) for at, acts in plan]   # 프랑크푸르트 평가를 20분 늦게 시작
        result = play(self, s, plan)
        self.assertFalse(result['cleared'])
        outcome = {r['site']: r['outcome'] for r in result['rows']}
        self.assertEqual(outcome['JP-OSA'], 'expired')
        self.assertEqual(outcome['DE-FRA'], 'late')
        self.assertIn('다시 도전', s.next_shift_reason())
        with self.assertRaises(ValueError):
            s.start_next_shift()
        db.close()

    def test_save_and_resume_at_start_middle_and_end(self):
        db, s = self.open(kind='shift', shift=2, seed=7)
        checkpoints = []

        def capture(sess):
            return ({rid: (r.request['status'], r.state.phase, r.state.plan, r.state.work_done, r.terms, r.conditions,
                           r.proposals, [a.payload() for a in r.server_allocations]) for rid, r in sess.runs.items()},
                    sess.minute, sess.global_.payload(), dict(sess.servers.allocations))

        checkpoints.append(capture(s))
        play(self, s, PLANS[2], until_done=False)       # t0 결정까지
        s.advance_time(30); s.advance_time(30)
        middle = capture(s)
        db.close()
        db, s = self.open()                              # 다시 열기: 종류·교대는 저장에서 읽습니다
        self.assertEqual(capture(s), middle)
        self.assertEqual(s.mode, 'global')
        db.close()

    def test_rollback_keeps_progress_when_saving_fails(self):
        db, s = self.open(kind='shift', shift=1, seed=7)
        before = s.global_.payload()
        with patch.object(db, 'save_simulation', side_effect=RuntimeError('disk full')):
            with self.assertRaises(RuntimeError):
                s.confirm_shift_briefing()
        self.assertEqual(s.global_.payload(), before)
        self.assertFalse(s.global_.briefed)
        with self.assertRaisesRegex(ValueError, '브리핑'):
            s.advance_time(10)
        db.close()

    def test_modes_stay_separate(self):
        db, s = self.open(kind='shift', shift=1, seed=7)
        db.close()
        db = Database(self.path)
        with self.assertRaisesRegex(ValueError, '모드'):
            GameSession(db)                              # 자유 운영으로 읽지 않습니다
        db.close()
        other = self.dir / 'free.db'
        db = Database(other)
        GameSession(db, seed=1)                          # 기존 자유 운영 저장
        payload = db.get_simulation()
        self.assertNotIn('global', payload)
        self.assertNotIn('mode', payload)
        with self.assertRaisesRegex(ValueError, '글로벌'):
            GlobalSession(db)
        db.close()
        self.assertEqual(GameSession.MODES, ('free', 'story', 'tutorial'))

    def test_free_global_operations_receive_many_catalog_customers(self):
        db, s = self.open(kind='free', seed=11)
        sites = set()
        for _ in range(30):
            for rid, run in s.runs.items():
                if run.request['status'] in ('new', 'review', 'waiting'):
                    s.select(rid)
                    for mode in ('economy', 'performance'):
                        options = s.allocation_options(run, mode)
                        if options['allowed']:
                            s.choose_plan(mode, options['options'][0])
                            break
            open_clients = [r.conditions['catalog']['client'] for r in s.runs.values()
                            if r.request['status'] in ('new', 'review', 'waiting', 'operating')]
            self.assertEqual(len(open_clients), len(set(open_clients)), 'one open request per customer')
            sites |= {r.conditions['catalog']['site'] for r in s.runs.values()}
            s.advance_time(30)
        self.assertGreaterEqual(len(sites), 10)
        self.assertTrue(all(r.state.scenario.startswith('global_v1:') for r in s.runs.values()))
        with self.assertRaises(ValueError):
            s.restart()
        db.close()

    def test_seen_flag_only_for_the_finished_current_shift(self):
        db, s = self.open(kind='shift', shift=1, seed=7)
        for key in ('shift1', 'shift2', 'x' * 41):
            with self.assertRaises(ValueError):
                s.mark_shift_seen(key)                  # shift 1 is still running
        play(self, s, PLANS[1])
        with self.assertRaises(ValueError):
            s.mark_shift_seen('shift2')
        s.mark_shift_seen('shift1')
        s.mark_shift_seen('shift1')                     # idempotent
        self.assertEqual(s.global_.seen, ['shift1'])
        db.close()

    def test_catalog_requires_a_first_arrival_at_shift_start(self):
        import json
        from aidc.global_ops.catalog import Catalog, CatalogError, CATALOG_FILE
        data = json.loads(CATALOG_FILE.read_text(encoding='utf-8'))
        data['shifts']['1']['arrivals'] = [[10, t] for _, t in data['shifts']['1']['arrivals']]
        with self.assertRaises(CatalogError):
            Catalog(data)

    def test_progress_payload_roundtrip_and_bad_payload(self):
        p = GlobalProgress(1, 'shift', {'a': 1}, shift=2)
        self.assertEqual(GlobalProgress.from_payload(p.payload()), p)
        for bad in (None, {'kind': 'x', 'version': 1}, {'kind': 'shift'}):
            with self.assertRaises(ValueError):
                GlobalProgress.from_payload(bad)


if __name__ == '__main__':
    unittest.main()
