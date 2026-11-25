"""Phase 6 글로벌 콘텐츠 카탈로그: 사이트(도시)·고객·업무 유형·업무 템플릿·교대 근무의 단일 원본.

* 데이터는 `catalog_v1.json` 하나에 있습니다. Python 엔진 규칙(이 모듈)과 3D 지도·어댑터가 같은 파일을 읽습니다.
* 업무 템플릿은 버전이 붙은 새 시나리오 키(`global_v1:<templateId>`)로 `game.SCENARIOS`에 **추가만** 합니다.
  기존 키는 재할당하지 않으며 같은 키의 내용이 다르면 즉시 오류입니다(저장된 요청이 같은 의미를 다시 읽도록).
* 요구 조건(자원·기한·허용 모드)은 국가가 아니라 템플릿(고객 계약 × 업무 유형)에 있습니다.
* 모든 고객·계약·수치는 교육용 가상 데이터입니다.
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

from game import SCENARIOS, GPU_TOTAL, POWER_TOTAL

CATALOG_FILE = Path(__file__).with_name('catalog_v1.json')
PLAN_LABELS = {'performance': ('고성능 모드', 15), 'economy': ('절약형 모드', 5)}
COUNTRY_CODE = r'[A-Z]{2}'


class CatalogError(ValueError):
    """카탈로그 데이터가 규칙에 맞지 않습니다."""


def _require(ok, message):
    if not ok:
        raise CatalogError(message)


def scenario_key(version, template_id):
    return f'global_v{version}:{template_id}'


def validate(data):
    """구조와 수치 범위를 검사합니다. 엔진이 처리할 수 없는 값이 들어오면 등록 전에 거부합니다."""
    _require(data.get('catalog') == 'global' and type(data.get('version')) is int and data['version'] >= 1, '카탈로그 버전 정보가 없습니다.')
    sites, clients, jobs, templates = (data.get(k) for k in ('sites', 'clients', 'jobTypes', 'templates'))
    corridors, landings = data.get('corridors', {}), data.get('landings', {})
    for cid, c in corridors.items():
        _require(c.get('landing') in landings or c.get('next') in corridors, f'회선 {cid}의 도착 육양국/다음 구간이 없습니다.')
        _require(len(c.get('points', [])) >= 2, f'회선 {cid}의 경유점이 부족합니다.')
    for sid, s in sites.items():
        _require(isinstance(s.get('city'), str) and s['city'] and isinstance(s.get('countryName'), str), f'사이트 {sid}의 도시/국가 이름이 없습니다.')
        _require(sid.startswith(s.get('country', '') + '-') and len(s['country']) == 2, f'사이트 ID {sid}는 국가 코드로 시작해야 합니다.')
        _require(-90 <= s.get('lat', 999) <= 90 and -180 <= s.get('lon', 999) <= 180, f'사이트 {sid}의 좌표가 범위를 벗어났습니다.')
        _require(s.get('domestic') or s.get('corridor') in corridors, f'사이트 {sid}의 국제 구간이 없습니다.')
        _require(s.get('cluster') in data.get('clusters', {}), f'사이트 {sid}의 지도 묶음이 없습니다.')
    for code, legacy in data.get('legacy', {}).items():
        _require(legacy.get('site') in sites, f'이전 국가 코드 {code}의 사이트가 없습니다.')
    for cid, c in clients.items():
        _require(c.get('site') in sites and c.get('name') and c.get('industry'), f'고객 {cid}의 사이트/이름/업종이 없습니다.')
    names = [c['name'] for c in clients.values()]
    _require(len(names) == len(set(names)), '고객 이름이 중복되었습니다.')
    for tid, t in templates.items():
        _require(t.get('client') in clients and t.get('jobType') in jobs, f'템플릿 {tid}의 고객/업무 유형이 없습니다.')
        _require(set(t.get('plans', {})) == set(PLAN_LABELS), f'템플릿 {tid}에는 고성능·절약형 두 모드가 필요합니다.')
        for mode, p in t['plans'].items():
            for field, limit in (('gpu', GPU_TOTAL), ('power', POWER_TOTAL), ('network', 8)):
                _require(type(p.get(field)) is int and 1 <= p[field] <= limit, f'템플릿 {tid} {mode}.{field}는 1~{limit} 정수여야 합니다.')
        e, h = t['plans']['economy'], t['plans']['performance']
        _require(e['gpu'] <= h['gpu'] and e['power'] <= h['power'], f'템플릿 {tid}의 절약형이 고성능보다 많은 자원을 씁니다.')
        _require(type(t.get('work')) is int and 10 <= t['work'] <= 200, f'템플릿 {tid}의 작업량이 범위를 벗어났습니다.')
        _require(all(type(t.get(k)) is int and t[k] > 0 for k in ('startDue', 'due', 'expiry')), f'템플릿 {tid}의 기한이 올바르지 않습니다.')
        _require(t['startDue'] < t['due'], f'템플릿 {tid}: 배정 권장 시각은 완료 기한보다 앞서야 합니다.')
        _require(isinstance(t.get('flexible'), bool) and t.get('title') and t.get('description'), f'템플릿 {tid}의 계약/설명이 없습니다.')
    for key, shift in data.get('shifts', {}).items():
        _require(shift.get('arrivals') and shift['arrivals'][0][0] == 0, f'교대 {key}는 시작(0분)에 도착하는 요청이 있어야 합니다.')
        seen = set()
        for at, tid in shift['arrivals']:
            _require(tid in templates and type(at) is int and at >= 0 and at % 10 == 0, f'교대 {key}의 도착 일정이 올바르지 않습니다.')
            _require(templates[tid]['client'] not in seen, f'교대 {key}에 같은 고객이 두 번 있습니다.')
            seen.add(templates[tid]['client'])
    return data


def template_fingerprint(template):
    """저장된 요청이 같은 의미를 다시 읽는지 확인하는 내용 해시(규칙에 쓰이는 필드만)."""
    rule = {k: template[k] for k in ('client', 'jobType', 'flexible', 'priority', 'startDue', 'due', 'expiry', 'plans', 'work')}
    return hashlib.sha256(json.dumps(rule, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def _scenario(data, tid):
    t = data['templates'][tid]
    plans = {mode: {'label': PLAN_LABELS[mode][0], 'gpu': p['gpu'], 'power': p['power'], 'network': p['network'],
                    'bonus': PLAN_LABELS[mode][1]} for mode, p in t['plans'].items()}
    return {'plans': plans, 'work': t['work'], 'window': (t['priority'], t['startDue'], t['due'], t['expiry']),
            'flexible': t['flexible'], 'catalog': {'version': data['version'], 'template': tid, 'fingerprint': template_fingerprint(t)}}


class Catalog:
    def __init__(self, data):
        self.data = validate(data)
        self.version = data['version']
        self.sites, self.clients, self.jobs = data['sites'], data['clients'], data['jobTypes']
        self.templates, self.shifts, self.legacy = data['templates'], data['shifts'], data.get('legacy', {})

    def key(self, tid):
        return scenario_key(self.version, tid)

    def register(self, scenarios=SCENARIOS):
        """시나리오를 추가만 합니다. 같은 키가 다른 내용이면 기존 의미를 지키기 위해 거부합니다."""
        for tid in self.templates:
            key, value = self.key(tid), _scenario(self.data, tid)
            if key in scenarios and scenarios[key] != value:
                raise CatalogError(f'{key}는 이미 다른 내용으로 등록되어 있습니다. 내용을 바꾸려면 새 버전 키를 쓰세요.')
            scenarios.setdefault(key, value)
        return self

    def template_of(self, key):
        """시나리오 키 → (템플릿 ID, 템플릿). 이 카탈로그의 키가 아니면 None."""
        prefix = scenario_key(self.version, '')
        if not isinstance(key, str) or not key.startswith(prefix) or key[len(prefix):] not in self.templates:
            return None
        tid = key[len(prefix):]
        return tid, self.templates[tid]

    def describe(self, tid):
        """요청에 고정해 둘 의미(고객·사이트·업무). 저장 파일에 그대로 남아 카탈로그가 바뀌어도 같은 뜻으로 읽힙니다."""
        t = self.templates[tid]
        client, job = self.clients[t['client']], self.jobs[t['jobType']]
        site = self.sites[client['site']]
        return {'version': self.version, 'template': tid, 'fingerprint': template_fingerprint(t),
                'client': t['client'], 'clientName': client['name'], 'industry': client['industry'],
                'site': client['site'], 'city': site['city'], 'cityEn': site['cityEn'], 'countryCode': site['country'],
                'countryName': site['countryName'], 'lat': site['lat'], 'lon': site['lon'], 'domestic': bool(site.get('domestic')),
                'jobType': t['jobType'], 'jobLabel': job['label'], 'title': t['title']}

    def mission_rows(self):
        """DB missions 행으로 만들 (템플릿 ID, 회사명, 국가 이름, 제목, 설명). 국가 이름은 기존 엔진의 표기(한국어)입니다."""
        rows = []
        for tid, t in self.templates.items():
            client = self.clients[t['client']]
            rows.append((tid, client['name'], self.sites[client['site']]['countryName'], t['title'], t['description']))
        return rows

    def counts(self):
        countries = {s['country'] for s in self.sites.values()}
        return {'sites': len(self.sites), 'countries': len(countries), 'clients': len(self.clients),
                'jobTypes': len(self.jobs), 'templates': len(self.templates),
                'byCountry': {c: sum(s['country'] == c for s in self.sites.values()) for c in sorted(countries)}}


@lru_cache(maxsize=1)
def load(path=CATALOG_FILE):
    return Catalog(json.loads(Path(path).read_text(encoding='utf-8'))).register()
