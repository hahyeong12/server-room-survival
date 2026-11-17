"""chapter4-001: native regular Chapter 1→2→3→4; no Chapter 5/Lab entry.

--focus <new-dir> tests only the new input flow in an isolated practice fixture.
<new-dir> <focus-result.json> runs one regular play, gated by the focused source hash.
--self-check opens no windows. Gameplay mutations use native mouse input only.
"""
import hashlib
import json
import platform
import re
import subprocess
import sys
import tempfile
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autoplay_chapter3 as ch3
from autoplay_chapter3 import ch1, ch2, top_by_title, AbortQA, ROOT


def clock_minutes(text):
    match = re.search(r'D(\d+) (\d+):(\d+)', text)
    if not match:
        raise AbortQA('화면에 예상/기한 시각이 없습니다: '+text)
    day, hour, minute = map(int, match.groups())
    return (day-1)*1440+hour*60+minute


def resource_pair(text):
    match = re.search(r'GPU (\d+) / 전력 (\d+)', text)
    if not match:
        raise AbortQA('화면 자원 수치를 읽을 수 없습니다: '+text)
    return tuple(map(int, match.groups()))


def choice_from_cells(cells, reason):
    """Choose from displayed feasibility/resources/forecast, never mission index or id."""
    normal = resource_pair(cells['정상 서버 가용'])
    needed = resource_pair(cells['필요 자원'])
    due = clock_minutes(cells['고객 완료 기한'])
    repair = clock_minutes(cells['장비 복구 예상'])
    if cells['작업 이전'] == '가능':
        migrate = clock_minutes(cells['작업 이전 예상'])
        if all(a >= b for a, b in zip(normal, needed)) and migrate <= due and migrate < repair:
            return 'migrate', f'정상 서버 {normal}로 작업 {needed} 이전 가능. 예상 {migrate} ≤ 기한 {due}, 복구 예상 {repair}보다 빠름.'
    elif cells['작업 이전'] == '불가능' and repair <= due and reason.strip():
        return 'repair', f'전체 이전 불가능: {reason}. 복구 예상 {repair} ≤ 기한 {due}.'
    raise AbortQA('진단 화면 근거로 기한 내 대응을 선택할 수 없습니다: '+repr(cells))


