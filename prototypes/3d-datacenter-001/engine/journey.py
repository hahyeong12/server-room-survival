"""3D tutorial journey: which real actions the player has already done.

The journey never changes game rules. Engine facts (read request, chosen plan, started job, server health,
finished job) come from session.GameSession; 3D-only facts (where the player navigated, which country /
building / rack they looked at, whether they opened the diagnosis or re-checked after recovery) are events
recorded *after* the player really performed them through the UI. A step is done only when its own fact
is true while it is the current step, so clicking [다음] in a dialogue, skipping, reviewing, reloading or
going back in the browser cannot advance it.
"""
from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path

VERSION = 1
MAX_EVENTS = 300
BUILDINGS = ('NOC', 'HALL-01', 'POWER', 'UPS', 'COOLING', 'NETWORK')
ROUTES = ('world', 'campus', 'noc', 'hall', 'room')
ENTER_VIA = ('dblclick', 'key', 'button')
BACK_VIA = ('back', 'crumb')


def _after(events, since, kind, **match):
    """Events of `kind` recorded after sequence `since` whose fields equal `match` (callables are predicates)."""
    out = []
    for e in events:
        if e['seq'] <= since or e['type'] != kind:
            continue
        if all(v(e.get(k)) if callable(v) else e.get(k) == v for k, v in match.items()):
            out.append(e)
    return out


