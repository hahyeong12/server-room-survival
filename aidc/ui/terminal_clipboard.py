"""가상 터미널의 복사/붙여넣기. 화면 입력만 다루며 게임 상태·명령 해석기는 건드리지 않습니다.

- 출력(읽기 전용 Text): 마우스로 드래그해 선택을 끝내면 선택한 글이 클립보드로 복사됩니다.
  Ctrl+C/Ctrl+A 같은 Tk 기본 단축키는 그대로 유지합니다.
- 입력(Entry): 오른쪽 클릭하면 클립보드 내용을 붙여넣습니다. Ctrl+V 기본 동작도 유지합니다.
  붙여넣기는 입력창에 글만 넣을 뿐 자동 실행하지 않으며, 줄바꿈·제어 문자는 공백으로 바꿉니다.
"""
import re
import tkinter as tk

MAX_PASTE = 300  # 가상 터미널 한 줄에 필요한 길이를 넘는 붙여넣기는 잘라 냅니다.
_CONTROL = re.compile(r'[\x00-\x1f\x7f]+')


def clean_paste(text):
    """클립보드 글을 한 줄 입력으로 정리합니다. 줄바꿈이 있어도 여러 명령으로 나뉘어 실행되지 않습니다."""
    if not isinstance(text, str):
        return ''
    return _CONTROL.sub(' ', text).strip()[:MAX_PASTE]


def copy_selection(widget):
    """선택한 글을 클립보드에 복사하고 복사한 글자 수를 돌려줍니다. 선택이 없으면 0입니다."""
    try:
        text = widget.get('sel.first', 'sel.last')
    except tk.TclError:
        return 0
    if not text:
        return 0
    widget.clipboard_clear()
    widget.clipboard_append(text)
    return len(text)


def paste_clipboard(entry):
    """클립보드 글을 입력 커서 위치(선택 영역이 있으면 대체)에 넣고 넣은 글을 돌려줍니다. 넣을 수 없으면 None입니다."""
    if str(entry.cget('state')) == 'disabled':
        return None
    try:
        text = clean_paste(entry.clipboard_get())
    except tk.TclError:  # 클립보드가 비었거나 글이 아닙니다.
        return None
    if not text:
        return None
    try:
        entry.delete('sel.first', 'sel.last')
    except tk.TclError:
        pass
    entry.insert('insert', text)
    return text


def bind_output_copy(widget, on_copy=None):
    """읽기 전용 출력에서 드래그 선택이 끝나면 자동 복사합니다. on_copy(글자 수)는 상태 안내용입니다."""
    def released(_event):
        count = copy_selection(widget)
        if count and on_copy:
            on_copy(count)

    # 읽기 전용(disabled)이면 Tk가 클릭 때 포커스를 주지 않으므로 직접 주어 Ctrl+C 등 기본 단축키도 동작하게 합니다.
    widget.bind('<Button-1>', lambda _: widget.focus_set(), add='+')
    widget.bind('<ButtonRelease-1>', released, add='+')
    widget.configure(cursor='xterm', selectbackground='#2f5d8a', selectforeground='#ffffff',
                     inactiveselectbackground='#24476b')


def bind_entry_paste(entry, on_paste=None):
    """입력창을 오른쪽 클릭하면 클립보드 내용을 붙여넣습니다. on_paste(글자 수)는 상태 안내용입니다."""
    def pressed(_event):
        entry.focus_set()
        text = paste_clipboard(entry)
        if text is not None and on_paste:
            on_paste(len(text))
        return 'break'

    entry.bind('<Button-3>', pressed)
