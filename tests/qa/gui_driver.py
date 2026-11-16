"""실제 Tk 화면을 OS 마우스 입력으로 조작하는 QA 하네스(Windows 전용).

- 게임은 이 프로세스의 메인 스레드에서 실제 `ModeSelection` → `SimulatorApp`으로 실행합니다.
- 시나리오는 별도 스레드에서 돌며 Tk 객체는 `call()`(메인 스레드 실행)로만 조회합니다.
- 클릭은 Win32 SendInput 실제 마우스 이벤트입니다(`click`). 위젯 좌표만 Tk에서 조회합니다.
  클릭 직전 그 좌표의 최상위 창이 이 프로세스의 창인지 확인하고, 아니면 클릭하지 않고 중단합니다.
- 저장은 임시 디렉터리의 별도 슬롯만 사용합니다(사용자 DB·슬롯·체크포인트 미사용).
- 화면은 PIL.ImageGrab으로 실제 화면을 캡처합니다(그림을 재구성하지 않음).
게임 규칙·진행 상태를 직접 바꾸는 호출은 하지 않습니다(조회 전용 + 종료 정리만).
"""
import ctypes
import ctypes.wintypes as wt
import json
import os
import queue
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

user32 = ctypes.windll.user32


# ---------------------------------------------------------------- Win32 입력/창
class POINT(ctypes.Structure):
    _fields_ = [('x', ctypes.c_long), ('y', ctypes.c_long)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [('dx', ctypes.c_long), ('dy', ctypes.c_long), ('mouseData', wt.DWORD),
                ('dwFlags', wt.DWORD), ('time', wt.DWORD), ('dwExtraInfo', ctypes.POINTER(ctypes.c_ulong))]


class INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [('mi', MOUSEINPUT), ('pad', ctypes.c_byte * 32)]
    _anonymous_ = ('u',)
    _fields_ = [('type', wt.DWORD), ('u', _U)]


MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP = 0x0002, 0x0004
GA_ROOT = 2


def _mouse(flag):
    inp = INPUT(type=0)
    inp.mi = MOUSEINPUT(0, 0, 0, flag, 0, None)
    if user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT)) != 1:
        raise OSError('SendInput 실패')


def window_pid(hwnd):
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def owner_at(x, y):
    hwnd = user32.WindowFromPoint(POINT(x, y))
    return hwnd, window_pid(hwnd) if hwnd else 0


def window_rect(hwnd):
    r = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


