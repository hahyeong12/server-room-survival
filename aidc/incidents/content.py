"""Phase 7 사건 콘텐츠(`incidents_v1.json`)의 로더·검증기.

* 고객 업무는 Phase 6 카탈로그 v1 템플릿을 그대로 쓰고(지문 불변), 사건은 이 별도 버전 파일에 있습니다.
* 저장된 사건은 유형별 지문(`fingerprint`)을 함께 저장합니다. 다시 열 때 지문이 다르면 거부합니다(소급 재해석 금지).
* 모든 수치·장비 이름·로그는 교육용 가상 모델입니다.
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

from aidc.core.server_resources import SERVERS
from aidc.global_ops.catalog import load as load_catalog

CONTENT_FILE = Path(__file__).with_name('incidents_v1.json')
LOCATIONS = ('noc', 'hall', 'NETWORK', 'COOLING', 'UPS')
EFFECTS = ('blocked', 'slow', 'exposed')
RESULTS = ('fix', 'none', 'move', 'pause', 'call', 'consent', 'isolate_move', 'isolate_repair')
GROUPS = ('comm', 'escalate', 'network', 'compute', 'storage', 'facility', 'platform')
STATUSES = ('ok', 'warn', 'bad')


class ContentError(ValueError):
    """사건 콘텐츠가 규칙에 맞지 않습니다."""


def _require(ok, message):
    if not ok:
        raise ContentError(message)


def validate(data):
    _require(data.get('content') == 'incidents' and type(data.get('version')) is int, '사건 콘텐츠 버전 정보가 없습니다.')
    probes, causes, actions, types, teams = (data.get(k, {}) for k in ('probes', 'causes', 'actions', 'types', 'teams'))
    servers = {s.key for s in SERVERS}
    topo = data['topology']
    _require(set(topo['dualHomed']) <= servers, '이중화 랙 목록이 서버 A~D가 아닙니다.')
    for group in ('coolingZones', 'upsFeeds'):
        covered = [k for v in topo[group].values() for k in v]
        _require(sorted(covered) == sorted(servers), f'{group}는 서버 A~D를 한 번씩 덮어야 합니다.')
    for pid, p in probes.items():
        _require(p.get('location') in LOCATIONS and p.get('label') and p.get('fact') and p.get('example'), f'관측 {pid}의 장소/설명이 없습니다.')
    for cid, c in causes.items():
        _require(c.get('label') and c.get('probes') and set(c['probes']) <= set(probes), f'원인 {cid}의 판단 관측이 없습니다.')
    for aid, a in actions.items():
        _require(a.get('group') in GROUPS and a.get('label'), f'조치 {aid}의 그룹이 없습니다.')
        _require(a['group'] != 'escalate' or a.get('team') in teams, f'호출 조치 {aid}의 팀이 없습니다.')
    _require(len(types) >= 10, '사건 유형은 최소 10종이어야 합니다.')
    domains = set()
    for tid, t in types.items():
        _require(tid in causes, f'사건 {tid}의 원인 정의가 없습니다.')
        domains.add(causes[tid]['domain'])
        _require(t.get('effect') in EFFECTS and t.get('alert') and t.get('symptom'), f'사건 {tid}의 영향/경보가 없습니다.')
        _require(t['effect'] != 'slow' or 0 < t.get('factor', 0) < 1, f'사건 {tid}의 지연 배율이 올바르지 않습니다.')
        _require(set(t.get('readings', {})) <= set(probes), f'사건 {tid}의 판독 관측 이름이 올바르지 않습니다.')
        judge = causes[tid]['probes']
        _require(all(pid in t['readings'] for pid in judge), f'사건 {tid}: 판단 관측 {judge}의 판독이 모두 있어야 합니다.')
        _require(any(t['readings'][pid]['status'] in ('warn', 'bad') for pid in judge), f'사건 {tid}: 판단 관측 중 하나는 이상을 보여야 합니다.')
        for pid, r in t['readings'].items():
            _require(r.get('status') in STATUSES and r.get('summary'), f'사건 {tid} 관측 {pid}의 판독이 올바르지 않습니다.')
        routes = 0
        for aid, a in t.get('actions', {}).items():
            _require(aid in actions and a.get('result') in RESULTS and a.get('text'), f'사건 {tid} 조치 {aid}가 올바르지 않습니다.')
            _require(a['result'] != 'fix' or (type(a.get('minutes')) is int and a['minutes'] > 0 and a['minutes'] % 10 == 0), f'사건 {tid} 조치 {aid}의 복구 시간이 올바르지 않습니다.')
            need = a.get('requires', '')
            _require(not need or need in ('consent', 'dualHomed') or (need.startswith('approval:') and need[9:] in teams), f'사건 {tid} 조치 {aid}의 조건이 올바르지 않습니다.')
            routes += a['result'] in ('fix', 'isolate_move', 'isolate_repair', 'move', 'pause')
        _require(routes >= 2, f'사건 {tid}에는 실질적으로 다른 해결·완화 경로가 둘 이상 필요합니다.')
        _require(t.get('verify') and set(t['verify']) <= set(t['readings']), f'사건 {tid}의 사후 확인 관측이 없습니다.')
        _require(t.get('limit') is None or (type(t['limit']) is int and t['limit'] % 10 == 0 and t.get('limitText')), f'사건 {tid}의 제한 시간이 올바르지 않습니다.')
        _require(all(t.get('postmortem', {}).get(k) for k in ('field', 'causal', 'alternatives')), f'사건 {tid}의 사후 분석이 없습니다.')
        _require(all(t.get('mentor', {}).get(k) for k in ('scope', 'evidence', 'cause', 'mitigate')), f'사건 {tid}의 선배 안내가 없습니다.')
    _require({'network', 'gpu', 'storage', 'facility', 'platform'} <= domains, '사건은 다섯 영역을 모두 덮어야 합니다.')
    catalog = load_catalog()
    used = set()
    for key, shift in data['shifts'].items():
        _require(shift.get('coaching') in ('full', 'short', 'none') and shift.get('arrivals'), f'교대 {key}의 정의가 없습니다.')
        _require(shift['arrivals'][0][0] == 0, f'교대 {key}는 시작(0분)에 도착하는 요청이 있어야 합니다.')
        clients = set()
        for at, tid, itype, fraction in shift['arrivals']:
            _require(tid in catalog.templates and type(at) is int and at % 10 == 0, f'교대 {key}의 도착 일정이 올바르지 않습니다.')
            _require(itype is None or itype in types, f'교대 {key}의 사건 유형 {itype}이 없습니다.')
            _require(0 < fraction < 1, f'교대 {key}의 사건 발생 지점이 올바르지 않습니다.')
            client = catalog.templates[tid]['client']
            _require(client not in clients, f'교대 {key}에 같은 고객이 두 번 있습니다.')
            clients.add(client)
            if itype:
                used.add(itype)
    _require(used == set(types), '세 교대가 사건 유형 10종을 모두 한 번 이상 다뤄야 합니다.')
    _require(set(data.get('practice', {})) == set(types) and all(v in catalog.templates for v in data['practice'].values()),
             '사건 유형마다 연습용 업무가 있어야 합니다.')
    return data


def type_fingerprint(data, tid):
    """저장된 사건이 같은 의미를 다시 읽는지 확인하는 내용 해시(규칙에 쓰이는 필드만)."""
    t = data['types'][tid]
    rule = {k: t.get(k) for k in ('effect', 'factor', 'hold', 'gpu', 'limit', 'readings', 'actions', 'verify')}
    rule['probes'] = data['causes'][tid]['probes']
    rule['shared'] = {'topology': {k: v for k, v in data['topology'].items() if k != 'note'},
                      'approval': {k: t['approval'] for k, t in data['teams'].items()}, 'refused': data['common']['refused']}
    return hashlib.sha256(json.dumps(rule, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


class Content:
    def __init__(self, data):
        self.data = validate(data)
        self.version = data['version']
        self.probes, self.causes, self.actions = data['probes'], data['causes'], data['actions']
        self.types, self.teams, self.topology = data['types'], data['teams'], data['topology']
        self.shifts, self.practice = data['shifts'], data['practice']
        self.fingerprints = {tid: type_fingerprint(data, tid) for tid in self.types}

    def shift_def(self, number):
        """GlobalSession이 읽는 모양(arrivals=[분, 템플릿])과 사건 연결(incidents=[[도착 순번, 유형, 발생 지점]])."""
        s = self.shifts[str(number)]
        return {**{k: v for k, v in s.items() if k != 'arrivals'}, 'arrivals': [[at, tid] for at, tid, _, _ in s['arrivals']],
                'incidents': [[i, itype, frac] for i, (_, _, itype, frac) in enumerate(s['arrivals']) if itype]}

    def practice_def(self, itype):
        t = self.types[itype]
        return {'code': 'P', 'title': f'개별 사건 연습 · {t["symptom"]}', 'subtitle': '진급 기록 없는 연습', 'coaching': 'short',
                'intro': '사건 하나를 처음부터 끝까지 연습합니다. 원인은 관측을 모아 직접 판단합니다.',
                'arrivals': [[0, self.practice[itype]]], 'incidents': [[0, itype, 0.3]],
                'goal': {'minResolved': 1, 'minSuccess': 1, 'notifyBeforeRecovery': False, 'maxExpired': 0}}

    def zone_of(self, server):
        return next(z for z, members in self.topology['coolingZones'].items() if server in members)

    def ups_of(self, server):
        return next(u for u, members in self.topology['upsFeeds'].items() if server in members)


@lru_cache(maxsize=1)
def load(path=CONTENT_FILE):
    return Content(json.loads(Path(path).read_text(encoding='utf-8')))
