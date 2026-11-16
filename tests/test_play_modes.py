"""플레이 모드 분리, 기존 슬롯 호환, 실제 엔진 판정과 체크포인트 복원."""
from copy import deepcopy
from pathlib import Path
import tempfile
import sqlite3
import unittest
from unittest.mock import patch

from database import Database, DB_PATH, STORY_DB_PATH
from session import GameSession
from aidc.story.chapters import CHAPTERS, current_chapter, chapter_state, heading
from aidc.storage.story_slots import StorySlots
from aidc.storage.checkpoints import capture, restore, checkpoint_path
from tests.test_story_patch import prepare, finish
from tests.test_chapter2 import after_chapter1, start, finish_all
from tests.test_training import regular_after_3b


class _DiskSessions(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.slots = StorySlots(self.temp.name)

    def session(self, mode='story', chapter=1):
        path = self.slots.reserve_new()
        db = Database(path)
        self.addCleanup(db.close)
        return GameSession(db, mode=mode, start_chapter=chapter, seed=9)


class PlayModeTests(_DiskSessions):
    def test_tutorial_uses_first_chapter_but_cannot_advance_story(self):
        s = self.session('tutorial')
        prepare(s); finish(s)
        self.assertEqual(chapter_state(s)[0], 'cleared')
        self.assertIn('튜토리얼', heading(s))
        with self.assertRaisesRegex(ValueError, '본편'):
            s.start_chapter2()
        self.assertIsNone(s.story.chapter2)

    def test_tutorial_resume_and_wrong_mode_rejection_preserve_save(self):
        s = self.session('tutorial')
        s.confirm_story_arrival(); s.select_story_server('A'); s.save()
        before = s.db.get_simulation()
        restored = GameSession(s.db, mode='tutorial')
        self.assertEqual(restored.story.step, 'resources')
        with self.assertRaises(ValueError):
            GameSession(s.db, mode='story')
        self.assertEqual(s.db.get_simulation(), before)

    def test_tutorial_rejects_later_chapter_starts(self):
        db = Database(':memory:'); self.addCleanup(db.close)
        for chapter in (2, 3, '3b', 'lab'):
            with self.subTest(chapter=chapter), self.assertRaises(ValueError):
                GameSession(db, mode='tutorial', start_chapter=chapter)
        self.assertIsNone(db.get_simulation())

    def test_tutorial_save_failure_rolls_back_learning_action(self):
        s = self.session('tutorial')
        before = deepcopy(s.story.payload())
        with patch.object(s.db, 'save_simulation', side_effect=RuntimeError('disk full')):
            with self.assertRaises(RuntimeError):
                s.confirm_story_arrival()
        self.assertEqual(s.story.payload(), before)

    def test_slot_lists_separate_regular_tutorial_and_existing_practice(self):
        regular = self.session()
        tutorial = self.session('tutorial')
        practices = [self.session(chapter=c) for c in (2, 3, '3b', 'lab')]
        self.assertEqual(self.slots.for_mode('story'), [regular.db.path])
        self.assertEqual(self.slots.for_mode('tutorial'), [tutorial.db.path])
        self.assertEqual(self.slots.for_mode('practice'), [s.db.path for s in practices])
        self.assertTrue(all(s.story.practice for s in practices))

    def test_old_regular_and_legacy_slots_are_still_discoverable(self):
        db = Database(self.slots.legacy_path); self.addCleanup(db.close)
        s = after_chapter1(db)
        before = deepcopy(db.get_simulation())
        self.assertIn(db.path, self.slots.for_mode('story'))
        self.assertTrue(GameSession(db, mode='story').story.chapter_completed)
        self.assertEqual(db.get_simulation(), before)

    def test_metadata_has_five_chapters_without_changing_save_ids(self):
        self.assertEqual([c.number for c in CHAPTERS.values()], [1, 2, 3, 4, 5])
        self.assertEqual(CHAPTERS['3b'].heading, '제4장 — 서버실의 경보')
        self.assertEqual(current_chapter(self.session(chapter='lab').story).key, 'lab')

    def test_skip_is_not_clear_and_customer_condition_error_is_not_failure(self):
        s = self.session()
        s.skip_tutorial()
        self.assertEqual(chapter_state(s)[0], 'in_progress')
        with self.assertRaises(ValueError):
            s.choose_plan('economy')
        self.assertEqual(chapter_state(s)[0], 'in_progress')

    def test_rejection_is_real_failure(self):
        s = self.session()
        s.reject_request('요청한 운영 조건을 충족하기 어려움')
        self.assertEqual(chapter_state(s)[0], 'failed')

    def test_database_paths_stay_at_project_root(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(DB_PATH, root/'aidc_game.db')
        self.assertEqual(STORY_DB_PATH, root/'aidc_story.db')

    def test_corrupt_menu_payload_does_not_hide_or_modify_slot(self):
        s = self.session()
        s.db.conn.execute("UPDATE simulation_state SET payload='[]' WHERE id=1")
        s.db.conn.commit()
        before = s.db.path.read_bytes()
        self.assertEqual(self.slots.for_mode('story'), [s.db.path])
        self.assertIsInstance(self.slots.describe(s.db.path), str)
        self.assertEqual(before, s.db.path.read_bytes())


class CheckpointTests(_DiskSessions):
    def test_checkpoint_preserves_first_start_and_retries_in_new_slots(self):
        s = self.session()
        checkpoint = capture(s)
        original = checkpoint.read_bytes()
        prepare(s); finish(s); s.save()
        failed_or_finished = s.db.path.read_bytes()
        self.assertEqual(capture(s), checkpoint)
        self.assertEqual(checkpoint.read_bytes(), original)
        for _ in range(2):
            target = restore(self.slots, s.db.path, 1)
            db = Database(target); self.addCleanup(db.close)
            fresh = GameSession(db, mode='story')
            self.assertEqual(fresh.story.step, 'arrival')
            self.assertFalse(fresh.story.chapter_completed)
            self.assertEqual(fresh.center.gpu_used, 0)
        self.assertEqual(s.db.path.read_bytes(), failed_or_finished)

    def test_chapter_two_retry_keeps_chapter_one_clear_and_resets_only_new_attempt(self):
        s = self.session(); prepare(s); finish(s)
        old = [dict(row) for row in s.db.get_recent_records()]
        s.start_chapter2(); capture(s)
        s.confirm_chapter2_briefing()
        jp, us = s.story.chapter2.request_ids
        s.selected_id = jp; s.reject_request('현재 GPU 자원 부족')
        start(s, us, 'performance'); finish_all(s)
        self.assertEqual(chapter_state(s)[0], 'failed')
        s.save(); before = s.db.path.read_bytes()
        target = restore(self.slots, s.db.path, 2)
        db = Database(target); self.addCleanup(db.close)
        fresh = GameSession(db, mode='story')
        self.assertTrue(fresh.story.chapter_completed)
        self.assertFalse(fresh.story.practice)
        self.assertIsNone(fresh.story.chapter2.failure)
        self.assertFalse(fresh.story.chapter2.briefing_confirmed)
        self.assertEqual([dict(row) for row in fresh.db.get_recent_records()], old)
        self.assertEqual(s.db.path.read_bytes(), before)

    def test_regular_training_retry_keeps_all_prior_chapter_records(self):
        s = self.session()
        # helper는 같은 저장 DB에서 정규 1~4장을 실제로 완료합니다.
        s = regular_after_3b(s.db)
        previous = deepcopy(s.story.chapter3b.records)
        s.start_training(); capture(s)
        target = restore(self.slots, s.db.path, 'lab')
        db = Database(target); self.addCleanup(db.close)
        fresh = GameSession(db, mode='story')
        self.assertEqual(fresh.story.chapter3b.records, previous)
        self.assertEqual(fresh.training.completed, [])
        self.assertFalse(fresh.training.practice)

    def test_practice_and_tutorial_do_not_create_regular_checkpoints(self):
        for mode, chapter in (('tutorial', 1), ('story', 3), ('story', 'lab')):
            s = self.session(mode, chapter)
            self.assertIsNone(capture(s))
        self.assertFalse(list(Path(self.temp.name).glob('aidc_checkpoint*')))

    def test_missing_checkpoint_does_not_reserve_a_new_slot(self):
        s = self.session()
        before = self.slots.available()
        with self.assertRaises(Exception):
            restore(self.slots, s.db.path, 1)
        self.assertEqual(self.slots.available(), before)

    def test_checkpoint_is_not_a_playable_slot(self):
        s = self.session(); checkpoint = capture(s)
        self.assertNotIn(checkpoint, self.slots.available())
        self.assertEqual(checkpoint, checkpoint_path(s.db.path, 1))

    def test_checkpoint_write_failure_preserves_live_save_and_removes_only_new_copy(self):
        s = self.session()
        before = s.db.path.read_bytes()
        with patch('aidc.storage.checkpoints.sqlite3.connect', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                capture(s)
        self.assertEqual(s.db.path.read_bytes(), before)
        self.assertFalse(checkpoint_path(s.db.path, 1).exists())

    def test_wrong_chapter_checkpoint_is_rejected_before_reserving_slot(self):
        s = self.session(); checkpoint = capture(s)
        connection = sqlite3.connect(checkpoint)
        try:
            connection.execute("UPDATE simulation_state SET payload='{}' WHERE id=1")
            connection.commit()
        finally:
            connection.close()
        before = self.slots.available()
        with self.assertRaisesRegex(ValueError, '일치'):
            restore(self.slots, s.db.path, 1)
        self.assertEqual(self.slots.available(), before)
