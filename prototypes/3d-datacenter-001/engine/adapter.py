"""Headless adapter: 3D client <-> existing Python engine (session.GameSession).

Rules live only in GameSession (the same code the Tkinter game runs): virtual time, GPU/power ledger,
server allocation, customer consent, deadlines, server faults, repair/migration and scores. This module
  * creates and opens saves in a separate 3D save folder (never the user's Python saves),
  * builds a JSON GameSnapshot from a session without changing it,
  * maps GameActions to existing GameSession methods (errors are the engine's own messages),
  * records 3D-only facts (navigation, what the player looked at) for the tutorial journey.
"""
from __future__ import annotations

import json
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database import Database  # noqa: E402  (existing engine modules, unmodified)
from session import GameSession, REQUEST_LABELS  # noqa: E402
from game import game_time, RESPONSES  # noqa: E402
from aidc.core.server_resources import SERVERS, ServerSlice  # noqa: E402
from aidc.storage.story_slots import StorySlots  # noqa: E402
from aidc.storage.checkpoints import capture, restore, checkpoint_path  # noqa: E402
from aidc.story.chapters import CHAPTERS, current_chapter, chapter_from_payload  # noqa: E402
from aidc.ui.job_status import job_status  # noqa: E402  (pure, no Tk)
from aidc.learning.lab_terminal import block_feedback  # noqa: E402  (pure)
from result_summary import job_summary  # noqa: E402
from aidc.global_ops.session import GlobalSession  # noqa: E402  (Phase 6: GameSession subclass, same rules)
from aidc.learning.training import TrainingProgress  # noqa: E402
from aidc.incidents.session import IncidentSession  # noqa: E402  (Phase 7: GlobalSession subclass, same rules)
from aidc.incidents.content import load as load_incidents  # noqa: E402
from aidc.learning.linux_session import LinuxSession  # noqa: E402
from aidc.learning import linux_curriculum  # noqa: E402
from aidc.global_ops.free_session import FreeShiftSession  # noqa: E402
from aidc.learning.senior_session import SeniorSession, SHIFTS as SENIOR_SHIFTS  # noqa: E402
from aidc.learning.career import assess  # noqa: E402

from .journey import Journey, ROUTES, BUILDINGS  # noqa: E402
from . import campaign  # noqa: E402
from . import global_view  # noqa: E402
from . import incident_view  # noqa: E402

# v2 (Phase 5): story.* covers chapters 1-5 (chapterKey, dialogue, campaign, next, retry, chapter2/3/3b/training,
# graduation) and world paths carry an evidence-based `link`. Every v1 field is kept with the same meaning.
API_VERSION = 2
API_COMPAT = (1,)
PRACTICE_CHAPTERS = (2, 3, '3b', 'lab')
# Phase 6: derived from the single catalog (legacy aliases SG/JP/US), no longer kept by hand in three files.
COUNTRY_CODES = global_view.COUNTRY_CODES
SITE_IDS = frozenset(global_view.CATALOG.sites)
FEATURES = ('global', 'incidents')
# Engine servers A~D live in column 1 of the 3D hall. The other 20 racks are decoration only.
SERVER_RACKS = {'A': 'A-01', 'B': 'B-01', 'C': 'C-01', 'D': 'D-01'}
RACK_SERVERS = {rack: key for key, rack in SERVER_RACKS.items()}
FACILITY_ASSETS = {'UPS-01': 'UPS / PDU 01', 'CRAC-01': '냉각 01', 'CRAC-02': '냉각 02', 'NET-01': '네트워크 코어'}
DECOR_RACKS = tuple(f'{row}-{col:02d}' for row in 'ABCD' for col in range(1, 7) if col != 1)
MODE_LABELS = {'tutorial': '튜토리얼', 'story': '스토리 도전', 'free': '자유 운영', 'practice': '장 연습',
               'global': '글로벌 교대 근무', 'global_free': '글로벌 자유 운영',
               'incident': '장애 대응 근무', 'incident_practice': '사건 연습'}
FREE_PATTERN = re.compile(r'aidc_3d_free_([0-9]+)\.db')
GLOBAL_PATTERN = re.compile(r'aidc_3d_global_([0-9]+)\.db')
INCIDENT_PATTERN = re.compile(r'aidc_3d_incident_([0-9]+)\.db')
KINDS = ('tutorial', 'story', 'free', 'practice', 'global', 'global_free', 'incident', 'incident_practice', 'linux', 'linux_practice', 'senior')
MODE_LABELS.update(linux='Linux 실무 연수', linux_practice='Linux 사건 연습')
MODE_LABELS['senior'] = '선임 평가'
SENIOR_PATTERN = re.compile(r'aidc_3d_senior_([0-9]+)\.db')
LINUX_PATTERN = re.compile(r'aidc_3d_linux_([0-9]+)\.db')
GAME_ID = re.compile(r'(aidc_story_slot|aidc_3d_free|aidc_3d_global|aidc_3d_incident|aidc_3d_linux|aidc_3d_senior)_[0-9]{3,}')
INCIDENT_LOCK = '장애 대응 근무는 글로벌 교대 근무 교대 3을 클리어한 뒤 열립니다.'
INCIDENT_TYPES = tuple(load_incidents().types)
GLOBAL_LOCK = '글로벌 교대 근무는 스토리 도전 제5장까지 클리어(운영 엔지니어 수료)한 뒤 열립니다.'
ADVANCE_MINUTES = (10, 30, 60)
OPEN_STATUSES = ('new', 'review', 'waiting')


class ActionError(ValueError):
    """A rejected action. `hint` is extra guidance; nothing in the game changed."""

    def __init__(self, message, hint=''):
        super().__init__(message)
        self.hint = hint


def _chapter_key(value):
    """'2' / 2 / '3b' / 'lab' -> the engine chapter key; anything else (lists, objects, unknown) -> None."""
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return None
    text = str(value)
    return {'1': 1, '2': 2, '3': 3, '3b': '3b', 'lab': 'lab'}.get(text)


class MissingSave(KeyError):
    """Only this means 'no such save' (HTTP 404); any other KeyError is an internal error."""


def _slices_payload(parts):
    return [{'server': p.server_id, 'rack': SERVER_RACKS[p.server_id], 'gpuSlots': list(p.gpu_slots),
             'gpu': p.gpu, 'power': p.power} for p in parts]


def _slices_from(payload):
    return tuple(ServerSlice(p['server'], tuple(p['gpuSlots']), p['power']) for p in payload)


