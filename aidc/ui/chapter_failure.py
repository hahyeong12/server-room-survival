"""장 실패 안내: 큰 판정 → 직접 원인/왜/다음에는 카드 → 행동 버튼(재도전이 주요 행동)."""
import tkinter as tk
from ui import BG, TEXT, MUTED, RED, label
from aidc.ui.window_placement import center_dialog
from aidc.ui.result_widgets import button_bar, failure_card
from aidc.ui.result_presentation import result_actions
from aidc.ui.scroll_area import ScrollArea


class ChapterFailureDialog(tk.Toplevel):
    def __init__(self, parent, title, reason, retry, select_mode, review=None, select_chapter=None, retry_label='체크포인트부터 다시 도전'):
        super().__init__(parent, bg=BG)
        self.withdraw()
        self.title(title+' · 실패')
        self.transient(parent)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        if isinstance(reason, str):
            reason = {'headline': reason, 'cause': reason, 'why': '요청이 정상 완료되지 않았습니다.', 'next': '고객 조건과 운영 상태를 확인하고 다시 도전하세요.'}
        top = tk.Frame(self, bg=BG)
        top.grid(row=0, sticky='ew', padx=28, pady=(18, 6))
        top.columnconfigure(0, weight=1)
        label(top, title, 10, MUTED, True).grid(row=0, sticky='w')
        self.verdict = label(top, 'MISSION FAILED', 28, RED, True)
        self.verdict.grid(row=1, sticky='w')
        self.failure_title = label(top, reason['headline'], 15, TEXT, True, wraplength=700, justify='left', anchor='w')
        self.failure_title.grid(row=2, sticky='ew', pady=(2, 0))
        top.bind('<Configure>', lambda e: self.failure_title.configure(wraplength=max(280, e.width-10)))
        self.scroll = ScrollArea(self)
        self.scroll.grid(row=1, sticky='nsew')
        self.cards = failure_card(self.scroll.body, reason)
        self.cards.grid(row=0, sticky='ew', padx=28, pady=(10, 4))
        label(self.scroll.body, '현재 기록은 보존되고, 재도전은 새 슬롯에서 시작합니다.', 10, MUTED).grid(
            row=1, sticky='w', padx=28, pady=(6, 10))
        entries = []
        for key, text, action in result_actions(retry, select_chapter, select_mode, retry_label):
            entries.append((key, text, action, key == 'retry' or (key == 'modes' and retry is None)))
        self.action_bar = button_bar(self, entries)
        self.action_bar.grid(row=2, sticky='ew', pady=(6, 16))
        self.buttons = dict(self.action_bar.buttons)
        center_dialog(self, parent, size=(780, 600), minimum=(640, 420))
