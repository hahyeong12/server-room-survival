"""Read-only views of an incident-response save for the 3D client (Issue #8, Phase 7).

Every value comes from aidc.incidents.session.IncidentSession (the engine). Before a diagnosis the views carry only
the symptom and what the player observed; the hidden cause, its fixes and the post-mortem appear only after the
engine confirmed the cause (or the incident ended). Nothing here changes a session, ledger or save.
"""
from __future__ import annotations

from aidc.incidents.content import load
from aidc.learning import linux_curriculum
from aidc.incidents.session import IncidentSession

CONTENT = load()
LOCATION_LABELS = {'noc': '내 모니터 (관제동)', 'hall': '서버동 01', 'NETWORK': '네트워크동 MMR', 'COOLING': '냉각 플랜트', 'UPS': 'UPS 구역'}
SPEAKERS = {'mentor': '선배 엔지니어 · 사건 대응 담당', 'system': '시스템 · 사건 대응 알림'}


def menu():
    """Same lists for every incident (so the menu itself never hints at the answer)."""
    return {'probes': [{'id': k, 'label': p['label'], 'location': p['location'], 'where': p['where'], 'fact': p['fact'],
                        'example': p['example']} for k, p in CONTENT.probes.items()],
            'causes': [{'id': k, 'label': c['label'], 'domain': c['domain']} for k, c in CONTENT.causes.items()],
            'actions': [{'id': k, 'label': a['label'], 'group': a['group'], 'team': a.get('team')} for k, a in CONTENT.actions.items()],
            'teams': {k: t['label'] for k, t in CONTENT.teams.items()},
            'stages': [label for _, label in CONTENT.data['stages']], 'locations': LOCATION_LABELS}


def view(session, location=None):
    if not isinstance(session, IncidentSession):
        return None
    g = session.global_
    d = session.shift_def()
    records = [session.incident_view(r) for r in session.incident.records if r.shift == g.shift]
    return {'contentVersion': CONTENT.version, 'notice': CONTENT.data['notice'], 'practice': session.incident.practice,
            'shift': g.shift, 'code': d['code'], 'title': d['title'], 'coaching': d['coaching'],
            'records': records, 'open': sum(r['state'] not in ('closed', 'failed', 'void', 'armed') for r in records),
            'alerts': [r['id'] for r in records if r['state'] == 'alert'],
            'facilities': session.facilities_view(location), 'menu': menu(), 'topology': CONTENT.topology['note'],
            'sources': CONTENT.data['sources'], 'shiftCount': len(linux_curriculum.SHIFTS) if session.mode == 'linux' else len(CONTENT.shifts),
            'shifts': ([{'number': n, 'code': f'L{n}', 'title': v['title'], 'incidents': len(v['cases'])}
                        for n, v in sorted(linux_curriculum.SHIFTS.items())] if session.mode == 'linux' else
                       [{'number': int(k), 'code': v['code'], 'title': v['title'], 'incidents': sum(1 for x in v['arrivals'] if x[2])}
                        for k, v in sorted(CONTENT.shifts.items())])}


def request_incidents(session, rid):
    if not isinstance(session, IncidentSession):
        return {}
    recs = [r for r in session.incident.records if r.rid == rid and r.state != 'armed']
    affecting = [r.id for r in session.incidents_for(rid)]
    return {'incidents': [r.id for r in recs], 'incidentAffecting': affecting}


def world_link(session, run):
    """(link, note, aidc) for the world map / route chain. Before a diagnosis: a symptom with no location blamed; after:
    the cause is inside the AIDC and the international hops stay normal (never the whole subsea path)."""
    recs = session.incidents_for(run.request['id'])
    if not recs:
        return None
    known = [r for r in recs if r.cause]
    if not known:
        return 'incident', f'작업 이상 · 원인 미확인 (사건 {recs[0].id} 조사 중) — 위치를 추정하지 않습니다', 'ok'
    r = known[0]
    label = CONTENT.causes[r.type]['label']
    return 'internal', f'원인: {label} · 울산 AIDC 내부 · 국제 구간·육양국·국내망 정상', 'incident'
