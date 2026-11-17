"""실제 Git 작업 트리에서 GUI 포함 회귀 실행. 사용자 저장은 열지 않습니다.

python -m tests.run_gui --output artifacts/gui-results.json [tests.test_module[.Class.test]]
이름을 생략하면 비GUI를 포함한 전체 스위트를 한 번 실행합니다.
"""
import argparse
from contextlib import ExitStack
import ctypes
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time
import tkinter as tk
import unittest
from unittest.mock import patch

from database import Database
from aidc.storage.story_slots import StorySlots

ROOT = Path(__file__).resolve().parents[1]


def saved_files():
    return {p.name: {'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
            for p in sorted(ROOT.iterdir()) if p.is_file()
            and ('.db' in p.name or p.suffix in ('.lock', '.json'))}


def check_test_path(path):
    if str(path) != ':memory:' and Path(path).resolve().parent == ROOT:
        raise AssertionError('사용자 저장 디렉터리는 회귀 테스트에서 쓸 수 없습니다.')


def preflight():
    """Tk 표시·전경·화면 배율을 확인합니다. DPI 설정이나 게임 상태를 바꾸지 않습니다."""
    root = tk.Tk()
    try:
        root.title('서버실 생존기 · GUI 회귀 Preflight')
        root.geometry('480x160+100+100')
        tk.Label(root, text='임시 DB를 사용하는 GUI 회귀 검증').pack(pady=45)
        root.lift()
        root.update()
        if sys.platform == 'win32':
            from ctypes import wintypes as wt
            user32 = ctypes.windll.user32
            user32.GetAncestor.argtypes = [wt.HWND, wt.UINT]
            user32.GetAncestor.restype = wt.HWND
            user32.GetForegroundWindow.restype = wt.HWND
            user32.SetForegroundWindow.argtypes = [wt.HWND]
            user32.WindowFromPoint.argtypes = [wt.POINT]
            user32.WindowFromPoint.restype = wt.HWND
            hwnd = user32.GetAncestor(root.winfo_id(), 2)
            user32.SetForegroundWindow(hwnd)
            deadline = time.monotonic() + 5
            while user32.GetForegroundWindow() != hwnd and time.monotonic() < deadline:
                root.update()
                time.sleep(.05)
            if user32.GetForegroundWindow() != hwnd or not root.winfo_viewable():
                raise RuntimeError('Preflight: GUI 표시/전경 확보 실패')
            point = wt.POINT(root.winfo_rootx()+240, root.winfo_rooty()+80)
            if user32.GetAncestor(user32.WindowFromPoint(point), 2) != hwnd:
                raise RuntimeError('Preflight: 검증 창이 다른 창에 가려져 있습니다.')
        return {'python': platform.python_version(), 'tk': root.tk.call('info', 'patchlevel'),
                'tk_scaling': float(root.tk.call('tk', 'scaling')),
                'screen': [root.winfo_screenwidth(), root.winfo_screenheight()], 'visible': True}
    finally:
        root.destroy()


class RecordedResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.passed = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.passed.append(test.id())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('names', nargs='*')
    args = parser.parse_args()
    before = saved_files()
    report = {'kind': 'GUI regression (real Tk, unittest fixtures; not native autoplay)',
              'selection': args.names or ['discover tests'], 'user_data_before': before}
    start = time.monotonic()
    try:
        subprocess.run(['git', 'rev-parse', '--show-toplevel'], cwd=ROOT, check=True, capture_output=True)
        report['environment'] = preflight()
        original = Database.__init__
        reserve = StorySlots.reserve_new

        def temporary_only(db, path=ROOT/'aidc_game.db'):
            check_test_path(path)
            original(db, path)

        def temporary_slot(slots):
            check_test_path(slots.directory/'aidc_story_slot_001.db')
            return reserve(slots)

        def unexpected_message(*args, **kwargs):
            raise AssertionError(f'예상 밖의 모달 대화상자: {args!r} {kwargs!r}')

        with ExitStack() as stack:
            stack.enter_context(patch.object(Database, '__init__', temporary_only))
            stack.enter_context(patch.object(StorySlots, 'reserve_new', temporary_slot))
            stack.enter_context(patch('tkinter.messagebox._show', side_effect=unexpected_message))
            suite = (unittest.defaultTestLoader.loadTestsFromNames(args.names) if args.names else
                     unittest.defaultTestLoader.discover(str(ROOT/'tests'), top_level_dir=str(ROOT)))
            result = unittest.TextTestRunner(verbosity=2, resultclass=RecordedResult).run(suite)
        report.update(ran=result.testsRun, passed=result.passed,
                      failures=[{'id': t.id(), 'traceback': detail} for t, detail in result.failures],
                      errors=[{'id': t.id(), 'traceback': detail} for t, detail in result.errors],
                      skipped=[{'id': t.id(), 'reason': detail} for t, detail in result.skipped])
    except Exception as exc:
        report['environment_error'] = repr(exc)
        raise
    finally:
        report['seconds'] = round(time.monotonic()-start, 3)
        report['user_data_after'] = saved_files()
        report['user_data_unchanged'] = before == report['user_data_after']
        args.output.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(report, ensure_ascii=False, indent=2)
        for path, label in ((ROOT, '<repo>'), (Path(tempfile.gettempdir()), '<temp>'),
                            (Path(sys.base_prefix), '<python>'), (Path.home(), '<user>')):
            payload = payload.replace(json.dumps(str(path), ensure_ascii=False)[1:-1], label)
        args.output.write_text(payload+'\n', encoding='utf-8')
    raise SystemExit(not result.wasSuccessful() or bool(result.skipped) or not report['user_data_unchanged'])


if __name__ == '__main__':
    main()
