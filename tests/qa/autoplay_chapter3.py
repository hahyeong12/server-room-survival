"""chapter3-001: native input, regular Chapter 1→2→3; never starts Chapter 4.

--focus <new-dir>: isolated practice fixture for testing this QA's new input flow.
<new-dir> <focus-result.json>: exactly one regular full play (exclusive attempt marker).
--self-check: no window. Game mutations in play_chapter3 use native clicks only.
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
import autoplay_chapter2 as ch2
import autoplay_story_ch1 as ch1
from autoplay_tutorial import top_by_title
from gui_driver import AbortQA, ROOT


def response_from_cells(cells):
    """Infer only from the opened diagnosis's displayed values, never mission/kind/id."""
    primary = cells['주 경로 상태']
    needed = int(cells['필요 대역폭'])
    available = int(cells['가용 대역폭'].split()[0])
    backup = cells['백업 경로']
    capacity = re.search(r'용량 (\d+)', backup)
    if primary == 'DOWN' and available == 0 and 'UP' in backup and capacity and int(capacity[1]) >= needed:
        return 'reroute', f'주 경로 DOWN·가용0, 백업 UP·용량{capacity[1]} ≥ 필요{needed}. 살아 있는 경로로 전환.'
    if primary == 'UP' and needed > available and '같은 병목 공유' in backup:
        return 'compress', f'주 경로 UP, 필요{needed} > 가용{available}, 백업도 같은 병목. 전송 필요량을 줄일 대응 선택.'
    raise AbortQA('화면 증거로 대응을 결정할 수 없습니다: '+repr(cells))


