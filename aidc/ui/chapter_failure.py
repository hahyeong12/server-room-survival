"""제1장도 실제 요청 종료 뒤에만 실패를 표시합니다."""
import tkinter as tk
from ui import BG, TEXT, MUTED, RED, ActionButton, label
from aidc.ui.window_placement import center_dialog
from aidc.ui.result_widgets import failure_card
from aidc.ui.result_presentation import result_actions
from aidc.ui.scroll_area import ScrollArea


class ChapterFailureDialog(tk.Toplevel):
    def __init__(self, parent, title, reason, retry, select_mode, review=None, select_chapter=None, retry_label='체크포인트부터 다시 도전'):
        super().__init__(parent, bg=BG)
        self.withdraw()
        self.title(title+' · 실패')
        self.transient(parent)
        label(self, title, 12, MUTED, True).pack(anchor='w', padx=24, pady=(18, 8))
        label(self, 'MISSION FAILED', 24, RED, True).pack(anchor='w', padx=24)
        if isinstance(reason, str):
            reason = {'headline': reason, 'cause': reason, 'why': '요청이 정상 완료되지 않았습니다.', 'next': '고객 조건과 운영 상태를 확인하고 다시 도전하세요.'}
        self.failure_title = label(self, reason['headline'], 16, RED, True, wraplength=640, justify='left')
        self.failure_title.pack(anchor='w', padx=24, pady=(10, 12))
        footer = tk.Frame(self, bg=BG)
        footer.pack(side='bottom', fill='x', padx=24, pady=12)
        self.scroll = ScrollArea(self)
        self.scroll.pack(fill='both', expand=True)
        failure_card(self.scroll.body, reason).pack(fill='x', padx=24, pady=6)
        label(self.scroll.body, '현재 기록을 보존하고 새 슬롯에서 재도전합니다.', 10, MUTED).pack(anchor='w', padx=24, pady=8)
        self.buttons = {}
        for index, (key, text, action) in enumerate(result_actions(retry, select_chapter, select_mode, retry_label)):
            button = self.buttons[key] = ActionButton(footer, text, action)
            button.grid(row=0, column=index, sticky='ew', padx=4)
            footer.columnconfigure(index, weight=1)
        center_dialog(self, parent, size=(760, 560), minimum=(640, 420))
