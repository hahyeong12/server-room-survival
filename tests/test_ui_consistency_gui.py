"""ui-consistency-001: 제4장 QA 후속 화면 정합성(실제 Tk).

1) 장 번호: 제4장(내부 키 '3b')의 장비 진단창·대응 카드 제목은 '제4장', 제3장 네트워크 진단창·카드는 '제3장'입니다.
2) 상태 배지: 장비 FAULT·REPAIRING·작업 이전 준비 중에는 '정상 실행 중'·초록(ok)으로 표시하지 않습니다.
3) 작업 이전 결과 카드: 이전 확정 직후(준비 10분이 남아 있을 때) 한 번만 표시하고, 시간 진행·이어하기 때 다시 띄우지 않습니다.

엔진 상태(시간·작업량·장애·원장)는 화면 확인만 하며 바꾸지 않습니다. 실제 GUI 환경에서만 실행합니다.
"""
import tempfile
import tkinter as tk
import unittest
from pathlib import Path

from database import Database
from main import SimulatorApp
from tests.support import dismiss_story_popups
from tests.test_chapter3 import to_incident


class Chapter4GuiBase(unittest.TestCase):
    def make_app(self, db=None, **options):
        root = tk.Tk(); self.addCleanup(self._destroy, root)
        if db is None:
            db = Database(':memory:')
        self.addCleanup(db.close)                       # 중간 실패에도 임시 DB 연결/잠금을 닫습니다(두 번 닫아도 안전).
        app = SimulatorApp(root, db, **options)
        self.addCleanup(app.network.stop)
        errors = []
        root.report_callback_exception = lambda *args: errors.append(args)
        root.update()
        return root, app, errors

    @staticmethod
    def _destroy(root):
        try:
            root.destroy()
        except tk.TclError:
            pass

    def begin_and_fault(self, root, app):
        a = app.session.story.chapter3b.request_ids[0]
        app.story_window.skip_button.invoke(); app.story_window.next_button.invoke(); root.update()
        dismiss_story_popups(app, root)
        app.open_message(a); app.message_window.destroy()
        app.action_buttons['start'].invoke(); root.update()
        dialog = app.allocation_window
        dialog.auto_button.invoke(); dialog.start_button.invoke(); root.update()
        dismiss_story_popups(app, root)
        app.advance_time(60); root.update()
        dismiss_story_popups(app, root)
        run = app.session.runs[a]
        self.assertEqual(app.session.hardware_servers(run), ('A',))
        return a, run

    def diagnose(self, root, app):
        app.action_buttons['hwdiag'].invoke(); root.update()
        window = app.diagnosis_window
        return window

    def migrate(self, root, app):
        app.action_buttons['migrate'].invoke(); root.update()
        dialog = app.allocation_window
        self.assertTrue(dialog.migration)
        dialog.start_button.invoke(); root.update(); root.update()


class ChapterLabelTests(Chapter4GuiBase):
    def test_hardware_diagnosis_and_card_titles_use_chapter_four(self):
        root, app, errors = self.make_app(mode='story', start_chapter='3b', seed=5)
        self.begin_and_fault(root, app)
        window = self.diagnose(root, app)
        self.assertIn('제4장', window.title())
        self.assertNotIn('3b', window.title()); self.assertNotIn('Chapter', window.title())
        window.close_button.invoke(); root.update()
        app.action_buttons['hwrepair'].invoke(); root.update()
        card = app.feedback_window
        self.assertTrue(card.winfo_exists())
        self.assertIn('제4장', card.title())
        self.assertNotIn('Chapter 3', card.title())
        self.assertIn('제4장', app.story_objective.cget('text'))        # 관제실과 같은 장 번호
        self.assertEqual(errors, [])

    def test_chapter_three_network_diagnosis_and_card_stay_chapter_three(self):
        root, app, errors = self.make_app(mode='story', start_chapter=3, seed=5)
        session = app.session
        a = session.story.chapter3.request_ids[0]
        session.confirm_chapter3_briefing(); session.read_conversation(a); session.selected_id = a
        session.choose_plan('performance')
        to_incident(session, a)
        dismiss_story_popups(app, root); app.refresh(); root.update()
        app.action_buttons['diagnose'].invoke(); root.update()
        window = app.diagnosis_window
        self.assertIn('제3장', window.title())
        self.assertNotIn('제4장', window.title())
        window.close_button.invoke(); root.update()
        session.respond('reroute' if session.runs[a].state.incident_kind == 'path_down' else 'compress')
        dismiss_story_popups(app, root)
        app.refresh(); app.open_chapter3_card(a); root.update()
        card = app.feedback_window
        self.assertIn('제3장', card.title())
        self.assertNotIn('제4장', card.title())
        self.assertEqual(errors, [])


