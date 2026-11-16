"""실제 완료 결과와 다음 행동을 보여 주는 Chapter 1·2 결과창.

v0.9-2b 원칙: 결과는 요약표로 먼저, 설명은 아래에, 고객 반응은 실제 결과에 맞게.
표시 값은 모두 session.chapter_result()/chapter2_result()가 실제 기록에서 계산한 것이며 이 창은 읽기 전용입니다.
"""
import tkinter as tk

from tkinter.scrolledtext import ScrolledText

from story import chapter2_failure_pages
from ui import BG, PANEL, CYAN, MUTED, TEXT, FONT, RED, GREEN, ActionButton, label
from story_portraits import draw_portrait
from aidc.ui.scroll_area import ScrollArea
from aidc.ui.window_placement import center_dialog
from aidc.story.chapters import CHAPTERS
from aidc.ui.result_presentation import (complete_actions, failure_explanation, result_actions, success_headline,
                                         success_mentor_lines, success_tiles)
from aidc.ui.result_widgets import button_bar, failure_card, failure_heading, tile_row, tone_card


def _mentor_box(parent, title, lines):
    """선배 초상화와 짧은 분석 문장을 PANEL 박스로 묶어 반환합니다."""
    box = tk.Frame(parent, bg=PANEL)
    box.columnconfigure(1, weight=1)
    portrait = tk.Canvas(box, width=44, height=60, bd=0, highlightthickness=0)
    portrait.grid(row=0, column=0, sticky='n', padx=8, pady=6)
    draw_portrait(portrait, 'mentor')
    portrait.scale('all', 0, 0, .37, .37)
    text = label(box, title+'\n'+'\n'.join('· '+line for line in lines), 10, TEXT, justify='left', anchor='w', wraplength=640)
    text.grid(row=0, column=1, sticky='w', padx=6, pady=6)
    box.bind('<Configure>', lambda e: text.configure(wraplength=max(300, e.width-90)))
    return box, portrait, text


