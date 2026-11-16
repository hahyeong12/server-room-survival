"""실제 Tk: 스토리 소개 전문 줄바꿈·모드 카드 정렬·버튼 가시성."""
import tempfile
import tkinter as tk
import unittest

from aidc.storage.story_slots import StorySlots
from aidc.story.chapters import CHAPTERS
from main import ModeSelection


class ModeIntroGuiTests(unittest.TestCase):
    def test_story_intro_fits_after_resize_and_keeps_all_text_and_buttons(self):
        with tempfile.TemporaryDirectory() as folder:
            root = tk.Tk()
            self.addCleanup(root.destroy)
            menu = ModeSelection(root, story_slots=StorySlots(folder))
            text = CHAPTERS[1].heading+'\n'+CHAPTERS[1].intro
            intro = next(w for w in menu.story_panel.winfo_children()
                         if 'text' in w.keys() and w.cget('text') == text)
            for width, height in ((1280, 760), (1000, 650), (1366, 768)):
                root.geometry(f'{width}x{height}')
                menu.show_modes()
                root.update()
                buttons = list(menu.buttons.values())
                self.assertEqual(len({b.winfo_rooty() for b in buttons}), 1)
                self.assertEqual(len({b.winfo_height() for b in buttons}), 1)
                menu.show_story_menu()
                root.update()
                self.assertEqual(intro.cget('text'), text)
                self.assertLessEqual(intro.winfo_reqwidth(), intro.winfo_width()+2)
                self.assertLessEqual(intro.winfo_reqheight(), intro.winfo_height()+2)
                self.assertLessEqual(intro.winfo_x()+intro.winfo_width(), menu.story_panel.winfo_width())
                for button in menu.story_buttons.values():
                    self.assertLessEqual(button.winfo_rooty()+button.winfo_height(),
                                         root.winfo_rooty()+root.winfo_height())


if __name__ == '__main__':
    unittest.main()