class HardwareStatusBadgeTests(Chapter4GuiBase):
    def chip(self, app):
        return app.status_chip.cget('text'), app.status_chip.tone

    def active_status(self, app, rid):
        return app.active_list.item(str(rid), 'values')[1]

    def test_fault_repair_and_resume_badges_follow_the_hardware_state(self):
        root, app, errors = self.make_app(mode='story', start_chapter='3b', seed=5)
        a, run = self.begin_and_fault(root, app)
        work = run.state.work_done
        text, tone = self.chip(app)
        self.assertNotIn('정상 실행 중', text)
        self.assertIn('장비 장애', text)
        self.assertEqual(tone, 'fault')
        self.assertIn('장비 장애', self.active_status(app, a))
        self.diagnose(root, app).close_button.invoke(); root.update()
        app.action_buttons['hwrepair'].invoke(); root.update()
        dismiss_story_popups(app, root)
        text, tone = self.chip(app)
        self.assertNotIn('정상 실행 중', text)
        self.assertIn('장비 복구 중', text)
        self.assertEqual(tone, 'recover')
        self.assertIn('장비 복구', self.active_status(app, a))
        self.assertEqual(run.state.work_done, work)                         # 화면 갱신이 작업량을 바꾸지 않음
        app.advance_time(10); root.update(); dismiss_story_popups(app, root)
        self.assertEqual(self.session_state(app), 'REPAIRING')
        self.assertIn('장비 복구 중', self.chip(app)[0])
        app.advance_time(10); root.update(); dismiss_story_popups(app, root)
        self.assertEqual(self.session_state(app), 'HEALTHY')
        text, tone = self.chip(app)
        self.assertIn('정상 실행 중', text)
        self.assertEqual(tone, 'ok')
        self.assertEqual(errors, [])

    def session_state(self, app):
        return app.session.servers.hardware['A'].state

    def test_migration_preparation_is_not_shown_as_normal_running(self):
        root, app, errors = self.make_app(mode='story', start_chapter='3b', seed=5)
        a, run = self.begin_and_fault(root, app)
        self.diagnose(root, app).close_button.invoke(); root.update()
        self.migrate(root, app)
        dismiss_story_popups(app, root)
        self.assertEqual(run.migration_left, 10)
        text, tone = self.chip(app)
        self.assertNotIn('정상 실행 중', text)
        self.assertIn('작업 이전 준비 중', text)
        self.assertEqual(tone, 'recover')
        self.assertIn('이전 준비', self.active_status(app, a))
        app.advance_time(10); root.update(); dismiss_story_popups(app, root)
        self.assertEqual(run.migration_left, 0)
        self.assertEqual(self.session_state(app), 'FAULT')                  # 이전은 장애 서버를 고치지 않음
        text, tone = self.chip(app)
        self.assertIn('정상 실행 중', text)                                 # 작업은 B/C에서 정상 실행
        self.assertEqual(tone, 'ok')
        self.assertEqual(errors, [])


class MigrationCardTimingTests(Chapter4GuiBase):
    def test_migration_card_opens_right_after_confirmation_once(self):
        root, app, errors = self.make_app(mode='story', start_chapter='3b', seed=5)
        a, run = self.begin_and_fault(root, app)
        self.diagnose(root, app).close_button.invoke(); root.update()
        minute = app.session.minute
        self.migrate(root, app)
        card = app.feedback_window
        self.assertIsNotNone(card)
        self.assertTrue(card.winfo_exists())                                # 확정 직후(시간 진행 전)
        self.assertEqual(card.card['kind'], 'migrate')
        self.assertEqual((app.session.minute, run.migration_left), (minute, 10))
        self.assertIn('10분 남음', card.cells['현재 상태'].cget('text'))
        root.update()
        for button in (*card.buttons.values(), card.close_button):          # 행이 늘어도 버튼이 창 밖으로 잘리지 않음
            self.assertLessEqual(button.winfo_y()+button.master.winfo_y()+button.winfo_height(), card.winfo_height())
        key = f'{a}:migrate:1'
        self.assertIn(key, app.session.story.chapter3b.feedback_seen)
        card.close_button.invoke(); root.update()
        app.advance_time(10); root.update()
        self.assertEqual(app.session.minute, minute+10)                     # 시간은 한 번만 진행
        self.assertEqual(run.migration_left, 0)
        shown = app.feedback_window
        self.assertFalse(shown is not None and shown.winfo_exists() and getattr(shown, 'card', {}).get('kind') == 'migrate')
        self.assertEqual(app.session.story.chapter3b.feedback_seen.count(key), 1)
        # 다시 열어 보는 카드는 선택 당시 기록과 현재 상태를 구분합니다.
        app.action_buttons['result3b'].invoke(); root.update()
        reopened = app.feedback_window
        self.assertIn('정상 실행 중', reopened.cells['현재 상태'].cget('text'))
        self.assertIn('준비 10분', reopened.cells['선택 당시 결과'].cget('text'))   # 과거 선택 기록임을 표시
        self.assertEqual(errors, [])

    def test_migration_card_is_not_replayed_after_resume(self):
        folder = tempfile.TemporaryDirectory(); self.addCleanup(folder.cleanup)
        path = str(Path(folder.name)/'ch4.db')
        root, app, errors = self.make_app(Database(path), mode='story', start_chapter='3b', seed=5)
        a, run = self.begin_and_fault(root, app)
        self.diagnose(root, app).close_button.invoke(); root.update()
        self.migrate(root, app)
        self.assertEqual(app.feedback_window.card['kind'], 'migrate')
        app.on_close()
        root2, app2, errors2 = self.make_app(Database(path), mode='story')
        self.addCleanup(app2.on_close)
        root2.update()
        window = app2.feedback_window
        self.assertFalse(window is not None and window.winfo_exists())
        self.assertIsNone(app2.session.chapter3b_pending_feedback())
        self.assertEqual(app2.session.runs[a].migration_left, 10)          # 이어하기는 준비 시간을 그대로 복원
        self.assertEqual(errors + errors2, [])


if __name__ == '__main__':
    unittest.main()
