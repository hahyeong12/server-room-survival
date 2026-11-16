"""결과창 공통 카드 위젯. 의미 단위(원인·성과·피드백·행동)를 개별 카드로 나누어 보여 줍니다.

색 역할: 청록=기본/진행, 금색=현재 목표/강조, 빨강=위험/실패, 회색=보조/비활성. 읽기 전용 표시 도구입니다.
"""
import tkinter as tk
from ui import PANEL, BORDER, TEXT, MUTED, RED, CYAN, GREEN, ActionButton, label
from aidc.ui.ui_kit import PrimaryButton

GOLD = '#ffe08a'
TONES = {'cyan': CYAN, 'gold': GOLD, 'red': RED, 'gray': MUTED, 'green': GREEN}


def tone_card(parent, title, body, tone='cyan', icon='', body_size=12):
    """왼쪽 색 띠 + 작은 제목 + 본문의 카드. 본문 줄바꿈 너비는 카드 크기를 따라갑니다."""
    color = TONES.get(tone, CYAN)
    outer = tk.Frame(parent, bg=PANEL, highlightthickness=1, highlightbackground=BORDER)
    tk.Frame(outer, bg=color, width=6).pack(side='left', fill='y')
    inner = tk.Frame(outer, bg=PANEL, padx=14, pady=9)
    inner.pack(side='left', fill='both', expand=True)
    outer.head = label(inner, (icon+' ' if icon else '')+title, 10, color, True, anchor='w')
    outer.head.pack(anchor='w')
    outer.body = label(inner, body, body_size, TEXT, anchor='w', justify='left', wraplength=520)
    outer.body.pack(anchor='w', fill='x', pady=(3, 0))
    inner.bind('<Configure>', lambda e, w=outer.body: w.configure(wraplength=max(200, e.width-30)))
    return outer


def stat_tile(parent, name, value, tone='cyan'):
    """큰 숫자/상태 하나를 보여 주는 타일(점수·기한·반환 자원 등)."""
    tile = tk.Frame(parent, bg=PANEL, highlightthickness=1, highlightbackground=BORDER, padx=14, pady=8)
    tile.name_label = label(tile, name, 10, MUTED, anchor='w')
    tile.name_label.pack(anchor='w')
    tile.value_label = label(tile, value, 18, TONES.get(tone, CYAN), True, anchor='w')
    tile.value_label.pack(anchor='w')
    return tile


def tile_row(parent, tiles):
    """타일들을 같은 너비로 한 줄에 배치합니다. tiles=[(이름, 값, 톤)]"""
    row = tk.Frame(parent, bg=parent.cget('bg'))
    for column, (name, value, tone) in enumerate(tiles):
        row.columnconfigure(column, weight=1, uniform='tiles')
        stat_tile(row, name, value, tone).grid(row=0, column=column, sticky='nsew', padx=(0 if column == 0 else 6, 0))
    return row


def button_bar(parent, entries):
    """결과창 행동 버튼. entries=[(key, 문구, 명령, 주요 여부)] — 주요 행동 하나만 강조하고 가운데 정렬합니다."""
    bar = tk.Frame(parent, bg=parent.cget('bg'))
    inner = tk.Frame(bar, bg=parent.cget('bg'))
    inner.pack(anchor='center')
    buttons = {}
    for key, text, command, primary in entries:
        button = (PrimaryButton(inner, text, command, strong=True) if primary else ActionButton(inner, text, command))
        button.pack(side='left', padx=6)
        buttons[key] = button
    bar.buttons = buttons
    return bar


def failure_heading(parent, explanation, row=3):
    title = label(parent, explanation['headline'], 16, RED, True, anchor='w', justify='left', wraplength=640)
    title.grid(row=row, column=0, columnspan=2, sticky='ew', pady=(10, 12))
    parent.bind('<Configure>', lambda e: title.configure(wraplength=max(280, e.width-10)), add='+')
    return title


def failure_card(parent, explanation):
    """실패 설명 3장: 직접 원인(빨강) → 왜 그렇게 되었나(회색) → 다음 도전에서는(청록)."""
    box = tk.Frame(parent, bg=parent.cget('bg'))
    box.columnconfigure(0, weight=1)
    box.cards = {}
    for row, (key, title, tone, icon) in enumerate((('cause', '직접 원인', 'red', '✖'),
                                                    ('why', '왜 그렇게 되었나요?', 'gray', '?'),
                                                    ('next', '다음 도전에서는', 'cyan', '➜'))):
        card = tone_card(box, title, explanation[key], tone, icon, body_size=13 if key == 'cause' else 12)
        card.grid(row=row, column=0, sticky='ew', pady=(0 if row == 0 else 8, 0))
        box.cards[key] = card
    return box