class Game:
    """One open save: the engine session plus the 3D journey sidecar."""

    def __init__(self, gid, path, kind, db, session, journey):
        self.id, self.path, self.kind = gid, Path(path), kind
        self.db, self.session, self.journey = db, session, journey

    def reconcile(self):
        """Keep the 3D sidecar consistent with the engine DB (which is authoritative). A sidecar written by a crashed
        or older run (or a checkpoint copy) can hold a plan choice for a request the engine does not have; such
        choices are dropped (never applied). A choice for a started request is history and stays (start_job always
        re-validates in the engine). The engine chapter/minute are stamped so a mismatch is visible."""
        s, data = self.session, self.journey.data
        dropped = [rid for rid in list(data['selection']) if not rid.isdigit() or int(rid) not in s.runs]
        for rid in dropped:
            data['selection'].pop(rid, None)
        stamp = self._stamp()
        old = data.get('engine')
        if dropped or (old and old.get('chapter') != stamp['chapter']):
            self.journey.record('reconciled', s.minute, dropped=dropped, sidecar=old, engine=stamp)
        data['engine'] = stamp

    def _stamp(self):
        s = self.session
        key = current_chapter(s.story).key if s.story and s.mode == 'story' else s.mode
        if s.mode == 'global' and s.global_.kind == 'shift':
            key = f'shift{s.global_.shift}'
        if isinstance(s, IncidentSession) and not isinstance(s, FreeShiftSession):
            key = f'practice:{s.incident.practice}' if s.incident.practice else f'incident{s.global_.shift}'
        return {'chapter': str(key), 'minute': s.minute, 'requests': len(s.runs)}

    # ------------------------------------------------------------------ facts & snapshot (read-only)
    def _tutorial_run(self):
        s = self.session
        intro = s.story.onboarding if s.story else None
        return s.runs.get(intro.rid) if intro and intro.rid else None

    def facts(self):
        s, run = self.session, self._tutorial_run()
        intro = s.story.onboarding if s.story else None
        rid = run.request['id'] if run else None
        sel = self.journey.selection(rid) if rid else None
        fault = self.journey.data['fault']
        health = s.servers.hardware[fault['server']].state if fault else None
        migrated = bool(run and len(run.server_allocations) > 1)
        return {
            'introduced': bool(intro and intro.introduced),
            'rid': rid, 'code': COUNTRY_CODES.get(run.mission['country']) if run else None,
            'read': bool(intro and rid in intro.read), 'reviewed': bool(intro and rid in intro.reviewed),
            'selected': sel is not None,
            'plan_servers': [p['server'] for p in sel['slices']] if sel else [],
            'started': bool(run and run.playthrough_id is not None),
            'fault_server': fault['server'] if fault else None,
            'responded': bool(fault and (health in ('REPAIRING', 'HEALTHY') or migrated)),
            'recovered': bool(fault and ((health == 'HEALTHY' and not migrated) or (migrated and run.migration_left == 0))),
            'finished': bool(run and run.state.phase == 'finished' and run.state.succeeded and run.request['status'] == 'completed'),
            'reported': bool(rid and rid in self.journey.data['reported']),
        }

    def _stage(self, run):
        """One visual stage per request, used by the world map, campus and racks."""
        s, st = self.session, run.state
        status = run.request['status']
        if status == 'rejected':
            return 'rejected'
        if st.phase == 'finished':
            return 'done' if st.succeeded else 'failed'
        if status in OPEN_STATUSES:
            return 'incoming'
        servers = s.hardware_servers(run)
        if servers:
            return 'hw_fault' if any(s.servers.hardware[k].state == 'FAULT' for k in servers) else 'hw_repair'
        if st.allocated and run.migration_left:
            return 'migration'
        if isinstance(s, IncidentSession) and st.allocated and s.incidents_for(run.request['id']):
            return 'incident'   # Phase 7: an engine incident affects this job (cause shown only after diagnosis)
        if st.phase in ('incident', 'paused'):
            return 'net_fault'
        if st.phase == 'recovering':
            return 'recovering'
        return 'running'

    def _request(self, rid, run):
        s, st = self.session, run.state
        country = run.mission['country']
        allocation = s.servers.allocations.get(run.playthrough_id) if run.playthrough_id else None
        open_request = run.request['status'] in OPEN_STATUSES and not st.allocated
        proposal = run.proposals[-1] if run.proposals else None
        status = job_status(s, run)
        terms = run.terms or {}
        hide = bool(self._training_run(run) and st.incident_kind and st.phase in ('incident', 'paused'))
        view = {
            'id': rid, 'country': country, 'code': global_view.site_code(run),
            'company': run.mission['company_name'], 'title': run.mission['title'],
            'status': run.request['status'], 'statusLabel': REQUEST_LABELS[run.request['status']],
            'unread': not run.request['is_read'], 'stage': self._stage(run), 'phase': st.phase,
            'progress': round(st.progress, 1), 'workDone': st.work_done, 'workTotal': st.work_total,
            'plan': st.plan, 'planLabel': st.plans[st.plan]['label'] if st.plan else None,
            'gpu': st.gpu_used, 'power': st.power_used,
            'terms': {'priority': terms.get('priority'), 'received': game_time(terms['received']) if terms else None,
                      'startDue': game_time(terms['start_due']) if terms else None,
                      'due': game_time(terms['due']) if terms else None, 'dueMinute': terms.get('due'),
                      'expires': game_time(terms['expires']) if terms else None,
                      'completed': game_time(terms['completed']) if 'completed' in terms else None,
                      'receivedMinute': terms.get('received'), 'expiresMinute': terms.get('expires'),
                      'lateMinutes': terms.get('late_minutes')},
            'conditions': ({'type': run.conditions['type'], 'requestedMode': run.conditions['requested_mode'],
                            'allowedModes': list(run.conditions['allowed_modes']),
                            'plans': {k: {'label': p['label'], 'gpu': p['gpu'], 'power': p['power'], 'network': p['network']}
                                      for k, p in run.conditions['plans'].items()}} if run.conditions else None),
            'proposal': ({'status': proposal['status'], 'mode': proposal['proposed']['mode'], 'reason': proposal.get('reason', '')}
                         if proposal else None),
            'modes': s.allocation_mode_rows(run) if open_request else [],
            'allocation': _slices_payload(allocation.slices) if allocation else [],
            'jobStatus': status,
            'hardware': s.hardware_status(run), 'migrationLeft': run.migration_left,
            'hardwareDowntime': run.hardware_downtime,
            # Chapter 5 (as the Python main screen): an active training incident shows no cause numbers.
            'network': {'needed': None if hide else st.network_needed, 'available': None if hide else st.network_available,
                        'hidden': hide, 'attempts': st.response_attempts,
                        'downtime': st.downtime, 'incident': st.phase in ('incident', 'paused')},
            'recoveryLeft': st.recovery_left,
            'score': st.score, 'succeeded': st.succeeded, 'resultText': st.result_text,
            'deadline': s.deadline_summary(run), 'deadlineLevel': s.deadline_level(run),
            'canNotifyDelay': s.can_notify_delay(run),
            'canRetry': st.phase == 'finished' and st.succeeded is False and not run.followup_closed,
            'lastFeedback': run.last_feedback, 'log': run.messages[-10:],
            'selection': self.journey.selection(rid),
            'reported': rid in self.journey.data['reported'],
            'summary': job_summary(run) if st.phase == 'finished' or run.request['status'] == 'rejected' else None,
            **global_view.request_extra(s, run),
            **incident_view.request_incidents(s, rid),
        }
        return view

    def _servers(self):
        s = self.session
        owners = {}
        for pid, allocation in s.servers.allocations.items():
            rid = next((rid for rid, r in s.runs.items() if r.playthrough_id == pid), None)
            for part in allocation.slices:
                for slot in part.gpu_slots:
                    owners[(part.server_id, slot)] = rid
        out = []
        for spec in SERVERS:
            gpu, power = s.servers.usage(spec.key)
            health = s.servers.hardware[spec.key]
            out.append({'key': spec.key, 'name': spec.name, 'rack': SERVER_RACKS[spec.key], 'gpu': spec.gpu, 'power': spec.power,
                        'usedGpu': gpu, 'usedPower': power, 'state': health.state, 'repairLeft': health.repair_left,
                        'reason': health.reason,
                        'slots': [owners.get((spec.key, i)) for i in range(spec.gpu)],
                        'jobs': sorted({rid for (k, _), rid in owners.items() if k == spec.key and rid is not None})})
        return out

    def _story(self):
        if not self.session.story:
            return None
        return campaign.story_view(self.session, self.path)

    def _world(self):
        s, paths = self.session, []
        for rid, run in s.runs.items():
            stage = self._stage(run)
            if stage in ('done', 'failed', 'rejected'):
                continue
            aidc = {'hw_fault': 'fault', 'hw_repair': 'repairing', 'migration': 'repairing'}.get(stage, 'ok')
            link, note = self._link(run, stage)
            wl = incident_view.world_link(s, run) if isinstance(s, IncidentSession) and stage == 'incident' else None
            if wl:
                link, note, aidc = wl
            # A network symptom is shown on the customer->AIDC transit as a whole; the server building (aidc) keeps
            # its own (hardware) state. No single international hop is blamed unless the engine evidence says so.
            transit = {'ok': 'ok', 'symptom': 'degraded', 'primary_down': 'degraded', 'congested': 'degraded',
                       'rerouted': 'ok', 'recovering': 'ok', 'incident': 'ok', 'internal': 'ok'}[link]
            paths.append({'rid': rid, 'code': global_view.site_code(run),
                          'tone': 'incoming' if stage == 'incoming' else 'active', 'focus': rid == s.selected_id,
                          'link': link, 'linkNote': note, 'domestic': bool((run.conditions or {}).get('catalog', {}).get('domestic')),
                          'segments': {'sea': transit, 'landing': transit, 'backbone': transit, 'aidc': aidc}})
        return {'paths': paths}

    def _link(self, run, stage):
        """Transit state from what the player has actually established. Before a diagnosis a network incident is
        only a symptom (transfer stopped / slow); the cause appears after the engine's network diagnosis was opened."""
        st, story = run.state, self.session.story
        if st.allocated and st.rerouted and st.phase in ('running', 'recovering'):
            return 'rerouted', '주 경로 대신 백업 경로로 전송 중'
        if stage == 'recovering':
            return 'recovering', '조치 성공 · 복구 준비 중'
        if stage != 'net_fault':
            return 'ok', ''
        if not st.incident_kind and not self._training_run(run):
            # Free mode / older saves: the existing random incident only lowers the available bandwidth.
            return 'congested', f'필요 {st.network_needed} / 가용 {st.network_available} (자유 운영 장애 모델: 대역폭 부족)'
        chapter3 = story.chapter3 if story else None
        diagnosed = bool(chapter3 and run.request['id'] in chapter3.diagnosed)
        if diagnosed and st.incident_kind == 'path_down':
            return 'primary_down', '진단: 주 통신 경로 링크 신호 없음 · 백업 경로 대기 (정확한 끊긴 지점은 이 진단으로 알 수 없음)'
        if diagnosed and st.incident_kind == 'bandwidth':
            return 'congested', f'진단: 경로는 연결됨 · 필요 {st.network_needed} / 가용 {st.network_available} (대역폭 한계)'
        return 'symptom', '전송 중단 · 원인 미확인 — 진단으로 확인하세요'

    def can_advance(self):
        """Time runs when a job runs, in free mode, and from chapter 2 on also while a request waits (waiting is a
        real choice there: the customer's deadline keeps coming). Chapter 1 / the tutorial keep the Phase 4 rule."""
        s = self.session
        if isinstance(s, FreeShiftSession):
            return s.global_.briefed and s.global_.result is None
        if isinstance(s, GlobalSession):
            # Phase 6: a shift runs after its briefing; waiting is a real choice there (deadlines keep coming).
            return s.global_.kind == 'free' or s.global_.briefed
        if s.mode == 'free' or any(run.state.allocated for run in s.runs.values()):
            return True
        if s.mode == 'story' and s.story and current_chapter(s.story).key != 1:
            return any(run.request['status'] in OPEN_STATUSES for run in s.runs.values())
        return False

    def snapshot(self):
        """Read-only view of the engine state and the saved journey."""
        s = self.session
        story = self._story()
        center = s.center
        healthy_gpu, healthy_power = s.servers.available()
        return {
            'api': API_VERSION, 'apiCompat': list(API_COMPAT), 'features': list(FEATURES), 'engine': 'python:session.GameSession', 'id': self.id, 'mode': s.mode,
            'modeLabel': MODE_LABELS[self.kind if isinstance(s, GlobalSession) else s.mode], 'kind': self.kind,
            'clock': {'minute': s.minute, 'label': s.time_label},
            'focus': s.selected_id,
            'requests': [self._request(rid, run) for rid, run in s.runs.items()],
            'servers': self._servers(),
            'datacenter': {'gpuTotal': center.gpu_total, 'gpuUsed': center.gpu_used, 'powerTotal': center.power_total,
                           'powerUsed': center.power_used, 'healthyFreeGpu': healthy_gpu, 'healthyFreePower': healthy_power},
            'canAdvance': self.can_advance(),
            'story': story,
            'free': ({'pending': s.pending_request_count, 'nextArrival': s.next_arrival_label} if s.mode == 'free' else
                     {'pending': s.pending_request_count, 'nextArrival': game_time(s.global_.free_next)}
                     if s.mode == 'global' and s.global_.kind == 'free' else None),
            'global': global_view.view(s),
            'linux': s.learning_view() if isinstance(s, LinuxSession) else None,
            'assessment': assess(s) if isinstance(s, GlobalSession) else None,
            'senior': ({'shift': s.global_.shift, 'count': 2, 'role': ('선임 엔지니어' if s.global_.result and s.global_.result.get('senior', {}).get('ending') else '담당 엔지니어 · 선임 평가'),
                        'ending': bool(s.global_.result and s.global_.result.get('senior', {}).get('ending')),
                        'qualification': '독립 관제 엔지니어 (교육 수료 · 직무와 별도)'} if isinstance(s, SeniorSession) else None),
            'incident': incident_view.view(s, self._location() if isinstance(s, IncidentSession) else None),
            'journey': {**self.journey.view(), **({'verifyRacks': self.verify_racks()} if self.journey.kind == 'tutorial' else {})},
            'world': self._world(),
            'racks': {'engine': SERVER_RACKS, 'decor': list(DECOR_RACKS)},
            'responses': {k: v['label'] for k, v in RESPONSES.items()},
        }

    # ------------------------------------------------------------------ actions
    def _run(self, rid):
        try:
            rid = int(rid)
        except (TypeError, ValueError):
            raise ActionError('요청 번호가 올바르지 않습니다.') from None
        if rid not in self.session.runs:
            raise ActionError('접수된 요청을 찾을 수 없습니다.')
        return rid, self.session.runs[rid]

    def _focus(self, rid):
        """Select the request inside the engine (GameSession methods act on session.current)."""
        if self.session.selected_id != rid:
            self.session.select(rid)

    def _require_diagnosis(self, run):
        """Tutorial learning order (like Chapter 3b's rule): look at the evidence before acting."""
        if self.journey.kind != 'tutorial' or not self.journey.data['fault']:
            return
        if not self.journey.data['fault'].get('diagnosed'):
            raise ActionError('먼저 [장비 진단]을 열어 원인과 가능한 조치를 확인하세요.',
                              '증거를 보기 전에 조치하지 않습니다. 내 모니터 → [장비 진단] 탭')

    def act(self, action):
        if not isinstance(action, dict) or not isinstance(action.get('type'), str):
            raise ActionError('행동 형식이 올바르지 않습니다.')
        kind = action['type']
        handler = getattr(self, 'do_' + kind.replace('-', '_'), None)
        if handler is None or kind.startswith('_'):
            raise ActionError(f'지원하지 않는 행동입니다: {kind}')
        self._backup = self.journey.transaction()
        try:
            result = handler(action) or {}
        except Exception as exc:
            # Journey facts of a refused action are undone (the engine already rolled itself back); only the
            # attempt itself is kept, so a wrong click never completes a step.
            self.journey.rollback(self._backup)
            if isinstance(exc, ValueError):
                self.journey.record('rejected', self._minute(), action=kind, message=str(exc)[:200])
                self.journey.misclick()
                self.journey.save()
                worded = campaign._player_words(str(exc))
                if worded != str(exc):
                    raise ActionError(worded, getattr(exc, 'hint', '')) from exc
            raise
        # The engine part succeeded and is committed. Journey facts stay in memory even if saving the sidecar
        # fails; the error is reported and the next successful save writes them (never rolled back here).
        self.journey.evaluate(self.facts())
        self.journey.data['engine'] = self._stamp()
        self.journey.save()
        return result

    # observations: no engine state changes -------------------------------------------------------------
    def _minute(self):
        return self.session.minute

    def do_navigate(self, a):
        route, via = a.get('route'), a.get('via', 'tab')
        if route not in ROUTES:
            raise ActionError('알 수 없는 공간입니다.')
        building = a.get('building')
        if building is not None and building not in BUILDINGS:
            raise ActionError('알 수 없는 건물입니다.')
        self.journey.record('navigate', self._minute(), route=route, via=str(via)[:16], building=building,
                            origin=self.journey.route)
        if route == 'room' and building:
            self.journey.data['room'] = building   # Phase 7: which facility interior the player stands in (on-site evidence)
        return {}

    def do_select_facility(self, a):
        if a.get('id') not in BUILDINGS:
            raise ActionError('알 수 없는 건물입니다.')
        self.journey.record('select_facility', self._minute(), id=a['id'], via=str(a.get('via', 'chip'))[:16],
                            route=self.journey.route)
        return {}

    def do_select_country(self, a):
        code = a.get('id')
        if not isinstance(code, str) or code not in ('KR', *COUNTRY_CODES.values(), *SITE_IDS):
            raise ActionError('알 수 없는 국가입니다.')
        self.journey.record('select_country', self._minute(), id=code)
        if self.session.mode == 'global':
            return self._select_site(code)
        active = [r for r in self.session.runs.values() if self._stage(r) not in ('done', 'failed', 'rejected')
                  and COUNTRY_CODES.get(r.mission['country']) == code]
        if code == 'KR':
            return {'info': '울산 AIDC 캠퍼스입니다. 요청은 다른 나라에서 이곳으로 들어옵니다.'}
        if not active:
            self.journey.misclick()
            origins = sorted({COUNTRY_CODES.get(r.mission['country'], '??') for r in self.session.runs.values()
                              if self._stage(r) not in ('done', 'failed', 'rejected')})
            names = {'SG': '싱가포르', 'JP': '일본', 'US': '미국'}
            return {'hint': '이 나라에서는 지금 도착한 요청이 없습니다.'
                    + (f' 점등된 경로는 {", ".join(names.get(c, c) for c in origins)}에서 시작합니다.' if origins else '')}
        run = active[0]
        return {'info': f'{run.mission["company_name"]} · {run.mission["title"]} · {REQUEST_LABELS[run.request["status"]]}'}

    def _select_site(self, code):
        """Phase 6: a click on a city selects that city's request in the engine. A second click on a city with two
        open requests moves to the other one (so the same city's tickets are told apart)."""
        s = self.session
        if code == 'KR':
            return {'info': '울산 AIDC입니다. 국내·해외 고객의 요청이 모두 이곳 서버동에서 처리됩니다.'}
        live = [(rid, r) for rid, r in s.runs.items() if self._stage(r) not in ('done', 'failed', 'rejected')]
        here = [rid for rid, r in live if global_view.site_code(r) == code]
        catalog = global_view.CATALOG
        site = catalog.sites.get(code) or catalog.sites.get(catalog.legacy.get(code, {}).get('site'))
        name = f'{site["city"]} ({site["countryName"]})' if site else code
        if not here:
            self.journey.misclick()
            origins = sorted({global_view.site_code(r) for _, r in live})
            return {'hint': f'{name}에서는 지금 도착한 요청이 없습니다.' + (f' 점등된 도시: {", ".join(origins)}' if origins else '')}
        rid = here[(here.index(s.selected_id) + 1) % len(here)] if s.selected_id in here else here[0]
        self._focus(rid)
        run = s.runs[rid]
        more = f' · 이 도시의 열린 요청 {len(here)}건' if len(here) > 1 else ''
        return {'info': f'{name} · 요청 #{rid} {run.mission["company_name"]} · {REQUEST_LABELS[run.request["status"]]}{more}',
                'rid': rid}

    def do_inspect_rack(self, a):
        rack = a.get('rack')
        if rack in FACILITY_ASSETS:
            self.journey.record('inspect_rack', self._minute(), rack=rack, server=None)
            return {'info': f'{FACILITY_ASSETS[rack]} · 시설 설비 모식 (게임 규칙 미연결)'}
        if not isinstance(rack, str) or not re.fullmatch(r'[A-D]-0[1-6]', rack):
            raise ActionError('알 수 없는 랙입니다.')
        server = RACK_SERVERS.get(rack)
        self.journey.record('inspect_rack', self._minute(), rack=rack, server=server)
        if server is None:
            self.journey.misclick()
            return {'hint': f'{rack}은 교육 범위 밖의 장식 랙입니다. 엔진 서버 A~D는 1번 열의 A-01~D-01입니다.'}
        rid = self.session.selected_id
        sel = self.journey.selection(rid) if rid else None
        if sel and server not in [p['server'] for p in sel['slices']] and not self.session.runs[rid].state.allocated:
            self.journey.misclick()
            names = '·'.join(p['server'] for p in sel['slices'])
            return {'hint': f'Server {server}({rack})는 고른 배정안에 없습니다. 배정안의 서버: {names}'}
        return {}

    def do_view_plans(self, a):
        rid, run = self._run(a.get('rid'))
        self.journey.record('view_plans', self._minute(), rid=rid)
        s = self.session
        modes = {}
        for key in run.state.plans:
            o = s.allocation_options(run, key)
            modes[key] = {'allowed': o['allowed'], 'reason': o['reason'],
                          'options': [_slices_payload(opt) for opt in o['options']],
                          # Chapter 2: what each option would leave for the other customer (engine, read-only copy).
                          'impacts': [s.allocation_impacts(run, opt) for opt in o['options']]}
        return {'plans': modes, 'briefing': s.chapter2_briefing_lines(run)}

    def do_select_plan(self, a):
        rid, run = self._run(a.get('rid'))
        mode, index = a.get('mode'), a.get('index')
        if mode not in run.state.plans or type(index) is not int:
            raise ActionError('배정안 선택 형식이 올바르지 않습니다.')
        s = self.session
        options = s.allocation_options(run, mode)
        self.journey.record('select_plan', self._minute(), rid=rid, mode=mode, index=index, allowed=options['allowed'])
        if not options['allowed']:
            self.journey.misclick()
            row = next((r for r in s.allocation_mode_rows(run) if r['key'] == mode), None)
            raise ActionError(f'{run.state.plans[mode]["label"]}은 지금 시작할 수 없습니다: {options["reason"]}',
                              row['reason'] if row and row['reason'] else '')
        if not 0 <= index < len(options['options']):
            raise ActionError('배정안을 다시 조회해 주세요.')
        parts = options['options'][index]
        shown = a.get('slices')
        if shown is not None and shown != _slices_payload(parts):
            raise ActionError('조회 이후 배정안이 바뀌었습니다. [다시 조회]로 최신 배정안을 확인해 주세요.',
                              '시간·다른 작업·서버 상태가 바뀌면 엔진의 배정안도 바뀝니다.')
        self.journey.set_selection(rid, {'mode': mode, 'index': index, 'slices': _slices_payload(parts),
                                         'label': run.state.plans[mode]['label'], 'minute': s.minute})
        s.inspect_story_preview(rid)   # engine: marks the plan review (onboarding 'reviewed') when the request was read
        return {'info': f'{run.state.plans[mode]["label"]} · 배정안 {index+1} 선택 (자원 미점유). 서버동에서 시작하세요.'}

    def _training_run(self, run):
        t = self.session.training
        return t is not None and run.request['id'] in t.request_ids

    def do_diagnose(self, a):
        rid, run = self._run(a.get('rid'))
        s = self.session
        self.journey.record('diagnose', self._minute(), rid=rid)
        fault = self.journey.data['fault']
        if fault and fault.get('rid') == rid:
            fault['diagnosed'] = True
        story = s.story
        extra = {}
        # Opening the monitor's diagnosis pane is the engine's "open the diagnosis window" action for chapters 3/4.
        if (story and story.chapter3 is not None and rid in story.chapter3.request_ids
                and run.state.allocated and run.state.incident_kind):
            extra['networkDiagnosis'] = campaign.jsonable(s.view_network_diagnosis(rid))
        if story and story.chapter3b is not None and rid in story.chapter3b.request_ids and s.hardware_servers(run):
            extra['hardwareDiagnosis'] = campaign.jsonable(s.view_hardware_diagnosis(rid))
        if self._training_run(run):
            # Chapter 5 is an independent diagnosis: the monitor shows only the symptom; evidence comes from the Lab.
            return {'diagnosis': {'training': True, 'progress': round(run.state.progress, 1),
                                  'symptom': campaign.job_symptom(campaign.observe(s, rid)),
                                  'locked': s.training_response_locked(run),
                                  'hardware': s.hardware_status(run) or '이 작업의 서버는 모두 정상입니다.',
                                  'servers': [], 'network': '진단 정보 없음 · Engineering Lab에서 직접 관측하세요',
                                  'migration': {'allowed': False, 'reason': '서버 장애가 아닙니다.', 'options': []},
                                  'free': {'gpu': s.servers.available()[0], 'power': s.servers.available()[1]}}}
        preview = s.migration_preview(run)
        return {'diagnosis': {**extra,
            'hardware': s.hardware_status(run) or '이 작업의 서버는 모두 정상입니다.',
            'servers': [{'key': k, 'rack': SERVER_RACKS[k], 'state': s.servers.hardware[k].state,
                         'repairLeft': s.servers.hardware[k].repair_left}
                        for k in (p['server'] for p in _slices_payload(s.servers.allocations[run.playthrough_id].slices))]
                       if run.playthrough_id in s.servers.allocations else [],
            'network': ('네트워크 장애 · 필요 {} / 가용 {}'.format(run.state.network_needed, run.state.network_available)
                        if run.state.phase in ('incident', 'paused') else
                        f'네트워크 정상 · 필요 {run.state.network_needed} / 가용 {run.state.network_available}'),
            'progress': round(run.state.progress, 1),
            'migration': {'allowed': preview['allowed'], 'reason': preview['reason'],
                          'options': [_slices_payload(o) for o in preview['options']]},
            'free': {'gpu': s.servers.available()[0], 'power': s.servers.available()[1]},
        }}

    def verify_racks(self):
        """Racks whose re-check counts for the tutorial: the fault server, or after a migration the new servers."""
        fault = self.journey.data['fault']
        if not fault:
            return []
        run = self.session.runs.get(fault['rid'])
        if run and len(run.server_allocations) > 1:
            return [SERVER_RACKS[p.server_id] for p in run.server_allocations[-1].slices]
        return [fault['rack']]

    def do_verify(self, a):
        rid, run = self._run(a.get('rid'))
        s = self.session
        allocation = s.servers.allocations.get(run.playthrough_id) if run.playthrough_id else None
        rack = a.get('rack')
        server = RACK_SERVERS.get(rack) if isinstance(rack, str) else None
        fault = self.journey.data['fault']
        allowed = self.verify_racks()
        target = server or (RACK_SERVERS[allowed[0]] if allowed else None)
        state = s.servers.hardware[target].state if target else None
        issues = s.hardware_status(run)
        ok = bool(target) and state == 'HEALTHY' and not issues and run.state.phase in ('running', 'finished')
        if fault and SERVER_RACKS.get(target) not in allowed:
            self.journey.record('verify', self._minute(), rid=rid, server=target, state=state, ok=False)
            where = '·'.join(allowed)
            return {'hint': f'다시 확인할 서버는 {where} 입니다 ({"이전한 새 서버" if len(self.session.runs[fault["rid"]].server_allocations) > 1 else "장애가 났던 서버"}).'}
        self.journey.record('verify', self._minute(), rid=rid, server=target, state=state, ok=ok)
        detail = (f'Server {target} {state} · 작업 {run.state.phase} · 진행률 {round(run.state.progress)}%'
                  + (f' · {issues}' if issues else ''))
        if not ok:
            return {'hint': '아직 정상으로 확인되지 않았습니다. ' + detail}
        return {'info': '사후 확인 완료 · ' + detail + (' · 배정 유지' if allocation else '')}

    def do_report(self, a):
        rid, run = self._run(a.get('rid'))
        if run.state.phase != 'finished' and run.request['status'] != 'rejected':
            raise ActionError('작업이 끝난 뒤 결과를 확인할 수 있습니다.')
        lines = self.session.read_conversation(rid)   # engine: marks the customer's final message as read
        self.journey.record('report', self._minute(), rid=rid)
        if rid not in self.journey.data['reported']:
            self.journey.data['reported'].append(rid)
        return {'conversation': [list(x) for x in lines]}

    def do_skip_tutorial(self, a):
        if self.journey.kind != 'tutorial':
            raise ActionError('튜토리얼에서만 건너뛸 수 있습니다.')
        self.journey.record('skip', self._minute())
        self.journey.skip()
        return {'info': '튜토리얼 안내를 건너뛰었습니다. 실습 완료로 기록하지 않으며 게임 상태는 그대로입니다.'}

    # engine actions -----------------------------------------------------------------------------------
    def do_confirm_briefing(self, a):
        s = self.session
        if isinstance(s, IncidentSession):
            self.journey.record('engine', self._minute(), name='confirm_shift_briefing')
            s.confirm_shift_briefing()
            return {'info': f'{s.shift_def()["title"]} 시작 · 요청함의 업무를 배정하고, 경보가 오면 [사건] 탭에서 대응하세요.'}
        if s.mode == 'global':
            self.journey.record('engine', self._minute(), name='confirm_shift_briefing')
            s.confirm_shift_briefing()
            return {'info': f'교대 {s.global_.shift} 근무 시작 · 요청함에서 도착한 요청을 확인하세요.'}
        key = current_chapter(s.story).key if s.story and s.mode == 'story' else 1
        self.journey.record('engine', self._minute(), name='confirm_briefing', chapter=str(key))
        {1: s.confirm_story_arrival, 2: s.confirm_chapter2_briefing, 3: s.confirm_chapter3_briefing,
         '3b': s.confirm_chapter3b_briefing}.get(key, s.confirm_story_arrival)()
        return {}

    def do_mark_dialogue(self, a):
        """The player read the senior's pages for the current event. A display fact only (engine dialogue_seen)."""
        s = self.session
        if not s.story:
            raise ActionError('스토리 대화가 없습니다.')
        event = a.get('event')
        self.journey.record('dialogue', self._minute(), event=str(event)[:40])
        s.mark_story_dialogue(event)
        return {}

    def do_start_next_chapter(self, a):
        """Start the next chapter in this regular story save with the engine's own start method, then keep the
        chapter-start checkpoint (as the Python game does). The expected chapter guards against a stale double click."""
        s = self.session
        if s.mode != 'story' or not s.story:
            raise ActionError('스토리 도전 저장에서만 다음 장을 시작할 수 있습니다.')
        key = current_chapter(s.story).key
        nxt = campaign.next_key(key)
        if nxt is None:
            raise ActionError('마지막 장입니다. 결과 화면에서 다음 행동을 고르세요.')
        if str(a.get('chapter')) != str(nxt):
            raise ActionError('화면의 장 정보가 최신이 아닙니다. 다시 확인해 주세요.', f'지금 이어지는 장: {CHAPTERS[nxt].heading}')
        self.journey.record('engine', self._minute(), name='start_next_chapter', chapter=str(nxt))
        start = {2: s.start_chapter2, 3: s.start_chapter3, '3b': s.start_chapter3b, 'lab': s.start_training}[nxt]
        try:
            start()   # engine checks unlock (previous chapter success), practice/tutorial rules and receives the requests
        except ValueError as exc:
            raise ActionError(campaign._player_words(str(exc))) from None
        self.journey.data['selection'] = {}
        result = {'info': f'{CHAPTERS[nxt].heading} 시작 · 새 고객 요청이 도착했습니다.', 'chapter': str(nxt)}
        try:
            result['checkpoint'] = capture(s).name
        except Exception as exc:   # the chapter already started and is saved; only the retry copy is missing
            result['hint'] = f'장은 시작됐지만 재도전용 시작 기록을 만들지 못했습니다: {exc}'
        return result

    def do_start_next_shift(self, a):
        """Phase 6: the next global shift starts in THIS save (engine start_next_shift). A stale screen is refused."""
        s = self.session
        if not isinstance(s, GlobalSession) or s.global_.kind != 'shift':
            raise ActionError('글로벌 교대 근무 저장에서만 다음 교대를 시작할 수 있습니다.')
        nxt = s.next_shift()
        if nxt is None or str(a.get('shift')) != str(nxt):
            raise ActionError('화면의 교대 정보가 최신이 아닙니다. 다시 확인해 주세요.')
        self.journey.record('engine', self._minute(), name='start_next_shift', shift=nxt)
        s.start_next_shift()   # engine: refuses unless the current shift is cleared
        self.journey.data['selection'] = {}
        return {'info': f'교대 {nxt} · {s.shift_def()["title"]} 시작 · 선배 브리핑을 확인하세요.', 'shift': nxt}

    def do_mark_shift_seen(self, a):
        """The player closed a shift result screen (display fact only)."""
        if not isinstance(self.session, GlobalSession):
            raise ActionError('글로벌 근무에서만 사용합니다.')
        key = a.get('key')
        self.journey.record('feedback', self._minute(), card='shift', key=str(key)[:40])
        self.session.mark_shift_seen(key)
        return {}

    # Phase 7 · incident response: every judgement is the engine's (IncidentSession) ----------------------------
    def _incidents(self):
        if not isinstance(self.session, IncidentSession):
            raise ActionError('장애 대응 근무 또는 사건 연습에서만 사용할 수 있습니다.')
        return self.session

    def do_end_free_shift(self, a):
        if not isinstance(self.session, FreeShiftSession):
            raise ActionError('새 글로벌 자유 교대에서만 사용할 수 있습니다.')
        out = self.session.end_free_shift()
        return {'freeShift': out, 'info': '새 접수를 멈췄습니다. 남은 요청·사건을 정리하면 결과를 표시합니다.'}

    def _linux(self):
        if not isinstance(self.session, LinuxSession):
            raise ActionError('Linux 실무 연수에서만 사용할 수 있습니다.')
        if self._location() != 'noc':
            raise ActionError('내 자리 모니터의 가상 터미널에서 실행하세요. 랙 현장 콘솔과 구분됩니다.')
        return self.session

    def do_linux_command(self, a):
        s = self._linux()
        if not isinstance(a.get('token'), str):
            raise ActionError('현재 화면의 사건 토큰이 필요합니다. 새로고침 후 다시 실행하세요.')
        out = s.cli(self._iid(a), a.get('line'), a.get('node'), a.get('token'))
        return {'linux': out}

    def do_linux_interpret(self, a):
        s = self._linux()
        if type(a.get('seq')) is not int:
            raise ActionError('실행한 관측 번호를 선택하세요.')
        if not isinstance(a.get('token'), str):
            raise ActionError('현재 화면의 사건 토큰이 필요합니다. 새로고침 후 다시 선택하세요.')
        return {'linux': s.interpret(self._iid(a), a['seq'], a.get('answer'), a['token'])}

    def do_linux_help(self, a):
        return {'info': self._linux().help_for(self._iid(a))}

    def _location(self):
        route = self.journey.route
        return self.journey.data.get('room') if route == 'room' else route

    @staticmethod
    def _iid(a):
        iid = a.get('incident')
        if not isinstance(iid, str) or len(iid) > 16:
            raise ActionError('사건을 고르세요.')
        return iid

    def do_incident_ack(self, a):
        s, iid = self._incidents(), self._iid(a)
        self.journey.record('incident', self._minute(), name='ack', incident=iid)
        scope = s.incident_ack(iid)
        return {'incident': {'scope': campaign.jsonable(scope)}, 'info': '범위 확인: ' + scope['text']}

    def do_incident_observe(self, a):
        s, iid, probe = self._incidents(), self._iid(a), a.get('probe')
        if not isinstance(probe, str):
            raise ActionError('관측을 고르세요.')
        where = self._location()
        self.journey.record('incident', self._minute(), name='observe', incident=iid, probe=probe[:20], at=str(where))
        entry = s.incident_observe(iid, probe, where)
        return {'incident': {'evidence': campaign.jsonable(entry)}, 'info': f'관측 기록 · {entry["summary"]}'}

    def do_incident_hypothesis(self, a):
        s, iid, cause = self._incidents(), self._iid(a), a.get('cause')
        if not isinstance(cause, str):
            raise ActionError('원인 가설을 고르세요.')
        self.journey.record('incident', self._minute(), name='hypothesis', incident=iid, cause=cause[:20])
        entry = s.incident_hypothesis(iid, cause)
        word = {'confirmed': '원인 확정', 'refuted': '가설 반박', 'insufficient': '근거 부족'}[entry['verdict']]
        out = {'incident': {'hypothesis': campaign.jsonable(entry)}}
        out['info' if entry['verdict'] == 'confirmed' else 'hint'] = f'{word} · {entry["reason"]}'
        return out

    def do_incident_act(self, a):
        s, iid, action = self._incidents(), self._iid(a), a.get('action')
        if not isinstance(action, str):
            raise ActionError('조치를 고르세요.')
        if isinstance(s, LinuxSession):
            rec = s._open(iid)
            if rec.cause:
                location = s.action_location(rec, action)
                if location and self._location() != location:
                    raise ActionError(f'이 대응은 {incident_view.LOCATION_LABELS.get(location, location)}의 승인된 현장 화면에서 요청하세요.')
        rid, index = a.get('rid'), a.get('index', 0)
        if rid is not None and type(rid) is not int:
            raise ActionError('요청 번호가 올바르지 않습니다.')
        if type(index) is not int:
            raise ActionError('배정안 번호가 올바르지 않습니다.')
        self.journey.record('incident', self._minute(), name='act', incident=iid, action=action[:24], rid=rid)
        entry = s.incident_act(iid, action, rid=rid, index=index)
        out = {'incident': {'action': campaign.jsonable(entry)}}
        out['hint' if entry['result'] in ('none', 'refused') else 'info'] = f'{entry["label"]} · {entry["text"]}'
        return out

    def do_incident_verify(self, a):
        s, iid = self._incidents(), self._iid(a)
        self.journey.record('incident', self._minute(), name='verify', incident=iid)
        out = s.incident_verify(iid)
        return {'incident': out, 'info': f'사후 확인 완료 · {out["verified"]}'}

    def do_incident_report(self, a):
        s, iid = self._incidents(), self._iid(a)
        self.journey.record('incident', self._minute(), name='report', incident=iid)
        out = s.incident_report(iid)
        return {'incident': out, 'info': out['report']}

    def do_wait_request(self, a):
        rid, _ = self._run(a.get('rid'))
        self.journey.record('engine', self._minute(), name='wait_request', rid=rid)
        self._focus(rid)
        self.session.wait_request()
        return {'info': '요청을 대기로 두었습니다. GPU·전력은 점유하지 않으며 기한은 계속 다가옵니다.'}

    def do_reject_request(self, a):
        rid, _ = self._run(a.get('rid'))
        reason = a.get('reason')
        if not isinstance(reason, str) or len(reason) > 200:
            raise ActionError('거절 사유를 입력해 주세요.')
        self.journey.record('engine', self._minute(), name='reject_request', rid=rid)
        self._focus(rid)
        self.session.reject_request(reason)
        return {'info': '요청을 거절했습니다. 고객에게 사유를 전달했습니다.'}

    def do_ack_feedback(self, a):
        """The player closed a senior's result card. Display fact only; the engine shows each card once."""
        s, kind, key = self.session, a.get('kind'), a.get('key')
        self.journey.record('feedback', self._minute(), card=str(kind)[:12], key=str(key)[:40])
        if kind == 'chapter2':
            s.mark_chapter2_failure_seen()
        elif kind == 'chapter3':
            s.mark_chapter3_feedback_seen(key)
        elif kind == 'chapter3b':
            s.mark_chapter3b_feedback_seen(key)
        else:
            raise ActionError('알 수 없는 안내입니다.')
        return {}

    # Chapter 5 · Engineering Lab: the Python training methods (same interpreter as the Tk Lab) ----------------
    def _lab(self):
        if not self.session.training:
            raise ActionError('제5장(심화 연수) 또는 Engineering Lab 연습에서만 사용할 수 있습니다.')
        return self.session.training

    @staticmethod
    def _command_payload(result):
        return {'line': result.line, 'ok': result.ok, 'output': result.output, 'kind': result.kind,
                'command': result.command, 'hint': result.hint, 'time': result.time_label,
                'facts': campaign.jsonable(result.facts)}

    def do_lab_segment(self, a):
        self._lab()
        segment = a.get('segment')
        if not isinstance(segment, str):
            raise ActionError('구간을 고르세요.')
        self.journey.record('lab', self._minute(), name='segment', segment=segment[:24])
        correct, text = self.session.training_select_segment(segment)
        return {'lab': {'correct': correct, 'text': text}}

    def do_lab_answer(self, a):
        self._lab()
        stage, question, answer = a.get('stage'), a.get('question'), a.get('answer')
        if not isinstance(stage, str) or not isinstance(question, str):
            raise ActionError('질문 형식이 올바르지 않습니다.')
        if not (isinstance(answer, (str, int)) and not isinstance(answer, bool)
                or isinstance(answer, dict) and all(isinstance(v, str) for v in answer.values())):
            raise ActionError('답 형식이 올바르지 않습니다.')
        self.journey.record('lab', self._minute(), name='answer', stage=stage, question=question)
        correct, text = self.session.training_answer(stage, question, answer)
        return {'lab': {'correct': correct, 'text': text}}

    def do_lab_command(self, a):
        self._lab()
        source, stage, payload = a.get('source'), a.get('stage'), a.get('payload')
        if source == 'blocks':
            if not isinstance(payload, list) or len(payload) != 3 or any(x is not None and not isinstance(x, str) for x in payload):
                raise ActionError('명령 블록 형식이 올바르지 않습니다.')
            payload = tuple(x or None for x in payload)
        elif not isinstance(payload, str) or len(payload) > 200:
            raise ActionError('명령은 200자 이하의 한 줄이어야 합니다.')
        self.journey.record('lab', self._minute(), name='command', source=str(source)[:10], stage=str(stage)[:12])
        result = self.session.training_command(source, payload, stage)
        return {'lab': self._command_payload(result)}

    def do_lab_blocks_preview(self, a):
        """Read-only: how the current blocks read as one command line (same parser). Records nothing."""
        parts = a.get('blocks')
        if not isinstance(parts, list) or len(parts) != 3 or any(x is not None and not isinstance(x, str) for x in parts):
            raise ActionError('명령 블록 형식이 올바르지 않습니다.')
        line, roles, errors = block_feedback(*(x or None for x in parts))
        return {'lab': {'line': line, 'roles': roles, 'errors': errors}}

    def do_lab_next_stage(self, a):
        self._lab()
        self.journey.record('lab', self._minute(), name='next_stage')
        return {'lab': {'stage': self.session.start_next_stage()}}

    def do_lab_focus_stage(self, a):
        self._lab()
        self.journey.record('lab', self._minute(), name='focus_stage', stage=str(a.get('stage'))[:12])
        self.session.focus_training_stage(a.get('stage'))
        return {}

    def do_lab_restart_incident(self, a):
        self._lab()
        self.journey.record('lab', self._minute(), name='restart_incident')
        rid = self.session.restart_training_incident()
        return {'info': f'같은 교육 조건의 새 연수 사건(요청 #{rid})을 접수했습니다. 통과한 Stage는 유지됩니다.'}

    def do_read_request(self, a):
        rid, _ = self._run(a.get('rid'))
        self.journey.record('engine', self._minute(), name='read_request', rid=rid)
        lines = self.session.read_conversation(rid)
        return {'conversation': [list(x) for x in lines]}

    def do_select_request(self, a):
        rid, _ = self._run(a.get('rid'))
        self.journey.record('engine', self._minute(), name='select_request', rid=rid)
        self._focus(rid)
        return {}

    def do_propose_alternative(self, a):
        rid, _ = self._run(a.get('rid'))
        self.journey.record('engine', self._minute(), name='propose_alternative', rid=rid)
        self._focus(rid)
        proposal = self.session.propose_alternative()
        return {'info': '고객에게 절약형 대안을 제시했습니다. [고객 답변 확인]으로 회신을 확인하세요.',
                'proposal': {'mode': proposal['proposed']['mode'], 'onTime': proposal['on_time']}}

    def do_check_reply(self, a):
        rid, _ = self._run(a.get('rid'))
        self.journey.record('engine', self._minute(), name='check_reply', rid=rid)
        self._focus(rid)
        accepted = self.session.review_alternative()
        return {'info': '고객이 대안에 동의했습니다.' if accepted else '고객이 대안을 거절했습니다. 원래 조건으로만 시작할 수 있습니다.'}

    def do_start_job(self, a):
        rid, run = self._run(a.get('rid'))
        sel = self.journey.selection(rid)
        if sel is None:
            raise ActionError('먼저 내 모니터의 [배정 계획]에서 배정안을 고르세요.')
        if self.journey.route != 'hall':
            raise ActionError('작업 시작은 서버동 01 현장에서 합니다.', '위쪽 [서버동 01]로 이동하세요.')
        server = RACK_SERVERS.get(a.get('rack')) if isinstance(a.get('rack'), str) else None
        if server not in [p['server'] for p in sel['slices']]:
            raise ActionError('고른 배정안에 들어 있는 서버 랙에서 시작하세요.',
                              '배정안의 서버: ' + '·'.join(f"{p['server']}({p['rack']})" for p in sel['slices']))
        self.journey.record('engine', self._minute(), name='start_job', rid=rid, rack=a.get('rack'))
        self._focus(rid)
        # The engine re-checks consent, resources and the exact GPU slots; a stale choice is refused, never replaced.
        self.session.choose_plan(sel['mode'], _slices_from(sel['slices']))
        return {'info': f'{sel["label"]} 시작 · 엔진이 GPU {run.state.gpu_used} / 전력 {run.state.power_used}을 점유했습니다.'}

    def do_advance_time(self, a):
        minutes = a.get('minutes')
        if type(minutes) is not int or minutes not in ADVANCE_MINUTES:
            raise ActionError('시간은 10분, 30분 또는 60분 단위로 진행해 주세요.')
        s = self.session
        if not self.can_advance():
            raise ActionError('진행 중인 작업이 없습니다. 먼저 배정안으로 작업을 시작하세요.',
                              '요청 확인 → 배정 계획 → 서버동에서 작업 시작')
        self.journey.record('engine', self._minute(), name='advance_time', minutes=minutes)
        injected = self._tutorial_director()
        s.advance_time(minutes)
        return {'info': f'{minutes}분 진행 · 현재 {s.time_label}', 'fault': injected}

    def _tutorial_director(self):
        """Tutorial scenario: the first time the player lets time run, a training server fault starts on the
        busiest server of the job. It uses the engine's existing educational fault injection; nothing else
        (time, progress, score) is touched here."""
        if self.journey.kind != 'tutorial' or self.journey.data['fault'] or self.journey.data['skipped']:
            return None
        run = self._tutorial_run()
        s = self.session
        if not run or not run.state.allocated or run.state.work_done > 0 or s.hardware_servers(run):
            return None
        allocation = s.servers.allocations[run.playthrough_id]
        server = max(allocation.slices, key=lambda p: (p.gpu, -ord(p.server_id))).server_id
        s.inject_server_fault(server)
        self.journey.data['fault'] = {'server': server, 'rack': SERVER_RACKS[server], 'minute': s.minute, 'rid': run.request['id']}
        self.journey.record('tutorial_fault', s.minute, server=server, rid=run.request['id'])
        self._backup = self.journey.transaction()   # the engine fault is committed; keep its record even if a later step fails
        return {'server': server, 'rack': SERVER_RACKS[server]}

    def do_begin_repair(self, a):
        rid, run = self._run(a.get('rid'))
        server = a.get('server')
        self._require_diagnosis(run)
        self.journey.record('engine', self._minute(), name='begin_repair', rid=rid, server=server)
        if server not in {spec.key for spec in SERVERS}:
            raise ActionError('존재하지 않는 서버입니다.')
        self.session.begin_server_repair(server)
        return {'info': f'Server {server} 장비 복구 시작 · 가상 시간 20분 필요'}

    def do_migrate(self, a):
        rid, run = self._run(a.get('rid'))
        self._require_diagnosis(run)
        self.journey.record('engine', self._minute(), name='migrate', rid=rid, index=a.get('index'))
        self._focus(rid)
        s = self.session
        if s.chapter3b_locked(run):
            raise ActionError('먼저 [장비 진단]을 열어 이전 가능 여부와 예상 시간을 확인한 뒤 대응을 선택해 주세요.',
                              '내 모니터 → [진단] 탭')
        preview = s.migration_preview(run)
        if not preview['allowed']:
            raise ActionError('작업 이전 불가: ' + preview['reason'], '진단 결과의 정상 서버 여유를 다시 보세요.')
        index = a.get('index', 0)
        if type(index) is not int or not 0 <= index < len(preview['options']):
            raise ActionError('이전 계획을 다시 조회해 주세요.')
        s.migrate(preview['options'][index], preview['source'])
        return {'info': '작업 이전 확정 · 준비 10분 후 새 서버에서 재개'}

    def do_respond(self, a):
        rid, run = self._run(a.get('rid'))
        key = a.get('key')
        if key not in RESPONSES:
            raise ActionError('존재하지 않는 대응입니다.')
        self._require_diagnosis(run)
        self.journey.record('engine', self._minute(), name='respond', rid=rid, key=key)
        self._focus(rid)
        try:
            self.session.respond(key)
        except ValueError as exc:
            if self.session.hardware_servers(run):
                raise ActionError(str(exc), '지금 문제는 네트워크가 아니라 서버 장비입니다. 진단의 서버 상태를 보세요.') from None
            raise
        return {'info': run.state.result_text}

    def do_notify_delay(self, a):
        rid, _ = self._run(a.get('rid'))
        self.journey.record('engine', self._minute(), name='notify_delay', rid=rid)
        self._focus(rid)
        self.session.notify_delay()
        return {'info': '고객에게 지연 상황을 안내했습니다.'}

    def do_retry(self, a):
        rid, run = self._run(a.get('rid'))
        key = a.get('mode', run.state.plan)
        self.journey.record('engine', self._minute(), name='retry', rid=rid, mode=key)
        self._focus(rid)
        self.session.retry(key)
        return {'info': '재처리를 시작했습니다. 준비 20분 후 실행됩니다.'}

    def do_report_failure(self, a):
        rid, _ = self._run(a.get('rid'))
        self.journey.record('engine', self._minute(), name='report_failure', rid=rid)
        self._focus(rid)
        self.session.report_failure()
        return {'info': '고객에게 처리 불가를 보고했습니다.'}

    def close(self):
        try:
            self.session.close()
        finally:
            self.db.release_game()


