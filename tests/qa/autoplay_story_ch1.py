"""story-001: 기존 하네스로 제1장을 실제 마우스 입력으로 한 번 플레이합니다.

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
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gui_driver import (ROOT, AbortQA, Harness, POINT, _mouse, owner_at,
                        user32, window_pid, window_rect, MOUSEEVENTF_LEFTDOWN,
                        MOUSEEVENTF_LEFTUP)
from autoplay_tutorial import centered, layout_issues, placement, top_by_title


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


class StoryHarness(Harness):
    """공용/튜토리얼 코드는 보존하고 이번 실행에만 더 엄격한 입력·캡처 보호를 적용."""
    def _grab(self, bbox_phys=None):
        if bbox_phys is None:  # 기존 calibrate의 메모리 내 해상도 측정(저장하지 않음)
            return super()._grab()
        # 클라이언트 영역만 저장: 바깥 앱/작업 표시줄/투명 창틀을 제외합니다.
        import ctypes.wintypes as wt
        hwnd = user32.GetAncestor(self.root.winfo_id(), 2)
        rect, point = wt.RECT(), POINT(0, 0)
        user32.GetClientRect(hwnd, ctypes.byref(rect))
        user32.ClientToScreen(hwnd, ctypes.byref(point))
        bounds = self.phys((point.x, point.y, point.x+rect.right, point.y+rect.bottom))
        work = self.phys(self.work_area())
        box = (max(bbox_phys[0], bounds[0], work[0]), max(bbox_phys[1], bounds[1], work[1]),
               min(bbox_phys[2], bounds[2], work[2]), min(bbox_phys[3], bounds[3], work[3]))
        if box[2] <= box[0] or box[3] <= box[1]:
            raise AbortQA('게임 클라이언트 바깥 캡처 중단')
        # EnumWindows는 Z 순서입니다. 루트 위 외부 창이 캡처 사각형과 겹치면 저장하지 않습니다.
        foreign = []
        callback_type = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

        def visit(other, _):
            if other == hwnd:
                return False
            if user32.IsWindowVisible(other) and window_pid(other) != os.getpid():
                cloaked = wt.DWORD()
                ctypes.windll.dwmapi.DwmGetWindowAttribute(other, 14, ctypes.byref(cloaked), ctypes.sizeof(cloaked))
                if not cloaked.value:
                    r = self.phys(window_rect(other))
                    if max(r[0], box[0]) < min(r[2], box[2]) and max(r[1], box[1]) < min(r[3], box[3]):
                        foreign.append(True)
            return True
        user32.EnumWindows(callback_type(visit), 0)
        if foreign:
            self.capture_blocked = True
            self.occlusions.append({'step': self.step, 't': round(time.perf_counter()-self.t0, 3),
                                    'capture_box': box})
            raise AbortQA('외부 창이 캡처 영역을 가려 화면 저장/추가 클릭 중단')
        return super()._grab(box)

    def click(self, item, dx=None, dy=None, settle=.6):
        if getattr(self, 'capture_blocked', False):
            raise AbortQA('외부 창 감지 후 입력 중단')
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
        issues = layout_issues(h, part)
        h.layouts.append({'step': h.step, 'window': part, 'issues': issues, 'snapshot': h.snapshot()})
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

    h.step = '시작 메뉴'
    h.env = h.call(lambda: {'tk': h.root.tk.call('info', 'patchlevel'), 'scaling': float(h.root.tk.call('tk', 'scaling')),
                            'screen': [h.root.winfo_screenwidth(), h.root.winfo_screenheight()], 'work_area': h.work_area(),
                            'capture_scale': h.scale})
    geometry()
    h.shot('title', note='실제 메인 메뉴')
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
        check('요청 순서·독립 접수·직전 완료 고객 수', request['country'] == country
              and len(request['request_ids']) == index and len(request['completed']) == index-1, request)
        check('새 고객은 진행 0·미배정·전체 자원 가용', request['progress'] == 0 and request['plan'] is None
              and request['avail'] == request['center'] == (10, 10) and not request['ledger'])
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
    h.shot('success', note='실제 제1장 성공 결과·다음 장 안내(이동하지 않음)')
    h.completed = True


def self_check():
    from game import GameState
    from aidc.story.onboarding import COUNTRIES
    assert COUNTRIES == ('싱가포르', '일본', '미국')
    assert request_numbers('GPU 요구량\n3\n 개\n전력 요구량\n4\n 단위') == (3, 4)
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
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.gettempdir())/'srs_qa_story_001'
    out.mkdir(parents=True, exist_ok=True)
    # 덮어쓰기/암묵적 반복 실행 금지. 재실행은 새로운 출력 디렉터리를 명시해야 합니다.
    marker = out/'attempt.json'
    with marker.open('x', encoding='utf-8') as f:
        json.dump({'started': datetime.now(ZoneInfo('Asia/Seoul')).isoformat(timespec='seconds')}, f)
    print('실제 GUI 자동 플레이 1회: 마우스/키보드를 사용하지 마세요.', flush=True)
    before = db_hashes()
    h = StoryHarness(out)
    h.env, h.placements, h.layouts, h.goals, h.jobs, h.occlusions = {}, [], [], [], [], []
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
                  'shots': h.shots, 'window_events': getattr(getattr(h, 'monitor', None), 'events', []),
                  'capture_occlusions': h.occlusions,
                  'frame_offset_trace': h.frame_trace,
                  'log': [line.replace(str(ROOT), '<repo>').replace(str(h.tmp), '<qa-temp>') for line in h.log]}
        (out/'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
        print(f'완주={report["completed"]} 오류={error} PASS={report["passed"]} FAIL={report["failed"]} 클릭={h.clicks}', flush=True)
    raise SystemExit(bool(error or report['failed'] or not report['completed']))


if __name__ == '__main__':
    main()
