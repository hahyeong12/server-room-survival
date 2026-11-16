"""새 입문/첫 근무와 구 슬롯 호환. Tk 창 없이 실제 세션·임시 DB 사용."""
from copy import deepcopy
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from database import Database
from session import GameSession
from aidc.story.chapters import chapter_state
from aidc.storage.checkpoints import capture, restore
from aidc.storage.story_slots import StorySlots


class OnboardingTests(unittest.TestCase):
    def session(self, mode='story', db=None):
        db = db or Database(':memory:')
        self.addCleanup(db.close)
        return GameSession(db, mode=mode, intro_flow=True, seed=9, incident_chance=1)

    def work(self, s, mode='performance'):
        rid = s.story.onboarding.rid
        s.read_conversation(rid)
        s.inspect_story_preview(rid)
        s.choose_plan(mode)
        while s.runs[rid].state.allocated:
            s.advance_time(10)
        return rid

    def test_short_tutorial_uses_one_ten_minute_job_and_cannot_advance(self):
        s = self.session('tutorial')
        self.assertEqual(s.story.ui_step, 'arrival')
        s.confirm_story_arrival()
        self.assertEqual(s.story.ui_step, 'request')
        self.work(s)
        self.assertEqual(s.minute, 550)
        self.assertTrue(s.story.ui_done)
        self.assertEqual(chapter_state(s)[0], 'cleared')
        self.assertEqual(len(s.runs), 1)
        with self.assertRaisesRegex(ValueError, '본편'):
            s.start_chapter2()

    def test_three_sequential_jobs_release_resources_and_gate_chapter_two(self):
        s = self.session()
        s.confirm_story_arrival()
        ids = []
        for index in range(3):
            self.assertEqual(len(s.runs), index + 1)
            self.assertEqual(s.current.mission['country'], ('싱가포르', '일본', '미국')[index])
            if index:
                with self.assertRaisesRegex(ValueError, '세 업무'):
                    s.start_chapter2()
            ids.append(self.work(s))
            self.assertEqual((s.center.gpu_used, s.center.power_used), (0, 0))
            self.assertFalse(s.servers.allocations)
            self.assertEqual(s.story.ui_done, index == 2)
        self.assertEqual(s.story.onboarding.completed, ids)
        self.assertEqual(len(s.chapter_result()['jobs']), 3)
        self.assertTrue(all(r.state.incident_at is None for r in s.runs.values()))
        s.start_chapter2()
        self.assertEqual(s.story.ui_step, 'c2_briefing')
        self.assertEqual(s.current.state.scenario, 'ch2_jp')

    def test_flexible_customer_economy_is_still_allowed(self):
        s = self.session(); s.confirm_story_arrival()
        self.work(s); self.work(s)
        self.work(s, 'economy')
        self.assertTrue(s.story.ui_done)

    def test_rejected_second_customer_is_failure_even_when_first_succeeded(self):
        s = self.session(); s.confirm_story_arrival(); self.work(s)
        s.reject_request('요청한 운영 조건을 충족하기 어려움')
        self.assertTrue(s.story.chapter_completed)  # 기존 첫 업무 기록은 보존
        self.assertFalse(s.story.ui_done)
        self.assertEqual(chapter_state(s)[0], 'failed')
        with self.assertRaises(ValueError):
            s.start_chapter2()

    def test_automatic_next_request_and_save_failure_are_one_transaction(self):
        s = self.session(); s.confirm_story_arrival()
        rid = s.story.onboarding.rid
        s.choose_plan('performance'); s.advance_time(10); s.advance_time(10)
        before = deepcopy(s.db.get_simulation())
        with patch.object(s.db, 'save_simulation', side_effect=RuntimeError('disk full')):
            with self.assertRaises(RuntimeError):
                s.advance_time(10)
        self.assertEqual(s.db.get_simulation(), before)
        self.assertEqual(len(s.runs), 1)
        self.assertEqual(s.current.state.work_done, 20)
        self.assertEqual(len(s.db.get_requests()), 1)
        self.assertEqual(s.story.onboarding.completed, [])

    def test_resume_each_job_and_checkpoint_retry_preserve_original(self):
        with tempfile.TemporaryDirectory() as folder:
            slots = StorySlots(folder)
            db = Database(slots.reserve_new())
            try:
                s = GameSession(db, mode='story', intro_flow=True, seed=9)
                capture(s); s.confirm_story_arrival()
                for _ in range(3):
                    self.work(s)
                    s = GameSession(db, mode='story')
                s.start_chapter2()
                s = GameSession(db, mode='story')
                self.assertEqual(s.story.ui_step, 'c2_briefing')
                before = db.path.read_bytes()
                retry_path = restore(slots, db.path, 1)
                retry_db = Database(retry_path)
                try:
                    retry = GameSession(retry_db, mode='story')
                    self.assertEqual(retry.story.ui_step, 'arrival')
                    self.assertEqual(len(retry.runs), 1)
                finally:
                    retry_db.close()
                self.assertEqual(db.path.read_bytes(), before)
            finally:
                db.close()

    def test_legacy_slot_does_not_gain_new_jobs_or_fields(self):
        db = Database(':memory:'); self.addCleanup(db.close)
        s = GameSession(db, mode='story', seed=9)
        before = deepcopy(db.get_simulation())
        restored = GameSession(db, mode='story', intro_flow=True)
        self.assertIsNone(restored.story.onboarding)
        self.assertEqual(db.get_simulation(), before)
        self.assertNotIn('onboarding', restored.story.payload())

    def test_corrupt_completed_records_are_rejected_without_repair(self):
        s = self.session(); payload = s.db.get_simulation()
        payload['story']['onboarding']['completed'] = [s.selected_id]
        s.db.save_simulation(payload)
        with self.assertRaises(ValueError):
            GameSession(s.db, mode='story')
        self.assertEqual(s.db.get_simulation(), payload)