class ChapterCompleteDialog(tk.Toplevel):
    """튜토리얼/제1장 성공 결과. 큰 제목 → 성과 타일 → 선배 한마디 카드 → 다음 행동 순서로 한 화면에 보여 줍니다."""
    def __init__(self, parent, result, select_mode, start_free, status, review, start_chapter2=None, tutorial=False, retry=None, select_chapter=None):
        super().__init__(parent, bg=BG)
        name = '튜토리얼 — 관제실 첫걸음' if tutorial else CHAPTERS[1].heading
        self.title(name+' · 클리어')
        self.withdraw()
        self.transient(parent)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self.result = result
        top = tk.Frame(self, bg=BG)
        top.grid(row=0, sticky='ew', padx=28, pady=(18, 6))
        top.columnconfigure(0, weight=1)
        label(top, name, 10, MUTED).grid(row=0, sticky='w')
        self.verdict = label(top, 'MISSION SUCCESS', 28, GREEN, True)
        self.verdict.grid(row=1, sticky='w')
        self.congratulations = label(top, success_headline(result, tutorial), 13, TEXT, justify='left', wraplength=700)
        self.congratulations.grid(row=2, sticky='w', pady=(2, 0))
        deadline = '기한 내 완료' if result['on_time'] is True else '기한 초과' if result['on_time'] is False else '기한 평가 제외'
        self.full_text = (f'이번 근무의 고객 업무를 완료했습니다.\n'
                          f'고객: {result["company"]}\n작업: {result["task"]}\n'
                          f'운영 점수: {result["score"]}점 · 완료 기한: {deadline}\n'
                          f'반환 GPU: {result["gpu"]}개 · 반환 전력: {result["power"]}단위\n'
                          + '서버 상태: '+' / '.join(f'{key} {value}' for key, value in result['servers'].items())
                          + f'\n고객 완료 안내: {result["feedback"]}')
        # 화면이 작을 때만 스크롤합니다(내용이 맞으면 스크롤바가 나타나지 않습니다). 버튼은 항상 아래에 고정됩니다.
        self.scroll = ScrollArea(self)
        self.scroll.grid(row=1, sticky='nsew')
        body = self.scroll.body
        body.columnconfigure(0, weight=1)
        self.tiles = tile_row(body, success_tiles(result))
        self.tiles.grid(row=0, sticky='ew', padx=28, pady=(8, 10))
        jobs = result.get('jobs') or []
        if len(jobs) > 1:
            self.job_chips = tk.Frame(body, bg=BG)
            self.job_chips.grid(row=1, sticky='ew', padx=28, pady=(0, 10))
            for column, job in enumerate(jobs):
                self.job_chips.columnconfigure(column, weight=1, uniform='jobs')
                tone_card(self.job_chips, job['company'], f'정상 완료 · {job["score"]}점', 'cyan', '✔', body_size=11).grid(
                    row=0, column=column, sticky='nsew', padx=(0 if column == 0 else 6, 0))
        # 상세 표는 카드 아래의 보조 정보입니다(값은 기존 요약 그대로).
        self.summary = tk.Frame(body, bg=PANEL)
        self.summary.grid(row=2, sticky='ew', padx=28)
        self.summary.columnconfigure(1, weight=1)
        self.summary_cells = {}
        for index, (key, value) in enumerate(result.get('summary', [])):
            label(self.summary, key, 10, MUTED, anchor='w').grid(row=index, column=0, sticky='w', padx=(12, 18), pady=1)
            cell = label(self.summary, value, 10, GREEN if key in ('운영 점수', '평균 운영 점수') else TEXT, True, anchor='w')
            cell.grid(row=index, column=1, sticky='w', pady=1)
            self.summary_cells[key] = cell
        box, self.mentor_portrait, self.mentor_note = _mentor_box(body, '[선배 엔지니어]', success_mentor_lines(tutorial))
        box.grid(row=3, sticky='ew', padx=28, pady=(10, 0))
        self.customer_reply = label(body, '고객 안내 · '+str(result['feedback']), 10, MUTED, justify='left', wraplength=700)
        self.customer_reply.grid(row=4, sticky='w', padx=28, pady=(6, 0))
        notice = ('튜토리얼을 마쳤습니다. 스토리 도전은 별도 슬롯에서 제1장부터 시작합니다.' if tutorial else
                  '다음 근무: 일본·미국 고객의 요청이 함께 들어옵니다. 한정된 자원을 어떻게 나눌지 판단해 보세요.' if start_chapter2 is not None else
                  '메인 메뉴에서 다른 기록을 선택하거나 다음 근무를 준비할 수 있습니다.')
        self.next_card = tone_card(body, '다음 단계', notice, 'gold', '▶', body_size=12)
        self.next_card.grid(row=5, sticky='ew', padx=28, pady=(10, 12))
        self.next_notice = self.next_card.body
        self.buttons = {}
        self.action_bar = button_bar(self, complete_actions(tutorial, start_chapter2, CHAPTERS[2].heading+' · 시작',
                                                            retry, select_chapter, select_mode))
        self.action_bar.grid(row=2, sticky='ew', pady=(6, 16))
        self.buttons.update(self.action_bar.buttons)
        if 'next' in self.buttons:
            self.buttons['chapter2'] = self.buttons['next']
        center_dialog(self, parent, size=(820, 640), minimum=(640, 420))


