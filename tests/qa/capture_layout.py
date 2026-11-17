"""layout-001 수정 전후 화면·좌표 기록. 전체 플레이나 DPI 설정 변경 없음."""
import json
import os
from pathlib import Path
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tests.qa import inspect_regression_layout as capture
from tests.run_gui import preflight, saved_files
from tests.test_tutorial_ux import TutorialGuiTests
from tests.test_play_modes_gui import PlayModesGuiTests
from tests.test_console import ConsoleTests
from tests.support import start_legacy_plan


def native_click(widget, x=None, y=None):
    """기존 Win32 드라이버로 이 프로세스의 확인된 위젯에만 실제 클릭합니다."""
    from tests.qa.gui_driver import POINT, owner_at, user32, _mouse, MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP
    user32.WindowFromPoint.argtypes = [POINT]
    root = widget.winfo_toplevel()
    root.lift(); root.focus_force(); root.update()
    x = widget.winfo_width()//2 if x is None else x
    y = widget.winfo_height()//2 if y is None else y
    sx, sy = widget.winfo_rootx()+x, widget.winfo_rooty()+y
    hit = root.winfo_containing(sx, sy)
    if not widget.winfo_viewable() or hit is not widget or owner_at(sx, sy)[1] != os.getpid():
        raise RuntimeError('클릭 대상이 보이지 않거나 이 프로세스의 창이 아닙니다.')
    user32.SetCursorPos(sx, sy)
    root.update(); time.sleep(.03)
    try:
        _mouse(MOUSEEVENTF_LEFTDOWN); time.sleep(.03)
    finally:
        _mouse(MOUSEEVENTF_LEFTUP)
    root.update()
    return [sx, sy]


