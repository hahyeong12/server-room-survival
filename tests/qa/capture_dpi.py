"""dpi-review-001: DPI 비인식과 실험용 System DPI Aware 화면을 같은 조건으로 캡처·측정합니다.

python tests/qa/capture_dpi.py <출력 폴더>

- 모드마다 별도 자식 프로세스를 띄웁니다(DPI 인식은 프로세스당 한 번만 정할 수 있음).
- 메모리 DB와 같은 seed로 같은 화면을 엽니다: 교육창 → 관제실 → 배정창 → 장비 진단창 → 결과 카드(제4장 연습),
  Engineering Lab(연습). 사용자 저장은 열지 않고, 실행 전후 목록·SHA-256이 같지 않으면 실패로 기록합니다.
- 캡처는 Per-Monitor 스레드 문맥의 GDI BitBlt로 화면의 실제(물리) 픽셀을 읽습니다. 두 모드를 같은 방식으로 비교합니다.
- 선명도는 두 가지로 잽니다.
  1) 1px 검은 세로선 시험 Canvas의 중간 회색 비율(0이면 확대 보간 없음).
  2) 화면 캡처의 경계 선명도: 3px 안에서 크게 바뀌는 밝기 변화 중 한 칸에서 일어난 몫의 평균(1에 가까울수록 선명).
- 겹침·잘림·클릭 영역 판정은 이 도구가 아니라 기존 GUI 테스트(tests.run_gui --dpi system)의 경계 검사가 맡습니다.
"""
import ctypes
from ctypes import wintypes as wt
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

MODES = ('unaware', 'system')


def physical_capture(window):
    """window(최상위 창)의 클라이언트 영역을 물리 픽셀로 캡처합니다. (PIL Image, (x, y, w, h)) 반환."""
    from PIL import Image
    user32, gdi = ctypes.windll.user32, ctypes.windll.gdi32
    user32.GetAncestor.argtypes = [wt.HWND, wt.UINT]; user32.GetAncestor.restype = wt.HWND
    user32.SetThreadDpiAwarenessContext.argtypes = [ctypes.c_void_p]
    user32.SetThreadDpiAwarenessContext.restype = ctypes.c_void_p
    gdi.CreateCompatibleDC.argtypes = [ctypes.c_void_p]; gdi.CreateCompatibleDC.restype = ctypes.c_void_p
    gdi.CreateCompatibleBitmap.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
    gdi.CreateCompatibleBitmap.restype = ctypes.c_void_p
    gdi.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    gdi.BitBlt.argtypes = [ctypes.c_void_p]+[ctypes.c_int]*4+[ctypes.c_void_p]+[ctypes.c_int]*2+[wt.DWORD]
    gdi.GetDIBits.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wt.UINT, wt.UINT, ctypes.c_void_p, ctypes.c_void_p, wt.UINT]
    gdi.DeleteObject.argtypes = [ctypes.c_void_p]; gdi.DeleteDC.argtypes = [ctypes.c_void_p]
    user32.GetDC.argtypes = [wt.HWND]; user32.GetDC.restype = ctypes.c_void_p
    user32.ReleaseDC.argtypes = [wt.HWND, ctypes.c_void_p]
    old = user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))
    try:
        hwnd = user32.GetAncestor(window.winfo_id(), 2)
        rect = wt.RECT(); user32.GetClientRect(hwnd, ctypes.byref(rect))
        point = wt.POINT(0, 0); user32.ClientToScreen(hwnd, ctypes.byref(point))
        w, h = rect.right, rect.bottom
        screen = user32.GetDC(None); memory = gdi.CreateCompatibleDC(screen)
        bitmap = gdi.CreateCompatibleBitmap(screen, w, h); gdi.SelectObject(memory, bitmap)
        gdi.BitBlt(memory, 0, 0, w, h, screen, point.x, point.y, 0x00CC0020)
        info = ctypes.create_string_buffer(40)
        ctypes.memmove(info, (ctypes.c_uint32*11)(40, w, (-h) & 0xffffffff, 1 | (32 << 16), 0, 0, 0, 0, 0, 0, 0), 40)
        pixels = ctypes.create_string_buffer(w*h*4)
        gdi.GetDIBits(memory, bitmap, 0, h, pixels, info, 0)
        gdi.DeleteObject(bitmap); gdi.DeleteDC(memory); user32.ReleaseDC(None, screen)
        image = Image.frombuffer('RGBA', (w, h), pixels, 'raw', 'BGRA', 0, 1).convert('RGB')
        return image, (point.x, point.y, w, h)
    finally:
        user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(old))


