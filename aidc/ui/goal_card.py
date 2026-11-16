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
    """3줄 카드: ① 제목 + 장 이름 ② 지금 할 행동 ③ 단계 표시 + 선배 한마디. 오른쪽 `side`에는 교육 보조 버튼을 둡니다.

    QA tutorial-001 Q-01: 5줄 카드(145px)와 별도 교육 버튼 줄(48px) 때문에 관제실 본문이 82px로 눌려
    [요청 확인] 버튼이 보이지 않았습니다. 같은 정보를 3줄로 모으고 버튼 줄을 카드 오른쪽으로 옮겼습니다."""
    def __init__(self, parent):
        super().__init__(parent, bg=PANEL, highlightthickness=1, highlightbackground=BORDER, padx=12, pady=5)
        self.columnconfigure(1, weight=1)
        self.badge = tk.Label(self, text='ACTION', bg=RAISED, fg=CYAN, font=(FONT, 9, 'bold'), padx=8, pady=3)
        self.badge.grid(row=0, column=0, rowspan=2, sticky='n', padx=(0, 12), pady=2)
        head = tk.Frame(self, bg=PANEL)
        head.grid(row=0, column=1, sticky='ew')
        self.title = label(head, '', 13, TEXT, True, anchor='w', justify='left')
        self.title.pack(side='left')
        self.kicker = label(head, '', 9, MUTED, anchor='w')
        self.kicker.pack(side='left', padx=(12, 0))
        self.action = label(self, '', 11, TEXT, anchor='w', justify='left')
        self.action.grid(row=1, column=1, sticky='ew')
        foot = tk.Frame(self, bg=PANEL)
        foot.grid(row=2, column=1, sticky='ew', pady=(3, 0))
        self.pip_row = tk.Frame(foot, bg=PANEL)
        self.pip_row.pack(side='left')
        self.mentor = label(foot, '', 10, MUTED, anchor='w', justify='left')
        self.mentor.pack(side='left', fill='x', expand=True, padx=(8, 0))
        self.side = tk.Frame(self, bg=PANEL)  # 교육 도움말·건너뛰기·재도전 등(관제실이 채움)
        self.side.grid(row=0, column=2, rowspan=3, sticky='e', padx=(12, 0))
        self._pips = None
        self.bind('<Configure>', self._wrap)

    def _wrap(self, event):
        width = max(260, event.width-110-self.side.winfo_reqwidth())
        self.title.configure(wraplength=max(200, width-self.kicker.winfo_reqwidth()-12))
        self.action.configure(wraplength=width)
        self.mentor.configure(wraplength=max(200, width-self.pip_row.winfo_reqwidth()-8))

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
