"""튜토리얼 실제 자동 플레이 QA (tutorial-001).

실행(Windows, 저장소 루트):  python tests/qa/autoplay_tutorial.py [출력 디렉터리, 기본: 시스템 임시 폴더]
- 실제 Tk 창을 띄우고 Win32 SendInput 마우스 클릭으로만 진행합니다. 실행 중 마우스를 움직이지 마세요.
- 저장은 임시 디렉터리 슬롯만 사용하며 사용자 DB·슬롯·체크포인트를 열지 않습니다(실행 전후 해시 비교).
- 게임 상태는 검증을 위해 조회만 합니다. 진행·완료를 직접 호출하지 않습니다.
- unittest 자동 탐색 대상이 아닙니다(test_*.py 아님, tests/qa는 패키지 아님).
"""
import hashlib
import json
import platform
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gui_driver import ROOT, Harness, own_windows  # noqa: E402


def repo_db_hashes():
    return {p.name: hashlib.md5(p.read_bytes()).hexdigest() for p in sorted(ROOT.glob('*.db'))}


def top_by_title(snap, part):
    return next((t for t in snap['tops'] if part in t['title']), None)


def centered(h, part):
    """대화창 중심과 관제실(루트) 중심의 차이(논리 px)."""
    snap = h.snapshot()
    root, top = snap['tops'][0], top_by_title(snap, part)
    if top is None:
        return None
    return (top['x'] + top['w'] // 2 - (root['x'] + root['w'] // 2), top['y'] + top['h'] // 2 - (root['y'] + root['h'] // 2))


def placement(h, part):
    """게임이 표시 직후 측정해 남긴 dialog.placement 기록(window_placement.center_dialog)."""
    def run():
        for w in h.root.winfo_children():
            if w.winfo_class() == 'Toplevel' and part in w.title():
                return getattr(w, 'placement', None)
    record = h.call(run)
    h.placements.append({'step': h.step, 'window': part, 'record': record, 'measured_offset': centered(h, part)})
    return record


def close_by_caption(h, part):
    """하단 버튼이 화면 밖일 때 사용자가 할 수 있는 행동: 제목 표시줄의 [X]를 실제 클릭합니다."""
    from gui_driver import window_rect
    hwnd = h.call(lambda: next(int(w.wm_frame(), 16) for w in h.root.winfo_children()
                               if w.winfo_class() == 'Toplevel' and part in w.title()))
    left, top, right, _ = window_rect(hwnd)
    h.click({'x': right - 30, 'y': top + 15, 'w': 0, 'h': 0, 'text': f'[X] {part}', 'class': 'caption', 'top': '.'}, settle=1.2)


def layout_issues(h, title_part=None):
    """보이는 버튼·글자 중 창 밖·작업 영역 밖·다른 위젯에 가려짐·글자 요구 크기 초과 목록."""
    snap = h.snapshot()
    issues = []
    for t in snap['tops']:
        if title_part and title_part not in t['title']:
            continue
        for item in t['buttons'] + t['labels']:
            flags = [k for k in ('covered', 'offscreen', 'clipped_text') if item[k]] + ([] if item['inside_top'] else ['outside_window'])
            if flags:
                issues.append({'window': t['title'], 'text': item['text'][:40].replace('\n', ' / '), 'class': item['class'],
                               'flags': flags, 'covered_by': item['covered_by']})
    return issues


def scenario(h):
    S = h
    app = lambda: S.selector.app  # noqa: E731
    session = lambda: S.selector.app.session  # noqa: E731

    # ---------------------------------------------------------------- 0. 실행 환경
    S.step = '0 환경'
    env = S.call(lambda: {'tk': S.root.tk.call('info', 'patchlevel'), 'scaling': float(S.root.tk.call('tk', 'scaling')),
                          'screen': (S.root.winfo_screenwidth(), S.root.winfo_screenheight())})
    import ctypes
    aware = ctypes.c_int(-1)
    ctypes.windll.shcore.GetProcessDpiAwareness(None, ctypes.byref(aware))
    env.update({'work_area': S.work_area(), 'dpi_awareness': aware.value, 'capture_scale': S.scale})
    S.env = env
    S.note(f'환경 {env}')

    # ---------------------------------------------------------------- 1. 시작 화면
    S.step = '1 시작 화면'
    S.wait_text('서버실 생존기')
    snap = S.snapshot()
    root = snap['tops'][0]
    S.check(S.step, '모드 카드 3장의 [시작 / 이어하기] 버튼 표시',
            sum(1 for b in root['buttons'] if '시작 / 이어하기' in b['text']) == 3)
    S.check(S.step, '모드 선택 화면 위젯 중 창 밖·가려짐·글자 잘림 없음', not layout_issues(S), str(layout_issues(S)))
    work = env['work_area']
    S.check(S.step, '모드 선택 창 전체가 작업 영역(작업 표시줄 제외) 안', root['y'] + root['h'] <= work[3],
            f"창 아래 {root['y'] + root['h']} / 작업 영역 아래 {work[3]}")
    S.shot('title', note='시작 화면(모드 카드 3장)')

    # ---------------------------------------------------------------- 2. 튜토리얼 시작
    S.step = '2 튜토리얼 시작'
    S.click_text('시작 / 이어하기')  # 첫 카드 = 튜토리얼
    S.click_text('튜토리얼 처음부터', settle=1.5)
    S.wait_for(lambda: top_by_title(S.snapshot(), '현장 교육'), what='현장 교육창')
    S.check(S.step, '튜토리얼 모드·별도 임시 슬롯으로 시작', S.call(lambda: (session().mode, str(app().db.path.parent) == str(S.tmp))) == ('tutorial', True))

    # ---------------------------------------------------------------- 3. 선배 교육 안내(4쪽)
    S.step = '3 교육 안내'
    off = centered(S, '현장 교육')
    placement(S, '현장 교육')
    S.check(S.step, '교육창이 관제실 중앙(±4px)', off is not None and max(map(abs, off)) <= 4, f'중심 차이 {off}')
    S.check(S.step, '교육창 안 버튼·글자 잘림/가려짐 없음', not layout_issues(S, '현장 교육'), str(layout_issues(S, '현장 교육')))
    root_issues = [i for i in layout_issues(S) if i['window'].endswith('관제실') and 'offscreen' in i['flags']]
    S.check(S.step, '관제실 기본 창의 버튼이 작업 영역 안(작업 표시줄에 가리지 않음)', not root_issues, str(root_issues))
    expected = [s for _, s in S.call(lambda: session().story.onboarding.pages)]
    pages_ok = []
    for index in range(4):
        text = S.snapshot()
        top = top_by_title(text, '현장 교육')
        shown = top['texts'][0] if top['texts'] else ''
        pages_ok.append(shown == expected[index])
        S.note(f'교육창 {index + 1}/4 본문: {shown!r}')
        if index in (0, 1, 2, 3):
            S.shot(f'guide_p{index + 1}', note=f'교육창 {index + 1}/4 페이지')
        if index < 3:
            S.click_text('다음 ▶', top='현장 교육 | 교육 담당자 · 튜토리얼 — 관제실 첫걸음')
    S.check(S.step, '4쪽 본문이 데이터의 줄바꿈(\\n) 그대로 표시', all(pages_ok), str(pages_ok))
    last_buttons = [b['text'] for b in top_by_title(S.snapshot(), '현장 교육')['buttons']]
    S.check(S.step, '교육창 마지막 페이지에 중복 행동 버튼([마지막 안내]·[업무로 돌아가기]) 없음',
            '마지막 안내' not in last_buttons and '업무로 돌아가기' not in last_buttons, str(last_buttons))
    S.check(S.step, '긴 줄 없음(교육창 본문 한 줄 최대 40자 이하)', max(len(line) for p in expected for line in p.split('\n')) <= 40,
            f"최대 {max(len(line) for p in expected for line in p.split(chr(10)))}자")
    S.click_text('첫 업무 시작', settle=1.2)
    S.check(S.step, '교육창 종료 후 STEP 2/5(요청 확인)', S.call(lambda: session().story.onboarding.step) == 'request')

    # ---------------------------------------------------------------- 4. 요청 확인 — 기본 창 크기
    S.step = '4 요청 확인(기본 창)'
    target = S.call(lambda: S.widget_info(app().tutorial_highlight.target) | {'key': app().tutorial_highlight.key,
                                                                             'edges': len(app().tutorial_highlight.edges)})
    S.note(f'강조 대상 {target}')
    S.check(S.step, '금색 강조 대상 하나(테두리 8개 = 버튼 1개)', target['edges'] == 8, f"key={target['key']} edges={target['edges']}")
    S.check(S.step, '강조된 [요청 확인] 버튼이 실제로 보이고 클릭 가능', not target['covered'],
            f"중심점 위젯: {target['covered_by'] or '자기 자신'}")
    shown_edges = S.call(lambda: (app().tutorial_highlight.hidden, sum(1 for e in app().tutorial_highlight.edges if e.winfo_ismapped())))
    S.check(S.step, '금색 테두리가 실제로 그려짐(가려진 대상 위의 테두리 아님)', shown_edges == (False, 8), f'(숨김, 표시된 테두리) = {shown_edges}')
    geo = S.call(lambda: (S.root.state(), S.root.winfo_width(), S.root.winfo_height()))
    S.default_geometry = geo
    S.check(S.step, '최대화하지 않은 기본 창으로 진행', geo[0] == 'normal', f'상태 {geo[0]} · 내용 {geo[1]}x{geo[2]}')
    S.shot('step2_default_window', note=f'기본 창 {geo[1]}x{geo[2]}: STEP 2 [요청 확인] 강조'
           + (' — 가려짐' if target['covered'] else ''))
    if target['covered']:
        S.click(target, settle=1.0)  # 보이는 강조 테두리 안을 사용자가 누른 상황 재현
        S.check(S.step, '가려진 버튼 위치 실제 클릭 시 요청이 열리지 않음(재현)', S.call(lambda: session().story.onboarding.step) == 'request'
                and not top_by_title(S.snapshot(), 'AIDC LINK |'), '단계 그대로 request, 요청창 없음')
        S.note('사용자 행동처럼 관제실 창을 최대화합니다.')
        S.maximize_root()
        target = S.call(lambda: S.widget_info(app().tutorial_highlight.target))
        S.check(S.step + '→최대화', '최대화 후 [요청 확인] 버튼이 보이고 클릭 가능', not target['covered'], target['covered_by'])
    S.step = '4 요청 확인'
    maxi = layout_issues(S)
    S.check(S.step, '현재 관제실 창의 버튼·글자 가려짐/잘림/작업 영역 밖 없음', not maxi, f'{len(maxi)}건 ' + str(maxi[:8]))
    rack = S.call(lambda: (app().network.winfo_height(), app().network.columns))
    from server_console import rack_layout
    S.rack = {'canvas_height': rack[0], 'columns': rack[1], 'rack_height': rack[0]-40, 'layout': rack_layout(rack[1], rack[0]-40)}
    S.note(f'서버 랙 배치 {S.rack}')
    S.click(target, settle=1.5)
    S.wait_for(lambda: top_by_title(S.snapshot(), 'AIDC LINK |'), what='고객 요청서')
    off = centered(S, 'AIDC LINK |')
    record = placement(S, 'AIDC LINK |')
    S.check(S.step, '고객 요청서가 관제실 중앙(±8px)', off is not None and max(map(abs, off)) <= 8,
            f"중심 차이 {off} · 게임 기록 offset {record and record.get('offset')} target {record and record.get('target_client')} actual {record and record.get('actual_client')}")
    facts = S.call(lambda: (lambda r: {'gpu': r.state.plans['performance']['gpu'], 'power': r.state.plans['performance']['power'],
                                       'due': S.selector.app.session.deadline_summary(r), 'avail': S.selector.app.session.servers.available()})(session().current))
    labels = ' | '.join(i['text'] for i in top_by_title(S.snapshot(), 'AIDC LINK |')['labels'])
    S.note(f'요청 사실 {facts}')
    S.check(S.step, '요청서 GPU/전력 요구량이 실제 요청(고성능 모드)과 일치',
            'GPU 요구량' in labels and str(facts['gpu']) in labels and str(facts['power']) in labels, f"GPU {facts['gpu']} / 전력 {facts['power']}")
    S.check(S.step, '요청서의 현재 가용량이 실제 서버 가용량과 일치', f"현재 가용 {facts['avail'][0]}" in labels, f"가용 {facts['avail']}")
    issues = layout_issues(S, 'AIDC LINK |')
    S.check(S.step, '고객 요청서 창 안 버튼·글자 잘림/작업 영역 밖 없음', not issues, str(issues))
    S.shot('request', note='고객 요청서(AIDC LINK)' + (' — 하단 버튼이 작업 표시줄 아래로 밀림' if issues else ''))
    confirm = S.find('확인 · 운영실로')
    if confirm and confirm['offscreen']:
        S.note('[확인 · 운영실로]가 작업 영역 밖이므로 제목 표시줄 [X]로 닫습니다(사용자 대체 행동).')
        close_by_caption(S, 'AIDC LINK |')
        S.check(S.step, '[X]로 닫아도 요청 열람 기록 유지', S.call(lambda: session().story.onboarding.step) == 'preview'
                and not top_by_title(S.snapshot(), 'AIDC LINK |'))
    else:
        S.click_text('확인 · 운영실로', settle=1.0)
        still_open = bool(top_by_title(S.snapshot(), 'AIDC LINK |'))
        S.check(S.step, '[확인 · 운영실로] 첫 클릭으로 요청서가 닫힘', not still_open,
                '창이 남음: 타이핑이 끝나기 전 첫 클릭은 본문만 완성(MessageDialog.next → reveal)' if still_open else '')
        if still_open:
            S.monitor_open_dialog = S.call(lambda: (app().message_window is not None and app().message_window.winfo_exists(),
                                                    app().tutorial_highlight.key))
            S.note(f'요청서가 열린 동안 관제실 강조 상태 (메시지 창 열림, 강조 key) = {S.monitor_open_dialog}')
            S.shot('request_still_open', note='[확인 · 운영실로] 첫 클릭 뒤에도 요청서가 남음(본문 타이핑만 완성)', keep=False)
            S.click_text('확인 · 운영실로', settle=1.2)  # 사용자가 다시 누르는 행동
            S.check(S.step, '두 번째 클릭으로 요청서 닫힘', not top_by_title(S.snapshot(), 'AIDC LINK |'))
    S.check(S.step, '요청 열람 후 STEP 3/5(배정 검토)', S.call(lambda: session().story.onboarding.step) == 'preview')
    first_pos = record and record.get('actual_client')
    positions = [tuple(first_pos) if first_pos else None]
    for again in range(2):  # Q-02: 여러 번 열고 닫아도 같은 위치, 확인 버튼 한 번으로 닫힘
        S.click_text('AIDC LINK ·', settle=1.2)
        S.wait_for(lambda: top_by_title(S.snapshot(), 'AIDC LINK |'), what='요청서 다시 열기')
        rec = placement(S, 'AIDC LINK |')
        positions.append(tuple(rec['actual_client']) if rec else None)
        inside = not [i for i in layout_issues(S, 'AIDC LINK |') if 'offscreen' in i['flags']]
        S.click_text('확인 · 운영실로', settle=1.0)
        S.check(S.step, f'요청서 다시 열기 {again + 2}회차: 같은 위치·버튼 화면 안·확인 한 번에 닫힘',
                positions[-1] == positions[0] and inside and not top_by_title(S.snapshot(), 'AIDC LINK |'),
                f'위치 {positions}')

    # ---------------------------------------------------------------- 5. 배정 검토
    S.step = '5 배정 검토'
    def current_highlight():
        t = app().tutorial_highlight
        if t.target is None or not t.target.winfo_exists():
            return None
        return (t.key, S.widget_info(t.target)['text'] or str(t.target))
    try:
        hl = S.wait_for(lambda: S.call(current_highlight), timeout=4, what='STEP 3 금색 강조')
    except Exception:
        hl = (None, '강조 없음 · 열린 창: ' + ', '.join(t['title'] for t in S.snapshot()['tops']))
    card = S.call(lambda: session().story.onboarding.card['action'])
    S.note(f'목표 카드 "{card}" / 금색 강조 {hl}')
    S.check(S.step, '목표 카드 안내 버튼과 금색 강조 대상이 같은 위젯', '배정 설정' in card and '배정 설정' in str(hl[1]),
            f'목표 카드: {card} / 강조: key={hl[0]} ({hl[1]})')
    S.shot('step3_goal_vs_highlight', note=f'STEP 3: 목표 카드 "{card}" / 금색 강조 {hl[1]}')
    before = S.call(lambda: session().servers.available())
    S.click_text('배정 설정·선택', settle=1.5)
    S.wait_for(lambda: top_by_title(S.snapshot(), '배정 설정'), what='배정 설정창')
    off = centered(S, '배정 설정')
    placement(S, '배정 설정')
    S.check(S.step, '배정 설정창이 관제실 중앙(±8px)', off is not None and max(map(abs, off)) <= 8, f'중심 차이 {off}')
    snap = S.snapshot()
    dialog = top_by_title(snap, '배정 설정')
    start_btn = next(b for b in dialog['buttons'] if '선택한 계획으로 작업 시작' in b['text'])
    S.check(S.step, '배정안 선택 전 [작업 시작] 비활성', start_btn['state'] == 'disabled')
    S.check(S.step, '배정안 카드 3개 표시', sum(1 for b in dialog['buttons'] if b['text'].startswith('배정안')) == 3)
    S.check(S.step, '[작업 시작]·[닫기] 하단 버튼이 창 안·작업 영역 안',
            all(b['inside_top'] and not b['offscreen'] for b in dialog['buttons'] if b['text'] in ('닫기', '선택한 계획으로 작업 시작')))
    S.check(S.step, '배정창 금색 강조 대상 하나(배정안 1)', len(dialog['gold_edges']) == 8 and
            S.call(lambda: app().tutorial_highlight.key) == 'plan', f"edges={len(dialog['gold_edges'])}")
    S.shot('allocation', note='배정 설정창(운영 모드 카드·배정안 3개)')
    S.click_text('배정안 1 (추천)', settle=1.2)
    after = S.call(lambda: session().servers.available())
    S.check(S.step, '배정안 선택만으로는 자원 미점유', before == after == (10, 10), f'{before} → {after}')
    S.check(S.step, '배정안 선택 후 STEP 4/5·[작업 시작] 활성·강조 이동',
            S.call(lambda: (session().story.onboarding.step, app().tutorial_highlight.key)) == ('allocation', 'allocation')
            and S.find('선택한 계획으로 작업 시작', top='배정 설정 · 운영 모드와 서버 배정안 · v0.9-4b')['state'] == 'normal')
    S.shot('plan_selected', note='배정안 1 선택 · 시작 요약 · [작업 시작] 강조', keep=False)

    # ---------------------------------------------------------------- 6. 작업 시작
    S.step = '6 작업 시작'
    S.click_text('선택한 계획으로 작업 시작', settle=1.5)
    state = S.call(lambda: (lambda r, s: {'phase': r.state.phase, 'progress': r.state.progress, 'avail': s.servers.available(),
                                          'center': (s.center.available_gpu(), s.center.available_power()),
                                          'ledger': [(x.server_id, x.gpu, x.power) for x in s.servers.allocations[r.playthrough_id].slices]
                                          if r.playthrough_id in s.servers.allocations else None,
                                          'step': s.story.onboarding.step})(session().current, session()))
    S.note(f'시작 후 상태 {state}')
    S.check(S.step, '작업 실행 중(running)·진행률 0%', state['phase'] == 'running' and state['progress'] == 0)
    S.check(S.step, 'GPU 7·전력 7 점유 반영(가용 3/3, 서버 원장·전체 HUD 일치)', state['avail'] == (3, 3) and state['center'] == (3, 3))
    S.check(S.step, '서버 원장이 선택한 배정안 1(A 4/4, B 2/2, C 1/1)과 일치', state['ledger'] == [('A', 4, 4), ('B', 2, 2), ('C', 1, 1)], str(state['ledger']))
    hud = S.find('GPU 7/10 · 전력 7/10')
    S.check(S.step, '상단 HUD에 GPU 7/10 · 전력 7/10 표시', hud is not None)
    hl = S.call(lambda: {'key': app().tutorial_highlight.key, 'parts': [b.cget('text') for b in app().tutorial_highlight.parts],
                         'edges': len(app().tutorial_highlight.edges)})
    S.check(S.step, '시간 버튼 3개(+10/+30/+60분)가 각각 테두리 강조', hl['parts'] == ['+10분', '+30분', '+60분'] and hl['edges'] == 24, str(hl))
    golds = S.snapshot()['tops'][0]['gold_edges']
    label = S.find('⏩ 시간 빨리감기', exact=True, classes=('Label',))
    on_label = [g for g in golds if label and label['x'] <= g['x'] <= label['x'] + label['w'] and g['w'] < 10]
    S.check(S.step, '[시간 빨리감기] 라벨에는 테두리 없음', not on_label)
    S.shot('running_time_highlight', note='작업 진행 중 관제실 · 시간 버튼 3개 금색 테두리')

    # ---------------------------------------------------------------- 7. 시간 빨리감기
    S.step = '7 시간 빨리감기'
    events_before = len(S.monitor.events)
    thread, frames = S.burst(seconds=2.5)
    S.click_text('+10분', settle=0.2)
    thread.join()
    S.wait_for(lambda: top_by_title(S.snapshot(), '결과'), what='결과창')
    peak = max(frames, key=lambda f: f['white_ratio']) if frames else None
    base = frames[0]['white_ratio'] if frames else None
    S.note(f"연속 캡처 {len(frames)}장, 흰 비율 시작 {base} / 최대 {peak and peak['white_ratio']} (t={peak and peak['t']})")
    if peak:
        path = S.out / 'shots' / 'burst_peak.png'
        peak['img'].save(path)
    S.burst_summary = [{'t': f['t'], 'white_ratio': f['white_ratio'], 'windows': f['windows']} for f in frames]
    new_events = S.monitor.events[events_before:]
    flashes = [e for e in new_events if e['event'] == 'appear' and (e.get('white_ratio') or 0) > .35]
    moved = [e for e in new_events if e['event'] == 'move']
    S.check(S.step, '시간 진행 직후 흰 창 순간 표시 없음(창 등장 순간 캡처·연속 캡처)',
            not flashes and (peak is None or peak['white_ratio'] - base < .15),
            f'창 등장 {sum(1 for e in new_events if e["event"] == "appear")}건, 흰 창 후보 {len(flashes)}건, 등장 후 이동 {len(moved)}건, '
            f'연속 캡처 최대 흰 비율 {peak and peak["white_ratio"]} (기준 {base})')
    result = S.call(lambda: (lambda r, s: {'phase': r.state.phase, 'succeeded': r.state.succeeded, 'progress': r.state.progress,
                                           'status': r.request['status'], 'avail': s.servers.available(),
                                           'center': (s.center.available_gpu(), s.center.available_power()),
                                           'ledger': r.playthrough_id in s.servers.allocations, 'step': s.story.onboarding.step,
                                           'clock': s.clock_label if hasattr(s, 'clock_label') else None,
                                           'tutorial_completed': s.story.tutorial_completed})(session().current, session()))
    S.note(f'완료 후 상태 {result}')
    S.check(S.step, '+10분 진행으로 진행률 0% → 100% 증가', result['progress'] == 100, f"{result['progress']}%")
    S.check(S.step, '고객 업무 정상 완료(completed·성공)', result['status'] == 'completed' and result['succeeded'] is True and result['phase'] == 'finished')
    S.check(S.step, '완료 후 자원 반환(가용 10/10, 원장에서 제거)', result['avail'] == (10, 10) and result['center'] == (10, 10) and not result['ledger'])
    S.check(S.step, '튜토리얼 단계 complete', result['step'] == 'complete')

    # ---------------------------------------------------------------- 8. 결과창
    S.step = '8 결과창'
    off = centered(S, '결과')
    placement(S, '결과')
    S.check(S.step, '결과창이 관제실 중앙(±8px)', off is not None and max(map(abs, off)) <= 8, f'중심 차이 {off}')
    res = top_by_title(S.snapshot(), '결과')
    texts = [l['text'] for l in res['labels']]
    S.check(S.step, '결과창 MISSION SUCCESS 표시', 'MISSION SUCCESS' in texts)
    S.check(S.step, '처음부터 끝까지 관제실을 최대화하지 않음', S.call(lambda: S.root.state()) == 'normal')
    S.check(S.step, '결과창 점수·기한·반환 자원 = 100.0점 / 기한 내 완료 / GPU 7 · 전력 7',
            {'100.0점', '기한 내 완료', 'GPU 7 · 전력 7'} <= set(texts))
    S.check(S.step, '결과창 버튼 2개([다시 학습]·[메인 메뉴])', sorted(b['text'] for b in res['buttons']) == ['다시 학습', '메인 메뉴'],
            str([b['text'] for b in res['buttons']]))
    S.check(S.step, '결과창 버튼·글자 잘림/가려짐 없음', not layout_issues(S, '결과'), str(layout_issues(S, '결과')))
    buttons = res['buttons']
    if len(buttons) == 2:
        gap_left = buttons[0]['x'] - res['x']
        gap_right = res['x'] + res['w'] - (buttons[-1]['x'] + buttons[-1]['w'])
        S.note(f'결과창 버튼 좌우 여백 {gap_left} / {gap_right}, 버튼 높이 {[b["h"] for b in buttons]}')
        S.res_buttons = {'left': gap_left, 'right': gap_right, 'heights': [b['h'] for b in buttons]}
    S.shot('result', note='튜토리얼 성공 결과창')

    # ---------------------------------------------------------------- 9. 메인 메뉴 복귀
    S.step = '9 메인 메뉴'
    S.click_text('메인 메뉴', settle=1.5)
    S.wait_for(lambda: S.find('튜토리얼 처음부터') or S.find('시작 / 이어하기'), what='모드 선택 화면')
    S.check(S.step, '[메인 메뉴]로 같은 창에서 모드 선택 복귀', True)
    S.shot('back_to_menu', note='메인 메뉴 복귀', keep=False)


def main():
    # 기본 출력은 시스템 임시 폴더입니다(저장소에 추적되지 않는 캡처가 남지 않게).
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.gettempdir()) / 'srs_qa_tutorial_001'
    out.mkdir(parents=True, exist_ok=True)
    started = datetime.now().astimezone()
    hashes_before = repo_db_hashes()
    others = [w for w in own_windows()]
    h = Harness(out)
    h.env, h.placements = {}, []
    result = h.run(scenario)
    hashes_after = repo_db_hashes()
    leftovers = h.cleanup()
    commit = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    report = {
        'started': started.isoformat(timespec='seconds'), 'commit': commit, 'python': sys.version, 'platform': platform.platform(),
        'env': h.env, 'error': result['error'], 'clicks': h.clicks,
        'repo_db_unchanged': hashes_before == hashes_after, 'repo_db_count': len(hashes_before),
        'temp_files_removed': leftovers, 'checks': h.checks,
        'shots': h.shots, 'window_events': h.monitor.events, 'burst': getattr(h, 'burst_summary', []),
        'result_buttons': getattr(h, 'res_buttons', None), 'rack': getattr(h, 'rack', None), 'default_geometry': getattr(h, 'default_geometry', None), 'placements': h.placements, 'frame_offset_trace': h.frame_trace, 'log': h.log, 'preexisting_windows': len(others)}
    (out / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
    passed = sum(c['result'] == 'PASS' for c in h.checks)
    print(f"\n완료: 오류={result['error']} 검사 {passed}/{len(h.checks)} PASS · 실제 클릭 {h.clicks}회 · "
          f"사용자 DB 불변={hashes_before == hashes_after} · 결과 {out / 'result.json'}")


if __name__ == '__main__':
    main()
