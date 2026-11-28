"""Phase9 rule overlay. Keeps published incident v1 fingerprints and old saves unchanged.

Only the Phase9 sessions (seeded free shifts, senior evaluation) mix this in. Existing incident/global/Linux
saves and the incident v1 definitions are never reinterpreted.

Trade-off rule (Phase9): a quick on-site workaround restores service sooner, but the affected job then runs
degraded for a while; the slower root-cause fix by the owning team keeps the job stopped/slow longer but runs at
full speed afterwards. Which one finishes earlier depends on how much work is left, so neither path is always better.
Measured on the 10-minute clock (tests/test_operating_branches.py): with 20 minutes of normal-speed work left the
workaround finishes first for every type; with 100 minutes left the root fix does (blocking types already from ~50).
The degraded minutes are recorded in the real ledger (`slow_minutes`) and move the real completion time.
"""
import hashlib
import json
import math
from copy import deepcopy

from game import MODE_SPEEDS, game_time

RULES = {'gpu_oom': {'escalate_platform': {'result': 'call', 'team': 'platform',
                                         'text': '플랫폼 담당에게 작업 메모리 설정 검토를 요청했습니다.'}},
         'storage_full': {'escalate_platform': {'result': 'call', 'team': 'platform',
                                              'text': '플랫폼 담당에게 안전한 스토리지 확장 승인을 요청했습니다.'}}}

