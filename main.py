"""서버실 생존기: 첫 출근부터 Chapter 2, 모드 전환과 결과 보고까지."""
import tkinter as tk
from tkinter import ttk, messagebox

from database import Database, DB_PATH, STORY_DB_PATH
from session import GameSession, MAX_PENDING_REQUESTS
from game import RESPONSES, game_time
from server_console import LiveOverview, LiveServerRoom, ServerPanel, server_views
from allocation_dialog import AllocationDialog
from server_widgets import gpu_module, reset_hardware
from story import GUIDES, STEPS, Dialogue, chapter2_failure_pages
from chapter_dialog import ChapterCompleteDialog, Chapter2CompleteDialog, Chapter3CompleteDialog
from network_dialog import NetworkDiagnosisDialog, HardwareDiagnosisDialog, Chapter3FeedbackDialog
from engineering_lab import EngineeringLabDialog, TrainingResultDialog
from aidc.learning.lab_model import diagnosis_lab_target, lab_support
from story_dialog import StoryDialogueDialog, StoryReviewDialog
from aidc.storage.story_slots import StorySlots
from aidc.storage.checkpoints import capture, restore, checkpoint_path
from aidc.story.chapters import CHAPTERS, current_chapter, chapter_from_payload, heading, chapter_state, STATE_LABELS
from tutorial_highlight import TutorialHighlight
from result_summary import free_result_lines
from aidc.ui.result_presentation import failure_explanation
from aidc.ui.ui_kit import PrimaryButton, StatusChip
from aidc.ui.goal_card import GoalCard
from aidc.ui.window_placement import center_dialog
from version import APP_NAME, APP_NAME_EN, VERSION
from story_feedback import StoryFeedbackDialog, FEEDBACK
from request_summary import request_summary
from ui import (BG, PANEL, BORDER, TEXT, MUTED, CYAN, GREEN, RED, AMBER, FONT,
                ActionButton, RejectionDialog, MessageDialog,
                TextDialog, label, request_status_of, status_of)


TIME_BUTTON_GAP = 12  # 교육 강조 테두리(바깥 3px x 2)보다 넓어야 버튼 사이가 비어 보입니다.


def status_tone(run, color):
    """요청 상태를 배지 색 역할로 바꿉니다(순수 함수, 표시 전용). 빨강=위험/실패, 청록=정상 진행, 회색=대기."""
    state = run.state
    if run.terms.get('expired') or (state.phase == 'finished' and not state.succeeded):
        return 'failed'
    if state.phase in ('incident', 'paused'):
        return 'fault'
    if state.phase == 'recovering':
        return 'recover'
    if state.phase == 'running':
        return 'ok'
    if state.phase == 'finished':
        return 'done'
    return 'warn' if run.request['status'] == 'waiting' else 'idle'


