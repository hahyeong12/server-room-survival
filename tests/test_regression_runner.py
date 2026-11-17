"""회귀 러너가 실제 사용자 저장 위치를 허용하지 않는지 검사합니다(Tk 생성 없음)."""
from pathlib import Path
import tempfile
import unittest
from tests.run_gui import ROOT, check_test_path, load_suite, test_id
from tests.run_headless import flatten


class RegressionRunnerTests(unittest.TestCase):
    def test_default_discovery_includes_gui_and_git_checks_without_import_errors(self):
        cases = list(flatten(load_suite([])))
        self.assertFalse(any(type(case).__name__ == '_FailedTest' for case in cases))
        names = {test_id(case) for case in cases}
        self.assertIn('tests.test_story_slots.SlotFilesTests.test_git_ignores_slots_journal_wal_shm_and_lease', names)
        self.assertIn('tests.test_play_modes_gui.PlayModesGuiTests.test_all_menu_buttons_fit_three_resolutions', names)

    def test_existing_and_future_root_saves_are_blocked(self):
        for name in ('aidc_game.db', 'aidc_story_slot_999.db', 'aidc_checkpoint_future.db'):
            with self.subTest(name=name), self.assertRaises(AssertionError):
                check_test_path(ROOT/name)

    def test_parent_segments_cannot_bypass_the_save_guard(self):
        with self.assertRaises(AssertionError):
            check_test_path(ROOT/'tests'/'..'/'aidc_game.db')

    def test_memory_and_temporary_fixtures_are_allowed(self):
        check_test_path(':memory:')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'aidc_game.db'
            check_test_path(path)
            self.assertFalse(path.exists())
