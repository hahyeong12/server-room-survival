"""배정 설정창: 요청 요약 → 운영 모드 선택 → 서버 배정안 선택 → 최종 확인 후 작업 시작.
선택·모드 변경·재조회는 원장과 DB를 변경하지 않으며, [선택한 계획으로 작업 시작]만 실제 배정을 요청합니다.

v0.9-4b 화면 구조: 핵심 비교(요약 카드·모드 카드 2개·배정안 카드 2~3개)를 한 화면에 두고, 시작할 수 없는 이유는
빨간 경고 카드로 따로 보여 줍니다. 시작 요약과 버튼은 아래에 고정되어 스크롤해도 항상 보입니다.
"""
import tkinter as tk

from aidc.core.server_resources import SERVERS
from server_console import server_views
from aidc.ui.scroll_area import ScrollArea
from aidc.ui.ui_kit import PrimaryButton
from version import VERSION
from aidc.ui.window_placement import center_dialog
from aidc.ui import dpi
from ui import GREEN, AMBER
from server_widgets import (BG, PANEL, EDGE, TEXT, MUTED, CYAN, RED, FONT,
                            gpu_module, reset_hardware, ink)

# 금색(#ffe08a)은 교육 강조(TutorialHighlight)에만 씁니다. 이 창의 선택 상태·점유 예정은 흰색 테두리로 구분합니다(Q-05).
SELECTED = '#eef4ff'
WARNING_BG = '#2a1218'


def start_blocker(has_options, confirmed, migration, loaded_signature, current_signature):
    """작업을 시작할 수 없는 이유(없으면 None). 창 없이 검증할 수 있는 순수 함수입니다.
    운영 모드와 배정안(자동 추천 포함)을 직접 선택해야 하고, 창을 연 뒤 상황이 바뀌었다면 다시 확인해야 합니다."""
    if not has_options:
        return '시작할 수 있는 배정안이 없습니다.'
    if not confirmed:
        return '운영 모드와 배정안(자동 추천 포함)을 직접 선택해야 작업을 시작할 수 있습니다.'
    if not migration and loaded_signature != current_signature:
        return '창을 연 뒤 시간이나 서버 점유가 바뀌었습니다. [현재 자원으로 다시 확인] 후 계획을 다시 선택해 주세요.'
    return None


def mode_badges(row):
    """운영 모드 카드 아래의 배지 [(문구, 색 역할)]. 기한 준수 여부와 고객 동의 상태를 색과 기호로 구분합니다(순수 함수)."""
    badges = []
    if row['on_time'] is True:
        badges.append((f'✔ 기한 {row["due_label"]} 준수', 'green'))
    elif row['on_time'] is False:
        badges.append((f'✖ 기한 {row["due_label"]}보다 {row["late_minutes"]}분 늦음', 'red'))
    badges.append((('✔ ' if row['agreed'] else '⚠ ')+row['status'], 'cyan' if row['agreed'] else 'amber'))
    return badges


BADGE_COLORS = {'green': GREEN, 'red': RED, 'cyan': CYAN, 'amber': AMBER}


