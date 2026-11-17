"""chapter5-001: native Lab input fixture, then one regular Chapter 1→5 play.

--focus <new-dir> initializes only an independent practice slot; all actions use
Win32 input. <new-dir> <focus-result.json> requires the same focused QA sources.
--self-check validates the new parser/input boundaries without opening windows.
"""
import ctypes
from ctypes import wintypes as wt
from dataclasses import asdict
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autoplay_chapter4 as ch4
from autoplay_chapter4 import ch1, ch2, ch3, top_by_title, AbortQA, ROOT
from gui_driver import MOUSEINPUT, user32, owner_at
from tutorial_highlight import widget_visible


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [('wVk', wt.WORD), ('wScan', wt.WORD), ('dwFlags', wt.DWORD),
                ('time', wt.DWORD), ('dwExtraInfo', ctypes.POINTER(ctypes.c_ulong))]


class KEYINPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [('mi', MOUSEINPUT), ('ki', KEYBDINPUT)]
    _anonymous_ = ('u',)
    _fields_ = [('type', wt.DWORD), ('u', _U)]


def ping_counts(output):
    match = re.search(r'(\d+) packets transmitted, (\d+) received', output)
    if not match:
        raise AbortQA('화면의 ping 송신·응답 수를 읽을 수 없습니다.')
    return tuple(map(int, match.groups()))


def fact_choice(text):
    if '회선이 물리적으로 끊어졌다' in text or '서버 장비가 고장' in text:
        return '아직 확정 불가'
    if text.startswith(('가까운 라우터(', 'AIDC 쪽 대상(', 'AIDC 네트워크로 가는 경로는 ')):
        return '확인된 사실'
    raise AbortQA('관측과 대조할 수 없는 새 분류 문장: '+text)


def source_hashes():
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in map(Path, (__file__, ch1.__file__, ch2.__file__, ch3.__file__, ch4.__file__))}


class LabHarness(ch1.StoryHarness):
    def __init__(self, out):
        super().__init__(out)
        self.keyboard_events, self.input_log = 0, []

    def type_command(self, entry, line):
        """Unicode SendInput + native Enter; never paste/insert/event_generate.

        Each key verifies foreground and Tk focus so input cannot land in another app.
        """
        if not line or not line.isascii() or len(line) > 120 or any(c in line for c in '\r\n'):
            raise AbortQA('QA 명령은 ASCII 한 줄이어야 합니다.')
        item = self.call(lambda: self.widget_info(entry))
        self.click(item, settle=.2)
        expected = self.call(lambda: user32.GetAncestor(entry.winfo_toplevel().winfo_id(), 2))
        point = item['x']+item['w']//2, item['y']+item['h']//2
        self.wait_clear(point=point)

        def guard():
            if (self.preflight_data['status'] != 'passed' or user32.GetForegroundWindow() != expected
                    or owner_at(*point)[1] != os.getpid()
                    or not self.call(lambda: self.root.focus_get() is entry and entry.cget('state') == 'normal')):
                raise AbortQA('키보드 대상 전경·소유·입력 포커스 불일치: 입력 중단')

        def send(code, virtual=False):
            guard()
            for up in (False, True):
                event = KEYINPUT(type=1)
                event.ki = KEYBDINPUT(code if virtual else 0, 0 if virtual else code,
                                         (0 if virtual else 4) | (2 if up else 0), 0, None)
                if user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(event)) != 1:
                    raise OSError('키보드 SendInput 실패')
                self.keyboard_events += 1

        if self.call(entry.get):
            raise AbortQA('입력창에 기존 문자가 있어 덮어쓰지 않고 중단합니다.')
        for character in line:
            send(ord(character))
        self.wait_for(lambda: self.call(entry.get) == line, what='실제 키보드 입력문 일치')
        self.note('실제 키보드 입력·Enter: '+line)
        self.input_log.append({'stage': self.step, 'line': line, 'verified_entry': self.call(entry.get),
                               'method': 'Win32 Unicode SendInput + VK_RETURN'})
        send(0x0d, virtual=True)
        time.sleep(.6)