# Degraded running after a quick workaround: processing factor and minutes after recovery (None = until completion).
# Blocking incidents use 0.7 x 90 min, slowing incidents (congestion, I/O latency) 0.75 x 90 min, batch reduction
# keeps the 0.8 the customer-consent estimate already assumes.
RESIDUAL = {
    'dns': {'dns_failover': {'factor': 0.7, 'minutes': 90, 'text': '보조 리졸버 경유로 이름 조회가 느려집니다'}},
    'tor_uplink': {'reroute_uplink': {'factor': 0.7, 'minutes': 90, 'text': '남은 업링크 하나로 트래픽이 몰립니다'}},
    'congestion': {'qos_adjust': {'factor': 0.75, 'minutes': 90, 'text': 'QoS 대역 제한으로 대량 전송이 느려집니다'}},
    'storage_full': {'cleanup_temp': {'factor': 0.7, 'minutes': 90, 'text': '지운 임시 캐시를 다시 만드는 동안 느려집니다'}},
    'storage_latency': {'storage_path': {'factor': 0.75, 'minutes': 90, 'text': '보조 저장 경로의 대역이 작습니다'}},
    'crashloop': {'rollback_deploy': {'factor': 0.7, 'minutes': 90, 'text': '최적화가 빠진 이전 버전으로 실행합니다'}},
    'gpu_oom': {'reduce_batch': {'factor': 0.8, 'minutes': None, 'text': '고객이 동의한 작은 배치로 완료까지 실행합니다'}},
}
RULE_VERSION = 'residual-v2:jobs-on-scope;window-inclusive;reduce-batch-deadline-recheck;deadline-ceil10'
FINGERPRINT = hashlib.sha256(json.dumps([RULES, RESIDUAL, RULE_VERSION], sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def ceil10(minutes):
    """Minutes the 10-minute clock really needs for `minutes` of work (float noise rounded away first)."""
    return max(0, math.ceil(round(minutes, 6) / 10)) * 10


TRADEOFF_NOTE = ('임시 우회는 정지가 짧지만 복구 뒤 감속 운전, 담당팀 근본 조치는 정지가 길지만 복구 뒤 정상 속도입니다. '
                 '남은 작업량과 기한을 보고 고르세요. 원인을 판단하면 이 사건에 쓸 수 있는 우회의 비용이 버튼에 표시됩니다.')


def _note(r):
    span = '완료까지' if r['minutes'] is None else f'{r["minutes"]}분간'
    return f'임시 우회 · 복구 뒤 {span} 처리량 {r["factor"]}배 ({r["text"]})'


class OperatingRules:
    TRADEOFF_NOTE = TRADEOFF_NOTE

    def _tdef(self, rec):
        definition = super()._tdef(rec)
        if rec.type not in RULES:
            return definition
        definition = deepcopy(definition)
        definition['actions'].update(RULES[rec.type])
        return definition

    # ------------------------------------------------------------------ degraded running after a workaround
    def _residual(self, rec):
        spec = RESIDUAL.get(rec.type, {}).get(rec.recovery_by)
        if spec is None or rec.recovered is None or rec.state in ('failed', 'void'):
            return None
        # self.minute is the END of the 10-minute tick being processed: ticks ending recovered+10 .. recovered+minutes.
        if spec['minutes'] is not None and self.minute > rec.recovered + spec['minutes']:
            return None
        return spec

    def _residual_jobs(self, rec):
        """Jobs that really run through the workaround now (allocation ledger), not the request number."""
        if self._tdef(rec).get('hold'):
            return {rid for rid, run in self.runs.items() if run.state.allocated and (a := self._alloc(run))
                    and any(p.server_id in rec.servers for p in a.slices)}
        run = self.runs[rec.rid]
        return {rec.rid} if run.state.allocated and run.state.phase == 'running' else set()

    def _residuals(self, run):
        rid = run.request['id']
        return [rec for rec in self.incident.records if self._residual(rec) and rid in self._residual_jobs(rec)]

    def _job_hold(self, run):
        factors = [f for f in [super()._job_hold(run), *(self._residual(r)['factor'] for r in self._residuals(run))]
                   if f is not None]
        return min(factors) if factors else None

    def _hold_tick(self, run, factor):
        degraded = self._residuals(run)
        super()._hold_tick(run, factor)
        for rec in degraded:
            # Count only when this workaround is what actually slowed the tick (no double count under a stop).
            if factor > 0 and factor == self._residual(rec)['factor']:
                rec.slow_minutes += 10

    def _residual_spec(self, rec, action):
        return RESIDUAL.get(rec.type, {}).get(action)

    def _consent_finish(self, run):
        # Phase 7's `int(x + 9) // 10 * 10` floors for x in (10k, 10k+1): a consent could then end 10 minutes late.
        s = run.state
        return self.minute + 10 + ceil10((s.work_total - s.work_done) / (MODE_SPEEDS[s.plan] * 0.8))

    def _apply(self, rec, action, plan, rid, index):
        spec = RESIDUAL.get(rec.type, {}).get(action)
        if action == 'reduce_batch' and spec and rec.consent == 'accepted' and rec.state != 'recovering':
            run = self.runs[rec.rid]
            s = run.state
            finish = self.minute + plan['minutes'] + ceil10((s.work_total - s.work_done) / (MODE_SPEEDS[s.plan] * spec['factor']))
            if run.terms and finish > run.terms['due']:
                last = rec.actions[-1] if rec.actions else None
                if last and last['action'] == action and last['result'] == 'refused' and last['minute'] == self.minute:
                    return dict(last)
                return self._entry(rec, action, 'refused', f'동의를 받은 뒤 시간이 지나 지금 배치를 줄이면 예상 완료 {game_time(finish)}로 '
                                   f'기한 {game_time(run.terms["due"])}을 넘깁니다. 조건을 바꾸지 않는 다른 방법을 찾으세요.', condition=True)
        return super()._apply(rec, action, plan, rid, index)

    def reading(self, rec, probe):
        out = super().reading(rec, probe)
        spec = self._residual(rec)
        jobs = sorted(self._residual_jobs(rec)) if spec else []
        if jobs:
            out = {**out, 'lines': [*out['lines'], f'원인은 해소됨 · 임시 우회 운전 중: 요청 #{", #".join(map(str, jobs))} 처리량 {spec["factor"]}배'
                                    + ('' if spec['minutes'] is None else f' · {game_time(rec.recovered + spec["minutes"])}까지')]}
        return out

    def _overlay_view(self, rec, view):
        spec = self._residual(rec)
        jobs = sorted(self._residual_jobs(rec)) if spec else []
        view['residual'] = None if not jobs else {
            'factor': spec['factor'], 'text': spec['text'], 'jobs': jobs,
            'until': None if spec['minutes'] is None else game_time(rec.recovered + spec['minutes']),
            'label': (f'임시 우회 감속 운전 · 요청 #{", #".join(map(str, jobs))} 처리량 {spec["factor"]}배 · '
                      + ('완료까지' if spec['minutes'] is None else f'{game_time(rec.recovered + spec["minutes"])}까지'))}
        # Per-incident costs only after the player's own diagnosis, so nothing hidden is revealed earlier.
        view['actionNotes'] = ({a: _note(r) for a, r in RESIDUAL.get(rec.type, {}).items()} if rec.cause is not None else {})
        return view

    def incident_view(self, rec):
        return self._overlay_view(rec, super().incident_view(rec))
