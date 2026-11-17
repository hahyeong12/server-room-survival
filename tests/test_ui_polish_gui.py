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


if __name__ == '__main__':
    unittest.main()
