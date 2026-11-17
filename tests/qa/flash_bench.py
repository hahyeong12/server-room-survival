"""ui-polish-001 교육창 첫 등장 흰 프레임 측정(별도 프로세스 관측, 메모리/임시 DB만 사용).

python tests/qa/flash_bench.py <출력 JSON> <소스 폴더> <시나리오> <반복 수>

- 게임(자식 프로세스): 지정한 소스 폴더의 코드로 실제 모드 메뉴(ModeSelection)를 띄우고 mainloop를 그대로 돌립니다.
  메뉴가 그려진 뒤 메뉴 버튼과 같은 `start(...)`를 호출하거나(시나리오 ch2·ch3b·lab), 제4장 결과 화면에서
  [제5장 시작]과 같은 `begin_training()`을 호출합니다(시나리오 training). 시각은 시스템 공용 QPC로 기록합니다.
- 관측(부모 프로세스): 교육창 HWND의 표시 시각, 클라이언트 영역의 흰 비율(밝기>235, 80×60 축소)을 연속 캡처하고,
  별도 스레드가 SendMessageTimeout(WM_NULL)로 창의 메시지 처리 재개(입력 가능) 시각을 잽니다.
- 게임 프로세스 안에서 sleep·캡처를 하지 않으므로 이벤트 루프와 GIL을 막지 않습니다(이전 flash_probe와의 차이).
- 사용자 저장은 열지 않습니다(임시 폴더 슬롯). 게임 코드·DPI 설정을 바꾸지 않습니다.
"""
import ctypes
import ctypes.wintypes as wt
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading

kernel32, user32 = ctypes.windll.kernel32, ctypes.windll.user32
_freq = ctypes.c_int64()
kernel32.QueryPerformanceFrequency(ctypes.byref(_freq))


def qpc():
    """시스템 공용 고해상도 시계(초). 두 프로세스가 같은 기준을 씁니다."""
    value = ctypes.c_int64()
    kernel32.QueryPerformanceCounter(ctypes.byref(value))
    return value.value / _freq.value


TITLE = '현장 교육'
FRAMES = Path(os.environ['SRS_FLASH_FRAMES']) if os.environ.get('SRS_FLASH_FRAMES') else None  # 첫 캡처 6장 저장 폴더(선택)


