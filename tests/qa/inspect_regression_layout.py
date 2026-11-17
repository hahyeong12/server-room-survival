"""GUI 회귀 실패의 배치만 계측·캡처합니다. 전체 플레이나 DPI 설정 변경은 하지 않습니다."""
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from PIL import ImageGrab
from tests.run_gui import preflight, saved_files
from tests.support import reveal_scroll_widget
from tests.test_conditions import ConditionGuiTests
from tests.test_play_modes_gui import PlayModesGuiTests
from tests.test_story import StoryGuiTests
from tests.test_story_patch import PatchGuiTests
from tests.test_tutorial_ux import TutorialGuiTests

OUT = ROOT/'docs/qa/gui-regression-001'


def rect(w):
    return [w.winfo_rootx(), w.winfo_rooty(), w.winfo_width(), w.winfo_height()]


def measure(w):
    return {'rect': rect(w), 'requested': [w.winfo_reqwidth(), w.winfo_reqheight()],
            'mapped': bool(w.winfo_ismapped()), 'class': w.winfo_class(),
            'text': str(w.cget('text')) if 'text' in w.keys() else ''}


def shot(root, name):
    root.lift(); root.update()
    x, y, w, h = rect(root)
    image = ImageGrab.grab()
    scale = image.width/root.winfo_screenwidth()
    image.crop(tuple(round(v*scale) for v in (x, y, x+w, y+h))).save(OUT/'screenshots'/f'{name}.png')


def inspect(case_type, action):
    case = case_type()
    try:
        case.setUp()
        return action(case)
    finally:
        case.doCleanups()


def modes(c):
    from session import GameSession
    for mode, chapter in (('story', 1), ('tutorial', 1), ('story', 'lab')):
        db = c.factory(c.slots.reserve_new())
        GameSession(db, mode=mode, start_chapter=chapter); db.close()
    rows = []
    for size in ('1000x650', '1280x680', '1366x768'):
        for category in ('tutorial', 'story', 'practice'):
            c.root.geometry(size+'+30+30')
            c.menu.show_menu(category); c.root.update()
            rows.append({'category': category, 'size': size, 'root': rect(c.root), 'content': measure(c.menu.content),
                         'buttons': {k: measure(w) for k, w in c.menu.menu_buttons[category].items()}})
            if size == '1000x650':
                shot(c.root, 'menu_'+category)
    return rows


def condition(c):
    import tkinter.font as font
    c.root.geometry('1000x650+30+30'); c.root.update()
    rows = []
    for k, w in c.app.action_buttons.items():
        data = measure(w)
        data.update(key=k, text_pixels=font.Font(root=c.root, font=w.cget('font')).measure(w.cget('text')))
        rows.append(data)
    shot(c.root, 'condition_minimum')
    return {'buttons': rows, 'body': measure(c.app.body),
            'active_list': measure(c.app.active_list),
            'first_row': c.app.active_list.bbox(c.app.active_list.get_children()[0]) if c.app.active_list.get_children() else None}


def inspector(c):
    c.root.geometry('1000x650+30+30'); c.root.update()
    canvas = c.app.resources.inspector
    rows = {'canvas': measure(canvas), 'items': [{'text': canvas.itemcget(i, 'text'), 'bbox': canvas.bbox(i)}
            for i in canvas.find_all() if canvas.type(i) == 'text']}
    shot(c.root, 'legacy_inspector_minimum')
    return rows


def completion(c):
    d = c.complete(); d.geometry('700x510'); c.root.update()
    rows = {'dialog': measure(d), 'summary_before': measure(d.summary), 'next_before': measure(d.next_notice),
            'buttons': {k: measure(w) for k, w in d.action_bar.buttons.items()}}
    shot(d, 'completion_scroll_top')
    reveal_scroll_widget(d.scroll, d.next_notice)
    rows['next_after_scroll'] = measure(d.next_notice)
    rows['viewport'] = measure(d.scroll.canvas)
    shot(d, 'completion_scroll_bottom')
    return rows


def targets(c):
    c.arrival(); c.app.network.select('A'); c.close_guide()
    rows = []
    for size in ('1000x650', '1280x680', '1366x768'):
        c.root.geometry(size+'+30+30'); c.root.update()
        rows.append({'size': size, 'key': c.h.key, 'target': measure(c.h.target),
                     'resource_button': measure(c.app.resource_confirm_button),
                     'selected_tab': c.app.resources.book.select()})
        if size == '1000x650':
            shot(c.root, 'legacy_highlight_minimum')
    return rows


def main():
    (OUT/'screenshots').mkdir(exist_ok=True)
    before = saved_files()
    data = {'kind': 'layout observations; unittest fixtures, not native autoplay', 'environment': preflight()}
    data['environment']['capture_size'] = list(ImageGrab.grab().size)
    with patch('tkinter.messagebox._show', side_effect=AssertionError('Unexpected modal')):
        data['modes'] = inspect(PlayModesGuiTests, modes)
        data['condition'] = inspect(ConditionGuiTests, condition)
        data['inspector'] = inspect(StoryGuiTests, inspector)
        data['completion'] = inspect(PatchGuiTests, completion)
        data['targets'] = inspect(TutorialGuiTests, targets)
    data['user_data_unchanged'] = before == saved_files()
    assert data['user_data_unchanged']
    (OUT/'layout-observations.json').write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