# Each step: id, short title, what to do (one sentence), why it matters, where the real control is,
# a highlight target for the client, and the completion predicate (facts, events-after-since) -> bool.
TUTORIAL = (
    ('explore', '캠퍼스 둘러보기', (
        {'id': 'briefing', 'title': '선배 브리핑', 'what': '선배의 말을 읽고 [근무 시작]을 누르세요.',
         'why': '오늘 할 일과 화면의 역할을 먼저 알아 둡니다.', 'where': '화면 가운데 선배 대화창',
         'target': {'kind': 'dom', 'selector': '#coach-start'},
         'done': lambda f, ev: f['introduced']},
        {'id': 'campus-info', 'title': '건물 정보 보기', 'what': '[울산 캠퍼스]로 가서 건물 하나를 한 번 클릭하세요.',
         'why': '한 번 클릭은 정보만 보여 주고 아무것도 바꾸지 않습니다.', 'where': '위쪽 [울산 캠퍼스] → 3D 건물',
         'target': {'kind': 'route', 'route': 'campus', 'then': {'kind': 'campus', 'id': 'facility:COOLING'}},
         'done': lambda f, ev: bool(_after(ev, f['since'], 'select_facility', route='campus', via=lambda v: v in ('pick', 'chip')))},
        {'id': 'enter', 'title': '건물 안으로', 'what': '같은 건물을 두 번 클릭해 안으로 들어가 보세요.',
         'why': '두 번 클릭(또는 Enter)은 건물 내부로 이동합니다.', 'where': '3D 건물 두 번 클릭',
         'target': {'kind': 'campus-selected'},
         'done': lambda f, ev: bool(_after(ev, f['since'], 'navigate', via=lambda v: v in ENTER_VIA))},
        {'id': 'back', 'title': '돌아오기', 'what': '[← 상위 공간]을 눌러 캠퍼스로 돌아오세요.',
         'why': '어디에 있든 상위 공간으로 돌아올 수 있습니다.', 'where': '왼쪽 위 [← 상위 공간]',
         'target': {'kind': 'dom', 'selector': '#back'},
         'done': lambda f, ev: bool(_after(ev, f['since'], 'navigate', route='campus', via=lambda v: v in BACK_VIA))},
    )),
    ('request', '요청 확인', (
        {'id': 'world', 'title': '세계지도 열기', 'what': '새 고객 요청이 도착했어요. [세계지도]를 여세요.',
         'why': '요청이 어느 나라에서 어떤 경로로 오는지 봅니다.', 'where': '위쪽 [세계지도]',
         'target': {'kind': 'dom', 'selector': '#places [data-route=world]'},
         'done': lambda f, ev: bool(_after(ev, f['since'], 'navigate', route='world'))},
        {'id': 'origin', 'title': '요청 출처 찾기', 'what': '빛나는 경로의 출발 국가를 지도에서 직접 클릭하세요.',
         'why': '요청이 실제로 도착한 경로만 점등됩니다. 다른 나라는 비어 있어요.', 'where': '3D 세계지도의 점등 경로 끝',
         'target': {'kind': 'world-request'},
         'done': lambda f, ev: bool(f['code'] and _after(ev, f['since'], 'select_country', id=f['code']))},
        {'id': 'read', 'title': '요청서 읽기', 'what': '[관제동 · 내 자리]의 내 모니터 요청함에서 요청을 열어 조건을 읽으세요.',
         'why': 'GPU·전력·네트워크·기한·허용 모드가 고객과의 약속입니다.', 'where': '내 모니터 → 요청함 → [요청서 열기]',
         'target': {'kind': 'dom', 'selector': '[data-read-request]', 'route': 'noc'},
         'done': lambda f, ev: f['read']},
    )),
    ('plan', '배정 결정', (
        {'id': 'compare', 'title': '배정안 비교', 'what': '내 모니터 [배정 계획] 탭을 열어 두 운영 모드와 후보 배정안을 비교하세요.',
         'why': '고객이 허용한 모드인지, 자원이 충분한지 엔진이 계산한 결과를 봅니다.', 'where': '내 모니터 → [배정 계획] 탭',
         'target': {'kind': 'dom', 'selector': '[data-ws-tab=plan]', 'route': 'noc'},
         'done': lambda f, ev: bool(_after(ev, f['since'], 'view_plans', rid=f['rid']))},
        {'id': 'choose', 'title': '배정안 선택', 'what': '고객 조건에 맞는 배정안 카드 하나를 직접 고르세요.',
         'why': '고르기만 해서는 자원을 쓰지 않습니다. 시작은 현장에서 합니다.', 'where': '내 모니터 → 배정안 카드',
         'target': {'kind': 'dom', 'selector': '[data-plan-list]', 'route': 'noc'},
         'done': lambda f, ev: f['reviewed'] and f['selected']},
    )),
    ('site', '현장 시작', (
        {'id': 'hall', 'title': '서버동 이동', 'what': '[서버동 01]로 이동하세요.',
         'why': '작업은 실제 서버가 있는 현장 건물에서 시작합니다.', 'where': '위쪽 [서버동 01]',
         'target': {'kind': 'dom', 'selector': '#places [data-route=hall]'},
         'done': lambda f, ev: bool(_after(ev, f['since'], 'navigate', route='hall'))},
        {'id': 'rack', 'title': '배정 서버 찾기', 'what': '고른 배정안에 들어 있는 서버 랙을 3D 화면에서 직접 클릭하세요.',
         'why': '엔진 서버 A~D는 1번 열의 랙 A-01~D-01입니다. 나머지 랙은 장식입니다.', 'where': '서버동 3D 랙',
         'target': {'kind': 'racks-of-plan'},
         'done': lambda f, ev: bool(_after(ev, f['since'], 'inspect_rack', server=lambda v: v in f['plan_servers']))},
        {'id': 'start', 'title': '작업 시작', 'what': '선택한 랙 카드에서 [이 배정으로 작업 시작]을 누르세요.',
         'why': '이 순간 엔진이 고객 동의·자원·서버 조합을 다시 검사하고 GPU·전력을 점유합니다.', 'where': '오른쪽 랙 카드',
         'target': {'kind': 'dom', 'selector': '[data-start-job]', 'route': 'hall'},
         'done': lambda f, ev: f['started']},
    )),
    ('incident', '장애 대응', (
        {'id': 'time', 'title': '시간 진행', 'what': '위쪽 [⏩ +10분]으로 가상 시간을 진행하세요.',
         'why': '시간이 흘러야 작업량이 쌓입니다. 무엇이 바뀌는지 보세요.', 'where': '위쪽 시계 옆 [⏩ +10분]',
         'target': {'kind': 'dom', 'selector': '[data-advance="10"]'},
         'done': lambda f, ev: f['fault_server'] is not None},
        {'id': 'diagnose', 'title': '증거 확인', 'what': '경보가 울렸어요. 내 모니터 [장비 진단]을 열어 원인과 가능한 조치를 확인하세요.',
         'why': '조치 전에 증상(진행률 0%)과 원인(서버 상태)을 구분합니다.', 'where': '내 모니터 → [장비 진단] 탭',
         'target': {'kind': 'dom', 'selector': '[data-ws-tab=diagnosis]', 'route': 'noc'},
         'done': lambda f, ev: bool(_after(ev, f['since'], 'diagnose', rid=f['rid']))},
        {'id': 'respond', 'title': '대응 선택', 'what': '진단 결과를 근거로 대응 하나를 고르세요.',
         'why': '이전·복구·네트워크 우회는 서로 다른 문제를 고칩니다. 엔진이 조건을 검사합니다.', 'where': '내 모니터 → 장비 진단 → 대응',
         'target': {'kind': 'dom', 'selector': '[data-responses]', 'route': 'noc'},
         'done': lambda f, ev: f['responded']},
        {'id': 'recover', 'title': '복구 기다리기', 'what': '시간을 진행해 장비 복구(또는 이전 준비)를 끝내세요.',
         'why': '복구에도 가상 시간이 걸립니다. 버튼 하나로 끝나지 않아요.', 'where': '위쪽 [⏩] 시간 버튼',
         'target': {'kind': 'dom', 'selector': '[data-advance="10"]'},
         'done': lambda f, ev: f['recovered']},
    )),
    ('wrap', '검증·보고', (
        {'id': 'verify', 'title': '사후 확인', 'what': '서버동에서 장애가 났던 랙을 다시 클릭하고 [상태 재확인]을 누르세요.',
         'why': '복구됐다는 알림과 실제로 정상인지 확인하는 것은 다른 일입니다.', 'where': '서버동 → 해당 랙 카드 → [상태 재확인]',
         'target': {'kind': 'fault-rack'},
         'done': lambda f, ev: bool(_after(ev, f['since'], 'verify', ok=True))},
        {'id': 'finish', 'title': '작업 마무리', 'what': '시간을 진행해 작업을 100%까지 끝내세요.',
         'why': '작업이 끝나면 엔진이 GPU·전력을 반환하고 점수를 계산합니다.', 'where': '위쪽 [⏩] 시간 버튼',
         'target': {'kind': 'dom', 'selector': '[data-advance="10"]'},
         'done': lambda f, ev: f['finished']},
        {'id': 'report', 'title': '결과 보고 확인', 'what': '내 모니터 [결과] 탭에서 고객 회신과 결과를 확인하세요.',
         'why': '원래 조건·실행 조건·자원 반환·점수를 한 번에 대조합니다.', 'where': '내 모니터 → [결과] 탭',
         'target': {'kind': 'dom', 'selector': '[data-ws-tab=result]', 'route': 'noc'},
         'done': lambda f, ev: f['reported']},
    )),
)
STEP_IDS = tuple(step['id'] for _, _, steps in TUTORIAL for step in steps)
LEARNED = ('세계지도·캠퍼스·건물 내부를 오가는 법 (한 번 클릭 = 정보, 두 번 클릭 = 내부)',
           '요청이 실제로 도착한 경로만 점등된다는 것과 고객의 원래 조건 읽기',
           '고객이 허용한 모드 안에서 배정안을 비교·선택하기 (동의 없는 변경은 엔진이 거부)',
           '현장에서 배정 서버를 찾아 작업 시작 · 엔진의 자원 점유',
           '증상과 원인을 구분하는 장비 진단 → 근거 있는 대응 → 가상 시간이 드는 복구',
           '복구 후 재확인과 결과·자원 반환·점수 대조')