class SimulatorApp:
    def __init__(self, root, db=None, db_factory=Database, story_slots=None, checkpoint_start=False, **session_options):
        self.root = root
        self.db_factory, self.closed, self.transitioning = db_factory, False, False
        root.title(f'{APP_NAME} {VERSION} | 울산 AI 데이터센터 관제실')
        root.geometry(f'{min(1280, root.winfo_screenwidth()-40)}x{min(680, root.winfo_screenheight()-100)}')
        root.minsize(1000, 650)
        root.configure(bg=BG)
        self.db = db if db is not None else Database(
            (story_slots or StorySlots()).reserve_new() if session_options.get('mode') == 'tutorial' else
            STORY_DB_PATH if session_options.get('mode') == 'story' else DB_PATH)
        self.story_slots = story_slots or StorySlots(self.db.path.parent if self.db.path else None)
        before = set(root.winfo_children())
        claimed = False
        try:
            self.db.claim_game()
            claimed = True
            self.session = GameSession(self.db, **session_options)
            if checkpoint_start:
                capture(self.session)
            self.center = self.session.center
            self.message_window = None
            self.allocation_window = None
            self.story_window = None
            self.chapter_window = None
            self.story_event_timer = None
            self.story_reviews = set()
            self.feedback_window = None
            self.diagnosis_window = None
            self.lab_window = None
            self.highlight_deferred = False
            self.pending_feedback = None
            self.feedback_events = set()
            self.story_ui_busy = False
            self.tutorial_highlight = TutorialHighlight(root)
            self.story_destroy_binding = root.bind('<Destroy>', self.cancel_story_event, add='+')
            self.setup_ui()
            if self.session.story:
                self.resources.book.select(self.resources.inspector_frame)
            self.refresh()
            self.network.start()
            root.protocol('WM_DELETE_WINDOW', self.on_close)
            if self.session.story:
                if self.session.story.ui_done:
                    self.show_chapter_complete()
                else:
                    self.show_story_event()
        except Exception:
            if claimed:
                self.closed = True
                if hasattr(self, 'network'):
                    self.network.stop()
                if hasattr(self, 'tutorial_highlight'):
                    self.tutorial_highlight.stop()
                if hasattr(self, 'story_destroy_binding'):
                    self.cancel_story_event()
                    root.unbind('<Destroy>', self.story_destroy_binding)
                for widget in set(root.winfo_children()) - before:
                    widget.destroy()
                self.db.release_game()
            if db is None:
                self.db.close()
            raise

    @property
    def state(self):
        return self.session.current.state
    @property
    def mission(self):
        return self.session.current.mission
    @property
    def playthrough_id(self):
        return self.session.current.playthrough_id

    def setup_ui(self):
        style = ttk.Style(self.root)
        style.theme_use('clam')
        style.configure('Treeview', background=PANEL, fieldbackground=PANEL, foreground=TEXT,
                        borderwidth=0, rowheight=29, font=(FONT, 10))
        style.configure('Treeview.Heading', background=BORDER, foreground=TEXT, font=(FONT, 10, 'bold'))
        style.map('Treeview', background=[('selected', BORDER)], foreground=[('selected', CYAN)])
        style.configure('TNotebook',background=PANEL,borderwidth=0)
        style.configure('TNotebook.Tab',background=BORDER,foreground=MUTED,padding=(7,4))
        style.map('TNotebook.Tab',background=[('selected',PANEL)],foreground=[('selected',CYAN)])
        style.configure('Treeview',bordercolor=BORDER,lightcolor=BORDER,darkcolor=BORDER)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(2, weight=1)
        top = tk.Frame(self.root, bg=BG)
        top.grid(row=0, sticky='ew')
        header = tk.Frame(top, bg=BG, padx=16, pady=8)
        header.pack(fill='x')
        if self.session.story:
            # 현재 목표는 하단 긴 문장이 아니라 위쪽의 별도 카드(단계 배지·행동 하나·단계 표시)로 보여 줍니다.
            self.goal_card = GoalCard(top)
            self.goal_card.pack(fill='x', padx=12, pady=(0, 6))
            self.story_objective = self.goal_card.title
        label(header, 'AIDC', 22, CYAN, True).pack(side='left')
        mode_label = '스토리 모드' if self.session.story else '자유 운영 모드'
        label(header, f'ULSAN / {VERSION} · {mode_label}', 11, bold=True).pack(side='left', padx=12)
        self.notice_var = tk.StringVar()
        self.notice_button = ActionButton(header, 'AIDC LINK', self.open_latest_message)
        self.notice_button.pack(side='right')
        self.mode_select_button = ActionButton(header, '모드 선택', self.return_to_modes)
        self.mode_select_button.pack(side='right', padx=(0, 8))
        self.status_var = tk.StringVar()
        tk.Label(header, textvariable=self.status_var, bg=BG, fg=CYAN, font=(FONT, 11),
                 justify='right').pack(side='right', padx=14)
        self.overview = LiveOverview(self.root, self.session)
        self.overview.grid(row=1, sticky='ew', padx=12, pady=(0,6))
        body = self.body = tk.Frame(self.root, bg=BG)
        body.grid(row=2, sticky='nsew', padx=12, pady=(0, 5))
        body.columnconfigure(0, minsize=220)
        body.columnconfigure(1, weight=1, minsize=300)
        body.columnconfigure(2, minsize=244)
        body.rowconfigure(0, weight=1)
        left = tk.Frame(body, bg=PANEL, padx=6, pady=5)
        left.grid(row=0, column=0, sticky='nsew', padx=(0, 10))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=2, minsize=58 if self.session.story else 55)
        left.rowconfigure(4, weight=1, minsize=60)
        label(left, 'AIDC LINK · 고객 요청함', 12, bold=True).grid(row=0, sticky='w', pady=(0, 5))
        self.inbox = self.make_list(left, ('client', 'status'), ('고객 / 국가', '상태 / 기한'), (110, 100), 4)
        self.inbox.grid(row=1, sticky='nsew')
        self.inbox.bind('<ButtonRelease-1>', self.on_inbox_click)
        self.inbox.bind('<Return>', lambda _: self.open_selected_message())
        arrival = tk.Frame(left, bg=BORDER, padx=8, pady=6)
        arrival.grid(row=2, sticky='ew', pady=6)
        arrival.columnconfigure(0, weight=1)
        self.arrival_notice = label(arrival, size=10, justify='left', anchor='w', wraplength=190)
        self.arrival_notice.grid(row=0, sticky='ew')
        self.arrival_request_id = None
        self.arrival_open_button = ActionButton(arrival, '요청 확인', self.open_arrival_message)
        self.arrival_open_button.grid(row=1, sticky='ew', pady=(4, 0))
        self.arrival_schedule = label(arrival, size=10, color=MUTED, anchor='w', wraplength=190)
        self.arrival_schedule.grid(row=2, sticky='ew', pady=(4,0))
        label(left, '운영 작업 · 진행률', 12, bold=True).grid(row=3, sticky='w', pady=(3, 5))
        self.active_list = self.make_list(left, ('client', 'progress'), ('고객', '상태 / 진행'), (70, 140), 3)
        self.active_list.grid(row=4, sticky='nsew')
        self.active_list.bind('<ButtonRelease-1>', self.on_active_click)
        middle = tk.Frame(body, bg=PANEL, padx=0, pady=0)
        middle.grid(row=0, column=1, sticky='nsew', padx=(0, 10))
        self.resources = ServerPanel(body, self.session)
        self.resources.compare_button.configure(command=self.open_allocation_plans)
        self.resources.fault_button.configure(command=lambda:self._perform(
            lambda:self.session.inject_server_fault(self.resources.selected)))
        self.resources.repair_button.configure(command=lambda:self._perform(
            lambda:self.session.begin_server_repair(self.resources.selected)))
        self.network = self.server_room = LiveServerRoom(middle, self.session, self.select_server)
        self.network.pack(fill='both', expand=True)
        self.alert = label(middle, size=10, color=AMBER, justify='left', wraplength=400)
        self.alert.pack(fill='x', pady=(3, 0))
        self.resources.grid(row=0, column=2, sticky='nsew')
        self.network.extra_canvases = [self.overview, self.resources.inspector]
        controls = self.controls = tk.Frame(self.root, bg=PANEL, padx=12, pady=4)
        controls.grid(row=3, sticky='ew', padx=12, pady=(0, 5))
        controls.columnconfigure(0, weight=1)
        self.detail_title = label(controls, size=13, bold=True, anchor='w')
        self.detail_title.grid(row=0, column=0, sticky='ew')
        # 상태는 글줄 대신 색·기호가 있는 배지로 먼저 보여 줍니다.
        self.status_chip = StatusChip(controls, 'idle', '대기', size=11)
        self.status_chip.grid(row=0, column=1, sticky='e', padx=(10, 0))
        self.action_hint = label(controls, size=10, color=MUTED, anchor='w', justify='left')
        self.action_hint.grid(row=1, sticky='ew', pady=(3, 5))
        self.action_hint.bind('<Configure>', lambda e: self.action_hint.configure(wraplength=max(300, e.width-5)))
        modes = tk.Frame(controls, bg=PANEL)
        modes.grid(row=2, sticky='ew', pady=(0, 5))
        label(modes, '배정 설정 · 운영 모드', 10, MUTED).pack(side='left', padx=(0, 10))
        self.allocation_choice = None
        self.plan_var = tk.StringVar(value='performance')
        self.mode_buttons = {}
        for key, text in (('performance', '고성능 모드'), ('economy', '절약형 모드')):
            button = tk.Radiobutton(modes, text=text, variable=self.plan_var, value=key,
                                    command=lambda:self.preview_plan(show_preview=True), bg=PANEL, fg=TEXT, selectcolor=BORDER,
                                    activebackground=PANEL, activeforeground=CYAN, font=(FONT, 10))
            button.pack(side='left', padx=(0, 12))
            button.bind('<Enter>', lambda _, k=key: self.resources.refresh(k))
            button.bind('<Leave>', lambda _: self.preview_plan())
            self.mode_buttons[key] = button
        # 모드 오른쪽: 현재 선택한 모드와 배정안 설정 여부(실제 선택은 [배정 설정·선택] 창에서 합니다).
        self.allocation_status = label(modes, '', 10, CYAN, anchor='w')
        self.allocation_status.pack(side='left', padx=(8, 0))
        self.action_frame = tk.Frame(controls, bg=PANEL)
        self.action_frame.grid(row=3, sticky='ew')
        tools = tk.Frame(self.root, bg=BG, padx=12)
        tools.grid(row=4, sticky='ew', pady=(0, 5))
        self.time_buttons = {}
        # 라벨과 +10/+30/+60분을 하나의 [시간 빨리감기] 기능으로 묶어 교육에서도 그룹 단위로 강조합니다.
        self.time_group = tk.Frame(tools, bg=PANEL, highlightthickness=1, highlightbackground=CYAN, padx=10, pady=4)
        self.time_group.pack(side='left')
        label(self.time_group, '⏩ 시간 빨리감기', 11, CYAN, True).pack(side='left', padx=(0, 10))
        for minutes in (10, 30, 60):
            b = ActionButton(self.time_group, f'+{minutes}분', lambda m=minutes: self.advance_time(m))
            # 버튼마다 금색 테두리(바깥 3px)를 치므로 간격을 넓혀 버튼 사이 빈 공간이 강조되지 않게 합니다.
            b.pack(side='left', padx=(0, TIME_BUTTON_GAP))
            self.time_buttons[minutes] = b
        # 교육 강조는 묶음 프레임(라벨·빈 공간)이 아니라 세 버튼 각각에 테두리를 칩니다. 다른 장의 시간 안내도 같은 대상을 씁니다.
        self.time_group.tutorial_parts = lambda: list(self.time_buttons.values())
        ActionButton(tools, '대화 기록', self.show_conversation_history).pack(side='right', padx=(6, 0))
        # v0.9-4a: 현재 교육 사건을 더 깊게 관찰하는 조회 전용 화면(지원하지 않는 미션에서는 이유만 안내합니다).
        self.lab_button = ActionButton(tools, 'Engineering Lab (Prototype)', self.open_engineering_lab, accent=AMBER)
        self.lab_button.pack(side='right', padx=6)
        ActionButton(tools, '수행 기록', self.show_history).pack(side='right', padx=6)
        ActionButton(tools, '이벤트 / 로그', self.show_events).pack(side='right', padx=6)
        if self.session.story:
            self.story_bar = tk.Frame(self.root, bg=PANEL, padx=12, pady=5)
            self.story_bar.grid(row=5, sticky='ew', padx=12, pady=(0, 5))
            self.story_bar.columnconfigure(0, weight=1)
            self.story_help_button = ActionButton(self.story_bar, '교육 도움말', self.show_story_help)
            self.story_help_button.grid(row=0, column=1, padx=6)
            self.story_skip_button = ActionButton(self.story_bar, '튜토리얼 건너뛰기', self.skip_tutorial, accent=AMBER)
            self.story_skip_button.grid(row=0, column=2)
            self.story_complete_button = ActionButton(self.story_bar, CHAPTERS[1].label+' 완료', self.show_chapter_complete)
            self.story_retry_button = ActionButton(self.story_bar, '이번 시도 종료 · 재도전', self.confirm_retry_chapter2, accent=AMBER)
            self.story_retry3_button = ActionButton(self.story_bar, CHAPTERS[3].label+' 다시 도전', self.confirm_retry_chapter3, accent=AMBER)
            self.story_retry3b_button = ActionButton(self.story_bar, CHAPTERS['3b'].label+' 다시 도전', self.confirm_retry_chapter3b, accent=AMBER)
            # v0.9-4a-1 심화 연수: Chapter 3b 성공 정규 슬롯에서만 [심화 연수 시작], 연수 사건이 끝났을 때만 [연수 사건 다시 받기]
            self.story_training_button = ActionButton(self.story_bar, CHAPTERS['lab'].label+' 시작 ▶', self.begin_training)
            self.story_restart_button = ActionButton(self.story_bar, '연수 사건 다시 받기', self.restart_training_incident, accent=AMBER)
            self.resources.book.bind('<<NotebookTabChanged>>', self.on_story_preview, add='+')
            self.resource_confirm_button = tk.Button(
                self.resources.inspector_frame, text='GPU·전력 정보 확인', bg=PANEL, fg=CYAN,
                font=(FONT, 9), command=self.confirm_story_resources, relief='flat')
            self.resource_confirm_button.pack(fill='x', before=self.resources.fault_button.master)

    def make_list(self, parent, columns, names, widths, height):
        tree = ttk.Treeview(parent, columns=columns, show='headings', height=height, selectmode='browse')
        for key, name, width in zip(columns, names, widths):
            tree.heading(key, text=name)
            tree.column(key, width=width, minwidth=45, stretch=True)
        # 긴 목록만 자체 스크롤하며 관제실 전체는 스크롤하지 않습니다.
        tree.bind('<MouseWheel>', lambda e: tree.yview_scroll(-int(e.delta/120), 'units'))
        return tree

    def refresh(self):
        self.update_status()
        self.render_actions()
        self.preview_plan()
        if self.session.story:
            story = self.session.story
            self.update_goal_card()
            self.story_skip_button.configure(state='disabled' if story.tutorial_completed else 'normal')
            self.resource_confirm_button.configure(state='normal' if story.step == 'resources' else 'disabled')
            training = story.training
            if story.chapter3 is None and story.chapter3b is None and story.chapter2 is not None and self.session.chapter2_retry_available:
                self.story_retry_button.grid(row=0, column=3, padx=(6, 0))
            else:
                self.story_retry_button.grid_remove()
            if story.chapter3 is not None and story.chapter3b is None and self.session.chapter3_retry_available:
                self.story_retry3_button.grid(row=0, column=3, padx=(6, 0))
            else:
                self.story_retry3_button.grid_remove()
            if story.chapter3b is not None and training is None and self.session.chapter3b_retry_available:
                self.story_retry3b_button.grid(row=0, column=3, padx=(6, 0))
            else:
                self.story_retry3b_button.grid_remove()
            if training is None and story.chapter3b is not None and story.chapter3b.completed and not self.session.training_unlock_reason():
                self.story_training_button.grid(row=0, column=4, padx=(6, 0))
            else:
                self.story_training_button.grid_remove()
            if training is not None and self.session.training_can_restart():
                self.story_restart_button.grid(row=0, column=4, padx=(6, 0))
            else:
                self.story_restart_button.grid_remove()
            if training is not None:
                self.story_skip_button.grid_remove()
                if training.done:
                    self.story_complete_button.configure(text='연수 결과')
                    self.story_complete_button.grid(row=0, column=2)
                else:
                    self.story_complete_button.grid_remove()
            elif story.chapter3b is not None:
                self.story_skip_button.grid_remove()
                if story.chapter3b.completed:
                    self.story_complete_button.configure(text=CHAPTERS['3b'].label+' 결과')
                    self.story_complete_button.grid(row=0, column=2)
                else:
                    self.story_complete_button.grid_remove()
            elif story.chapter3 is not None:
                # Chapter 3(독립 연습 포함)에는 Chapter 1 건너뛰기가 없습니다. 완료한 뒤에는 결과 창을 다시 열 수 있습니다.
                self.story_skip_button.grid_remove()
                if story.chapter3.completed:
                    self.story_complete_button.configure(text=CHAPTERS[3].label+' 결과')
                    self.story_complete_button.grid(row=0, column=2)
                else:
                    self.story_complete_button.grid_remove()
            elif story.chapter2 is not None:
                # Chapter 2(연습 포함)에는 Chapter 1 건너뛰기가 없습니다. 완료한 뒤에는 결과 창을 다시 열 수 있습니다.
                self.story_skip_button.grid_remove()
                if story.chapter2.completed:
                    self.story_complete_button.configure(text=CHAPTERS[2].label+' 결과')
                    self.story_complete_button.grid(row=0, column=2)
                else:
                    self.story_complete_button.grid_remove()
            elif story.intro_active:
                self.story_skip_button.grid_remove()
                self.resource_confirm_button.pack_forget()
                if story.ui_done or story.onboarding.step == 'closed':
                    failed = story.onboarding.step == 'closed'
                    self.story_complete_button.configure(text='실패 결과·재도전' if failed else '근무 결과',
                                                         command=self.show_chapter_failure if failed else self.show_chapter_complete)
                    self.story_complete_button.grid(row=0, column=2)
                else:
                    self.story_complete_button.grid_remove()
            elif story.chapter_completed:
                self.story_skip_button.grid_remove()
                self.story_complete_button.configure(text=current_chapter(story).label+' 결과')
                self.story_complete_button.grid(row=0, column=2)
            elif story.mission_status == 'closed':
                self.story_complete_button.configure(text='실패 결과·재도전', command=self.show_chapter_failure)
                self.story_complete_button.grid(row=0, column=2)
            else:
                self.story_complete_button.grid_remove()
        self.update_tutorial_highlight()
        lab = getattr(self, 'lab_window', None)
        if lab is not None and lab.winfo_exists():
            lab.refresh()  # 같은 세션 상태를 다시 읽기만 합니다.

    def update_goal_card(self):
        """세션의 현재 목표를 위쪽 목표 카드에 반영합니다(표시 전용, 게임 상태를 바꾸지 않음)."""
        story = self.session.story
        if not story or not hasattr(self, 'goal_card') or not self.goal_card.winfo_exists():
            return
        phase = self.story_phase or 'ACTION'
        head = heading(self.session)
        if story.intro_active and story.chapter2 is None:
            card = story.onboarding.card
            if card['done'] or card['closed']:
                self.goal_card.set('RESULT', self.session.story_objective(), kicker=head, phase='FEEDBACK' if card['done'] else 'ACTION')
                return
            kicker = head+(f' · 업무 {card["job"][0]}/{card["job"][1]}' if card['job'] else '')
            self.goal_card.set(f'STEP {card["step_no"]}/{card["total"]}', card['title'], card['action'], kicker,
                               card['pips'], card['mentor'], phase)
            return
        self.goal_card.set(phase, f'{head} · {self.session.story_objective()}', phase=phase)

    def update_tutorial_highlight(self):
        """현재 사실에서 대상을 재계산합니다. 대화/복습을 읽는 동안 관제실은 점멸하지 않습니다."""
        highlight = self.tutorial_highlight
        story = self.session.story
        if (story and not self.closed and not self.transitioning
                and self.story_objective.winfo_exists()):
            self.update_goal_card()
        if getattr(self, 'highlight_deferred', False):
            # 단계가 바뀐 직후에는 피드백/교육창이 먼저 열리므로, 다음 대상 강조를 그 뒤로 미룹니다(순간 점멸 방지).
            highlight.clear()
            return
        guided_intro = bool(story and story.intro_active and self.session.mode == 'tutorial' and not story.ui_done)
        if (self.closed or self.transitioning or not story or (story.intro_active and not guided_intro)
                or (story.tutorial_completed and not guided_intro) or story.chapter2 is not None
                or story.chapter3 is not None or story.chapter3b is not None or story.training is not None
                or (story.chapter_completed and not guided_intro) or story.mission_status == 'closed'
                or any(w is not None and w.winfo_exists()
                       for w in (self.story_window, self.feedback_window, self.message_window, *self.story_reviews))):
            highlight.clear()
            return
        step, widget, key = story.ui_step, None, story.ui_step
        plan_window = self.allocation_window
        if plan_window is not None and plan_window.winfo_exists():
            # 팝업이 열려 있으면 팝업 안의 위젯만 대상으로 합니다. 부모 화면 버튼은 강조하지 않습니다.
            if plan_window.migration:
                pass
            elif step == 'allocation' and plan_window.start_button.cget('state') != 'disabled':
                widget = plan_window.start_button
            elif step == 'allocation' and plan_window.plan_buttons:
                # 아직 계획을 확인하지 않았다면 먼저 계획 카드를 직접 선택하게 합니다.
                widget, key = plan_window.plan_buttons[0], 'plan'
            elif step == 'preview' and plan_window.plan_buttons:
                widget, key = plan_window.plan_buttons[0], 'plan'
        elif step == 'server':
            widget = self.network
        elif step == 'resources':
            if self.resources.book.select() == str(self.resources.inspector_frame):
                widget = self.resource_confirm_button
            else:
                widget, key = self.resources, 'inspector'
        elif step == 'request':
            target_id = story.onboarding.rid if story.intro_active else story.request_id
            widget = self.arrival_open_button if self.arrival_request_id == target_id else self.notice_button
        elif step == 'preview':
            # 탭은 이동 수단일 뿐입니다. 탭이 열려 있으면 실제 비교 버튼을 가리킵니다.
            if self.resources.book.select() == str(self.resources.review_frame):
                if self.resources.compare_button.cget('state') != 'disabled':
                    widget, key = self.resources.compare_button, 'compare'
            else:
                widget = self.resources
        elif step == 'allocation':
            allowed = self.session.allocation_preview(self.session.current, self.plan_var.get())['allowed']
            widget = self.action_buttons.get('start') if allowed else self.mode_buttons['performance']
        elif step in ('time', 'work_complete'):
            widget = self.time_group
        elif step == 'operations':
            widget = self.action_buttons.get('operations')
        # 새 튜토리얼은 위쪽 목표 카드가 '지금 할 행동'을 이미 말하므로 같은 내용의 금색 클릭 안내를 따로 띄우지 않습니다.
        highlight.show(key, widget, pointer=not guided_intro)

    def tutorial_window_closed(self, event):
        if event.widget is self.story_window:
            pass  # 기존 호출부가 닫힌 대화창의 존재 여부도 조회할 수 있도록 참조를 유지합니다.
        elif event.widget in self.story_reviews:
            self.story_reviews.discard(event.widget)
        else:
            return
        self.update_tutorial_highlight()

    @property
    def story_phase(self):
        if self.feedback_window is not None and self.feedback_window.winfo_exists():
            return 'FEEDBACK'
        if any(w is not None and w.winfo_exists() for w in (self.story_window, self.chapter_window)):
            return 'STORY'
        return 'ACTION' if self.session.story else None

    def story_anchor(self, step):
        widget = {'server': self.network, 'resources': getattr(self, 'resource_confirm_button', self.resources),
                  'request': self.arrival_open_button, 'preview': self.resources,
                  'allocation': self.action_frame, 'time': self.time_group,
                  'work_complete': self.time_group, 'operations': self.action_frame,
                  'c2_requests': self.arrival_open_button, 'c2_review': self.resources,
                  'c2_allocate': self.action_frame, 'c2_progress': self.time_group,
                  'c2_finish': self.time_group, 'c3_a_start': self.arrival_open_button, 'c3_b_start': self.arrival_open_button,
                  'c3_a_incident': self.time_group, 'c3_b_incident': self.time_group,
                  'c3_a_finish': self.time_group, 'c3_b_finish': self.time_group}.get(step, self.controls)
        if step == 'server' and 'A' in self.network.rack_bounds:
            x, y, right, bottom = self.network.rack_bounds['A']
            return self.network.winfo_rootx()+int(x), self.network.winfo_rooty()+int(y), int(right-x), int(bottom-y)
        return widget.winfo_rootx(), widget.winfo_rooty(), widget.winfo_width(), widget.winfo_height()

    def queue_story_feedback(self, previous, anchor):
        story = self.session.story
        if story and story.intro_active:
            return  # 짧은 입문/첫 근무는 목표 카드로 안내하며 매 조작마다 창을 열지 않습니다.
        if (not story or previous not in FEEDBACK or story.skipped or story.ui_done
                or story.mission_status == 'closed' or previous not in story.ui_completed_steps):
            return
        # 완료 단계는 단조 증가합니다. 실행 중 실제 전환에서만 생성하므로 재실행 시 성공을 재생하지 않습니다.
        token = (previous, story.ui_step)
        if token not in self.feedback_events:
            self.pending_feedback = (token, previous, anchor)

    def build_popup(self, factory, *args, **kwargs):
        # 중앙/인접 배치의 update_idletasks 중 종료 예약이 재진입하지 않게 합니다.
        previous = self.story_ui_busy
        before = set(self.root.winfo_children())
        self.story_ui_busy = True
        try:
            return factory(*args, **kwargs)
        except Exception:
            for widget in set(self.root.winfo_children())-before:
                if isinstance(widget, tk.Toplevel):
                    widget.destroy()
            raise
        finally:
            self.story_ui_busy = previous

    def feedback_closed(self, event):
        if event.widget is not self.feedback_window or self.closed or self.transitioning:
            return
        self.cancel_story_event()
        self.story_event_timer = self.root.after_idle(self.resume_story_event)

    def update_status(self):
        active = [r for r in self.session.runs.values() if r.state.phase in ('running','incident','paused','recovering')]
        unread = sum(not r.request['is_read'] for r in self.session.runs.values())
        clock = getattr(self.session, 'time_label', '09:00')
        self.status_var.set(f'{clock}   운영 {len(active)}건\nGPU {self.center.gpu_used}/10 · 전력 {self.center.power_used}/10')
        self.notice_var.set(f'새 업무 메시지 {unread}건' if unread else '모든 메시지 확인함')
        self.notice_button.configure(text=f'AIDC LINK · {self.notice_var.get()}', fg=CYAN if unread else MUTED)
        for tree in (self.inbox, self.active_list):
            for item in tree.get_children():
                tree.delete(item)
        for rid, run in self.session.runs.items():
            name, color = request_status_of(run)
            short = {'new':'신규','review':'검토','waiting':'대기','operating':'운영','rejected':'거절','completed':'완료'}[run.request['status']]
            if run.state.phase == 'accepted': short = '수락'
            elif run.state.phase in ('incident','paused'): short = '장애'
            elif run.state.phase == 'recovering': short = '복구'
            elif run.terms.get('expired'): short = '만료'
            elif run.state.phase == 'finished' and not run.state.succeeded: short = '실패'
            if self.session.hardware_servers(run):
                short, color = '장비', RED
            elif run.state.allocated and run.migration_left:
                short = '이전'
            level = self.session.deadline_level(run)
            if level:
                color = RED if level=='overdue' else AMBER
                name = ('초과 · ' if level=='overdue' else '임박 · ') + name
            tag = f'request-{rid}'
            if run.terms:
                t = run.terms
                wait = t.get('started', t.get('completed', t.get('closed', self.session.minute)))-t['received']
                name = f'{short} {wait}분/{game_time(t["due"]).split()[-1]}'
            self.inbox.tag_configure(tag, foreground=color)
            marker = '● ' if not run.request['is_read'] else ''
            country = {'싱가포르':'SG','일본':'JP','미국':'US'}.get(run.mission['country'],run.mission['country'])
            self.inbox.insert('', 'end', iid=str(rid), values=(f'{marker}{country} · {run.mission["company_name"]}', name), tags=(tag,))
            if run in active:
                status = ('서버 장애' if self.session.hardware_servers(run) else '이전 준비' if run.migration_left else
                          f'복구 준비 {run.state.recovery_left}분' if run.state.incident_kind and run.state.recovered_by and run.state.phase == 'recovering'
                          else status_of(run.state)[0])
                self.active_list.insert('', 'end', iid=str(rid), values=(run.mission['country'], f'{status} {getattr(run.state,"progress",0):.0f}%'))
        self.inbox.selection_set(str(self.session.selected_id))
        unread_new = [r for r in self.session.runs.values()
                      if not r.request['is_read'] and r.request['status']=='new']
        incoming = max(unread_new, key=lambda r:r.request['id']) if unread_new else None
        self.arrival_request_id = incoming.request['id'] if incoming else None
        if incoming:
            plan = incoming.state.plans['performance']
            self.arrival_notice.configure(text=f'{incoming.mission["company_name"]} · 새 요청\n'
                                          f'필요 GPU {plan["gpu"]} · 가용 GPU {self.session.servers.available()[0]}', fg=CYAN)
        else:
            self.arrival_notice.configure(text='새 요청은 시간 진행 중 자동 도착합니다.', fg=MUTED)
        self.arrival_open_button.configure(state='normal' if incoming else 'disabled')
        pending = self.session.pending_request_count
        limit_note = ' · 접수 보류' if pending >= MAX_PENDING_REQUESTS else ''
        self.arrival_schedule.configure(text=f'다음 {self.session.next_arrival_label} · '
                                       f'{pending}/{MAX_PENDING_REQUESTS}'+(' 보류' if limit_note else ''))
        if self.session.story:
            self.arrival_schedule.configure(text=f'{heading(self.session)} · 미션에 따라 요청 접수')
            story = self.session.story
            if story.step == 'request' and not story.request_read and not story.tutorial_completed:
                target = self.session.runs[story.request_id]
                self.arrival_request_id = story.request_id
                self.arrival_notice.configure(text=f'{target.mission["company_name"]} · 고객 조건 확인\n요청 모드·자원·완료 기한을 읽어 주세요.', fg=CYAN)
                self.arrival_open_button.configure(state='normal')
            if not incoming:
                if self.arrival_request_id is None:
                    self.arrival_notice.configure(text=f'{heading(self.session)} · 고객 업무', fg=MUTED)
        faults = [r for r in active if r.state.phase in ('incident','paused')]
        self.alert.configure(text='! ' + ' · '.join(r.mission['country'] for r in faults)+' 장애 / 중단 · 대응을 선택하세요' if faults else '정상 작업은 시간 진행 버튼으로 함께 처리됩니다.')
        hardware = [key for key,value in self.session.servers.hardware.items() if value.state != 'HEALTHY']
        if hardware:
            self.alert.configure(text='장비 사용 불가: '+', '.join(hardware)+' · 랙 선택 → 복구 / 고객 선택 → 작업 이전')
        self.network.redraw()
        self.overview.refresh()

    def preview_plan(self, show_preview=False):
        self.resources.refresh(self.plan_var.get())
        if show_preview:
            self.resources.show_preview()
        plan = self.state.plans[self.plan_var.get()]
        available_gpu, available_power = self.session.servers.available()
        available_gpu = min(available_gpu, self.center.available_gpu())
        available_power = min(available_power, self.center.available_power())
        fits = plan['gpu'] <= available_gpu and plan['power'] <= available_power
        editable = self.state.phase in ('ready','accepted') or (self.state.phase == 'finished' and not self.state.succeeded)
        for key, button in self.mode_buttons.items():
            p = self.state.plans[key]
            status = self.session.mode_status(self.session.current, key)
            if editable and (p['gpu'] > available_gpu or p['power'] > available_power):
                status += ' · 자원 부족'
            button.configure(text=f'{p["label"]} — {status}', state='normal' if editable else 'disabled')
        self.update_allocation_status()
        for key in ('start','retry'):
            if key in self.action_buttons:
                # 시작할 수 없는 모드(자원 부족·고객 동의 없음)는 설정 버튼도 비활성화합니다. 이유는 모드 표시와 Inspector의
                # [배정 계획 비교·선택]으로 열리는 설정창에서 확인할 수 있습니다.
                allowed = fits and self.session.allocation_preview(self.session.current, self.plan_var.get())['allowed'] and (key != 'retry' or self.state.retry_count < 2)
                self.action_buttons[key].configure(state='normal' if allowed else 'disabled')
        self.update_tutorial_highlight()

    def render_actions(self):
        for widget in self.action_frame.winfo_children():
            widget.destroy()
        for column in range(6):
            self.action_frame.columnconfigure(column, weight=0)
        s, r = self.state, self.session.current.request
        name, color = request_status_of(self.session.current)
        if self.session.hardware_status(self.session.current):
            name += ' · '+self.session.hardware_status(self.session.current)
            color = RED if self.session.hardware_servers(self.session.current) else AMBER
        self.detail_title.configure(text=f'요청 #{r["id"]} · {self.mission["company_name"]} / {self.mission["country"]}', fg=TEXT)
        self.status_chip.set(status_tone(self.session.current, color), name)
        eta = getattr(s, 'remaining_minutes', 0)
        self.action_hint.configure(text=f'{self.mission["title"]}  |  진행 {getattr(s,"progress",0):.0f}% · 예상 잔여 {eta}분 (장애·복구 지연 제외)')
        if s.phase in ('ready','accepted'):
            if s.phase == 'accepted':
                self.action_hint.configure(text='요청을 수락했습니다 · 배정 대기 중입니다. 아직 서버와 자원은 점유하지 않았습니다. [배정 설정·선택]에서 운영 모드와 서버 배정안을 정해 작업을 시작하세요.')
            else:
                self.action_hint.configure(text='새 요청입니다. 조건과 기한을 확인한 뒤 [배정 설정·선택]으로 바로 배정하거나, 먼저 수락만 하고 나중에 배정할 수 있습니다.')
            if self.session.current.proposals:
                proposal = self.session.current.proposals[-1]
                status = {'pending':'고객 답변 대기 · 시작 전 답변 확인', 'accepted':'고객 동의 · 절약형으로 시작 가능',
                          'rejected':'고객 거절 · 기존 고성능 조건 유지'}[proposal['status']]
                self.action_hint.configure(text=f'절약형 대안: {status}. 자원은 작업 시작 시 다시 확인합니다.')
        elif s.phase == 'running' and s.progress == 0:
            self.action_hint.configure(text='자원 배정 완료 · 진행 0% · [시간 빨리감기]로 시간을 진행하면 모든 정상 작업이 함께 진행됩니다.')
        elif s.phase in ('incident','paused'):
            self.action_hint.configure(text=f'필요 네트워크 {s.network_needed} / 가용 {s.network_available} · 중단 {s.downtime}/60분 · 대응 {s.response_attempts}/3회 · 자원 점유 유지')
            locked = self.session.training_response_locked(self.session.current)
            training = self.session.story.training if self.session.story else None
            if s.incident_kind and training is not None and r['id'] in training.request_ids:
                # 심화 연수: 원인 수치를 보여 주지 않습니다. 관측은 Engineering Lab, 조치는 Stage 5 판단 뒤 이 버튼으로 합니다.
                self.action_hint.configure(text='심화 연수 사건 · 고객 작업 중단 · 원인 미확인\n'
                                           f'중단 {s.downtime}/60분 · 대응 {s.response_attempts}/3회'
                                           + (f'\n{locked}' if locked else '\nStage 5: 판단한 원인에 맞는 조치를 선택하세요.'))
            elif s.incident_kind:
                # Chapter 3: 원인은 알려 주지 않고 장비가 정상이라는 사실과 확인 방법만 안내합니다.
                self.action_hint.configure(text='GPU·서버 장비 정상 · 네트워크 문제로 작업 중단 · [네트워크 진단]에서 원인을 확인한 뒤 대응하세요.\n'
                                           f'필요 네트워크 {s.network_needed} / 가용 {s.network_available} · 중단 {s.downtime}/60분 · 대응 {s.response_attempts}/3회'
                                           + (f'\n{s.result_text}' if s.phase == 'paused' and s.response_attempts else ''))
        elif s.phase == 'recovering':
            self.action_hint.configure(text=f'복구·재처리 준비 {s.recovery_left}분 · 진행 {s.progress:.0f}% · 준비 후 정상 실행을 재개합니다.')
        elif s.phase == 'finished':
            self.action_hint.configure(text=s.result_text if s.succeeded else f'{s.result_text} 재처리 {s.retry_count}/2회 · 새 배정과 20분 준비가 필요합니다.')
        delay_reason = self.session.delay_reason(self.session.current)
        recovery = self.session.recovery_status_lines(self.session.current)
        if recovery:
            # 장애 해결 뒤: 복구 준비 중 / 정상 실행 중 상태를 간략히 표시(지연 위험이 실제로 있을 때만 그 내용을 덧붙임)
            self.action_hint.configure(text='\n'.join(recovery)+('\n'+delay_reason if delay_reason else '')
                                       +'\n'+self.session.deadline_summary(self.session.current))
        elif delay_reason:
            self.action_hint.configure(text=delay_reason)
        else:
            self.action_hint.configure(text=self.action_hint.cget('text')+'\n'+self.session.deadline_summary(self.session.current))
        if self.session.mode == 'free':
            # v0.9-2b: 팝업 없이 운영 패널에 실제 결과 요약을 덧붙입니다. 끝나지 않은 요청에는 표시하지 않습니다.
            summary = free_result_lines(self.session.current)
            if summary:
                self.action_hint.configure(text=self.action_hint.cget('text')+'\n── 결과 요약 ──\n'+'\n'.join(summary))
        options = []
        if r['status'] in ('new','review','waiting'):
            options = [('start','배정 설정·선택',self.open_allocation_plans),
                       ('propose','대안 제시',self.propose_alternative),
                       ('wait','요청 대기',self.wait_request), ('reject','거절 · 사유',self.show_rejection)]
            if self.session.current.proposals and self.session.current.proposals[-1]['status'] in ('pending','accepted'):
                options[1] = ('propose','대안 · 고객 답변',lambda: self.open_message(self.session.selected_id))
            elif self.session.current.conditions and (self.session.current.proposals
                    or 'economy' in self.session.current.conditions['allowed_modes']):
                options = [option for option in options if option[0] != 'propose']
            if s.phase != 'accepted':
                options.insert(1, ('accept','요청 수락 · 배정은 나중에',lambda: self._perform(self.session.accept_request)))
        elif s.phase in ('incident','paused'):
            options = [(key, value['label'], lambda k=key: self.respond(k)) for key,value in RESPONSES.items()]
            options += [('delay','고객 지연 안내',lambda: self._perform(self.session.notify_delay)),
                        ('fail','처리 불가 보고',lambda: self._perform(self.session.report_failure))]
            training = self.session.story.training if self.session.story else None
            if training is not None and r['id'] in training.request_ids:
                options.insert(0, ('lab', 'Engineering Lab에서 진단', self.open_engineering_lab))
            elif (s.incident_kind and self.session.story and self.session.story.chapter3 is not None
                    and r['id'] in self.session.story.chapter3.request_ids):
                options.insert(0, ('diagnose','네트워크 진단',self.open_network_diagnosis))
        elif s.phase in ('running','recovering'):
            options = [('delay','고객 지연 안내',lambda: self._perform(self.session.notify_delay))]
            if self.session.hardware_servers(self.session.current) or self.session.current.migration_left:
                options += [('fail','처리 불가 보고',lambda:self._perform(self.session.report_failure))]
            if self.session.story and self.session.story.chapter3b is not None:
                if self.session.hardware_servers(self.session.current):
                    # 장비 장애: 먼저 진단(이전 가능 여부 조회) → 복구 또는 이전 중 직접 선택
                    options.insert(0, ('hwrepair','장비 복구 · 20분',self.repair_faulted_server))
                    options.insert(0, ('hwdiag','장비 진단',self.open_hardware_diagnosis))
                if self.session.chapter3b_card(self.session.selected_id) is not None:
                    options.append(('result3b','장애 결과 보기',lambda rid=self.session.selected_id: self.open_chapter3b_card(rid)))
        elif s.phase == 'finished' and not s.succeeded and not self.session.current.followup_closed:
            options = [('retry','선택 모드로 재처리',lambda: self._perform(lambda: self.session.retry(self.plan_var.get()))),
                       ('delay','고객 지연 안내',lambda: self._perform(self.session.notify_delay)),
                       ('report','처리 불가 · 최종 보고',lambda: self._perform(self.session.report_failure))]
            if self.session.chapter3_card(self.session.selected_id) is not None:
                options.insert(0, ('result3', '장애 결과 보기', lambda rid=self.session.selected_id: self.open_chapter3_card(rid)))
            if self.session.story and self.session.story.chapter3b is not None and self.session.chapter3b_card(self.session.selected_id) is not None:
                options.insert(0, ('result3b', '장애 결과 보기', lambda rid=self.session.selected_id: self.open_chapter3b_card(rid)))
        else:
            options = [('restart','같은 고객의 새 요청',self.new_mission)]
        if self.session.story:
            options = [option for option in options if option[0] != 'restart']
            if self.session.story.step == 'operations' and not self.session.story.tutorial_completed:
                options.append(('operations', '운영 상태 확인', self.show_story_help))
        if not self.session.can_notify_delay(self.session.current):
            options = [option for option in options if option[0] != 'delay']
        if self.session.hardware_servers(self.session.current) and not self.session.current.migration_left:
            options.insert(0, ('migrate','작업 이전 계획',self.open_migration_plans))
        if options:
            self.action_frame.grid()
        else:
            self.action_frame.grid_remove()
        self.action_buttons = {}
        for index,(key,text,command) in enumerate(options):
            if key == 'start':
                b = PrimaryButton(self.action_frame, text, command, strong=True)  # 이 화면의 주요 행동
            else:
                b = ActionButton(self.action_frame, text, command, accent=AMBER if key in ('fail','report','reject') else CYAN)
            b.grid(row=0, column=index, sticky='ew', padx=(0, 6))
            self.action_frame.columnconfigure(index, weight=1, uniform='actions')
            self.action_buttons[key] = b
            if key in RESPONSES and self.session.chapter3_response_locked(self.session.current):
                b.configure(state='disabled')  # 진단창을 열기 전에는 대응을 선택할 수 없습니다.
            if key in RESPONSES and self.session.training_response_locked(self.session.current):
                b.configure(state='disabled')  # 심화 연수: Stage 5 관측·원인 판단 전에는 조치할 수 없습니다(엔진도 검증).
            if key in ('hwrepair', 'migrate') and self.session.chapter3b_locked(self.session.current):
                b.configure(state='disabled')  # 장비 진단을 열기 전에는 복구/이전을 선택할 수 없습니다.
            if key == 'hwrepair' and not any(self.session.servers.hardware[k].state == 'FAULT'
                                             for k in self.session.hardware_servers(self.session.current)):
                b.configure(state='disabled')  # 이미 복구 중

    def _perform(self, action):
        story = self.session.story
        previous_chapter = current_chapter(story).key if story else None
        previous = (story.ui_step, story.tutorial_completed, story.ui_done) if story else None
        anchor = self.story_anchor(story.ui_step) if story else None
        try:
            action()
        except Exception as exc:
            messagebox.showerror('처리 오류', str(exc), parent=self.root)
            return False
        current = self.session.story
        if current and current_chapter(current).key != previous_chapter:
            self.record_chapter_start()
        # 교육 단계가 바뀌면 refresh가 다음 대상을 먼저 강조했다가 곧바로 열리는 피드백 창이 지우는 순간 점멸이 생겼습니다.
        self.highlight_deferred = bool(story and current and (current.ui_step != previous[0] or current.ui_done != previous[2]))
        try:
            self.refresh()
        finally:
            self.highlight_deferred = False
        if story:
            current = self.session.story
            if current.ui_step != previous[0]:
                if self.story_window is not None and self.story_window.winfo_exists():
                    self.story_window.destroy()
                self.queue_story_feedback(previous[0], anchor)
            if current.ui_done and not previous[2]:
                self.show_chapter_complete()
            else:
                self.show_story_event()
            self.update_tutorial_highlight()
        return True

    def select_server(self, key):
        previous = self.resources.selected
        self.resources.select_server(key)
        if self.session.story:
            if not self._perform(lambda:self.session.select_story_server(key)):
                self.resources.select_server(previous)
                self.network.selected = previous
                self.network.redraw()

    def show_story_event(self):
        """실제 세션 작업 뒤에만 호출합니다. refresh/타이머는 대화를 만들지 않습니다."""
        story = self.session.story
        if not story or self.closed or self.transitioning or self.story_ui_busy or story.ui_done:
            return None
        # 고객 요청/계획을 읽는 중에는 해당 창을 닫은 뒤 사건 대화를 보여 줍니다.
        for window in (self.message_window, self.allocation_window):
            if window is not None and window.winfo_exists():
                return None
        if self.story_window is not None and self.story_window.winfo_exists():
            return self.story_window
        if current_chapter(story).key == 1 and chapter_state(self.session)[0] == 'failed':
            return self.show_chapter_failure()
        if self.session.chapter2_failure_pending:
            return self.show_chapter2_failure()
        if story.chapter3b is not None and self.session.chapter3b_pending_feedback() is not None:
            return self.show_chapter3b_feedback()
        if story.chapter3b is None and story.chapter3 is not None and self.session.chapter3_pending_feedback() is not None:
            return self.show_chapter3_feedback()
        if self.pending_feedback is not None:
            token, completed, anchor = self.pending_feedback
            self.pending_feedback = None
            if self.feedback_window is not None and self.feedback_window.winfo_exists():
                self.feedback_window.destroy()
            self.tutorial_highlight.clear()
            try:
                self.feedback_window = self.build_popup(StoryFeedbackDialog, self.root, completed, story.objective, anchor,
                                                        avoid=(self.story_anchor(story.ui_step),))
            except Exception as exc:
                self.pending_feedback = (token, completed, anchor)
                messagebox.showerror('피드백 표시 오류', str(exc), parent=self.root)
                self.update_tutorial_highlight()
                return None
            try:
                if story.step != 'request':
                    self.session.mark_story_dialogue(story.dialogue_event)
            except Exception as exc:
                self.feedback_window.destroy()
                self.pending_feedback = (token, completed, anchor)
                messagebox.showerror('피드백 저장 오류', str(exc), parent=self.root)
                self.update_tutorial_highlight()
                return None
            self.feedback_events.add(token)
            self.feedback_window.bind('<Destroy>', self.feedback_closed, add='+')
            self.update_tutorial_highlight()
            return self.feedback_window
        if self.feedback_window is not None and self.feedback_window.winfo_exists():
            return self.feedback_window
        if story.intro_active:
            if story.ui_step == 'arrival' and story.dialogue_event not in story.dialogue_seen:
                return self.show_story_help()
            self.update_tutorial_highlight()
            return None
        if (story.dialogue_event in ('arrival', 'request', 'closed', 'skipped', 'c2_briefing', 'c3_briefing',
                                     'c3_a_diagnose', 'c3_b_start', 'c3_b_diagnose',
                                     'c3b_briefing', 'c3b_a_diagnose', 'c3b_b_start', 'c3b_b_diagnose', 't_structure')
                and story.dialogue_event not in story.dialogue_seen):
            return self.show_story_help()
        self.update_tutorial_highlight()
        return None

    def show_chapter2_failure(self):
        """Chapter 2 실패가 확정된 순간 선배가 원인과 다음 선택을 알려 줍니다. 같은 실패는 한 번만 표시합니다."""
        story = self.session.story
        if (not story or story.chapter2 is None or not self.session.chapter2_failure_pending
                or self.closed or self.transitioning):
            return None
        self.pending_feedback = None
        for window in (self.feedback_window, self.story_window):
            if window is not None and window.winfo_exists():
                window.destroy()
        self.tutorial_highlight.clear()
        from aidc.ui.chapter_failure import ChapterFailureDialog
        # 확정 실패만 안내합니다. 닫으면 다른 고객의 기존 작업을 계속 확인할 수 있습니다.
        self.story_window = self.build_popup(ChapterFailureDialog, self.root, CHAPTERS[2].heading,
                                             failure_explanation({'failure': story.chapter2.failure}),
                                             self.retry_chapter2, self.return_to_modes,
                                             select_chapter=self.return_to_chapters)
        self.story_window.bind('<Destroy>', self.tutorial_window_closed, add='+')
        try:
            self.session.mark_chapter2_failure_seen()
        except Exception as exc:
            self.story_window.destroy()
            messagebox.showerror('실패 안내 저장 오류', str(exc), parent=self.root)
            return None
        self.update_tutorial_highlight()
        return self.story_window

    def chapter3_card_actions(self, card):
        """카드의 다음 행동 버튼. 시간 진행은 기존 advance_time(10분)을 그대로 사용합니다."""
        actions = []
        if card['can_advance']:
            actions.append(('업무로 돌아가기', self.close_feedback))
            actions.append(('복구 준비 10분 진행', lambda: (self.close_feedback(), self.advance_time(10))))
        elif card['can_retry']:
            actions.append((CHAPTERS[3].label+' 다시 도전', lambda: (self.close_feedback(), self.confirm_retry_chapter3())))
            actions.append(('후속 처리로 돌아가기', self.close_feedback))
        else:
            actions.append(('업무로 돌아가기', self.close_feedback))
        return actions

    def close_feedback(self):
        if self.feedback_window is not None and self.feedback_window.winfo_exists():
            self.feedback_window.destroy()

    def open_chapter3_card(self, rid):
        """장애 결과 카드를 엽니다(조회 전용). 확인 기록은 남기지 않으므로 닫았다가 다시 열 수 있습니다."""
        card = self.session.chapter3_card(rid)
        if card is None or self.closed or self.transitioning:
            return None
        for window in (self.feedback_window, self.story_window):
            if window is not None and window.winfo_exists():
                window.destroy()
        self.tutorial_highlight.clear()
        self.feedback_window = self.build_popup(Chapter3FeedbackDialog, self.root, card, self.chapter3_card_actions(card))
        self.feedback_window.bind('<Destroy>', self.feedback_closed, add='+')
        return self.feedback_window

    def show_chapter3_feedback(self):
        """실제 대응/결과가 기록된 뒤에만 짧은 결과 카드를 보여 줍니다. 같은 사건은 한 번만 표시합니다."""
        story = self.session.story
        pending = self.session.chapter3_pending_feedback() if story and story.chapter3 is not None else None
        if pending is None or self.closed or self.transitioning:
            return None
        key = pending[0]
        self.pending_feedback = None
        window = self.open_chapter3_card(int(key.split(':')[0]))
        if window is None:
            return None
        try:
            self.session.mark_chapter3_feedback_seen(key)
        except Exception as exc:
            window.destroy()
            messagebox.showerror('피드백 저장 오류', str(exc), parent=self.root)
            return None
        self.update_tutorial_highlight()
        return window

    def story_work_window_closed(self, event):
        if self.closed or self.transitioning:
            return
        if event.widget is self.message_window:
            self.message_window = None
        elif event.widget is self.allocation_window:
            self.allocation_window = None
        else:
            return
        self.cancel_story_event()
        self.story_event_timer = self.root.after_idle(self.resume_story_event)

    def resume_story_event(self):
        self.story_event_timer = None
        if not self.closed and not self.transitioning:
            self.show_story_event()
            self.update_tutorial_highlight()

    def cancel_story_event(self, event=None):
        if event is not None and event.widget is not self.root:
            return
        if event is not None:
            self.tutorial_highlight.stop()
        if self.story_event_timer is not None:
            self.root.after_cancel(self.story_event_timer)
            self.story_event_timer = None

    def show_story_help(self):
        story = self.session.story
        if not story:
            return None
        if current_chapter(story).key == 1 and chapter_state(self.session)[0] == 'failed':
            return self.show_chapter_failure()
        if self.feedback_window is not None and self.feedback_window.winfo_exists():
            self.feedback_window.destroy()
        if self.story_window is not None and self.story_window.winfo_exists():
            self.story_window.destroy()
        self.tutorial_highlight.clear()
        confirms = {'arrival':('첫 업무 시작', lambda:self.confirm_story_step(self.session.confirm_story_arrival)),
                    'resources':('자원 정보 확인', self.confirm_story_resources),
                    'operations':('운영 상태 확인', lambda:self.confirm_story_step(self.session.confirm_story_operations)),
                    'c2_briefing':('브리핑 확인', lambda:self.confirm_story_step(self.session.confirm_chapter2_briefing)),
                    'c3_briefing':('브리핑 확인', lambda:self.confirm_story_step(self.session.confirm_chapter3_briefing)),
                    'c3b_briefing':('브리핑 확인', lambda:self.confirm_story_step(self.session.confirm_chapter3b_briefing))}
        confirm = confirms.get(story.ui_step) if not story.ui_done and not story.skipped else None
        pages = [line.page() for line in story.dialogue]
        if not story.intro_active and story.ui_step in ('arrival', 'c2_briefing', 'c3_briefing', 'c3b_briefing', 't_structure') and pages:
            speaker, text = pages[0]
            pages[0] = speaker, current_chapter(story).intro+'\n\n'+text
        if not story.intro_active and story.step == 'operations' and not story.chapter_completed:
            run = self.session.runs[story.request_id]
            remaining = '\n'.join(f'Server {v["spec"].key}: GPU {v["gpu_available"]} · 전력 {v["power_available"]}'
                                  for v in server_views(self.session))
            info = (f'예상 완료: {game_time(self.session.minute+run.state.remaining_minutes)}\n'
                    + self.session.deadline_summary(run) + '\n\n서버별 잔여 자원\n' + remaining)
            pages.append(Dialogue('system', info).page())
        if story.chapter2_active:
            # Chapter 2: 두 고객의 조건을 현재 엔진 값으로 나란히 보여 줍니다. 정답이나 권장 순서는 없습니다.
            comparison = self.session.chapter2_comparison_lines()
            if comparison:
                pages.append(Dialogue('system', '\n'.join(comparison)).page())
        self.story_window = self.build_popup(StoryDialogueDialog, self.root, pages, confirm=confirm,
                                             chapter_label=heading(self.session))
        self.story_window.bind('<Destroy>', self.tutorial_window_closed, add='+')
        try:
            self.session.mark_story_dialogue(story.dialogue_event)
        except Exception as exc:
            self.story_window.destroy()
            messagebox.showerror('대화 저장 오류', str(exc), parent=self.root)
            return None
        self.update_tutorial_highlight()
        return self.story_window

    def confirm_story_step(self, action):
        if self._perform(action):
            return True
        return False

    def on_story_preview(self, _=None):
        if self.closed or self.transitioning:
            return
        story = self.session.story
        # 탭 이동은 검토가 아닙니다. 배정 검토는 비교 창에서 계획을 직접 고를 때만 확인합니다.
        self.update_tutorial_highlight()

    def show_story_review(self):
        self.tutorial_highlight.clear()
        window = StoryReviewDialog(self.root)
        self.story_reviews.add(window)
        window.bind('<Destroy>', self.tutorial_window_closed, add='+')
        return window

    def show_story_status(self):
        story = self.session.story
        state, reason = chapter_state(self.session)
        lines = [heading(self.session), STATE_LABELS[state]+' · '+reason,
                 current_chapter(story).intro,
                 '튜토리얼·연습은 본편 진급 기록과 별개입니다.' if self.session.mode == 'tutorial' or story.practice
                 else '각 장 시작 체크포인트는 재도전 시 새 슬롯으로 복원합니다.']
        for key, field in ((1, 'chapter_completed'), (2, 'chapter2'), (3, 'chapter3'), ('3b', 'chapter3b'), ('lab', 'training')):
            progress = getattr(story, field)
            if key == 1:
                note = '클리어' if story.chapter1_cleared else '미완료'
            elif progress is None:
                available = (self.session.mode == 'story' and (
                    (key == 2 and story.chapter1_cleared) or
                    (key == 3 and not self.session.chapter3_unlock_reason()) or
                    (key == '3b' and not self.session.chapter3b_unlock_reason()) or
                    (key == 'lab' and not self.session.training_unlock_reason())))
                note = '시작 가능' if available else '아직 시작하지 않음'
            else:
                done = progress.done if key == 'lab' else progress.completed
                note = '종료 · 결과 확인' if done else '진행 중'
            lines.append(CHAPTERS[key].heading+' · '+note)
        if story.training is not None:
            lines.append('\nLab 학습 과제 1~5 (Stage)는 본편의 장 번호와 별개입니다.')
            lines.extend(f'학습 과제 {item["no"]} · {item["short"]} — {item["badge_text"]}'
                         for item in self.session.training_status()['stages'])
        return TextDialog(self.root, '진행 현황', '\n\n'.join(lines))

    def show_chapter_failure(self):
        from aidc.ui.chapter_failure import ChapterFailureDialog
        if self.chapter_window is not None and self.chapter_window.winfo_exists():
            self.chapter_window.lift()
            return self.chapter_window
        self.chapter_window = ChapterFailureDialog(
            self.root, heading(self.session), failure_explanation(run=self.session.runs[
                self.session.story.onboarding.rid if self.session.story.intro_active else self.session.story.request_id]),
            self.retry_current_chapter, self.return_to_modes, select_chapter=self.return_to_chapters,
            retry_label='튜토리얼 다시 도전' if self.session.mode == 'tutorial' else '체크포인트부터 다시 도전')
        return self.chapter_window

    def record_chapter_start(self):
        try:
            capture(self.session)
        except Exception as exc:
            messagebox.showerror('체크포인트 저장 오류',
                                 '장은 시작되었지만 재도전용 복사본을 만들지 못했습니다. 현재 저장은 유지됩니다.\n'+str(exc), parent=self.root)

    def show_chapter_complete(self):
        self.pending_feedback = None
        if self.feedback_window is not None and self.feedback_window.winfo_exists():
            self.feedback_window.destroy()
        if self.chapter_window is not None and self.chapter_window.winfo_exists():
            self.chapter_window.lift()
            return self.chapter_window
        if self.story_window is not None and self.story_window.winfo_exists():
            self.story_window.destroy()
        if self.session.story.training is not None:
            self.chapter_window = TrainingResultDialog(self.root, self.session.training_result(), self.return_to_modes,
                                                       self.open_engineering_lab)
        elif self.session.story.chapter3b is not None:
            self.chapter_window = Chapter3CompleteDialog(
                self.root, self.session.chapter3b_result(), self.return_to_modes,
                lambda:self.return_to_modes('free'), self.show_story_status, self.show_story_review,
                retry=self.retry_chapter3b,
                start_next=self.begin_training if not self.session.training_unlock_reason() else None,
                next_label=CHAPTERS['lab'].heading+' · 시작', select_chapter=self.return_to_chapters)
        elif self.session.story.chapter3 is not None:
            self.chapter_window = Chapter3CompleteDialog(
                self.root, self.session.chapter3_result(), self.return_to_modes,
                lambda:self.return_to_modes('free'), self.show_story_status, self.show_story_review,
                retry=self.retry_chapter3,
                start_next=self.begin_chapter3b if not self.session.chapter3b_unlock_reason() else None,
                next_label=CHAPTERS['3b'].heading+' · 시작', select_chapter=self.return_to_chapters)
        elif self.session.story.chapter2 is not None:
            self.chapter_window = Chapter2CompleteDialog(
                self.root, self.session.chapter2_result(), self.return_to_modes,
                lambda:self.return_to_modes('free'), self.show_story_status, self.show_story_review,
                retry=self.retry_chapter2,
                start_chapter3=self.begin_chapter3 if not self.session.chapter3_unlock_reason() else None,
                select_chapter=self.return_to_chapters)
        else:
            self.chapter_window = ChapterCompleteDialog(
                self.root, self.session.chapter_result(), self.return_to_modes,
                lambda:self.return_to_modes('free'), self.show_story_status, self.show_story_review,
                start_chapter2=self.begin_chapter2 if self.session.mode != 'tutorial' else None,
                tutorial=self.session.mode == 'tutorial', retry=self.retry_current_chapter,
                select_chapter=self.return_to_chapters if self.session.mode == 'story' else None)
        self.chapter_window.title(heading(self.session)+' · 결과')
        return self.chapter_window

    def confirm_retry_chapter2(self):
        """플레이어가 직접 선택했을 때만 재도전합니다. 현재 슬롯과 진행 중인 작업은 그대로 저장됩니다."""
        if messagebox.askyesno('이번 시도 종료 · 재도전',
                               '지금 진행은 현재 슬롯에 그대로 저장하고, 새 슬롯에서 이 장을 다시 시작할까요?',
                               parent=self.root):
            return self.retry_chapter2()
        return False

    def retry_chapter2(self):
        """현재 슬롯과 기록은 그대로 저장하고, 새 독립 슬롯에서 Chapter 2를 처음부터 시작합니다."""
        return self.retry_current_chapter('chapter2')

    # ---- Chapter 3b: 서버 장비 장애 ----
    def open_hardware_diagnosis(self):
        """장비 진단창을 실제로 여는 행동만 진단(이전 가능 여부 조회) 확인으로 기록합니다."""
        rid, box = self.session.selected_id, []
        if not self._perform(lambda: box.append(self.session.view_hardware_diagnosis(rid))):
            return None
        if self.diagnosis_window is not None and self.diagnosis_window.winfo_exists():
            self.diagnosis_window.destroy()
        self.diagnosis_window = self.build_popup(HardwareDiagnosisDialog, self.root, box[0])
        return self.diagnosis_window

    def repair_faulted_server(self):
        """장애가 난 서버의 장비 복구를 시작합니다(시간은 흐르지 않고, 시간 빨리감기로 20분이 진행됩니다)."""
        servers = self.session.hardware_servers(self.session.current)
        faulted = [key for key in servers if self.session.servers.hardware[key].state == 'FAULT']
        if not faulted:
            return False
        return self._perform(lambda: self.session.begin_server_repair(faulted[0]))

    def chapter3b_card_actions(self, card):
        if card['can_retry']:
            return [(CHAPTERS['3b'].label+' 다시 도전', lambda: (self.close_feedback(), self.confirm_retry_chapter3b())),
                    ('후속 처리로 돌아가기', self.close_feedback)]
        return [('업무로 돌아가기', self.close_feedback)]

    def open_chapter3b_card(self, rid):
        card = self.session.chapter3b_card(rid)
        if card is None or self.closed or self.transitioning:
            return None
        for window in (self.feedback_window, self.story_window):
            if window is not None and window.winfo_exists():
                window.destroy()
        self.tutorial_highlight.clear()
        self.feedback_window = self.build_popup(Chapter3FeedbackDialog, self.root, card, self.chapter3b_card_actions(card))
        self.feedback_window.bind('<Destroy>', self.feedback_closed, add='+')
        return self.feedback_window

    def show_chapter3b_feedback(self):
        key = self.session.chapter3b_pending_feedback()
        if key is None or self.closed or self.transitioning:
            return None
        self.pending_feedback = None
        window = self.open_chapter3b_card(int(key.split(':')[0]))
        if window is None:
            return None
        try:
            self.session.mark_chapter3b_feedback_seen(key)
        except Exception as exc:
            window.destroy()
            messagebox.showerror('피드백 저장 오류', str(exc), parent=self.root)
            return None
        self.update_tutorial_highlight()
        return window

    def confirm_retry_chapter3b(self):
        if messagebox.askyesno(CHAPTERS['3b'].label+' 다시 도전',
                               '지금 진행은 현재 슬롯에 그대로 저장하고, 새 슬롯에서 이 장을 다시 시작할까요?',
                               parent=self.root):
            return self.retry_chapter3b()
        return False

    def retry_chapter3b(self):
        return self.retry_current_chapter('chapter3b')

    def begin_training(self):
        """Chapter 3b 성공 결과에서 호출합니다. 기존 Chapter 기록은 그대로 두고 연수용 사건 요청만 접수합니다."""
        if self.closed or self.transitioning:
            return False
        old = self.chapter_window
        if not self._perform(self.session.start_training):
            return False
        if old is not None and old.winfo_exists():
            old.destroy()
        self.chapter_window = None
        self.refresh()
        return True

    def restart_training_incident(self):
        if not messagebox.askyesno('연수 사건 다시 받기', '같은 교육 조건의 새 연수 사건을 접수할까요? 통과한 Stage와 지난 기록은 유지됩니다.',
                                   parent=self.root):
            return False
        return self._perform(self.session.restart_training_incident)

    def lab_changed(self):
        """Lab의 학습 행동 뒤 관제실 목표·버튼을 다시 계산합니다. 연수를 모두 마치면 Lab이 on_result로 결과 화면을 엽니다."""
        if self.closed or self.transitioning:
            return
        self.refresh()

    def show_training_result(self):
        if self.session.story and self.session.story.training is not None and self.session.story.training.done:
            return self.show_chapter_complete()
        return None

    def begin_chapter3b(self):
        """Chapter 3a 성공 결과 화면에서 호출합니다. 3a 기록은 그대로 두고 첫 장비 장애 미션 요청만 접수합니다."""
        if self.closed or self.transitioning:
            return False
        old = self.chapter_window
        if not self._perform(self.session.start_chapter3b):
            return False
        if old is not None and old.winfo_exists():
            old.destroy()
        self.chapter_window = None
        self.refresh()
        return True

    def confirm_retry_chapter3(self):
        """플레이어가 직접 선택했을 때만 재도전합니다. 현재 슬롯과 기록은 그대로 저장되고 새 슬롯에서 시작합니다."""
        if messagebox.askyesno(CHAPTERS[3].label+' 다시 도전',
                               '지금 진행은 현재 슬롯에 그대로 저장하고, 새 슬롯에서 이 장을 다시 시작할까요?',
                               parent=self.root):
            return self.retry_chapter3()
        return False

    def retry_chapter3(self):
        return self.retry_current_chapter('chapter3')

    def retry_current_chapter(self, fallback=None):
        story = self.session.story
        chapter = current_chapter(story)
        if self.session.mode == 'tutorial':
            return self.return_to_modes('tutorial')
        if story.practice:
            return self.return_to_modes(fallback or 'lab')
        if self.db.path is None or not checkpoint_path(self.db.path, chapter.key).is_file():
            messagebox.showinfo('장 시작 기록 없음',
                                '이전 버전 슬롯에는 장 시작 체크포인트가 없습니다. 현재 기록은 보존됩니다.\n'
                                '메인 메뉴의 스토리 도전에서 새로 시작하거나 다른 장 기록을 선택해 주세요.', parent=self.root)
            return False
        try:
            self.session.save()
            path = restore(self.story_slots, self.db.path, chapter.key)
        except Exception as exc:
            messagebox.showerror('재도전 준비 오류', str(exc), parent=self.root)
            return False
        if not self.return_to_modes():
            return False
        return self.mode_selector.start('story', path=path, resume=True, checkpoint_start=True)

    def begin_chapter3(self):
        """Chapter 2 성공 결과 화면에서 호출합니다. Chapter 2 기록은 그대로 두고 첫 장애 미션 요청만 접수합니다."""
        if self.closed or self.transitioning:
            return False
        old = self.chapter_window
        if not self._perform(self.session.start_chapter3):
            return False
        if old is not None and old.winfo_exists():
            old.destroy()
        self.chapter_window = None
        self.refresh()
        return True

    def begin_chapter2(self):
        """Chapter 1 완료 화면에서 호출합니다. 기존 완료 기록은 그대로 두고 일본·미국 요청만 접수합니다."""
        if self.closed or self.transitioning:
            return False
        old = self.chapter_window
        if not self._perform(self.session.start_chapter2):
            return False
        if old is not None and old.winfo_exists():
            old.destroy()
        self.chapter_window = None
        self.refresh()
        return True

    def return_to_modes(self, mode=None):
        if self.closed or self.transitioning:
            return False
        self.transitioning = True
        try:
            self.session.close()
        except Exception as exc:
            self.transitioning = False
            messagebox.showerror('저장 오류', f'현재 상태를 저장하지 못해 모드를 전환하지 않았습니다.\n{exc}', parent=self.root)
            return False
        self.closed = True
        self.cancel_story_event()
        self.tutorial_highlight.stop()
        self.root.unbind('<Destroy>', self.story_destroy_binding)
        self.network.stop()
        for widget in self.root.winfo_children():
            widget.destroy()
        self.root.rowconfigure(2, weight=0)
        self.mode_selector = ModeSelection(self.root, db_factory=self.db_factory, story_slots=self.story_slots,
                                           preferred_story=self.db.path if self.session.story else None)
        if mode == 'chapters':
            self.mode_selector.show_chapter_menu()
        elif mode == 'chapter2':
            self.mode_selector.new_story(2)
        elif mode == 'chapter3':
            self.mode_selector.new_story(3)
        elif mode == 'chapter3b':
            self.mode_selector.new_story('3b')
        elif mode == 'tutorial':
            self.mode_selector.new_tutorial()
        elif mode == 'lab':
            self.mode_selector.new_story('lab')
        elif mode is not None:
            self.mode_selector.start(mode)
        return True

    def return_to_chapters(self):
        return self.return_to_modes('chapters')

    def confirm_story_resources(self):
        if (self.resources.selected != 'A'
                or self.resources.book.select() != str(self.resources.inspector_frame)):
            messagebox.showerror('교육 안내', 'Server A를 다시 선택하고 Inspector를 확인해 주세요.', parent=self.root)
            return False
        self.resources.book.select(self.resources.inspector_frame)
        if self._perform(self.session.confirm_story_resources):
            return True
        return False

    def skip_tutorial(self):
        if (not self.session.story or self.session.story.tutorial_completed or self.session.story.chapter2 is not None
                or self.session.story.chapter3 is not None or self.session.story.chapter3b is not None
                or self.session.story.training is not None):
            return False
        if messagebox.askyesno('튜토리얼 건너뛰기',
                               '교육 안내를 건너뛸까요? 고객 업무는 직접 진행하며 스토리 모드는 유지됩니다.', parent=self.root):
            return self._perform(self.session.skip_tutorial)
        return False
    def select_request(self, rid):
        success = self._perform(lambda: self.session.select(rid))
        if success and hasattr(self, 'resources') and not self.state.allocated and not self.session.story:
            self.resources.show_preview()
        return success
    def choose_plan(self, key):
        """프로그램/테스트용 직접 시작. 화면의 시작 흐름은 반드시 [배정 설정·선택] 창을 거칩니다."""
        return self._perform(lambda: self.session.choose_plan(key))
    def update_allocation_status(self):
        """[배정 설정·선택] 옆에 현재 모드와 배정안 설정 여부를 간결하게 보여 줍니다."""
        if not hasattr(self, 'allocation_status') or self.closed:
            return
        run, key = self.session.current, self.plan_var.get()
        if run.state.allocated or run.request['status'] not in ('new', 'review', 'waiting'):
            self.allocation_status.configure(text='')
            return
        choice = self.allocation_choice
        valid = (choice is not None and choice[0] == run.request['id'] and choice[1] == key and choice[3] == self.session.minute)
        plan = '자동 추천' if valid and choice[2] is None else f'배정안 {choice[2]+1}' if valid else None
        self.allocation_status.configure(text=f'선택 모드: {run.state.plans[key]["label"]} · 배정안: '
                                         + (f'{plan} 확인됨 · 설정창에서 시작' if plan else '설정 전'))
    def remember_allocation_choice(self, mode, index):
        self.allocation_choice = (self.session.selected_id, mode, index, self.session.minute)
        self.update_allocation_status()
    def change_allocation_mode(self, mode):
        self.plan_var.set(mode)
        self.preview_plan()
    def open_allocation_plans(self):
        if self.allocation_window is not None and self.allocation_window.winfo_exists():
            self.allocation_window.lift()
            return self.allocation_window
        if self.feedback_window is not None and self.feedback_window.winfo_exists():
            self.feedback_window.destroy()
        self.allocation_window = self.build_popup(AllocationDialog,
            self.root, self.session, self.plan_var.get(),
            lambda mode, parts: self._perform(lambda: self.session.choose_plan(mode, server_plan=parts)),
            on_review=self.review_allocation_plan if self.session.story else None,
            on_reload=self.update_tutorial_highlight if self.session.story else None,
            on_mode=self.change_allocation_mode, on_choice=self.remember_allocation_choice)
        if self.session.story and self.story_window is not None and self.story_window.winfo_exists():
            self.story_window.destroy()
        if self.session.story:
            self.allocation_window.bind('<Destroy>', self.story_work_window_closed, add='+')
        self.update_tutorial_highlight()
        return self.allocation_window
    def review_allocation_plan(self):
        """비교 창에서 계획(추천안 포함)을 직접 고른 행동만 배정 검토로 확인합니다."""
        window = self.allocation_window
        if window is None or not window.winfo_exists() or window.migration:
            return
        rid = window.request_id
        if self.session.selected_id == rid:
            self._perform(lambda:self.session.inspect_story_preview(rid))
            window.paint_cards()

    def open_migration_plans(self):
        if self.allocation_window is not None and self.allocation_window.winfo_exists():
            self.allocation_window.lift()
            return self.allocation_window
        self.allocation_window = AllocationDialog(
            self.root, self.session, self.state.plan,
            lambda mode, parts:self._perform(lambda:self.session.migrate(parts, self.allocation_window.source)),
            migration=True)
        return self.allocation_window
    def propose_alternative(self):
        if self._perform(self.session.propose_alternative):
            return self.open_message(self.session.selected_id)
    def review_alternative(self, rid, proposal_count):
        if self.session.selected_id != rid or len(self.session.current.proposals) != proposal_count:
            messagebox.showerror('고객 협의 오류', '대안을 제시한 요청을 다시 선택해 고객 답변을 확인해 주세요.', parent=self.root)
            return
        if self._perform(self.session.review_alternative):
            if self.session.current.proposals[-1]['status'] == 'accepted':
                self.plan_var.set('economy')
            else:
                self.plan_var.set('performance')
            return self.open_message(rid)
    def respond(self, key):
        done = self._perform(lambda: self.session.respond(key))
        window = getattr(self, 'diagnosis_window', None)
        if done and window is not None and window.winfo_exists():
            window.destroy()  # 대응 전의 진단 값이 남지 않도록 닫고, 다시 열어 비교하게 합니다.
        return done

    def open_network_diagnosis(self):
        """Chapter 3: 진단창을 실제로 여는 행동만 진단 확인으로 기록합니다."""
        rid, box = self.session.selected_id, []
        if not self._perform(lambda: box.append(self.session.view_network_diagnosis(rid))):
            return None
        if self.diagnosis_window is not None and self.diagnosis_window.winfo_exists():
            self.diagnosis_window.destroy()
        # v0.9-4a-2: Lab에서 관찰할 수 있는 장애일 때만 [네트워크 구조 자세히 보기]를 둡니다(미지원 요청에는 버튼 없음).
        target = diagnosis_lab_target(self.session, rid)
        on_open_lab = (lambda r=rid: self.open_lab_network(r)) if target else None
        self.diagnosis_window = self.build_popup(NetworkDiagnosisDialog, self.root, box[0], on_open_lab=on_open_lab)
        return self.diagnosis_window

    def open_lab_network(self, rid):
        """진단창이 닫힌 뒤 Lab의 [네트워크 구조] 탭을 엽니다. 화면 이동만 하며 세션 작업을 실행하지 않습니다.
        Lab 모드(미리보기/연수/연습)와 Stage 권한은 기존 open_engineering_lab()·lab_mode() 그대로입니다."""
        if self.closed or self.transitioning or not self.root.winfo_exists():
            return None
        target = diagnosis_lab_target(self.session, rid)          # 닫는 사이 상황이 바뀌었으면 열지 않습니다.
        if target is None:
            return None
        lab = self.open_engineering_lab(rid)                       # 진단한 요청 그대로(선택 변경·저장 없음)
        if lab is None or not lab.winfo_exists():
            return None
        lab.show_tab(target[1])
        lab.deiconify()
        lab.lift()
        lab.focus_set()
        return lab

    def open_engineering_lab(self, rid=None):
        """v0.9-4a: 조회·학습 전용 Lab을 엽니다. 여는 것만으로 시간·자원·동의·작업 상태를 바꾸지 않습니다.
        rid(v0.9-4a-2, 진단창 이동용)를 주면 그 요청을 열고, 심화 연수 중에는 항상 연수 요청을 엽니다."""
        if self.closed or self.transitioning:
            return None
        training = self.session.story.training if self.session.story else None
        rid = training.rid if training is not None else (self.session.selected_id if rid is None else rid)
        reason = lab_support(self.session, rid)
        if reason:
            messagebox.showinfo('Engineering Lab (Prototype)', reason, parent=self.root)
            return None
        window = self.lab_window
        if window is not None and window.winfo_exists():
            if window.rid == rid and window.winfo_exists():
                window.refresh()
                window.deiconify()
                window.lift()
                return window
            window.destroy()
        self.lab_window = self.build_popup(EngineeringLabDialog, self.root, self.session, rid,
                                           on_change=self.lab_changed, on_result=self.show_training_result)
        return self.lab_window
    def next_request(self):
        return self._perform(self.session.deliver_next_request)
    def open_arrival_message(self):
        if self.arrival_request_id is not None:
            return self.open_message(self.arrival_request_id)
    def wait_request(self):
        return self._perform(self.session.wait_request)
    def new_mission(self):
        return self._perform(self.session.restart)
    def advance_time(self, minutes):
        return self._perform(lambda: self.session.advance_time(minutes))
    def on_inbox_click(self, event):
        rid = self.inbox.identify_row(event.y)
        if rid:
            self.open_message(int(rid))
    def on_active_click(self, event):
        rid = self.active_list.identify_row(event.y)
        if rid:
            self.select_request(int(rid))
    def open_latest_message(self):
        rid = next((rid for rid,r in self.session.runs.items() if not r.request['is_read']), self.session.selected_id)
        return self.open_message(rid)
    def open_selected_message(self):
        selected = self.inbox.selection()
        return self.open_message(int(selected[0]) if selected else self.session.selected_id)
    def open_message(self, rid):
        was_unread = not self.session.runs[rid].request['is_read']
        story = self.session.story
        previous = story.ui_step if story else None
        anchor = self.story_anchor(previous) if story else None
        try:
            steps = self.session.read_conversation(rid)
        except Exception as exc:
            messagebox.showerror('메시지 확인 오류', str(exc), parent=self.root)
            return
        if story and story.ui_step != previous:
            self.queue_story_feedback(previous, anchor)
        self.refresh()
        if self.feedback_window is not None and self.feedback_window.winfo_exists():
            self.feedback_window.destroy()
        if self.message_window is not None and self.message_window.winfo_exists():
            self.message_window.destroy()
        run = self.session.current
        if not run.state.allocated and not self.session.story:
            self.resources.show_preview()
        confirm = None
        if (run.proposals and run.proposals[-1]['status'] == 'pending'
                and run.request['status'] in ('new','review','waiting')):
            confirm = ('고객 답변 확인', lambda count=len(run.proposals): self.review_alternative(rid, count))
        self.message_window = self.build_popup(MessageDialog, self.root, run.mission['company_name'], run.mission['country'], steps,
                                            message_kind='새 메시지' if was_unread else '확인한 메시지 · 현재 상태',
                                            confirm=confirm, summary=request_summary(run),
                                            availability=self.available_for_request())
        if self.session.story:
            if self.story_window is not None and self.story_window.winfo_exists():
                self.story_window.destroy()
            self.message_window.bind('<Destroy>', self.story_work_window_closed, add='+')
        self.update_tutorial_highlight()
        return self.message_window
    def available_for_request(self):
        gpu, power = self.session.servers.available()
        return min(gpu, self.center.available_gpu()), min(power, self.center.available_power())
    def show_conversation_history(self):
        steps = self.session.conversation(self.session.selected_id, history=True)
        return TextDialog(self.root, 'AIDC LINK · 과거 대화 기록', '\n\n'.join(f'{s}\n{t}' for s,t in steps))
    def show_rejection(self):
        rid = self.session.selected_id
        return RejectionDialog(self.root, lambda reason: self._perform(lambda: self.session.reject_request(reason))
                               if self.session.selected_id == rid else False)
    def show_events(self):
        text = '\n\n'.join(self.session.current.messages) or '아직 이벤트가 없습니다.'
        return TextDialog(self.root, '작업 이벤트 / 고객 피드백', text)
    def show_history(self):
        win = tk.Toplevel(self.root, bg=BG)
        win.withdraw()
        win.title('전체 수행 기록 · 더블클릭으로 상세 로그')
        self.history = self.make_list(win, ('id','client','plan','status','score'),
                                      ('수행 ID','고객','모드','결과','점수'), (70,220,140,140,80), 10)
        self.history.pack(fill='both', expand=True, padx=10, pady=10)
        for row in self.session.recent_records():
            active_ids = {r.playthrough_id for r in self.session.runs.values() if r.state.allocated}
            status = '이전 실행 미완료' if row['status']=='진행중' and row['id'] not in active_ids else row['status']
            self.history.insert('', 'end', iid=str(row['id']), values=(row['id'],row['company_name'],row['plan'],status,row['score']))
        for rid,run in self.session.runs.items():
            if run.terms.get('expired'):
                self.history.insert('', 'end', iid=f'request-{rid}',
                                    values=(f'요청 {rid}', run.mission['company_name'], '미배정', '미처리 · 기한 만료', 0))
        self.history.bind('<Double-1>', self.show_record)
        center_dialog(win, self.root, size=(950, 420), minimum=(700, 320))
        return win
    def show_record(self, _=None):
        selected = self.history.selection()
        if selected:
            if selected[0].startswith('request-'):
                rid = int(selected[0].split('-')[1])
                return TextDialog(self.root, f'미처리 요청 #{rid}', '\n\n'.join(self.session.runs[rid].messages))
            return TextDialog(self.root, f'수행 기록 #{selected[0]}', '\n\n'.join(
                f'{r["created_at"]}\n{r["message"]}' for r in self.session.logs(int(selected[0]))))
    def on_close(self):
        if self.closed:
            return
        try:
            self.session.close()
        except Exception as exc:
            messagebox.showerror('저장 오류', f'현재 상태를 저장하지 못해 종료하지 않았습니다.\n{exc}', parent=self.root)
            return
        self.network.stop()
        self.closed = True
        self.root.destroy()


