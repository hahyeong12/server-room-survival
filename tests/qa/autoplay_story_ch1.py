"""story-002: 기존 하네스로 제1장을 실제 마우스 입력으로 한 번 플레이합니다.

Windows 저장소 루트: python tests/qa/autoplay_story_ch1.py <새 출력 디렉터리>
실행 중 마우스/키보드를 사용하지 마세요. 게임 코드와 사용자 저장은 변경하지 않습니다.
--self-check는 GUI 없이 QA 보조 함수와 import만 검사합니다.
"""
import ctypes
import hashlib
import json
import os
import platform
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gui_driver import (ROOT, AbortQA, Harness, POINT, _mouse, owner_at,
                        user32, window_pid, window_rect, MOUSEEVENTF_LEFTDOWN,
                        MOUSEEVENTF_LEFTUP)
from autoplay_tutorial import centered, placement, top_by_title
from tutorial_highlight import widget_visible


def db_hashes():
    """슬롯·체크포인트·SQLite 보조 파일 포함. 경로/해시는 공개 결과에 싣지 않습니다."""
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in ROOT.rglob('*') if p.is_file() and '.git' not in p.parts
            and (p.suffix == '.db' or '.db-' in p.name or p.name.endswith('.db.lock'))}


def disk_state(path):
    conn = sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True)
    try:
        return {'simulation': json.loads(conn.execute('SELECT payload FROM simulation_state WHERE id=1').fetchone()[0]),
                'runtime': {str(rid): json.loads(payload) for rid, payload in
                            conn.execute('SELECT request_id,payload FROM request_runtime')},
                'integrity': conn.execute('PRAGMA quick_check').fetchone()[0]}
    finally:
        conn.close()


def request_numbers(labels):
    """요구량 제목 다음 숫자를 읽습니다. 숫자·단위는 별개 Tk 라벨입니다."""
    lines = labels.splitlines()
    return tuple(int(lines[lines.index(title)+1].strip()) for title in ('GPU 요구량', '전력 요구량'))


def intersection(a, b):
    box = (max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3]))
    return box if box[0] < box[2] and box[1] < box[3] else None


class OcclusionWatch:
    """창 제목·PID·핸들을 보존하지 않는 가림 구간 기록. 시계는 호출자가 제공합니다."""
    def __init__(self):
        self.events, self.current = [], None

    def observe(self, regions, now, step):
        if regions:
            if self.current is None:
                self.current = {'start': now, 'step': step, 'status': 'blocked', 'samples': []}
                self.events.append(self.current)
            event = self.current
            if not event['samples'] or event['samples'][-1]['regions'] != regions:
                event['samples'].append({'t': now, 'regions': regions})
            event['duration'] = round(now-event['start'], 3)
        elif self.current is not None:
            self.current.update(end=now, duration=round(now-self.current['start'], 3), status='cleared')
            self.current = None
        return self.current is not None and self.current['duration'] >= 5