class Journey:
    """Persisted 3D-side facts for one save. kind: 'tutorial' (guided steps) | 'story' | 'free' (events only)."""

    def __init__(self, path: Path | None, kind: str):
        if kind not in ('tutorial', 'story', 'free'):
            raise ValueError('unknown journey kind')
        self.path = Path(path) if path is not None else None
        self.data = {'version': VERSION, 'kind': kind, 'seq': 0, 'events': [], 'done': {}, 'skipped': False,
                     'fault': None, 'selection': {}, 'route': 'noc', 'misclicks': 0, 'reported': []}
        if self.path is not None and self.path.is_file():
            loaded = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(loaded, dict) or loaded.get('version') != VERSION or loaded.get('kind') != kind:
                raise ValueError('3D 진행 기록이 이 저장과 맞지 않습니다.')
            self.data.update(loaded)

    # ---- persistence -------------------------------------------------------------------------------------
    @property
    def kind(self):
        return self.data['kind']

    def save(self):
        if self.path is None:
            return
        tmp = self.path.with_name(self.path.name + '.tmp')
        tmp.write_text(json.dumps(self.data, ensure_ascii=False), encoding='utf-8')
        os.replace(tmp, self.path)

    def transaction(self):
        """Snapshot for rollback when an engine call fails after the journey changed in memory."""
        return deepcopy(self.data)

    def rollback(self, snapshot):
        self.data = snapshot

    # ---- facts -------------------------------------------------------------------------------------------
    def record(self, kind, minute, **fields):
        self.data['seq'] += 1
        event = {'seq': self.data['seq'], 'type': kind, 'minute': minute, **fields}
        self.data['events'].append(event)
        del self.data['events'][:-MAX_EVENTS]
        if kind == 'navigate' and fields.get('route') in ROUTES:
            self.data['route'] = fields['route']
        return event

    def misclick(self):
        self.data['misclicks'] += 1

    @property
    def route(self):
        return self.data['route']

    def selection(self, rid):
        return self.data['selection'].get(str(rid))

    def set_selection(self, rid, value):
        if value is None:
            self.data['selection'].pop(str(rid), None)
        else:
            self.data['selection'][str(rid)] = value

    def skip(self):
        self.data['skipped'] = True

    # ---- tutorial evaluation -----------------------------------------------------------------------------
    def evaluate(self, facts):
        """Mark the current step (and following ones) done while their facts hold. Returns newly done ids."""
        if self.kind != 'tutorial':
            return []
        done, newly = self.data['done'], []
        events = self.data['events']
        while True:
            current = self.current_step()
            if current is None:
                return newly
            since = max(done.values(), default=0)
            if not current['done']({**facts, 'since': since}, events):
                return newly
            done[current['id']] = self.data['seq']
            newly.append(current['id'])

    def current_step(self):
        for _, _, steps in TUTORIAL:
            for step in steps:
                if step['id'] not in self.data['done']:
                    return step
        return None

    @property
    def completed(self):
        return self.kind == 'tutorial' and all(s in self.data['done'] for s in STEP_IDS)

    def view(self):
        """Client view (no predicates). Goals list with step states and the single current step."""
        if self.kind != 'tutorial':
            return {'kind': self.kind, 'misclicks': self.data['misclicks']}
        current = self.current_step()
        goals = []
        for index, (gid, title, steps) in enumerate(TUTORIAL, start=1):
            states = [{'id': s['id'], 'title': s['title'], 'done': s['id'] in self.data['done']} for s in steps]
            goals.append({'id': gid, 'index': index, 'title': title, 'steps': states,
                          'done': all(s['done'] for s in states),
                          'current': current is not None and any(s['id'] == current['id'] for s in steps)})
        cur = None
        if current is not None:
            goal = next(g for g in goals if g['current'])
            cur = {k: current[k] for k in ('id', 'title', 'what', 'why', 'where', 'target')}
            cur.update(goal=goal['id'], goalIndex=goal['index'], goalTitle=goal['title'])
        return {'kind': 'tutorial', 'goals': goals, 'total': len(goals), 'current': cur,
                'completed': self.completed, 'skipped': self.data['skipped'], 'misclicks': self.data['misclicks'],
                'doneSteps': len(self.data['done']), 'totalSteps': len(STEP_IDS),
                'learned': list(LEARNED) if self.completed else []}