class AllocationDialog(tk.Toplevel):
    def __init__(self, parent, session, mode, on_start, migration=False, on_review=None, on_reload=None,
                 on_mode=None, on_choice=None):
        super().__init__(parent)
        self.session, self.mode, self.on_start = session, mode, on_start
        self.on_review, self.on_reload = on_review, on_reload
        self.on_mode, self.on_choice = on_mode, on_choice
        self.request_id = session.selected_id
        self.migration = migration
        # 직접 고르기 전(자동 추천 포함)에는 작업을 시작할 수 없습니다. 이전 계획은 기존처럼 첫 안이 선택되어 있습니다.
        self.confirmed = migration
        self.title(('작업 이전 계획' if migration else '배정 설정 · 운영 모드와 서버 배정안')+' · '+VERSION)
        self.configure(bg=BG)
        self.withdraw()  # center_dialog가 위치를 정한 뒤 보여 줍니다(기본 위치의 빈 흰 창 점멸 방지).
        self.transient(parent)
        self.geometry(dpi.geometry('1000x740'))
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        # 화면이 작을 때만 스크롤합니다. 시작 요약/[작업 시작]/[닫기]는 항상 보이게 아래에 고정합니다.
        self.scroll = ScrollArea(self, bg=BG)
        self.scroll.grid(row=0, sticky='nsew')
        body = self.body = self.scroll.body
        body.columnconfigure(0, weight=1)
        self.selection = tk.IntVar(value=-1)
        self.mode_var = tk.StringVar(value=mode)

        # 상단: 요청 요약 카드
        self.request_card = tk.Frame(body, bg=PANEL, highlightthickness=1, highlightbackground=EDGE, padx=14, pady=8)
        self.request_card.grid(row=0, sticky='ew', padx=12, pady=(10, 6))
        self.request_card.columnconfigure(0, weight=1)
        self.heading = tk.Label(self.request_card, bg=PANEL, fg=TEXT, font=(FONT, 13, 'bold'), anchor='w', justify='left')
        self.heading.grid(row=0, column=0, sticky='ew')
        self.request_extra = tk.Label(self.request_card, bg=PANEL, fg=TEXT, font=(FONT, 11, 'bold'), anchor='e')
        self.request_extra.grid(row=0, column=1, sticky='e', padx=(12, 0))

        # 중단: 운영 모드 선택 카드 2개
        self.mode_title = tk.Label(body, bg=BG, fg=CYAN, font=(FONT, 11, 'bold'), anchor='w',
                                   text='① 운영 모드 · 모드마다 필요한 자원과 처리 시간이 다릅니다')
        self.mode_title.grid(row=1, sticky='ew', padx=14, pady=(2, 2))
        self.mode_frame = tk.Frame(body, bg=BG)
        self.mode_frame.grid(row=2, sticky='ew', padx=12, pady=(0, 4))
        self.mode_buttons = {}
        self.mode_cards = {}
        self.mode_rows = []
        # 왜 안 되는지는 빨간 경고 카드로 따로 보여 줍니다(없으면 숨김).
        self.warning_card = tk.Frame(body, bg=WARNING_BG, highlightthickness=1, highlightbackground=RED, padx=12, pady=6)
        tk.Label(self.warning_card, text='⚠', bg=WARNING_BG, fg=RED, font=(FONT, 14, 'bold')).pack(side='left', padx=(0, 8))
        self.mode_reason = tk.Label(self.warning_card, bg=WARNING_BG, fg='#ffd5d9', font=(FONT, 11, 'bold'), anchor='w',
                                    justify='left', wraplength=880)
        self.mode_reason.pack(side='left', fill='x', expand=True)
        self.warning_card.grid(row=3, sticky='ew', padx=12, pady=(0, 4))
        self.warning_card.grid_remove()
        if migration:
            self.mode_title.grid_remove()
            self.mode_frame.grid_remove()

        # 하단: 배정안 선택 카드 2~3개
        plan_head = tk.Frame(body, bg=BG)
        plan_head.grid(row=4, sticky='ew', padx=14, pady=(4, 2))
        plan_head.columnconfigure(0, weight=1)
        self.plan_title_label = tk.Label(plan_head, bg=BG, fg=CYAN, font=(FONT, 11, 'bold'), anchor='w',
                                         text=('이전 위치 · 현재 수행의 새 서버 위치 (수치는 GPU / 전력)' if migration else
                                               '② 서버 배정안 · 서버별 GPU / 전력 배분'))
        self.plan_title_label.grid(row=0, column=0, sticky='w')
        self.auto_button = tk.Radiobutton(plan_head, text='자동 추천 · 시작 시 현재 자원으로 다시 계산',
                                         variable=self.selection, value=-1, command=self.user_select,
                                         bg=BG, fg=CYAN, selectcolor=PANEL, activebackground=BG,
                                         activeforeground=CYAN, font=(FONT, 10), anchor='e')
        self.auto_button.grid(row=0, column=1, sticky='e')
        if migration:
            self.auto_button.grid_remove()
        self.cards = tk.Frame(body, bg=BG)
        self.cards.grid(row=5, sticky='ew', padx=12, pady=4)
        self.canvas = tk.Canvas(body, bg=PANEL, height=dpi.px(96), highlightthickness=1, highlightbackground=EDGE)
        self.canvas.grid(row=6, sticky='ew', padx=12)
        self.canvas.bind('<Configure>', lambda _: self.draw_preview())
        info = tk.Frame(body, bg=BG)
        info.grid(row=7, sticky='ew', padx=12, pady=(4, 8))
        info.columnconfigure(0, weight=1)
        self.notice = tk.Label(info, bg=BG, fg=MUTED, font=(FONT, 10), anchor='w', justify='left', wraplength=880)
        self.notice.grid(row=0, sticky='ew')
        self.change_label = tk.Label(info, bg=BG, fg=AMBER, font=(FONT, 10), anchor='w', justify='left', wraplength=880)
        self.change_label.grid(row=1, sticky='ew')
        self.impact_label = tk.Label(info, bg=BG, fg=CYAN, font=(FONT, 10), anchor='w', justify='left', wraplength=880)
        self.impact_label.grid(row=2, sticky='ew')

        # 고정 하단: 시작 요약 + 버튼
        footer = tk.Frame(self, bg=BG)
        footer.grid(row=1, sticky='ew', padx=12, pady=(4, 10))
        footer.columnconfigure(0, weight=1)
        self.summary_label = tk.Label(footer, bg=PANEL, fg=TEXT, font=(FONT, 11, 'bold'), anchor='w', justify='left',
                                      wraplength=880, padx=12, pady=6, highlightthickness=1, highlightbackground=EDGE)
        self.summary_label.grid(row=0, columnspan=3, sticky='ew', pady=(0, 6))
        self.reload_button = self.button(footer, '현재 자원으로 다시 확인', self.reload)
        self.reload_button.grid(row=1, column=0, sticky='w')
        # 이 창의 주요 행동: 선택한 계획으로 시작(대비가 강한 기본 버튼). 닫기·재조회는 보조 버튼입니다.
        self.start_button = PrimaryButton(footer, '선택한 계획으로 작업 시작', self.start)
        self.start_button.configure(font=(FONT, 12, 'bold'), padx=18, pady=8)
        if migration:
            self.start_button.configure(text='선택한 계획으로 이전 · 준비 10분')
        self.start_button.grid(row=1, column=1, padx=8)
        self.close_button = self.button(footer, '닫기', self.destroy)
        self.close_button.grid(row=1, column=2)
        self.bind('<Configure>', self._wrap, add='+')
        self.reload()
        center_dialog(self, parent, size=(1000, 740), minimum=(700, 460))
        self.grab_set()

    def _wrap(self, event):
        if event.widget is self:
            width = max(300, event.width-60)
            for widget in (self.heading, self.mode_reason, self.notice, self.change_label, self.impact_label, self.summary_label):
                widget.configure(wraplength=width-(140 if widget is self.heading else 0))

    @staticmethod
    def button(parent, text, command):
        return tk.Button(parent, text=text, command=command, bg=PANEL, fg=MUTED,
                         activebackground=EDGE, activeforeground=TEXT, font=(FONT, 10),
                         relief='flat', padx=12, pady=7)

    def set_warning(self, text):
        """시작할 수 없는 이유를 빨간 경고 카드로 표시합니다. 비어 있으면 카드를 숨깁니다."""
        self.mode_reason.configure(text=text)
        if text:
            self.warning_card.grid()
        else:
            self.warning_card.grid_remove()

    def reload(self):
        # 재조회 버튼을 누른 경우에만 기존 직접 선택을 해제합니다.
        run = self.session.runs[self.request_id]
        result = self.session.migration_preview(run) if self.migration else self.session.allocation_options(run, self.mode)
        self.options = result['options']
        self.source = result.get('source')
        self.views = server_views(self.session, exclude_playthrough=run.playthrough_id if self.migration else None)
        self.selection.set(0 if self.migration else -1)
        self.confirmed = self.migration       # 모드를 바꾸거나 다시 조회하면 계획을 다시 확인해야 합니다.
        self.loaded_signature = self.signature()
        p = run.state.plans[self.mode]
        if not self.migration:
            self.build_mode_rows(run)
        self.heading.configure(text=f'요청 #{self.request_id} · {run.mission["company_name"]} · {p["label"]}'
                               f'  |  GPU {p["gpu"]} / 전력 {p["power"]}\n'
                               + ('이전할 새 서버 위치를 고르세요.' if self.migration else '운영 모드와 서버 배정안을 고른 뒤 작업을 시작하세요.'),
                               wraplength=760)
        if not self.migration:
            # Chapter 2: 모드별 처리 시간·기한은 모드 카드에 있으므로 두 고객 동시 실행 가능 여부만 덧붙입니다.
            briefing = [line for line in self.session.chapter2_briefing_lines(run) if line.startswith('두 고객')]
            if briefing:
                self.heading.configure(text=self.heading.cget('text')+'\n'+'\n'.join(briefing))
            due = next((r['due_label'] for r in self.mode_rows if r['due_label']), None)
            self.request_extra.configure(text=f'완료 기한 {due}' if due else '')
        if self.migration:
            current = ', '.join(f'{s.server_id} {s.gpu}/{s.power}' for s in self.source.slices) if self.source else '점유 없음'
            self.heading.configure(text=self.heading.cget('text')+f'\n현재 위치: {current} · 기존 수행/진행률/기한 유지 · 이전 준비 10분')
            self.request_extra.configure(text='이전 준비 10분')
        for child in self.cards.winfo_children():
            child.destroy()
        for i in range(3):
            self.cards.columnconfigure(i, weight=0, uniform='')
        self.plan_buttons = []
        self.plan_cards = []
        self.card_captions = []
        self.previous_parts = None
        self.change_text = ''
        self.comparison_rows = []
        for i, parts in enumerate(self.options):
            self.cards.columnconfigure(i, weight=1, uniform='plans')
            card = tk.Frame(self.cards, bg=PANEL, highlightthickness=3, highlightbackground=EDGE, padx=6, pady=4,
                            cursor='hand2', takefocus=True)
            self.plan_cards.append(card)
            card.grid(row=0, column=i, sticky='nsew', padx=3)
            radio = tk.Radiobutton(card, text=self.plan_title(i), variable=self.selection, value=i,
                                   command=self.user_select, bg=PANEL, fg=CYAN, selectcolor=BG,
                                   activebackground=PANEL, activeforeground=CYAN, font=(FONT, 11, 'bold'))
            radio.grid(row=0, columnspan=3, sticky='w')
            self.plan_buttons.append(radio)
            for column, text in enumerate(('서버', '배정 GPU/전력', '잔여 GPU/전력')):
                tk.Label(card, text=text, bg=PANEL, fg=MUTED, font=(FONT, 10)).grid(row=1, column=column, padx=4)
            rows = []
            for row, view in enumerate(self.views, 2):
                spec = view['spec']
                part = next((s for s in parts if s.server_id == spec.key), None)
                g, power = (part.gpu, part.power) if part else (0, 0)
                values = (spec.name, f'{g} / {power}', f'{view["gpu_available"]-g} / {view["power_available"]-power}')
                rows.append((spec.key, g, power, view['gpu_available']-g, view['power_available']-power))
                for column, value in enumerate(values):
                    tk.Label(card, text=value, bg=PANEL, fg=TEXT if part else MUTED,
                             font=(FONT, 10, 'bold' if part else 'normal')).grid(row=row, column=column, padx=4, pady=1)
            self.comparison_rows.append(rows)
            caption = tk.Label(card, text=self.caption(i, parts), bg=PANEL, fg=CYAN, font=(FONT, 10),
                               justify='left', anchor='w', wraplength=290)
            caption.grid(row=6, columnspan=3, pady=(4, 0), sticky='w')
            self.card_captions.append(caption)
            for widget in (card, *card.winfo_children()):
                # Radio의 기본 클릭/키보드 동작은 유지합니다.
                if widget is not radio:
                    widget.bind('<Button-1>', lambda _, n=i: self.select_card(n))
                widget.bind('<Enter>', lambda _, n=i: self.paint_cards(n), add='+')
                widget.bind('<Leave>', lambda _: self.paint_cards(), add='+')
                widget.configure(cursor='hand2')
            card.bind('<Return>', lambda _, n=i: self.select_card(n))
            card.bind('<space>', lambda _, n=i: self.select_card(n))
            card.bind('<Left>', lambda _, n=i: self.select_card((n-1) % len(self.options), focus=True))
            card.bind('<Right>', lambda _, n=i: self.select_card((n+1) % len(self.options), focus=True))
        self.auto_button.configure(state='normal' if self.options else 'disabled')
        if self.options and not self.migration and len(self.options) == 1:
            self.heading.configure(text=self.heading.cget('text')+'\n이 조건에서 의미 있게 구별되는 배정안은 하나뿐입니다.')
        self.start_button.configure(state='normal' if self.options and self.confirmed else 'disabled')
        blocked = '' if self.migration else next((r['reason'] for r in self.mode_rows if r['key'] == self.mode and r['reason']), '')
        self.notice.configure(text=('고르기만 해서는 자원을 점유하지 않습니다. 자동 추천을 포함해 계획을 직접 선택한 뒤 [선택한 계획으로 작업 시작]을 눌러야 시작하며, '
                                    '시작 직전에 한 번 더 검사합니다.'
                                    if self.options else '배정 불가 · '+(blocked or result['reason'])+' · 조건을 확인한 후 다시 조회해 주세요.'),
                              fg=MUTED if self.options else RED)
        if not self.options and not blocked:
            self.set_warning('배정 불가 · '+result['reason'])  # 모드 사유가 없어도 이유를 경고 카드로 보여 줍니다.
        self.draw_preview()
        if self.on_reload is not None:
            self.on_reload()

    def signature(self):
        """창을 연 뒤 요청 상태나 서버 점유가 바뀌었는지 확인하기 위한 값."""
        run = self.session.runs[self.request_id]
        return (self.session.minute, run.request['status'], run.state.phase, tuple(sorted(self.session.servers.allocations)))

    def build_mode_rows(self, run):
        """고성능/절약형을 이 창에서 직접 고릅니다. 값은 모두 현재 엔진에서 읽습니다."""
        self.mode_rows = self.session.allocation_mode_rows(run)
        for child in self.mode_frame.winfo_children():
            child.destroy()
        self.mode_buttons, self.mode_cards = {}, {}
        for column, row in enumerate(self.mode_rows):
            self.mode_frame.columnconfigure(column, weight=1, uniform='modes')
            card = tk.Frame(self.mode_frame, bg=PANEL, highlightthickness=2, highlightbackground=EDGE, padx=2, pady=2)
            card.grid(row=0, column=column, sticky='nsew', padx=3)
            text = f'{row["label"]}\nGPU {row["gpu"]} / 전력 {row["power"]}\n처리 {row["minutes"]}분 → {row["finish_label"]} 완료'
            button = tk.Radiobutton(card, text=text, variable=self.mode_var, value=row['key'], command=self.change_mode,
                                    indicatoron=False, bg=PANEL, fg=TEXT if row['agreed'] else MUTED, selectcolor='#253746',
                                    activebackground=EDGE, activeforeground=TEXT, font=(FONT, 12, 'bold'), justify='left', anchor='w',
                                    padx=12, pady=6, relief='flat', bd=0, highlightthickness=0)
            button.pack(fill='x')
            badges = tk.Frame(card, bg=PANEL)
            badges.pack(fill='x', padx=12, pady=(0, 4))
            for text, tone in mode_badges(row):
                tk.Label(badges, text=text, bg=PANEL, fg=BADGE_COLORS[tone], font=(FONT, 10, 'bold'), anchor='w').pack(anchor='w')
            self.mode_buttons[row['key']] = button
            self.mode_cards[row['key']] = card
        self.paint_modes()
        current = next((r for r in self.mode_rows if r['key'] == self.mode), None)
        self.set_warning(current['reason'] if current else '')

    def paint_modes(self):
        for key, card in self.mode_cards.items():
            card.configure(highlightbackground=SELECTED if key == self.mode_var.get() else EDGE)

    def change_mode(self):
        """모드만 바꾸고 해당 모드의 요구량으로 배정안을 다시 계산합니다. 자원은 점유하지 않습니다."""
        mode = self.mode_var.get()
        if mode == self.mode:
            return
        self.mode = mode
        if self.on_mode is not None:
            self.on_mode(mode)
        self.reload()

    def plan_title(self, index):
        name = '이전안' if self.migration else '배정안'
        return f'{name} {index+1}'+(' (추천)' if index == 0 else '')

    def caption(self, index, parts):
        """실제 원장 수치로만 특징을 설명합니다. 성능/안정성 효과는 주장하지 않습니다."""
        lefts = [{v['spec'].key:(v['gpu_available']-next((s.gpu for s in o if s.server_id == v['spec'].key), 0),
                                 v['power_available']-next((s.power for s in o if s.server_id == v['spec'].key), 0))
                  for v in self.views} for o in self.options]
        total_g = sum(g for g, _ in lefts[index].values())
        total_p = sum(p for _, p in lefts[index].values())
        lines = [f'{len(parts)}개 서버 사용 · 전체 잔여 GPU {total_g} / 전력 {total_p}']
        counts = [len(o) for o in self.options]
        if len(set(counts)) > 1 and len(parts) == min(counts):
            lines.append('특징: 사용 서버 수가 가장 적음')
        elif len(set(counts)) > 1 and len(parts) == max(counts):
            lines.append('특징: 여러 서버에 나누어 배정')
        biggest = max(sorted(lefts[index].items()), key=lambda kv: kv[1][0])
        lines.append(f'남는 GPU 최대: Server {biggest[0]} {biggest[1][0]}개')
        if not self.migration:
            if index == 0:
                lines.append('자동 추천과 같은 배분')
            else:
                base = {s.server_id:s for s in self.options[0]}
                diff = []
                for server in SERVERS:
                    new = next((s for s in parts if s.server_id == server.key), None)
                    g = (new.gpu if new else 0)-(base[server.key].gpu if server.key in base else 0)
                    if g:
                        diff.append(f'{server.key} {g:+d}')
                if diff:
                    lines.append('추천안 대비 GPU: '+', '.join(diff))
        # 카드 높이를 줄이기 위해 첫 줄 아래 설명은 한 단락으로 묶습니다(내용은 같음).
        return lines[0]+'\n'+' · '.join(lines[1:]) if len(lines) > 1 else lines[0]

    def user_select(self):
        """라디오/카드로 계획을 직접 고른 사용자 행동. 화면 갱신 뒤에만 검토 확인을 알립니다."""
        self.confirmed = True
        if self.options:
            self.start_button.configure(state='normal')
        self.draw_preview()
        if self.on_choice is not None and not self.migration:
            index = self.selection.get()
            self.on_choice(self.mode, None if index == -1 else index)
        if self.on_review is not None and not self.migration:
            self.on_review()

    def select_card(self, index, focus=False):
        self.selection.set(index)
        if focus:
            self.plan_cards[index].focus_set()
        self.user_select()

    def paint_cards(self, hover=None):
        for index, card in enumerate(self.plan_cards):
            selected = self.selection.get() == index
            bg = '#253746' if selected else '#182a3b' if hover == index else PANEL
            card.configure(bg=bg, highlightbackground=SELECTED if selected else '#91a7c1' if hover == index else EDGE)
            for widget in card.winfo_children():
                widget.configure(bg=bg)
            self.plan_buttons[index].configure(text=self.plan_title(index)+
                                                (' · 선택 중 ✓' if selected else ' · 클릭하여 선택'))

    def update_selection(self, parts):
        self.paint_cards()
        if self.previous_parts is not None and parts != self.previous_parts:
            changes = []
            for server in SERVERS:
                old = next((p for p in self.previous_parts if p.server_id == server.key), None)
                new = next((p for p in parts if p.server_id == server.key), None)
                g = (new.gpu if new else 0)-(old.gpu if old else 0)
                power = (new.power if new else 0)-(old.power if old else 0)
                if g or power:
                    changes.append(f'Server {server.key} '+', '.join(text for text in
                                   (f'GPU {g:+d}' if g else '', f'전력 {power:+d}' if power else '') if text))
            self.change_text = '이전 선택 대비: '+(' / '.join(changes) if changes else 'GPU 슬롯 위치 변경')
        self.previous_parts = parts
        self.change_label.configure(text=self.change_text)
        # Chapter 2: 이 안을 선택했을 때 다른 고객 요청의 배정 가능 여부를 현재 원장으로 보여 줍니다.
        impacts = ([] if self.migration or not parts else
                   self.session.allocation_impacts(self.session.runs[self.request_id], parts))
        self.impact_label.configure(text=('이 안을 선택하면 → '+' / '.join(impacts)) if impacts else '')
        self.summary_label.configure(text=self.start_summary(parts))

    def start_summary(self, parts):
        """시작 전에 선택한 모드·자원·예상 완료를 한눈에 확인하는 요약. 조회 전용입니다."""
        if self.migration:
            return ''
        if not self.options:
            return '시작할 수 없는 조건입니다. 위의 사유를 확인해 주세요.'
        if not self.confirmed:
            return '시작 전 확인: 운영 모드를 정하고, 자동 추천 또는 배정안 중 하나를 직접 선택해 주세요.'
        row = next(r for r in self.mode_rows if r['key'] == self.mode)
        index = self.selection.get()
        where = ('자동 추천(시작 시 현재 자원으로 다시 계산 · 지금 추천: '
                 + ', '.join(f'{s.server_id} {s.gpu}/{s.power}' for s in self.options[0])+')' if index == -1 else
                 f'{self.plan_title(index)}: '+', '.join(f'{s.server_id} {s.gpu}/{s.power}' for s in parts)+' (선택한 슬롯 그대로 적용)')
        due = ('' if row['on_time'] is None else
               f' · 기한 {row["due_label"]} 준수 가능' if row['on_time'] else f' · 기한 {row["due_label"]}보다 {row["late_minutes"]}분 늦음')
        return (f'시작 요약 · {row["label"]} · GPU {row["gpu"]} / 전력 {row["power"]}\n배정: {where}\n'
                f'예상: 처리 {row["minutes"]}분 → {row["finish_label"]} 완료{due}')

    def draw_preview(self):
        if not hasattr(self, 'options'):
            return
        c = self.canvas
        c.delete('all')
        reset_hardware(c)
        index = self.selection.get()
        parts = self.options[max(0, index)] if self.options else ()
        self.update_selection(parts)
        width = dpi.unpx(c.winfo_width())  # 설계 기준 px로 그리고 끝에서 좌표만 늘립니다.
        if width < 100:
            return
        ink(c, 10, 5, '점유 예정 미리보기 · 흰 테두리 = 선택 예정 / 고객 코드 = 기존 작업', 9, MUTED)
        cell = (width-20)/4
        module = max(28, min(52, (cell-14)/4-4))   # 서버당 최대 4개 GPU를 한 줄로 그립니다.
        for i, view in enumerate(self.views):
            spec = view['spec']
            part = next((s for s in parts if s.server_id == spec.key), None)
            x = 10+i*cell
            ink(c, x+4, 24, spec.name+(f' · 예정 {part.gpu}/{part.power}' if part else ' · 유지'), 10, TEXT, True)
            for slot, owner in enumerate(view['slots']):
                mx, my = x+4+slot*(module+4), 50
                gpu_module(c, mx, my, module, 24, 'fault' if view['health'] != 'HEALTHY' else 'busy' if owner else 'available',
                           owner['code'] if owner else None, slot)
                if part and slot in part.gpu_slots:
                    c.create_rectangle(mx-3, my-3, mx+module+3, my+27, outline=SELECTED, width=3,
                                       tags=('planned-slot', f'planned-{spec.key}-{slot}'))
                    c.create_rectangle(mx-5, my-5, mx+module+5, my+29, outline='#6f86a8', width=1, tags='planned-glow')
        dpi.finish_canvas(c)

    def start(self):
        if self.options and self.session.selected_id != self.request_id:
            self.notice.configure(text='선택한 고객 요청이 변경되었습니다. 창을 닫고 해당 요청에서 다시 열어 주세요.', fg=RED)
            self.start_button.configure(state='disabled')
            return
        reason = start_blocker(bool(self.options), self.confirmed, self.migration,
                               getattr(self, 'loaded_signature', None), self.signature() if not self.migration else None)
        if reason is not None:
            if self.options:
                self.notice.configure(text=reason, fg=RED)
                if not self.confirmed:
                    self.start_button.configure(state='disabled')
            return
        index = self.selection.get()
        parts = None if index == -1 else self.options[index]
        if self.on_start(self.mode, parts):
            self.destroy()
        else:
            self.notice.configure(text='작업을 시작하지 못했습니다. 선택은 유지됩니다. [현재 자원으로 다시 확인] 후 계획을 다시 선택해 주세요.', fg=RED)
