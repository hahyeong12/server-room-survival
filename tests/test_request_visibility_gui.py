"""실제 Tk 요청함: 신규 행 노출·레이아웃 변경·과거 기록 스크롤 보존."""
import tkinter as tk
import unittest
from unittest.mock import patch

from database import Database
from main import SimulatorApp


class RequestVisibilityGuiTests(unittest.TestCase):
    def test_tutorial_and_free_requests_keep_selection_resources_and_history(self):
        for mode in ('tutorial', 'free'):
            with self.subTest(mode=mode), patch.object(SimulatorApp, 'show_story_event'):
                root, db = tk.Tk(), Database(':memory:')
                app = None
                try:
                    app = SimulatorApp(root, db=db, mode=mode, intro_flow=True)
                    root.update()
                    s = app.session
                    if mode == 'tutorial':
                        s.confirm_story_arrival()
                        rid = s.selected_id
                        s.read_conversation(rid)
                        s.inspect_story_preview(rid)
                        s.choose_plan('performance')
                        s.advance_time(10)
                        self.assertTrue(s.story.ui_done)
                    else:
                        s.deliver_next_request()
                        rid = s.deliver_next_request()
                        s.select(rid)
                        self.assertIsNone(s.story)
                    before = (s.selected_id, s.center.gpu_used, s.center.power_used, tuple(s.runs))
                    app.refresh()
                    root.update()
                    self.assertTrue(app.inbox.bbox(str(s.selected_id)))
                    self.assertEqual(app.inbox.selection(), (str(s.selected_id),))
                    self.assertEqual(before, (s.selected_id, s.center.gpu_used, s.center.power_used, tuple(s.runs)))
                    self.assertEqual(len(app.inbox.get_children()), len(s.runs))
                finally:
                    if app:
                        app.network.stop()
                        app.tutorial_highlight.stop()
                    root.destroy()
                    db.close()

    def test_new_customers_visible_without_losing_history_or_manual_scroll(self):
        root = tk.Tk()
        db = Database(':memory:')
        self.addCleanup(db.close)
        self.addCleanup(root.destroy)
        with patch.object(SimulatorApp, 'show_story_event'):
            app = SimulatorApp(root, db=db, mode='story', intro_flow=True)
            self.addCleanup(app.network.stop)
            self.addCleanup(app.tutorial_highlight.stop)
            root.update()
            s = app.session
            s.confirm_story_arrival()
            for count in (2, 3):
                rid = s.selected_id
                s.read_conversation(rid)
                s.inspect_story_preview(rid)
                s.choose_plan('performance')
                s.advance_time(30)
                app.refresh()
                root.update()
                tree = app.inbox
                self.assertEqual(len(tree.get_children()), count)
                self.assertEqual(tree.selection(), (str(s.selected_id),))
                box = tree.bbox(str(s.selected_id))
                self.assertTrue(box, '새 고객이 실제 렌더링 뒤 보이지 않음')
                self.assertLessEqual(box[1]+box[3], tree.winfo_height())
                # 과거 고객은 스크롤로 접근 가능하고, 일반 상태 갱신은 그 위치를 빼앗지 않습니다.
                tree.yview_moveto(0)
                root.update()
                self.assertTrue(tree.bbox('1'))
                app.refresh()
                root.update()
                self.assertTrue(tree.bbox('1'))
                self.assertEqual(tree.selection(), (str(s.selected_id),))
                # 실제 뷰포트 크기가 바뀌면 선택 고객이 다시 노출되어야 합니다.
                parent = tree.master
                parent.rowconfigure(2, minsize=tree.winfo_height()+30)
                root.update()
                self.assertTrue(tree.bbox(str(s.selected_id)))
                parent.rowconfigure(2, minsize=58)
                root.update()
                self.assertTrue(tree.bbox(str(s.selected_id)))


if __name__ == '__main__':
    unittest.main()
