"""Read-only views of a global shift / global free-operations session for the 3D client (Issue #7, Phase 6).

Every value comes from aidc.global_ops.session.GlobalSession (the existing GameSession rules) or from the
versioned catalog frozen into each request's conditions. Nothing here changes a session, ledger or save.
"""
from __future__ import annotations

from copy import deepcopy

from aidc.global_ops.catalog import load

CATALOG = load()
# Old saves and chapters 1-5 keep their country codes; they are aliases of catalog sites at the same place.
COUNTRY_CODES = {legacy['country']: code for code, legacy in CATALOG.legacy.items()}
SPEAKERS = {'mentor': '선배 엔지니어 · 글로벌 근무 담당', 'player': '나 · 운영 엔지니어', 'system': '시스템 · 교대 근무 알림'}


def site_code(run):
    meta = run.conditions.get('catalog') if run.conditions else None
    return meta['site'] if meta else COUNTRY_CODES.get(run.mission['country'], '??')


def request_extra(session, run):
    """Site / client / job meaning of one request (frozen in the save), plus the senior's hint if this shift gives one."""
    meta = run.conditions.get('catalog') if run.conditions else None
    if not meta:
        return {}
    site = CATALOG.sites.get(meta['site'], {})
    job = CATALOG.jobs.get(meta['jobType'], {})
    hint = session.request_hint(run.request['id']) if hasattr(session, 'request_hint') else None
    return {'site': {'id': meta['site'], 'city': meta['city'], 'cityEn': meta['cityEn'], 'country': meta['countryCode'],
                     'countryName': meta['countryName'], 'lat': meta['lat'], 'lon': meta['lon'], 'domestic': meta['domestic'],
                     'cluster': site.get('cluster'), 'region': site.get('region')},
            'client': {'id': meta['client'], 'name': meta['clientName'], 'industry': meta['industry']},
            'job': {'type': meta['jobType'], 'label': meta['jobLabel'], 'short': job.get('short', meta['jobLabel']),
                    'what': job.get('what', ''), 'practice': job.get('practice', ''), 'game': job.get('game', '')},
            'catalog': {'version': meta['version'], 'template': meta['template']},
            'hint': hint}


def view(session):
    if session.mode not in ('global', 'incident', 'linux'):   # Phase 7: incident shifts reuse the same shift progress
        return None
    status = session.shift_status()
    pages = [[role, SPEAKERS.get(role, role), text] for role, text in session.shift_briefing()]
    g = session.global_
    out = {**deepcopy(status), 'catalogVersion': CATALOG.version, 'notice': CATALOG.data['notice'],
           'briefing': pages, 'seen': list(g.seen)}
    if status['kind'] == 'shift':
        out['shiftCount'] = len(CATALOG.shifts)
        out['requestIds'] = session.shift_request_ids()
        shifts = ({str(n): session.shift_def(n) for n in range(1, 6)} if session.mode == 'linux' else
                  session.content.shifts if session.mode == 'incident' else CATALOG.shifts)
        out['shiftCount'] = len(shifts)
        out['shifts'] = [{'number': int(k), 'title': v['title'], 'subtitle': v['subtitle'], 'coaching': v['coaching'],
                          'requests': len(v['arrivals'])} for k, v in sorted(shifts.items())]
    return out
