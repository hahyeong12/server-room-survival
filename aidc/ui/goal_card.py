"""관제실 위쪽의 '현재 목표' 카드. 긴 문장 대신 단계 배지·짧은 제목·지금 할 행동 하나·단계 표시로 알려 줍니다.

표시 전용입니다(게임 상태·저장 변경 없음). 색 역할: 금색=지금 할 일(ACTION), 청록=이야기/안내(STORY), 초록=결과 피드백.
"""
import tkinter as tk

from ui import BG, PANEL, TEXT, MUTED, CYAN, GREEN, FONT, label

GOLD = '#ffe08a'
PHASE_COLORS = {'ACTION': GOLD, 'STORY': CYAN, 'FEEDBACK': GREEN}
PIP_STYLE = {'done': ('✔ ', CYAN, False), 'current': ('▶ ', GOLD, True), 'todo': ('○ ', MUTED, False)}


def pip_text(name, state):
    """단계 표시 한 칸의 문구와 색(순수 함수). 색만이 아니라 기호(✔ ▶ ○)로도 상태를 구분합니다."""
    icon, color, bold = PIP_STYLE[state]
    return icon+name, color, bold


class GoalCard(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=PANEL, highlightthickness=2, highlightbackground=GOLD, padx=12, pady=7)
        self.columnconfigure(1, weight=1)
        self.badge = tk.Label(self, text='ACTION', bg=GOLD, fg=BG, font=(FONT, 10, 'bold'), padx=10, pady=4)
        self.badge.grid(row=0, column=0, rowspan=2, sticky='n', padx=(0, 12), pady=2)
        self.kicker = label(self, '', 9, MUTED, anchor='w')
        self.kicker.grid(row=0, column=1, sticky='ew')
        self.title = label(self, '', 13, TEXT, True, anchor='w', justify='left')
        self.title.grid(row=1, column=1, sticky='ew')
        self.action = label(self, '', 11, GOLD, True, anchor='w', justify='left')
        self.action.grid(row=2, column=1, sticky='ew', pady=(1, 0))
        self.pip_row = tk.Frame(self, bg=PANEL)
        self.pip_row.grid(row=3, column=1, sticky='w', pady=(5, 0))
        self.mentor = label(self, '', 10, MUTED, anchor='w', justify='left')
        self.mentor.grid(row=4, column=1, sticky='ew', pady=(3, 0))
        self._pips = None
        self.bind('<Configure>', self._wrap)

    def _wrap(self, event):
        width = max(260, event.width-110)
        for widget in (self.title, self.action, self.mentor):
            widget.configure(wraplength=width)

    def set(self, badge, title, action='', kicker='', pips=None, mentor='', phase='ACTION'):
        color = PHASE_COLORS.get(phase, GOLD)
        self.configure(highlightbackground=color)
        self.badge.configure(text=badge, bg=color)
        self.kicker.configure(text=kicker)
        self.title.configure(text=title)
        self.action.configure(text=('▶ '+action) if action else '', fg=color)
        self.mentor.configure(text=('선배 · '+mentor) if mentor else '')
        key = tuple(pips or ())
        if key != self._pips:
            self._pips = key
            for widget in self.pip_row.winfo_children():
                widget.destroy()
            for name, state in key:
                text, fg, bold = pip_text(name, state)
                tk.Label(self.pip_row, text=text, bg=PANEL, fg=fg, font=(FONT, 9, 'bold' if bold else 'normal'),
                         anchor='w').pack(side='left', padx=(0, 16))