def play_chapter4(h, focused=False):
    app = lambda: h.selector.app
    session = lambda: app().session
    check = lambda item, ok, detail='': h.check(h.step, item, ok, detail)
    h.completed = False
    h.chapter4_data = data = {'guides': [], 'feedback': [], 'missions': [], 'ticks': [], 'row_access': []}

    def state():
        def read():
            from server_console import server_views
            s = session()
            jobs = []
            for rid in s.story.chapter3b.request_ids:
                r = s.runs[rid]
                a = s.servers.allocations.get(r.playthrough_id)
                fields = ('scenario', 'plan', 'phase', 'work_done', 'work_total', 'elapsed', 'progress', 'score', 'succeeded',
                          'network_needed', 'network_available', 'incident_kind')
                jobs.append({'id': rid, 'country': r.mission['country'], 'conditions': dict(r.conditions),
                             'terms': dict(r.terms), 'plans': r.state.plans, 'proposals': list(r.proposals),
                             'status': r.request['status'], 'playthrough_id': r.playthrough_id,
                             'ledger': [asdict(p) for p in a.slices] if a else [],
                             'allocation_history': [asdict(a) for a in r.server_allocations],
                             'faulted': s.hardware_servers(r), 'migration_left': r.migration_left,
                             'hardware_downtime': r.hardware_downtime, 'migration_downtime': r.migration_downtime,
                             **{key: getattr(r.state, key) for key in fields}})
            views = [{key: asdict(v) if key == 'spec' else v for key, v in view.items()}
                     for view in server_views(s)]
            return {'minute': s.minute, 'practice': s.story.practice, 'chapter4': asdict(s.story.chapter3b),
                    'chapter5': s.story.training, 'jobs': jobs, 'available': s.servers.available(),
                    'used': (s.center.gpu_used, s.center.power_used), 'server_views': views,
                    'center_available': (s.center.available_gpu(), s.center.available_power()),
                    'ledger_used': (sum(a.gpu for a in s.servers.allocations.values()),
                                    sum(a.power for a in s.servers.allocations.values())),
                    'hardware': {key: asdict(value) for key, value in s.servers.hardware.items()},
                    'action_hint': app().action_hint.cget('text'), 'objective': app().story_objective.cget('text')}
        return h.call(read)

    def guide():
        for _ in range(18):
            snap = h.snapshot()
            card = top_by_title(snap, 'FEEDBACK')
            if card:
                data['feedback'].append({'step': h.step, 'screen': card})
                h.shot('c4_feedback', note='실제 장비 대응 결과 카드')
                button = h.find('업무로 돌아가기', top=card['path']) or h.find('확인 · 다음 목표', top=card['path'])
                if not button:
                    raise AbortQA('예상하지 않은 결과 카드: '+card['title'])
                h.click(button)
                continue
            if not top_by_title(snap, '현장 교육'):
                return
            page = h.call(lambda: {'index': app().story_window.index,
                                  'body': app().story_window.bubble.get('1.0', 'end-1c'),
                                  'button': h.widget_info(app().story_window.next_button)})
            data['guides'].append({'step': h.step, 'index': page['index'], 'body': page['body']})
            h.click(page['button'], settle=.55)
        raise AbortQA('교육/결과 창 종료 한도 초과')

    def tick(label):
        before = state()
        thread, frames = h.burst(seconds=1.1)
        h.click_text('+10분', settle=.35)
        thread.join(timeout=4)
        if thread.is_alive():
            raise AbortQA('프레임 관측 종료 지연')
        after = state()
        data['ticks'].append({'label': label, 'state': after,
                              'frames': [{k: v for k, v in f.items() if k != 'img'} for f in frames]})
        conserved = all(sum(v[key+'_available']+v[key+'_used']+v[key+'_unavailable'] for v in after['server_views']) == 10
                        for key in ('gpu', 'power'))
        check(label+' 시간·자원 보존', after['minute'] == before['minute']+10
              and after['used'] == after['ledger_used'] and conserved, after)
        guide()
        return after

    h.step = '제4장 정규 진입' if not focused else '제4장 집중·독립 연습 fixture'
    if not focused:
        h.click_text('제4장 — 서버실의 경보 · 시작', settle=1)
    h.wait_for(lambda: top_by_title(h.snapshot(), '현장 교육'), what='제4장 브리핑')
    initial = state()
    data['initial'] = initial
    check('정규/fixture 구분·첫 요청·자원 미점유', initial['practice'] is focused
          and len(initial['jobs']) == 1 and initial['jobs'][0]['scenario'] == 'ch3b_jp'
          and initial['available'] == (10, 10) and h.call(lambda: app().db.path == h.slot))
    from aidc.storage.checkpoints import checkpoint_path
    checkpoint = checkpoint_path(h.slot, '3b')
    checkpoint_hash = hashlib.sha256(checkpoint.read_bytes()).hexdigest() if not focused else None
    check('정규 체크포인트/연습 미생성 구분', checkpoint.is_file() is (not focused))
    guide()

    for index in range(2):
        tag = 'AB'[index]
        h.step = '제4장 미션 '+tag+' 요청·시작'
        current = state()
        if len(current['jobs']) <= index:
            raise AbortQA('후속 요청 미접수')
        rid = current['jobs'][index]['id']
        mission = {'id': rid, 'before': current}
        data['missions'].append(mission)
        h.wheel_inbox(-1200)
        for _ in range(18):
            row = h.call(lambda: {'box': app().inbox.bbox(str(rid)), 'height': app().inbox.winfo_height(),
                                 'view': app().inbox.yview(), 'selected': app().inbox.selection(),
                                 'widget': h.widget_info(app().inbox)})
            data['row_access'].append({'id': rid, **row})
            if row['box'] and row['box'][1]+row['box'][3] <= row['height']:
                break
            h.wheel_inbox(120)
        else:
            raise AbortQA('실제 휠 고객 행 접근 실패')
        h.click(row['widget'], dy=row['box'][1]+row['box'][3]//2, settle=.8)
        if not top_by_title(h.snapshot(), 'AIDC LINK |'):
            h.click_text('고객 대화')
        h.wait_for(lambda: h.call(lambda: app().message_window.shown == len(app().message_window.full_text)),
                   timeout=30, what='고객 요청서 타이핑')
        for _ in range(30):
            def position():
                text = app().message_window.bubble
                found = text.search('요청 GPU:', '1.0')
                line = text.dlineinfo(found) if found else None
                return {'visible': bool(line and line[1]+line[3] <= text.winfo_height()-int(text.cget('pady'))-6),
                        'bar': h.widget_info(text.vbar)}
            pos = h.call(position)
            if pos['visible']:
                break
            h.click(pos['bar'], dy=pos['bar']['h']-8, settle=.08)
        else:
            raise AbortQA('고객 자원 본문 노출 실패')
        request = top_by_title(h.snapshot(), 'AIDC LINK |')
        mission['request'] = request
        job = state()['jobs'][index]
        labels = '\n'.join(x['text'] for x in request['labels'])
        p = job['plans']['performance']
        check('실제 요청 GPU·전력·네트워크·허용 표시', ch1.request_numbers(labels) == (p['gpu'], p['power'])
              and f'네트워크: {p["network"]}단위' in '\n'.join(request['texts']) and '허용 운영 모드' in labels)
        h.shot('c4_'+tag+'_request', note='고객 요청·원래 허용 조건·기한')
        h.click_text('확인 · 운영실로')
        guide()
        if 'performance' not in job['conditions']['allowed_modes']:
            raise AbortQA('고성능은 실제 고객 허용 범위 밖입니다. 무단 실행하지 않습니다.')
        h.click(h.call(lambda: h.widget_info(app().mode_buttons['performance'])))
        h.click_text('배정 설정·선택')
        rows = h.call(lambda: app().allocation_window.mode_rows)
        mission['allocation_modes'] = rows
        check('원래 허용 고성능·시작 가능', rows[0]['agreed'] and not rows[0]['reason'])
        h.click_text('배정안 1 (추천)')
        chosen = h.call(lambda: [asdict(p) for p in app().allocation_window.options[0]])
        mission['chosen'] = chosen
        h.shot('c4_'+tag+'_allocation', note='허용 고성능의 실제 서버 배정 선택')
        h.click_text('선택한 계획으로 작업 시작')
        guide()
        started = state()
        mission['started'] = started
        check('실제 시작·슬롯 일치', started['jobs'][index]['phase'] == 'running'
              and started['jobs'][index]['ledger'] == chosen and started['used'] == (p['gpu'], p['power']))

        h.step = '제4장 미션 '+tag+' 장비 장애·진단'
        for n in range(12):
            if state()['jobs'][index]['faulted']:
                break
            tick('장애 전 진행'+str(n+1))
        else:
            raise AbortQA('장비 장애 미발생')
        fault = state()
        mission['fault'] = fault
        controls = h.call(lambda: {k: h.widget_info(v) for k, v in app().action_buttons.items()})
        mission['before_diagnosis_controls'] = controls
        check('진단 전 복구·이전 잠금·네트워크 장애와 분리',
              all(controls[k]['state'] == 'disabled' for k in ('hwrepair', 'migrate'))
              and fault['jobs'][index]['incident_kind'] is None and fault['used'] == started['used'])
        h.shot('c4_'+tag+'_fault', note='FAULT 서버·GPU 표시·장비 중단·네트워크와 구분')
        h.click(controls['hwdiag'])
        h.wait_for(lambda: top_by_title(h.snapshot(), '장비 진단'), what='실제 장비 진단창')
        h.shot('c4_'+tag+'_diagnosis_top', note='장비 진단창 첫 화면 원본')
        seen = []
        for name in ('장애 서버', '정상 서버 가용', '필요 자원', '작업 이전', '장비 복구 예상', '작업 이전 예상', '고객 완료 기한'):
            top_path, path = h.call(lambda n=name: (str(app().diagnosis_window), str(app().diagnosis_window.cells[n])))
            seen.append({'cell': name, 'scroll': h.scroll_to(top_path, path, 'down')})
        cells = h.call(lambda: {k: v.cget('text') for k, v in app().diagnosis_window.cells.items()})
        reason = h.call(lambda: app().diagnosis_window.reason_label.cget('text'))
        if reason:
            top_path, path = h.call(lambda: (str(app().diagnosis_window), str(app().diagnosis_window.reason_label)))
            seen.append({'cell': '이전 불가 사유', 'scroll': h.scroll_to(top_path, path, 'down')})
        mission['diagnosis'] = {'cells': cells, 'reason': reason,
                                'visible_rows': seen,
                                'screen': top_by_title(h.snapshot(), '장비 진단')}
        h.shot('c4_'+tag+'_diagnosis', note='장애/정상 서버·필요 자원·복구/이전 예상 시각·기한')
        choice, why = choice_from_cells(cells, reason)
        mission['decision'] = {'choice': choice, 'reason': why, 'source': 'actual displayed hardware diagnosis'}
        h.note('화면 근거 판단: '+why)
        check('실제 진단 기록·조회 중 작업/점유 유지', rid in state()['chapter4']['diagnosed']
              and state()['jobs'][index]['work_done'] == fault['jobs'][index]['work_done'] and state()['used'] == fault['used'])
        h.click_text('진단 확인 · 대응 선택')
        guide()
        if choice == 'migrate':
            h.click(h.call(lambda: h.widget_info(app().action_buttons['migrate'])))
            plan = h.call(lambda: [asdict(p) for p in app().allocation_window.options[0]])
            mission['migration_plan'] = plan
            h.click_text('이전안 1 (추천)')
            check('이전 선택만으로 원장 불변', state()['jobs'][index]['ledger'] == chosen)
            h.shot('c4_'+tag+'_migration_plan', note='정상 서버로 옮길 실제 슬롯·전력 선택')
            h.click_text('선택한 계획으로 이전 · 준비 10분')
        else:
            h.click(h.call(lambda: h.widget_info(app().action_buttons['hwrepair'])))
        selected = state()
        mission['after_choice'] = selected
        j = selected['jobs'][index]
        old = fault['jobs'][index]
        check('선택 후 수행·진행·모드·기한·총점유 보존', selected['used'] == fault['used']
              and all(j[k] == old[k] for k in ('playthrough_id', 'work_done', 'plan', 'terms', 'conditions')))
        check('실제 선택 기록 1회', selected['chapter4']['records'][str(rid)]['choices'] == [choice])
        if choice == 'migrate':
            check('선택 이전안 적용·장애 서버는 FAULT 유지', j['ledger'] == plan and j['migration_left'] == 10
                  and not j['faulted'] and selected['hardware'][old['faulted'][0]]['state'] == 'FAULT')
        else:
            check('기존 원장 유지·장비 복구20분 시작', j['ledger'] == chosen
                  and all(selected['hardware'][key]['state'] == 'REPAIRING'
                          and selected['hardware'][key]['repair_left'] == 20 for key in old['faulted']))
        guide()
        h.shot('c4_'+tag+'_preparing', note='이전 준비/장비 복구 시작·작업량 유지')
        h.step = '제4장 미션 '+tag+' 준비·재개·완료'
        preparation = 10 if choice == 'migrate' else 20
        for n in range(preparation//10):
            prepared = tick('대응 준비'+str((n+1)*10)+'분')
            check('준비 구간 작업량 동결'+str(n+1), prepared['jobs'][index]['work_done'] == old['work_done'])
        j = prepared['jobs'][index]
        check('준비 종료·진행 재개 가능', not j['faulted'] and j['migration_left'] == 0)
        h.shot('c4_'+tag+'_resumed', note='준비 종료·정상 실행·서버 상태')
        for n in range(20):
            if state()['jobs'][index]['phase'] == 'finished':
                break
            tick('재개 후 진행'+str(n+1))
        else:
            raise AbortQA('고객 정상 완료 한도 초과')
        final = state()
        mission['final'] = final
        j = final['jobs'][index]
        expected_finish = clock_minutes(cells['작업 이전 예상' if choice == 'migrate' else '장비 복구 예상'])
        check('실제 완료=진단 예상·기한 준수·전량 반환', j['succeeded'] and j['status'] == 'completed'
              and j['terms']['completed'] == expected_finish <= j['terms']['due'] and not j['ledger']
              and final['used'] == (0, 0) and final['available'] == (10, 10), j)
        check('조건/동의 불변·모든 서버 정상', j['conditions'] == job['conditions'] and not j['proposals']
              and all(v['state'] == 'HEALTHY' for v in final['hardware'].values()))
        h.shot('c4_'+tag+'_returned', note='고객 완료·서버 정상·전량 반환')

    h.step = '제4장 최종 결과'
    if not h.find('MISSION SUCCESS'):
        h.click_text('제4장', classes=['Button', 'TButton'])
    h.wait_text('MISSION SUCCESS')
    data['result'] = result = h.call(lambda: session().chapter3b_result())
    data['result_screen'] = h.snapshot()
    check('제4장2/2 성공·기한 준수·전량 반환', result['mission'] == 'success' and result['released']
          and all(j['success'] and j['on_time'] for j in result['jobs']))
    data['next_unlock_reason'] = h.call(lambda: session().training_unlock_reason())
    next_active = any('제5장' in b['text'] and b['state'] == 'normal'
                      for t in data['result_screen']['tops'] for b in t['buttons'])
    check('정규 제5장 해제/연습 진급 불가 구분·Lab/제5장 미진입', bool(data['next_unlock_reason']) is focused
          and next_active is (not focused)
          and state()['chapter5'] is None
          and not top_by_title(h.snapshot(), 'Engineering Lab'))
    h.shot('c4_success', note='제4장 최종 결과·제5장 버튼 미클릭')
    h.final_disk = ch1.disk_state(h.slot)
    check('디스크 무결성·체크포인트 보존·제5장 없음', h.final_disk['integrity'] == 'ok'
          and h.final_disk['simulation']['story']['chapter3b']['completed_steps'][-1] == 'b_finish'
          and not h.final_disk['simulation']['story'].get('training')
          and (not checkpoint.exists() if focused else hashlib.sha256(checkpoint.read_bytes()).hexdigest() == checkpoint_hash))
    h.completed = True


def scenario(h):
    ch3.scenario(h)
    play_chapter4(h)


def focus(h):
    # Only component-fixture initialization uses the direct practice entry.
    h.call(lambda: h.selector.new_story('3b'))
    h.slot = h.call(lambda: Path(h.selector.app.db.path))
    h.env = h.call(lambda: {'tk': h.root.tk.call('info', 'patchlevel'), 'screen': [h.root.winfo_screenwidth(), h.root.winfo_screenheight()],
                            'capture_scale': h.scale})
    play_chapter4(h, focused=True)


def self_check():
    ch1.self_check()
    cells = {'정상 서버 가용': 'GPU 6 / 전력 6  (B 3/2 · C 2/3 · D 1/1)',
             '필요 자원': 'GPU 3 / 전력 4', '고객 완료 기한': 'D1 10:15',
             '작업 이전': '가능', '작업 이전 예상': '10분 → D1 10:10 · 기한 내',
             '장비 복구 예상': '20분 → D1 10:20 · 기한 초과'}
    assert choice_from_cells(cells, '')[0] == 'migrate'
    cells.update({'필요 자원': 'GPU 7 / 전력 7', '작업 이전': '불가능', '작업 이전 예상': '해당 없음',
                  '고객 완료 기한': 'D1 12:40'})
    assert choice_from_cells(cells, '정상 GPU6 < 필요GPU7')[0] == 'repair'
    cells['고객 완료 기한'] = 'D1 10:00'
    try:
        choice_from_cells(cells, '정상 GPU6 < 필요GPU7')
    except AbortQA:
        pass
    else:
        raise AssertionError('기한 내 대응 증거가 없으면 중단해야 함')
    assert clock_minutes('D2 00:05') == 1445
    print('chapter4 QA self-check PASS')


def main():
    if '--self-check' in sys.argv:
        self_check()
        return
    focused = sys.argv[1] == '--focus'
    out = Path(sys.argv[2] if focused else sys.argv[1])
    if not focused:
        gate = json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))
        if gate['kind'] != 'chapter4_focused_fixture' or not gate['completed'] or gate['error'] or gate['failed']:
            raise SystemExit('제3장 QA 입력 흐름 집중 검사 통과 자료가 필요합니다.')
        if gate['qa_source_sha256'] != hashlib.sha256(Path(__file__).read_bytes()).hexdigest():
            raise SystemExit('집중 검사 이후 QA 코드가 바뀌었습니다. 다시 집중 검사하세요.')
        reused = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in (Path(ch1.__file__), Path(ch2.__file__), Path(ch3.__file__))}
        if gate['reused_source_sha256'] != reused:
            raise SystemExit('집중 검사 이후 재사용하는 QA 코드가 바뀌었습니다.')
    out.mkdir(parents=True, exist_ok=True)
    marker = out/'attempt.json'
    with marker.open('x', encoding='utf-8') as f:
        json.dump({'started': datetime.now(ZoneInfo('Asia/Seoul')).isoformat(timespec='seconds')}, f)
    before = ch1.db_hashes()
    h = ch1.StoryHarness(out)
    h.env, h.placements, h.layouts, h.goals, h.jobs = {}, [], [], [], []
    error = None
    try:
        error = h.run(focus if focused else scenario)['error']
    except BaseException as exc:
        error = f'{type(exc).__name__}: {exc}'
    finally:
        after = ch1.db_hashes()
        (out/'storage-audit.json').write_text(json.dumps({'before': before, 'after': after}, indent=1), encoding='utf-8')
        h.check('보존', '사용자 DB·슬롯·체크포인트·보조 파일 동일', before == after, f'기존{len(before)}개/이후{len(after)}개')
        if getattr(h, 'slot', None) and h.slot.exists():
            h.final_disk = ch1.disk_state(h.slot)
            h.check('종료', '정상 종료 후 SQLite 무결성', h.final_disk['integrity'] == 'ok')
        completed = getattr(h, 'completed', False)
        assert h.tmp.resolve().parent == Path(tempfile.gettempdir()).resolve() and h.tmp.name.startswith('srs_qa_')
        removed = h.cleanup() if completed and not error and not any(c['result'] == 'FAIL' for c in h.checks) else []
        report = {'started': json.loads(marker.read_text(encoding='utf-8'))['started'],
                  'kind': 'chapter4_focused_fixture' if focused else 'regular_chapter1_2_3_4_full_play',
                  'commit': subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip(),
                  'python': platform.python_version(), 'env': h.env, 'completed': completed, 'error': error,
                  'clicks': h.clicks, 'wheel_events': h.wheel_events, 'full_play_attempts': 0 if focused else int(h.play_attempted),
                  'preflight': h.preflight_data, 'passed': sum(c['result'] == 'PASS' for c in h.checks),
                  'failed': sum(c['result'] == 'FAIL' for c in h.checks), 'repo_db_unchanged': before == after,
                  'repo_db_count': len(before), 'temp_files_removed': removed, 'temp_preserved_on_failure': not bool(removed),
                  'checks': h.checks, 'chapter1': getattr(h, 'chapter1', None), 'chapter2': getattr(h, 'chapter2_data', None),
                  'chapter3': getattr(h, 'chapter3_data', None), 'chapter4': getattr(h, 'chapter4_data', None), 'final_disk': getattr(h, 'final_disk', None),
                  'shots': h.shots, 'window_events': getattr(getattr(h, 'monitor', None), 'events', []),
                  'capture_occlusions': h.occlusions, 'native_guard_events': h.guard_events,
                  'qa_source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  'reused_source_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(ch1.__file__), Path(ch2.__file__), Path(ch3.__file__))},
                  'log': [line.replace(str(ROOT), '<repo>').replace(str(h.tmp), '<qa-temp>') for line in h.log]}
        (out/'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
        print(f'완주={completed} error={error} PASS={report["passed"]} FAIL={report["failed"]} clicks={h.clicks}', flush=True)
    raise SystemExit(bool(error or report['failed'] or not completed))


if __name__ == '__main__':
    main()