class StoryHarness(Harness):
    """공용/튜토리얼 코드는 보존하고 이번 실행에만 더 엄격한 입력·캡처 보호를 적용."""
    def __init__(self, out_dir):
        super().__init__(out_dir)
        self.watch, self.guard_lock = OcclusionWatch(), threading.Lock()
        self.occlusions = self.watch.events

    def calibrate(self):
        # 백그라운드 실행 셸에서 띄운 Tk가 다른 앱 뒤에 남지 않게 자체 창만 최초 한 번 활성화합니다.
        hwnd = self.call(lambda: user32.GetAncestor(self.root.winfo_id(), 2))
        before = user32.GetForegroundWindow() == hwnd
        self.call(lambda: (self.root.lift(), self.root.focus_force()))
        time.sleep(.4)
        self.activation = {'foreground_before': before, 'foreground_after': user32.GetForegroundWindow() == hwnd,
                           'own_window_activated_once': True}
        return super().calibrate()

    def root_bounds(self):
        import ctypes.wintypes as wt
        hwnd = user32.GetAncestor(self.root.winfo_id(), 2)
        rect, point = wt.RECT(), POINT(0, 0)
        user32.GetClientRect(hwnd, ctypes.byref(rect))
        user32.ClientToScreen(hwnd, ctypes.byref(point))
        bounds = self.phys((point.x, point.y, point.x+rect.right, point.y+rect.bottom))
        return hwnd, bounds

    def foreign_regions(self):
        """루트 위 외부 창의 교차 영역만 조회. 감시·클릭에서 같은 전체 루트 영역을 검사합니다."""
        import ctypes.wintypes as wt
        hwnd, bounds = self.root_bounds()
        foreign, found_root = [], []
        callback_type = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

        def visit(other, _):
            if other == hwnd:
                found_root.append(True)
                return False
            if user32.IsWindowVisible(other) and window_pid(other) != os.getpid():
                cloaked = wt.DWORD()
                ctypes.windll.dwmapi.DwmGetWindowAttribute(other, 14, ctypes.byref(cloaked), ctypes.sizeof(cloaked))
                if not cloaked.value:
                    r = self.phys(window_rect(other))
                    overlap = intersection(r, bounds)
                    if overlap:
                        foreign.append({'window_rect': r, 'overlap': overlap,
                                        'overlap_pixels': (overlap[2]-overlap[0])*(overlap[3]-overlap[1])})
            return True
        user32.EnumWindows(callback_type(visit), 0)
        if not found_root:
            raise AbortQA('게임 루트 창의 Z 순서 확인 불가')
        now = round(time.perf_counter()-self.t0, 3)
        with self.guard_lock:
            expired = self.watch.observe(foreign, now, self.step)
        return foreign, expired

    def wait_clear(self):
        """최대 5초만 기다리며 외부 앱의 창·포커스를 변경하지 않습니다."""
        deadline, clear_since, waited = time.monotonic()+5, None, False
        while True:
            regions, expired = self.foreign_regions()
            now = time.monotonic()
            if not regions:
                clear_since = now if clear_since is None else clear_since
                if not waited or now-clear_since >= .3:
                    return
            else:
                clear_since, waited = None, True
            if expired or now >= deadline:
                raise AbortQA('외부 창 가림이 지속되어 입력·캡처 중단(최대 5초 대기)')
            time.sleep(.1)

    def _grab(self, bbox_phys=None):
        if bbox_phys is None:  # calibrate의 메모리 내 해상도 측정(저장하지 않음)
            return super()._grab()
        _, bounds = self.root_bounds()
        box = intersection(bbox_phys, bounds)
        box = intersection(box, self.phys(self.work_area())) if box else None
        if box is None:
            raise AbortQA('게임 클라이언트 바깥 캡처 중단')
        if self.foreign_regions()[0]:
            raise AbortQA('외부 창 가림 중 캡처 금지')
        frame = super()._grab(box)
        if self.foreign_regions()[0]:
            raise AbortQA('캡처 도중 외부 창 등장: 프레임 폐기')
        return frame

    def shot(self, *args, **kwargs):
        self.wait_clear()
        return super().shot(*args, **kwargs)

    def click(self, item, dx=None, dy=None, settle=.6):
        self.wait_clear()
        # 현재 좌표를 다시 조회합니다. 가려진 위젯이나 화면 밖은 대체 좌표를 추측하지 않습니다.
        if item.get('path'):
            item = self.call(lambda: self.widget_info(self.root.nametowidget(item['path'])))
        if any(item.get(k) for k in ('offscreen', 'covered')) or not item.get('inside_top', True):
            raise AbortQA('보이지 않는 버튼 클릭 중단: '+item['text'])
        x = item['x']+(item['w']//2 if dx is None else dx)
        y = item['y']+(item['h']//2 if dy is None else dy)
        expected = self.call(lambda: user32.GetAncestor(self.root.nametowidget(item['top']).winfo_id(), 2))
        if owner_at(x, y)[1] != os.getpid() or user32.GetAncestor(owner_at(x, y)[0], 2) != expected:
            raise AbortQA('다른 창이 클릭 좌표를 차지함: 입력 없이 중단')
        user32.SetCursorPos(x, y)
        time.sleep(.08)
        if self.foreign_regions()[0]:
            self.wait_clear()
        if owner_at(x, y)[1] != os.getpid() or user32.GetAncestor(owner_at(x, y)[0], 2) != expected:
            raise AbortQA('입력 직전 창 변경: 클릭 중단')
        _mouse(MOUSEEVENTF_LEFTDOWN)
        time.sleep(.06)
        _mouse(MOUSEEVENTF_LEFTUP)
        self.clicks += 1
        self.note(f"실제 클릭 ({x},{y}) '{item['text'][:40]}'")
        time.sleep(.15)
        self.park()
        time.sleep(settle)

    def scroll_to(self, top_path, target_path, direction):
        """스크롤바 화살표를 실제 클릭. Tk yview/see/event_generate로 이동하지 않습니다."""
        def status():
            top, target = self.root.nametowidget(top_path), self.root.nametowidget(target_path)
            return {'visible': widget_visible(target), 'view': top.scroll.canvas.yview(),
                    'scrollbar': self.widget_info(top.scroll.scrollbar)}
        history = []
        for _ in range(16):
            current = self.call(status)
            history.append({k:v for k,v in current.items() if k != 'scrollbar'})
            ready = current['visible'] if direction == 'down' else current['view'][0] <= .001
            if ready:
                return history
            bar = current['scrollbar']
            self.click(bar, dy=bar['h']-8 if direction == 'down' else 8, settle=.08)
        raise AbortQA('실제 스크롤 16회 내 대상 접근/원위치 복귀 실패')


def scenario(h):
    app = lambda: h.selector.app
    session = lambda: app().session

    def state(rid):
        s, r = session(), session().runs[rid]
        alloc = s.servers.allocations.get(r.playthrough_id)
        return {'id': rid, 'country': r.mission['country'], 'company': r.mission['company_name'],
                'scenario': r.state.scenario, 'conditions': r.conditions, 'terms': dict(r.terms),
                'plans': r.state.plans, 'work_total': r.state.work_total, 'work_done': r.state.work_done,
                'estimated_minutes': r.state.estimate_minutes(r.state.plan or 'performance'),
                'minute': s.minute, 'elapsed': r.state.elapsed, 'phase': r.state.phase,
                'status': r.request['status'], 'succeeded': r.state.succeeded, 'score': r.state.score,
                'progress': r.state.progress, 'plan': r.state.plan,
                'avail': s.servers.available(), 'center': (s.center.available_gpu(), s.center.available_power()),
                'ledger': [asdict(x) for x in alloc.slices] if alloc else [],
                'step': s.story.onboarding.step, 'selected_id': s.selected_id,
                'request_ids': list(s.story.onboarding.request_ids), 'completed': list(s.story.onboarding.completed)}

    def check(item, ok, detail=''):
        h.check(h.step, item, ok, str(detail))

    def geometry(part=None):
        snap = h.snapshot()
        # 스크롤 본문 밖의 라벨은 별도 후보로 보존하고 실제 스크롤 접근 검사로 판정합니다.
        def clipped_paths():
            paths = set()
            for top in snap['tops']:
                for item in top['buttons']+top['labels']:
                    w = h.root.nametowidget(item['path'])
                    parent = w.master
                    while parent is not None:
                        if parent.winfo_class() == 'Canvas' and hasattr(parent.master, 'scrollbar'):
                            viewport = (parent.winfo_rootx(), parent.winfo_rooty(),
                                        parent.winfo_rootx()+parent.winfo_width(), parent.winfo_rooty()+parent.winfo_height())
                            rect = (item['x'], item['y'], item['x']+item['w'], item['y']+item['h'])
                            if intersection(rect, viewport) != rect:
                                paths.add(item['path'])
                        parent = parent.master
            return paths
        clipped = h.call(clipped_paths)
        issues, deferred = [], []
        for top in snap['tops']:
            if part and part not in top['title']:
                continue
            for item in top['buttons']+top['labels']:
                flags = [k for k in ('covered', 'offscreen', 'clipped_text') if item[k]]
                if not item['inside_top']:
                    flags.append('outside_window')
                if flags:
                    record = {'window': top['title'], 'path': item['path'], 'text': item['text'], 'flags': flags}
                    (deferred if item['path'] in clipped and 'clipped_text' not in flags else issues).append(record)
        h.layouts.append({'step': h.step, 'window': part, 'issues': issues, 'scroll_candidates': deferred, 'snapshot': snap})
        check('버튼·라벨 가려짐/잘림/화면 밖 없음'+(' · '+part if part else ''), not issues, issues)
        if part:
            placement(h, part)
            offset = centered(h, part)
            check('대화창 중앙 배치 ±8px · '+part, offset is not None and max(map(abs, offset)) <= 8, offset)

    def goal(number, step):
        data = h.call(lambda: {'step': session().story.onboarding.step,
                              'job': session().story.onboarding.card['job'],
                              'action': app().goal_card.action.cget('text'),
                              'kicker': app().goal_card.kicker.cget('text'),
                              'highlight': app().tutorial_highlight.key,
                              'edges': len(app().tutorial_highlight.edges)})
        h.goals.append(data)
        check('고객별 목표 카드와 현재 업무·단계 일치', data['step'] == step and data['job'] == (number, 3)
              and f'업무 {number}/3' in data['kicker'], data)
        check('스토리에서 튜토리얼 금색 강조 잔존 없음(설계상 비활성)', data['edges'] == 0, data['highlight'])

    def lists():
        def read():
            return {name: {'selected': tree.selection(), 'height': tree.winfo_height(),
                           'rows': [{'id': rid, 'values': tree.item(rid, 'values'), 'bbox': tree.bbox(rid)}
                                    for rid in tree.get_children()]}
                    for name, tree in (('inbox', app().inbox), ('active', app().active_list))}
        return h.call(read)

    h.step = '시작 메뉴'
    h.env = h.call(lambda: {'tk': h.root.tk.call('info', 'patchlevel'), 'scaling': float(h.root.tk.call('tk', 'scaling')),
                            'screen': [h.root.winfo_screenwidth(), h.root.winfo_screenheight()], 'work_area': h.work_area(),
                            'capture_scale': h.scale})
    geometry()
    h.click(h.call(lambda: h.widget_info(h.selector.buttons['story'])))
    geometry()
    h.shot('story_menu', note='스토리 도전 · 제1장 새 시작 메뉴')
    h.click_text('새 도전 시작', settle=1.3)
    h.wait_for(lambda: top_by_title(h.snapshot(), '현장 교육'), what='제1장 시작 안내')
    check('정규 스토리·첫 근무·임시 슬롯', h.call(lambda: session().mode == 'story' and session().story.onboarding.kind == 'shift'
          and app().db.path.parent == h.tmp))
    h.slot = h.call(lambda: app().db.path)
    from aidc.storage.checkpoints import checkpoint_path
    checkpoint = checkpoint_path(h.slot, 1)
    h.checkpoint_hash = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    initial = disk_state(checkpoint)
    check('제1장 시작 체크포인트 존재·정상 SQLite·안내 전 상태', initial['integrity'] == 'ok'
          and initial['simulation']['story']['onboarding']['step'] == 'arrival')
    h.step = '제1장 안내'
    geometry('현장 교육')
    h.shot('guide', note='선배 엔지니어 첫 근무 안내')
    h.dialogue_pages = []
    for index, (_, expected) in enumerate(h.call(lambda: session().story.onboarding.pages)):
        top = top_by_title(h.snapshot(), '현장 교육')
        shown = top['texts'][0]
        h.dialogue_pages.append(shown)
        check(f'첫 근무 안내 {index+1}/4 본문', shown == expected)
        if index < 3:
            h.click_text('다음 ▶', top=top['path'])
    h.click_text('첫 업무 시작', settle=1)

    for index, country in enumerate(('싱가포르', '일본', '미국'), 1):
        h.step = f'{index} {country} 요청'
        rid = h.call(lambda: session().story.onboarding.rid)
        job = {'request': h.call(lambda: state(rid)), 'frames': []}
        h.jobs.append(job)
        request = job['request']
        job['request_lists'] = lists()
        check('요청 순서·독립 접수·직전 완료 고객 수', request['country'] == country
              and len(request['request_ids']) == index and len(request['completed']) == index-1, request)
        check('새 고객은 진행 0·미배정·전체 자원 가용', request['progress'] == 0 and request['plan'] is None
              and request['avail'] == request['center'] == (10, 10) and not request['ledger'])
        inbox = job['request_lists']['inbox']
        row = next((r for r in inbox['rows'] if r['id'] == str(rid)), None)
        check('새 고객 요청함 행 생성·현재 선택 일치', row is not None and str(rid) in inbox['selected'], inbox)
        check('새 고객 요청함 행이 스크롤 없이 실제 노출', bool(row and row['bbox']), row)
        goal(index, 'request')
        geometry()
        h.click_text('요청 확인', settle=1)
        h.wait_for(lambda: top_by_title(h.snapshot(), 'AIDC LINK |'), what='고객 요청서')
        top = top_by_title(h.snapshot(), 'AIDC LINK |')
        labels = '\n'.join(x['text'] for x in top['labels'])
        h.shot(f'{index}_request', note=f'{country} 고객의 실제 조건·기한')
        geometry('AIDC LINK |')
        p = request['plans']['performance']
        check('고객 요청서 GPU·전력 수치 = 실제 고성능 조건',
              request_numbers(labels) == (p['gpu'], p['power']), labels)
        job['request_labels'] = labels
        h.click_text('확인 · 운영실로', settle=1)
        check('요청서 확인 한 번에 닫힘', not top_by_title(h.snapshot(), 'AIDC LINK |'))
        if top_by_title(h.snapshot(), 'AIDC LINK |'):
            h.click_text('확인 · 운영실로')
        goal(index, 'preview')
        h.step = f'{index} {country} 배정'
        h.click_text('배정 설정·선택', settle=1)
        geometry('배정 설정')
        check('선택 전 시작 버튼 비활성', h.find('선택한 계획으로 작업 시작')['state'] == 'disabled')
        rows = h.call(lambda: app().allocation_window.mode_rows)
        job['mode_rows'] = rows
        # 고객 원래 요청을 따르되, UI가 계산한 실행 가능·기한 준수 조건부터 확인합니다.
        mode = next(row for row in rows if row['key'] == 'performance')
        check('선택 모드가 고객 허용·기한 내 실행 가능', mode['agreed'] and mode['on_time'] and not mode['reason'], mode)
        if not (mode['agreed'] and mode['on_time'] and not mode['reason']):
            raise AbortQA('계획한 정상 경로 실행 불가: 화면/사유를 기록하고 중단')
        h.click(h.call(lambda: h.widget_info(app().allocation_window.mode_buttons['performance'])))
        job['selected_plan'] = h.call(lambda: [asdict(x) for x in app().allocation_window.options[0]])
        h.click_text('배정안 1 (추천)')
        preview = h.call(lambda: state(rid))
        check('모드·배정안 조회/선택은 GPU·전력 미점유', preview['avail'] == preview['center'] == (10, 10) and not preview['ledger'])
        h.shot(f'{index}_allocation', note=f'{country} 고성능·배정안 1 선택(시작 전 미점유)')
        top_path, notice_path = h.call(lambda: (str(app().allocation_window), str(app().allocation_window.notice)))
        probe = {'before_visible': h.call(lambda: widget_visible(app().allocation_window.notice))}
        probe['down'] = h.scroll_to(top_path, notice_path, 'down')
        probe['after_visible'] = h.call(lambda: widget_visible(app().allocation_window.notice))
        check('배정창 설명은 실제 스크롤로 접근 가능', probe['after_visible'], probe)
        probe['up'] = h.scroll_to(top_path, notice_path, 'up')
        job['scroll_probe'] = probe
        h.click_text('선택한 계획으로 작업 시작', settle=1)
        started = job['started'] = h.call(lambda: state(rid))
        check('실제 실행·진행 0·선택한 GPU 슬롯/전력 원장과 일치', started['phase'] == 'running'
              and started['progress'] == 0 and started['ledger'] == job['selected_plan'], started)
        check('서버 가용·전체 가용·요구 자원 차감 일치', started['avail'] == started['center'] == (10-p['gpu'], 10-p['power']))
        goal(index, 'time')
        h.step = f'{index} {country} 시간 진행'
        # 실제 예상 시간에서 유한 클릭 횟수를 계산. 고객별 완료 시간을 하드코딩하지 않습니다.
        limit = (started['estimated_minutes']+9)//10
        for tick in range(limit):
            baseline = h.white_ratio(h.call(lambda: (h.root.winfo_rootx(), h.root.winfo_rooty(),
                    h.root.winfo_rootx()+h.root.winfo_width(), h.root.winfo_rooty()+h.root.winfo_height())))
            thread, frames = h.burst(seconds=1.3)
            h.click_text('+10분', settle=.4)
            thread.join(timeout=4)
            if thread.is_alive():
                raise AbortQA('화면 관측 스레드 종료 지연')
            current = h.call(lambda: state(rid))
            sample = {'tick': tick+1, 'state': current, 'baseline_white': baseline,
                      'frames': [{k:v for k,v in f.items() if k != 'img'} for f in frames]}
            job['frames'].append(sample)
            check(f'+10분 #{tick+1}: 작업량·가상 시간·경과 시간 증가',
                  current['minute'] == started['minute']+10*(tick+1) and current['elapsed'] == 10*(tick+1)
                  and current['work_done'] > (job['frames'][-2]['state']['work_done'] if tick else 0), current)
            if tick == 0:
                h.shot(f'{index}_running', note=f'{country} +10분 실제 진행률 {current["progress"]:.1f}%')
                geometry()
            if current['status'] == 'completed':
                break
        final = job['completed'] = h.call(lambda: state(rid))
        check('예측 시간과 실제 처리 시간 일치·정상 완료', final['status'] == 'completed' and final['succeeded']
              and final['elapsed'] == started['estimated_minutes'] and final['progress'] == 100, final)
        check('완료 후 GPU·전력 모두 반환·수행 원장 제거', final['avail'] == final['center'] == (10, 10) and not final['ledger'])
        persisted = disk_state(h.slot)
        check('각 완료가 디스크 runtime·onboarding에 저장됨', persisted['integrity'] == 'ok'
              and persisted['runtime'][str(rid)]['state']['succeeded']
              and rid in persisted['simulation']['story']['onboarding']['completed'])
        check('장 시작 체크포인트 내용 보존', hashlib.sha256(checkpoint.read_bytes()).hexdigest() == h.checkpoint_hash)
        job['completed_lists'] = lists()
        if index < 3:
            h.shot(f'{index}_completed_next_arrival', note=f'{country} 완료·자원 반환·다음 고객 접수')

    h.step = '제1장 결과'
    check('세 고객 정상 완료·제1장 클리어·다음 장 미시작', h.call(lambda: session().story.chapter1_cleared
          and session().story.onboarding.done and len(session().story.onboarding.completed) == 3 and session().story.chapter2 is None))
    # 자동 결과창은 정상 UI의 [X]로 닫아 관제실을 기록한 뒤 [근무 결과]로 다시 엽니다.
    result_top = top_by_title(h.snapshot(), '결과')
    if result_top:
        hwnd = h.call(lambda: int(h.root.nametowidget(result_top['path']).wm_frame(), 16))
        left, top, right, _ = window_rect(hwnd)
        h.click({'x': right-30, 'y': top+15, 'w': 0, 'h': 0, 'text': '결과창 [X]', 'top': result_top['path']})
    h.shot('all_completed', note='세 업무 완료·GPU 전력 반환 직후 관제실')
    geometry()
    h.click_text('근무 결과')
    h.wait_text('MISSION SUCCESS')
    h.chapter_result = h.call(lambda: session().chapter_result())
    geometry('결과')
    top = top_by_title(h.snapshot(), '결과')
    h.result_screen = top
    check('성공 결과창·3/3·평균 점수·자원 반환 표시', 'MISSION SUCCESS' in [x['text'] for x in top['labels']]
          and '3/3건' in [x['text'] for x in top['labels']], h.chapter_result)
    check('제2장 시작 버튼 활성·다음 근무 안내 표시', any('제2장' in b['text'] and b['state'] == 'normal' for b in top['buttons'])
          and any('다음 근무' in x['text'] for x in top['labels']))
    # 결과창 본문의 다음 장 안내까지 실제 스크롤로 읽고, 제2장 시작 버튼은 누르지 않습니다.
    result_path, next_path = h.call(lambda: (str(app().chapter_window), str(app().chapter_window.next_notice)))
    h.result_scroll = h.scroll_to(result_path, next_path, 'down')
    check('결과창 다음 근무 안내 실제 접근 가능', h.call(lambda: widget_visible(app().chapter_window.next_notice)))
    h.shot('success', note='실제 제1장 성공 결과·다음 장 안내(이동하지 않음)')
    h.final_disk = disk_state(h.slot)
    check('최종 저장에 세 고객 성공·완료 이력·제2장 미시작', len(h.final_disk['runtime']) == 3
          and all(r['state']['succeeded'] for r in h.final_disk['runtime'].values())
          and len(h.final_disk['simulation']['story']['onboarding']['completed']) == 3
          and not h.final_disk['simulation']['story'].get('chapter2'))
    h.completed = True


def self_check():
    from game import GameState
    from aidc.story.onboarding import COUNTRIES
    assert COUNTRIES == ('싱가포르', '일본', '미국')
    assert request_numbers('GPU 요구량\n3\n 개\n전력 요구량\n4\n 단위') == (3, 4)
    assert intersection((0, 0, 10, 10), (5, 5, 20, 20)) == (5, 5, 10, 10)
    assert intersection((0, 0, 10, 10), (10, 0, 20, 10)) is None
    watch = OcclusionWatch()
    regions = [{'overlap': (1, 1, 2, 2)}]
    assert not watch.observe(regions, 1, 'click') and watch.current is not None
    assert not watch.observe([], 2, 'click') and watch.current is None
    assert watch.events[0]['duration'] == 1 and watch.events[0]['status'] == 'cleared'
    assert not watch.observe(regions, 3, 'shot')
    assert watch.observe(regions, 8, 'shot') and watch.current is not None
    for country, scenario_name in zip(COUNTRIES, ('intro_sg_v1', 'intro_jp_v1', 'intro_us_v1')):
        state = GameState(country=country, scenario=scenario_name)
        assert state.work_total == 30 and state.estimate_minutes('performance') == 30
    with tempfile.TemporaryDirectory(prefix='srs_qa_self_') as tmp:
        path = Path(tmp)/'sample.db'
        conn = sqlite3.connect(path)
        conn.executescript('CREATE TABLE simulation_state(id,payload); CREATE TABLE request_runtime(request_id,payload);'
                           'INSERT INTO simulation_state VALUES(1,\'{"story":{}}\');')
        conn.close()
        before = path.read_bytes()
        assert disk_state(path) == {'simulation': {'story': {}}, 'runtime': {}, 'integrity': 'ok'}
        assert path.read_bytes() == before
    print('QA self-check PASS: 시나리오 조회/import·읽기 전용 SQLite')


def main():
    if '--self-check' in sys.argv:
        self_check()
        return
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.gettempdir())/'srs_qa_story_002'
    out.mkdir(parents=True, exist_ok=True)
    # 덮어쓰기/암묵적 반복 실행 금지. 재실행은 새로운 출력 디렉터리를 명시해야 합니다.
    marker = out/'attempt.json'
    with marker.open('x', encoding='utf-8') as f:
        json.dump({'started': datetime.now(ZoneInfo('Asia/Seoul')).isoformat(timespec='seconds')}, f)
    print('실제 GUI 자동 플레이 1회: 마우스/키보드를 사용하지 마세요.', flush=True)
    before = db_hashes()
    h = StoryHarness(out)
    h.env, h.placements, h.layouts, h.goals, h.jobs = {}, [], [], [], []
    error = None
    try:
        error = h.run(scenario)['error']
    except BaseException as exc:
        error = f'{type(exc).__name__}: {exc}'
    finally:
        after = db_hashes()
        h.check('보존', '사용자 DB·슬롯·체크포인트·보조 파일 해시/파일 집합 동일', before == after,
                f'기존 파일 {len(before)}개 / 실행 후 {len(after)}개')
        if getattr(h, 'slot', None) and h.slot.exists():
            saved = disk_state(h.slot)
            h.check('종료 저장', '정상 종료 뒤 임시 SQLite 무결성', saved['integrity'] == 'ok')
        assert h.tmp.resolve().parent == Path(tempfile.gettempdir()).resolve() and h.tmp.name.startswith('srs_qa_')
        removed = h.cleanup()
        report = {'started': json.loads(marker.read_text(encoding='utf-8'))['started'],
                  'commit': subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip(),
                  'python': platform.python_version(), 'os': platform.system()+' '+platform.release(), 'env': h.env,
                  'completed': getattr(h, 'completed', False), 'error': error, 'clicks': h.clicks,
                  'passed': sum(c['result'] == 'PASS' for c in h.checks), 'failed': sum(c['result'] == 'FAIL' for c in h.checks),
                  'repo_db_unchanged': before == after, 'repo_db_count': len(before), 'temp_files_removed': removed,
                  'checks': h.checks, 'jobs': h.jobs, 'goals': h.goals, 'layouts': h.layouts, 'placements': h.placements,
                  'chapter_result': getattr(h, 'chapter_result', None), 'result_screen': getattr(h, 'result_screen', None),
                  'final_disk': getattr(h, 'final_disk', None), 'result_scroll': getattr(h, 'result_scroll', None),
                  'qa_source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  'shots': h.shots, 'window_events': getattr(getattr(h, 'monitor', None), 'events', []),
                  'capture_occlusions': h.occlusions,
                  'startup_activation': getattr(h, 'activation', None),
                  'frame_offset_trace': h.frame_trace,
                  'log': [line.replace(str(ROOT), '<repo>').replace(str(h.tmp), '<qa-temp>') for line in h.log]}
        (out/'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
        print(f'완주={report["completed"]} 오류={error} PASS={report["passed"]} FAIL={report["failed"]} 클릭={h.clicks}', flush=True)
    raise SystemExit(bool(error or report['failed'] or not report['completed']))


if __name__ == '__main__':
    main()