def edge_sharpness(image):
    """3px 안에서 밝기가 크게(>=90) 바뀌는 곳마다 '가장 큰 한 칸 변화 / 3px 전체 변화'의 평균(가로·세로)."""
    import numpy as np
    g = np.asarray(image.convert('L'), dtype=np.int16)
    ratios = []
    for a in (g, g.T):
        d1 = np.abs(np.diff(a, axis=1))                     # 한 칸 변화
        total = np.abs(a[:, 3:]-a[:, :-3])                  # 3칸 전체 변화
        step = np.maximum(np.maximum(d1[:, :-2], d1[:, 1:-1]), d1[:, 2:])
        mask = total >= 90
        if mask.any():
            ratios.append(np.clip(step[mask]/total[mask], 0, 1))
    values = np.concatenate(ratios) if ratios else np.array([0.0])
    return round(float(values.mean()), 4), int(values.size)


def line_test(tk):
    """1px 검은 세로선(2px 간격)을 그린 시험 창의 물리 캡처에서 중간 회색 비율."""
    from aidc.ui import dpi
    root = tk.Tk(); root.geometry('+120+120'); root.attributes('-topmost', True)
    canvas = tk.Canvas(root, width=dpi.px(200), height=dpi.px(60), bg='white', highlightthickness=0)
    canvas.pack()
    for i in range(40):
        canvas.create_line(10+i*2, 10, 10+i*2, 50, fill='black')
    dpi.finish_canvas(canvas)
    settle(root)
    image, box = physical_capture(root)
    gray = image.convert('L'); s = dpi.scale()
    k = box[2]/root.winfo_width()  # 비인식이면 Windows 확대 배율(1.25), 인식이면 1.0
    region = [gray.getpixel((x, y)) for y in range(int(20*s*k), int(45*s*k)) for x in range(int(12*s*k), int(86*s*k))]
    root.destroy()
    return round(sum(40 < v < 215 for v in region)/len(region), 4)


def settle(widget, rounds=12):
    top = widget.winfo_toplevel()
    top.lift()
    try:
        top.attributes('-topmost', True)
    except Exception:
        pass
    for _ in range(rounds):
        top.update(); time.sleep(0.05)
    try:
        top.attributes('-topmost', False)
    except Exception:
        pass
    top.update()


