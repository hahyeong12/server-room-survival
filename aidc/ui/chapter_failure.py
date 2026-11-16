"""제1장도 실제 요청 종료 뒤에만 실패를 표시합니다."""
import tkinter as tk
from ui import BG, TEXT, MUTED, RED, ActionButton, label
from aidc.ui.window_placement import center_dialog


class ChapterFailureDialog(tk.Toplevel):
    def __init__(self, parent, title, reason, retry, select_mode, review):
        super().__init__(parent, bg=BG)
        self.withdraw()
        self.title(title+' · 실패')
        self.transient(parent)
        label(self, title, 16, TEXT, True).pack(anchor='w', padx=24, pady=(22, 12))
        label(self, 'MISSION FAILED', 24, RED, True).pack(anchor='w', padx=24)
        label(self, reason, 12, TEXT, wraplength=500, justify='left').pack(anchor='w', padx=24, pady=14)
        label(self, '현재 기록을 보존합니다. 재도전은 새 슬롯에서 시작합니다.', 10, MUTED).pack(anchor='w', padx=24)
        self.buttons = {}
        for key, text, action in (('retry', '다시 도전', retry), ('review', '교육 복습', review), ('modes', '모드 선택', select_mode)):
            button = self.buttons[key] = ActionButton(self, text, action)
            button.pack(fill='x', padx=24, pady=5)
        center_dialog(self, parent, size=(560, 350), minimum=(500, 330))
