"""Phase 6 글로벌 근무 세션: 기존 GameSession의 규칙(접수·조건 고정·동의·서버 원장·시간·기한·점수·저장)을
그대로 쓰면서 고객 요청을 카탈로그에서 받습니다.

* 접수: 카탈로그 템플릿마다 DB `missions` 행이 하나 있고, 기존 `_receive`가 버전 시나리오 키로 조건·기한을 고정합니다.
  요청 조건(`conditions`)에는 고객·도시·업무 의미(`catalog`)를 함께 고정해 저장합니다.
* 판정: 배정 가능 여부·고객 동의·서버 조각·만료·완료·점수는 모두 기존 메서드가 계산합니다. 이 모듈은 교대 근무의
  도착 일정과 교대 결과(엔진 기록의 집계)만 담당합니다.
* 저장: 기존 `simulation_state` JSON에 `mode='global'`, `global={...}`를 더합니다(SQL 구조 변경 없음).
* 이번 범위에서 장애 확률은 0입니다(새 장애 원인은 Phase 7). 재처리·같은 고객 재요청은 제공하지 않습니다.
"""
from __future__ import annotations

import random
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass, field, asdict

from database import Database
from game import game_time
from result_summary import outcome_key, OUTCOME_NAMES
from session import GameSession

from .catalog import load

KINDS = ('shift', 'free')
OPEN = ('new', 'review', 'waiting')
FREE_INTERVAL = 30
FREE_MAX_OPEN = 3
FREE_COOLDOWN = 90
COACHING_LABELS = {'full': '선배 안내 많음', 'short': '선배 안내 짧게', 'none': '선배 안내 없음'}


@dataclass
class GlobalProgress:
    version: int
    kind: str
    missions: dict
    shift: int | None = None
    start: int = 540
    briefed: bool = False
    delivered: list = field(default_factory=list)      # [[arrival index, request id], ...] 현재 교대
    result: dict | None = None                         # 현재 교대가 끝난 시점의 엔진 기록 집계(고정)
    history: list = field(default_factory=list)        # 끝난 이전 교대의 결과
    free_next: int = 0
    free_slot: int = 0
    free_last: dict = field(default_factory=dict)      # client id -> 마지막 접수 시각
    seen: list = field(default_factory=list)           # 표시만: 교대 결과 화면을 본 기록

    def payload(self):
        return asdict(self)

    @classmethod
    def from_payload(cls, value):
        if not isinstance(value, dict) or value.get('kind') not in KINDS or type(value.get('version')) is not int:
            raise ValueError('저장된 글로벌 근무 기록이 올바르지 않습니다.')
        allowed = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in value.items() if k in allowed})


def ensure_missions(db: Database, catalog):
    """새 글로벌 저장에 카탈로그 템플릿별 고객·업무 행을 만듭니다. 이 저장 파일 안에서만 실행합니다."""
    mapping = {}
    with db.transaction():
        for tid, company, country, title, description in catalog.mission_rows():
            row = db.conn.execute('SELECT id FROM clients WHERE company_name=? AND country=? ORDER BY id LIMIT 1',
                                  (company, country)).fetchone()
            client_id = row['id'] if row else db.conn.execute('INSERT INTO clients (company_name, country) VALUES (?, ?)',
                                                              (company, country)).lastrowid
            found = db.conn.execute('SELECT id FROM missions WHERE client_id=? AND title=?', (client_id, title)).fetchone()
            mapping[tid] = found['id'] if found else db.conn.execute(
                'INSERT INTO missions (client_id, title, description) VALUES (?, ?, ?)', (client_id, title, description)).lastrowid
    return mapping


