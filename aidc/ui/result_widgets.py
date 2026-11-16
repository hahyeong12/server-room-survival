"""실패 설명을 원인→기록→다음 행동 순서로 보여 주는 공통 표시."""
import tkinter as tk
from ui import PANEL, BORDER, TEXT, MUTED, RED, CYAN, label


def failure_heading(parent, explanation, row=3):
    title = label(parent, explanation['headline'], 16, RED, True, anchor='w', justify='left', wraplength=640)
    title.grid(row=row, column=0, columnspan=2, sticky='ew', pady=(10, 12))
    parent.bind('<Configure>', lambda e: title.configure(wraplength=max(280, e.width-10)), add='+')
    return title


def failure_card(parent, explanation):
    card = tk.Frame(parent, bg=PANEL, padx=18, pady=12, highlightbackground=BORDER, highlightthickness=1)
    card.columnconfigure(0, weight=1)
    for row, (name, key) in enumerate((('직접 원인', 'cause'), ('왜 그렇게 되었나요?', 'why'), ('다음 도전에서는', 'next'))):
        label(card, name, 10, CYAN if key == 'next' else MUTED, True).grid(row=row*2, sticky='w', pady=(8, 3))
        text = label(card, explanation[key], 12, TEXT, anchor='w', justify='left', wraplength=700)
        text.grid(row=row*2+1, sticky='ew', pady=(0, 6))
        card.bind('<Configure>', lambda e, w=text: w.configure(wraplength=max(260, e.width-40)), add='+')
    return card
