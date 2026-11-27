"""Phase 7 사건 대응 세션: 기존 GameSession/GlobalSession 규칙(접수·조건 고정·동의·서버 원장·시간·기한·점수·저장)을
그대로 쓰면서, 요청 번호에 연결된 사건 상태 기계를 더합니다.

상태: armed → alert →[범위 확인]→ investigating →[관측 기록·가설]→ diagnosed →[조치]→ recovering →(가상 시간)→
monitoring →[정상 10분 + 복구 뒤 재관측 → 사후 확인]→ verified →[고객 보고]→ closed. 영향이 남은 채 제한 시간을 넘기거나
대상 작업이 실패하면 failed, 사건 전에 요청이 끝나면 void.

* 원인(`type`)은 엔진만 압니다. 화면 보기(`incident_view`)는 진단 확정 전에는 증상·관측 결과만 돌려줍니다.
* 관측 판독은 숨은 원인과 현재 엔진 상태(서버 원장·위치·복구 여부)에서 계산합니다. 가설 판정은 그 가설을 판단할 관측을
  실제로 기록했는지 먼저 봅니다(근거 부족 문구는 정답 여부와 무관하게 같습니다).
* 작업 영향(정지·지연·배터리 노출)은 기존 advance_time의 `_job_hold` 훅으로 실제 진행률·기한에 반영됩니다. GPU 장치 사건의
  격리·이전·수리는 기존 서버 FAULT/REPAIRING·이전 원장을 그대로 씁니다.
* 모든 수치·장비·로그는 교육용 가상 모델입니다.
"""
from __future__ import annotations

from collections import defaultdict
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass, field, asdict, fields

from game import MODE_SPEEDS, game_time
from aidc.core.server_resources import ServerHealth, ServerPool, Allocation
from aidc.global_ops.session import GlobalSession
from result_summary import outcome_key

from .content import load

RACKS = {'A': 'A-01', 'B': 'B-01', 'C': 'C-01', 'D': 'D-01'}
NET = {'A': 11, 'B': 12, 'C': 13, 'D': 14}
OPEN = ('alert', 'investigating', 'diagnosed', 'recovering', 'monitoring', 'verified')
FINAL = ('closed', 'failed', 'void')
STATES = ('armed',) + OPEN + FINAL
STAGE_OF = {'armed': 0, 'alert': 0, 'investigating': 2, 'diagnosed': 4, 'recovering': 4, 'monitoring': 5, 'verified': 6,
            'closed': 6, 'failed': 6, 'void': 6}
BUSY = 10
STATE_LABELS = {'armed': '대기', 'alert': '경보 · 미확인', 'investigating': '근거 수집 중', 'diagnosed': '원인 확정 · 조치 필요',
                'recovering': '복구 진행 중', 'monitoring': '복구됨 · 사후 확인 필요', 'verified': '사후 확인 완료 · 보고 필요',
                'closed': '종료(해결)', 'failed': '실패', 'void': '사건 없음(요청 종료)'}
# 원인이 해소된 상태의 판독(교육용 가상 값). 사건 판독이 없는 관측도 이 값을 씁니다.
NORMAL = {
    'ping': '대상 IP 응답 3/3 · RTT 0.8 ms', 'dns': '이름 조회 정상 · 주 리졸버 응답',
    'link_stats': 'AIDC 엣지 링크 E1 UP · 이용률 42% · 드롭 0 · RTT 2 ms', 'tor_port': '서버동 01 ToR 업링크 모두 UP',
    'dcgm': 'Server {servers} GPU 건강 검사 PASS', 'job_log': '로그: 정상 처리 중 · 오류 없음',
    'service_events': '서비스 재시작 0회 · 최근 배포 변경 없음', 'storage_space': '작업 볼륨 vol-{rid} 사용률 46%',
    'storage_latency': 'vol-{rid} 읽기 지연 4 ms · 처리량 정상', 'cooling': '냉각 구역 {zone}: 펌프 P-1·P-2 ON · 유량 42 L/min · 흡입 24.5 °C',
    'ups': '{ups}: 상용 전원 운전 · 배터리 대기 100%'}
NORMAL_TREND = {'link_stats': [42, 18, 6, 2], 'storage_latency': [85, 31, 9, 4], 'cooling': [31.5, 28.5, 26.0, 24.5], 'ups': [58, 64, 80, 100]}


class _Fmt(dict):
    def __missing__(self, key):
        return '—'


@dataclass
class IncidentRecord:
    id: str
    type: str
    shift: int
    index: int
    rid: int
    at: float
    fingerprint: str
    state: str = 'armed'
    detected: int | None = None
    acknowledged: int | None = None
    primary: str | None = None
    servers: list = field(default_factory=list)
    slot: int | None = None
    zone: str | None = None
    ups: str | None = None
    evidence: list = field(default_factory=list)
    hypotheses: list = field(default_factory=list)
    cause: str | None = None
    diagnosed: int | None = None
    actions: list = field(default_factory=list)
    escalations: dict = field(default_factory=dict)
    consent: str | None = None
    busy_until: int = 0
    cause_active: bool = False
    recovery_left: int = 0
    recovery_by: str | None = None
    moved: list = field(default_factory=list)
    paused: list = field(default_factory=list)
    isolated: str | None = None
    recovered: int | None = None
    verified: int | None = None
    reported: int | None = None
    notified: list = field(default_factory=list)
    outcome: str | None = None
    reason: str = ''
    downtime: int = 0
    slow_minutes: int = 0
    seq: int = 0
    timeline: list = field(default_factory=list)

    @classmethod
    def from_payload(cls, value):
        names = {f.name for f in fields(cls)}
        if not isinstance(value, dict) or not {'id', 'type', 'rid', 'fingerprint', 'state'} <= set(value):
            raise ValueError('저장된 사건 기록이 올바르지 않습니다.')
        return cls(**{k: v for k, v in value.items() if k in names})


@dataclass
class IncidentBook:
    version: int
    practice: str | None = None
    records: list = field(default_factory=list)   # IncidentRecord

    def payload(self):
        return {'version': self.version, 'practice': self.practice, 'records': [asdict(r) for r in self.records]}

    @classmethod
    def from_payload(cls, value):
        if not isinstance(value, dict) or type(value.get('version')) is not int or not isinstance(value.get('records'), list):
            raise ValueError('저장된 사건 대응 기록이 올바르지 않습니다.')
        return cls(value['version'], value.get('practice'), [IncidentRecord.from_payload(r) for r in value['records']])


