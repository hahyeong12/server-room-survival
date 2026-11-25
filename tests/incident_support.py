"""Phase 7 사건 대응 테스트 도우미: 엔진 메서드만으로 교대/연습을 진행합니다(화면 없음).

`FIX`는 사건 유형별 올바른 조치 순서입니다('+10'은 승인 대기 10분). QA·테스트가 같은 순서를 씁니다.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from database import Database
from aidc.incidents.content import load
from aidc.incidents.session import IncidentSession

C = load()
FIX = {'dns': ['dns_failover'], 'tor_uplink': ['reroute_uplink'], 'congestion': ['qos_adjust'], 'gpu_health': ['isolate_migrate'],
       'gpu_oom': ['ask_consent', 'reduce_batch'], 'storage_full': ['cleanup_temp'], 'storage_latency': ['storage_path'],
       'cooling': ['escalate_facility', '+10', 'standby_pump'], 'ups': ['escalate_facility', 'planned_pause'],
       'crashloop': ['escalate_platform', '+10', 'rollback_deploy']}


class Temp:
    def __init__(self):
        self.dir = Path(tempfile.mkdtemp(prefix='srs-inc-'))
        self.dbs = []

    def db(self, name='inc.db'):
        db = Database(self.dir / name)
        self.dbs.append(db)
        return db

    def cleanup(self):
        for db in self.dbs:
            try:
                db.close()
            except Exception:
                pass
        shutil.rmtree(self.dir, ignore_errors=True)


def where(probe):
    return C.probes[probe]['location']


def observe(s, iid, probes):
    return [s.incident_observe(iid, p, where(p)) for p in probes]


def diagnose(s, rec):
    s.incident_ack(rec.id)
    observe(s, rec.id, C.causes[rec.type]['probes'])
    return s.incident_hypothesis(rec.id, rec.type)


def fix(s, rec, steps=None):
    out = []
    for a in steps or FIX[rec.type]:
        if a == '+10':
            s.advance_time(10)
            continue
        out.append(s.incident_act(rec.id, a))
    return out


def finish(s, rec, notify=False):
    """복구될 때까지 시간을 진행하고, 정상 10분 뒤 재관측 → 사후 확인 → 보고."""
    for _ in range(12):
        if s.record(rec.id).state == 'monitoring':
            break
        s.advance_time(10)
    assert s.record(rec.id).state == 'monitoring', s.record(rec.id).timeline[-3:]
    s.advance_time(10)
    observe(s, rec.id, C.types[rec.type]['verify'])
    s.incident_verify(rec.id)
    return s.incident_report(rec.id)


def start_open(s, prefer=None):
    """열린 요청을 엔진 배정안으로 시작합니다(고객 허용 모드·첫 배정안). prefer(rid) -> (mode, chooser) 로 고를 수 있습니다."""
    started = []
    for rid, run in list(s.runs.items()):
        if run.request['status'] not in ('new', 'review', 'waiting') or run.state.allocated:
            continue
        s.select(rid)
        s.read_conversation(rid)
        choice = prefer(s, rid) if prefer else None
        modes = [choice[0]] if choice else ['performance', 'economy']
        for mode in modes:
            if mode not in run.conditions['allowed_modes']:
                continue
            opts = s.allocation_options(run, mode)
            if opts['options']:
                plan = choice[1](opts['options']) if choice else opts['options'][0]
                s.choose_plan(mode, plan)
                started.append(rid)
                break
    return started


def play_shift(s, prefer=None, notify=True, handle=None, limit=60):
    """교대를 끝까지: 열린 요청 시작 → 경보마다 진단·조치 → 복구 확인·보고. handle(s, rec)로 사건 처리를 바꿀 수 있습니다."""
    if not s.global_.briefed:
        s.confirm_shift_briefing()
    for _ in range(limit):
        start_open(s, prefer)
        for rec in s.shift_records():
            if rec.state == 'alert':
                if handle and handle(s, rec):
                    continue
                diagnose(s, rec)
                if notify:
                    s.incident_act(rec.id, 'notify_customer')
                fix(s, rec)
                if rec.type == 'ups':
                    # 같은 UPS 계통의 다른 작업도 영향 범위입니다: 모두 안전하게 계획 중단합니다.
                    for rid in s._affected(rec):
                        if rid not in rec.paused:
                            s.incident_act(rec.id, 'planned_pause', rid=rid)
            if rec.state == 'monitoring' and s.minute >= rec.recovered + 10:
                observe(s, rec.id, C.types[rec.type]['verify'])
                s.incident_verify(rec.id)
                s.incident_report(rec.id)
        if s.global_.result is not None:
            return s.global_.result
        s.advance_time(10)
    raise AssertionError('shift did not finish: ' + str([(r.id, r.state) for r in s.shift_records()]))


def new_session(temp, shift=1, practice=None, seed=5, name=None):
    return IncidentSession(temp.db(name or f'inc_{shift}_{practice}_{len(temp.dbs)}.db'), shift=shift, practice=practice, seed=seed)