def child(mode, out):
    from aidc.ui import dpi
    if mode == 'system' and not dpi.enable_system_awareness():
        raise SystemExit('System DPI Aware 설정 실패: '+dpi.status()['reason'])
    import tkinter as tk
    from unittest.mock import patch
    from database import Database
    from main import SimulatorApp
    from tests.support import dismiss_story_popups
    from aidc.ui.window_placement import work_area
    s = dpi.scale()
    rows, report = [], {'mode': mode, 'dpi': dpi.status(), 'line_gray_ratio': line_test(tk)}

    def record(name, window, design=None):
        settle(window)
        image, box = physical_capture(window)
        path = out/f'{mode}_{name}.png'
        image.save(path, optimize=True)
        area = work_area(window.winfo_toplevel())
        root_box = (window.winfo_rootx(), window.winfo_rooty(), window.winfo_width(), window.winfo_height())
        sharp, edges = edge_sharpness(image)
        rows.append({'screen': name, 'tk_client': [root_box[2], root_box[3]], 'physical_client': [box[2], box[3]],
                     'design_px': [round(root_box[2]/s), round(root_box[3]/s)], 'edge_sharpness': sharp, 'edges': edges,
                     'inside_work_area': (area[0] <= root_box[0] and area[1] <= root_box[1]
                                          and root_box[0]+root_box[2] <= area[2] and root_box[1]+root_box[3] <= area[3]),
                     'placement': getattr(window, 'placement', None), 'file': path.name})

    with patch('tkinter.messagebox._show', side_effect=AssertionError('예상 밖의 모달 대화상자')):
        root = tk.Tk(); db = Database(':memory:')
        app = SimulatorApp(root, db, mode='story', start_chapter='3b', seed=5)
        report['tk_scaling'] = float(root.tk.call('tk', 'scaling'))
        for _ in range(40):                       # 교육창은 관제실이 그려진 뒤 표시됩니다(after_idle → after(0)).
            root.update(); time.sleep(0.02)
            if app.story_window is not None and app.story_window.winfo_viewable():
                break
        record('education', app.story_window)
        a = app.session.story.chapter3b.request_ids[0]
        app.story_window.skip_button.invoke(); app.story_window.next_button.invoke(); root.update()
        dismiss_story_popups(app, root)
        app.open_message(a); app.message_window.destroy(); root.update()
        record('control_room', root)
        app.action_buttons['start'].invoke(); root.update()
        dialog = app.allocation_window
        record('allocation', dialog)
        dialog.auto_button.invoke(); dialog.start_button.invoke(); root.update()
        dismiss_story_popups(app, root)
        app.advance_time(60); root.update(); dismiss_story_popups(app, root)
        app.action_buttons['hwdiag'].invoke(); root.update()
        record('hardware_diagnosis', app.diagnosis_window)
        app.diagnosis_window.close_button.invoke(); root.update()
        app.action_buttons['hwrepair'].invoke(); root.update()
        record('result_card', app.feedback_window)
        app.network.stop(); root.destroy(); db.close()

        root = tk.Tk(); db = Database(':memory:')
        app = SimulatorApp(root, db, mode='story', start_chapter='lab', seed=5)
        root.update(); dismiss_story_popups(app, root)
        lab = app.open_engineering_lab(); root.update()
        record('engineering_lab', lab)
        app.network.stop(); root.destroy(); db.close()
    report['screens'] = rows
    (out/f'{mode}.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


def compare(out):
    from PIL import Image, ImageDraw
    data = {m: json.loads((out/f'{m}.json').read_text(encoding='utf-8')) for m in MODES}
    summary = {'line_gray_ratio': {m: data[m]['line_gray_ratio'] for m in MODES}, 'screens': []}
    for a, b in zip(data['unaware']['screens'], data['system']['screens']):
        ua, sa = Image.open(out/a['file']), Image.open(out/b['file'])
        summary['screens'].append({
            'screen': a['screen'],
            'physical_unaware': a['physical_client'], 'physical_system': b['physical_client'],
            'size_ratio': [round(b['physical_client'][i]/a['physical_client'][i], 3) for i in (0, 1)],
            'edge_sharpness': [a['edge_sharpness'], b['edge_sharpness']],
            'inside_work_area': [a['inside_work_area'], b['inside_work_area']],
            'center_offset': [(a['placement'] or {}).get('offset'), (b['placement'] or {}).get('offset')]})
        # 같은 물리 크기 비율로 나란히 놓은 비교 이미지(위: 비인식, 아래: 실험 인식).
        width = max(ua.width, sa.width)
        sheet = Image.new('RGB', (width, ua.height+sa.height+28), (40, 40, 40))
        sheet.paste(ua, (0, 0)); sheet.paste(sa, (0, ua.height+28))
        ImageDraw.Draw(sheet).text((8, ua.height+8), 'above: DPI unaware (Windows bitmap scaling)  /  below: System DPI Aware (experimental)',
                                   fill=(230, 230, 230))
        sheet.save(out/f'compare_{a["screen"]}.png', optimize=True)
    (out/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    return summary


def main():
    if len(sys.argv) == 4 and sys.argv[1] == '--child':
        child(sys.argv[2], Path(sys.argv[3]))
        return
    out = Path(sys.argv[1]).resolve(); out.mkdir(parents=True, exist_ok=True)
    from tests.run_gui import saved_files
    before = saved_files()
    for mode in MODES:
        subprocess.run([sys.executable, str(Path(__file__).resolve()), '--child', mode, str(out)], check=True, cwd=ROOT)
    summary = compare(out)
    summary['user_data_unchanged'] = before == saved_files()
    (out/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    if not summary['user_data_unchanged']:
        raise SystemExit('사용자 저장이 바뀌었습니다.')


if __name__ == '__main__':
    main()