class IncidentSession(GlobalSession):
    MODES = GlobalSession.MODES + ('incident',)
    SAVE_MODE = 'incident'

    def __init__(self, db, shift=1, practice=None, seed=None):
        self.content = load()
        saved = db.get_simulation()
        if saved:
            if saved.get('mode') != self.SAVE_MODE:
                raise ValueError('장애 대응 근무 저장이 아닙니다. 모드별 저장 파일을 사용해 주세요.')
            self.incident = IncidentBook.from_payload(saved.get('incident'))
            if self.incident.version != self.content.version:
                raise ValueError(f'이 저장은 사건 콘텐츠 v{self.incident.version}로 만들어졌습니다. 같은 버전으로만 이어할 수 있습니다.')
        else:
            if practice is not None and practice not in self.content.types:
                raise ValueError('존재하지 않는 사건 연습입니다.')
            if practice is None and not self._has_shift(shift):
                raise ValueError('존재하지 않는 장애 대응 근무입니다.')
            self.incident = IncidentBook(self.content.version, practice)
        super().__init__(db, kind='shift', shift=1 if practice else shift, seed=seed)
        if saved:
            self._validate_incidents()

    # ------------------------------------------------------------------ engine hooks
    def _has_shift(self, number):
        return str(number) in self.content.shifts

    def _extra_payload(self):
        return {**super()._extra_payload(), 'incident': self.incident.payload()}

    @contextmanager
    def _atomic(self):
        before = deepcopy(self.incident)
        try:
            with super()._atomic():
                yield
                self._settle()
        except Exception:
            self.incident = before
            raise

    def _validate_incidents(self):
        for rec in self.incident.records:
            if rec.type not in self.content.types or rec.state not in STATES:
                raise ValueError(f'사건 {rec.id}의 유형 또는 상태가 올바르지 않습니다.')
            if rec.fingerprint != self.content.fingerprints[rec.type]:
                raise ValueError(f'사건 {rec.id}의 정의가 저장 당시와 다릅니다(소급 재해석 금지).')
            if rec.rid not in self.runs:
                raise ValueError(f'사건 {rec.id}의 요청 #{rec.rid}를 찾을 수 없습니다.')

    def shift_def(self, number=None):
        if self.incident.practice:
            return self.content.practice_def(self.incident.practice)
        return self.content.shift_def(number or self.global_.shift)

    def next_shift(self):
        if self.incident.practice or self.global_.kind != 'shift':
            return None
        nxt = self.global_.shift + 1
        return nxt if str(nxt) in self.content.shifts else None

    def _deliver_shift(self):
        g = self.global_
        before = len(g.delivered)
        super()._deliver_shift()
        links = {i: (itype, frac) for i, itype, frac in self.shift_def()['incidents']}
        code = self.shift_def()['code']
        for index, rid in g.delivered[before:]:
            if index in links and not any(r.rid == rid for r in self.incident.records):
                itype, frac = links[index]
                n = sum(r.shift == g.shift for r in self.incident.records) + 1
                self.incident.records.append(IncidentRecord(f'INC-{code}{n}', itype, g.shift, index, rid, frac,
                                                            self.content.fingerprints[itype]))

    def _update_shift(self):
        g = self.global_
        if g.result is None and any(r.shift == g.shift and r.state not in FINAL for r in self.incident.records):
            return
        super()._update_shift()

    # ------------------------------------------------------------------ helpers
    def record(self, iid):
        rec = next((r for r in self.incident.records if r.id == iid), None)
        if rec is None:
            raise ValueError('사건을 찾을 수 없습니다.')
        return rec

    def shift_records(self):
        return [r for r in self.incident.records if r.shift == self.global_.shift]

    def _tdef(self, rec):
        return self.content.types[rec.type]

    def _log(self, rec, kind, text):
        rec.timeline.append([self.minute, kind, text])
        run = self.runs[rec.rid]
        self._emit(run, 'incident_' + kind, f'[사건 {rec.id}] {text}')

    def _alloc(self, run):
        return self.servers.allocations.get(run.playthrough_id) if run.playthrough_id is not None else None

    def _job_servers(self, run):
        alloc = self._alloc(run) or (run.server_allocations[-1] if run.server_allocations else None)
        return [p.server_id for p in alloc.slices] if alloc else []

    def _affected(self, rec):
        """사건이 지금 영향을 주는 요청 번호(실제 서버 원장 기준)."""
        if not rec.cause_active or rec.state in FINAL or rec.state == 'armed':
            return []
        if self._tdef(rec).get('hold'):
            return [rid for rid, run in self.runs.items() if run.state.allocated and (a := self._alloc(run))
                    and any(p.server_id in rec.servers for p in a.slices)]
        return [rec.rid] if self.runs[rec.rid].state.allocated else []

    def _held_servers(self):
        return {k for r in self.incident.records if r.cause_active and r.state not in FINAL and self._tdef(r).get('hold')
                for k in r.servers}

    def incidents_for(self, rid):
        return [r for r in self.incident.records if rid in self._affected(r)]

    # ------------------------------------------------------------------ ledger: no new work on an incident's servers
    @contextmanager
    def _masked(self):
        """조회 전용: 진행 중 사건의 영향 서버(ToR 단절 랙·냉각 구역·UPS 계통·의심 GPU 서버)를 신규 배정 후보에서 뺀 원장."""
        held = self._held_servers()
        if not held:
            yield
            return
        real = self.servers
        pool = ServerPool()
        pool.hardware = {k: (ServerHealth('FAULT', reason='사건 영향 범위 · 신규 배정 보류') if k in held and v.state == 'HEALTHY' else v)
                         for k, v in real.hardware.items()}
        pool.allocations = dict(real.allocations)
        self.servers = pool
        try:
            yield
        finally:
            self.servers = real

    def allocation_preview(self, run, key):
        with self._masked():
            return super().allocation_preview(run, key)

    def allocation_options(self, run, key):
        with self._masked():
            return super().allocation_options(run, key)

    def migration_preview(self, run):
        with self._masked():
            return super().migration_preview(run)

    def _start(self, run, key, retry=False, server_plan=None):
        held = self._held_servers()
        if held and key in run.state.plans:
            if server_plan is not None and any(p.server_id in held for p in server_plan):
                raise ValueError('사건 영향 범위의 서버(' + '·'.join(sorted(held)) + ')에는 새 작업을 배정할 수 없습니다. 배정 계획을 다시 조회해 주세요.')
            if server_plan is None:
                with self._masked():
                    p = run.state.plans[key]
                    server_plan = self.servers.plan(p['gpu'], p['power'])
                if server_plan is None:
                    raise ValueError('사건 영향 범위의 서버를 빼면 GPU·전력 조합이 성립하지 않습니다. 사건이 복구된 뒤 시작하세요.')
        return super()._start(run, key, retry, server_plan)

    # ------------------------------------------------------------------ engine effects (time)
    def _factor(self, rec, rid):
        """이 사건이 이 작업에 주는 이번 구간 처리 배율(None=영향 없음)."""
        t = self._tdef(rec)
        if rec.type == 'gpu_health' and rec.isolated:
            return None   # 격리 뒤에는 기존 하드웨어 FAULT/REPAIRING 경로가 작업을 멈춥니다.
        if rid in rec.paused or t['effect'] == 'blocked':
            return 0.0
        return t['factor'] if t['effect'] == 'slow' else None

    def _job_hold(self, run):
        factors = [f for rec in self.incidents_for(run.request['id']) if (f := self._factor(rec, run.request['id'])) is not None]
        return min(factors) if factors else None

    def _hold_tick(self, run, factor):
        s = run.state
        s.elapsed += 10
        if factor > 0:
            s.work_done = min(s.work_total, s.work_done + 10 * MODE_SPEEDS[s.plan] * factor)
        for rec in self.incidents_for(run.request['id']):
            own = self._factor(rec, run.request['id'])
            if own == 0:
                rec.downtime += 10
            elif own is not None:
                rec.slow_minutes += 10
        if s.work_done >= s.work_total:
            s.finish(True, '고객의 AI 작업이 정상 완료되었습니다.')

    def _trigger_story_faults(self):
        stop = super()._trigger_story_faults()
        self._tick_incidents()
        return self._arm() or stop

    def _tick_incidents(self):
        for rec in self.incident.records:
            if rec.state in FINAL or rec.state == 'armed':
                continue
            for team, at in rec.escalations.items():
                if at + self.content.teams[team]['approval'] == self.minute:
                    self._log(rec, 'approval', f'{self.content.teams[team]["label"]} 승인 · 요청한 조치를 진행할 수 있습니다.')
            if rec.state == 'recovering' and rec.cause_active:
                if rec.recovery_by in ('isolate_migrate', 'gpu_repair'):
                    run = self.runs[rec.rid]
                    done = (self.servers.hardware[rec.isolated].state == 'HEALTHY' if rec.recovery_by == 'gpu_repair'
                            else not run.migration_left and rec.isolated not in self._job_servers(run))
                    if done or run.state.phase == 'finished':
                        self._clear(rec)
                else:
                    rec.recovery_left = max(0, rec.recovery_left - 10)
                    if rec.recovery_left == 0:
                        self._clear(rec)
            t = self._tdef(rec)
            if rec.cause_active and t.get('limit') and self.minute >= rec.detected + t['limit']:
                exposed = [rid for rid in self._affected(rec) if rid not in rec.paused and self.runs[rid].state.phase == 'running'
                           and not (self.runs[rid].migration_left)]
                for rid in exposed:
                    run = self.runs[rid]
                    run.state.finish(False, t['limitText'])
                    self._finish_if_needed(run)
                if exposed:
                    self._log(rec, 'limit', t['limitText'] + f' (영향 요청 #{", #".join(map(str, exposed))})')

    def _arm(self):
        fired = False
        for rec in self.incident.records:
            if rec.state != 'armed':
                continue
            run = self.runs[rec.rid]
            s = run.state
            if (s.phase == 'running' and not self.hardware_servers(run) and not run.migration_left
                    and s.work_done >= rec.at * s.work_total):
                self._trigger(rec, run)
                fired = True
        return fired

    def _trigger(self, rec, run):
        t = self._tdef(rec)
        alloc = self._alloc(run)
        primary = max(alloc.slices, key=lambda p: (p.gpu, -ord(p.server_id)))
        rec.primary = primary.server_id
        if rec.type == 'gpu_health':
            rec.slot = primary.gpu_slots[0]
        rec.zone, rec.ups = self.content.zone_of(rec.primary), self.content.ups_of(rec.primary)
        rec.servers = ({'cooling': self.content.topology['coolingZones'][rec.zone], 'ups': self.content.topology['upsFeeds'][rec.ups]}
                       .get(rec.type, [rec.primary]) if t.get('hold') else [])
        rec.state, rec.detected, rec.cause_active = 'alert', self.minute, True
        self._log(rec, 'alert', f'경보({t["severity"]}): {t["alert"]}')
        if t['effect'] != 'exposed':
            self._feedback(run, '작업 진행이 평소와 다릅니다. 현재 상황과 예상 시각을 알려 주세요.', 'customer_incident')

    def _clear(self, rec):
        rec.cause_active, rec.recovery_left, rec.paused = False, 0, []
        rec.state, rec.recovered = 'monitoring', self.minute
        self._log(rec, 'recovered', '원인 해소 · 정상 실행 재개. 정상 10분 이상 지난 뒤 지표를 다시 관측하고 사후 확인하세요.')

    def _settle(self):
        for rec in self.incident.records:
            if rec.state in FINAL:
                continue
            run = self.runs[rec.rid]
            key = outcome_key(run)
            if rec.state == 'armed' and key != 'in_progress':
                rec.state, rec.outcome, rec.reason = 'void', 'void', '사건이 일어나기 전에 요청이 끝났습니다.'
                rec.timeline.append([self.minute, 'void', rec.reason])
            elif key in ('failed', 'expired', 'rejected') and rec.state != 'armed' and rec.recovered is None:
                rec.state, rec.outcome = 'failed', 'failed'
                rec.reason = run.state.result_text or '대상 작업이 실패했습니다.'
                rec.cause_active = False
                rec.timeline.append([self.minute, 'failed', '대상 작업 실패 · 사건 대응 실패로 기록'])

    # ------------------------------------------------------------------ readings (pure from engine state)
    def _context(self, rec):
        run = self.runs[rec.rid]
        servers = self._job_servers(run)
        primary = rec.primary or (servers[0] if servers else 'A')
        dual = primary in self.content.topology['dualHomed']
        t = self._tdef(rec)
        runtime = max(0, rec.detected + t['limit'] - self.minute) if t.get('limit') and rec.detected is not None else '—'
        scope = rec.servers or servers
        return _Fmt(rack=RACKS[primary], net=NET[primary], server=primary, slot=rec.slot if rec.slot is not None else 0,
                    servers='·'.join(servers) or '—', racks='·'.join(RACKS[k] for k in scope) or '—', rid=rec.rid,
                    zone=rec.zone or self.content.zone_of(primary), ups=rec.ups or self.content.ups_of(primary), runtime=runtime,
                    downPorts='P1' if not dual else 'P1(P2는 UP)',
                    uplinkNote='같은 랙의 두 번째 업링크 P2 UP · 우회 가능' if dual else '이 랙은 업링크 1개(이중화 없음)')

    def reading(self, rec, probe):
        """관측 하나의 현재 판독(조회 전용). 원인이 남아 있으면 숨은 원인의 판독, 아니면 정상값."""
        ctx = self._context(rec)
        t = self._tdef(rec)
        own = t['readings'].get(probe) if rec.cause_active else None
        if probe == 'dcgm' and rec.type == 'gpu_health' and rec.isolated:
            job = self._job_servers(self.runs[rec.rid])
            state = self.servers.hardware[rec.isolated].state
            note = (f'격리된 Server {rec.isolated}: {"FAIL · 수리 중" if state == "REPAIRING" else "FAIL · 격리(사용 불가)" if state == "FAULT" else "수리 후 PASS"}')
            ok = rec.isolated not in job or state == 'HEALTHY'
            summary = (f'작업 서버 {"·".join(job)} GPU 건강 검사 PASS · {note}' if ok else f'Server {rec.isolated} GPU 검사 FAIL · 작업이 아직 이 서버에 있음')
            return {'status': 'ok' if ok and not rec.cause_active else 'warn' if ok else 'bad', 'summary': summary, 'lines': [], 'trend': None}
        # 같은 관측에 다른 진행 중 사건이 보이면, 이 사건의 작업과 범위가 같은지 구분해 적습니다(원인·범위 분리).
        others = []
        for other in self.incident.records:
            if other is rec or not other.cause_active or other.state in FINAL or other.state == 'armed':
                continue
            o = self._tdef(other)['readings'].get(probe)
            if not o or o['status'] == 'ok':
                continue
            mine = rec.rid in self._affected(other)
            others.append((mine, other, o))
        base = NORMAL[probe].format_map(ctx)
        recovered = rec.recovered is not None
        if own:
            trend = own.get('trend')
            out = {'status': own['status'], 'summary': own['summary'].format_map(ctx), 'lines': [x.format_map(ctx) for x in own.get('lines', [])],
                   'trend': {'label': trend['label'].format_map(ctx), 'values': list(trend['values'])} if trend else None}
        else:
            out = {'status': 'ok', 'summary': ('복구 후 ' if recovered else '') + base, 'lines': [], 'trend': None}
        if not own and recovered and probe in NORMAL_TREND:
            out['trend'] = {'label': {'link_stats': 'E1 RTT·이용률 회복', 'storage_latency': 'vol 지연 (ms)', 'cooling': '흡입 온도 (°C, 가상)',
                                      'ups': '배터리 잔량 (%, 가상)'}[probe], 'values': list(NORMAL_TREND[probe])}
        for mine, other, o in others:
            octx = self._context(other)
            line = '같은 계기의 다른 이상: ' + o['summary'].format_map(octx)
            if mine:
                out['status'] = 'warn' if out['status'] == 'ok' else out['status']
                out['lines'].append(line + ' · 이 작업도 그 범위에 있음(다른 진행 중 사건으로 추적)')
            else:
                out['lines'].append(line + ' · 이 작업의 서버/경로와는 무관')
        return out

    # ------------------------------------------------------------------ player actions
    def _open(self, iid, *, acked=True):
        self._require_briefed()
        rec = self.record(iid)
        if rec.state == 'armed':
            raise ValueError('아직 발생하지 않은 사건입니다.')
        if rec.state in FINAL:
            raise ValueError(f'이미 끝난 사건입니다({STATE_LABELS[rec.state]}).')
        if acked and rec.acknowledged is None:
            raise ValueError('먼저 [범위 확인]으로 영향 받는 고객·작업·장비를 확인하세요.')
        return rec

    def incident_ack(self, iid):
        rec = self._open(iid, acked=False)
        if rec.acknowledged is not None:
            return self.incident_scope(rec)     # 멱등: 이미 확인한 범위를 그대로 돌려줍니다.
        with self._atomic():
            rec.acknowledged = self.minute
            if rec.state == 'alert':
                rec.state = 'investigating'
            scope = self.incident_scope(rec)
            self._log(rec, 'scope', '범위 확인: ' + scope['text'])
        return scope

    def incident_scope(self, rec):
        rids = self._affected(rec) or [rec.rid]
        jobs = []
        for rid in rids:
            run = self.runs[rid]
            meta = run.conditions.get('catalog', {})
            jobs.append({'rid': rid, 'client': meta.get('clientName', run.mission['company_name']), 'city': meta.get('city', ''),
                         'servers': self._job_servers(run), 'progress': round(run.state.progress, 1),
                         'due': game_time(run.terms['due']) if run.terms else None})
        text = ', '.join(f'요청 #{j["rid"]} {j["client"]}({j["city"]}) · 서버 {"·".join(j["servers"]) or "—"}' for j in jobs)
        return {'jobs': jobs, 'text': text}

    def incident_observe(self, iid, probe, location):
        rec = self._open(iid)
        spec = self.content.probes.get(probe)
        if spec is None:
            raise ValueError('지원하지 않는 관측입니다.')
        if location != spec['location']:
            raise ValueError(f'{spec["label"]}은(는) {spec["where"]}에서만 관측할 수 있습니다. 그 장소로 이동하세요.')
        last = next((e for e in reversed(rec.evidence) if e['probe'] == probe), None)
        if last and last['minute'] == self.minute:
            return dict(last)      # 같은 시각의 같은 관측(이중 클릭)은 새 기록을 만들지 않습니다.
        with self._atomic():
            rec.seq += 1
            entry = {'seq': rec.seq, 'probe': probe, 'minute': self.minute, 'time': game_time(self.minute), 'location': location,
                     'after': rec.recovered is not None, **self.reading(rec, probe)}
            rec.evidence.append(entry)
            self._log(rec, 'evidence', f'관측 · {spec["label"]}: {entry["summary"]}')
        return dict(entry)

    def _seen(self, rec, probe, since):
        return any(e['probe'] == probe and e['minute'] >= since for e in rec.evidence)

    def incident_hypothesis(self, iid, cause):
        rec = self._open(iid)
        if cause not in self.content.causes:
            raise ValueError('지원하지 않는 원인 가설입니다.')
        if rec.cause is not None:
            raise ValueError(f'원인은 이미 확정했습니다: {self.content.causes[rec.cause]["label"]}. 조치를 선택하세요.')
        c = self.content.causes[cause]
        last = rec.hypotheses[-1] if rec.hypotheses else None
        if last and last['cause'] == cause and last['minute'] == self.minute and len(rec.evidence) == last.get('evidenceCount', -1):
            return dict(last)   # 같은 근거로 같은 가설을 다시 누른 것(이중 클릭)은 새 기록을 만들지 않습니다.
        missing = [p for p in c['probes'] if not self._seen(rec, p, rec.detected)]
        with self._atomic():
            rec.seq += 1
            if missing:
                verdict, reason = 'insufficient', ('근거 부족: 이 가설을 판단하려면 '
                                                   + ', '.join(f'{self.content.probes[p]["label"]}({self.content.probes[p]["where"]})' for p in missing)
                                                   + ' 관측이 필요합니다.')
            elif cause == rec.type:
                verdict = 'confirmed'
                reason = '관측과 일치: ' + ' / '.join(self._latest(rec, p)['summary'] for p in c['probes'])
                rec.cause, rec.diagnosed, rec.state = cause, self.minute, 'diagnosed'
            else:
                verdict = 'refuted'
                reason = ('관측과 모순: ' + ' / '.join(self._latest(rec, p)['summary'] for p in c['probes'])
                          + ' — 이 가설로는 이 사건의 증상이 설명되지 않습니다.')
            entry = {'seq': rec.seq, 'cause': cause, 'label': c['label'], 'minute': self.minute, 'time': game_time(self.minute),
                     'verdict': verdict, 'reason': reason, 'evidenceCount': len(rec.evidence)}
            rec.hypotheses.append(entry)
            self._log(rec, 'hypothesis', f'가설 · {c["label"]}: {({"confirmed": "확정", "refuted": "반박", "insufficient": "근거 부족"})[verdict]} — {reason}')
        return dict(entry)

    def _latest(self, rec, probe):
        return next(e for e in reversed(rec.evidence) if e['probe'] == probe)

    def incident_act(self, iid, action, rid=None, index=0):
        rec = self._open(iid)
        spec = self.content.actions.get(action)
        if spec is None:
            raise ValueError('지원하지 않는 조치입니다.')
        if spec['group'] == 'comm':
            return self._notify(rec)
        if rec.cause is None:
            raise ValueError('원인을 판단하기 전에는 복구·완화 조치를 할 수 없습니다. 관측으로 근거를 모아 원인을 먼저 판단하세요.')
        if rec.state in ('monitoring', 'verified'):
            raise ValueError('원인이 이미 해소되었습니다. 지표를 다시 관측하고 사후 확인을 진행하세요.')
        if self.minute < rec.busy_until:
            raise ValueError(f'직전 조치 결과를 확인하는 중입니다. {game_time(rec.busy_until)} 이후 다음 조치를 할 수 있습니다.')
        t = self._tdef(rec)
        plan = t['actions'].get(action)
        common = self.content.data['common']
        with self._atomic():
            if plan is None:
                if action in common['refused']:
                    out = self._refuse(rec, action, common['refused'][action])
                else:
                    if spec['group'] == 'escalate':
                        rec.escalations.setdefault(spec['team'], self.minute)
                    out = self._none(rec, action, common['escalateNone'] if spec['group'] == 'escalate' else common['none'])
            else:
                out = self._apply(rec, action, plan, rid, index)
        return out

    def _entry(self, rec, action, result, text, **extra):
        rec.seq += 1
        entry = {'seq': rec.seq, 'action': action, 'label': self.content.actions[action]['label'], 'minute': self.minute,
                 'time': game_time(self.minute), 'result': result, 'text': text, **extra}
        rec.actions.append(entry)
        word = {'fix': '해결 조치 시작', 'none': '개선 없음', 'refused': '허용 안 됨', 'move': '작업 이전', 'pause': '계획 중단',
                'call': '담당 호출', 'notice': '고객 안내', 'consent': '고객 동의 요청', 'isolate_move': '격리·이전', 'isolate_repair': '격리·수리'}[result]
        self._log(rec, 'action', f'조치 · {entry["label"]}: {word} — {text}')
        return dict(entry)

    def _consent_finish(self, run):
        """Expected completion if the customer agrees to the smaller batch (published Phase 7 estimate, kept as is so
        incident/Linux saves are judged the same way; the Phase 9 overlay overrides it with an exact 10-minute ceiling)."""
        s = run.state
        return self.minute + 10 + int((s.work_total - s.work_done) / (MODE_SPEEDS[s.plan] * 0.8) + 9) // 10 * 10

    def _refuse(self, rec, action, text):
        last = rec.actions[-1] if rec.actions else None
        if last and last['action'] == action and last['result'] == 'refused' and last['minute'] == self.minute:
            return dict(last)   # 같은 시각에 같은 거부 조치를 다시 누른 것은 한 번만 기록합니다.
        return self._entry(rec, action, 'refused', text)

    def _none(self, rec, action, text):
        rec.busy_until = self.minute + BUSY
        return self._entry(rec, action, 'none', text)

    def _approval(self, rec, team):
        label = self.content.teams[team]['label']
        if team not in rec.escalations:
            return f'승인이 필요한 조치입니다. 먼저 [{label} 호출]로 담당팀에 요청하세요.'
        ready = rec.escalations[team] + self.content.teams[team]['approval']
        if self.minute < ready:
            return f'{label} 승인 대기 중입니다. {game_time(ready)} 이후 진행할 수 있습니다.'
        return ''

    def _apply(self, rec, action, plan, rid, index):
        result, need = plan['result'], plan.get('requires', '')
        ctx = self._context(rec)
        if result in ('fix', 'isolate_move', 'isolate_repair') and rec.state == 'recovering':
            raise ValueError(f'이미 복구 조치가 진행 중입니다({self.content.actions[rec.recovery_by]["label"]}).')
        if need == 'dualHomed' and rec.primary not in self.content.topology['dualHomed']:
            return self._refuse(rec, action, plan['refused'].format_map(ctx))
        if need == 'consent' and rec.consent != 'accepted':
            return self._refuse(rec, action, '고객이 조건 변경을 거절했습니다. 조건을 바꾸지 않는 다른 방법을 찾으세요.' if rec.consent == 'rejected'
                                else self.content.data['common']['refused']['reduce_batch'])
        if need.startswith('approval:'):
            blocked = self._approval(rec, need[9:])
            if blocked:
                return self._refuse(rec, action, blocked)
        if plan.get('team'):
            if result == 'call' and plan['team'] in rec.escalations:
                raise ValueError('이미 호출한 담당팀입니다. 승인 시각을 기다리세요.')
            rec.escalations.setdefault(plan['team'], self.minute)
        if result == 'none':
            return self._none(rec, action, plan['text'])
        if result == 'call':
            ready = rec.escalations[plan['team']] + self.content.teams[plan['team']]['approval']
            return self._entry(rec, action, 'call', plan['text'] + f' 승인 예정 {game_time(ready)}.')
        if result == 'fix':
            rec.state, rec.recovery_left, rec.recovery_by = 'recovering', plan['minutes'], action
            return self._entry(rec, action, 'fix', plan['text'], eta=game_time(self.minute + plan['minutes']))
        if result == 'consent':
            if rec.consent is not None:
                raise ValueError('이미 고객 동의를 요청했습니다. 회신 결과를 확인하세요.')
            run = self.runs[rec.rid]
            finish = self._consent_finish(run)
            ok = bool(run.terms) and finish <= run.terms['due']
            rec.consent = 'accepted' if ok else 'rejected'
            self._feedback(run, ('배치 크기 조정에 동의합니다. 결과가 같고 완료 기한 안이라면 진행해 주세요.' if ok else
                                 '배치 크기를 바꾸면 완료 기한을 넘길 것 같습니다. 조건 변경에는 동의하지 않습니다.'), 'customer_incident_consent')
            return self._entry(rec, action, 'consent', plan['text'] + (' 고객 동의.' if ok else ' 고객 거절.'), consent=rec.consent)
        if result in ('move', 'pause'):
            target = rid if rid is not None else rec.rid
            if target not in self._affected(rec):
                raise ValueError(f'요청 #{target}은(는) 이 사건의 영향 범위에 없습니다.')
            run = self.runs[target]
            if result == 'pause':
                if target in rec.paused:
                    raise ValueError('이미 계획 중단한 작업입니다.')
                rec.paused.append(target)
                self._feedback(run, '계획 중단 안내를 받았습니다. 전원 복구 후 재개해 주세요.', 'customer_incident_notice')
                return self._entry(rec, action, 'pause', plan['text'], rid=target)
            if run.migration_left:
                raise ValueError('이미 작업 이전을 준비 중입니다.')
            options = self._move_options(run)
            if not options:
                return self._refuse(rec, action, f'영향 범위 밖 정상 서버에 GPU {run.state.gpu_used}·전력 {run.state.power_used}을 '
                                                 '한 번에 옮길 여유가 없습니다(이전 불가). 다른 방법을 고르세요.')
            parts = options[min(max(index, 0), len(options) - 1)]
            self._relocate(run, parts, f'사건 {rec.id} 영향 범위 밖으로 작업 이전')
            rec.moved.append(target)
            return self._entry(rec, action, 'move', plan['text'], rid=target,
                               servers=[p.server_id for p in parts])
        if result in ('isolate_move', 'isolate_repair'):
            run = self.runs[rec.rid]
            server = rec.primary
            if result == 'isolate_move':
                options = self._move_options(run, extra={server})
                if not options:
                    return self._refuse(rec, action, f'Server {server}를 뺀 정상 서버에 GPU {run.state.gpu_used}·전력 {run.state.power_used}을 '
                                                     '옮길 여유가 없습니다(이전 불가). 격리 후 수리를 고려하세요.')
            reason = f'사건 {rec.id} · GPU{rec.slot} 장치 오류 의심 · 격리'
            self.servers.hardware[server] = (ServerHealth('FAULT', reason=reason) if result == 'isolate_move'
                                             else ServerHealth('REPAIRING', 20, reason))
            rec.isolated, rec.state = server, 'recovering'
            rec.recovery_by = 'isolate_migrate' if result == 'isolate_move' else 'gpu_repair'
            for other in self.runs.values():
                if other is not run and server in self.hardware_servers(other):
                    self._emit(other, 'hardware_fault', f'Server {server} 격리(사건 {rec.id}) · 이 작업도 중단됩니다.')
            if result == 'isolate_move':
                parts = options[min(max(index, 0), len(options) - 1)]
                self._relocate(run, parts, f'Server {server} 격리 · 정상 서버로 작업 이전')
                return self._entry(rec, action, 'isolate_move', plan['text'], servers=[p.server_id for p in parts])
            self._emit(run, 'hardware_repair', f'Server {server} 격리 · 장비 수리 20분(가상).')
            return self._entry(rec, action, 'isolate_repair', plan['text'], eta=game_time(self.minute + 20))
        raise ValueError('처리할 수 없는 조치 결과입니다.')

    def _move_options(self, run, extra=()):
        """현재 수행만 제외한 복사 원장에서, 사건 영향 범위와 비정상 서버를 뺀 이전 배정안(조회 전용)."""
        held = self._held_servers() | set(extra)
        pool = self.servers.excluding(run.playthrough_id)
        pool.hardware = {k: (ServerHealth('FAULT', reason='사건 영향 범위') if k in held and v.state == 'HEALTHY' else v)
                         for k, v in pool.hardware.items()}
        current = self.servers.allocations[run.playthrough_id]
        return tuple(pool.plans(current.gpu, current.power))[:3]

    def _relocate(self, run, parts, text):
        allocation = Allocation(run.playthrough_id, tuple(parts))
        self.servers.allocations[run.playthrough_id] = allocation
        run.server_allocations.append(allocation)
        run.migration_left = 10
        self._emit(run, 'migration', f'{text} · 진행률·모드·기한 유지 · 준비 10분.\n서버 배정: '
                   + ', '.join(f'{p.server_id} GPU{p.gpu}/전력{p.power}' for p in parts))
        self._feedback(run, '작업 위치 변경 계획을 확인했습니다. 준비가 끝나면 계속 진행해 주세요.', 'customer_migration')

    def _notify(self, rec):
        if self.minute in rec.notified:
            raise ValueError('이미 이 시각에 고객에게 안내했습니다. 상황이 바뀌면 다시 안내하세요.')
        run = self.runs[rec.rid]
        with self._atomic():
            if rec.state == 'recovering' and rec.recovery_by not in ('isolate_migrate',):
                eta = f'복구 예상 {game_time(self.minute + max(rec.recovery_left, 10 if rec.recovery_by == "gpu_repair" else 0))}'
            elif rec.state == 'recovering':
                eta = f'작업 이전 준비 {run.migration_left}분 후 재개 예상'
            elif rec.state in ('monitoring', 'verified'):
                eta = '복구됨 · 사후 확인 중'
            else:
                eta = '원인 조사 중 · 다음 안내 때 예상 시각을 알려 드립니다'
            rec.notified.append(self.minute)
            self._emit(run, 'notice', f'[사건 {rec.id}] 고객 영향 안내: {self._tdef(rec)["symptom"]} · {eta}')
            self._feedback(run, f'상황 안내 감사합니다. ({eta}) 진행 상황을 계속 알려 주세요.', 'customer_notice')
            return self._entry(rec, 'notify_customer', 'notice', f'고객에게 영향과 예상 시각을 안내했습니다: {eta}')

    def verify_blocker(self, rec):
        if rec.state != 'monitoring':
            return {'alert': '먼저 범위를 확인하세요.', 'investigating': '원인을 아직 판단하지 않았습니다.',
                    'diagnosed': '아직 조치하지 않았습니다.', 'recovering': '복구가 아직 끝나지 않았습니다.',
                    'verified': '이미 사후 확인을 마쳤습니다. 고객에게 보고하세요.'}.get(rec.state, '확인할 수 없는 상태입니다.')
        run = self.runs[rec.rid]
        if self.minute < rec.recovered + 10 and run.state.phase != 'finished':
            return f'경보가 사라진 직후입니다. 정상 실행을 10분 이상 지켜본 뒤({game_time(rec.recovered + 10)} 이후) 확인하세요.'
        missing = [p for p in self._tdef(rec)['verify'] if not self._seen(rec, p, max(rec.recovered, rec.recovered + 10 if run.state.phase != 'finished' else rec.recovered))]
        if missing:
            return '복구 뒤 다시 관측해야 할 지표: ' + ', '.join(f'{self.content.probes[p]["label"]}({self.content.probes[p]["where"]})' for p in missing)
        bad = [p for p in self._tdef(rec)['verify'] if self.reading(rec, p)['status'] == 'bad']
        if bad:
            return '아직 비정상인 지표가 있습니다: ' + ', '.join(self.content.probes[p]['label'] for p in bad)
        return ''

    def incident_verify(self, iid):
        rec = self._open(iid)
        blocker = self.verify_blocker(rec)
        if blocker:
            raise ValueError(blocker)
        with self._atomic():
            rec.state, rec.verified = 'verified', self.minute
            self._log(rec, 'verified', '사후 확인 완료: ' + ' / '.join(self._latest(rec, p)['summary'] for p in self._tdef(rec)['verify']))
        return {'verified': game_time(self.minute)}

    def incident_report(self, iid):
        rec = self._open(iid)
        if rec.state != 'verified':
            raise ValueError('사후 확인을 마친 뒤 고객에게 최종 보고할 수 있습니다.')
        run = self.runs[rec.rid]
        with self._atomic():
            rec.state, rec.outcome, rec.reported = 'closed', 'resolved', self.minute
            label = self.content.causes[rec.type]['label']
            text = (f'사건 보고: 원인은 {label}였습니다. {game_time(rec.detected)} 발생 · {game_time(rec.recovered)} 복구 · '
                    f'{game_time(rec.verified)} 사후 확인 완료. 작업 정지 {rec.downtime}분 / 지연 운전 {rec.slow_minutes}분.')
            if rec.isolated and self.servers.hardware[rec.isolated].state == 'FAULT':
                # 격리 후 이전한 경우: 보고와 함께 장비 담당 수리 요청을 접수합니다(기존 REPAIRING 20분 경로).
                self.servers.hardware[rec.isolated] = ServerHealth('REPAIRING', 20, self.servers.hardware[rec.isolated].reason)
                text += f' 격리한 Server {rec.isolated}는 장비 담당 수리 접수(가상 20분).'
            self._log(rec, 'report', text)
            self._feedback(run, '사건 보고를 받았습니다. 원인과 재발 방지 내용을 확인했습니다.', 'customer_incident_report')
        return {'report': text}

    # ------------------------------------------------------------------ views (read-only)
    def _stage_key(self, rec):
        if rec.state == 'alert':
            return 'scope'
        if rec.state == 'investigating':
            return 'evidence' if len({e['probe'] for e in rec.evidence}) < 2 else 'cause'
        return 'mitigate'

    def next_step(self, rec):
        """지금 할 일 하나와 이유(정답 원인·조치를 알려 주지 않습니다)."""
        s = rec.state
        if s == 'alert':
            return '범위 확인', '어느 고객·작업·장비가 영향을 받는지부터 봐야 우선순위를 정할 수 있습니다.'
        if s == 'investigating':
            n = len({e['probe'] for e in rec.evidence})
            return ('근거 수집', '관측을 두 곳 이상 모아 서로 비교하세요. 현장 관측은 그 건물에 들어가야 할 수 있습니다.') if n < 2 else \
                   ('원인 판단', '모은 관측으로 가설을 고르세요. 관측과 맞지 않는 가설은 반박됩니다.')
        if s == 'diagnosed':
            return '완화·복구', '원인에 맞는 조치를 고르세요. 담당팀 승인·고객 동의가 필요한 조치가 있습니다.'
        if s == 'recovering':
            return '복구 대기', '조치가 끝날 때까지 가상 시간을 진행하세요. 영향 받는 고객에게 예상 시각을 안내할 수 있습니다.'
        if s == 'monitoring':
            return '검증', self.verify_blocker(rec) or '지표를 다시 관측했다면 [사후 확인]을 누르세요.'
        if s == 'verified':
            return '보고', '고객에게 원인·영향·복구를 보고하면 사건이 종료됩니다.'
        return '종료', STATE_LABELS[s]

    def incident_view(self, rec):
        t = self._tdef(rec)
        known = rec.cause is not None or rec.state in FINAL
        coaching = self.shift_def()['coaching']
        hint = None
        if rec.state in OPEN and rec.state not in ('monitoring', 'verified'):
            key = self._stage_key(rec)
            hint = t['mentor'][key] if coaching == 'full' else ('관측 두 곳 이상을 비교하고, 영향 범위를 고객별로 나눠 보세요.' if coaching == 'short' and key in ('evidence', 'cause') else None)
        step, why = self.next_step(rec)
        run = self.runs[rec.rid]
        meta = run.conditions.get('catalog', {})
        view = {
            'id': rec.id, 'shift': rec.shift, 'rid': rec.rid, 'state': rec.state, 'stateLabel': STATE_LABELS[rec.state],
            'stage': STAGE_OF[rec.state] if rec.state != 'investigating' else (3 if len({e['probe'] for e in rec.evidence}) >= 2 else 2),
            'severity': t['severity'] if rec.state != 'armed' else None, 'symptom': t['symptom'] if rec.state != 'armed' else None,
            'alert': t['alert'] if rec.state != 'armed' else None,
            'title': (self.content.causes[rec.type]['label'] if known else (t['alert'].split(' · ')[0] if rec.state != 'armed' else '아직 경보 없음')),
            'cause': rec.cause if known else None, 'causeLabel': self.content.causes[rec.type]['label'] if known else None,
            'client': meta.get('clientName'), 'city': meta.get('city'), 'site': meta.get('site'),
            'detected': game_time(rec.detected) if rec.detected is not None else None, 'detectedMinute': rec.detected,
            'acknowledged': rec.acknowledged is not None,
            'scope': self.incident_scope(rec) if rec.acknowledged is not None and rec.state not in FINAL else None,
            'servers': list(rec.servers) if rec.acknowledged is not None else [],
            'evidence': deepcopy(rec.evidence), 'hypotheses': deepcopy(rec.hypotheses), 'actions': deepcopy(rec.actions),
            'escalations': {team: {'label': self.content.teams[team]['label'], 'called': game_time(at),
                                   'approved': game_time(at + self.content.teams[team]['approval']),
                                   'ready': self.minute >= at + self.content.teams[team]['approval']} for team, at in rec.escalations.items()},
            'consent': rec.consent, 'busyUntil': game_time(rec.busy_until) if self.minute < rec.busy_until else None,
            'recoveryLeft': rec.recovery_left, 'recoveryBy': self.content.actions[rec.recovery_by]['label'] if rec.recovery_by else None,
            'eta': game_time(self.minute + rec.recovery_left) if rec.state == 'recovering' and rec.recovery_left else None,
            'recovered': game_time(rec.recovered) if rec.recovered is not None else None,
            'verified': game_time(rec.verified) if rec.verified is not None else None,
            'reported': game_time(rec.reported) if rec.reported is not None else None,
            'verifyBlocker': self.verify_blocker(rec) if rec.state in OPEN else '',
            'verifyProbes': list(t['verify']) if known else [],
            'notified': [game_time(m) for m in rec.notified], 'outcome': rec.outcome, 'reason': rec.reason,
            'downtime': rec.downtime, 'slowMinutes': rec.slow_minutes,
            'wrongHypotheses': sum(h['verdict'] == 'refuted' for h in rec.hypotheses),
            'wrongActions': sum(a['result'] in ('none', 'refused') for a in rec.actions),
            'next': step, 'why': why, 'hint': hint,
            'timeline': [[game_time(m), k, x] for m, k, x in rec.timeline[-30:]],
            'limitLeft': (max(0, rec.detected + t['limit'] - self.minute) if t.get('limit') and rec.cause_active and rec.detected is not None else None),
            'postmortem': deepcopy(t['postmortem']) if rec.state in FINAL else None,
        }
        return view

    def facilities_view(self, location=None):
        """3D 시설·랙이 그릴 현재 물리 상태(조회 전용). 플레이어가 서 있는 건물의 계기만 돌려줍니다(진단 전 원인 노출 방지).
        냉각 플랜트=냉각 구역, UPS 구역·전력동=UPS 계통, 네트워크동=ToR 포트·엣지 링크·리졸버, 서버동=랙의 ToR 포트 LED·스토리지 패널."""
        full = self._facilities_all()
        keep = {'COOLING': ('cooling',), 'UPS': ('ups',), 'POWER': ('ups',), 'NETWORK': ('tor', 'edge', 'dns'), 'hall': ('tor', 'storage')}.get(location, ())
        return {'location': location, **{k: full[k] for k in keep}}

    def _facilities_all(self):
        topo = self.content.topology
        active = [r for r in self.incident.records if r.cause_active and r.state not in FINAL and r.state != 'armed']
        recovering = {r.type: r for r in self.incident.records if r.state in ('monitoring', 'verified') and r.recovered is not None}
        cooling = {}
        for zone, members in topo['coolingZones'].items():
            rec = next((r for r in active if r.type == 'cooling' and r.zone == zone), None)
            if rec:
                steps = min(3, (self.minute - rec.detected) // 10 + 1)
                standby = rec.recovery_by == 'standby_pump'
                cooling[zone] = {'state': 'recovering' if standby else 'warn', 'pumps': {'P-1': 'ON', 'P-2': 'WARN', 'P-3': 'ON' if standby else 'OFF'},
                                 'flow': 40 if standby else 18, 'inlet': [24.5, 27.0, 29.5, 31.5][steps], 'servers': members}
            else:
                cooling[zone] = {'state': 'ok', 'pumps': {'P-1': 'ON', 'P-2': 'ON', 'P-3': 'OFF'}, 'flow': 42, 'inlet': 24.5, 'servers': members}
        ups = {}
        for name, members in topo['upsFeeds'].items():
            rec = next((r for r in active if r.type == 'ups' and r.ups == name), None)
            left = max(0, rec.detected + self._tdef(rec)['limit'] - self.minute) if rec else None
            ups[name] = {'mode': 'battery' if rec else 'utility', 'runtime': left, 'battery': (max(5, round(100 - (20 - left) * 2.1)) if rec else 100),
                         'servers': members, 'restoring': bool(rec and rec.state == 'recovering')}
        tor = {}
        for key in RACKS:
            dual = key in topo['dualHomed']
            rec = next((r for r in active if r.type == 'tor_uplink' and r.primary == key), None)
            ports = {'P1': 'DOWN' if rec else 'UP'}
            if dual:
                ports['P2'] = 'UP'
            tor[key] = {'rack': RACKS[key], 'ports': ports, 'dual': dual, 'rerouted': bool(rec and rec.recovery_by == 'reroute_uplink')}
        cong = next((r for r in active if r.type == 'congestion'), None)
        dns = next((r for r in active if r.type == 'dns'), None)
        storage = []
        for rec in active:
            if rec.type in ('storage_full', 'storage_latency'):
                storage.append({'rid': rec.rid, 'volume': f'vol-{rec.rid}', 'used': 100 if rec.type == 'storage_full' else 61,
                                'latency': 4 if rec.type == 'storage_full' else 85})
        return {'cooling': cooling, 'ups': ups, 'tor': tor, 'storage': storage,
                'edge': {'E1': 98 if cong else 42, 'E2': 91 if cong else 35, 'state': 'congested' if cong else 'ok',
                         'qos': bool(cong and cong.recovery_by == 'qos_adjust')},
                'dns': {'state': 'fail' if dns else 'ok', 'failover': bool(dns and dns.recovery_by == 'dns_failover')}}

    def incident_rows(self):
        out = []
        for rec in self.shift_records():
            run = self.runs[rec.rid]
            meta = run.conditions.get('catalog', {})
            first_notice = min(rec.notified) if rec.notified else None
            out.append({'id': rec.id, 'rid': rec.rid, 'type': rec.type, 'label': self.content.causes[rec.type]['label'],
                        'domain': self.content.causes[rec.type]['domain'], 'client': meta.get('clientName'), 'city': meta.get('city'),
                        'outcome': rec.outcome or 'open', 'reason': rec.reason,
                        'detected': game_time(rec.detected) if rec.detected is not None else None,
                        'diagnosedAfter': (rec.diagnosed - rec.detected) if rec.diagnosed is not None else None,
                        'recoveredAfter': (rec.recovered - rec.detected) if rec.recovered is not None else None,
                        'evidence': len(rec.evidence), 'probes': sorted({e['probe'] for e in rec.evidence}),
                        'wrongHypotheses': [h['label'] for h in rec.hypotheses if h['verdict'] == 'refuted'],
                        'wrongActions': [a['label'] for a in rec.actions if a['result'] in ('none', 'refused')],
                        'noEffect': [a['label'] for a in rec.actions if a['result'] == 'none'],
                        'refused': [a['label'] for a in rec.actions if a['result'] == 'refused'],
                        'notices': len(rec.notified),
                        'fix': next((a['label'] for a in rec.actions if a['result'] in ('fix', 'isolate_move', 'isolate_repair')), None),
                        'mitigations': [a['label'] for a in rec.actions if a['result'] in ('move', 'pause')],
                        'notifiedBeforeRecovery': first_notice is not None and (rec.recovered is None or first_notice <= rec.recovered),
                        'downtime': rec.downtime, 'slowMinutes': rec.slow_minutes,
                        'postmortem': deepcopy(self._tdef(rec)['postmortem'])})
        return out

    def shift_result(self):
        base = super().shift_result()
        rows = self.incident_rows()
        goal = self.shift_def()['goal']
        resolved = sum(r['outcome'] == 'resolved' for r in rows)
        notified = all(r['notifiedBeforeRecovery'] for r in rows) if goal['notifyBeforeRecovery'] else True
        cleared = resolved >= goal['minResolved'] and base['success'] >= goal['minSuccess'] and notified
        lines = []
        for r in rows:
            head = f'{r["id"]} {r["label"]} ({r["city"]} 요청 #{r["rid"]}): ' + ({'resolved': '해결', 'failed': '실패', 'void': '사건 없음'}.get(r['outcome'], '진행 중'))
            detail = []
            if r['wrongHypotheses']:
                detail.append('반박된 가설 ' + ', '.join(r['wrongHypotheses']))
            if r['noEffect']:
                detail.append('개선 없던 조치 ' + ', '.join(r['noEffect']))
            if r['refused']:
                detail.append('허용 안 된 조치(승인·동의·정책) ' + ', '.join(r['refused']))
            if r['fix']:
                detail.append('해결 조치 ' + r['fix'])
            lines.append(head + (' · ' + ' · '.join(detail) if detail else ''))
        if goal['notifyBeforeRecovery'] and not notified:
            lines.append('복구 전에 영향 고객에게 안내하지 않은 사건이 있습니다 — 고객은 복구 시각보다 먼저 영향을 알고 싶어 합니다.')
        word = '연습' if self.incident.practice else '근무'
        lines.append(f'{word} 목표 달성' if cleared else f'{word} 목표 미달성 — 같은 {word}을(를) 새 슬롯에서 다시 도전할 수 있습니다.')
        base.update(cleared=cleared, incidents=rows, resolved=resolved, goal=goal, feedback=lines, practice=self.incident.practice)
        return base

    def shift_briefing(self):
        d = self.shift_def()
        if self.incident.practice:
            return [('system', f'개별 사건 연습 · {d["intro"]} 진급 기록은 남지 않습니다.')]
        pages = {'full': [('mentor', f'{d["title"]}이에요.\n{d["intro"]}'),
                          ('mentor', '경보가 오면 [사건] 탭에서 범위부터 확인해요.\n원인은 관측을 모아 직접 판단해요. 화면이 먼저 알려 주지 않아요.'),
                          ('mentor', '네트워크동·냉각 플랜트·UPS·서버동은 직접 들어가야 계기를 볼 수 있어요.\n복구 뒤에는 꼭 다시 확인하고 고객에게 보고해요.')],
                 'short': [('mentor', f'{d["title"]}입니다. {d["intro"]}'),
                           ('mentor', '설비는 직접 만지지 않아요. 팀을 부르고 승인을 받아요.\n영향 받는 고객에게는 복구 전에 먼저 알려요.')],
                 'none': [('system', f'{d["title"]} — {d["intro"]}')]}
        return pages[d['coaching']]

    def request_hint(self, rid):
        return None   # 사건 근무의 선배 안내는 사건 카드(incident_view.hint)에서만 합니다.