def play_chapter3(h, focused=False):
    app = lambda: h.selector.app
    session = lambda: app().session
    check = lambda item, ok, detail='': h.check(h.step, item, ok, detail)
    h.completed = False
    h.chapter3_data = data = {'guides': [], 'feedback': [], 'missions': [], 'ticks': [], 'row_access': []}

    def state():
        def read():
            s = session()
            jobs = []
            for rid in s.story.chapter3.request_ids:
                r = s.runs[rid]
                fields = ('scenario', 'plan', 'phase', 'work_done', 'elapsed', 'progress', 'score', 'succeeded',
                          'network_needed', 'network_available', 'primary_up', 'rerouted', 'backup_capacity',
                          'incident_kind', 'response_attempts', 'response_log', 'recovered_by', 'recovery_left', 'downtime')
                a = s.servers.allocations.get(r.playthrough_id)
                jobs.append({'id': rid, 'country': r.mission['country'], 'conditions': dict(r.conditions),
                             'terms': dict(r.terms), 'plans': r.state.plans, 'proposals': list(r.proposals),
                             'status': r.request['status'], 'ledger': [asdict(p) for p in a.slices] if a else [],
                             **{key: getattr(r.state, key) for key in fields}})
            return {'minute': s.minute, 'practice': s.story.practice, 'chapter3': asdict(s.story.chapter3),
                    'chapter4': s.story.chapter3b, 'jobs': jobs, 'available': s.servers.available(),
                    'used': (s.center.gpu_used, s.center.power_used),
                    'center_available': (s.center.available_gpu(), s.center.available_power()),
                    'ledger_used': (sum(a.gpu for a in s.servers.allocations.values()),
                                    sum(a.power for a in s.servers.allocations.values())),
                    'hardware': {key: value.state for key, value in s.servers.hardware.items()}}
        return h.call(read)

    def guide():
        for _ in range(18):
            snap = h.snapshot()
            card = top_by_title(snap, 'FEEDBACK')
            if card:
                data['feedback'].append({'step': h.step, 'screen': card})
                h.shot('c3_feedback', note='실제 대응/완료 결과 카드')
                button = h.find('업무로 돌아가기', top=card['path']) or h.find('확인 · 다음 목표', top=card['path'])
                if button is None:
                    raise AbortQA('예상하지 않은 결과 카드: '+card['title'])
                h.click(button)
                continue
            top = top_by_title(snap, '현장 교육')
            if not top:
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
            raise AbortQA('프레임 표본 스레드 종료 지연')
        after = state()
        data['ticks'].append({'label': label, 'state': after,
                              'frames': [{k: v for k, v in f.items() if k != 'img'} for f in frames]})
        check(label+' 시간·전체/서버 원장 일치', after['minute'] == before['minute']+10
              and after['used'] == after['ledger_used'] and all(v == 'HEALTHY' for v in after['hardware'].values()), after)
        guide()
        return after

    h.step = '제3장 진입' if not focused else '집중 검사·독립 연습 fixture'
    if not focused:
        h.click_text('제3장 — 끊어진 연결 · 시작', settle=1)
    h.wait_for(lambda: top_by_title(h.snapshot(), '현장 교육'), what='제3장 브리핑')
    initial = state()
    data['initial'] = initial
    check('정규/집중 fixture 구분·첫 미션 접수·자원 미점유', initial['practice'] is focused
          and len(initial['jobs']) == 1 and initial['jobs'][0]['scenario'] == 'ch3_path'
          and initial['available'] == (10, 10) and h.call(lambda: app().db.path == h.slot))
    from aidc.storage.checkpoints import checkpoint_path
    checkpoint = checkpoint_path(h.slot, 3)
    checkpoint_hash = hashlib.sha256(checkpoint.read_bytes()).hexdigest() if not focused else None
    check('정규 체크포인트 존재/연습 체크포인트 없음 구분', checkpoint.is_file() is (not focused))
    guide()

    for index in range(2):
        h.step = '제3장 미션 '+'AB'[index]+' 요청·시작'
        current = state()
        if len(current['jobs']) <= index:
            raise AbortQA('후속 고객이 접수되지 않음')
        rid = current['jobs'][index]['id']
        mission = {'id': rid, 'before': current}
        data['missions'].append(mission)
        h.wheel_inbox(-1200)
        for _ in range(16):
            row = h.call(lambda: {'box': app().inbox.bbox(str(rid)), 'height': app().inbox.winfo_height(),
                                 'view': app().inbox.yview(), 'selected': app().inbox.selection(),
                                 'widget': h.widget_info(app().inbox)})
            data['row_access'].append({'id': rid, **row})
            if row['box'] and row['box'][1]+row['box'][3] <= row['height']:
                break
            h.wheel_inbox(120)
        else:
            raise AbortQA('고객 행 실제 휠 접근 실패')
        h.click(row['widget'], dy=row['box'][1]+row['box'][3]//2, settle=.8)
        if not top_by_title(h.snapshot(), 'AIDC LINK |'):
            h.click_text('고객 대화')
        h.wait_for(lambda: h.call(lambda: app().message_window.shown == len(app().message_window.full_text)),
                   timeout=30, what='고객 요청서 전체 타이핑')
        for _ in range(30):
            def position():
                text = app().message_window.bubble
                line = text.dlineinfo(text.search('요청 GPU:', '1.0'))
                return {'visible': bool(line and line[1]+line[3] <= text.winfo_height()-int(text.cget('pady'))-6),
                        'bar': h.widget_info(text.vbar)}
            pos = h.call(position)
            if pos['visible']:
                break
            h.click(pos['bar'], dy=pos['bar']['h']-8, settle=.08)
        else:
            raise AbortQA('고객 요청 자원 본문 노출 실패')
        request = top_by_title(h.snapshot(), 'AIDC LINK |')
        mission['request'] = request
        job = state()['jobs'][index]
        labels = '\n'.join(x['text'] for x in request['labels'])
        p = job['plans']['performance']
        check('요청서 실제 GPU·전력·네트워크·허용 표시', ch1.request_numbers(labels) == (p['gpu'], p['power'])
              and f'네트워크: {p["network"]}단위' in '\n'.join(request['texts']) and '허용 운영 모드' in labels)
        h.shot('c3_'+'AB'[index]+'_request', note='실제 요청·허용 조건·기한')
        h.click_text('확인 · 운영실로')
        guide()
        if 'performance' not in job['conditions']['allowed_modes']:
            raise AbortQA('현재 QA의 고성능 계획은 실제 고객 허용 범위 밖입니다. 동의 우회하지 않고 중단합니다.')
        h.click(h.call(lambda: h.widget_info(app().mode_buttons['performance'])))
        h.click_text('배정 설정·선택')
        rows = h.call(lambda: app().allocation_window.mode_rows)
        mission['allocation_modes'] = rows
        check('고성능 원래 허용·협의 불필요·시작 가능', rows[0]['agreed'] and not rows[0]['reason'])
        h.click_text('배정안 1 (추천)')
        chosen = h.call(lambda: [asdict(p) for p in app().allocation_window.options[0]])
        mission['chosen'] = chosen
        h.shot('c3_'+'AB'[index]+'_allocation', note='실제 허용 고성능·서버 배정 선택')
        h.click_text('선택한 계획으로 작업 시작')
        guide()
        started = state()
        mission['started'] = started
        check('실제 시작·선택 슬롯 일치', started['jobs'][index]['phase'] == 'running'
              and started['jobs'][index]['ledger'] == chosen and started['used'] == (p['gpu'], p['power']))

        h.step = '미션 '+'AB'[index]+' 장애 관측·진단'
        for n in range(12):
            if state()['jobs'][index]['phase'] == 'incident':
                break
            tick('장애 전 진행'+str(n+1))
        else:
            raise AbortQA('장애 미발생')
        incident = state()
        mission['incident'] = incident
        controls = h.call(lambda: {k: h.widget_info(v) for k, v in app().action_buttons.items()})
        mission['before_diagnosis_controls'] = controls
        check('장애 발생·진단 전 대응 잠금·장비 정상',
              all(controls[k]['state'] == 'disabled' for k in ('reroute', 'compress', 'ignore'))
              and incident['jobs'][index]['downtime'] == 0 and incident['used'] == started['used'])
        h.shot('c3_'+'AB'[index]+'_incident', note='작업 중단·대응 비활성·네트워크 장애')
        h.click(controls['diagnose'])
        h.wait_for(lambda: top_by_title(h.snapshot(), '네트워크 진단'), what='실제 네트워크 진단창')
        cells = h.call(lambda: {k: v.cget('text') for k, v in app().diagnosis_window.cells.items()})
        mission['diagnosis_cells'] = cells
        mission['diagnosis_screen'] = top_by_title(h.snapshot(), '네트워크 진단')
        h.shot('c3_'+'AB'[index]+'_diagnosis', note='원인 판단에 실제 사용한 주 경로·필요/가용·백업·장비 수치')
        response, reason = response_from_cells(cells)
        mission['decision'] = {'response': response, 'reason': reason, 'source': 'actual visible diagnosis cells'}
        h.note('화면 기반 판단: '+reason)
        check('실제 진단 기록·자동 대응 없이 작업량 유지', rid in state()['chapter3']['diagnosed']
              and state()['jobs'][index]['response_attempts'] == 0
              and state()['jobs'][index]['work_done'] == incident['jobs'][index]['work_done'])
        h.click_text('진단 확인 · 대응 선택')
        guide()
        h.click(h.call(lambda: h.widget_info(app().action_buttons[response])))
        recovered = state()
        mission['response_state'] = recovered
        j = recovered['jobs'][index]
        check('선택 대응 1회·복구 준비10분·작업/자원 보존', j['phase'] == 'recovering'
              and j['recovery_left'] == 10 and j['response_log'] == [response]
              and j['network_needed'] <= j['network_available'] and j['recovered_by'] == response
              and j['work_done'] == incident['jobs'][index]['work_done'] and recovered['used'] == started['used'])
        guide()
        h.shot('c3_'+'AB'[index]+'_recovering', note='복구 성공 뒤 준비10분·즉시 작업량 증가하지 않음')
        h.step = '미션 '+'AB'[index]+' 복구·완료'
        resumed = tick('복구 준비10분')
        check('준비 구간 작업 동결·정상 실행 전환', resumed['jobs'][index]['phase'] == 'running'
              and resumed['jobs'][index]['recovery_left'] == 0
              and resumed['jobs'][index]['work_done'] == j['work_done'])
        h.shot('c3_'+'AB'[index]+'_resumed', note='정상 실행으로 전환·네트워크 진단 행동 제거')
        controls = h.call(lambda: list(app().action_buttons))
        check('복구 뒤 진단·불필요 지연 안내 제거', 'diagnose' not in controls and 'delay' not in controls)
        for n in range(20):
            if state()['jobs'][index]['phase'] == 'finished':
                break
            tick('복구 후 진행'+str(n+1))
        else:
            raise AbortQA('정상 완료 한도 초과')
        final = state()
        mission['final'] = final
        j = final['jobs'][index]
        check('고객 정상 완료·기한 내·전체 반환·조건 보존', j['succeeded'] and j['status'] == 'completed'
              and j['terms']['completed'] <= j['terms']['due'] and not j['ledger']
              and final['available'] == final['center_available'] == (10, 10)
              and final['used'] == (0, 0) and j['conditions'] == job['conditions'] and not j['proposals'], j)
        h.shot('c3_'+'AB'[index]+'_returned', note='고객 완료·GPU/전력 전량 반환')

    h.step = '제3장 최종 결과'
    # Chapter 3 result title is “제3장 성공 · 끊어진 연결”, without “결과”.
    if not h.find('MISSION SUCCESS'):
        h.click_text('제3장', classes=['Button', 'TButton'])
    h.wait_text('MISSION SUCCESS')
    result = h.call(lambda: session().chapter3_result())
    data['result'] = result
    data['result_screen'] = h.snapshot()
    check('제3장 미션2/2 성공·두 진단·대응·반환 결과', result['mission'] == 'success' and result['released']
          and all(j['diagnosed'] and j['recovered'] and j['success'] and j['attempts'] == 1 for j in result['jobs']))
    data['next_unlock_reason'] = h.call(lambda: session().chapter3b_unlock_reason())
    check('제4장 해제·실제 시작 버튼 활성·미진입', not data['next_unlock_reason']
          and any('제4장' in b['text'] and b['state'] == 'normal' for t in data['result_screen']['tops'] for b in t['buttons'])
          and state()['chapter4'] is None)
    h.shot('c3_success', note='제3장 최종 성공·두 미션 결과·제4장 버튼 클릭하지 않음')
    h.final_disk = ch1.disk_state(h.slot)
    check('제3장 디스크 무결성·체크포인트 불변·제4장 미시작', h.final_disk['integrity'] == 'ok'
          and h.final_disk['simulation']['story']['chapter3']['completed_steps'][-1] == 'b_finish'
          and not h.final_disk['simulation']['story'].get('chapter3b')
          and (not checkpoint.exists() if focused else hashlib.sha256(checkpoint.read_bytes()).hexdigest() == checkpoint_hash))
    h.completed = True


def scenario(h):
    ch2.scenario(h)
    play_chapter3(h)


def focus(h):
    # Component fixture initialization only. This is NOT a regular story QA completion.
    h.call(lambda: h.selector.new_story(3))
    h.slot = h.call(lambda: Path(h.selector.app.db.path))
    play_chapter3(h, focused=True)


def main():
    if '--self-check' in sys.argv:
        ch1.self_check()
        assert response_from_cells({'주 경로 상태': 'DOWN', '필요 대역폭': '5', '가용 대역폭': '0 (경로 없음)',
                                    '백업 경로': 'UP · 용량 6'})[0] == 'reroute'
        assert response_from_cells({'주 경로 상태': 'UP', '필요 대역폭': '6', '가용 대역폭': '4',
                                    '백업 경로': 'UP · 용량 4 · 같은 병목 공유'})[0] == 'compress'
        try:
            response_from_cells({'주 경로 상태': 'DOWN', '필요 대역폭': '8', '가용 대역폭': '0', '백업 경로': 'UP · 용량 6'})
        except AbortQA:
            pass
        else:
            raise AssertionError('증거 부족이면 중단해야 함')
        print('chapter3 QA self-check PASS')
        return
    focused = sys.argv[1] == '--focus'
    out = Path(sys.argv[2] if focused else sys.argv[1])
    if not focused:
        gate = json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))
        if gate['kind'] != 'chapter3_focused_fixture' or not gate['completed'] or gate['error'] or gate['failed']:
            raise SystemExit('제3장 QA 입력 흐름 집중 검사 통과 자료가 필요합니다.')
        if gate['qa_source_sha256'] != hashlib.sha256(Path(__file__).read_bytes()).hexdigest():
            raise SystemExit('집중 검사 이후 QA 코드가 바뀌었습니다. 다시 집중 검사하세요.')
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
        h.check('보존', '사용자 DB·슬롯·체크포인트·보조 파일 동일', before == after, f'기존{len(before)}개/이후{len(after)}개')
        if getattr(h, 'slot', None) and h.slot.exists():
            h.final_disk = ch1.disk_state(h.slot)
            h.check('종료', '정상 종료 후 SQLite 무결성', h.final_disk['integrity'] == 'ok')
        completed = getattr(h, 'completed', False)
        assert h.tmp.resolve().parent == Path(tempfile.gettempdir()).resolve() and h.tmp.name.startswith('srs_qa_')
        removed = h.cleanup() if completed and not error else []
        report = {'started': json.loads(marker.read_text(encoding='utf-8'))['started'],
                  'kind': 'chapter3_focused_fixture' if focused else 'regular_chapter1_2_3_full_play',
                  'commit': subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip(),
                  'python': platform.python_version(), 'env': h.env, 'completed': completed, 'error': error,
                  'clicks': h.clicks, 'wheel_events': h.wheel_events, 'full_play_attempts': 0 if focused else int(h.play_attempted),
                  'preflight': h.preflight_data, 'passed': sum(c['result'] == 'PASS' for c in h.checks),
                  'failed': sum(c['result'] == 'FAIL' for c in h.checks), 'repo_db_unchanged': before == after,
                  'repo_db_count': len(before), 'temp_files_removed': removed, 'temp_preserved_on_failure': not bool(removed),
                  'checks': h.checks, 'chapter1': getattr(h, 'chapter1', None), 'chapter2': getattr(h, 'chapter2_data', None),
                  'chapter3': getattr(h, 'chapter3_data', None), 'final_disk': getattr(h, 'final_disk', None),
                  'shots': h.shots, 'window_events': getattr(getattr(h, 'monitor', None), 'events', []),
                  'capture_occlusions': h.occlusions, 'native_guard_events': h.guard_events,
                  'qa_source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  'reused_source_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(ch1.__file__), Path(ch2.__file__))},
                  'log': [line.replace(str(ROOT), '<repo>').replace(str(h.tmp), '<qa-temp>') for line in h.log]}
        (out/'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
        print(f'완주={completed} error={error} PASS={report["passed"]} FAIL={report["failed"]} clicks={h.clicks}', flush=True)
    raise SystemExit(bool(error or report['failed'] or not completed))


if __name__ == '__main__':
    main()