class Chapter2CompleteDialog(tk.Toplevel):
    """Chapter 2 실제 결과. 미션 성공/실패와 종합 점수, 고객별 표, 선배 분석을 먼저 보여 주고 긴 기록은 접어 둡니다."""
    def __init__(self, parent, result, select_mode, start_free, status, review, retry=None, start_chapter3=None, select_chapter=None):
        super().__init__(parent, bg=BG)
        self.withdraw()
        success = result.get('mission') == 'success'
        self.title(CHAPTERS[2].heading+' · '+('클리어' if success else '실패'))
        self.transient(parent)
        self.columnconfigure(0, weight=1)
        self.result = result
        summary = result.get('summary') or {}
        # 스토리가 끝난 것과 미션에 성공한 것은 별개입니다. 두 고객 모두 기한 내 정상 처리했을 때만 성공입니다.
        lines = ['미션 성공 · 두 고객의 요청을 모두 기한 내에 정상 처리했습니다.' if success else
                 '미션 실패 · 두 고객의 요청을 모두 기한 내에 정상 처리하지 못했습니다.']
        if result.get('overall') is not None:
            lines.append(f'Chapter 2 종합 평가: {result["overall"]:g}/100 (두 고객 점수의 평균 · 미처리·실패 고객은 0점)')
        if not success and result.get('failure'):
            lines.append('실패 원인\n'+'\n'.join('· '+page.text for page in chapter2_failure_pages(result['failure'])[:-2]))
        if success and result.get('highlights'):
            lines.append('기한을 지킨 방법\n'+'\n'.join('· '+line for line in result['highlights']))
        for job in result['jobs']:
            deadline = '기한 내' if job['on_time'] is True else '기한 초과' if job['on_time'] is False else '기한 평가 없음'
            earned = f'미션 평가 {job["eval_score"]}점' if job.get('eval_score') is not None else '미션 평가 미확정'
            lines.append(f'{job["country"]} · {job["company"]} — {job["task"]}\n'
                         f'  결과: {job["outcome"]} · {earned} · {deadline}\n'
                         f'  운영 모드: {job["mode"]} · GPU {job["gpu"]} / 전력 {job["power"]} 사용 후 반환\n'
                         f'  배정 위치: {job["placement"]}')
        ran = sum(1 for job in result['jobs'] if job['started'] is not None)
        lines.append('두 작업은 같은 서버 원장을 나누어 쓰며 실행 시간이 겹쳤습니다.' if result['concurrent'] else
                     '두 작업은 실행 시간이 겹치지 않아 먼저 끝난 작업의 자원이 반환된 뒤 처리되었습니다.' if ran == 2 else
                     f'실제로 실행한 작업은 {ran}건입니다.')
        lines.append('서버 상태: '+' / '.join(f'{key} {value}' for key, value in result['servers'].items()))
        if result.get('decisions'):
            lines.append('주요 운영 결정과 기록\n'+'\n'.join('· '+line for line in result['decisions']))
        if result.get('practice'):
            lines.append('이 기록은 Chapter 2 연습 슬롯의 것이며 Chapter 1 진행·점수와 별개입니다.')
        self.full_text = '\n\n'.join(lines)

        top = tk.Frame(self, bg=BG)
        top.grid(row=0, sticky='ew', padx=22, pady=(12, 4))
        top.columnconfigure(0, weight=1)
        label(top, CHAPTERS[2].heading, 9, MUTED).grid(row=0, column=0, sticky='w')
        self.verdict = label(top, 'MISSION SUCCESS' if success else 'MISSION FAILED', 22, GREEN if success else RED, True)
        self.verdict.grid(row=1, column=0, sticky='w')
        overall = result.get('overall')
        self.score_label = label(top, f'{overall:g}' if overall is not None else '미확정', 30, CYAN, True)
        self.score_label.grid(row=0, column=1, rowspan=2, sticky='e', padx=6)
        label(top, '종합 점수 / 100', 9, MUTED).grid(row=2, column=1, sticky='e', padx=6)
        note = summary.get('verdict', '')
        if not success and overall is not None:
            note += ' · 종합 점수와 별개로 한 고객이라도 기한 내 정상 완료하지 못하면 미션은 실패입니다.'
        self.verdict_note = label(top, note, 10, TEXT, anchor='w', justify='left', wraplength=560)
        self.verdict_note.grid(row=2, column=0, sticky='w')
        if not success:
            self.failure = failure_explanation(result)
            self.failure_title = failure_heading(top, self.failure)

        self.scroll = ScrollArea(self)
        self.scroll.grid(row=1, sticky='nsew')
        self.rowconfigure(1, weight=1)
        body = self.scroll.body
        if not success:
            failure_card(body, self.failure).grid(row=0, sticky='ew', padx=22, pady=(4, 12))
        stats = tk.Frame(body, bg=PANEL)
        stats.grid(row=1, sticky='ew', padx=22, pady=(4, 6))
        stats.columnconfigure(1, weight=1)
        self.stats = {}
        for index, (name, value) in enumerate((('성공 고객', f'{summary.get("ok", 0)} / {summary.get("total", 2)}'),
                                              ('운영 전략', summary.get('strategy', '')), ('배정', summary.get('arrangement', '')),
                                              ('자원', summary.get('resources', '')))):
            label(stats, name, 9, MUTED, anchor='w').grid(row=index, column=0, sticky='w', padx=(10, 14), pady=1)
            self.stats[name] = label(stats, value, 10, TEXT, True, anchor='w')
            self.stats[name].grid(row=index, column=1, sticky='w', pady=1)

        table = tk.Frame(body, bg=PANEL)
        table.grid(row=2, sticky='ew', padx=22)
        for column, weight in enumerate((2, 2, 3, 2, 2)):
            table.columnconfigure(column, weight=weight)
        for column, name in enumerate(('고객', '운영 모드', '결과', '기한', '점수')):
            label(table, name, 9, MUTED, True, anchor='w').grid(row=0, column=column, sticky='w', padx=8, pady=(4, 2))
        self.table_cells = []
        for row, job in enumerate(result['jobs'], start=1):
            ok = job.get('state') == 'success'
            if job.get('eval_score') is None:
                score = '미확정'
            else:
                score = f'{job["eval_score"]}점' + ('' if ok else ' (미션 평가)')
            cells = (job['country'], job['mode'], job['outcome'], job.get('deadline', ''), score)
            row_cells = []
            for column, text in enumerate(cells):
                color = (GREEN if ok else RED) if column in (2, 3) else TEXT
                cell = label(table, text, 10, color, column in (0, 4), anchor='w', wraplength=170, justify='left')
                cell.grid(row=row, column=column, sticky='w', padx=8, pady=3)
                row_cells.append(cell)
            self.table_cells.append(row_cells)

        self.key_decisions = label(body, '주요 운영 결정\n· 전략: '+summary.get('strategy', '')+'\n· 배정: '+summary.get('arrangement', '')
                                   + '\n· 자원: '+summary.get('resources', '')+'\n· 결과: '+summary.get('verdict', '')
                                   + '\n· 평가: '+('미션 성공' if success else '미션 실패'),
                                   10, TEXT, justify='left', anchor='w')
        if success:
            self.key_decisions.grid(row=3, sticky='w', padx=22, pady=(8, 2))

        analysis = ([page.text for page in chapter2_failure_pages(result['failure'])[:-2]][:4] if (not success and result.get('failure'))
                    else list(result.get('highlights') or [])[:4])
        self.mentor_lines = analysis or ['분석할 실패·성공 기록이 없습니다.']
        box, self.mentor_portrait, self.mentor_label = _mentor_box(body, '[선배 엔지니어의 분석]', self.mentor_lines)
        if success:
            box.grid(row=4, sticky='ew', padx=22, pady=(6, 2))

        self.detail_shown = False
        self.detail_button = ActionButton(body, '상세 기록 보기 ▼', self.toggle_detail)
        self.detail_button.grid(row=5, sticky='w', padx=22, pady=(6, 2))
        self.summary = ScrolledText(body, wrap='word', height=9, font=(FONT, 10), bg=PANEL, fg=TEXT, bd=0, padx=12, pady=10)
        self.summary.insert('1.0', self.full_text)
        self.summary.configure(state='disabled')

        # 행동은 최대 3개, 주요 행동 하나만 강조합니다(성공=다음 장, 실패=재도전).
        next_action = start_chapter3 if success else None
        self.action_bar = button_bar(self, complete_actions(
            False, next_action, CHAPTERS[3].heading+' · 시작', retry,
            select_chapter, select_mode, failed=not success, practice=bool(result.get('practice'))))
        self.action_bar.grid(row=2, sticky='ew', pady=(6, 16))
        self.buttons = dict(self.action_bar.buttons)
        if 'next' in self.buttons:
            self.buttons['chapter3'] = self.buttons['next']
        center_dialog(self, parent, size=(820, 640), minimum=(640, 400))

    def toggle_detail(self):
        """긴 서버별 배정·대기 기록은 접어 두었다가 필요할 때만 펼칩니다. 조회 전용이며 게임 상태를 바꾸지 않습니다."""
        self.detail_shown = not self.detail_shown
        if self.detail_shown:
            self.summary.grid(row=6, sticky='nsew', padx=22)
            self.detail_button.configure(text='상세 기록 접기 ▲')
        else:
            self.summary.grid_remove()
            self.detail_button.configure(text='상세 기록 보기 ▼')


