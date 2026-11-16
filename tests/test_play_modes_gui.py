"""실제 Tk: 세 메뉴, 슬롯 분리, 결과·재도전·저장 실패·작은 창."""
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

from database import Database
from main import ModeSelection
from aidc.storage.story_slots import StorySlots
from aidc.storage.checkpoints import checkpoint_path
from tests.support import dismiss_story_popups
from tests.test_story_patch import prepare, finish


class PlayModesGuiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = tk.Tk()
        self.errors, self.dbs = [], []
        self.root.report_callback_exception = lambda *args:self.errors.append(args)
        self.slots = StorySlots(self.temp.name)
        def factory(path):
            db = Database(path)
            self.dbs.append(db)
            return db
        self.factory = factory
        self.menu = ModeSelection(self.root, db_factory=factory, story_slots=self.slots)
        self.addCleanup(self.cleanup)
        self.root.update()

    def cleanup(self):
        self.root.destroy()
        for db in self.dbs:
            db.close()
        self.temp.cleanup()

    def test_three_top_modes_and_submenus_open_no_database(self):
        self.assertEqual(set(self.menu.buttons), {'tutorial', 'story', 'practice'})
        for category in ('tutorial', 'story', 'practice'):
            self.menu.buttons[category].invoke(); self.root.update()
            self.assertTrue(self.menu.panels[category].winfo_ismapped())
            self.menu.menu_buttons[category]['back'].invoke(); self.root.update()
        self.assertEqual(self.dbs, [])
        self.assertEqual(self.slots.available(), [])
        self.assertEqual(self.errors, [])

    def test_all_menu_buttons_fit_three_resolutions(self):
        from session import GameSession
        for mode, chapter in (('story', 1), ('tutorial', 1), ('story', 'lab')):
            db = self.factory(self.slots.reserve_new())
            GameSession(db, mode=mode, start_chapter=chapter)
            db.close()
        for width, height in ((1000, 650), (1280, 680), (1366, 768)):
            for category in ('tutorial', 'story', 'practice'):
                self.root.geometry(f'{width}x{height}')
                self.menu.show_menu(category); self.root.update()
                panel = self.menu.content
                self.assertGreaterEqual(panel.winfo_y(), 0)
                self.assertLessEqual(panel.winfo_y()+panel.winfo_height(), self.root.winfo_height())
                for button in self.menu.menu_buttons[category].values():
                    self.assertLessEqual(button.winfo_rooty()+button.winfo_height(), self.root.winfo_rooty()+self.root.winfo_height())

    def test_tutorial_finish_cannot_offer_next_story_chapter(self):
        app = self.menu.new_tutorial(); self.root.update()
        dismiss_story_popups(app, self.root)
        prepare(app.session); finish(app.session)
        app.refresh(); app.show_chapter_complete(); self.root.update()
        self.assertNotIn('chapter2', app.chapter_window.buttons)
        self.assertIn('튜토리얼', app.chapter_window.title())
        self.assertIn('별도', app.chapter_window.next_notice.cget('text'))
        source = app.db.path
        self.assertTrue(app.return_to_modes())
        app.mode_selector.show_tutorial_menu(); self.root.update()
        self.assertEqual(app.mode_selector.paths_by_mode['tutorial'], [source])
        app.mode_selector.show_story_menu(); self.root.update()
        self.assertEqual(app.mode_selector.slot_paths, [])

    def test_story_checkpoint_retry_opens_new_regular_slot(self):
        app = self.menu.new_story(); self.root.update()
        source = app.db.path
        self.assertTrue(checkpoint_path(source, 1).is_file())
        dismiss_story_popups(app, self.root)
        app.session.reject_request('현재 GPU 자원 부족')
        app.refresh(); app.show_story_event(); self.root.update()
        self.assertIn('실패', app.chapter_window.title())
        app.chapter_window.buttons['retry'].invoke(); self.root.update()
        fresh = app.mode_selector.app
        self.assertNotEqual(fresh.db.path, source)
        self.assertFalse(fresh.session.story.practice)
        self.assertEqual(fresh.session.story.step, 'arrival')
        self.assertEqual(fresh.session.minute, 540)
        self.assertIsNotNone(fresh.story_window)
        self.assertEqual(self.errors, [])

    def test_next_chapter_creates_boundary_checkpoint_and_heading(self):
        app = self.menu.new_story(); self.root.update()
        dismiss_story_popups(app, self.root)
        prepare(app.session); finish(app.session)
        app.refresh(); app.show_chapter_complete(); self.root.update()
        app.chapter_window.buttons['chapter2'].invoke(); self.root.update()
        self.assertTrue(checkpoint_path(app.db.path, 2).is_file())
        self.assertIn('제2장', app.story_objective.cget('text'))
        self.assertIn('두 고객의 요청이 겹쳤습니다', app.story_window.full_text)
        self.assertTrue(app.session.story.chapter_completed)
        snapshot = self.slots.payload(checkpoint_path(app.db.path, 2))
        self.assertNotIn('c2_briefing', snapshot['story']['dialogue_seen'])
        self.assertTrue(app.retry_chapter2())
        self.root.update()
        fresh = app.mode_selector.app
        self.assertFalse(fresh.session.story.practice)
        self.assertTrue(fresh.session.story.chapter_completed)
        self.assertIn('두 고객의 요청이 겹쳤습니다', fresh.story_window.full_text)

    def test_checkpoint_failure_after_chapter_start_keeps_committed_story(self):
        app = self.menu.new_story(); self.root.update()
        dismiss_story_popups(app, self.root)
        prepare(app.session); finish(app.session)
        app.refresh(); app.show_chapter_complete(); self.root.update()
        with patch('main.capture', side_effect=OSError('disk full')), patch('main.messagebox.showerror') as error:
            self.assertTrue(app.begin_chapter2())
        error.assert_called_once()
        self.assertIsNotNone(app.session.story.chapter2)
        self.assertIsNotNone(app.db.get_simulation()['story']['chapter2'])
        self.assertFalse(checkpoint_path(app.db.path, 2).exists())
        self.assertFalse(app.closed)

    def test_save_failure_keeps_active_tutorial_and_menu_closed(self):
        app = self.menu.new_tutorial(); self.root.update()
        with patch.object(app.db, 'save_simulation', side_effect=RuntimeError('disk full')), patch('main.messagebox.showerror'):
            self.assertFalse(app.return_to_modes())
        self.assertFalse(app.closed)
        self.assertTrue(app.network.winfo_exists())
        self.assertFalse(hasattr(app, 'mode_selector'))

    def test_legacy_mid_chapter_does_not_get_a_fake_start_checkpoint(self):
        source = self.slots.reserve_new()
        db = self.factory(source)
        from session import GameSession
        s = GameSession(db, mode='story')
        s.confirm_story_arrival(); s.save(); db.close()
        app = self.menu.start('story', path=source, resume=True)
        self.root.update()
        self.assertFalse(checkpoint_path(source, 1).exists())
        with patch('main.messagebox.showinfo') as notice:
            self.assertFalse(app.retry_current_chapter())
        notice.assert_called_once()
        self.assertFalse(app.closed)
