"""실패 설명은 확정 사실에서만 계산하고 결과 행동에 연습 진입을 두지 않습니다."""
from copy import deepcopy
import unittest
from database import Database
from session import GameSession
from aidc.ui.result_presentation import failure_explanation, result_actions
from tests.test_chapter2 import after_chapter1, start, finish_all


class ResultUXTests(unittest.TestCase):
    def test_rejection_has_direct_cause_reason_and_next_step(self):
        db = Database(':memory:'); self.addCleanup(db.close)
        s = GameSession(db, mode='story', intro_flow=True)
        s.reject_request('요청한 운영 조건을 충족하기 어려움')
        before = deepcopy(db.get_simulation())
        info = failure_explanation(run=s.current)
        self.assertIn('거절', info['headline'])
        self.assertIn('정상 처리 목표', info['why'])
        self.assertIn('고객 조건', info['next'])
        self.assertEqual(db.get_simulation(), before)

    def test_late_completion_uses_recorded_delay_without_invented_blocker(self):
        db = Database(':memory:'); self.addCleanup(db.close)
        s = after_chapter1(db); s.start_chapter2()
        s.confirm_chapter2_briefing()
        jp, us = s.story.chapter2.request_ids
        start(s, jp, 'performance')
        for _ in range(4):
            s.advance_time(10)
        start(s, us, 'performance'); finish_all(s)
        result = s.chapter2_result(); before = deepcopy(result)
        info = failure_explanation(result)
        self.assertIn('완료 기한', info['headline'])
        self.assertIn('10분', info['why'])
        self.assertIn('뒤에 시작', info['why'])
        self.assertEqual(result, before)

    def test_hardware_late_result_distinguishes_work_done_and_mission_failure(self):
        result = {'jobs': [{'success': False, 'company': '고객', 'job': {'key': 'late'},
                            'choices': ['장비 복구'], 'downtime': 20, 'record': {}}]}
        info = failure_explanation(result)
        self.assertIn('작업은 끝났지만', info['cause'])
        self.assertIn('장비 복구', info['why'])
        self.assertIn('20분', info['why'])
        self.assertNotIn('자원을 점유', info['why'])

    def test_missing_evidence_never_claims_specific_network_cause(self):
        info = failure_explanation({'jobs': []})
        self.assertNotIn('경로 단절', info['why'])
        self.assertNotIn('대역폭', info['why'])

    def test_actions_only_offer_retry_chapters_and_main_menu(self):
        action = lambda: None
        entries = result_actions(action, action, action)
        self.assertEqual([entry[0] for entry in entries], ['retry', 'chapters', 'modes'])
        self.assertFalse(any('자유' in entry[1] or '연습' in entry[1] for entry in entries))
        self.assertEqual([e[0] for e in result_actions(None, None, action)], ['modes'])
