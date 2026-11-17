"""ui-polish-001 실제 Tk 검증: Engineering Lab 게이지의 글자 경계(제목·수치·보조 문구·막대)가 겹치지 않음.

단계 준비는 기존 테스트 도우미(엔진 직접 호출)를 사용합니다.
"""
import tkinter as tk
import unittest

from aidc.ui.ui_kit import Gauge
from database import Database
from main import SimulatorApp
from tests.support import dismiss_story_popups
from tests.test_training import pass_stage1, pass_stage2, pass_stage3, regular_after_3b, to_training_incident

SIZES = ('900x620', '1060x700', '1280x720', '1366x768')
PARTS = ('title', 'value', 'caption', 'track')


def overlap(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def all_gauges(widget):
    found = []
    for child in widget.winfo_children():
        if isinstance(child, Gauge):
            found.append(child)
        found.extend(all_gauges(child))
    return found


class LabGaugeGuiTests(unittest.TestCase):
    def make_app(self, practice):
        self.root = tk.Tk()
        self.root.geometry('1280x800+0+0')
        self.addCleanup(self.root.destroy)
        db = Database(':memory:'); self.addCleanup(db.close)
        if practice:
            app = SimulatorApp(self.root, db, mode='story', start_chapter='lab', seed=5)
        else:
            regular_after_3b(db).save()
            app = SimulatorApp(self.root, db, mode='story')
            self.root.update()
            app.begin_training()
        self.addCleanup(app.network.stop)
        self.errors = []
        self.root.report_callback_exception = lambda *a: self.errors.append(a)
        self.root.update(); dismiss_story_popups(app, self.root)
        return app

    def check_gauges(self, lab, label):
        for size in SIZES:
            for tab in ('연수 진행', '운영 상태', '서버 내부'):
                lab.geometry(size); lab.show_tab(tab)
                lab.update(); lab.update_idletasks(); lab.update()
                gauges = [g for g in all_gauges(lab.tabs[tab]) if g.winfo_ismapped()]
                self.assertTrue(gauges)
                for gauge in gauges:
                    boxes = {t: gauge.bbox(*gauge.find_withtag(t)) for t in PARTS if gauge.find_withtag(t)}
                    width, height = gauge.winfo_width(), gauge.winfo_height()
                    for i, a in enumerate(PARTS):
                        for b in PARTS[i+1:]:
                            if a in boxes and b in boxes:
                                with self.subTest(label=label, size=size, tab=tab, pair=(a, b)):
                                    self.assertFalse(overlap(boxes[a], boxes[b]))
                    for tag, box in boxes.items():
                        with self.subTest(label=label, size=size, tab=tab, tag=tag):
                            self.assertTrue(box[0] >= 0 and box[1] >= 0 and box[2] <= width+1 and box[3] <= height+1)

    def run_case(self, practice):
        app = self.make_app(practice)
        s = app.session
        to_training_incident(s)
        for index, step in enumerate((pass_stage1, pass_stage2, pass_stage3)):
            if practice:
                s.focus_training_stage(('structure', 'tool', 'assemble')[index])
            step(s)
            if not practice:
                s.start_next_stage()
        app.refresh(); dismiss_story_popups(app, self.root)
        lab = app.open_engineering_lab(); self.root.update()
        word = '체험한 Stage' if practice else '통과한 Stage'
        gauge = lab.progress_gauge
        self.assertEqual(gauge.itemcget(gauge.find_withtag('title')[0], 'text'), '진행률 · '+word)   # 두 문구 모두 유지
        self.assertEqual(gauge.itemcget(gauge.find_withtag('value')[0], 'text'), '3 / 5')
        self.check_gauges(lab, 'practice' if practice else 'regular')
        self.assertEqual(self.errors, [])

    def test_regular_training_gauges_do_not_overlap(self):
        self.run_case(practice=False)

    def test_practice_gauges_do_not_overlap(self):
        self.run_case(practice=True)


class DeferredStoryDialogGuiTests(unittest.TestCase):
    """교육창은 숨긴 채 완성·기록한 뒤 idle 시점에 표시합니다. 부모 MessageDialog.reveal()(글 전체 표시)과 이름이
    겹쳐 생성자에서 AttributeError가 나던 실험 회귀(ui-polish-001)도 함께 막습니다."""
    def setUp(self):
        self.root = tk.Tk()
        self.root.geometry('1280x800+0+0')
        self.addCleanup(self.root.destroy)
        self.errors = []
        self.root.report_callback_exception = lambda *a: self.errors.append(a)

    def test_dialog_class_keeps_message_text_reveal(self):
        from story_dialog import StoryDialogueDialog, StoryReviewDialog
        pages = [('선배 엔지니어', '첫 페이지'), ('선배 엔지니어', '둘째 페이지')]
        shown = StoryDialogueDialog(self.root, pages)                     # 기존 기본값: 생성 즉시 표시
        self.root.update()
        self.assertTrue(shown.winfo_viewable())
        self.assertEqual(shown.shown, len(shown.full_text))               # MessageDialog.reveal()이 그대로 동작
        shown.next(); self.root.update()
        self.assertEqual((shown.index, shown.shown), (1, len(shown.full_text)))
        hidden = StoryDialogueDialog(self.root, pages, show=False)
        self.root.update()
        self.assertFalse(hidden.winfo_viewable())
        self.assertTrue(hidden.show_window())
        self.assertFalse(hidden.show_window())                           # 한 번만 표시
        self.root.update()
        self.assertTrue(hidden.winfo_viewable())
        self.assertTrue(hidden.placement['inside_work_area'])
        hidden.destroy()
        self.assertFalse(hidden.show_window())                           # 닫힌 창은 무시
        review = StoryReviewDialog(self.root); self.root.update()
        self.assertTrue(review.winfo_viewable())
        self.assertEqual(self.errors, [])

    def test_chapter_start_dialog_shows_once_after_control_room_idle(self):
        db = Database(':memory:'); self.addCleanup(db.close)
        app = SimulatorApp(self.root, db, mode='story', start_chapter=2, seed=5)
        self.addCleanup(app.network.stop)
        window = app.story_window
        self.assertIsNotNone(window)
        self.assertFalse(window.winfo_viewable())                        # 같은 콜백 안에서는 아직 숨김
        self.assertIs(app.show_story_event(), window)                    # 표시 전 재호출도 새 창을 만들지 않음
        self.root.update()
        self.assertTrue(window.winfo_viewable())
        self.assertEqual(window.geometry().split('+')[0], '820x470')
        self.assertTrue(window.placement['inside_work_area'])
        self.assertTrue(window.next_button.winfo_viewable())
        dialogs = [w for w in self.root.winfo_children() if type(w).__name__ == 'StoryDialogueDialog']
        self.assertEqual(len(dialogs), 1)
        self.assertEqual(self.errors, [])

    def test_dialog_closed_before_idle_is_never_shown(self):
        db = Database(':memory:'); self.addCleanup(db.close)
        app = SimulatorApp(self.root, db, mode='story', start_chapter='3b', seed=5)
        self.addCleanup(app.network.stop)
        app.story_window.destroy()                                        # 예약된 표시 전에 닫힘
        self.root.update()
        self.assertFalse([w for w in self.root.winfo_children() if type(w).__name__ == 'StoryDialogueDialog'])
        self.assertEqual(self.errors, [])


if __name__ == '__main__':
    unittest.main()
