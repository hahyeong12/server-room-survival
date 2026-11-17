"""교육창 첫 등장 흰 프레임 가설 계측(게임 코드 미변경, 메모리 DB만 사용).

가설: center_dialog()가 deiconify한 직후에는 자식 위젯이 아직 한 번도 그려지지 않았고, 호출자가 이벤트 루프로
돌아가기 전까지(저장·갱신 등) 그 상태가 화면에 남는다.
측정: center_dialog 반환 직후(동기, 이벤트 처리 전) / 감시 스레드 5ms 간격 / root.update() 후의 흰 비율.
사용: python flash_probe.py <repo> <chapter> <repeats> [variant]
"""
import ctypes
import ctypes.wintypes as wt
import json
from pathlib import Path
OUT = Path(__file__).parent / 'frames'; OUT.mkdir(exist_ok=True)
import sys
import threading
import time

repo, chapter, repeats = sys.argv[1], sys.argv[2], int(sys.argv[3])
variant = sys.argv[4] if len(sys.argv) > 4 else 'baseline'
sys.path.insert(0, repo)
chapter = int(chapter) if chapter.isdigit() else chapter

import tkinter as tk
from PIL import ImageGrab
import story_dialog
from aidc.ui import window_placement
from database import Database
from main import SimulatorApp

user32 = ctypes.windll.user32
full = ImageGrab.grab()
SCALE = full.size[0] / user32.GetSystemMetrics(0)


def outer_rect(widget):
    hwnd = user32.GetParent(widget.winfo_id())
    r = wt.RECT(); user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


FRAMES = {}
def white(rect, name=None):
    l, t, r, b = (int(round(v * SCALE)) for v in rect)
    # 제목줄(흰 배경 Windows 기본)을 제외한 클라이언트 영역만 봅니다.
    t += int(40 * SCALE)
    raw = ImageGrab.grab((l, t, r, b))
    img = raw.convert('L').resize((80, 60))
    data = list(img.get_flattened_data()) if hasattr(img, 'get_flattened_data') else img.getdata()
    ratio = round(sum(1 for v in data if v > 235) / len(data), 3)
    if name: raw.save(OUT / name)
    return ratio
    data = img.getdata()
    return round(sum(1 for v in data if v > 235) / len(data), 3)


results = []
original = story_dialog.center_dialog
state = {}


def probed(dialog, parent, *a, **k):
    if variant == 'alpha':
        dialog.attributes('-alpha', 0.0)
    original(dialog, parent, *a, **k)
    if variant == 'redraw':
        hwnd = user32.GetParent(dialog.winfo_id())
        # RDW_INVALIDATE|RDW_ERASE|RDW_ALLCHILDREN|RDW_UPDATENOW|RDW_ERASENOW
        user32.RedrawWindow(hwnd, None, None, 0x1 | 0x4 | 0x80 | 0x100 | 0x200)
        dialog.update_idletasks()
    if variant == 'winevents':
        import _tkinter
        for _ in range(200):
            if not dialog.tk.dooneevent(_tkinter.WINDOW_EVENTS | _tkinter.DONT_WAIT):
                break
        dialog.update_idletasks()
    rect = outer_rect(dialog)
    state['rect'] = rect
    state['t0'] = time.perf_counter()
    state['sync'] = white(rect, f'{variant}_{chapter}_sync.png')          # 이벤트 루프가 돌기 전
    if variant == 'alpha':
        def show():
            try:
                dialog.attributes('-alpha', 1.0)
            except tk.TclError:
                pass
        dialog.after_idle(lambda: dialog.after(0, show))


story_dialog.center_dialog = probed

for index in range(repeats):
    state.clear()
    samples = []
    stop = threading.Event()

    def watch():
        while not stop.is_set():
            if 'rect' in state:
                try:
                    samples.append((round(time.perf_counter() - state['t0'], 4), white(state['rect'])))
                except Exception:
                    pass
            time.sleep(.005)

    root = tk.Tk()
    root.geometry('1280x800+40+20')
    thread = threading.Thread(target=watch, daemon=True); thread.start()
    db = Database(':memory:')
    t_start = time.perf_counter()
    app = SimulatorApp(root, db, mode='story', start_chapter=chapter, seed=5)
    t_ctor = time.perf_counter()
    after_ctor = white(state['rect'], f'{variant}_{chapter}_{index}_ctor.png') if 'rect' in state else None   # 생성자 나머지 작업 뒤(아직 이벤트 루프 전)
    root.update()
    after_update = white(state['rect'], f'{variant}_{chapter}_{index}_update.png') if 'rect' in state else None
    time.sleep(.15)
    mid = white(state['rect'], f'{variant}_{chapter}_{index}_sleep.png')
    state['outer_after'] = outer_rect(app.story_window) if app.story_window is not None and app.story_window.winfo_exists() else None
    time.sleep(.15)
    stop.set(); thread.join()
    results.append({'run': index, 'variant': variant, 'chapter': str(chapter),
                    'sync_after_deiconify': state.get('sync'), 'after_constructor_before_loop': after_ctor,
                    'after_update': after_update, 'during_sleep': mid, 'rect_at_show': state.get('rect'), 'rect_after': state.get('outer_after'),
                    'ms_from_show_to_ctor_end': round((t_ctor - state.get('t0', t_ctor)) * 1000, 1),
                    'max_watch': max((w for _, w in samples), default=None),
                    'white_samples_ms': [round(t * 1000, 1) for t, w in samples if w > .2][:5],
                    'samples': len(samples), 'last_white_ms': max((round(t*1000,1) for t, w in samples if w > .2), default=0), 'first_dark_ms': min((round(t*1000,1) for t, w in samples if w < .05 and t > 0.02), default=None)})
    app.network.stop(); db.close(); root.destroy()

print(json.dumps(results, ensure_ascii=False, indent=1))
