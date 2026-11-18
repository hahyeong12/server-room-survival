"""chapter5-ux-001 실제 Tk 집중 검증: Lab 헤더 가시성과 학습 결과창의 학습/고객 작업 상태 구분.

학습 단계 준비는 기존 테스트 도우미(엔진 직접 호출)를 사용합니다. 네이티브 마우스/키보드 플레이 실적이 아닙니다.
"""
from pathlib import Path
import tempfile
import tkinter as tk
import unittest

from database import Database
from engineering_lab import TrainingResultDialog
from main import SimulatorApp
from tests.support import dismiss_story_popups
from tests.test_chapter3 import to_incident
from tests.test_chapter5_ux import to_stage5_judged
from tests.test_training import SERVER, game_snapshot, regular_after_3b
from aidc.ui import dpi

SIZES = ('1060x700', '900x620', '1280x720', '1366x768')


def header_labels(lab):
    header = lab.grid_slaves(row=0)[0]
    found, stack = [], [header]
    while stack:
        widget = stack.pop()
        for child in widget.winfo_children():
            if isinstance(child, tk.Label) and child.cget('text') and child.winfo_ismapped():
                found.append(child)
            stack.append(child)
    return found


class Chapter5UxGuiTests(unittest.TestCase):
    def make_app(self, db=None, practice=False, fresh=True):
        self.root = tk.Tk()
        self.root.geometry(dpi.geometry('1280x800+0+0'))
        self.addCleanup(safe_destroy, self.root)
        if db is None:
            db = Database(':memory:')
            self.addCleanup(db.close)
            if not practice:
                regular_after_3b(db).save()
        self.db = db
        options = {'start_chapter': 'lab', 'seed': 5} if practice else {}
        self.app = SimulatorApp(self.root, db, mode='story', **options)
        self.addCleanup(self.app.network.stop)
        self.errors = []
        self.root.report_callback_exception = lambda *args: self.errors.append(args)
        self.root.update()
        if not practice and fresh:
            self.app.begin_training()
        dismiss_story_popups(self.app, self.root)
        return self.app

    def open_lab(self):
        lab = self.app.open_engineering_lab()
        self.root.update()
        return lab

    def assert_header_visible(self, lab, kind):
        rid = self.app.session.training.rid
        run = self.app.session.runs[rid]
        for size in SIZES:
            for tab in ('연수 진행', '가상 터미널'):
                lab.geometry(dpi.geometry(size)); lab.show_tab(tab)
                lab.update(); lab.update_idletasks(); lab.update()
                right = lab.winfo_rootx()+lab.winfo_width()
                for item in header_labels(lab):
                    with self.subTest(kind=kind, size=size, tab=tab, text=item.cget('text')):
                        self.assertLessEqual(item.winfo_reqwidth(), item.winfo_width()+1)       # 글자가 잘리지 않음
                        self.assertLessEqual(item.winfo_rootx()+item.winfo_width(), right+1)     # 창 밖으로 나가지 않음
                text = lab.mission_label.cget('text')
                for part in (f'요청 #{rid}', run.mission['company_name'], run.mission['country'], run.mission['title']):
                    self.assertIn(part, text)                                                    # 업무 식별 정보 보존
                button = lab.return_button
                self.assertTrue(button.winfo_ismapped())
                self.assertLessEqual(button.winfo_rootx()+button.winfo_width(), right+1)        # 관제실 복귀 버튼 보임
                self.assertGreater(lab.book.winfo_height(), 300)                                # 탭 영역이 눌리지 않음
                if tab == '연수 진행':
                    bar = lab.training_bar                                                       # 하단 실행 버튼 영역
                    self.assertTrue(bar.winfo_ismapped())
                    self.assertLessEqual(bar.winfo_rooty()+bar.winfo_height(), lab.winfo_rooty()+lab.winfo_height()+1)

    def test_lab_header_fits_in_regular_training(self):
        app = self.make_app()
        to_stage5_judged(app.session)
        app.refresh(); dismiss_story_popups(app, self.root)
        lab = self.open_lab()
        self.assertEqual(lab.mode, 'training')
        self.assertIn('심화 연수', lab.mode_head.cget('text'))
        self.assert_header_visible(lab, 'training')
        self.assertEqual(self.errors, [])

    def test_lab_header_fits_in_practice(self):
        app = self.make_app(practice=True)
        to_stage5_judged(app.session)
        app.refresh(); dismiss_story_popups(app, self.root)
        lab = self.open_lab()
        self.assertEqual(lab.mode, 'practice')
        self.assertIn('정규 기록 아님', lab.mode_head.cget('text'))
        self.assert_header_visible(lab, 'practice')
        self.assertEqual(self.errors, [])

    def test_lab_header_fits_in_chapter3_preview(self):
        """같은 헤더를 쓰는 Chapter 3a 관찰 미리보기에도 회귀가 없어야 합니다(연수 탭 없음)."""
        self.root = tk.Tk()
        self.addCleanup(safe_destroy, self.root)
        db = Database(':memory:'); self.addCleanup(db.close)
        app = SimulatorApp(self.root, db, mode='story', start_chapter=3, seed=5)
        self.addCleanup(app.network.stop)
        s = app.session
        s.confirm_chapter3_briefing()
        a = s.story.chapter3.request_ids[0]
        s.read_conversation(a); s.selected_id = a; s.choose_plan('performance')
        to_incident(s, a)
        app.refresh(); dismiss_story_popups(app, self.root)
        lab = app.open_engineering_lab(); self.root.update()
        self.assertEqual(lab.mode, 'preview')
        for size in SIZES:
            lab.geometry(dpi.geometry(size)); lab.update(); lab.update_idletasks(); lab.update()
            right = lab.winfo_rootx()+lab.winfo_width()
            for item in header_labels(lab):
                with self.subTest(size=size, text=item.cget('text')):
                    self.assertLessEqual(item.winfo_reqwidth(), item.winfo_width()+1)
                    self.assertLessEqual(item.winfo_rootx()+item.winfo_width(), right+1)
            self.assertIn(f'요청 #{a}', lab.mission_label.cget('text'))
            self.assertIn('관찰 미리보기', lab.mode_head.cget('text'))

    def status_texts(self, window):
        return {key: widget.cget('text') for key, widget in window.status_rows.items()}

    def test_result_window_separates_learning_and_customer_job_over_time(self):
        app = self.make_app()
        s = app.session
        rid = to_stage5_judged(s)
        app.refresh(); dismiss_story_popups(app, self.root)
        lab = self.open_lab()
        self.assertNotIsInstance(app.chapter_window, TrainingResultDialog)     # ① Stage 5 미통과: 결과창 없음
        self.assertNotIn('통과했습니다', lab.goal_title.cget('text'))
        app.select_request(rid)
        app.respond('reroute'); dismiss_story_popups(app, self.root)          # ② 복구 버튼 직후
        self.assertFalse(s.training.done)
        self.assertNotIsInstance(app.chapter_window, TrainingResultDialog)
        lab = self.open_lab()
        lab.run_terminal(f'ping -c 3 {SERVER}')                               # ③ 사후 ping → 통과, 결과창 자동 표시
        self.root.update()
        window = app.chapter_window
        self.assertIsInstance(window, TrainingResultDialog)
        self.assertEqual(s.runs[rid].state.phase, 'recovering')
        self.assertEqual(window.heading.cget('text'), '심화 연수 · Stage 5 / 5 통과')
        texts = self.status_texts(window)
        self.assertEqual(texts['training'], 'Stage 5 / 5 통과')
        self.assertEqual(texts['network'], '백업 경로 우회 후 통신 복구 확인')
        self.assertIn('복구 준비 중', texts['job'])
        self.assertNotIn('완료', texts['job'])
        self.assertIn('관제실에서 시간을 진행', texts['remaining'])
        self.assertIn('복구 준비 중', lab.goal_detail.cget('text'))
        before = game_snapshot(s)
        window.refresh(s.training_result()); self.root.update()                 # 다시 그려도 상태 불변
        self.assertEqual(game_snapshot(s), before)
        app.advance_time(s.runs[rid].state.recovery_left)                       # ④ 준비 종료 → 진행 중(창을 연 채)
        dismiss_story_popups(app, self.root)
        self.assertEqual(s.runs[rid].state.phase, 'running')
        self.assertIs(app.chapter_window, window)
        texts = self.status_texts(window)
        self.assertTrue(texts['job'].startswith(f'요청 #{rid} · 진행 중'))
        finish_customer_job_via_gui(app, self.root, rid)                        # ⑤ 최종 완료·자원 반환
        texts = self.status_texts(window)
        self.assertIn('정상 완료 · 기한 준수', texts['job'])
        self.assertIn('GPU·전력 반환 완료', texts['job'])
        self.assertTrue(texts['remaining'].startswith('없음'))
        self.assertEqual((s.center.gpu_used, s.center.power_used), (0, 0))
        window.destroy(); app.chapter_window = None
        reopened = app.show_training_result(); self.root.update()               # 재열기
        self.assertEqual(self.status_texts(reopened), texts)
        self.assertEqual(self.errors, [])

    def test_result_after_save_and_resume_shows_current_job_state(self):
        folder = tempfile.TemporaryDirectory(); self.addCleanup(folder.cleanup)
        path = str(Path(folder.name) / 'ux.db')
        seeded = Database(path)
        regular_after_3b(seeded).save()
        seeded.close()
        expected = {}
        for phase in ('recovering', 'running', 'finished'):
            db = Database(path)
            self.addCleanup(db.close)
            app = self.make_app(db, fresh=phase == 'recovering')
            s = app.session
            if phase == 'recovering':                                    # 첫 실행: Stage 5 통과까지(결과창 자동 표시)
                rid = to_stage5_judged(s)
                app.refresh(); dismiss_story_popups(app, self.root)
                app.select_request(rid)
                app.respond('reroute'); dismiss_story_popups(app, self.root)
                self.open_lab().run_terminal(f'ping -c 3 {SERVER}'); self.root.update()
                window = app.chapter_window
            else:                                                        # 이어하기: 상단 [연수 결과]로 다시 열기
                self.assertTrue(s.training.done)
                self.assertEqual(s.runs[rid].state.phase, previous)
                self.assertEqual(app.story_complete_button.cget('text'), '연수 결과')
                window = app.show_training_result(); self.root.update()
                self.assertEqual(self.status_texts(window), expected[previous])   # 저장 전 화면과 같은 사실
                if phase == 'running':
                    app.advance_time(s.runs[rid].state.recovery_left)
                else:
                    finish_customer_job_via_gui(app, self.root, rid)
                dismiss_story_popups(app, self.root)
            self.assertIsInstance(window, TrainingResultDialog)
            self.assertEqual(s.runs[rid].state.phase, phase)
            expected[phase] = self.status_texts(window)
            previous = phase
            app.network.stop(); db.close()                               # 행동마다 저장되므로 그대로 닫고 다시 엽니다.
            self.root.destroy()
        self.assertIn('복구 준비 중', expected['recovering']['job'])
        self.assertIn('진행 중', expected['running']['job'])
        self.assertIn('정상 완료', expected['finished']['job'])
        self.assertEqual(self.errors, [])

    def test_practice_result_window_keeps_practice_label_and_job_state(self):
        app = self.make_app(practice=True)
        s = app.session
        rid = to_stage5_judged(s)
        app.refresh(); dismiss_story_popups(app, self.root)
        app.select_request(rid)
        app.respond('reroute'); dismiss_story_popups(app, self.root)
        lab = self.open_lab()
        lab.run_terminal(f'ping -c 3 {SERVER}'); self.root.update()
        window = app.chapter_window
        self.assertIsInstance(window, TrainingResultDialog)
        texts = self.status_texts(window)
        self.assertEqual(texts['training'], '다섯 Stage 체험 · 정규 기록 아님')
        self.assertIn('복구 준비 중', texts['job'])
        self.assertEqual(window.heading.cget('text'), 'Engineering Lab 연습 · 다섯 Stage 체험')
        self.assertEqual(self.errors, [])


def safe_destroy(root):
    try:
        root.destroy()
    except tk.TclError:          # 이어하기 검증에서 이미 닫은 창
        pass


def finish_customer_job_via_gui(app, root, rid):
    for _ in range(40):
        if app.session.runs[rid].state.phase == 'finished':
            return
        app.advance_time(10)
        dismiss_story_popups(app, root)
    raise AssertionError('고객 작업이 끝나지 않았습니다.')


if __name__ == '__main__':
    unittest.main()