def native_checks(size, results):
    results['size'] = size

    def inspector(c):
        c.root.geometry(size); c.resources(); c.root.update()
        p = c.app.resources
        area = p.inspector_scroll
        item = next(i for i in p.inspector.find_all() if p.inspector.type(i) == 'text'
                    and p.inspector.itemcget(i, 'text').startswith('전력 총'))
        clicks = 0
        while clicks < 60:
            _, y1, _, y2 = p.inspector.bbox(item)
            origin = p.inspector.winfo_rooty()
            if area.canvas.winfo_rooty() <= origin+y1 and origin+y2 <= area.canvas.winfo_rooty()+area.canvas.winfo_height():
                break
            native_click(area.scrollbar, y=area.scrollbar.winfo_height()-8)
            clicks += 1
        else:
            raise AssertionError('실제 스크롤바 조작으로 전력 정보를 노출하지 못했습니다.')
        capture.shot(c.root, 'native_inspector_power_'+size)
        point = native_click(c.app.resource_confirm_button)
        assert c.app.session.story.resources_confirmed
        assert c.app.session.story.step == 'request'
        return {'scrollbar_clicks': clicks, 'confirm_point': point, 'step': c.app.session.story.step}

    def preview(c):
        c.root.geometry(size); c.preview()
        c.app.resources.show_preview(); c.root.update(); c.close_guide()
        point = native_click(c.app.resources.compare_button)
        dialog = c.app.allocation_window
        assert dialog.winfo_viewable()
        assert not c.app.session.story.preview_confirmed
        assert (c.app.center.gpu_used, c.app.center.power_used) == (0, 0)
        native_click(dialog.close_button)
        return {'compare_point': point, 'allocated': [c.app.center.gpu_used, c.app.center.power_used]}

    def rows(c):
        c.root.geometry(size); c.root.update()
        app = c.app
        app.next_request(); app.next_request()
        for rid in (3, 1, 2):
            app.select_request(rid); start_legacy_plan(app, 'economy')
        tree = app.active_list
        checks = []
        for rid in tree.get_children():
            # Treeview 기본 휠 바인딩으로 실제 행을 찾아 클릭합니다.
            tree.yview_moveto(0); c.root.update()
            wheels = 0
            def fully_visible():
                bounds = tree.bbox(rid)
                return bounds and bounds[1] >= 0 and bounds[1]+bounds[3] <= tree.winfo_height()
            while not fully_visible() and wheels < 20:
                tree.event_generate('<MouseWheel>', delta=-120); c.root.update(); wheels += 1
            assert fully_visible(), '휠로 행 전체를 노출하지 못했습니다: '+str((rid, tree.bbox(rid), tree.yview()))
            x, y, width, height = tree.bbox(rid)
            point = native_click(tree, x=x+width//2, y=y+height//2)
            assert app.session.selected_id == int(rid)
            assert tree.selection() == (rid,)
            x, y, width, height = tree.bbox(rid)
            bottom = tree.winfo_rooty()+y+height
            assert bottom <= app.body.winfo_rooty()+app.body.winfo_height()
            checks.append({'id': rid, 'wheel_events': wheels, 'click_point': point,
                           'selected': tree.selection(), 'row_bottom': bottom,
                           'body_bottom': app.body.winfo_rooty()+app.body.winfo_height()})
        capture.shot(c.root, 'native_active_rows_'+size)
        return {'rows': checks, 'tree': capture.measure(tree), 'body': capture.measure(app.body)}

    results['inspector'] = capture.inspect(TutorialGuiTests, inspector)
    results['preview'] = capture.inspect(TutorialGuiTests, preview)
    results['active_list'] = capture.inspect(ConsoleTests, rows)
    return results


def panel(c, preview=False):
    if preview:
        c.preview()
        c.app.resources.book.select(c.app.resources.review_frame)
        c.root.update(); c.close_guide()
    else:
        c.arrival(); c.app.network.select('A'); c.close_guide()
    rows = []
    for size in ('1000x650', '1280x680', '1366x768'):
        c.root.geometry(size+'+30+30'); c.root.update()
        p = c.app.resources
        target = p.compare_button if preview else c.app.resource_confirm_button
        data = {'size': size, 'target': capture.measure(target), 'highlight_key': c.h.key,
                'highlight_matches_button': c.h.target is target,
                'panel': capture.measure(p), 'inspector': capture.measure(p.inspector)}
        prefix = ('preview_' if preview else 'inspector_')+size
        capture.shot(c.root, prefix)
        area = getattr(p, 'review_scroll' if preview else 'inspector_scroll', None)
        if area is not None:
            data['viewport'] = capture.measure(area.canvas)
            data['scrollbar_shown'] = area.scrollbar_shown
            area.canvas.yview_moveto(1); c.root.update()
            data['scrolled_yview'] = area.canvas.yview()
            capture.shot(c.root, prefix+'_scrolled')
            area.canvas.yview_moveto(0); c.root.update()
        rows.append(data)
    return rows


def menus(c):
    rows = capture.modes(c)
    for size in ('1280x680', '1366x768'):
        c.root.geometry(size+'+30+30'); c.menu.show_practice_menu(); c.root.update()
        capture.shot(c.root, 'menu_practice_'+size)
    return rows


def main():
    out = Path(sys.argv[1]).resolve()
    (out/'screenshots').mkdir(parents=True, exist_ok=True)
    if (out/'observations.json').exists():
        raise FileExistsError('기존 계측을 덮어쓰지 않습니다.')
    capture.OUT = out
    before = saved_files()
    data = {'environment': preflight(), 'kind': 'real Tk fixture layout observations'}
    try:
        with patch('tkinter.messagebox._show', side_effect=AssertionError('Unexpected modal')):
            data['inspector'] = capture.inspect(TutorialGuiTests, panel)
            data['preview'] = capture.inspect(TutorialGuiTests, lambda c: panel(c, True))
            data['menus'] = capture.inspect(PlayModesGuiTests, menus)
            if '--native' in sys.argv:
                data['native'] = []
                for size in ('1000x650', '1280x680', '1366x768'):
                    result = {}
                    data['native'].append(result)
                    native_checks(size, result)
    except Exception as exc:
        data['error'] = str(exc)
        raise
    finally:
        data['user_data_unchanged'] = before == saved_files()
        (out/'observations.json').write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
        assert data['user_data_unchanged']


if __name__ == '__main__':
    main()
