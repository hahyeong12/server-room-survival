"""관제실 위쪽의 '현재 목표' 카드. 긴 문장 대신 단계 배지·짧은 제목·지금 할 행동 하나·단계 표시로 알려 줍니다.

표시 전용입니다(게임 상태·저장 변경 없음).
색 규칙: 카드는 중립 테두리를 유지하고 금색을 쓰지 않습니다. 금색의 가장 강한 강조는 실제로 누를 버튼(교육 강조)에만 씁니다.
배지는 단계 성격을 작게 표시합니다(ACTION=청록, STORY=파랑, FEEDBACK=초록). 완료 단계는 회색 ✔, 현재 단계는 청록 ●입니다.
"""
import tkinter as tk

from ui import PANEL, RAISED, BORDER, TEXT, MUTED, CYAN, BLUE, GREEN, FONT, label

PHASE_COLORS = {'ACTION': CYAN, 'STORY': BLUE, 'FEEDBACK': GREEN}
PIP_STYLE = {'done': ('✔ ', MUTED, False), 'current': ('● ', CYAN, True), 'todo': ('○ ', MUTED, False)}


def pip_text(name, state):
    """단계 표시 한 칸의 문구와 색(순수 함수). 색만이 아니라 기호(✔ ● ○)로도 상태를 구분합니다."""
    icon, color, bold = PIP_STYLE[state]
    return icon+name, color, bold


def card_colors(phase):
    """카드 각 부분의 색(순수 함수). 카드 자체에는 금색을 쓰지 않습니다."""
    accent = PHASE_COLORS.get(phase, CYAN)
    return {'border': BORDER, 'badge_fg': accent, 'badge_bg': RAISED, 'action': TEXT, 'mentor': MUTED}


class GoalCard(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=PANEL, highlightthickness=1, highlightbackground=BORDER, padx=12, pady=7)
        self.columnconfigure(1, weight=1)
        self.badge = tk.Label(self, text='ACTION', bg=RAISED, fg=CYAN, font=(FONT, 9, 'bold'), padx=8, pady=3)
        self.badge.grid(row=0, column=0, rowspan=2, sticky='n', padx=(0, 12), pady=2)
        self.kicker = label(self, '', 9, MUTED, anchor='w')
        self.kicker.grid(row=0, column=1, sticky='ew')
        self.title = label(self, '', 13, TEXT, True, anchor='w', justify='left')
        self.title.grid(row=1, column=1, sticky='ew')
        self.action = label(self, '', 11, TEXT, anchor='w', justify='left')
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
        colors = card_colors(phase)
        self.configure(highlightbackground=colors['border'])
        self.badge.configure(text=badge, bg=colors['badge_bg'], fg=colors['badge_fg'])
        self.kicker.configure(text=kicker)
        self.title.configure(text=title)
        self.action.configure(text=('▶ '+action) if action else '', fg=colors['action'])
        self.mentor.configure(text=('선배 · '+mentor) if mentor else '', fg=colors['mentor'])
        key = tuple(pips or ())
        if key != self._pips:
            self._pips = key
            for widget in self.pip_row.winfo_children():
                widget.destroy()
            for name, state in key:
                text, fg, bold = pip_text(name, state)
                tk.Label(self.pip_row, text=text, bg=PANEL, fg=fg, font=(FONT, 9, 'bold' if bold else 'normal'),
                         anchor='w').pack(side='left', padx=(0, 16))