# ───────────────────────── 게임(자식) ─────────────────────────
def child(source, scenario, out_path):
    sys.path.insert(0, source)
    os.chdir(source)
    import tkinter as tk
    import story_dialog
    from database import Database
    from aidc.storage.story_slots import StorySlots
    import main as game

    events = {'scenario': scenario, 'dialogs': []}
    original_init = story_dialog.StoryDialogueDialog.__init__
    original_center = story_dialog.center_dialog

    def center(dialog, parent, *args, **kwargs):
        # 창은 이미 만들어졌고(숨김) 아직 보이기 전입니다. 첫 Expose와 표시 호출 시각만 기록합니다.
        record = events['dialogs'][-1] if events['dialogs'] else {}

        def exposed(event):
            if event.widget is dialog and 't_expose' not in record:
                record['t_expose'] = qpc()
        dialog.bind('<Expose>', exposed, add='+')
        record['t_show_call'] = qpc()
        original_center(dialog, parent, *args, **kwargs)
        record['t_show_return'] = qpc()
    story_dialog.center_dialog = center

    def init(self, *args, **kwargs):
        record = {'t_build': qpc()}
        events['dialogs'].append(record)
        original_init(self, *args, **kwargs)
        record['t_built'] = qpc()                        # 생성자 끝(center_dialog 포함)
        record['hwnd'] = user32.GetParent(self.winfo_id())
        record['placement'] = getattr(self, 'placement', None)
        record['self'] = self
    story_dialog.StoryDialogueDialog.__init__ = init
    game.StoryDialogueDialog = story_dialog.StoryDialogueDialog

    temp = tempfile.TemporaryDirectory(prefix='srs-flash-')
    root = tk.Tk()
    slots = StorySlots(temp.name)
    menu = game.ModeSelection(root, story_slots=slots)
    holder = {}

    if scenario in ('training', 'next2'):
        path = slots.reserve_new()
        db = Database(path)
        if scenario == 'training':
            from tests.test_training import regular_after_3b
            regular_after_3b(db).save()
        else:
            from tests.test_chapter2 import after_chapter1
            after_chapter1(db).save()
        db.close()

    def trigger():
        events['t_trigger'] = qpc()
        if scenario in ('training', 'next2'):
            holder['app'] = app = menu.start('story', path=path, resume=True)
            events['t_resume_done'] = qpc()
            root.after(900, lambda: second(app))
            return
        chapter = {'ch2': 2, 'ch3b': '3b', 'lab': 'lab', 'ch3': 3}[scenario]
        holder['app'] = menu.start('story', path=slots.reserve_new(), fresh=True, chapter=chapter)
        events['t_callback_end'] = qpc()

    def second(app):
        # 제4장 결과 화면의 [제5장 시작] 버튼과 같은 호출입니다.
        events['dialogs'].clear()
        events['t_trigger'] = qpc()
        window = app.chapter_window
        events['result_window_open'] = bool(window is not None and window.winfo_exists())
        app.begin_training() if scenario == 'training' else app.begin_chapter2()  # 결과창의 다음 장 버튼과 같은 호출
        events['t_callback_end'] = qpc()

    def finish():
        app = holder.get('app')
        alive = [d for d in events['dialogs'] if d['self'].winfo_exists()]
        for d in events['dialogs']:
            win = d.pop('self')
            if win.winfo_exists():
                d['geometry'] = [win.winfo_rootx(), win.winfo_rooty(), win.winfo_width(), win.winfo_height()]
                d['buttons_viewable'] = all(b.winfo_viewable() for b in (win.next_button, win.previous_button))
                d['primary_inside'] = (win.next_button.winfo_rooty()+win.next_button.winfo_height()
                                       <= win.winfo_rooty()+win.winfo_height())
                d['pages'] = len(win.steps)
                d['placement'] = getattr(win, 'placement', None)  # 지연 표시 방식도 실제 표시 후 값을 읽습니다
        events['dialog_count'] = len(events['dialogs'])
        events['alive_dialogs'] = len(alive)
        events['story_window_is_last'] = bool(app and events['dialogs'] and app.story_window is not None
                                              and app.story_window.winfo_exists())
        Path(out_path).write_text(json.dumps(events, ensure_ascii=False))
        try:
            app.network.stop()
            app.closed = True
            app.db.close()
        except Exception:
            pass
        root.destroy()
        temp.cleanup()

    root.after(900, trigger)
    root.after(900 + (900 if scenario in ('training', 'next2') else 0) + 2600, finish)
    root.mainloop()


# ───────────────────────── 관측(부모) ─────────────────────────
WNDENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)


def find_dialog(pid):
    found = []

    def callback(hwnd, _):
        owner = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid and user32.IsWindowVisible(hwnd):
            buffer = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, buffer, 256)
            if TITLE in buffer.value:
                found.append(hwnd)
        return True
    user32.EnumWindows(WNDENUMPROC(callback), 0)
    return found


def client_rect(hwnd):
    rect = wt.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(rect))
    point = wt.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(point))
    return point.x, point.y, point.x+rect.right, point.y+rect.bottom


SMALL = (160, 92)


