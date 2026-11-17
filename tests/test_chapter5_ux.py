"""chapter5-ux-001: Stage 5 학습 통과와 고객 작업 완료의 구분(조회 전용 상태). Tk 창을 만들지 않는 검증.

다섯 시점(Stage 5 미통과 → 우회 직후 → 사후 ping 통과 → 복구 준비 종료 → 고객 최종 완료)에서
`training_job_status()`/`training_result()['status']`/Lab 목표/관제실 목표가 실제 상태와 맞는지,
조회가 시간·점수·자원·동의·저장을 바꾸지 않는지, 저장 후 이어하기에서도 같은지 확인합니다.
"""
from pathlib import Path
import tempfile
import unittest

from session import GameSession
from tests.test_chapter3 import open_db
from tests.test_training import (NEAR, SERVER, game_snapshot, lab_practice, pass_stage1, pass_stage2, pass_stage3,
                                 pass_stage4, regular_after_3b, stage5_evidence, to_training_incident)


def to_stage5_judged(s):
    """Stage 1~4 통과 → Stage 5 조치 전 증거·원인 판단까지(조치 전)."""
    rid = to_training_incident(s)
    for index, step in enumerate((pass_stage1, pass_stage2, pass_stage3, pass_stage4)):
        if s.training.practice:
            s.focus_training_stage(('structure', 'tool', 'assemble', 'terminal')[index])
        step(s)
        if not s.training.practice:
            s.start_next_stage()
    if s.training.practice:
        s.focus_training_stage('independent')
    stage5_evidence(s)
    s.training_answer('independent', 'cause', 'path_down')
    return rid


def verify(s):
    return s.training_command('terminal', f'ping -c 3 {SERVER}', 'independent')


def finish_customer_job(s, rid):
    for _ in range(40):
        if s.runs[rid].state.phase == 'finished':
            return
        s.advance_time(10)
    raise AssertionError('고객 작업이 끝나지 않았습니다.')


def viewed(s):
    """화면이 쓰는 조회를 모두 호출합니다(상태를 바꾸면 안 됨)."""
    status = s.training_job_status()
    s.training_status()
    s.training_objective()
    if s.training.done:
        s.training_result()
    return status


