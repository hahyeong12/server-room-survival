"""짧은 사건별 교육 대화와 주제 선택 복습. 고객 메신저와 별도 UI."""
import tkinter as tk
from tkinter import ttk

from story import GUIDES, STEPS, SPEAKERS
from story_portraits import draw_portrait
from aidc.ui.window_placement import center_dialog
from aidc.ui import dpi
from ui import BG, MUTED, CYAN, MessageDialog, label, ActionButton


class StoryDialogueDialog(MessageDialog):
    def __init__(self, parent, pages, confirm=None, portrait_renderer=draw_portrait, chapter_label='Chapter 1',
                 show=True):
        self.portrait_renderer = portrait_renderer
        self.portraits = {}
        super().__init__(parent, '교육 담당자', '울산 AIDC 운영팀', pages,
                         animate=False, message_kind='현장 교육', confirm=confirm,
                         history_hint='교육 도움말에서 다시 보기')
        self.title(f'현장 교육 | 교육 담당자 · {chapter_label}')
        self.geometry(dpi.geometry('820x470'))
        self.minsize(*dpi.size((740, 430)))
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)
        header = self.grid_slaves(row=0)[0]
        header.configure(text='ULSAN AIDC   /   현장 교육')
        for row in (0, 1, 3, 4):
            for widget in self.grid_slaves(row=row):
                widget.grid_configure(columnspan=2)
        self.cast = tk.Frame(self, bg=BG)
        self.cast.grid(row=2, column=0, padx=(20, 0), sticky='n')
        for column, role in enumerate(('player', 'mentor')):
            frame = tk.Frame(self.cast, bg=BG)
            frame.grid(row=0, column=column, padx=3)
            canvas = tk.Canvas(frame, width=dpi.px(120), height=dpi.px(165), bd=0)
            canvas.pack()
            label(frame, '신입 엔지니어' if role == 'player' else '선배 엔지니어',
                  9, MUTED).pack(pady=5)
            self.portraits[role] = canvas
        # 말풍선 기본 폭(80글자)은 초상화와 합치면 창(820px)보다 넓어 내용이 오른쪽에서 잘리고 왼쪽에 몰려 보였습니다.
        # 요구 폭을 창 안으로 줄이고, 실제 폭은 grid가 남는 공간만큼 늘립니다.
        self.bubble.configure(width=40)
        self.bubble.grid_configure(column=1, padx=(12, 20))
        self.skip_button.configure(text='마지막 안내')
        self.close_button = ActionButton(self.next_button.master, '업무로 돌아가기', self.destroy)
        self.render()  # 페이지에 맞게 [마지막 안내]·[업무로 돌아가기]를 배치합니다.
        # 주의: MessageDialog.reveal()(현재 페이지 글 전체 표시)과 이름이 겹치지 않게 show_window를 씁니다.
        self.show_parent, self.window_shown = parent, False
        if show:
            self.show_window()

    def show_window(self):
        """숨긴 채 완성한 교육창을 배치해 보여 줍니다. 이미 보였거나 닫힌 창이면 아무것도 하지 않습니다."""
        try:
            if self.window_shown or not self.winfo_exists():
                return False
        except tk.TclError:  # 예약한 표시 전에 앱(루트)이 이미 닫힌 경우
            return False
        self.window_shown = True
        center_dialog(self, self.show_parent)
        return True

    def render(self):
        super().render()
        self.update_page_buttons()
        speaker = self.steps[self.index][0]
        self.active_role = next((role for role, name in SPEAKERS.items() if name == speaker), 'system')
        for role, canvas in self.portraits.items():
            self.portrait_renderer(canvas, role, role == self.active_role)
        self.speaker.configure(fg=CYAN if self.active_role == 'player' else '#a9beff')


    def update_page_buttons(self):
        """마지막 페이지에서는 주 버튼([첫 업무 시작]·[확인 · 운영실로])이 이미 창을 닫으므로 같은 역할의
        [업무로 돌아가기]와 이미 도착한 [마지막 안내]를 숨깁니다. 앞 페이지에서는 둘 다 그대로 보입니다."""
        close = getattr(self, 'close_button', None)
        if close is None:  # 부모 생성자 안의 첫 render에서는 아직 버튼이 없습니다.
            return
        hide = last_page_hides(self.index, len(self.steps))
        for button in (self.skip_button, close):
            button.pack_forget()
        if not hide:
            self.skip_button.pack(side='right')
            close.pack(side='right', padx=6)


def last_page_hides(index, total):
    """교육창 페이지에서 [마지막 안내]·[업무로 돌아가기]를 숨길지(순수 함수). 마지막 페이지에서만 숨깁니다."""
    return index >= total-1


class StoryReviewDialog(StoryDialogueDialog):
    def __init__(self, parent):
        super().__init__(parent, [line.page() for line in GUIDES['arrival'][1]])
        self.title('교육 복습 · 장면 선택')
        header = self.grid_slaves(row=0, column=0)[0]
        header.configure(text='교육 복습')
        header.grid_configure(columnspan=1)
        self.scene_keys = STEPS
        self.scene = ttk.Combobox(self, state='readonly', width=35,
                                  values=[f'{i+1}. {GUIDES[key][0]}' for i, key in enumerate(STEPS)])
        self.scene.grid(row=0, column=1, sticky='e', padx=20)
        self.scene.current(0)
        self.scene.bind('<<ComboboxSelected>>', self.select_scene)
        self.page.configure(text='장면을 선택해 복습하세요. 업무 진행은 바뀌지 않습니다.')
        center_dialog(self, parent)

    def select_scene(self, _=None):
        key = self.scene_keys[self.scene.current()]
        self.steps = [line.page() for line in GUIDES[key][1]]
        self.index = 0
        self.render()
