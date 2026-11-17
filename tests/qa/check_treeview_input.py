"""chapter2-002 집중 검사: 작은 Tk 목록의 수정 전후 실제 Windows 휠·키보드 입력.

게임 플레이/DB를 만들지 않습니다. fixture 행 생성·선택만 설정하고 스크롤/탐색은 SendInput만 사용합니다.
python tests/qa/check_treeview_input.py <새 출력 디렉터리>
"""
import ctypes
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
from autoplay_story_ch1 import StoryHarness, db_hashes
from gui_driver import INPUT, user32, AbortQA


def scenario(h):
    import tkinter as tk
    from tkinter import ttk
    h.step = '독립 Tk 휠 집중 검사'
    h.probe = {'kind': 'component_native_input', 'full_play_attempts': 0, 'events': [], 'inputs': [], 'lists': {}}

    def setup():
        h.selector.frame.pack_forget()
        h.root.title('서버실 생존기 QA | 5행 목록 실제 입력 계측')
        body = tk.Frame(h.root, bg='#0b1422')
        body.pack(fill='both', expand=True)
        tk.Label(body, text='수정 전·후 실제 휠 비교 | 5행 / 한 행 높이 뷰포트',
                 bg='#0b1422', fg='white', font=('맑은 고딕', 16)).pack(pady=20)
        area = tk.Frame(body, bg='#0b1422')
        area.pack(fill='x', padx=20)
        ttk.Style(h.root).configure('Treeview', rowheight=29)
        trees = {}
        for index, name in enumerate(('baseline', 'tutorial', 'story', 'free')):
            panel = tk.Frame(area, width=224, height=180, bg='#0b1422')
            panel.grid(row=0, column=index, padx=6)
            panel.grid_propagate(False)
            tk.Label(panel, text=name, bg='#0b1422', fg='white').place(x=0, y=0)
            tree = h.main.SimulatorApp.make_list(None, panel, ('id',), ('고객 / 테스트 행',), (210,), 1)
            tree.place(x=0, y=32, width=214, height=58)
            for rid in range(1, 6):
                tree.insert('', 'end', iid=str(rid), values=(f'고객 {rid}',))
            tree.selection_set('3')  # 독립 fixture. 스크롤이 이 선택을 유지하는지 검사합니다.
            if name == 'baseline':
                tree.bind('<MouseWheel>', lambda e, w=tree: w.yview_scroll(-int(e.delta/120), 'units'))
            original_tags = tree.bindtags()
            h.probe['lists'][name] = {'bindtags': original_tags,
                'widget_binding': tree.bind('<MouseWheel>'),
                'class_binding': tree.bind_class('Treeview', '<MouseWheel>'),
                'initial': read(tree)}
            before, preclass, afterclass = (f'QA_{name}_{stage}' for stage in ('before', 'preclass', 'afterclass'))
            tags = list(original_tags)
            tags.insert(0, before)
            offset = tags.index('Treeview')
            tags.insert(offset, preclass)
            tags.insert(offset+2, afterclass)
            tree.bindtags(tuple(tags))
            for tag, stage in ((before, 'before_widget'), (preclass, 'after_widget_before_class'), (afterclass, 'after_class')):
                tree.bind_class(tag, '<MouseWheel>',
                    lambda e, w=tree, n=name, st=stage: record(n, st, e.delta, w))
            trees[name] = tree
        h.trees = trees
        h.selector.app = SimpleNamespace(inbox=trees['baseline'])

    def read(tree):
        return {'yview': tree.yview(), 'selection': tree.selection(), 'focus': tree.focus(),
                'height': tree.winfo_height(), 'rows': {rid: tree.bbox(rid) for rid in tree.get_children()}}

    def record(name, stage, delta, tree):
        h.probe['events'].append({'list': name, 'stage': stage, 'delta': delta,
                                 'input': h.input_id, **read(tree)})

    def visible(state):
        return [rid for rid, box in state['rows'].items() if box and box[1]+box[3] <= state['height']]

    def wheel(name, delta):
        h.selector.app.inbox = h.trees[name]
        h.input_id = len(h.probe['inputs'])
        before = h.call(lambda: read(h.trees[name]))
        h.wheel_inbox(delta)
        after = h.call(lambda: read(h.trees[name]))
        h.probe['inputs'].append({'list': name, 'sent_delta': delta, 'before': before, 'after': after})
        return visible(after)

    def check(item, ok, detail=''):
        h.check(h.step, item, ok, str(detail))

    def key(vk):
        # 실제 OS 키 입력. 클릭으로 목록에 초점을 준 뒤 전경 소유를 다시 확인합니다.
        h.wait_clear()
        class KeyboardInput(ctypes.Structure):
            _fields_ = [('vk', ctypes.c_ushort), ('scan', ctypes.c_ushort), ('flags', ctypes.c_ulong),
                        ('time', ctypes.c_ulong), ('extra', ctypes.c_void_p)]
        for flags in (0, 2):
            event, data = INPUT(type=1), KeyboardInput(vk, 0, flags, 0, None)
            ctypes.memmove(ctypes.addressof(event.u), ctypes.byref(data), ctypes.sizeof(data))
            if user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(INPUT)) != 1:
                raise AbortQA('키보드 SendInput 실패')
            time.sleep(.06)
        time.sleep(.25)

    h.input_id = -1
    h.call(setup)
    time.sleep(.7)
    check('수정 후 세 목록은 위젯 휠 바인딩 없음', all(not h.probe['lists'][n]['widget_binding'] for n in ('tutorial', 'story', 'free')))
    baseline = [wheel('baseline', -120) for _ in range(2)]
    check('수정 전 실제 한 칸 입력이 두 행씩 건너뜀 재현', baseline == [['3'], ['5']], baseline)
    h.shot('wheel_before', note='수정 전: 실제 휠 2회에 1→3→5, 선택3 유지')
    wheel('baseline', 60)
    wheel('baseline', 60)
    events = [e for e in h.probe['events'] if e['list'] == 'baseline']
    check('실제 Tk 전달 delta 계측·위젯/클래스 각 이동 확인',
          any(e['delta'] == -120 and e['stage'] == 'after_widget_before_class' and e['yview'][0] == .2 for e in events)
          and any(e['delta'] == -120 and e['stage'] == 'after_class' and e['yview'][0] == .4 for e in events), events)
    for name in ('tutorial', 'story', 'free'):
        down = [wheel(name, -120) for _ in range(4)]
        up = [wheel(name, 120) for _ in range(4)]
        check(name+' 실제 휠로 인접 5행 모두 왕복 접근', down == [['2'], ['3'], ['4'], ['5']]
              and up == [['4'], ['3'], ['2'], ['1']], {'down': down, 'up': up})
        check(name+' 휠 스크롤은 선택3 보존', h.call(lambda: h.trees[name].selection()) == ('3',))
    # 키보드 탐색은 명시적 사용자 선택이므로 순서대로 선택이 바뀌는 것이 정상입니다.
    h.click(h.call(lambda: h.widget_info(h.trees['story'])), dy=43)
    keyboard = []
    for vk in [0x28]*4+[0x26]*4:
        key(vk)
        keyboard.append(h.call(lambda: read(h.trees['story'])))
    h.probe['keyboard'] = keyboard
    check('실제 Down/Up 키로 1→5→1 탐색·행 노출', [s['selection'] for s in keyboard]
          == [('2',), ('3',), ('4',), ('5',), ('4',), ('3',), ('2',), ('1',)]
          and all(s['selection'][0] in visible(s) for s in keyboard), keyboard)
    h.shot('wheel_after', note='수정 후 세 목록: 인접 행 모두 접근·선택 유지, 실제 키보드 왕복')
    h.probe['passed'] = all(c['result'] == 'PASS' for c in h.checks)


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    with (out/'attempt.json').open('x', encoding='utf-8') as f:
        json.dump({'kind': 'focused_gui_not_full_play'}, f)
    before = db_hashes()
    h = StoryHarness(out)
    error = h.run(scenario)['error']
    h.check('보존', '기존 사용자 저장 파일 집합·해시 동일', before == db_hashes())
    data = {'error': error, 'kind': 'focused_gui_not_full_play', 'full_play_attempts': 0,
            'preflight': h.preflight_data, 'checks': h.checks, 'probe': getattr(h, 'probe', {}),
            'shots': h.shots, 'windows': h.monitor.events, 'occlusions': h.occlusions,
            'repo_db_unchanged': before == db_hashes(), 'repo_db_count': len(before),
            'passed': sum(c['result'] == 'PASS' for c in h.checks),
            'failed': sum(c['result'] == 'FAIL' for c in h.checks)}
    (out/'result.json').write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
    h.cleanup()
    raise SystemExit(bool(error or data['failed']))


if __name__ == '__main__':
    main()
