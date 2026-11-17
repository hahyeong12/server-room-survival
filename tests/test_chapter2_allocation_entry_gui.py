"""제2장 메인 모드 선택→배정창 연결 회귀. 메모리 fixture이며 실제 자동 플레이와 구분합니다."""
import tkinter as tk
import unittest
from unittest.mock import patch

from database import Database
from main import SimulatorApp
from tests.test_chapter2 import start


class Chapter2AllocationEntryGuiTests(unittest.TestCase):
    def test_us_economy_can_open_settings_while_japan_uses_power(self):
        root, db = tk.Tk(), Database(':memory:')
        self.addCleanup(root.destroy)
        self.addCleanup(db.close)
        errors = []
        root.report_callback_exception = lambda *args: errors.append(args)
        with patch.object(SimulatorApp, 'show_story_event'):
            app = SimulatorApp(root, db=db, mode='story', start_chapter=2, seed=9)
            self.addCleanup(app.network.stop)
            self.addCleanup(app.tutorial_highlight.stop)
            s = app.session
            s.confirm_chapter2_briefing()
            jp, us = s.story.chapter2.request_ids
            start(s, jp, 'performance')  # 단위 검사용 준비 상태. 자동 플레이 실적으로 세지 않습니다.
            app.select_request(us)
            root.update()
            self.assertEqual(app.action_buttons['start'].cget('state'), 'disabled')
            before = s.minute, s.center.gpu_used, s.center.power_used
            app.mode_buttons['economy'].invoke()
            root.update()
            self.assertEqual(app.action_buttons['start'].cget('state'), 'normal')
            self.assertEqual(before, (s.minute, s.center.gpu_used, s.center.power_used))
            app.action_buttons['start'].invoke()
            root.update()
            d = app.allocation_window
            self.assertEqual(d.mode, 'economy')
            d.mode_buttons['performance'].invoke()
            root.update()
            self.assertEqual(d.options, ())
            self.assertEqual(d.start_button.cget('state'), 'disabled')
            self.assertTrue(d.mode_reason.cget('text'))
            d.mode_buttons['economy'].invoke()
            d.plan_buttons[0].invoke()
            root.update()
            self.assertEqual(before, (s.minute, s.center.gpu_used, s.center.power_used))
            d.start_button.invoke()
            root.update()
            self.assertEqual((s.center.gpu_used, s.center.power_used), (8, 8))
            self.assertEqual(s.runs[us].state.plan, 'economy')
            self.assertFalse(s.runs[us].proposals)
            self.assertEqual(errors, [])


if __name__ == '__main__':
    unittest.main()
