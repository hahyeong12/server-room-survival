"""chapter2-002: 실제 휠 집중 검사 통과 후 정규 제1장→제2장을 검증합니다.

python tests/qa/autoplay_chapter2.py <새 출력 디렉터리> <집중 검사 result.json>
--self-check는 창/입력 없이 QA 로직만 검증합니다. 게임 상태 변경은 실제 클릭만 사용합니다.
"""
import hashlib
import json
import platform
import subprocess
import sys
import tempfile
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autoplay_story_ch1 as ch1
from autoplay_tutorial import top_by_title
from gui_driver import AbortQA, ROOT


def viable_impact(text):
    """다른 고객의 허용 절약형이 가능한 배정만 선택합니다(화면 문구 기반)."""
    return '절약형 모드 GPU 4/전력 3 배정 가능' in text


def scenario(h):
    # 검증된 첫 근무 3건·결과창까지 그대로 재사용합니다. 장 해제/클리어 조작 없음.
    ch1.scenario(h)
    h.chapter1 = {'jobs': h.jobs, 'result': h.chapter_result,
                  'checks': len(h.checks), 'clicks': h.clicks}
    h.completed = False
    app = lambda: h.selector.app
    session = lambda: app().session

    def read_state():
        s = session()
        jobs = []
        for rid in s.story.chapter2.request_ids:
            r = s.runs[rid]
            alloc = s.servers.allocations.get(r.playthrough_id)
            jobs.append({'id': rid, 'country': r.mission['country'], 'scenario': r.state.scenario,
                         'conditions': r.conditions, 'terms': dict(r.terms), 'plans': r.state.plans,
                         'plan': r.state.plan, 'phase': r.state.phase, 'status': r.request['status'],
                         'work_done': r.state.work_done, 'work_total': r.state.work_total,
                         'progress': r.state.progress, 'elapsed': r.state.elapsed,
                         'score': r.state.score, 'succeeded': r.state.succeeded,
                         'proposals': r.proposals,
                         'ledger': [asdict(p) for p in alloc.slices] if alloc else []})
        return {'minute': s.minute, 'jobs': jobs, 'available': s.servers.available(),
                'center_available': (s.center.available_gpu(), s.center.available_power()),
                'used': (s.center.gpu_used, s.center.power_used),
                'ledger_used': (sum(a.gpu for a in s.servers.allocations.values()),
                                sum(a.power for a in s.servers.allocations.values())),
                'chapter2': asdict(s.story.chapter2), 'practice': s.story.practice,
                'chapter3': s.story.chapter3}

    def state():
        return h.call(read_state)

    def check(item, ok, detail=''):
        h.check(h.step, item, ok, str(detail))

    def guide(capture=False):
        """현재 교육창의 모든 페이지를 실제 다음 버튼으로 읽고 닫습니다."""
        for _ in range(12):
            feedback = top_by_title(h.snapshot(), 'FEEDBACK')
            if feedback:
                h.chapter2_data['guides'].append({'step': h.step, 'feedback': feedback})
                h.click_text('확인 · 다음 목표', top=feedback['path'])
                continue
            top = top_by_title(h.snapshot(), '현장 교육')
            if not top:
                return
            data = h.call(lambda: {'index': app().story_window.index,
                                  'total': len(app().story_window.steps),
                                  'body': app().story_window.bubble.get('1.0', 'end-1c'),
                                  'next': h.widget_info(app().story_window.next_button)})
            h.chapter2_data['guides'].append(dict(step=h.step, **{k:v for k,v in data.items() if k != 'next'}))
            if capture and '두 고객 요청 비교' in data['body']:
                h.shot('comparison', note='제2장 브리핑의 두 고객 조건·모드·기한 비교')
            h.click(data['next'], settle=.7)
        raise AbortQA('교육창 12페이지 내 종료 실패')

    def select_request(rid):
        # 목록에 완료된 제1장 행도 남습니다. 실제 휠로 요청 행 전체를 노출합니다.
        h.wheel_inbox(-1200)
        def row_info():
            tree = app().inbox
            return {'box': tree.bbox(str(rid)), 'height': tree.winfo_height(),
                    'view': tree.yview(), 'selected': tree.selection(),
                    'rows': [{'id': key, 'box': tree.bbox(key)} for key in tree.get_children()],
                    'widget': h.widget_info(tree)}
        for _ in range(12):
            row = h.call(row_info)
            h.chapter2_data['row_access'].append({'id': rid, **row})
            if row['box'] and row['box'][1]+row['box'][3] <= row['height']:
                break
            h.wheel_inbox(120)  # 게임의 중복 바인딩 제거 뒤 실제 집중 검사로 검증한 표준 한 칸 입력.
        else:
            raise AbortQA('실제 휠로 고객 행 접근 실패')
        h.click(row['widget'], dy=row['box'][1]+row['box'][3]//2, settle=.9)
        check('요청 행 실제 클릭·현재 고객 일치', h.call(lambda: session().selected_id == rid))

    def open_allocation(rid, mode=None):
        select_request(rid)
        # 요청 행 클릭은 고객 대화를 열기도 합니다. 실제 버튼으로 닫습니다.
        if top_by_title(h.snapshot(), 'AIDC LINK |'):
            h.click_text('확인 · 운영실로')
        guide()
        if mode:
            h.click(h.call(lambda: h.widget_info(app().mode_buttons[mode])))
        h.click_text('배정 설정·선택', settle=.8)
        return h.call(lambda: app().allocation_window.mode_rows)

    def select_mode(key):
        h.click(h.call(lambda: h.widget_info(app().allocation_window.mode_buttons[key])))

    h.chapter2_data = {'guides': [], 'requests': [], 'options': [], 'ticks': [], 'row_access': []}
    h.step = '제2장 정규 진입'
    h.click_text('제2장 — 한정된 자원 · 시작', settle=1.2)
    h.wait_for(lambda: top_by_title(h.snapshot(), '현장 교육'), what='제2장 브리핑')
    initial = state()
    h.chapter2_data['initial'] = initial
    check('제1장 결과에서 정규 제2장 진입·같은 슬롯·연습 아님',
          not initial['practice'] and h.call(lambda: app().db.path == h.slot)
          and [j['scenario'] for j in initial['jobs']] == ['ch2_jp', 'ch2_us_v2'])
    check('두 고객 동시 접수·자원 미점유', initial['jobs'][0]['terms']['received'] == initial['jobs'][1]['terms']['received']
          and initial['available'] == initial['center_available'] == (10, 10) and initial['used'] == (0, 0))
    needs = tuple(sum(j['plans']['performance'][key] for j in initial['jobs']) for key in ('gpu', 'power'))
    check('두 고성능 합계 GPU10·전력11, 가용10/10 대비 전력만 부족', needs == (10, 11), needs)
    from aidc.storage.checkpoints import checkpoint_path
    checkpoint = checkpoint_path(h.slot, 2)
    checkpoint_hash = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    check('제2장 시작 체크포인트 SQLite 정상', ch1.disk_state(checkpoint)['integrity'] == 'ok')
    guide(capture=True)
    ids = [j['id'] for j in initial['jobs']]

    h.step = '두 고객 실제 요청서'
    for rid in ids:
        select_request(rid)
        if not top_by_title(h.snapshot(), 'AIDC LINK |'):
            h.click_text('고객 대화', settle=.8)
        top = h.wait_for(lambda: top_by_title(h.snapshot(), 'AIDC LINK |'), what='고객 요청서')
        h.wait_for(lambda: h.call(lambda: app().message_window.shown == len(app().message_window.full_text)),
                   timeout=30, what='요청서 본문 타이핑 완료')
        # 요청서 본문 아래 네트워크 요구량까지 실제 스크롤바 화살표로 읽습니다.
        scroll = []
        for _ in range(30):
            def text_position():
                text = app().message_window.bubble
                index = text.search('요청 GPU:', '1.0')
                line = text.dlineinfo(index) if index else None
                return {'visible': bool(line and line[1]+line[3] <= text.winfo_height()-int(text.cget('pady'))-6),
                        'view': text.yview(), 'bar': h.widget_info(text.vbar)}
            position = h.call(text_position)
            scroll.append({k:v for k,v in position.items() if k != 'bar'})
            if position['visible']:
                break
            h.click(position['bar'], dy=position['bar']['h']-8, settle=.08)
        else:
            raise AbortQA('요청서 네트워크 요구량 실제 스크롤 접근 실패')
        top = top_by_title(h.snapshot(), 'AIDC LINK |')
        labels = '\n'.join(x['text'] for x in top['labels'])
        job = next(j for j in initial['jobs'] if j['id'] == rid)
        h.chapter2_data['requests'].append({'id': rid, 'screen': top, 'scroll': scroll})
        h.shot(f'request_{rid}', note=job['country']+' 실제 요청서·원래 조건·허용 모드·기한')
        p = job['plans']['performance']
        check(job['country']+' 요청서 GPU·전력·네트워크·허용 모드 표시',
              ch1.request_numbers(labels) == (p['gpu'], p['power']) and f'네트워크: {p["network"]}단위' in '\n'.join(top['texts'])
              and '허용 운영 모드' in labels, labels)
        h.click_text('확인 · 운영실로', settle=.8)
        guide()
    check('두 실제 요청서 열람 기록', set(state()['chapter2']['requests_read']) == set(ids))

    h.step = '일본 배정 비교'
    rows = open_allocation(ids[0])
    h.chapter2_data['jp_modes'] = rows
    check('일본 고성능 허용·절약형 동의 필요', rows[0]['agreed'] and not rows[1]['agreed'], rows)
    select_mode('performance')
    options = h.call(lambda: [[asdict(p) for p in parts] for parts in app().allocation_window.options])
    for index in range(len(options)):
        h.click(h.call(lambda: h.widget_info(app().allocation_window.plan_buttons[index])))
        top_path, impact_path = h.call(lambda: (str(app().allocation_window), str(app().allocation_window.impact_label)))
        h.scroll_to(top_path, impact_path, 'down')
        impact = h.call(lambda: app().allocation_window.impact_label.cget('text'))
        h.chapter2_data['options'].append({'index': index, 'parts': options[index], 'impact': impact})
        if index in (0, len(options)-1):
            h.shot(f'jp_option_{index+1}', note='일본 배정안 비교: 다른 고객 모드별 실행 가능 여부')
        h.scroll_to(top_path, impact_path, 'up')
    candidates = [o for o in h.chapter2_data['options'] if viable_impact(o['impact'])]
    if not candidates:
        raise AbortQA('화면에서 미국 절약형 동시 배정 가능한 안을 찾지 못함')
    chosen = candidates[0]
    h.chapter2_data['chosen_jp'] = chosen
    h.click(h.call(lambda: h.widget_info(app().allocation_window.plan_buttons[chosen['index']])))
    check('일본 최종 선택 전 조회·선택 무점유', state()['used'] == (0, 0))
    h.shot('jp_final_plan', note='일본 고성능·미국 절약형 공간을 남기는 배정안 최종 선택')
    h.click_text('선택한 계획으로 작업 시작', settle=.9)
    guide()
    jp_started = state()
    h.chapter2_data['jp_started'] = jp_started
    check('일본 실제 배정 슬롯·전력 일치', jp_started['jobs'][0]['ledger'] == chosen['parts']
          and jp_started['jobs'][0]['phase'] == 'running' and jp_started['used'] == (4, 5))

    h.step = '미국 자원 부족·허용 모드 선택'
    rows = open_allocation(ids[1], 'economy')
    h.chapter2_data['us_modes'] = rows
    select_mode('performance')
    blocked = h.call(lambda: {'reason': app().allocation_window.mode_reason.cget('text'),
                             'options': len(app().allocation_window.options),
                             'start_state': app().allocation_window.start_button.cget('state')})
    h.chapter2_data['blocked_high'] = blocked
    check('미국 고성능은 전력 부족·시작 차단', blocked['options'] == 0 and blocked['start_state'] == 'disabled'
          and bool(blocked['reason']) and state()['available'] == (6, 5), blocked)
    h.shot('us_high_blocked', note='일본 실행 중 미국 고성능 GPU6/전력6: 전력 가용5로 시작 차단')
    economy = next(r for r in rows if r['key'] == 'economy')
    check('미국 절약형 원래 허용·기한 내·별도 협의 불필요', economy['agreed'] and economy['on_time']
          and not economy['reason'] and 'economy' in initial['jobs'][1]['conditions']['allowed_modes'], economy)
    if not (economy['agreed'] and economy['on_time'] and not economy['reason']):
        raise AbortQA('미국 절약형의 허용/기한/자원 조건 불충족')
    select_mode('economy')
    us_plan = h.call(lambda: [asdict(p) for p in app().allocation_window.options[0]])
    h.chapter2_data['chosen_us'] = us_plan
    h.click_text('배정안 1 (추천)')
    check('미국 선택만으로 점유하지 않음', state()['used'] == (4, 5))
    h.shot('us_economy_plan', note='미국 허용 절약형·100분·기한 일치·선택 서버 슬롯')
    h.click_text('선택한 계획으로 작업 시작', settle=.9)
    guide()
    started = state()
    h.chapter2_data['both_started'] = started
    start_minute = started['minute']
    check('두 작업 같은 시각 동시 실행·전체/서버 원장 8/8',
          all(j['phase'] == 'running' and j['progress'] == 0 for j in started['jobs'])
          and started['used'] == started['ledger_used'] == (8, 8)
          and started['available'] == started['center_available'] == (2, 2)
          and started['jobs'][0]['terms']['started'] == started['jobs'][1]['terms']['started'] == start_minute
          and started['jobs'][1]['ledger'] == us_plan, started)
    h.shot('both_started', note='일본 고성능 + 미국 절약형 동시 실행·가용GPU2/전력2')
    h.chapter2_data['rationale'] = ('일본은 고성능 지정 4/5·40분·기한50분. 미국은 두 모드 허용이며 절약형4/3·100분·기한100분. '
        '두 고성능은GPU10/전력11로 전력 부족. 일본 뒤 미국 고성능은110분으로10분 지연. '
        '일본 고성능+미국 절약형을 같은 가상 시각에 시작하고, 미국 절약형 배정 가능 표시가 있는 일본 위치를 선택. 합계8/8.')

    h.step = '동시 진행·선택적 반환'
    for tick in range(1, 11):
        previous = state()
        thread, frames = h.burst(seconds=1.3)
        h.click_text('+10분', settle=.4)
        thread.join(timeout=4)
        if thread.is_alive():
            raise AbortQA('프레임 관측 종료 지연')
        guide()
        current = state()
        h.chapter2_data['ticks'].append({'tick': tick, 'state': current,
                                        'frames': [{k:v for k,v in f.items() if k != 'img'} for f in frames]})
        check(f'+{tick*10}분 가상 시간·진행·원장 합계', current['minute'] == start_minute+10*tick
              and current['used'] == current['ledger_used']
              and all(j['work_done'] > old['work_done'] if old['phase'] == 'running' else j['work_done'] == old['work_done']
                      for j, old in zip(current['jobs'], previous['jobs'])), current)
        if tick in (1, 3, 9):
            h.shot(f'progress_{tick*10}', note=f'시작 후{tick*10}분 실제 작업량·기한·자원')
        if tick == 4:
            jp, us = current['jobs']
            check('40분 일본 기한 내 완료·4/5 반환·미국 원장 보존', jp['succeeded'] and jp['status'] == 'completed'
                  and jp['terms']['completed'] <= jp['terms']['due'] and not jp['ledger']
                  and us['phase'] == 'running' and us['ledger'] == us_plan and current['used'] == (4, 3)
                  and current['available'] == (6, 7), current)
            h.shot('jp_returned', note='일본40분 완료·자원 반환·미국 계속 실행')
    final = state()
    h.chapter2_data['final'] = final
    check('100분 두 고객 정상 완료·기한 준수·전량 반환', final['chapter2']['completed_steps'][-1] == 'finish'
          and final['chapter2']['failure'] is None and final['available'] == final['center_available'] == (10, 10)
          and final['used'] == (0, 0) and all(j['succeeded'] and not j['ledger']
              and j['terms']['completed'] <= j['terms']['due'] for j in final['jobs']), final)
    check('미국 정확히 기한에 완료·무단 조건 변경/협의 없음', final['jobs'][1]['terms']['completed'] == final['jobs'][1]['terms']['due']
          and all(j['conditions'] == old['conditions'] and not j['proposals'] for j, old in zip(final['jobs'], initial['jobs'])))

    h.step = '제2장 결과'
    if not top_by_title(h.snapshot(), '결과'):
        h.click_text('제2장', classes=['Button', 'TButton'])
    h.wait_text('MISSION SUCCESS')
    h.chapter2_data['result'] = h.call(lambda: session().chapter2_result())
    h.chapter2_data['result_screen'] = top_by_title(h.snapshot(), '결과')
    check('제2장 성공·동시 실행·두 고객 결과 표시', h.chapter2_data['result']['mission'] == 'success'
          and h.chapter2_data['result']['concurrent'] and len(h.chapter2_data['result']['jobs']) == 2)
    unlock = h.call(lambda: session().chapter3_unlock_reason())
    h.chapter2_data['next_unlock_reason'] = unlock
    check('제3장 해제·실제 시작 버튼 활성, 진입하지 않음', not unlock
          and any('제3장' in b['text'] and b['state'] == 'normal' for b in h.chapter2_data['result_screen']['buttons']))
    h.shot('chapter2_success', note='제2장 MISSION SUCCESS·고객별 결과·종합 평가(다음 장 미진입)')
    h.final_disk = ch1.disk_state(h.slot)
    check('제2장 디스크 완료·시작 체크포인트 불변·제3장 미시작', h.final_disk['integrity'] == 'ok'
          and h.final_disk['simulation']['story']['chapter2']['completed_steps'][-1] == 'finish'
          and not h.final_disk['simulation']['story'].get('chapter3')
          and hashlib.sha256(checkpoint.read_bytes()).hexdigest() == checkpoint_hash)
    h.completed = True


def main():
    if '--self-check' in sys.argv:
        ch1.self_check()
        assert viable_impact('고성능 모드 GPU 6/전력 6 배정 불가 · 절약형 모드 GPU 4/전력 3 배정 가능')
        assert not viable_impact('절약형 모드 GPU 4/전력 3 배정 불가')
        print('chapter2 QA self-check PASS')
        return
    focused = json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))
    if focused['error'] or focused['failed'] or not focused['probe']['passed'] or focused['kind'] != 'focused_gui_not_full_play':
        raise SystemExit('실제 입력 집중 검사 통과 자료가 필요합니다. 전체 플레이를 시작하지 않습니다.')
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    marker = out/'attempt.json'
    with marker.open('x', encoding='utf-8') as f:
        json.dump({'started': datetime.now(ZoneInfo('Asia/Seoul')).isoformat(timespec='seconds')}, f)
    before = ch1.db_hashes()
    h = ch1.StoryHarness(out)
    h.env, h.placements, h.layouts, h.goals, h.jobs = {}, [], [], [], []
    error = None
    try:
        error = h.run(scenario)['error']
    except BaseException as exc:
        error = f'{type(exc).__name__}: {exc}'
    finally:
        after = ch1.db_hashes()
        h.check('보존', '사용자 DB·슬롯·체크포인트·보조 파일 동일', before == after, f'기존{len(before)}개/이후{len(after)}개')
        if getattr(h, 'slot', None) and h.slot.exists():
            h.final_disk = ch1.disk_state(h.slot)
            h.check('종료', '정상 종료 후 SQLite 무결성', h.final_disk['integrity'] == 'ok')
        completed = getattr(h, 'completed', False)
        # 실패 때 임시 DB를 로컬에 보존하고, 공개 자료에는 저장 상태 JSON만 담습니다.
        assert h.tmp.resolve().parent == Path(tempfile.gettempdir()).resolve() and h.tmp.name.startswith('srs_qa_')
        removed = h.cleanup() if completed and not error else []
        report = {'started': json.loads(marker.read_text(encoding='utf-8'))['started'],
                  'commit': subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip(),
                  'python': platform.python_version(), 'env': h.env, 'completed': completed, 'error': error,
                  'clicks': h.clicks, 'wheel_events': h.wheel_events, 'play_attempts': int(h.play_attempted),
                  'preflight': h.preflight_data, 'passed': sum(c['result'] == 'PASS' for c in h.checks),
                  'failed': sum(c['result'] == 'FAIL' for c in h.checks), 'repo_db_unchanged': before == after,
                  'repo_db_count': len(before), 'temp_files_removed': removed, 'temp_preserved_on_failure': not bool(removed),
                  'checks': h.checks, 'chapter1': getattr(h, 'chapter1', None), 'chapter2': getattr(h, 'chapter2_data', None),
                  'final_disk': getattr(h, 'final_disk', None), 'layouts': h.layouts, 'placements': h.placements,
                  'shots': h.shots, 'window_events': getattr(getattr(h, 'monitor', None), 'events', []),
                  'capture_occlusions': h.occlusions, 'native_guard_events': h.guard_events,
                  'qa_source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  'reused_source_sha256': hashlib.sha256(Path(ch1.__file__).read_bytes()).hexdigest(),
                  'focused_gui_passed': True,
                  'log': [line.replace(str(ROOT), '<repo>').replace(str(h.tmp), '<qa-temp>') for line in h.log]}
        (out/'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
        print(f'완주={completed} error={error} PASS={report["passed"]} FAIL={report["failed"]} clicks={h.clicks}', flush=True)
    raise SystemExit(bool(error or report['failed'] or not completed))


if __name__ == '__main__':
    main()