def play_chapter5(h, focused=False):
    app = lambda: h.selector.app
    session = lambda: app().session
    lab = lambda: app().lab_window
    check = lambda item, ok, detail='': h.check(h.step, item, bool(ok), detail)
    h.completed = False
    h.chapter5_data = data = {'stages': [], 'commands': [], 'guides': [], 'access': [], 'ticks': []}

    def state():
        def read():
            s, t = session(), session().training
            r = s.runs[t.rid]
            return {'minute': s.minute, 'training': asdict(t), 'status': s.training_status(),
                    'run': {'id': t.rid, 'state': asdict(r.state), 'progress': r.state.progress,
                            'request': dict(r.request), 'terms': dict(r.terms), 'conditions': dict(r.conditions)},
                    'used': (s.center.gpu_used, s.center.power_used), 'available': s.servers.available(),
                    'objective': app().story_objective.cget('text')}
        return h.call(read)

    def operation():
        def read():
            s = session()
            return {'minute': s.minute, 'center': asdict(s.center),
                    'ledger': {str(k): asdict(v) for k, v in s.servers.allocations.items()},
                    'hardware': {k: asdict(v) for k, v in s.servers.hardware.items()},
                    'runs': {str(k): {'state': asdict(r.state), 'request': dict(r.request),
                                     'conditions': dict(r.conditions), 'terms': dict(r.terms),
                                     'proposals': list(r.proposals)} for k, r in s.runs.items()}}
        return h.call(read)

    def guide():
        for _ in range(20):
            snapshot = h.snapshot()
            card = top_by_title(snapshot, 'FEEDBACK')
            if card:
                button = h.find('업무로 돌아가기', top=card['path']) or h.find('확인 · 다음 목표', top=card['path'])
                if not button:
                    raise AbortQA('예상하지 않은 결과 카드')
                h.click(button, settle=.2)
            elif top_by_title(snapshot, '현장 교육'):
                page = h.call(lambda: {'text': app().story_window.bubble.get('1.0', 'end-1c'),
                                      'button': h.widget_info(app().story_window.next_button)})
                data['guides'].append({'stage': h.step, 'text': page['text']})
                h.click(page['button'], settle=.2)
            else:
                return
        raise AbortQA('제5장 교육창 종료 한도 초과')

    def tab(name):
        def point():
            book = lab().book
            wanted = book.index(lab().tabs[name])
            xs = []
            for x in range(2, book.winfo_width()-2, 2):
                try:
                    if book.index(f'@{x},10') == wanted:
                        xs.append(x)
                except Exception:
                    pass
            if not xs:
                raise AbortQA('표시된 탭 좌표를 찾을 수 없습니다: '+name)
            return h.widget_info(book), (min(xs)+max(xs))//2
        item, x = h.call(point)
        h.click(item, dx=x, dy=10, settle=.2)
        check('실제 탭 선택: '+name, h.call(lambda: lab().book.select() == str(lab().tabs[name])))

    def visible(target, area=None):
        """Only scroll-arrow clicks move content; target is re-found after each UI rebuild."""
        history = []
        for _ in range(100):
            def read():
                widget = target()
                info = h.widget_info(widget)
                view = area().canvas if area else None
                y = widget.winfo_rooty()
                return {'visible': widget_visible(widget), 'info': info,
                        'direction': 'up' if view and y < view.winfo_rooty() else 'down',
                        'bar': h.widget_info(area().scrollbar) if area else None}
            now = h.call(read)
            if now['visible']:
                data['access'].append({'stage': h.step, 'widget': now['info'], 'scroll_clicks': len(history)})
                return now['info']
            if not area:
                raise AbortQA('필수 조작이 가려져 있습니다: '+now['info']['text'])
            history.append(now['direction'])
            bar = now['bar']
            h.click(bar, dy=8 if now['direction'] == 'up' else bar['h']-8, settle=.03)
        raise AbortQA('본문 실제 스크롤로 대상에 접근할 수 없습니다.')

    def button(text, area=None, exact=False):
        def find():
            for widget in h._walk(lab()):
                if widget.winfo_toplevel() is lab() and widget.winfo_ismapped() and widget.winfo_class() in ('Button', 'TButton'):
                    value = str(widget.cget('text'))
                    if value == text if exact else text in value:
                        return widget
            raise AbortQA('Lab 버튼 없음: '+text)
        h.click(visible(find, area), settle=.25)

    def open_lab():
        h.click(h.call(lambda: h.widget_info(app().lab_button)), settle=.4)
        h.wait_for(lambda: h.call(lambda: lab() is not None and lab().winfo_viewable()), what='Lab 표시')

    def terminal(line):
        tab('가상 터미널')
        before = operation()
        old = h.call(lambda: lab().term.get('1.0', 'end-1c'))
        entry = h.call(lambda: lab().term_entry)
        h.type_command(entry, line)
        output = h.call(lambda: lab().term.get('1.0', 'end-1c'))
        current = state()
        record = {'stage': h.step, 'line': line, 'output_added': output[len(old):],
                  'training': current['training'], 'network': h.call(lambda: asdict(lab().obs.network)),
                  'clock': current['minute']}
        data['commands'].append(record)
        check('직접 입력 관측은 시간·자원·점수·동의 불변', before == operation())
        check('실제 터미널에 입력문·교육용 시각 표시', line in record['output_added'] and '교육용 출력' in record['output_added'])
        return record['output_added']

    def stage_shot(name):
        h.shot('c5_'+name, note=h.step)
        data['stages'].append({'stage': h.step, 'state': state(), 'screen': h.snapshot()})

    def advance(expected):
        tab('연수 진행')
        st = state()['status']
        check('현재 Stage 실제 통과', st['passed'])
        if focused:
            button('다음 연습 ▶')
        else:
            check('다음 Stage만 진행 가능', next(x['badge'] for x in st['stages'] if x['key'] == expected) == 'next')
            h.click(visible(lambda: lab().stage_boxes[expected][2]), settle=.3)
        guide()
        check('실제 GUI로 다음 Stage 이동', state()['training']['current'] == expected)

    h.step = '제5장 독립 연습 fixture' if focused else '제4장 결과→제5장 정규 진입'
    previous = h.call(lambda: {k: app().session.story.payload().get(k) for k in ('onboarding', 'chapter2', 'chapter3', 'chapter3b')})
    if not focused:
        h.click_text('제5장 — 홀로 선 엔지니어 · 시작', settle=.5)
    data['initial'] = state()
    check('연습/정규 구분·새 요청·미배정', state()['training']['practice'] is focused
          and state()['run']['state']['phase'] == 'ready' and state()['used'] == (0, 0))
    from aidc.storage.checkpoints import checkpoint_path
    checkpoint = checkpoint_path(h.slot, 'lab')
    checkpoint_hash = hashlib.sha256(checkpoint.read_bytes()).hexdigest() if checkpoint.exists() else None
    check('정규 시작 체크포인트와 연습 구분', checkpoint.exists() is (not focused))
    guide()
    open_lab()
    tab('연수 진행')
    check('Stage 지도·목표 표시·미배정 상태 안내', h.call(lambda: len(lab().stage_boxes) == 5
          and '실습 준비' in lab().goal_title.cget('text')))
    if not focused:
        before = state()['training']
        h.click(visible(lambda: lab().stage_boxes['terminal'][2]), settle=.2)
        check('잠긴 Stage 지도 클릭은 진급하지 않음', state()['training'] == before)
        tab('가상 터미널')
        check('Stage 4 전 터미널 입력·실행 잠금', h.call(lambda: lab().term_entry.cget('state') == 'disabled'
              and lab().term_run.cget('state') == 'disabled'))
        tab('연수 진행')
    stage_shot('setup')
    button('관제실로 돌아가기', exact=True)
    h.click(h.call(lambda: h.widget_info(app().arrival_open_button)), settle=.4)
    h.wait_for(lambda: h.call(lambda: app().message_window is not None and app().message_window.winfo_viewable()), what='제5장 고객 요청')
    h.shot('c5_request', note='연수용 실제 요청·원래 조건')
    h.click_text('확인 · 운영실로', settle=.3)
    guide()
    h.click_text('배정 설정·선택', settle=.4)
    h.click_text('배정안 1 (추천)', settle=.2)
    data['chosen'] = h.call(lambda: [asdict(p) for p in app().allocation_window.options[0]])
    h.click_text('선택한 계획으로 작업 시작', settle=.3)
    guide()
    for _ in range(15):
        if state()['run']['state']['phase'] in ('incident', 'paused'):
            break
        h.click_text('+10분', settle=.3)
        data['ticks'].append(state())
        guide()
    else:
        raise AbortQA('연수 사건의 실제 장애가 발생하지 않았습니다.')
    data['fault'] = state()
    check('실제 경로 장애·자원 배정 유지', not state()['run']['state']['primary_up'] and state()['used'] != (0, 0))
    open_lab()

    h.step = 'Stage 1 시스템 구조 관찰'
    before = operation()
    tab('네트워크 구조')
    check('탭 열기만으로 Stage 1 통과하지 않음', not state()['training']['completed'])
    def broken():
        canvas = lab().net_canvas
        rows = [{'coords': canvas.coords(i), 'tags': canvas.gettags(i), 'fill': canvas.itemcget(i, 'fill')}
                for i in canvas.find_withtag('link') if canvas.itemcget(i, 'dash')]
        red = [r for r in rows if r['fill'] == '#ff7a7a']
        # Find the displayed broken line's red style, not the engine's segment answer.
        if len(red) != 1:
            from ui import RED
            red = [r for r in rows if r['fill'] == RED]
        if len(red) != 1:
            raise AbortQA('실제 구조도에서 끊어진 점선 하나를 식별할 수 없습니다.')
        x1, y1, x2, y2 = red[0]['coords']
        return h.widget_info(canvas), int((x1+x2)/2), int((y1+y2)/2), rows
    item, x, y, rows = h.call(broken)
    data['structure_links'] = rows
    stage_shot('s1_structure_before')
    h.click(item, dx=x, dy=y, settle=.3)
    check('구간 실제 클릭은 선택만 기록·영향 답변 필요', state()['status']['segment']['correct'] and not state()['status']['passed'])
    stage_shot('s1_structure_selected')
    tab('연수 진행')
    button('고객 단말이 보낸 작업 데이터가', lambda: lab().training_area)
    check('구조 선택·영향 판단으로 통과·운영 상태 불변', state()['status']['passed'] and before == operation())
    stage_shot('s1_passed')
    advance('tool')

    h.step = 'Stage 2 진단 도구 선택'
    before = operation()
    tab('명령어 학습')
    h.click(visible(lambda: lab().level_buttons['beginner']), settle=.2)
    h.click(visible(lambda: lab().choice_buttons['ip route'], lambda: lab().level_frames['beginner']), settle=.3)
    check('목적에 맞지 않는 도구는 통과하지 않음', not state()['status']['passed'] and not state()['status']['choice']['correct'])
    data['wrong_tool_feedback'] = h.call(lambda: lab().choice_fit.cget('text'))
    h.click(visible(lambda: lab().choice_buttons['ping'], lambda: lab().level_frames['beginner']), settle=.3)
    output = h.call(lambda: lab().choice_output.get('1.0', 'end-1c'))
    data['commands'].append({'stage': h.step, 'source': 'choice', 'output': output})
    check('도구 선택만으로 통과하지 않음·장애 출력', not state()['status']['passed'] and ping_counts(output)[1] == 0)
    visible(lambda: lab().choice_fields['3. 확인할 수 없는 정보'], lambda: lab().level_frames['beginner'])
    stage_shot('s2_limits')
    tab('연수 진행')
    button('대상까지 ICMP 응답이', lambda: lab().training_area)
    check('ping 한계 판단으로 통과·운영 상태 불변', state()['status']['passed'] and before == operation())
    stage_shot('s2_passed')
    advance('assemble')

    h.step = 'Stage 3 명령어 조립'
    before = operation()
    tab('명령어 학습')
    h.click(visible(lambda: lab().level_buttons['intermediate']), settle=.2)
    area = lambda: lab().level_frames['intermediate']
    h.click(visible(lambda: lab().block_buttons[('command', 'ping')], area), settle=.2)
    button('조립 확인 · 실행', area)
    data['invalid_blocks'] = h.call(lambda: lab().block_output.get('1.0', 'end-1c'))
    check('불완전한 조립은 통과하지 않음·오류 안내', not state()['status']['passed'] and state()['status']['assembly'] is None
          and 'Destination address required' in data['invalid_blocks'])
    h.click(visible(lambda: lab().block_buttons[('option', '-c 3')], area), settle=.2)
    target = h.call(lambda: next(key[1] for key in lab().block_buttons if key[0] == 'target' and key[1] and key[1].startswith('10.')))
    h.click(visible(lambda: lab().block_buttons[('target', target)], area), settle=.2)
    button('조립 확인 · 실행', area)
    output = h.call(lambda: lab().block_output.get('1.0', 'end-1c'))
    sent, received = ping_counts(output)
    data['commands'].append({'stage': h.step, 'source': 'blocks', 'output': output})
    check('실제 -c 3 서버 ping·결과 질문 필요', sent == 3 and received == 0 and not state()['status']['passed'])
    visible(lambda: lab().block_next, area)
    stage_shot('s3_blocks')
    tab('연수 진행')
    button(f'{received}개', lambda: lab().training_area, exact=True)
    check('응답 수 읽기로 통과·운영 상태 불변', state()['status']['passed'] and before == operation())
    stage_shot('s3_passed')
    advance('terminal')

    h.step = 'Stage 4 터미널 직접 입력'
    wrong = terminal('ping -z 192.168.10.1')
    check('잘못된 명령 피드백·미통과', 'invalid option' in wrong and not state()['status']['passed'])
    near = terminal('ping -c 3 192.168.10.1')
    remote = terminal(f'ping -c 3 {target}')
    route = terminal('ip route')
    check('현재 장애 상태와 가까운/원격/경로 출력 일치', ping_counts(near) == (3, 3) and ping_counts(remote) == (3, 0)
          and '10.0.0.0/24 via 192.168.10.1 dev eth0' in route)
    check('관측3종만으로 통과하지 않음', not state()['status']['passed'])
    stage_shot('s4_terminal')
    tab('연수 진행')
    statements = state()['status']['statements']
    data['fact_decisions'] = []
    before = operation()
    for _, text in statements:
        choice = fact_choice(text)
        def fact_button(t=text, c=choice):
            for widget in h._walk(lab().training_area.body):
                if widget.winfo_class() == 'Label' and widget.cget('text') == t:
                    row = widget.grid_info()['row']
                    return next(w for w in widget.master.grid_slaves(row=row) if w.winfo_class() == 'Button' and w.cget('text') == c)
            raise AbortQA('화면의 사실 분류 행을 찾지 못했습니다.')
        h.click(visible(fact_button, lambda: lab().training_area), settle=.2)
        data['fact_decisions'].append({'displayed_statement': text, 'choice': choice, 'basis': 'actual terminal near/remote/route outputs; physical cause remains unproven'})
    button('정리 제출', lambda: lab().training_area, exact=True)
    check('사실/원인 추정 구분으로 통과·운영 상태 불변', state()['status']['passed'] and before == operation())
    stage_shot('s4_passed')
    advance('independent')

    h.step = 'Stage 5 독립 진단 시연'
    tab('네트워크 구조')
    check('판단 전 구조도 정답 숨김', h.call(lambda: lab().hide_answers and not lab().net_canvas.find_withtag('break')))
    stage_shot('s5_hidden')
    tab('연수 진행')
    check('Stage 4 증거를 Stage 5 증거로 대신하지 않음', not state()['status']['stage5']['evidence_ok'])
    if not focused:
        check('증거/판단 전 관제실 대응 잠금', bool(state()['status']['locked_response']))
    near = terminal('ping -c 3 192.168.10.1')
    remote = terminal(f'ping -c 3 {target}')
    route = terminal('ip route')
    check('직접 관측한 증거 확보·아직 미통과', state()['status']['stage5']['evidence_ok'] and not state()['status']['passed'])
    if ping_counts(near)[1] != 3 or ping_counts(remote)[1] or 'via 192.168.10.1' not in route:
        raise AbortQA('관측이 이미 경험한 경로 단절의 근거와 맞지 않습니다.')
    data['cause_rationale'] = '가까운 라우터 응답3/3, 원격0/3, 주 라우터 경로 설정. 같은 경로 단절 사건을 재사용하는 제한된 시연에서 가장 타당한 선택. 물리 단절을 ping만으로 증명한 것은 아님.'
    stage_shot('s5_evidence')
    tab('연수 진행')
    button('주 통신 경로 단절', lambda: lab().training_area)
    check('원인 판단 뒤 대응 가능·아직 미통과', state()['status']['stage5']['cause']['correct']
          and not state()['status']['locked_response'] and not state()['status']['passed'])
    stage_shot('s5_cause')
    button('관제실로 돌아가기', exact=True)
    before_action = state()
    h.click(h.call(lambda: h.widget_info(app().action_buttons['reroute'])), settle=.4)
    guide()
    data['after_response'] = state()
    check('복구 버튼만으로 Stage 5 통과하지 않음', not state()['status']['passed'] and not state()['status']['stage5']['verified']
          and state()['run']['state']['recovered_by'] == 'reroute')
    check('기존 대응은 가상 시각·GPU/전력 배정 유지', state()['minute'] == before_action['minute']
          and state()['used'] == before_action['used'])
    h.shot('c5_s5_control_response', note='실제 관제실 우회 대응·재확인 전 미통과')
    open_lab()
    after = terminal(f'ping -c 3 {target}')
    check('동일 도구의 조치 후 응답3/3으로5개 모두 통과', ping_counts(after) == (3, 3)
          and state()['status']['done'] and state()['status']['count'] == 5 and state()['status']['stage5']['verified'])
    data['verification'] = state()
    h.wait_text('TRAINING COMPLETE')
    data['result_screen'] = h.snapshot()
    data['training_result_at_verification'] = h.call(lambda: session().training_result())
    h.shot('c5_complete', note='실제 재확인 후 자동 결과 화면·5/5·시연 한계')
    h.click_text('닫기', top=h.call(lambda: str(app().chapter_window)), exact=True, settle=.3)
    button('관제실로 돌아가기', exact=True)
    for _ in range(20):
        if state()['run']['state']['phase'] == 'finished':
            break
        h.click_text('+10분', settle=.2)
        data['ticks'].append(state())
        guide()
    else:
        raise AbortQA('연수 고객 작업 정상 완료 한도 초과')
    data['final'] = state()
    check('연수 고객 정상 완료·기한 준수·전량 반환', state()['run']['state']['succeeded']
          and state()['run']['terms']['completed'] <= state()['run']['terms']['due']
          and state()['used'] == (0, 0) and state()['available'] == (10, 10))
    check('기존 제1~4장 진행 기록 보존', previous == h.call(lambda: {k: session().story.payload().get(k)
          for k in ('onboarding', 'chapter2', 'chapter3', 'chapter3b')}))
    check('장 시작 체크포인트 보존', not checkpoint.exists() if focused else hashlib.sha256(checkpoint.read_bytes()).hexdigest() == checkpoint_hash)
    data['training_result_final'] = h.call(lambda: session().training_result())
    h.final_disk = ch1.disk_state(h.slot)
    check('5개 Stage·실제 행동·사후 관측 디스크 보존', h.final_disk['integrity'] == 'ok'
          and len(h.final_disk['simulation']['story']['training']['completed']) == 5)
    h.shot('c5_final_returned', note='연수 완료와 고객 작업 정상 완료·전량 반환')
    h.completed = True


