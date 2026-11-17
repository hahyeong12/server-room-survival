"""회귀 러너가 실제 사용자 저장 위치를 허용하지 않는지 검사합니다(Tk 생성 없음)."""
from pathlib import Path
import tempfile
import unittest
from tests.run_gui import ROOT, check_test_path


class RegressionRunnerTests(unittest.TestCase):
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
