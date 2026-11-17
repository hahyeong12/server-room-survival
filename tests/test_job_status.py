"""ui-consistency-001: 작업 상태 표시 공통 판정(job_status)·제4장 카드 현재 상태·장 번호 문구. Tk 창 없음.

엔진 상태는 기존 하드웨어 엔진으로만 진행하며, 표시 함수가 시간·작업량·장애·원장을 바꾸지 않는지도 확인합니다.
"""
from copy import deepcopy
import unittest

from aidc.ui.job_status import job_status, chip_label
from story import GUIDES3B
from tests.test_chapter3b import fault_a, migrate_now, finish, mission_b
from tests.test_chapter3 import practice3, start_a, to_incident


def snapshot(s, run):
    return (s.minute, run.state.work_done, run.state.phase, run.migration_left, run.hardware_downtime,
            run.migration_downtime, dict(s.servers.hardware), deepcopy(dict(s.servers.allocations)))


class JobStatusTests(unittest.TestCase):
    def test_fault_is_interrupted_not_normal_running(self):
        s, a, run = fault_a()
        self.assertEqual(run.state.phase, 'running')                     # 엔진은 네트워크 단계와 독립(기존 규칙)
        before = snapshot(s, run)
        status = job_status(s, run)
        self.assertEqual((status['key'], status['tone'], status['interrupted']), ('hw_fault', 'fault', True))
        self.assertNotIn('정상 실행', chip_label(status))
        self.assertIn('Server A FAULT', status['detail'])
        self.assertEqual(snapshot(s, run), before)                         # 조회 전용

    def test_repair_then_resume(self):
        s, a, run = fault_a()
        s.view_hardware_diagnosis(a); s.begin_server_repair('A')
        status = job_status(s, run)
        self.assertEqual((status['key'], status['tone']), ('hw_repair', 'recover'))
        self.assertIn('20분 남음', status['detail'])
        self.assertIn('장비 복구 중', s.hardware_status(run))
        self.assertNotIn('서버 장애', s.hardware_status(run))
        s.advance_time(10)
        self.assertIn('10분 남음', job_status(s, run)['detail'])
        s.advance_time(10)
        status = job_status(s, run)
        self.assertEqual((status['key'], status['label'], status['tone']), ('resumed', '정상 실행 중', 'ok'))
        self.assertEqual(status['detail'], '장비 복구 후 재개')
        self.assertEqual(s.hardware_status(run), '')

    def test_migration_preparation_then_resume_while_faulted_server_stays_faulted(self):
        s, a, run = fault_a()
        migrate_now(s, run)
        status = job_status(s, run)
        self.assertEqual((status['key'], status['tone'], status['interrupted']), ('migration', 'recover', True))
        self.assertIn('준비 10분 남음', status['detail'])
        s.advance_time(10)
        self.assertEqual(s.servers.hardware['A'].state, 'FAULT')
        status = job_status(s, run)
        self.assertEqual((status['key'], status['detail']), ('resumed', '작업 이전 후 재개'))

    def test_network_incident_and_untouched_jobs_keep_existing_display(self):
        s = practice3()
        a = start_a(s)
        self.assertIsNone(job_status(s, s.runs[a]))                         # 정상 실행: 기존 표시 그대로
        to_incident(s, a)
        self.assertIsNone(job_status(s, s.runs[a]))                         # 네트워크 장애는 기존 '! 네트워크 장애'
        self.assertEqual(s.hardware_status(s.runs[a]), '')

    def test_finished_job_has_no_hardware_status(self):
        s, a, run = fault_a()
        migrate_now(s, run)
        finish(s, a)
        self.assertIsNone(job_status(s, run))


class Chapter4CardStatusTests(unittest.TestCase):
    def test_migration_card_separates_choice_record_from_current_state(self):
        s, a, run = fault_a()
        migrate_now(s, run)
        rows = dict(s.chapter3b_card(a)['rows'])
        self.assertIn('준비 10분', rows['선택 당시 결과'])
        self.assertIn('선택 시 예상 완료', rows)
        self.assertIn('10분 남음', rows['현재 상태'])
        s.advance_time(10)
        rows = dict(s.chapter3b_card(a)['rows'])
        self.assertIn('준비 10분', rows['선택 당시 결과'])                  # 선택 기록은 그대로
        self.assertTrue(rows['현재 상태'].startswith('정상 실행 중'))     # 현재 상태만 갱신
        finish(s, a)
        self.assertEqual(dict(s.chapter3b_card(a)['rows'])['현재 상태'], '작업 완료')

    def test_repair_card_current_state_and_pending_key_unchanged(self):
        s, b, run = mission_b()
        s.view_hardware_diagnosis(b); s.begin_server_repair('A')
        for _ in range(3):                                                    # 창 없이 진행해 앞선 미션 A 카드가 미확인 상태
            key = s.chapter3b_pending_feedback()
            if key is None or key.startswith(f'{b}:'):
                break
            s.mark_chapter3b_feedback_seen(key)
        self.assertEqual(s.chapter3b_pending_feedback(), f'{b}:repair:1')    # 저장 키 형식 유지
        rows = dict(s.chapter3b_card(b)['rows'])
        self.assertIn('장비 복구 중', rows['현재 상태'])


class ChapterFourLabelTextTests(unittest.TestCase):
    def test_chapter_four_objectives_do_not_show_internal_chapter_key(self):
        for step in ('briefing', 'done'):
            self.assertIn('제4장', GUIDES3B[step][0])
            self.assertNotIn('3b', GUIDES3B[step][0])

    def test_internal_label_and_save_keys_are_unchanged(self):
        s, a, run = fault_a()
        self.assertEqual(s.story.chapter_label, 'Chapter 3b')                 # 내부 식별자 유지(화면 미사용)
        self.assertIn('chapter3b', s.story.payload())                          # 저장 필드 이름 유지


if __name__ == '__main__':
    unittest.main()