def scenario(h):
    ch4.scenario(h)
    play_chapter5(h)


def focus(h):
    # Fixture construction only; no direct learning/incident/progression setup.
    h.maximize_root()
    h.call(lambda: h.selector.new_story('lab'))
    h.slot = h.call(lambda: Path(h.selector.app.db.path))
    h.env = h.call(lambda: {'tk': h.root.tk.call('info', 'patchlevel'), 'screen': [h.root.winfo_screenwidth(), h.root.winfo_screenheight()],
                            'capture_scale': h.scale})
    play_chapter5(h, focused=True)


def self_check():
    import ast
    from gui_driver import INPUT
    assert ctypes.sizeof(KEYINPUT) == ctypes.sizeof(INPUT)
    assert ping_counts('3 packets transmitted, 0 received, 100% packet loss') == (3, 0)
    assert fact_choice('가까운 라우터(1)는 ping에 응답했다') == '확인된 사실'
    assert fact_choice('주 경로의 라우터 너머 회선이 물리적으로 끊어졌다') == '아직 확정 불가'
    for fn, value in ((ping_counts, 'no counters'), (fact_choice, 'new statement')):
        try:
            fn(value)
        except AbortQA:
            pass
        else:
            raise AssertionError('증거를 해석할 수 없으면 중단해야 합니다.')
    tree = ast.parse(Path(__file__).read_text(encoding='utf8'))
    forbidden = {'training_answer', 'training_command', 'training_select_segment', 'start_next_stage',
                 'focus_training_stage', 'start_training', 'advance_time', 'choose_plan', 'respond',
                 'event_generate', 'invoke', 'run_terminal', 'submit_terminal'}
    assert not [n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute) and n.func.attr in forbidden]
    print('chapter5 native QA self-check PASS')