def draw_mode_icon(canvas, kind):
    """모드 카드의 단순한 아이콘(외부 이미지 없이 Canvas 도형으로 그립니다)."""
    if kind == 'play':
        canvas.create_oval(6, 4, 56, 54, outline=CYAN, width=3)
        canvas.create_polygon(25, 17, 25, 41, 44, 29, fill=CYAN, outline=CYAN)
    elif kind == 'book':
        gold = '#ffe08a'
        canvas.create_polygon(6, 12, 30, 18, 30, 52, 6, 46, outline=gold, fill='', width=3)
        canvas.create_polygon(34, 18, 58, 12, 58, 46, 34, 52, outline=gold, fill='', width=3)
        for y in (26, 34, 42):
            canvas.create_line(11, y-4, 25, y, fill=gold, width=2)
            canvas.create_line(39, y, 53, y-4, fill=gold, width=2)
    else:
        for index, led in enumerate((GREEN, CYAN, AMBER)):
            top = 4+index*18
            canvas.create_rectangle(6, top, 58, top+14, outline='#6d9fff', width=2)
            canvas.create_oval(12, top+4, 18, top+10, fill=led, outline='')
            canvas.create_line(26, top+7, 50, top+7, fill='#6d9fff', width=2)


class ModeSelection:
    """중앙 모드 메뉴와 독립 스토리 슬롯 선택. 메뉴에서는 DB를 열지 않습니다."""
    def __init__(self, root, db_factory=Database, story_slots=None, preferred_story=None):
        self.root, self.db_factory, self.app = root, db_factory, None
        self.story_slots = story_slots or StorySlots()
        self.preferred_story = preferred_story
        self.starting = False
        root.protocol('WM_DELETE_WINDOW', root.destroy)
        root.title(f'{APP_NAME} {VERSION} | 모드 선택')
        if root.winfo_width() <= 1:
            root.geometry('1000x650')
        root.minsize(1000, 650)
        root.configure(bg=BG)
        self.frame = tk.Frame(root, bg=BG)
        self.frame.pack(fill='both', expand=True)
        self.content = tk.Frame(self.frame, bg=BG)
        self.content.place(relx=.5, rely=.5, anchor='center', width=1060)
        self.frame.bind('<Configure>', self.layout_content)
        # 게임 타이틀 화면: 큰 로고와 한 줄 소개 → 독립 모드 카드 3장(아이콘·소개·목적·시작 버튼).
        banner = tk.Frame(self.content, bg=BG)
        banner.pack(fill='x', pady=(0, 20))
        icon = tk.Canvas(banner, width=76, height=40, bg=BG, highlightthickness=0)
        icon.pack()
        reset_hardware(icon)
        gpu_module(icon, 6, 6, 64, 27, 'available')
        self.title_label = label(banner, APP_NAME, 38, CYAN, True)
        self.title_label.pack(pady=(6, 0))
        label(banner, f'{APP_NAME_EN} · 울산 AI 데이터센터 운영 시뮬레이션', 13, MUTED).pack(pady=(2, 0))
        tk.Frame(banner, bg=CYAN, height=2, width=140).pack(pady=(12, 0))
        self.menu_body = tk.Frame(self.content, bg=BG)
        self.menu_body.pack(fill='x')
        self.mode_panel = tk.Frame(self.menu_body, bg=BG)
        self.mode_panel.pack(fill='x')
        self.buttons, self.mode_cards = {}, {}
        for column, (mode, kind, title, intro, purpose, command) in enumerate((
            ('tutorial', 'play', '튜토리얼', '관제실 기본 조작을 따라 해 보세요.',
             '요청 확인부터 작업 완료까지, 고객 요청 한 건을 처음부터 끝까지 익힙니다.', self.show_tutorial_menu),
            ('story', 'book', '스토리 도전', '신입 엔지니어가 되어 서버실에서 살아남으세요.',
             '제1장~제5장을 순서대로 진행합니다. 실제 업무와 학습으로 다음 장이 열립니다.', self.show_story_menu),
            ('practice', 'rack', '자유·연습', '내 방식대로 운영하거나 장별로 연습하세요.',
             '자유 운영, 장별 연습, Engineering Lab. 본편 진급 기록과는 별도입니다.', self.show_practice_menu))):
            self.mode_panel.columnconfigure(column, weight=1, uniform='modecards')
            card = self.mode_cards[mode] = tk.Frame(self.mode_panel, bg=PANEL, highlightthickness=2,
                                                    highlightbackground=BORDER, padx=20, pady=18, cursor='hand2')
            card.grid(row=0, column=column, sticky='nsew', padx=(0 if column == 0 else 8, 0))
            art = tk.Canvas(card, width=72, height=60, bg=PANEL, highlightthickness=0)
            art.pack(anchor='w')
            draw_mode_icon(art, kind)
            heading_label = label(card, title, 20, TEXT, True)
            heading_label.pack(anchor='w', pady=(8, 2))
            intro_label = label(card, intro, 12, CYAN, wraplength=260, justify='left')
            intro_label.pack(anchor='w', fill='x')
            purpose_label = label(card, '목적 · '+purpose, 10, MUTED, wraplength=260, justify='left')
            purpose_label.pack(anchor='w', fill='x', pady=(8, 14))
            self.buttons[mode] = PrimaryButton(card, '시작 / 이어하기  ▶', command, strong=True)
            self.buttons[mode].pack(side='bottom', fill='x')
            card.bind('<Configure>', lambda e, a=intro_label, b=purpose_label: [w.configure(wraplength=max(180, e.width-48)) for w in (a, b)])
            for widget in (card, art, heading_label, intro_label, purpose_label):
                widget.bind('<Button-1>', lambda _, c=command: c())
            for widget in (card, art, heading_label, intro_label, purpose_label, self.buttons[mode]):
                widget.bind('<Enter>', lambda _, c=card: c.configure(highlightbackground=CYAN), add='+')
                widget.bind('<Leave>', lambda _, c=card: c.configure(highlightbackground=BORDER), add='+')
        self.panels, self.choices, self.menu_buttons, self.previews = {}, {}, {}, {}
        for category, title in (('story', '스토리 도전'), ('tutorial', '튜토리얼'), ('practice', '자유·연습')):
            panel = tk.Frame(self.menu_body, bg=PANEL, padx=22, pady=14)
            self.panels[category] = panel
            label(panel, title, 16, CYAN, True).pack(anchor='w', pady=(0, 8))
            buttons = self.menu_buttons[category] = {}
            if category == 'story':
                text = CHAPTERS[1].heading+'\n'+CHAPTERS[1].intro
                label(panel, text, 11, TEXT, wraplength=730, justify='left').pack(anchor='w', pady=(0, 10))
                buttons['new'] = ActionButton(panel, '새 도전 시작 · '+CHAPTERS[1].heading, self.new_story)
                buttons['new'].pack(fill='x')
                buttons['chapters'] = ActionButton(panel, '장 선택 · 저장된 시작 지점', self.show_chapter_menu)
                buttons['chapters'].pack(fill='x', pady=(6, 0))
            elif category == 'tutorial':
                label(panel, '선배와 기본 조작을 익힙니다. 실패해도 새 튜토리얼에서 반복할 수 있습니다.',
                      11, MUTED, wraplength=720, justify='left').pack(anchor='w', pady=(0, 10))
                buttons['new'] = ActionButton(panel, '튜토리얼 처음부터 · 별도 슬롯', self.new_tutorial)
                buttons['new'].pack(fill='x')
            else:
                buttons['free'] = ActionButton(panel, '자유 운영 · 기존 기록 이어하기', lambda:self.start('free'))
                buttons['free'].pack(fill='x', pady=(0, 8))
                for key, chapter in (('chapter2', 2), ('chapter3', 3), ('chapter3b', '3b'), ('lab', 'lab')):
                    text = 'Engineering Lab · 학습 과제 1~5 연습' if chapter == 'lab' else CHAPTERS[chapter].heading+' · 연습'
                    buttons[key] = ActionButton(panel, text, lambda c=chapter:self.new_story(c))
                    buttons[key].pack(fill='x', pady=2)
                label(panel, '기존 연습 공개 정책을 유지합니다. 본편의 클리어·진급으로 기록되지 않습니다.',
                      10, MUTED).pack(anchor='w', pady=5)
            choice = self.choices[category] = ttk.Combobox(panel, state='readonly', font=(FONT, 10))
            choice.pack(fill='x', pady=(12, 6))
            preview = self.previews[category] = label(panel, '', 10, MUTED, wraplength=730, justify='left')
            preview.pack(anchor='w', pady=(0, 6))
            choice.bind('<<ComboboxSelected>>', lambda e, c=category:self.preview_slot(c))
            buttons['continue'] = ActionButton(panel, '선택한 기록 이어하기', lambda c=category:self.continue_selected(c))
            buttons['continue'].pack(fill='x')
            buttons['back'] = ActionButton(panel, '돌아가기', self.show_modes)
            buttons['back'].pack(anchor='w', pady=(10, 0))
        self.story_panel = self.panels['story']
        self.story_buttons = self.menu_buttons['story']
        self.practice_buttons = self.menu_buttons['practice']
        self.tutorial_buttons = self.menu_buttons['tutorial']
        self.slot_choice = self.choices['story']
        self.paths_by_mode = {}
        self.version_label = label(self.content, f'{APP_NAME_EN} {VERSION} · 제1장~제5장 / Lab 학습 과제 1~5 (프로토타입)', 10, MUTED)
        self.version_label.pack(anchor='w', pady=(12, 0))

    def layout_content(self, event):
        self.content.place_configure(width=min(1060, max(600, event.width-80)))

    def show_menu(self, category):
        if self.starting or self.app is not None:
            return
        if getattr(self, 'chapter_panel', None) is not None:
            self.chapter_panel.pack_forget()
        paths = self.paths_by_mode[category] = self.story_slots.for_mode(category)
        choice = self.choices[category]
        choice.configure(values=[self.story_slots.title(p)+self.story_slots.describe(p) for p in paths])
        if paths:
            index = paths.index(self.preferred_story) if self.preferred_story in paths else len(paths)-1
            choice.current(index)
        else:
            choice.set('저장된 기록이 없습니다.')
        self.menu_buttons[category]['continue'].configure(state='normal' if paths else 'disabled')
        self.mode_panel.pack_forget()
        for panel in self.panels.values():
            panel.pack_forget()
        self.panels[category].pack(fill='x', padx=130)  # 카드 화면보다 좁게 가운데 모아 보여 줍니다.
        self.preview_slot(category)
        if category == 'story':
            self.slot_paths = paths

    def preview_slot(self, category):
        paths = self.paths_by_mode.get(category, [])
        index = self.choices[category].current()
        text = ''
        if 0 <= index < len(paths):
            payload = self.story_slots.payload(paths[index])
            data = payload.get('story', {})
            if isinstance(data, dict) and data:
                chapter = chapter_from_payload(data)
                text = ('튜토리얼' if category == 'tutorial' else chapter.heading)+' · 저장 지점에서 이어하기'
                text += '\n'+chapter.intro
        self.previews[category].configure(text=text)

    def show_story_menu(self):
        self.show_menu('story')

    def show_chapter_menu(self):
        if self.starting or self.app is not None:
            return
        self.mode_panel.pack_forget()
        for panel in self.panels.values():
            panel.pack_forget()
        if getattr(self, 'chapter_panel', None) is not None:
            self.chapter_panel.destroy()
        panel = self.chapter_panel = tk.Frame(self.menu_body, bg=PANEL, padx=22, pady=14)
        panel.pack(fill='x', padx=130)
        label(panel, '장 선택', 18, CYAN, True).pack(anchor='w')
        label(panel, '보존된 장 시작 지점에서 새 슬롯으로 도전합니다.', 11, MUTED).pack(anchor='w', pady=(4, 10))
        paths = self.story_slots.for_mode('story')
        choice = ttk.Combobox(panel, state='readonly', font=(FONT, 11),
                              values=[self.story_slots.title(p) for p in paths])
        choice.pack(fill='x')
        if paths:
            choice.current(paths.index(self.preferred_story) if self.preferred_story in paths else len(paths)-1)
        else:
            choice.set('저장된 정규 도전이 없습니다.')
        rows = tk.Frame(panel, bg=PANEL)
        rows.pack(fill='x', pady=10)
        def render(_=None):
            for widget in rows.winfo_children():
                widget.destroy()
            if not paths:
                label(rows, '스토리 도전에서 제1장을 새로 시작해 주세요.', 11, MUTED).pack(anchor='w')
                return
            source = paths[choice.current()]
            found = False
            for chapter in CHAPTERS.values():
                if checkpoint_path(source, chapter.key).is_file():
                    found = True
                    ActionButton(rows, chapter.heading+' · 시작 지점부터',
                                 lambda c=chapter.key, p=source: self.start_checkpoint(p, c)).pack(fill='x', pady=3)
            if not found:
                label(rows, '이 기록에는 보존된 장 시작 지점이 없습니다.\n기존 진행은 스토리 도전의 이어하기에서 확인할 수 있습니다.',
                      11, MUTED, justify='left', wraplength=680).pack(anchor='w')
        choice.bind('<<ComboboxSelected>>', render)
        render()
        ActionButton(panel, '메인 메뉴', self.show_modes).pack(anchor='w', pady=(4, 0))

    def start_checkpoint(self, source, chapter):
        if self.starting or self.app is not None:
            return
        try:
            target = restore(self.story_slots, source, chapter)
        except Exception as exc:
            messagebox.showerror('재도전 준비 오류', str(exc), parent=self.root)
            return
        return self.start('story', path=target, resume=True, checkpoint_start=True)

    def show_practice_menu(self):
        self.show_menu('practice')

    def show_tutorial_menu(self):
        self.show_menu('tutorial')

    def show_modes(self):
        if getattr(self, 'chapter_panel', None) is not None:
            self.chapter_panel.pack_forget()
        if not self.starting:
            for panel in self.panels.values():
                panel.pack_forget()
            self.mode_panel.pack(fill='x')

    def new_tutorial(self):
        if self.app is not None or self.starting:
            return self.app
        try:
            path = self.story_slots.reserve_new()
        except Exception as exc:
            messagebox.showerror('튜토리얼 시작 오류', str(exc), parent=self.root)
            return None
        return self.start('tutorial', path=path, fresh=True)

    def continue_selected(self, category):
        paths = self.paths_by_mode.get(category, [])
        index = self.choices[category].current()
        if index < 0 or index >= len(paths):
            return None
        return self.start('tutorial' if category == 'tutorial' else 'story', path=paths[index], resume=True)

    def new_story(self, chapter=1):
        if self.app is not None or self.starting:
            return self.app
        try:
            path = self.story_slots.reserve_new()
        except Exception as exc:
            messagebox.showerror('새 스토리 시작 오류', str(exc), parent=self.root)
            return None
        return self.start('story', path=path, fresh=True, chapter=chapter)

    def start(self, mode, path=None, fresh=False, resume=False, chapter=1, checkpoint_start=False):
        # 직접 start('story')를 쓰는 기존 호출은 기존 스토리 파일을 이어갑니다.
        if self.app is not None or self.starting:
            return self.app
        if mode not in ('free', 'story', 'tutorial'):
            raise ValueError('존재하지 않는 게임 모드입니다.')
        db = None
        self.starting = True
        before = set(self.root.winfo_children())
        try:
            target = path if path is not None else (self.story_slots.reserve_new() if mode == 'tutorial' else
                     self.story_slots.legacy_path if mode == 'story' else DB_PATH)
            if resume and not target.is_file():
                raise ValueError('선택한 저장 파일을 찾을 수 없습니다. 새 스토리 시작을 이용해 주세요.')
            db = self.db_factory(target)
            if fresh and (db.get_simulation() or db.get_requests()):
                raise ValueError('새 스토리에 기존 기록을 사용할 수 없습니다.')
            if resume and not db.get_simulation():
                raise ValueError('이 슬롯에는 이어갈 진행 기록이 없습니다. 새 스토리 시작을 이용해 주세요.')
            self.frame.pack_forget()
            options = {'start_chapter': chapter} if chapter in (2, 3, '3b', 'lab') else {}
            if fresh and chapter == 1:
                options['intro_flow'] = True
            self.app = SimulatorApp(self.root, db=db, db_factory=self.db_factory,
                                    story_slots=self.story_slots, checkpoint_start=fresh or checkpoint_start, mode=mode, **options)
        except Exception as exc:
            if db is not None and not db._game_claimed:
                db.close()
            for widget in set(self.root.winfo_children()) - before:
                widget.destroy()
            self.root.rowconfigure(2, weight=0)
            self.frame.pack(fill='both', expand=True)
            self.root.protocol('WM_DELETE_WINDOW', self.root.destroy)
            messagebox.showerror('게임 시작 오류', str(exc), parent=self.root)
            return None
        finally:
            self.starting = False
        self.frame.destroy()
        return self.app


def main():
    root = tk.Tk()
    ModeSelection(root)
    root.mainloop()


if __name__ == '__main__':
    main()
