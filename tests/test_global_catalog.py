"""Phase 6: 글로벌 카탈로그의 정량 기준·실제 접수 가능 여부·불변성(창 없음)."""
import json
import math
import unittest
from copy import deepcopy
from pathlib import Path

import game
from database import Database
from aidc.global_ops.catalog import load, Catalog, CatalogError, CATALOG_FILE, template_fingerprint, scenario_key
from aidc.global_ops.session import GlobalSession

ROOT = Path(__file__).resolve().parents[1]
LAND = ROOT / 'prototypes/3d-datacenter-001/src/assets/land.geojson'
# 국가별 대략적 경계 상자(위도 최소, 최대, 경도 최소, 최대). 좌표 입력 실수(위·경도 뒤바뀜, 부호)만 잡습니다.
BOXES = {'US': (24, 50, -125, -66), 'IN': (6, 36, 68, 98), 'KR': (33, 39, 124, 131), 'JP': (30, 46, 128, 146),
         'DE': (47, 55, 5, 16), 'GB': (49, 61, -9, 2), 'FR': (41, 52, -5, 10), 'NL': (50, 54, 3, 8),
         'SG': (1, 2, 103, 105), 'TW': (21, 26, 119, 123), 'AU': (-44, -10, 112, 155), 'ID': (-11, 6, 95, 141),
         'VN': (8, 24, 102, 110)}


def _inside(lon, lat, ring):
    hit = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
            hit = not hit
    return hit


def _near_land(lon, lat, land, tolerance=1.0):
    for f in land['features']:
        g = f['geometry']
        for poly in (g['coordinates'] if g['type'] == 'MultiPolygon' else [g['coordinates']]):
            if _inside(lon, lat, poly[0]):
                return True
            if any(math.hypot(x - lon, y - lat) <= tolerance for x, y in poly[0]):
                return True
    return False


class CatalogContentTests(unittest.TestCase):
    def setUp(self):
        self.c = load()

    def test_quantitative_targets(self):
        n = self.c.counts()
        self.assertGreaterEqual(n['sites'], 20)
        self.assertGreaterEqual(n['countries'], 12)
        self.assertGreaterEqual(n['clients'], 30)
        self.assertGreaterEqual(n['jobTypes'], 8)
        by = n['byCountry']
        self.assertGreaterEqual(by['US'], 4)
        for code in ('IN', 'KR', 'JP'):
            self.assertGreaterEqual(by[code], 2, code)
        europe = {s['country'] for s in self.c.sites.values() if s['region'] == '유럽'}
        self.assertGreaterEqual(len(europe), 3)
        for city in ('샌프란시스코', '시애틀', '북버지니아 애슈번', '뉴욕', '벵갈루루', '뭄바이', '서울', '부산', '도쿄', '오사카'):
            self.assertIn(city, {s['city'] for s in self.c.sites.values()})
        # 모든 고객·업무 유형이 실제 템플릿에 쓰입니다(목록만 있는 고객 없음).
        self.assertEqual({t['client'] for t in self.c.templates.values()}, set(self.c.clients))
        self.assertEqual({t['jobType'] for t in self.c.templates.values()}, set(self.c.jobs))

    def test_coordinates_are_plausible(self):
        land = json.loads(LAND.read_text(encoding='utf-8'))
        for sid, s in self.c.sites.items():
            lat0, lat1, lon0, lon1 = BOXES[s['country']]
            self.assertTrue(lat0 <= s['lat'] <= lat1 and lon0 <= s['lon'] <= lon1, f'{sid} outside {s["country"]} box')
            self.assertTrue(_near_land(s['lon'], s['lat'], land), f'{sid} not on/near Natural Earth land')

    def test_requirements_follow_contract_not_country(self):
        by_country = {}
        for tid, t in self.c.templates.items():
            country = self.c.sites[self.c.clients[t['client']]['site']]['country']
            by_country.setdefault(country, []).append(t)
        # 같은 나라 안에서도 허용 모드·자원·작업량이 계약마다 다릅니다.
        for code in ('US', 'IN', 'KR', 'JP'):
            group = by_country[code]
            self.assertEqual({t['flexible'] for t in group}, {True, False}, code)
            self.assertGreater(len({json.dumps(t['plans'], sort_keys=True) for t in group}), 1, code)
        # 업무 유형마다 서로 다른 계약 방식(고정/유연, 기한)이 실제로 존재합니다.
        kinds = {self.c.templates[tid]['jobType']: set() for tid in self.c.templates}
        for t in self.c.templates.values():
            kinds[t['jobType']].add((t['flexible'], t['due'] <= 90))
        self.assertGreaterEqual(sum(len(v) > 0 for v in kinds.values()), 8)

    def test_shifts_have_15_distinct_customers_and_two_us_cities_in_one_shift(self):
        tids = [tid for s in self.c.shifts.values() for _, tid in s['arrivals']]
        clients = {self.c.templates[t]['client'] for t in tids}
        self.assertEqual(len(self.c.shifts), 3)
        self.assertGreaterEqual(len(clients), 15)
        self.assertEqual(len(clients), len(tids), 'no customer repeats across shifts')
        first = [self.c.clients[self.c.templates[t]['client']]['site'] for _, t in self.c.shifts['1']['arrivals']]
        self.assertGreaterEqual(len({s for s in first if s.startswith('US-')}), 2)
        domestic = [t for t in tids if self.c.sites[self.c.clients[self.c.templates[t]['client']]['site']].get('domestic')]
        self.assertGreaterEqual(len(domestic), 3, 'Korean customers in every shift')

    def test_legacy_codes_keep_their_meaning(self):
        self.assertEqual(set(self.c.legacy), {'SG', 'JP', 'US'})
        for code, legacy in self.c.legacy.items():
            site = self.c.sites[legacy['site']]
            self.assertEqual((site['lat'], site['lon']), (legacy['lat'], legacy['lon']))
        # 기존 국가별 규칙과 장별 시나리오는 그대로입니다.
        self.assertEqual(game.plans_for('싱가포르'), game.PLANS)
        self.assertEqual(game.WORK_TOTAL, {'싱가포르': 120, '일본': 60, '미국': 100})
        for key in ('intro_sg_v1', 'ch2_jp', 'ch2_us_v2', 'ch3_path', 'ch3b_sg'):
            self.assertNotIn('flexible', game.SCENARIOS[key])
            self.assertNotIn('catalog', game.SCENARIOS[key])

    def test_conditions_use_contract_flexibility_only_for_catalog_scenarios(self):
        us = {'country': '미국', 'title': 'x'}
        self.assertEqual(game.request_conditions(us, 100, 'ch2_us_v2')['type'], 'flexible')   # 기존 규칙(국가)
        self.assertEqual(game.request_conditions({'country': '일본', 'title': 'x'}, 100, 'ch2_jp')['type'], 'fixed')
        fixed_us = next(tid for tid, t in self.c.templates.items() if not t['flexible']
                        and self.c.sites[self.c.clients[t['client']]['site']]['country'] == 'US')
        self.assertEqual(game.request_conditions(us, 100, self.c.key(fixed_us))['type'], 'fixed')
        flex_jp = next(tid for tid, t in self.c.templates.items() if t['flexible']
                       and self.c.sites[self.c.clients[t['client']]['site']]['country'] == 'JP')
        self.assertEqual(game.request_conditions({'country': '일본', 'title': 'x'}, 100, self.c.key(flex_jp))['allowed_modes'],
                         ['performance', 'economy'])