class GameHost:
    """All 3D saves live in one folder. Starting always creates a new file; nothing is overwritten.

    SQLite connections belong to the thread that opened them (database.py is unchanged), so a server passes
    worker=True and every engine call then runs on one dedicated thread through `run()`.
    """

    def __init__(self, save_dir, worker=False):
        self.dir = Path(save_dir).resolve()
        if self.dir == ROOT:
            raise ValueError('3D 저장 폴더로 기존 Python 게임 폴더를 사용할 수 없습니다.')
        self.dir.mkdir(parents=True, exist_ok=True)
        self.slots = StorySlots(self.dir)
        self.games: dict[str, Game] = {}
        self.lock = threading.RLock()
        self._worker = ThreadPoolExecutor(1, thread_name_prefix='srs3d-engine') if worker else None

    def run(self, fn, *args):
        if self._worker is None:
            return fn(*args)
        return self._worker.submit(fn, *args).result()

    def _sidecar(self, path):
        return Path(path).with_name(Path(path).stem + '.3d.json')

    def _reserve_free(self):
        number = max((int(m[1]) for p in self.dir.glob('aidc_3d_free_*.db') if (m := FREE_PATTERN.fullmatch(p.name))), default=0) + 1
        while True:
            path = self.dir / f'aidc_3d_free_{number:03d}.db'
            try:
                with path.open('xb'):
                    pass
            except FileExistsError:
                number += 1
            else:
                return path

    def _open(self, path, kind, fresh, chapter=1, options=None):
        db = Database(path)
        try:
            if fresh and (db.get_simulation() or db.get_requests()):
                raise ValueError('새 게임에 기존 기록을 사용할 수 없습니다.')
            db.claim_game()
            if kind == 'senior':
                session = SeniorSession(db, shift=chapter or 1) if fresh else SeniorSession(db)
            elif kind in ('linux', 'linux_practice'):
                session = (LinuxSession(db, practice=chapter if kind == 'linux_practice' else None,
                                        shift=1 if kind == 'linux_practice' else chapter or 1)
                           if fresh else LinuxSession(db))
            elif kind in ('incident', 'incident_practice'):
                # Phase 7: IncidentSession (GlobalSession rules + incident state machine); the save says shift/practice.
                session = ((IncidentSession(db, shift=chapter or 1) if kind == 'incident' else IncidentSession(db, practice=chapter))
                           if fresh else IncidentSession(db))
            elif kind in ('global', 'global_free'):
                # Phase 6: the same GameSession rules through its subclass; a saved file says its own kind/shift.
                payload = db.get_simulation() if not fresh else None
                if (fresh and kind == 'global_free') or (payload and payload.get('free_incidents')):
                    session = FreeShiftSession(db, **(options or {}))
                else:
                    session = (GlobalSession(db, kind='shift' if kind == 'global' else 'free', shift=chapter or 1)
                               if fresh else GlobalSession(db))
            else:
                mode = {'free': 'free', 'practice': 'story'}.get(kind, kind)
                options = {'intro_flow': True} if fresh and kind in ('tutorial', 'story') else {}
                if fresh and kind == 'practice':
                    options = {'start_chapter': chapter}
                session = GameSession(db, mode=mode, **options)
            if fresh and kind == 'story':
                capture(session)   # chapter-start checkpoint, as the Python menu does for a new story
            if kind in ('global', 'global_free'):
                kind = 'global' if session.global_.kind == 'shift' else 'global_free'   # the save decides, not a file peek
            if kind in ('incident', 'incident_practice'):
                kind = 'incident_practice' if session.incident.practice else 'incident'
            journey = Journey(self._sidecar(path), {'practice': 'story', 'global': 'free', 'global_free': 'free',
                                                    'incident': 'free', 'incident_practice': 'free',
                                                    'linux': 'free', 'linux_practice': 'free', 'senior': 'free'}.get(kind, kind))
            game = Game(Path(path).stem, path, kind, db, session, journey)
            game.reconcile()
            journey.evaluate(game.facts())
            journey.save()
        except Exception as exc:
            db.release_game()
            db.close()
            if not fresh and not isinstance(exc, ValueError):
                # A damaged or foreign save: report it plainly (never 404/500) and leave the file as it is.
                raise ActionError(f'이 저장 파일을 열 수 없습니다(손상되었거나 다른 형식). 파일은 그대로 두었습니다: {type(exc).__name__}') from exc
            raise
        self.games[game.id] = game
        return game

    def new_game(self, mode, chapter=None, options=None):
        if mode not in KINDS:
            raise ActionError('지원하지 않는 모드입니다.')
        if mode == 'incident_practice' and chapter not in INCIDENT_TYPES:
            raise ActionError('연습할 사건 유형을 고르세요.')
        if mode == 'linux_practice' and chapter not in INCIDENT_TYPES:
            raise ActionError('연습할 Linux 사건 유형을 고르세요.')
        if mode == 'practice':
            chapter = _chapter_key(chapter)
            if chapter not in PRACTICE_CHAPTERS:
                raise ActionError('연습할 장을 고르세요 (제2~5장).')
        with self.lock:
            if mode == 'senior':
                career = self.career()
                if not career['seniorAvailable']:
                    raise ActionError(career['reason'])
                return self._new_senior(1)
            if mode in ('linux', 'linux_practice'):
                if mode == 'linux' and not self.graduated():
                    raise ActionError('제5장 수료 후 Linux 실무 연수가 열립니다. 기존 수료 저장을 이어하거나 Linux 사건 연습을 이용하세요.')
                return self._new_linux(mode, chapter if mode == 'linux_practice' else 1)
            if mode == 'global':
                if not self.graduated():
                    raise ActionError(GLOBAL_LOCK, '스토리 도전에서 제1~5장을 클리어하면 메뉴의 글로벌 운영 카드가 열립니다.')
                return self._new_global('global', 1)
            if mode == 'global_free':
                options = options or {}
                if not isinstance(options, dict) or set(options) - {'seed', 'difficulty'}:
                    raise ActionError('자유 교대 옵션이 올바르지 않습니다.')
                return self._new_global('global_free', None, options=options)
            if mode == 'incident':
                if not self.incident_unlocked():
                    raise ActionError(INCIDENT_LOCK, '글로벌 운영 카드의 교대 근무에서 교대 3까지 클리어하면 장애 대응 근무가 열립니다.')
                return self._new_incident('incident', 1)
            if mode == 'incident_practice':
                return self._new_incident('incident_practice', chapter)
            path = self._reserve_free() if mode == 'free' else self.slots.reserve_new()
            return self._open(path, mode, fresh=True, chapter=chapter)

    def _new_linux(self, kind, which, origin=None):
        number = max((int(m[1]) for p in self.dir.glob('aidc_3d_linux_*.db')
                      if (m := LINUX_PATTERN.fullmatch(p.name))), default=0) + 1
        while True:
            path = self.dir / f'aidc_3d_linux_{number:03d}.db'
            try:
                with path.open('xb'):
                    pass
            except FileExistsError:
                number += 1
            else:
                break
        try:
            game = self._open(path, kind, fresh=True, chapter=which)
        except Exception:
            for created in (path, self._sidecar(path), path.with_name(path.name + '.lock')):
                created.unlink(missing_ok=True)
            raise
        if origin:
            game.journey.data['origin'] = origin
            game.journey.save()
        return game

    def _new_senior(self, shift, origin=None):
        number = max((int(m[1]) for p in self.dir.glob('aidc_3d_senior_*.db')
                      if (m := SENIOR_PATTERN.fullmatch(p.name))), default=0) + 1
        while True:
            path = self.dir / f'aidc_3d_senior_{number:03d}.db'
            try:
                with path.open('xb'):
                    pass
            except FileExistsError:
                number += 1
            else:
                break
        try:
            game = self._open(path, 'senior', fresh=True, chapter=shift)
        except Exception:
            for created in (path, self._sidecar(path), path.with_name(path.name + '.lock')):
                created.unlink(missing_ok=True)
            raise
        if origin:
            game.journey.data['origin'] = origin
            game.journey.save()
        return game

    def _reserve_global(self):
        number = max((int(m[1]) for p in self.dir.glob('aidc_3d_global_*.db') if (m := GLOBAL_PATTERN.fullmatch(p.name))), default=0) + 1
        while True:
            path = self.dir / f'aidc_3d_global_{number:03d}.db'
            try:
                with path.open('xb'):
                    pass
            except FileExistsError:
                number += 1
            else:
                return path

    def _reserve_incident(self):
        number = max((int(m[1]) for p in self.dir.glob('aidc_3d_incident_*.db') if (m := INCIDENT_PATTERN.fullmatch(p.name))), default=0) + 1
        while True:
            path = self.dir / f'aidc_3d_incident_{number:03d}.db'
            try:
                with path.open('xb'):
                    pass
            except FileExistsError:
                number += 1
            else:
                return path

    def _new_incident(self, kind, which, origin=None):
        path = self._reserve_incident()
        try:
            game = self._open(path, kind, fresh=True, chapter=which)
        except Exception:
            for created in (path, self._sidecar(path), path.with_name(path.name + '.lock')):
                created.unlink(missing_ok=True)
            raise
        if origin:
            game.journey.data['origin'] = origin
            game.journey.save()
        return game

    def incident_unlocked(self):
        """Global shift saves in this 3D folder whose shift 3 is cleared (read-only payload check)."""
        out = []
        for path in sorted(self.dir.glob('aidc_3d_global_*.db')):
            if not GLOBAL_PATTERN.fullmatch(path.name):
                continue
            g = self.slots.payload(path).get('global')
            if not isinstance(g, dict) or g.get('kind') != 'shift':
                continue
            done = [x for x in (g.get('history') or []) + [g.get('result')] if isinstance(x, dict)]
            if any(x.get('shift') == 3 and x.get('cleared') is True for x in done):
                out.append(path.stem)
        return out

    def _new_global(self, kind, shift, origin=None, options=None):
        path = self._reserve_global()
        try:
            game = self._open(path, kind, fresh=True, chapter=shift, options=options)
        except Exception:
            for created in (path, self._sidecar(path), path.with_name(path.name + '.lock')):
                created.unlink(missing_ok=True)
            raise
        if origin:
            game.journey.data['origin'] = origin
            game.journey.save()
        return game

    def graduated(self):
        """Regular story saves in this 3D folder whose chapters 1-5 are all cleared (read-only payload check)."""
        out = []
        for path in self.slots.available():
            data = self.slots.payload(path)
            story = data.get('story') if isinstance(data.get('story'), dict) else None
            if data.get('mode') != 'story' or not story or story.get('practice') is True:
                continue
            training = story.get('training')
            try:
                if isinstance(training, dict) and TrainingProgress(**training).done:
                    out.append(Path(path).stem)
            except (TypeError, ValueError):
                continue
        return out

    def unlocks(self):
        grads, shifts = self.graduated(), self.incident_unlocked()
        return {'global': {'available': bool(grads), 'reason': '' if grads else GLOBAL_LOCK, 'proof': grads[:1]},
                'globalFree': {'available': True, 'reason': ''},
                'incident': {'available': bool(shifts), 'reason': '' if shifts else INCIDENT_LOCK, 'proof': shifts[:1]},
                'incidentPractice': {'available': True, 'reason': '', 'types': list(INCIDENT_TYPES)},
                'linux': {'available': bool(grads), 'reason': '' if grads else '제5장 수료 후 시작 · 기존 수료 슬롯 이어하기 또는 사건 연습 가능', 'proof': grads[:1]},
                'linuxPractice': {'available': True, 'types': list(INCIDENT_TYPES)},
                'career': self.career()}

    def career(self):
        """Read-only career map, regular engine result proofs only. No XP or mutable cross-save ledger."""
        complete = {'global': set(), 'incident': set(), 'linux': set(), 'senior': set()}
        for path in self.dir.glob('*.db'):
            if not GAME_ID.fullmatch(path.stem):
                continue
            data = self.slots.payload(path)
            mode, g = data.get('mode'), data.get('global', {})
            if mode not in complete or g.get('kind') != 'shift':
                continue
            if data.get('incident', {}).get('practice') or data.get('linux', {}).get('practice'):
                continue
            for r in (g.get('history') or []) + [g.get('result')]:
                if isinstance(r, dict) and r.get('cleared') is True:
                    complete[mode].add(r.get('shift'))
        story = bool(self.graduated())
        specs = [('story', '제1~5장', 5, 5 if story else 0),
                 ('global', '글로벌 교대', 3, len(complete['global'] & {1, 2, 3})),
                 ('incident', '사건 대응', 3, len(complete['incident'] & {1, 2, 3})),
                 ('linux', 'Linux 실무 연수', 5, len(complete['linux'] & {1, 2, 3, 4, 5})),
                 ('senior', '선임 평가', 2, len(complete['senior'] & {1, 2}))]
        available = story and all(n == total for key, _, total, n in specs if key != 'senior')
        ending = complete['senior'] >= {1, 2}
        return {'version': 1, 'role': '선임 엔지니어' if ending else '담당 엔지니어' if complete['global'] >= {1, 2, 3} else '신입 엔지니어',
                'education': '독립 관제 엔지니어' if complete['linux'] >= {1, 2, 3, 4, 5} else '운영 엔지니어 수료' if story else '교육 중',
                'stages': [{'id': k, 'title': label, 'total': total, 'completed': n, 'done': total == n} for k, label, total, n in specs],
                'seniorAvailable': available, 'ending': ending,
                'reason': '' if available else '제1~5장·글로벌 3교대·사건 3교대·Linux 5근무를 모두 수료하면 선임 평가가 열립니다.'}

    def retry(self, gid):
        """[현재 장 재도전]: save the current game, then copy its chapter-start checkpoint into a NEW exclusive slot
        (aidc.storage.checkpoints.restore). The current slot and its records stay untouched. A practice save retries
        as a new practice save of the same chapter; a tutorial as a new tutorial."""
        with self.lock:
            game = self.get(gid)
            s = game.session
            if game.kind == 'senior':
                return self._new_senior(s.global_.shift, origin={'source': game.id, 'shift': s.global_.shift})
            if game.kind in ('linux', 'linux_practice'):
                return self._new_linux(game.kind, s.linux['practice'] if game.kind == 'linux_practice' else s.global_.shift,
                                       origin={'source': game.id, 'shift': s.global_.shift})
            if game.kind == 'tutorial':
                return self.new_game('tutorial')
            if game.kind == 'global':
                # Phase 6: a shift retry is a NEW global save that starts at the same shift; this save stays as it is.
                # Only a shift save qualifies (it proves the player reached that shift after graduating).
                if s.mode != 'global' or s.global_.kind != 'shift' or not s.global_.shift:
                    raise ActionError('교대 근무 저장에서만 교대를 재도전할 수 있습니다.')
                shift = s.global_.shift
                return self._new_global('global', shift, origin={'source': game.id, 'shift': shift})
            if game.kind == 'global_free':
                options = ({'seed': s.seed, 'difficulty': s.free_incidents['difficulty']}
                           if isinstance(s, FreeShiftSession) else {'seed': s.seed, 'difficulty': 'none'})
                return self._new_global('global_free', None, origin={'source': game.id}, options=options)
            if game.kind == 'incident':
                # Phase 7: a NEW incident save starting at the same response shift; this save stays as it is.
                shift = s.global_.shift
                return self._new_incident('incident', shift, origin={'source': game.id, 'shift': shift})
            if game.kind == 'incident_practice':
                return self._new_incident('incident_practice', s.incident.practice, origin={'source': game.id})
            if game.kind not in ('story', 'practice') or not s.story:
                raise ActionError('재도전은 스토리 저장에서만 할 수 있습니다.')
            key = current_chapter(s.story).key
            if game.kind == 'practice':
                return self.new_game('practice', key)
            if game.kind != 'story':
                raise ActionError('재도전은 스토리 저장에서만 할 수 있습니다.')
            if not checkpoint_path(game.path, key).is_file():
                raise ActionError('이 저장에는 현재 장의 시작 기록(체크포인트)이 없습니다. 현재 기록은 그대로 보존됩니다.',
                                  '메뉴의 스토리 도전에서 새로 시작하거나 다른 장 기록을 고르세요.')
            # Every adapter action is already committed by the engine, so the source slot is only read here.
            return self._from_checkpoint(game.path, key)

    def _from_checkpoint(self, source, key):
        target = restore(self.slots, source, key)   # read-only copy of the checkpoint into a new reserved slot
        sidecar = self._sidecar(target)
        try:
            journey = Journey(sidecar, 'story')
            journey.data['origin'] = {'source': Path(source).stem, 'chapter': str(key)}
            journey.save()
            game = self._open(target, 'story', fresh=False)
        except Exception:
            # Only files this call created are removed (the new slot copy, its sidecar and lock); the source save
            # and its checkpoint are never touched.
            for created in (target, sidecar, target.with_name(target.name + '.lock')):
                created.unlink(missing_ok=True)
            raise
        # Like the Python menu (checkpoint_start=True): the new slot keeps its own chapter-start copy, so it can be
        # retried again later. A failure here leaves the playable new slot and only reports the missing copy.
        try:
            capture(game.session)
        except Exception as exc:
            game.journey.record('checkpoint_error', game.session.minute, message=str(exc)[:200])
            game.journey.save()
        return game

    def start_checkpoint(self, gid, chapter):
        """Chapter select in the menu: start a saved chapter-start point as a new slot (source unchanged)."""
        with self.lock:
            if not isinstance(gid, str) or not GAME_ID.fullmatch(gid) or not (self.dir / f'{gid}.db').is_file():
                raise MissingSave(gid)
            key = _chapter_key(chapter)
            source = self.dir / f'{gid}.db'
            if key not in CHAPTERS or not checkpoint_path(source, key).is_file():
                raise ActionError('이 저장에는 그 장의 시작 기록이 없습니다.')
            return self._from_checkpoint(source, key)

    def checkpoints(self, path):
        return [str(key) for key in CHAPTERS if checkpoint_path(path, key).is_file()]

    def get(self, gid):
        with self.lock:
            if not isinstance(gid, str) or not GAME_ID.fullmatch(gid):
                raise MissingSave(gid)
            if gid in self.games:
                return self.games[gid]
            path = self.dir / f'{gid}.db'
            if not path.is_file():
                raise MissingSave(gid)
            kind = self._kind(path)
            if kind not in KINDS:
                raise ActionError('이 저장은 3D 시연에서 열 수 없는 종류입니다.')
            if not self._sidecar(path).is_file():
                raise ActionError('3D 진행 기록이 없는 저장입니다.')
            return self._open(path, kind, fresh=False)

    def saves(self):
        with self.lock:
            out = []
            for path in sorted(self.dir.glob('*.db')):
                if not GAME_ID.fullmatch(path.stem) or not self._sidecar(path).is_file():
                    continue
                kind = self._kind(path)
                payload = self.slots.payload(path)
                story = payload.get('story') if isinstance(payload.get('story'), dict) else None
                chapter = chapter_from_payload(story) if story and kind in ('story', 'practice') else None
                out.append({'id': path.stem, 'kind': kind, 'label': MODE_LABELS.get(kind, kind),
                            'describe': (f'선임 평가 {payload.get("global", {}).get("shift", 1)}' if kind == 'senior' else
                                         f'Linux 근무 {payload.get("global", {}).get("shift", 1)}' + (' · 연습' if kind == 'linux_practice' else '') if kind in ('linux', 'linux_practice') else
                                         self._describe_incident(payload) if kind in ('incident', 'incident_practice') else
                                         self._describe_global(payload) if kind in ('global', 'global_free') else
                                         self.slots.describe(path).lstrip(' ·') if kind != 'free' else '자유 운영'),
                            'clock': game_time(payload['minute']) if 'minute' in payload else '',
                            'chapter': ({'key': str(chapter.key), 'number': chapter.number, 'heading': chapter.heading}
                                        if chapter else None),
                            'checkpoints': self.checkpoints(path) if kind == 'story' else [],
                            'open': path.stem in self.games})
            return out

    def _kind(self, path):
        path = Path(path)
        if SENIOR_PATTERN.fullmatch(path.name):
            return 'senior'
        if LINUX_PATTERN.fullmatch(path.name):
            l = self.slots.payload(path).get('linux')
            return 'linux_practice' if isinstance(l, dict) and l.get('practice') else 'linux'
        if FREE_PATTERN.fullmatch(path.name):
            return 'free'
        if INCIDENT_PATTERN.fullmatch(path.name):
            inc = self.slots.payload(path).get('incident')
            return 'incident_practice' if isinstance(inc, dict) and inc.get('practice') else 'incident'
        if GLOBAL_PATTERN.fullmatch(path.name):
            g = self.slots.payload(path).get('global')
            return 'global_free' if isinstance(g, dict) and g.get('kind') == 'free' else 'global'
        return self.slots.category(path)

    @staticmethod
    def _describe_incident(payload):
        inc = payload.get('incident') if isinstance(payload.get('incident'), dict) else {}
        g = payload.get('global') if isinstance(payload.get('global'), dict) else {}
        content = load_incidents()
        if inc.get('practice') in content.types:
            return f'사건 연습 · {content.types[inc["practice"]]["symptom"]}'
        shift = content.shifts.get(str(g.get('shift')), {})
        state = ('클리어' if g['result'].get('cleared') else '목표 미달성') if isinstance(g.get('result'), dict) else '진행 중'
        return f'{shift.get("title", "장애 대응 근무")} · {state}'

    @staticmethod
    def _describe_global(payload):
        g = payload.get('global') if isinstance(payload.get('global'), dict) else {}
        if g.get('kind') == 'free':
            return '글로벌 자유 운영'
        shift = g.get('shift')
        title = global_view.CATALOG.shifts.get(str(shift), {}).get('title', '')
        state = ('클리어' if g['result'].get('cleared') else '목표 미달성') if isinstance(g.get('result'), dict) else '진행 중'
        return f'교대 {shift} · {title} · {state}'

    def close(self, gid=None):
        def work():
            with self.lock:
                for key in ([gid] if gid else list(self.games)):
                    game = self.games.pop(key, None)
                    if game:
                        game.close()
        self.run(work)

    def shutdown(self):
        self.close()
        if self._worker is not None:
            self._worker.shutdown(wait=True)