def main():
    if '--self-check' in sys.argv:
        self_check()
        return
    focused = sys.argv[1] == '--focus'
    out = Path(sys.argv[2] if focused else sys.argv[1])
    if not focused:
        gate = json.loads(Path(sys.argv[2]).read_text(encoding='utf8'))
        if (gate['kind'] != 'chapter5_focused_fixture' or not gate['completed'] or gate['error'] or gate['failed']
                or gate['source_sha256'] != source_hashes()):
            raise SystemExit('같은 QA 코드의 실제 입력 집중 검사 통과 자료가 필요합니다.')
    out.mkdir(parents=True, exist_ok=True)
    marker = out/'attempt.json'
    with marker.open('x', encoding='utf8') as file:
        json.dump({'started': datetime.now(ZoneInfo('Asia/Seoul')).isoformat(timespec='seconds')}, file)
    before = ch1.db_hashes()
    h = LabHarness(out)
    h.env, h.placements, h.layouts, h.goals, h.jobs = {}, [], [], [], []
    error = None
    try:
        error = h.run(focus if focused else scenario)['error']
    except BaseException as exc:
        error = f'{type(exc).__name__}: {exc}'
    finally:
        after = ch1.db_hashes()
        h.check('보존', '사용자 저장·잠금·체크포인트 보존', before == after, f'{len(before)}→{len(after)}개')
        if getattr(h, 'slot', None) and h.slot.exists():
            h.final_disk = ch1.disk_state(h.slot)
        completed = getattr(h, 'completed', False)
        assert h.tmp.resolve().parent == Path(tempfile.gettempdir()).resolve() and h.tmp.name.startswith('srs_qa_')
        # Existing cleanup is restricted to this verified temporary directory.
        removed = h.cleanup() if completed and not error and not any(c['result'] == 'FAIL' for c in h.checks) else []
        report = {'kind': 'chapter5_focused_fixture' if focused else 'regular_chapter1_2_3_4_5_full_play',
                  'started': json.loads(marker.read_text(encoding='utf8'))['started'],
                  'commit': subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                  'completed': completed, 'error': error, 'passed': sum(c['result'] == 'PASS' for c in h.checks),
                  'failed': sum(c['result'] == 'FAIL' for c in h.checks), 'checks': h.checks, 'env': h.env,
                  'preflight': h.preflight_data, 'full_play_attempts': 0 if focused else int(h.play_attempted),
                  'clicks': h.clicks, 'wheel_events': h.wheel_events, 'keyboard_events': h.keyboard_events,
                  'input_log': h.input_log, 'repo_data_unchanged': before == after, 'repo_data_count': len(before),
                  'temp_files_removed': removed, 'temp_preserved_on_failure': not bool(removed),
                  **{name: getattr(h, attr, None) for name,attr in [('chapter1','chapter1'),('chapter2','chapter2_data'),
                      ('chapter3','chapter3_data'),('chapter4','chapter4_data'),('chapter5','chapter5_data'),('final_disk','final_disk')]},
                  'source_sha256': source_hashes(), 'shots': h.shots, 'window_events': getattr(h.monitor,'events',[]),
                  'capture_occlusions': h.occlusions, 'native_guard_events': h.guard_events,
                  'log': [line.replace(str(ROOT),'<repo>').replace(str(h.tmp),'<qa-temp>') for line in h.log]}
        (out/'storage-audit.json').write_text(json.dumps({'before':before,'after':after},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        (out/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=1)+'\n',encoding='utf8')
        print(f'completed={completed} error={error} PASS={report["passed"]} FAIL={report["failed"]}',flush=True)
    raise SystemExit(bool(error or report['failed'] or not completed))


if __name__ == '__main__':
    main()