class CatalogEngineTests(unittest.TestCase):
    def test_every_template_is_received_by_the_engine(self):
        """화면 데이터가 아니라 엔진 접수: 각 템플릿을 실제 _receive로 받아 조건·기한·원장 판정을 확인합니다."""
        c = load()
        for tid, t in c.templates.items():
            with self.subTest(tid=tid):
                db = Database(':memory:')
                s = GlobalSession(db, kind='free', seed=3)
                mid = s.global_.missions[tid]
                rid = next((r for r, x in s.runs.items() if x.mission['id'] == mid), None)
                if rid is None:   # 처음 자동 접수된 두 건이 아니면 같은 엔진 경로로 접수
                    with s._atomic():
                        rid = s._receive(mid, f'test:{tid}')
                run = s.runs[rid]
                self.assertEqual(run.state.scenario, scenario_key(1, tid))
                self.assertEqual(run.conditions['catalog']['template'], tid)
                self.assertEqual(run.conditions['type'], 'flexible' if t['flexible'] else 'fixed')
                self.assertEqual(run.state.work_total, t['work'])
                self.assertEqual(run.terms['due'] - run.terms['received'], t['due'])
                for mode in ('performance', 'economy'):
                    self.assertEqual(run.state.plans[mode]['gpu'], t['plans'][mode]['gpu'])
                self.assertIn(c.sites[c.clients[t['client']]['site']]['city'], run.messages[-1])
                # 빈 데이터센터에서: 원래 조건은 배정 가능하거나(대부분) 서버 조합 규칙으로 거부됩니다(연구 배치).
                s.select(rid)
                preview = s.allocation_preview(run, 'performance')
                if not preview['allowed']:
                    self.assertEqual(preview['reason'], '서버별 GPU·전력 조합 불가', tid)
                db.close()

    def test_register_never_reassigns_a_key(self):
        data = json.loads(CATALOG_FILE.read_text(encoding='utf-8'))
        changed = deepcopy(data)
        first = next(iter(changed['templates']))
        changed['templates'][first]['work'] += 10
        with self.assertRaises(CatalogError):
            Catalog(changed).register()
        # 이미 등록된 같은 내용은 그대로 둡니다.
        Catalog(data).register()

    def test_validation_rejects_engine_impossible_values(self):
        data = json.loads(CATALOG_FILE.read_text(encoding='utf-8'))
        for path, value in ((('plans', 'performance', 'gpu'), 11), (('plans', 'economy', 'power'), 0), (('work',), 0),
                            (('startDue',), 999)):
            bad = deepcopy(data)
            target = bad['templates'][next(iter(bad['templates']))]
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            with self.assertRaises(CatalogError, msg=str(path)):
                Catalog(bad)

    def test_v1_rules_are_frozen(self):
        pinned_file = Path(__file__).with_name('global_catalog_v1_fingerprints.json')
        c = load()
        now = {tid: template_fingerprint(t) for tid, t in c.templates.items()}
        pinned = json.loads(pinned_file.read_text(encoding='utf-8'))
        for tid, fp in pinned.items():
            self.assertEqual(now.get(tid), fp, f'{tid}: v1 규칙이 바뀌었습니다. 새 버전 키를 만드세요.')


if __name__ == '__main__':
    unittest.main()