class Chapter3CompleteDialog(tk.Toplevel):
    """Chapter 3 결과(v0.9-3a-1 압축판). 판정·성공 수 → 결과표 → 선배 평가 2~3문장 → 접힌 상세 기록.
    버튼은 스크롤 영역 밖 아래에 고정되어 창이 작아도 항상 보입니다."""
    def __init__(self, parent, result, select_mode, start_free, status, review, retry=None, start_next=None, next_label='', select_chapter=None):
        super().__init__(parent, bg=BG)
        self.withdraw()
        success = result.get('mission') == 'success'
        summary = result.get('summary') or {}
        name = summary.get('name', 'Chapter 3')
        subtitle = summary.get('subtitle', '네트워크 장애 진단과 대응')
        chapter = CHAPTERS['3b' if name == 'Chapter 3b' else 3]
        name, subtitle = f'제{chapter.number}장', chapter.title
        self.title(f'{name} '+('성공' if success else '실패')+f' · {subtitle}')
        self.transient(parent)
        self.columnconfigure(0, weight=1)
        self.result = result
        top = tk.Frame(self, bg=BG)
        top.grid(row=0, sticky='ew', padx=22, pady=(10, 2))
        top.columnconfigure(0, weight=1)
        label(top, f'{name.upper()} · {subtitle}', 9, MUTED).grid(row=0, column=0, sticky='w')
        self.verdict = label(top, 'MISSION SUCCESS' if success else 'MISSION FAILED', 22, GREEN if success else RED, True)
        self.verdict.grid(row=1, column=0, sticky='w')
        self.count_label = label(top, f'{summary.get("ok", 0)} / {summary.get("total", 2)}', 24, CYAN, True)
        self.count_label.grid(row=0, column=1, rowspan=2, sticky='e', padx=6)
        label(top, '성공한 미션', 9, MUTED).grid(row=2, column=1, sticky='e', padx=6)
        self.verdict_note = label(top, summary.get('verdict', ''), 10, TEXT, anchor='w', justify='left', wraplength=560)
        self.verdict_note.grid(row=2, column=0, sticky='w')
        if not success:
            self.failure = failure_explanation(result)
            self.failure_title = failure_heading(top, self.failure)

        self.scroll = ScrollArea(self)
        self.scroll.grid(row=1, sticky='nsew')
        self.rowconfigure(1, weight=1)
        body = self.scroll.body
        if not success:
            failure_card(body, self.failure).grid(row=0, sticky='ew', padx=22, pady=(4, 12))
        table = tk.Frame(body, bg=PANEL)
        table.grid(row=1, sticky='ew', padx=22, pady=(4, 4))
        columns = summary.get('columns', ('미션', '장애 원인', '선택 대응', '복구 결과', '점수'))
        for column in range(len(columns)):
            table.columnconfigure(column, weight=(1, 2, 5, 2, 2, 2)[column] if len(columns) == 6 and column == 5 else (1, 2, 5, 2, 2)[column])
        for column, header in enumerate(columns):
            label(table, header, 9, MUTED, True, anchor='w').grid(row=0, column=column, sticky='w', padx=8, pady=(4, 2))
        self.table_cells = []
        for row, values in enumerate(summary.get('table', []), start=1):
            ok = values[3] in ('성공', '기한 내 완료')
            row_cells = []
            for column, text in enumerate(values):
                color = (GREEN if ok else RED) if column == 3 else TEXT
                cell = label(table, text, 10, color, column in (0, 3, len(values)-1), anchor='w', wraplength=240, justify='left')
                cell.grid(row=row, column=column, sticky='w', padx=8, pady=3)
                row_cells.append(cell)
            self.table_cells.append(row_cells)
        self.mentor_lines = result.get('mentor') or ['분석할 장애 기록이 없습니다.']
        box, self.mentor_portrait, self.mentor_label = _mentor_box(body, '[선배 평가]', self.mentor_lines)
        if success:
            box.grid(row=2, sticky='ew', padx=22, pady=(6, 2))

        lines = []
        for index, job in enumerate(result['jobs'] if not summary.get('detail_text') else ()):
            record = job['record']
            lines.append(f'미션 {"AB"[index]} · {job["country"]} {job["company"]} — {job["job"]["task"]}')
            for name, value in summary.get('rows', [[]]*2)[index]:
                lines.append(f'  {name}: {value}')
            lines.append(f'  운영 모드 {job["job"]["mode"]} · GPU {job["job"]["gpu"]} / 전력 {job["job"]["power"]} 사용 후 '
                         + ('반환' if result.get('released') else '(반환 확인 필요)'))
            if record:
                lines.append(f'  마지막 수치: 필요 {record["needed"]} / 가용 {record["available"]} · 주 경로 '
                             f'{"UP" if record["primary_up"] else "DOWN"}{" · 백업 경로 사용" if record["rerouted"] else ""}')
        lines.append('서버 상태: '+' / '.join(f'{key} {value}' for key, value in result['servers'].items()))
        if result.get('practice'):
            lines.append('이 기록은 Chapter 3 독립 연습 슬롯의 것이며 Chapter 1·2 진행·점수와 별개입니다.')
        lines.append('이 장의 네트워크 구성은 교육용이며 실제 네트워크의 모든 경우를 대표하지 않습니다.')
        self.full_text = summary.get('detail_text') or '\n'.join(lines)
        self.detail_shown = False
        self.detail_button = ActionButton(body, '상세 기록 보기 ▼', self.toggle_detail)
        self.detail_button.grid(row=3, sticky='w', padx=22, pady=(4, 2))
        self.summary = ScrolledText(body, wrap='word', height=9, font=(FONT, 10), bg=PANEL, fg=TEXT, bd=0, padx=12, pady=10)
        self.summary.insert('1.0', self.full_text)
        self.summary.configure(state='disabled')

        next_action = start_next if success else None
        self.action_bar = button_bar(self, complete_actions(
            False, next_action, next_label, retry, select_chapter, select_mode,
            failed=not success, practice=bool(result.get('practice'))))
        self.action_bar.grid(row=2, sticky='ew', pady=(6, 16))
        self.buttons = dict(self.action_bar.buttons)
        center_dialog(self, parent, size=(820, 560), minimum=(640, 380))

    def toggle_detail(self):
        """조회 전용. 상세 기록(수치·반환 자원·서버 상태)은 접어 두었다가 필요할 때만 펼칩니다."""
        self.detail_shown = not self.detail_shown
        if self.detail_shown:
            self.summary.grid(row=4, sticky='nsew', padx=22)
            self.detail_button.configure(text='상세 기록 접기 ▲')
        else:
            self.summary.grid_remove()
            self.detail_button.configure(text='상세 기록 보기 ▼')
