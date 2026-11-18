"""layout-001: 작은 창의 실제 본문·고정 조작·목록 스크롤 접근성."""
import tempfile
from pathlib import Path
import tkinter as tk
from tkinter.font import Font
import unittest

from database import Database
from main import SimulatorApp
from session import GameSession
from tests.support import assert_tree_row_visible, dismiss_story_popups, start_legacy_plan
from tests import test_play_modes_gui as modes_fixture, test_tutorial_ux as tutorial_fixture
from aidc.ui import dpi

SIZES = ('1000x650', '1280x680', '1366x768')


def click_button(case, widget):
    """실제 위젯 중심의 hit-test와 Tk 마우스 바인딩을 함께 거칩니다."""
    root = widget.winfo_toplevel()
    root.update()
    x, y = widget.winfo_width()//2, widget.winfo_height()//2
    case.assertTrue(widget.winfo_viewable())
    case.assertIs(root.winfo_containing(widget.winfo_rootx()+x, widget.winfo_rooty()+y), widget)
    widget.event_generate('<Enter>')
    widget.event_generate('<ButtonPress-1>', x=x, y=y)
    widget.event_generate('<ButtonRelease-1>', x=x, y=y)
    root.update()


class LayoutGuiTests(unittest.TestCase):
    def fixture(self, cls=tutorial_fixture.TutorialGuiTests):
        fixture = cls()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        return fixture

    def test_inspector_items_scroll_into_view_with_confirmation_fixed(self):
        c = self.fixture(); c.resources()
        p = c.app.resources
        heights = []
        for size in SIZES:
            with self.subTest(size=size):
                c.root.geometry(dpi.geometry(size)); c.root.update()
                area = p.inspector_scroll
                heights.append(area.canvas.winfo_height())
                self.assertEqual(p.inspector.winfo_height(), 190)
                self.assertIs(c.h.target, c.app.resource_confirm_button)
                for item in p.inspector.find_all():
                    if p.inspector.type(item) != 'text':
                        continue
                    x1, y1, x2, y2 = p.inspector.bbox(item)
                    top = p.inspector.winfo_y()+y1
                    maximum = max(0, area.body.winfo_height()-area.canvas.winfo_height())
                    area.canvas.yview_moveto(min(top, maximum)/area.body.winfo_height())
                    c.root.update()
                    actual = p.inspector.winfo_rooty()
                    self.assertGreaterEqual(actual+y1, area.canvas.winfo_rooty())
                    self.assertLessEqual(actual+y2, area.canvas.winfo_rooty()+area.canvas.winfo_height())
                    self.assertLessEqual(x2, p.inspector.winfo_width())
                    self.assertIs(c.root.winfo_containing(p.inspector.winfo_rootx()+(x1+x2)//2,
                                                         actual+(y1+y2)//2), p.inspector)
                self.assertIsNone(c.h.pointer)
                self.assertTrue(all(edge.winfo_viewable() for edge in c.h.edges))
                if area.scrollbar_shown:
                    self.assertTrue(area.scrollbar.winfo_viewable())
                button = c.app.resource_confirm_button
                self.assertTrue(button.winfo_viewable())
                self.assertGreaterEqual(button.winfo_rooty(), area.canvas.winfo_rooty()+area.canvas.winfo_height())
        self.assertGreater(heights[-1], heights[0])
        before = (c.app.session.minute, c.app.center.gpu_used, c.app.center.power_used)
        c.root.geometry(dpi.geometry(SIZES[0])); c.root.update()
        click_button(self, c.app.resource_confirm_button)
        self.assertEqual(c.app.session.story.step, 'request')
        self.assertTrue(c.app.session.story.resources_confirmed)
        self.assertEqual(before, (c.app.session.minute, c.app.center.gpu_used, c.app.center.power_used))
        self.assertEqual(c.errors, [])

    def test_preview_compare_stays_clickable_without_reserving_resources(self):
        c = self.fixture(); c.preview()
        p = c.app.resources
        p.show_preview(); c.root.update(); c.close_guide()
        for size in SIZES:
            with self.subTest(size=size):
                c.root.geometry(dpi.geometry(size)); c.root.update()
                self.assertIs(c.h.target, p.compare_button)
                p.review_scroll.canvas.yview_moveto(1); c.root.update()
                self.assertTrue(p.compare_button.winfo_viewable())
                click_button(self, p.compare_button)
                dialog = c.app.allocation_window
                self.assertTrue(dialog.winfo_viewable())
                self.assertFalse(c.app.session.story.preview_confirmed)
                self.assertEqual((c.app.center.gpu_used, c.app.center.power_used), (0, 0))
                dialog.close_button.invoke(); c.root.update(); c.close_guide()
        self.assertEqual(c.errors, [])

    def test_new_tutorial_completes_through_small_window_controls(self):
        c = self.fixture(modes_fixture.PlayModesGuiTests)
        c.root.geometry(dpi.geometry(SIZES[0]))
        app = c.menu.new_tutorial(); c.root.update()
        app.story_window.skip_button.invoke(); app.story_window.next_button.invoke(); c.root.update()
        click_button(self, app.arrival_open_button)
        app.message_window.destroy(); c.root.update()
        click_button(self, app.action_buttons['start'])
        dialog = app.allocation_window
        dialog.plan_buttons[0].invoke(); dialog.start_button.invoke(); c.root.update()
        click_button(self, app.time_buttons[10])
        self.assertTrue(app.session.story.ui_done)
        self.assertEqual((app.center.gpu_used, app.center.power_used), (0, 0))
        self.assertTrue(app.chapter_window.winfo_exists())
        self.assertNotIn('chapter2', app.chapter_window.buttons)
        self.assertEqual(c.errors, [])

    def test_legacy_disk_resume_keeps_progress_and_can_confirm_resources(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name)/'legacy.db'
        db = Database(path)
        session = GameSession(db, mode='story', seed=9)
        session.confirm_story_arrival(); session.select_story_server('A')
        before = (session.minute, session.center.gpu_used, session.center.power_used)
        session.close()
        root = tk.Tk(); self.addCleanup(root.destroy)
        db = Database(path); self.addCleanup(db.close)
        app = SimulatorApp(root, db, mode='story')
        self.addCleanup(app.network.stop)
        root.geometry(dpi.geometry(SIZES[0])); root.update(); dismiss_story_popups(app, root)
        self.assertIsNone(app.session.story.onboarding)
        self.assertEqual(app.session.story.step, 'resources')
        click_button(self, app.resource_confirm_button)
        self.assertEqual(before, (app.session.minute, app.center.gpu_used, app.center.power_used))
        app.session.save()
        restored = GameSession(db, mode='story')
        self.assertTrue(restored.story.resources_confirmed)
        self.assertEqual(restored.story.step, 'request')

    def test_menu_header_version_and_buttons_fit_and_restore_large_size(self):
        c = self.fixture(modes_fixture.PlayModesGuiTests)
        from session import GameSession
        for mode, chapter in (('story', 1), ('tutorial', 1), ('story', 'lab')):
            db = c.factory(c.slots.reserve_new())
            GameSession(db, mode=mode, start_chapter=chapter); db.close()
        for size in SIZES:
            for category in ('tutorial', 'story', 'practice'):
                with self.subTest(size=size, category=category):
                    c.root.geometry(dpi.geometry(size)); c.menu.show_menu(category); c.root.update()
                    for widget in (c.menu.title_icon, c.menu.title_label, c.menu.version_label,
                                   c.menu.choices[category], *c.menu.menu_buttons[category].values()):
                        self.assertTrue(widget.winfo_viewable())
                        self.assertGreaterEqual(widget.winfo_rooty(), c.root.winfo_rooty())
                        self.assertLessEqual(widget.winfo_rooty()+widget.winfo_height(), c.root.winfo_rooty()+c.root.winfo_height())
                        self.assertGreaterEqual(widget.winfo_height(), widget.winfo_reqheight())
        self.assertEqual(Font(root=c.root, font=c.menu.title_label.cget('font')).cget('size'), 38)
        c.root.geometry(dpi.geometry(SIZES[0])); c.menu.show_modes(); c.root.update()
        self.assertEqual(Font(root=c.root, font=c.menu.title_label.cget('font')).cget('size'), 38)

    def test_multiple_active_rows_scroll_select_and_keep_text_inside_body(self):
        c = self.fixture()
        c.app.db_factory = lambda _: Database(':memory:')
        c.app.return_to_modes('free'); c.root.update()
        app = c.app.mode_selector.app
        self.addCleanup(app.db.close); self.addCleanup(app.network.stop)
        app.next_request(); app.next_request()
        for rid in (3, 1, 2):
            app.select_request(rid); start_legacy_plan(app, 'economy')
        self.assertEqual(len(app.active_list.get_children()), 3)
        for size in SIZES:
            with self.subTest(size=size):
                c.root.geometry(dpi.geometry(size)); c.root.update()
                tree = app.active_list
                tree.yview_moveto(0); c.root.update()
                top = tree.yview()
                tree.event_generate('<MouseWheel>', delta=-120); c.root.update()
                if size == SIZES[0]:
                    self.assertGreater(tree.yview()[0], top[0])
                for rid in tree.get_children():
                    tree.see(rid); c.root.update()
                    x, y, width, height = assert_tree_row_visible(self, tree, rid, app.body)
                    for column, value in zip(tree['columns'], tree.item(rid, 'values')):
                        self.assertLessEqual(Font(root=c.root, font='TkDefaultFont').measure(value), tree.column(column, 'width'))
                    tree.event_generate('<ButtonPress-1>', x=x+width//2, y=y+height//2)
                    tree.event_generate('<ButtonRelease-1>', x=x+width//2, y=y+height//2)
                    c.root.update()
                    self.assertEqual(app.session.selected_id, int(rid))
                    self.assertEqual(tree.selection(), (rid,))
        self.assertEqual(c.errors, [])


if __name__ == '__main__':
    unittest.main()