class StatusTimelineTests(unittest.TestCase):
    def check_timeline(self, s):
        rid = to_stage5_judged(s)
        # ① Stage 5 미통과(조치 전)
        st = viewed(s)
        self.assertFalse(s.training.done)
        self.assertEqual((st['finished'], st['job_tone']), (False, 'fault'))
        self.assertIn('장애 조치 전', st['job_label'])
        self.assertIn('장애 조치 전', st['network'])
        # ② 복구(우회) 버튼 직후: 학습은 아직 미통과, 고객 작업은 복구 준비 중
        s.selected_id = rid
        s.respond('reroute')
        st = viewed(s)
        self.assertFalse(s.training.done)                                   # 조치만으로 통과하지 않음(조건 불변)
        self.assertEqual(s.runs[rid].state.phase, 'recovering')
        self.assertIn('복구 준비 중', st['job_label'])
        self.assertIn('재확인 전', st['network'])
        # ③ 사후 ping → Stage 5 통과. 고객 작업은 여전히 복구 준비 중(완료로 표시하지 않음)
        self.assertEqual(verify(s).facts['received'], 3)
        self.assertTrue(s.training.done)
        self.assertEqual(s.runs[rid].state.phase, 'recovering')            # 학습 통과가 작업을 자동 완료시키지 않음
        st = viewed(s)
        result = s.training_result()
        self.assertEqual(result['status'], st)
        self.assertFalse(st['finished'])
        self.assertEqual(st['network'], '백업 경로 우회 후 통신 복구 확인')
        self.assertIn('복구 준비 중', st['job_label'])
        self.assertNotIn('완료', st['job_label'])
        self.assertIn('관제실에서 시간을 진행', st['remaining'])
        self.assertIn('고객 작업은 아직 복구 준비 중', s.training_objective())
        head = s.training_status()['headline']
        self.assertIn(f'요청 #{rid}', head['detail'])
        self.assertIn('복구 준비 중', head['detail'])
        # ④ 복구 준비 종료 → 진행 중
        s.advance_time(s.runs[rid].state.recovery_left)
        self.assertEqual(s.runs[rid].state.phase, 'running')
        st = viewed(s)
        self.assertEqual((st['finished'], st['job_label'], st['job_tone']), (False, '진행 중', 'ok'))
        self.assertIn('작업 진행률', st['job_detail'])
        self.assertIn('고객 작업은 아직 진행 중', s.training_objective())
        # ⑤ 최종 완료·자원 반환
        finish_customer_job(s, rid)
        st = viewed(s)
        self.assertTrue(st['finished'] and st['returned'])
        self.assertEqual(st['job_label'], '정상 완료 · 기한 준수')
        self.assertIn('GPU·전력 반환 완료', st['job_detail'])
        self.assertNotIn(s.runs[rid].playthrough_id, s.servers.allocations)
        self.assertNotIn('아직', s.training_objective())
        self.assertNotIn('아직', s.training_status()['headline']['detail'])
        return rid

    def test_regular_training_timeline(self):
        s = regular_after_3b()
        s.start_training()
        self.check_timeline(s)
        self.assertFalse(s.training.practice)

    def test_practice_timeline(self):
        s = lab_practice()
        self.check_timeline(s)
        self.assertTrue(s.training.practice)

    def test_viewing_does_not_change_time_score_resources_or_consent(self):
        s = regular_after_3b(); s.start_training()
        rid = to_stage5_judged(s)
        s.selected_id = rid; s.respond('reroute'); verify(s)
        before = game_snapshot(s)
        payload = s.story.payload()
        for _ in range(3):
            viewed(s)
        self.assertEqual(game_snapshot(s), before)
        self.assertEqual(s.story.payload(), payload)

    def test_same_play_with_and_without_viewing_ends_identically(self):
        """조회를 섞은 플레이와 섞지 않은 플레이의 시간·점수·GPU·전력·원장이 같습니다."""
        results = []
        for view in (False, True):
            s = regular_after_3b(); s.start_training()
            rid = to_stage5_judged(s)
            s.selected_id = rid; s.respond('reroute'); verify(s)
            for _ in range(40):
                if view:
                    viewed(s)
                if s.runs[rid].state.phase == 'finished':
                    break
                s.advance_time(10)
            run = s.runs[rid]
            results.append((s.minute, run.state.score, run.state.succeeded, run.terms.get('completed'),
                            s.center.gpu_used, s.center.power_used, dict(s.servers.allocations), s.story.payload()))
        self.assertEqual(results[0], results[1])

    def test_status_matches_after_save_and_resume(self):
        folder = tempfile.TemporaryDirectory(); self.addCleanup(folder.cleanup)
        path = Path(folder.name) / 'ux.db'
        s = regular_after_3b(open_db(self, path)); s.start_training()
        rid = to_stage5_judged(s)
        s.selected_id = rid; s.respond('reroute'); verify(s)
        for step in ('passed', 'running', 'finished'):
            if step == 'running':
                s.advance_time(s.runs[rid].state.recovery_left)
            elif step == 'finished':
                finish_customer_job(s, rid)
            expected = s.training_result()
            objective = s.training_objective()
            s.close()
            s = GameSession(open_db(self, path), mode='story')
            self.assertTrue(s.training.done)
            self.assertEqual(s.training_result(), expected)
            self.assertEqual(s.training_objective(), objective)
        self.assertTrue(s.training_job_status()['finished'])
        s.close()

    def test_failed_or_unassigned_jobs_are_not_reported_as_completed(self):
        s = regular_after_3b(); s.start_training()
        st = s.training_job_status()                                        # 연수 요청 배정 전
        self.assertEqual((st['finished'], st['job_label']), (False, '배정 전'))
        self.assertEqual(st['network'], '장애 대응 기록 없음')


if __name__ == '__main__':
    unittest.main()