class GlobalSession(GameSession):
    MODES = GameSession.MODES + ('global',)

    def __init__(self, db: Database, kind=None, shift=1, seed=None):
        self.catalog = load()
        saved = db.get_simulation()
        if saved:
            if saved.get('mode') != 'global':
                raise ValueError('글로벌 근무 저장이 아닙니다. 모드별 저장 파일을 사용해 주세요.')
            self.global_ = GlobalProgress.from_payload(saved.get('global'))
            if self.global_.version != self.catalog.version:
                raise ValueError(f'이 저장은 카탈로그 v{self.global_.version}로 만들어졌습니다. 같은 버전으로만 이어할 수 있습니다.')
        else:
            if db.get_requests():
                raise ValueError('기존 요청이 있는 저장에서는 글로벌 근무를 시작할 수 없습니다.')
            if kind not in KINDS:
                raise ValueError('글로벌 근무 종류(교대 근무 / 글로벌 자유 운영)를 골라 주세요.')
            if kind == 'shift' and str(shift) not in self.catalog.shifts:
                raise ValueError('존재하지 않는 교대 근무입니다.')
            self.global_ = GlobalProgress(self.catalog.version, kind, ensure_missions(db, self.catalog),
                                          shift=int(shift) if kind == 'shift' else None)
        self._mission_template = {mid: tid for tid, mid in self.global_.missions.items()}
        super().__init__(db, seed=seed, incident_chance=0, mode='global')
        if saved:
            self._validate_global()

    # ------------------------------------------------------------------ engine hooks
    def _extra_payload(self):
        return {'mode': 'global', 'global': self.global_.payload()}

    @contextmanager
    def _atomic(self):
        before = deepcopy(self.global_)
        try:
            with super()._atomic():
                yield
                self._update_shift()
        except Exception:
            self.global_ = before
            raise

    def _validate_global(self):
        missions = {mid: m for mid, m in self.missions.items()}
        for tid, mid in self.global_.missions.items():
            if tid not in self.catalog.templates or mid not in missions:
                raise ValueError('저장된 글로벌 고객·업무 연결이 카탈로그와 맞지 않습니다.')
            client = self.catalog.clients[self.catalog.templates[tid]['client']]
            if missions[mid]['company_name'] != client['name']:
                raise ValueError('저장된 고객 이름이 카탈로그와 다릅니다.')
        for rid, run in self.runs.items():
            found = self.catalog.template_of(run.state.scenario)
            meta = run.conditions.get('catalog') if run.conditions else None
            if found is None or not meta or meta.get('template') != found[0]:
                raise ValueError(f'요청 #{rid}의 카탈로그 업무를 찾을 수 없습니다.')
            if meta['fingerprint'] != self.catalog.describe(found[0])['fingerprint']:
                raise ValueError(f'요청 #{rid}의 업무 조건이 현재 카탈로그와 다릅니다(소급 재해석 금지).')
            if self._mission_template.get(run.mission['id']) != found[0]:
                raise ValueError(f'요청 #{rid}의 고객 업무 연결이 올바르지 않습니다.')

    def _message(self, mission, conditions):
        tid = self._mission_template.get(mission['id'])
        if tid is None:
            return super()._message(mission, conditions)
        meta = self.catalog.describe(tid)
        head = (f'[신규 작업 요청 · 가상 고객]\n발신: {meta["clientName"]} ({meta["industry"]})\n'
                f'위치: {meta["city"]}, {meta["countryName"]} · 사이트 {meta["site"]}\n업무 유형: {meta["jobLabel"]}\n\n')
        body = super()._message(mission, conditions)
        return head + body.split('\n\n', 1)[1]

    def _receive(self, mid, key=None, scenario=None):
        tid = self._mission_template.get(mid)
        if tid is None:
            raise ValueError('카탈로그에 없는 고객 업무는 글로벌 근무에서 접수하지 않습니다.')
        rid = super()._receive(mid, key, scenario or self.catalog.key(tid))
        run = self.runs[rid]
        if 'catalog' not in run.conditions:
            run.conditions['catalog'] = self.catalog.describe(tid)
        self.global_.free_last[self.catalog.templates[tid]['client']] = self.minute
        return rid

    def deliver_next_request(self):
        g = self.global_
        if self.runs:
            return None
        with self._atomic():
            g.start = self.minute
            if g.kind == 'shift':
                self._deliver_shift()
            else:
                g.free_next = self.minute + FREE_INTERVAL
                for tid in self._free_pick(self.minute, 2, exact=True):
                    self._receive(self.global_.missions[tid], f'gfree:{self.minute}:{tid}')
        return next(iter(self.runs), None)

    def _deliver_scheduled_requests(self):
        if self.global_.kind == 'shift':
            self._deliver_shift()
            return
        g = self.global_
        while self.minute >= g.free_next:
            due = g.free_next
            room = max(0, FREE_MAX_OPEN - self.pending_request_count)
            for tid in self._free_pick(due, room):
                self._receive(g.missions[tid], f'gfree:{due}:{tid}')
            g.free_next += FREE_INTERVAL
            g.free_slot += 1

    def _free_pick(self, due, room, exact=False):
        """글로벌 자유 운영의 재현 가능한 접수 추첨. 같은 고객은 열린 요청이 있거나 쿨다운 중이면 제외합니다."""
        if room <= 0:
            return []
        busy = {self.catalog.templates[self._mission_template[r.mission['id']]]['client'] for r in self.runs.values()
                if r.request['status'] in (*OPEN, 'operating')}
        last = self.global_.free_last
        eligible = [tid for tid, t in self.catalog.templates.items() if t['client'] not in busy
                    and due - last.get(t['client'], due - FREE_COOLDOWN) >= FREE_COOLDOWN]
        rng = random.Random(f'{self.seed}:global:{self.global_.free_slot}')
        rng.shuffle(eligible)
        counts = {}
        for r in self.runs.values():
            tid = self._mission_template[r.mission['id']]
            counts[tid] = counts.get(tid, 0) + 1
        eligible.sort(key=lambda tid: counts.get(tid, 0))
        amount = room if exact else min(room, rng.randint(1, 2))
        picked, clients = [], set()
        for tid in eligible:
            client = self.catalog.templates[tid]['client']
            if client not in clients:
                picked.append(tid)
                clients.add(client)
            if len(picked) >= amount:
                break
        return picked

    def _deliver_shift(self):
        g = self.global_
        if g.kind != 'shift' or g.result is not None:
            return
        done = {index for index, _ in g.delivered}
        for index, (at, tid) in enumerate(self.shift_def()['arrivals']):
            if index not in done and self.minute >= g.start + at:
                rid = self._receive(g.missions[tid], f'shift{g.shift}:{index}:{tid}')
                g.delivered.append([index, rid])

    # ------------------------------------------------------------------ shifts
    def shift_def(self, number=None):
        return self.catalog.shifts[str(number or self.global_.shift)]

    def shift_request_ids(self):
        return [rid for _, rid in self.global_.delivered]

    def _update_shift(self):
        g = self.global_
        if g.kind != 'shift' or g.result is not None:
            return
        arrivals = self.shift_def()['arrivals']
        if len(g.delivered) < len(arrivals):
            return
        if all(self.runs[rid].request['status'] in ('completed', 'rejected') for rid in self.shift_request_ids()):
            g.result = self.shift_result()

    def confirm_shift_briefing(self):
        if self.global_.kind != 'shift':
            raise ValueError('교대 근무에서만 브리핑을 확인합니다.')
        if not self.global_.briefed:
            with self._atomic():
                self.global_.briefed = True

    def mark_shift_seen(self, key):
        if not isinstance(key, str) or len(key) > 40:
            raise ValueError('표시 기록 형식이 올바르지 않습니다.')
        if key not in self.global_.seen:
            with self._atomic():
                self.global_.seen.append(key)

    def advance_time(self, minutes):
        g = self.global_
        if g.kind == 'shift' and not g.briefed:
            raise ValueError('먼저 교대 브리핑을 확인하고 근무를 시작해 주세요.')
        return super().advance_time(minutes)

    def next_shift(self):
        g = self.global_
        if g.kind != 'shift':
            return None
        nxt = str(g.shift + 1)
        return int(nxt) if nxt in self.catalog.shifts else None

    def next_shift_reason(self):
        g = self.global_
        if g.kind != 'shift':
            return '글로벌 자유 운영에는 교대 순서가 없습니다.'
        if g.result is None:
            return '현재 교대의 모든 요청이 끝나야 다음 교대를 시작할 수 있습니다.'
        if not g.result['cleared']:
            return '현재 교대의 목표를 달성하지 못했습니다. 이 교대를 새 슬롯에서 다시 도전하세요.'
        if self.next_shift() is None:
            return '마지막 교대입니다.'
        return ''

    def start_next_shift(self):
        reason = self.next_shift_reason()
        if reason:
            raise ValueError(reason)
        g = self.global_
        with self._atomic():
            g.history.append(g.result)
            g.shift, g.start, g.briefed, g.delivered, g.result = self.next_shift(), self.minute, False, [], None
            self._deliver_shift()
            self.selected_id = self.shift_request_ids()[0]
        return g.shift

    def request_hint(self, rid):
        """선배의 짧은 안내: 교대 1은 템플릿의 '왜 다른가', 교대 2는 업무 유형 한 줄, 교대 3·자유 운영은 없음."""
        run = self.runs.get(rid)
        meta = run.conditions.get('catalog') if run and run.conditions else None
        if not meta or self.global_.kind != 'shift':
            return None
        coaching = self.shift_def()['coaching']
        if coaching == 'full':
            return self.catalog.templates[meta['template']].get('why') or None
        if coaching == 'short':
            return self.catalog.jobs[meta['jobType']]['game']
        return None

    def shift_briefing(self):
        """교대 시작 대화(선배/시스템). 교대가 진행될수록 짧아집니다."""
        if self.global_.kind != 'shift':
            return [('system', '글로벌 자유 운영 · 시간에 따라 세계 여러 도시의 가상 고객 요청이 계속 도착합니다. 진급 기록은 없습니다.')]
        d = self.shift_def()
        pages = {'full': [('mentor', f'오늘은 {d["title"]}이에요.\n{d["intro"]}'),
                          ('mentor', '요청함에서 도시·업종·업무 유형부터 보세요.\n원래 조건과 고객이 허용한 모드가 요청마다 달라요.'),
                          ('mentor', '세계지도에는 실제로 도착한 요청의 도시만 불이 들어와요.\n준비되면 [근무 시작]을 눌러요.')],
                 'short': [('mentor', f'{d["title"]}입니다. {d["intro"]}'),
                           ('mentor', '안내는 짧게만 할게요.\n동의 없이 고객 조건을 바꾸지 않는 것만 기억해요.')],
                 'none': [('system', f'교대 {self.global_.shift} · {d["title"]} — {d["intro"]}')]}
        return pages[d['coaching']]

    def _consent_label(self, run):
        s = run.state
        if s.plan is None:
            return '배정 없음'
        proposal = run.proposals[-1] if run.proposals else None
        if proposal and proposal['status'] == 'accepted' and s.plan == proposal['proposed']['mode']:
            return '고객 동의 대안'
        if run.conditions and s.plan != run.conditions['requested_mode']:
            return '고객 허용 모드'
        return '원래 요청 조건'

    def _row(self, rid):
        run = self.runs[rid]
        meta, t, key = run.conditions['catalog'], run.terms, outcome_key(run)
        proposal = run.proposals[-1] if run.proposals else None
        return {'rid': rid, 'template': meta['template'], 'client': meta['clientName'], 'industry': meta['industry'],
                'site': meta['site'], 'city': meta['city'], 'country': meta['countryName'], 'job': meta['jobLabel'],
                'outcome': key, 'label': OUTCOME_NAMES[key],
                'score': t.get('evaluation') if key in ('on_time', 'late', 'expired') else None,
                'mode': run.state.plans[run.state.plan]['label'] if run.state.plan else None,
                'consent': self._consent_label(run), 'proposal': proposal['status'] if proposal else None,
                'received': game_time(t['received']), 'started': game_time(t['started']) if 'started' in t else None,
                'completed': game_time(t['completed']) if 'completed' in t else None, 'due': game_time(t['due']),
                'waited': max(0, t.get('started', t.get('completed', self.minute)) - t['received']),
                'late': t.get('late_minutes') or 0, 'reason': run.request['rejection_reason']}

    def shift_result(self):
        """엔진 기록만 모은 교대 결과. 목표 판정은 카탈로그의 교대 목표(정상 완료 수·만료 허용 수)를 씁니다."""
        g = self.global_
        rows = [self._row(rid) for rid in self.shift_request_ids()]
        count = {k: sum(r['outcome'] == k for r in rows) for k in OUTCOME_NAMES}
        success = count['on_time'] + count['late']
        scored = [r['score'] or 0 for r in rows if r['outcome'] != 'rejected']
        goal = self.shift_def()['goal']
        cleared = success >= goal['minSuccess'] and count['expired'] <= goal['maxExpired']
        return {'shift': g.shift, 'title': self.shift_def()['title'], 'cleared': cleared, 'rows': rows, 'counts': count,
                'success': success, 'total': len(rows), 'goal': goal,
                'average': round(sum(scored) / len(scored)) if scored else 0,
                'finished': game_time(self.minute), 'started': game_time(g.start),
                'feedback': self._growth(rows, count, cleared)}

    def _growth(self, rows, count, cleared):
        lines = []
        agreed = [r for r in rows if r['consent'] == '고객 동의 대안']
        refused = [r for r in rows if r['proposal'] == 'rejected']
        waited = [r for r in rows if r['started'] and r['waited'] >= 20]
        if agreed:
            lines.append('고객 동의를 받은 대안: ' + ', '.join(f'{r["city"]} {r["client"]}' for r in agreed)
                         + ' — 조건을 몰래 바꾸지 않고 자원을 나눴습니다.')
        if refused:
            lines.append('고객이 거절한 대안: ' + ', '.join(f'{r["city"]} {r["client"]}' for r in refused)
                         + ' — 기한을 넘기는 제안은 받아들여지지 않습니다.')
        if waited:
            lines.append('기다렸다 시작한 요청: ' + ', '.join(f'{r["city"]}({r["waited"]}분)' for r in waited)
                         + ' — 여유 있는 요청은 기다리게 하고 급한 요청을 먼저 처리했습니다.')
        if count['late']:
            lines.append('완료 기한을 넘긴 요청: ' + ', '.join(f'{r["city"]} {r["late"]}분' for r in rows if r['outcome'] == 'late'))
        if count['expired']:
            lines.append('시작하지 못해 만료된 요청: ' + ', '.join(f'{r["city"]} {r["client"]}' for r in rows if r['outcome'] == 'expired')
                         + ' — 최종 접수 시각이 촉박한 요청을 먼저 보세요.')
        if count['rejected']:
            lines.append('사유와 함께 거절한 요청: ' + ', '.join(f'{r["city"]} ({r["reason"]})' for r in rows if r['outcome'] == 'rejected'))
        lines.append('교대 목표 달성' if cleared else '교대 목표 미달성 — 같은 교대를 새 슬롯에서 다시 도전할 수 있습니다.')
        return lines

    def shift_status(self):
        """조회 전용 요약(화면용)."""
        g = self.global_
        if g.kind != 'shift':
            return {'kind': 'free', 'open': self.pending_request_count, 'received': len(self.runs),
                    'next': game_time(g.free_next)}
        d = self.shift_def()
        rows = [self.runs[rid] for rid in self.shift_request_ids()]
        return {'kind': 'shift', 'shift': g.shift, 'title': d['title'], 'subtitle': d['subtitle'], 'coaching': d['coaching'],
                'coachingLabel': COACHING_LABELS[d['coaching']], 'intro': d['intro'], 'briefed': g.briefed,
                'total': len(d['arrivals']), 'arrived': len(g.delivered),
                'closed': sum(r.request['status'] in ('completed', 'rejected') for r in rows),
                'success': sum(outcome_key(r) in ('on_time', 'late') for r in rows),
                'goal': d['goal'], 'started': game_time(g.start), 'done': g.result is not None,
                'result': deepcopy(g.result), 'history': deepcopy(g.history),
                'next': self.next_shift(), 'nextReason': self.next_shift_reason()}

    # Global work has no retry chain and no "same customer again" button (requests arrive on their own schedule).
    def retry(self, key):
        raise ValueError('글로벌 근무에서는 재처리를 제공하지 않습니다. [처리 불가 보고]로 종료해 주세요.')

    def restart(self):
        raise ValueError('글로벌 근무의 새 요청은 일정에 따라 도착합니다.')

    @property
    def has_next_request(self):
        return False
