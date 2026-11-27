"""Versioned, seeded global free shifts. Uses the real incident and resource engines.

Old GlobalSession saves are intentionally not migrated. No wall-clock timers or OS calls.
"""
from contextlib import contextmanager
from copy import deepcopy
import random
import hashlib
import json

from aidc.global_ops.session import GlobalSession, BRIEFING_LOCK
from aidc.incidents.session import IncidentSession, IncidentBook, IncidentRecord, FINAL, OPEN
from aidc.incidents.content import load
from aidc.incidents.operating_rules import OperatingRules, FINGERPRINT
from aidc.learning.linux_session import LinuxSession

DIFFICULTIES = {
    'none': {'label': '무사건 연습', 'interval': 0, 'maximum': 0},
    'relaxed': {'label': '편안한', 'interval': 80, 'maximum': 1},
    'standard': {'label': '표준', 'interval': 40, 'maximum': 2},
    'challenge': {'label': '도전', 'interval': 20, 'maximum': 2},
}
SCHEDULE_FINGERPRINT = hashlib.sha256(json.dumps(
    [DIFFICULTIES, FINGERPRINT, 'eligible-v1:remaining20/slack60;closing-no-injection;optional-cli'], sort_keys=True).encode()).hexdigest()


class FreeShiftSession(OperatingRules, LinuxSession):
    SAVE_MODE = 'global'
    learning_optional = True

    def __init__(self, db, seed=None, difficulty='standard'):
        self.content = load()
        saved = db.get_simulation()
        if saved:
            value = saved.get('free_incidents')
            if not isinstance(value, dict) or value.get('version') != 1:
                raise ValueError('이 저장은 새 자유 교대 형식이 아닙니다. 기존 글로벌 저장은 기존 모드로 이어하세요.')
            self.free_incidents = deepcopy(value)
            self.incident = IncidentBook.from_payload(saved.get('incident'))
        else:
            if not isinstance(difficulty, str) or difficulty not in DIFFICULTIES:
                raise ValueError('장애 빈도는 무사건/편안한/표준/도전 중에서 선택하세요.')
            if seed is not None and (type(seed) is not int or not 0 <= seed < 2**31):
                raise ValueError('seed는 0~2147483647 정수입니다.')
            self.free_incidents = {'version': 1, 'rules': SCHEDULE_FINGERPRINT, 'difficulty': difficulty, 'cursor': 0,
                                   'last': None, 'next': None, 'events': [], 'closing': False}
            self.incident = IncidentBook(self.content.version)
        if saved:
            value = saved.get('linux')
            if not isinstance(value, dict) or value.get('version') != 1 or value.get('fingerprint') != self._fingerprint():
                raise ValueError('자유 교대의 가상 터미널 기록 형식이 올바르지 않습니다.')
            self.linux = deepcopy(value)
        else:
            self.linux = {'version': 1, 'fingerprint': self._fingerprint(), 'practice': None,
                          'seq': 0, 'observations': [], 'interpretations': [], 'help': []}
        GlobalSession.__init__(self, db, kind='free', seed=seed)
        self._validate_free()
        self._validate_learning()
        if saved:
            self._validate_incidents()

    def _validate_free(self):
        f = self.free_incidents
        if isinstance(f.get('rules'), str) and f['rules'] != SCHEDULE_FINGERPRINT:
            raise ValueError('이 자유 교대는 이전 버전의 Phase 9 운영 규칙(사건 일정·임시 우회 비용)으로 만들어졌습니다. '
                             '규칙을 바꿔 다시 해석하지 않도록 열지 않습니다. 원본 저장은 보존됩니다. 새 자유 교대를 시작하세요.')
        if (self.global_.kind != 'free' or self.incident.version != self.content.version or f.get('rules') != SCHEDULE_FINGERPRINT or
                not isinstance(f.get('difficulty'), str) or f['difficulty'] not in DIFFICULTIES or type(f.get('cursor')) is not int or
                f['cursor'] < 0 or type(f.get('closing')) is not bool or not isinstance(f.get('events'), list)):
            raise ValueError('자유 교대 기록이 올바르지 않습니다. 원본 저장은 보존됩니다.')
        interval = DIFFICULTIES[f['difficulty']]['interval']
        if self.global_.briefed and self.global_.result is None and interval and not f['closing'] and f.get('next') is None:
            raise ValueError('저장된 사건 일정이 비어 있습니다. 원본 저장은 보존됩니다.')
        for key in ('last', 'next'):
            if f.get(key) is not None and (type(f[key]) is not int or f[key] % 10 or f[key] < self.global_.start):
                raise ValueError('저장된 사건 시각이 올바르지 않습니다.')
        if len(f['events']) != len(self.incident.records) or len(f['events']) > f['cursor']:
            raise ValueError('사건 생성 이력과 사건 원장이 일치하지 않습니다.')
        previous = 0
        for event, rec in zip(f['events'], self.incident.records):
            if (not isinstance(event, dict) or type(event.get('cursor')) is not int or
                    not previous < event['cursor'] <= f['cursor'] or type(event.get('minute')) is not int or
                    event['minute'] < self.global_.start or event['minute'] % 10 or
                    event.get('id') != rec.id or event.get('rid') != rec.rid or
                    event.get('type') != rec.type or event['minute'] != rec.detected):
                raise ValueError('저장된 사건 생성 이력이 올바르지 않습니다.')
            previous = event['cursor']

    def _extra_payload(self):
        return {**super()._extra_payload(), 'free_incidents': deepcopy(self.free_incidents)}

    @contextmanager
    def _atomic(self):
        before = deepcopy(self.free_incidents)
        try:
            with super()._atomic():
                yield
        except Exception:
            self.free_incidents = before
            raise

    def _require_briefed(self):
        if self.global_.result is not None:
            raise ValueError('마친 교대입니다. 결과를 확인하거나 새 자유 교대를 시작하세요.')
        if not self.global_.briefed:
            raise ValueError(BRIEFING_LOCK)

    def confirm_shift_briefing(self):
        if self.global_.result is not None:
            raise ValueError('이미 마친 교대입니다.')
        if not self.global_.briefed:
            with self._atomic():
                self.global_.briefed = True
                interval = DIFFICULTIES[self.free_incidents['difficulty']]['interval']
                self.free_incidents['next'] = self.minute + interval if interval else None

    def advance_time(self, minutes):
        self._require_briefed()
        return super().advance_time(minutes)

    def _deliver_scheduled_requests(self):
        if not self.free_incidents['closing'] and self.global_.briefed:
            super()._deliver_scheduled_requests()

    def shift_def(self, number=None):
        return {'code': 'FREE', 'title': '글로벌 자유 교대', 'coaching': 'short', 'subtitle': '진급 없는 운영 연습',
                'role': '자유 교대 운영 담당', 'rank': '연습 · 진급 없음', 'input': 'terminal',
                'intro': '요청 조건과 실제 서버 상황에 따라 돌발 사건이 발생합니다. 마무리를 누르면 새 접수를 멈춥니다.',
                'goal': {'minSuccess': 0, 'maxExpired': 999, 'minResolved': 0, 'notifyBeforeRecovery': False}}

    def shift_briefing(self):
        d = DIFFICULTIES[self.free_incidents['difficulty']]
        return [('mentor', f'글로벌 자유 교대 · {d["label"]} · seed {self.seed}\n고객 조건을 읽고 배정하세요. 시간은 위쪽 시간 버튼으로만 흐릅니다.'),
                ('mentor', '경보가 오면 사건 탭에서 범위·근거·원인을 확인하고 승인된 조치를 요청하세요. 복구 뒤 재관측과 고객 보고까지가 업무입니다. 마무리를 누르면 접수를 멈추고 남은 업무를 정리합니다.')]

    def next_shift(self):
        return None

    def shift_records(self):
        return list(self.incident.records)

    def incident_view(self, rec):
        return self._overlay_view(rec, IncidentSession.incident_view(self, rec))

    def incident_observe(self, iid, probe, location):
        return IncidentSession.incident_observe(self, iid, probe, location)

    def incident_hypothesis(self, iid, cause):
        return IncidentSession.incident_hypothesis(self, iid, cause)

    def verify_blocker(self, rec):
        return IncidentSession.verify_blocker(self, rec)

    def reveal_interpretation(self):
        return False

    def learning_view(self):
        view = super().learning_view()
        view.update(optional=True, shiftCount=None, rank='연습 · 진급 없음')
        return view

    def shift_request_ids(self):
        return list(self.runs)

    def _eligible(self):
        candidates = []
        used = {r.rid for r in self.incident.records}
        for rid, run in self.runs.items():
            s = run.state
            if (rid in used or s.phase != 'running' or not s.allocated or self.hardware_servers(run)
                    or run.migration_left or self.incidents_for(rid)):
                continue
            # Allow time to diagnose, request a safe response and reobserve. No guaranteed late/failing injection.
            remaining = s.estimate_minutes(s.plan)
            if remaining < 20 or run.terms['due'] - self.minute < remaining + 60:
                continue
            candidates.append(rid)
        return sorted(candidates)

    def _arm(self):
        f = self.free_incidents
        if not self.global_.briefed or self.global_.result is not None or f['closing'] or f['last'] == self.minute:
            return False
        f['last'] = self.minute
        config = DIFFICULTIES[f['difficulty']]
        if not config['interval'] or f['next'] is None or self.minute < f['next']:
            return False
        f['cursor'] += 1
        rng = random.Random(f'{self.seed}:free-incidents-v1:{f["cursor"]}')
        f['next'] = self.minute + config['interval'] + rng.randrange(3) * 10
        candidates = self._eligible()
        if len([r for r in self.incident.records if r.state in OPEN]) >= config['maximum'] or not candidates:
            return False
        rid = rng.choice(candidates)
        types = sorted(self.content.types)
        itype = rng.choice(types)
        seq = len(self.incident.records) + 1
        rec = IncidentRecord(f'INC-F{seq}', itype, None, seq - 1, rid, 0, self.content.fingerprints[itype])
        self.incident.records.append(rec)
        self._trigger(rec, self.runs[rid])
        f['events'].append({'minute': self.minute, 'cursor': f['cursor'], 'id': rec.id, 'rid': rid, 'type': itype})
        return True

    def end_free_shift(self):
        self._require_briefed()
        if not self.free_incidents['closing']:
            with self._atomic():
                self.free_incidents['closing'] = True
        return self.free_status()

    def _update_shift(self):
        if (self.free_incidents['closing'] and self.global_.result is None and
                all(r.request['status'] in ('completed', 'rejected') for r in self.runs.values()) and
                all(r.state in FINAL for r in self.incident.records)):
            self.global_.result = self.shift_result()

    def shift_result(self):
        result = super().shift_result()
        result.update(title='글로벌 자유 교대 결과', regular=False, seed=self.seed,
                      difficulty=self.free_incidents['difficulty'])
        return result

    def mark_shift_seen(self, key):
        if self.global_.result is None or key != 'shiftfree':
            raise ValueError('끝난 자유 교대 결과만 기록할 수 있습니다.')
        if key not in self.global_.seen:
            with self._atomic():
                self.global_.seen.append(key)

    def free_status(self):
        return {'seed': self.seed, 'difficulty': self.free_incidents['difficulty'],
                'difficultyLabel': DIFFICULTIES[self.free_incidents['difficulty']]['label'],
                'closing': self.free_incidents['closing'], 'briefed': self.global_.briefed,
                'done': self.global_.result is not None, 'result': deepcopy(self.global_.result),
                'remaining': sum(r.request['status'] not in ('completed', 'rejected') for r in self.runs.values()),
                'openIncidents': sum(r.state in OPEN for r in self.incident.records), 'regular': False}

    def shift_status(self):
        return {**super().shift_status(), **self.free_status(), 'title': '글로벌 자유 교대',
                'shift': None, 'next': None, 'seen': list(self.global_.seen)}