class Grabber:
    """GDI StretchBlt로 화면 영역을 작은 비트맵에 바로 축소해 읽습니다(PIL 전체 캡처보다 훨씬 빠름, 수 ms).
    관측 프로세스는 DPI 비인식이라 논리 좌표를 그대로 씁니다(게임 프로세스·전역 DPI 설정은 건드리지 않음)."""
    def __init__(self):
        import ctypes.wintypes as w
        self.gdi = gdi = ctypes.windll.gdi32
        for name in ('GetDC',):
            getattr(user32, name).restype = ctypes.c_void_p
        user32.GetDC.argtypes = [ctypes.c_void_p]
        gdi.CreateCompatibleDC.restype = gdi.CreateCompatibleBitmap.restype = gdi.SelectObject.restype = ctypes.c_void_p
        gdi.CreateCompatibleDC.argtypes = [ctypes.c_void_p]
        gdi.CreateCompatibleBitmap.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
        gdi.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        gdi.SetStretchBltMode.argtypes = [ctypes.c_void_p, ctypes.c_int]
        gdi.StretchBlt.argtypes = [ctypes.c_void_p] + [ctypes.c_int]*4 + [ctypes.c_void_p] + [ctypes.c_int]*4 + [w.DWORD]
        gdi.GetDIBits.argtypes = [ctypes.c_void_p, ctypes.c_void_p, w.UINT, w.UINT, ctypes.c_void_p, ctypes.c_void_p, w.UINT]
        self.screen = user32.GetDC(None)
        self.mem = gdi.CreateCompatibleDC(self.screen)
        self.bmp = gdi.CreateCompatibleBitmap(self.screen, *SMALL)
        gdi.SetStretchBltMode(self.mem, 4)  # HALFTONE
        header = (ctypes.c_uint32*10)()
        header[0], header[1], header[2] = 40, SMALL[0], ctypes.c_uint32(-SMALL[1]).value
        header[3] = 1 | (32 << 16)
        self.info = header
        self.buffer = ctypes.create_string_buffer(SMALL[0]*SMALL[1]*4)

    def grab(self, rect):
        left, top, right, bottom = rect
        old = self.gdi.SelectObject(self.mem, self.bmp)
        self.gdi.StretchBlt(self.mem, 0, 0, SMALL[0], SMALL[1], self.screen, left, top, right-left, bottom-top, 0x00CC0020)
        self.gdi.SelectObject(self.mem, old)
        self.gdi.GetDIBits(self.mem, self.bmp, 0, SMALL[1], self.buffer, self.info, 0)
        raw = self.buffer.raw
        return raw[1::4], raw  # 녹색 채널을 밝기 근사로 사용(흰색·어두운 배경 구분에 충분, 빠름)