def window_title(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(hwnd, buf, 256)
    return buf.value


def own_windows():
    """이 프로세스의 보이는 최상위 창 목록 [(hwnd, title, rect)]."""
    pid, found = os.getpid(), []
    proc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

    def cb(hwnd, _):
        if user32.IsWindowVisible(hwnd) and window_pid(hwnd) == pid:
            found.append((hwnd, window_title(hwnd), window_rect(hwnd)))
        return True
    user32.EnumWindows(proc(cb), 0)
    return found


class AbortQA(RuntimeError):
    """안전 조건(다른 프로그램 창 위 클릭 등)을 만족하지 않아 자동 조작을 중단합니다."""


# ---------------------------------------------------------------- 창 감시(흰 창 점등 후보)
class WindowMonitor(threading.Thread):
    """15ms마다 이 프로세스의 보이는 최상위 창을 조사해 등장·이동·사라짐을 기록합니다.
    새 창이 처음 보인 순간 그 영역을 실제 캡처해 흰 픽셀 비율을 잽니다(게임 배경은 어두운 색)."""
    def __init__(self, harness):
        super().__init__(daemon=True)
        self.h, self.stop_flag, self.events, self.known = harness, threading.Event(), [], {}

    def run(self):
        while not self.stop_flag.is_set():
            try:
                now = {hwnd: (title, rect) for hwnd, title, rect in own_windows()}
            except Exception:
                now = {}
            t = round(time.perf_counter() - self.h.t0, 3)
            for hwnd, (title, rect) in now.items():
                if hwnd not in self.known:
                    white, frame = self.h.white_ratio(rect, keep=True)
                    self.events.append({'t': t, 'step': self.h.step, 'event': 'appear', 'title': title,
                                        'rect': rect, 'white_ratio': white})
                    if white is not None and white > .35 and frame is not None:
                        # 흰 비율을 잰 바로 그 프레임을 저장합니다(다시 찍으면 이미 그려진 뒤일 수 있음).
                        name = f'flash_{len(self.events):03d}_{t:.3f}s.png'
                        frame.save(self.h.out / 'shots' / name)
                        self.h.shots.append({'file': name, 'step': self.h.step, 'note': f'새 창 등장 순간 프레임(흰 비율 {white})',
                                             'rect': rect, 'keep': False})
                elif self.known[hwnd][1] != rect:
                    self.events.append({'t': t, 'step': self.h.step, 'event': 'move', 'title': title,
                                        'from': self.known[hwnd][1], 'rect': rect})
            for hwnd in set(self.known) - set(now):
                self.events.append({'t': t, 'step': self.h.step, 'event': 'hide', 'title': self.known[hwnd][0]})
            self.known = now
            time.sleep(.015)


# ---------------------------------------------------------------- 하네스
class Harness:
    def __init__(self, out_dir):
        self.out = Path(out_dir)
        (self.out / 'shots').mkdir(parents=True, exist_ok=True)
        self.tmp = Path(tempfile.mkdtemp(prefix='srs_qa_'))
        self.q, self.step, self.t0 = queue.Queue(), 'boot', time.perf_counter()
        self.shots, self.log, self.checks = [], [], []
        self.scale, self.clicks, self.frame_trace = None, 0, []

    # -- 격리 설정: 게임 모듈을 import하기 전에 기본 DB 경로를 임시 디렉터리로 바꿉니다.
    def isolate(self):
        import database
        database.DB_PATH = self.tmp / 'aidc_game.db'
        database.STORY_DB_PATH = self.tmp / 'aidc_story.db'
        import aidc.storage.story_slots as story_slots
        story_slots.STORY_DB_PATH = database.STORY_DB_PATH
        import main
        main.DB_PATH, main.STORY_DB_PATH = database.DB_PATH, database.STORY_DB_PATH
        self.trace_frame_offset()
        self.main = main
        self.slots = story_slots.StorySlots(self.tmp)
        return main

    def trace_frame_offset(self):
        """진단 전용: 게임의 window_placement.frame_offset 입력·출력을 기록합니다(원래 함수를 그대로 호출, 결과 불변)."""
        import aidc.ui.window_placement as wp
        original, trace = wp.frame_offset, self.frame_trace

        def traced(dialog, parent):
            result = original(dialog, parent)
            try:
                trace.append({'t': round(time.perf_counter() - self.t0, 3), 'step': self.step, 'dialog': dialog.title(),
                              'dialog_viewable': bool(dialog.winfo_viewable()),
                              'dialog_root': (dialog.winfo_rootx(), dialog.winfo_rooty()), 'dialog_xy': (dialog.winfo_x(), dialog.winfo_y()),
                              'parent_root': (parent.winfo_rootx(), parent.winfo_rooty()), 'parent_xy': (parent.winfo_x(), parent.winfo_y()),
                              'result': result})
            except Exception as exc:
                trace.append({'error': str(exc)})
            return result
        wp.frame_offset = traced

    # -- 메인 스레드 실행
    def _poll(self):
        try:
            while True:
                fn, box, ev = self.q.get_nowait()
                try:
                    box['r'] = fn()
                except BaseException as exc:  # 시나리오 쪽에서 다시 던집니다.
                    box['e'] = exc
                ev.set()
        except queue.Empty:
            pass
        try:
            self.root.after(25, self._poll)
        except Exception:
            pass

    def call(self, fn, timeout=15):
        box, ev = {}, threading.Event()
        self.q.put((fn, box, ev))
        if not ev.wait(timeout):
            raise AbortQA('메인 스레드 응답 없음(모달 대기 등)')
        if 'e' in box:
            raise box['e']
        return box.get('r')

    def note(self, text):
        line = f'[{time.perf_counter()-self.t0:7.2f}s] [{self.step}] {text}'
        self.log.append(line)
        print(line, flush=True)

    def check(self, step, item, ok, detail='', kind='auto'):
        """kind: auto(자동 측정) / visual(캡처를 사람이 본 판단은 보고서에서 별도 표기)."""
        self.checks.append({'step': step, 'item': item, 'result': 'PASS' if ok is True else 'FAIL' if ok is False else str(ok),
                            'detail': detail, 'kind': kind})
        self.note(f"CHECK {'PASS' if ok is True else 'FAIL' if ok is False else ok}: {item} {detail}")

    # -- 위젯 조회(메인 스레드에서만 호출)
    def _walk(self, widget):
        yield widget
        for child in widget.winfo_children():
            yield from self._walk(child)

    def _visible_toplevels(self):
        tops = [self.root] + [w for w in self._walk(self.root) if w.winfo_class() == 'Toplevel']
        return [t for t in tops if t.winfo_exists() and t.winfo_viewable() and t.state() in ('normal', 'zoomed')]

    def widget_info(self, w):
        top = w.winfo_toplevel()
        x, y, wd, ht = w.winfo_rootx(), w.winfo_rooty(), w.winfo_width(), w.winfo_height()
        tx, ty, tw, th = top.winfo_rootx(), top.winfo_rooty(), top.winfo_width(), top.winfo_height()
        text = ''
        try:
            text = w.cget('text')
        except Exception:
            pass
        # 가려짐: 위젯 중심점의 최상위 Tk 위젯이 같은 창의 다른(자신·자손이 아닌) 위젯이면 화면에서 보이지 않습니다.
        hit = w.winfo_containing(x + wd // 2, y + ht // 2)
        covered = bool(hit is not None and hit.winfo_toplevel() is top and not str(hit).startswith(str(w)))
        work = self.work_area()
        return {'path': str(w), 'class': w.winfo_class(), 'text': str(text), 'x': x, 'y': y, 'w': wd, 'h': ht,
                'state': (w.cget('state') if 'state' in w.keys() else ''),
                'inside_top': tx <= x and ty <= y and x + wd <= tx + tw and y + ht <= ty + th,
                'clipped_text': w.winfo_reqwidth() > wd + 2 or w.winfo_reqheight() > ht + 2,
                'covered': covered, 'covered_by': str(hit) if covered else '',
                'offscreen': x < work[0] or y < work[1] or x + wd > work[2] or y + ht > work[3],
                'top': str(top)}

    @staticmethod
    def work_area():
        """작업 표시줄을 뺀 화면 영역(이 프로세스의 논리 좌표)."""
        r = wt.RECT()
        user32.SystemParametersInfoW(0x30, 0, ctypes.byref(r), 0)
        return r.left, r.top, r.right, r.bottom

    def snapshot(self):
        """보이는 창·버튼·글자·강조 상태를 한 번에 조회합니다(조회 전용)."""
        def run():
            tops = []
            for t in self._visible_toplevels():
                buttons, labels, golds, texts = [], [], [], []
                for w in self._walk(t):
                    if w is not t and w.winfo_toplevel() is not t:
                        continue
                    if not w.winfo_ismapped():
                        continue
                    cls = w.winfo_class()
                    if cls in ('Button', 'Radiobutton', 'Checkbutton', 'TButton', 'TRadiobutton'):
                        buttons.append(self.widget_info(w))
                    elif cls == 'Label' and str(w.cget('text')).strip():
                        labels.append(self.widget_info(w))
                    elif cls == 'Text':
                        texts.append(w.get('1.0', 'end-1c'))
                    if cls == 'Frame' and getattr(w, 'tutorial_side', None):  # TutorialHighlight 금색 테두리(점멸 중 색 변화)
                        golds.append(self.widget_info(w) | {'part': str(getattr(w, 'tutorial_part', None))})
                tops.append({'path': str(t), 'title': t.title(), 'x': t.winfo_rootx(), 'y': t.winfo_rooty(),
                             'w': t.winfo_width(), 'h': t.winfo_height(), 'buttons': buttons, 'labels': labels,
                             'texts': texts, 'gold_edges': golds})
            return {'tops': tops, 'screen': (self.root.winfo_screenwidth(), self.root.winfo_screenheight())}
        return self.call(run)

    def find(self, text, top=None, exact=False, classes=None):
        """보이는 창에서 글자가 일치하는 위젯 정보를 찾습니다(가장 위 창 우선)."""
        snap = self.snapshot()
        for t in reversed(snap['tops']):
            if top and top not in (t['title'], t['path']):
                continue
            for item in t['buttons'] + t['labels']:
                if classes and item['class'] not in classes:
                    continue
                if (item['text'] == text) if exact else (text in item['text']):
                    return item
        return None

    def wait_for(self, predicate, timeout=15, interval=.2, what=''):
        end = time.time() + timeout
        while time.time() < end:
            value = predicate()
            if value:
                return value
            time.sleep(interval)
        raise AbortQA(f'시간 초과: {what}')

    def wait_text(self, text, timeout=15, **kw):
        return self.wait_for(lambda: self.find(text, **kw), timeout, what=f'"{text}" 표시')

    # -- 실제 마우스 클릭
    def click(self, item, dx=None, dy=None, settle=.6):
        x = item['x'] + (item['w'] // 2 if dx is None else dx)
        y = item['y'] + (item['h'] // 2 if dy is None else dy)
        hwnd, pid = owner_at(x, y)
        if pid != os.getpid():
            # 게임 창이 가려져 있으면 해당 창만 앞으로 가져온 뒤 한 번 더 확인합니다.
            self.call(lambda: (self.root.nametowidget(item['top']).lift(), self.root.nametowidget(item['top']).focus_force()))
            time.sleep(.4)
            hwnd, pid = owner_at(x, y)
            if pid != os.getpid():
                raise AbortQA(f'클릭 위치({x},{y})의 창이 게임 창이 아닙니다(다른 프로그램 보호를 위해 중단).')
        user32.SetCursorPos(x, y)
        time.sleep(.08)
        _mouse(MOUSEEVENTF_LEFTDOWN)
        time.sleep(.06)
        _mouse(MOUSEEVENTF_LEFTUP)
        self.clicks += 1
        self.note(f"실제 클릭 ({x},{y}) '{item['text'][:30]}' [{item['class']}]")
        time.sleep(.15)
        self.park()
        time.sleep(settle)

    def park(self):
        """캡처에 마우스 올림 색이 남지 않도록 커서를 관제실 왼쪽 위 로고 영역으로 옮깁니다(클릭 없음)."""
        try:
            x, y = self.call(lambda: (self.root.winfo_rootx() + 30, self.root.winfo_rooty() + 30))
            user32.SetCursorPos(x, y)
        except Exception:
            pass

    def maximize_root(self):
        """사용자처럼 관제실 제목 표시줄의 [최대화] 버튼을 실제 클릭합니다."""
        hwnd = self.call(lambda: int(self.root.wm_frame(), 16))
        left, top, right, _ = window_rect(hwnd)
        item = {'x': right - 76, 'y': top + 15, 'w': 0, 'h': 0, 'text': '창 최대화(제목 표시줄)', 'class': 'caption', 'top': '.'}
        self.click(item, settle=1.2)
        state = self.call(lambda: self.root.state())
        if state != 'zoomed':
            raise AbortQA(f'최대화 버튼 클릭 후 창 상태가 {state}입니다.')
        return state

    def burst(self, seconds=2.0, interval=.03):
        """시간 진행 직후 관제실 영역을 연속 캡처해 프레임별 흰 픽셀 비율을 기록합니다(백그라운드 스레드)."""
        frames = []

        def run():
            end = time.time() + seconds
            while time.time() < end:
                rects = [r for _, _, r in own_windows()]
                if rects:
                    rect = (min(r[0] for r in rects), min(r[1] for r in rects), max(r[2] for r in rects), max(r[3] for r in rects))
                    t = round(time.perf_counter() - self.t0, 3)
                    try:
                        img = self._grab(self.phys(rect))
                        small = img.convert('L').resize((160, 90))
                        ratio = sum(1 for v in small.getdata() if v > 235) / (160 * 90)
                        frames.append({'t': t, 'white_ratio': round(ratio, 3), 'img': img, 'windows': len(rects)})
                    except Exception:
                        pass
                time.sleep(interval)
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        return thread, frames

    def click_text(self, text, **kw):
        settle = kw.pop('settle', .6)
        item = self.wait_text(text, **kw)
        if item.get('state') == 'disabled':
            raise AbortQA(f'"{text}" 버튼이 비활성 상태입니다.')
        self.click(item, settle=settle)
        return item

    # -- 화면 캡처
    def _grab(self, bbox_phys=None):
        from PIL import ImageGrab
        return ImageGrab.grab(bbox=bbox_phys)

    def calibrate(self):
        img = self._grab()
        logical = (user32.GetSystemMetrics(0), user32.GetSystemMetrics(1))
        self.scale = img.size[0] / logical[0]
        self.note(f'캡처 해상도 {img.size}, 논리 해상도 {logical}, 배율 {self.scale:.3f}')
        return img.size, logical

    def phys(self, rect):
        s = self.scale or 1
        return tuple(int(round(v * s)) for v in rect)

    def white_ratio(self, rect, keep=False):
        """rect 영역의 흰 픽셀 비율. keep=True면 (비율, 캡처한 원본 프레임)을 돌려줍니다."""
        try:
            l, t, r, b = self.phys(rect)
            if r - l < 10 or b - t < 10:
                return (None, None) if keep else None
            frame = self._grab((l, t, r, b))
            data = frame.convert('L').resize((80, 60)).getdata()
            ratio = round(sum(1 for v in data if v > 235) / len(data), 3)
            return (ratio, frame) if keep else ratio
        except Exception:
            return (None, None) if keep else None

    def shot(self, name, rect=None, note='', keep=True):
        """이 프로세스의 보이는 창 전체를 감싸는 영역(또는 rect)을 실제 화면에서 캡처합니다."""
        if rect is None:
            rects = [r for _, _, r in own_windows()]
            if not rects:
                return None
            rect = (min(r[0] for r in rects), min(r[1] for r in rects), max(r[2] for r in rects), max(r[3] for r in rects))
        sw, sh = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        rect = (max(0, rect[0]), max(0, rect[1]), min(sw, rect[2]), min(sh, rect[3]))
        path = self.out / 'shots' / f'{len(self.shots)+1:02d}_{name}.png'
        self._grab(self.phys(rect)).save(path)
        self.shots.append({'file': path.name, 'step': self.step, 'note': note, 'rect': rect, 'keep': keep})
        self.note(f'캡처 {path.name} {note}')
        return path

    # -- 실행
    def run(self, scenario):
        import tkinter as tk
        main = self.isolate()
        self.root = tk.Tk()
        self.selector = main.ModeSelection(self.root, story_slots=self.slots)
        self.root.after(25, self._poll)
        self.monitor = WindowMonitor(self)
        self.result = {'error': None}

        def worker():
            try:
                time.sleep(1.0)
                self.calibrate()
                self.monitor.start()
                scenario(self)
            except BaseException as exc:
                import traceback
                self.result['error'] = f'{type(exc).__name__}: {exc}'
                self.note('중단: ' + traceback.format_exc())
                try:
                    self.shot('abort_state', note='중단 시점 화면')
                except Exception:
                    pass
            finally:
                self.monitor.stop_flag.set()
                try:
                    self.call(self.close_game, timeout=20)
                except Exception as exc:
                    self.note(f'종료 처리 오류: {exc}')
        threading.Thread(target=worker, daemon=True).start()
        self.root.mainloop()
        return self.result

    def cleanup(self):
        """이 하네스가 만든 임시 저장 디렉터리만 지웁니다. 지우기 전 파일 목록을 돌려줍니다."""
        import shutil
        files = sorted(p.name for p in self.tmp.iterdir()) if self.tmp.exists() else []
        if self.tmp.exists() and self.tmp.name.startswith('srs_qa_'):
            shutil.rmtree(self.tmp, ignore_errors=True)
        return files

    def close_game(self):
        """테스트 종료 정리: 열린 게임은 기존 종료 처리(on_close: 저장·DB 닫기)로 닫습니다."""
        app = getattr(self.selector, 'app', None)
        selector = getattr(app, 'mode_selector', None) if app else None
        if app is not None and not getattr(app, 'closed', True):
            app.on_close()
        else:
            self.root.destroy()
        return selector

    def dump(self, name):
        (self.out / name).write_text(json.dumps({'checks': self.checks, 'shots': self.shots, 'log': self.log,
                                                 'windows': self.monitor.events, 'result': self.result},
                                                ensure_ascii=False, indent=1), encoding='utf-8')
