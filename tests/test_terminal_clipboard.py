"""가상 터미널 복사/붙여넣기. 실제 Tk 창 없이 위젯과 같은 메서드를 가진 가짜 객체로 검증합니다."""
import tkinter as tk
import unittest

from aidc.ui.terminal_clipboard import (MAX_PASTE, bind_entry_paste, bind_output_copy, clean_paste, copy_selection,
                                        paste_clipboard)


class FakeText:
    def __init__(self, selected=None, state='disabled'):
        self.selected, self.state, self.clipboard = selected, state, 'unchanged'
        self.bindings, self.options, self.focused = {}, {}, 0

    def get(self, first, last):
        if self.selected is None:
            raise tk.TclError('text doesn\'t contain any characters tagged with "sel"')
        return self.selected

    def clipboard_clear(self):
        self.clipboard = ''

    def clipboard_append(self, text):
        self.clipboard += text

    def bind(self, sequence, func, add=None):
        self.bindings[sequence] = func

    def configure(self, **options):
        self.options.update(options)

    def focus_set(self):
        self.focused += 1


class FakeEntry(FakeText):
    def __init__(self, clip='', value='', state='normal', selected=None):
        super().__init__(selected, state)
        self.clip, self.value = clip, value

    def cget(self, name):
        return self.state

    def clipboard_get(self):
        if self.clip is None:
            raise tk.TclError('CLIPBOARD selection doesn\'t exist or form "STRING" not defined')
        return self.clip

    def delete(self, first, last):
        if self.selected is None:
            raise tk.TclError('selection isn\'t in widget')
        self.value = self.value.replace(self.selected, '', 1)
        self.selected = None

    def insert(self, index, text):
        self.value += text


class CleanPasteTests(unittest.TestCase):
    def test_newlines_and_control_characters_become_one_line(self):
        self.assertEqual(clean_paste('ping -c 3\nip addr\r\n'), 'ping -c 3 ip addr')
        self.assertEqual(clean_paste('\tip\x00route\x7f'), 'ip route')

    def test_empty_non_text_and_very_long_text(self):
        self.assertEqual(clean_paste(''), '')
        self.assertEqual(clean_paste(None), '')
        self.assertEqual(len(clean_paste('a'*(MAX_PASTE+50))), MAX_PASTE)

    def test_paste_never_inserts_an_enter_that_would_run_a_command(self):
        self.assertNotIn('\n', clean_paste('help\nip addr\nping 10.0.0.1'))


class CopyTests(unittest.TestCase):
    def test_copy_selection_puts_selected_text_on_clipboard(self):
        widget = FakeText('ip addr 출력')
        self.assertEqual(copy_selection(widget), len('ip addr 출력'))
        self.assertEqual(widget.clipboard, 'ip addr 출력')

    def test_no_selection_leaves_clipboard_untouched(self):
        widget = FakeText(None)
        self.assertEqual(copy_selection(widget), 0)
        self.assertEqual(widget.clipboard, 'unchanged')

    def test_mouse_release_copies_and_reports_count(self):
        widget, counts = FakeText('64 bytes from 10.0.0.1'), []
        bind_output_copy(widget, counts.append)
        widget.bindings['<Button-1>'](None)
        self.assertEqual(widget.focused, 1)  # 읽기 전용 출력도 클릭하면 포커스를 받아 기본 단축키가 동작합니다.
        widget.bindings['<ButtonRelease-1>'](None)
        self.assertEqual(widget.clipboard, '64 bytes from 10.0.0.1')
        self.assertEqual(counts, [len('64 bytes from 10.0.0.1')])

    def test_plain_click_without_drag_does_not_copy_or_report(self):
        widget, counts = FakeText(None), []
        bind_output_copy(widget, counts.append)
        widget.bindings['<ButtonRelease-1>'](None)
        self.assertEqual((widget.clipboard, counts), ('unchanged', []))

    def test_output_stays_read_only_and_bindings_do_not_replace_keyboard_shortcuts(self):
        widget = FakeText('x')
        bind_output_copy(widget)
        self.assertEqual(widget.state, 'disabled')
        self.assertEqual(set(widget.bindings), {'<Button-1>', '<ButtonRelease-1>'})  # Ctrl+C/A 등은 Tk 기본 그대로


class PasteTests(unittest.TestCase):
    def test_right_click_pastes_clipboard_into_entry_without_running(self):
        entry, counts = FakeEntry(clip='ping -c 3 10.0.0.1\n', value=''), []
        bind_entry_paste(entry, counts.append)
        self.assertEqual(entry.bindings['<Button-3>'](None), 'break')
        self.assertEqual(entry.value, 'ping -c 3 10.0.0.1')
        self.assertEqual(counts, [len('ping -c 3 10.0.0.1')])
        self.assertNotIn('<Return>', entry.bindings)  # 붙여넣기만으로 실행하지 않습니다.

    def test_selected_text_is_replaced(self):
        entry = FakeEntry(clip='ip route', value='ip addr', selected='addr')
        self.assertEqual(paste_clipboard(entry), 'ip route')
        self.assertEqual(entry.value, 'ip ip route')  # 'ip ' 뒤에 붙여넣기

    def test_disabled_entry_ignores_paste(self):
        entry = FakeEntry(clip='ip addr', state='disabled')
        self.assertIsNone(paste_clipboard(entry))
        self.assertEqual(entry.value, '')

    def test_empty_or_non_text_clipboard_is_ignored(self):
        self.assertIsNone(paste_clipboard(FakeEntry(clip=None)))
        self.assertIsNone(paste_clipboard(FakeEntry(clip=' \n ')))

    def test_right_click_still_breaks_default_menu_when_nothing_pasted(self):
        entry = FakeEntry(clip=None)
        bind_entry_paste(entry)
        self.assertEqual(entry.bindings['<Button-3>'](None), 'break')
        self.assertEqual(entry.value, '')


if __name__ == '__main__':
    unittest.main()