def run_once(source, scenario, index, workdir):
    grabber = Grabber()
    out = Path(workdir) / f'{scenario}_{index}.json'
    process = subprocess.Popen([sys.executable, __file__, '--child', source, scenario, str(out)],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    samples, pings, state = [], [], {'hwnd': None, 'stop': False}

    def pinger():
        result = ctypes.c_size_t()
        while not state['stop']:
            hwnd = state['hwnd']
            if hwnd:
                sent = qpc()
                ok = user32.SendMessageTimeoutW(hwnd, 0, 0, 0, 0x0002, 3000, ctypes.byref(result))
                pings.append((sent, qpc(), bool(ok)))
            else:
                kernel32.Sleep(1)
    thread = threading.Thread(target=pinger, daemon=True)
    thread.start()
    first_seen = None
    while process.poll() is None:
        if state['hwnd'] is None:
            hits = find_dialog(process.pid)
            if hits:
                state['hwnd'] = hits[0]
                first_seen = qpc()
            else:
                kernel32.Sleep(1)
                continue
        if qpc()-first_seen > 1.6:
            break
        try:
            rect = client_rect(state['hwnd'])
            t = qpc()
            data, raw = grabber.grab(rect)
            samples.append((t, round(sum(1 for v in data if v > 235)/len(data), 3), data, raw if len(samples) < 40 else None))
        except Exception:
            kernel32.Sleep(1)
    state['stop'] = True
    process.wait(timeout=30)
    thread.join(timeout=5)
    stderr = process.stderr.read().decode('utf-8', 'replace')
    events = json.loads(out.read_text()) if out.exists() else {'error': stderr[-2000:]}
    if FRAMES is not None and samples:
        # 처음 캡처들을 한 장의 띠 이미지로 저장합니다(축소본, 시각 확인용).
        from PIL import Image
        frames = [(t, Image.frombuffer('RGBA', SMALL, raw, 'raw', 'BGRA', 0, 1).convert('RGB'))
                  for t, _, _, raw in samples if raw is not None][:24]
        strip = Image.new('RGB', ((SMALL[0]+4)*len(frames), SMALL[1]), 'red')
        for number, (_, image) in enumerate(frames):
            strip.paste(image, (number*(SMALL[0]+4), 0))
        strip.save(FRAMES/f'{Path(source).name}_{scenario}_{index}.png')
    # 최종 화면(마지막 캡처)과의 평균 밝기 차이로 '정상 프레임'을 판정합니다. 합성 전에 비친 뒤쪽 어두운 관제실을
    # 정상으로 오인하지 않기 위해서입니다(흰 비율만으로는 구분 불가).
    final = samples[-1][2] if samples else b''
    rows = [(t, w, round(sum(abs(a-b) for a, b in zip(data, final))/len(final), 1)) for t, w, data, _ in samples]
    return summarize(events, first_seen, rows, pings, stderr)


def summarize(events, first_seen, samples, pings, stderr):
    t0 = events.get('t_trigger')
    dialogs = events.get('dialogs') or [{}]
    first = dialogs[0]
    ms = lambda t: None if t is None or t0 is None else round((t-t0)*1000, 1)
    white = [(t, w) for t, w, _ in samples if w > 0.2]
    # 정상 프레임: 최종 화면과의 평균 밝기 차이 6 미만인 첫 캡처(마지막 흰 캡처 이후)
    last_white = white[-1][0] if white else None
    normal = next((t for t, w, diff in samples if diff < 6 and (last_white is None or t > last_white)), None)
    differing = [t for t, w, diff in samples if diff >= 6]
    responded = next((done for sent, done, ok in pings if ok and first_seen and sent >= first_seen), None)
    return {
        'trigger_to_build_ms': ms(first.get('t_build')),
        'trigger_to_shown_ms': ms(first.get('t_show_return')),    # center_dialog(deiconify) 반환 시점
        'trigger_to_built_ms': ms(first.get('t_built')),          # 교육창 생성자 끝
        'trigger_to_callback_end_ms': ms(events.get('t_callback_end')),
        'trigger_to_visible_ms': ms(first_seen),                  # 관측 프로세스가 처음 본 시점
        'trigger_to_first_expose_ms': ms(first.get('t_expose')),
        'trigger_to_first_normal_ms': ms(normal),                 # 흰 비율 0.05 미만 첫 캡처
        'trigger_to_input_ready_ms': ms(responded),               # 창 스레드가 메시지에 다시 응답한 시점
        'white_samples': len(white), 'samples': len(samples),
        'white_first_ms': ms(white[0][0]) if white else None,
        'white_last_ms': ms(white[-1][0]) if white else None,
        'white_duration_ms': round((white[-1][0]-first_seen)*1000, 1) if white and first_seen else 0.0,
        'max_white': max((w for _, w, _ in samples), default=None),
        'not_final_samples': len(differing),
        'not_final_last_ms': ms(differing[-1]) if differing else None,
        'timeline': [(ms(t), w, diff) for t, w, diff in samples[:80]],
        'dialog_count': events.get('dialog_count'), 'alive_dialogs': events.get('alive_dialogs'),
        'story_window_is_last': events.get('story_window_is_last'),
        'placement': first.get('placement'), 'geometry': first.get('geometry'),
        'buttons_viewable': first.get('buttons_viewable'), 'primary_inside': first.get('primary_inside'),
        'pages': first.get('pages'), 'result_window_open': events.get('result_window_open'),
        'error': events.get('error') or (stderr[-800:] if 'Traceback' in stderr else None),
    }


def main():
    if sys.argv[1] == '--child':
        return child(*sys.argv[2:5])
    output, source, scenario, repeats = sys.argv[1], str(Path(sys.argv[2]).resolve()), sys.argv[3], int(sys.argv[4])
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tests.run_gui import preflight, saved_files
    before = saved_files()
    report = {'source': Path(source).name, 'scenario': scenario, 'environment': preflight(), 'runs': []}
    with tempfile.TemporaryDirectory(prefix='srs-flash-out-') as workdir:
        for index in range(repeats):
            result = run_once(source, scenario, index, workdir)
            report['runs'].append(result)
            print(scenario, index, {k: result[k] for k in ('trigger_to_shown_ms', 'trigger_to_visible_ms', 'trigger_to_callback_end_ms', 'trigger_to_first_expose_ms', 'white_duration_ms', 'max_white', 'not_final_last_ms',
                                                         'white_samples', 'trigger_to_first_normal_ms',
                                                         'trigger_to_input_ready_ms', 'dialog_count', 'error')}, flush=True)
    report['user_data_unchanged'] = saved_files() == before
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(json.dumps(report, ensure_ascii=False, indent=1)+'\n', encoding='utf-8')
    print('user data unchanged', report['user_data_unchanged'])


if __name__ == '__main__':
    main()
