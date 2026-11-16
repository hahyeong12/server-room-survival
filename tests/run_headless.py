"""GUI 가능성이 있는 클래스를 제외하고 Tk 생성도 차단하는 비GUI 회귀 러너.

실행: python -m tests.run_headless
제외 수는 실행한 테스트 수에 포함하지 않습니다. 화면 검사는 별도 수동 확인 대상입니다.
"""
import inspect
import re
import unittest
from unittest.mock import patch
import tkinter as tk


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


def needs_window(case):
    cls = type(case)
    if re.search(r'gui|tk|window', cls.__name__, re.I) or cls.__module__.endswith('_gui'):
        return True
    for base in cls.__mro__:
        if base in (unittest.TestCase, object):
            continue
        source = inspect.getsource(base)
        if re.search(r'\bTk\s*\(|self\.root\b|self\.app\b|make_root\s*\(', source):
            return True
    return False


def main():
    discovered = list(flatten(unittest.defaultTestLoader.discover('tests')))
    selected = [test for test in discovered if not needs_window(test)]
    print(f'비GUI 선택: {len(selected)} / GUI 등 제외: {len(discovered)-len(selected)}', flush=True)
    with patch.object(tk.Tk, '__init__', side_effect=AssertionError('비GUI 검사에서 Tk 생성 금지')), \
         patch.object(tk.Toplevel, '__init__', side_effect=AssertionError('비GUI 검사에서 Toplevel 생성 금지')):
        result = unittest.TextTestRunner(verbosity=1).run(unittest.TestSuite(selected))
    raise SystemExit(not result.wasSuccessful())


if __name__ == '__main__':
    main()
