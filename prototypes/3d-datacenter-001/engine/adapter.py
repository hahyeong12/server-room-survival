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
from aidc.storage.checkpoints import capture  # noqa: E402
from aidc.story.chapters import CHAPTERS, chapter_state, STATE_LABELS  # noqa: E402
from aidc.ui.job_status import job_status  # noqa: E402  (pure, no Tk)
from result_summary import job_summary  # noqa: E402

from .journey import Journey, ROUTES, BUILDINGS  # noqa: E402

API_VERSION = 1
COUNTRY_CODES = {'싱가포르': 'SG', '일본': 'JP', '미국': 'US'}
# Engine servers A~D live in column 1 of the 3D hall. The other 20 racks are decoration only.
SERVER_RACKS = {'A': 'A-01', 'B': 'B-01', 'C': 'C-01', 'D': 'D-01'}
RACK_SERVERS = {rack: key for key, rack in SERVER_RACKS.items()}
DECOR_RACKS = tuple(f'{row}-{col:02d}' for row in 'ABCD' for col in range(1, 7) if col != 1)
MODE_LABELS = {'tutorial': '튜토리얼', 'story': '스토리 도전', 'free': '자유 운영'}
FREE_PATTERN = re.compile(r'aidc_3d_free_([0-9]+)\.db')
GAME_ID = re.compile(r'(aidc_story_slot|aidc_3d_free)_[0-9]{3,}')
ADVANCE_MINUTES = (10, 30, 60)
OPEN_STATUSES = ('new', 'review', 'waiting')


class ActionError(ValueError):
    """A rejected action. `hint` is extra guidance; nothing in the game changed."""

    def __init__(self, message, hint=''):
        super().__init__(message)
        self.hint = hint


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
        view = {
            'id': rid, 'country': country, 'code': COUNTRY_CODES.get(country, '??'),
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
            'network': {'needed': st.network_needed, 'available': st.network_available, 'attempts': st.response_attempts,
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
        s = self.session
        if not s.story:
            return None
        intro = s.story.onboarding
        state, text = chapter_state(s) if s.mode == 'story' else (('cleared' if intro and intro.done else 'in_progress'), '')
        chapter = CHAPTERS[1]
        view = {'kind': intro.kind if intro else None, 'step': intro.step if intro else None,
                'card': intro.card if intro else None, 'objective': intro.objective if intro else '',
                'pages': [list(p) for p in intro.pages] if intro and intro.step == 'arrival' else [],
                'done': bool(intro and intro.done), 'jobsDone': len(intro.completed) if intro else 0,
                'jobsTotal': intro.total if intro else 0,
                'chapter': {'key': 1, 'label': chapter.label, 'title': chapter.title, 'heading': chapter.heading,
                            'intro': chapter.intro, 'state': state, 'stateLabel': STATE_LABELS.get(state, state), 'text': text},
                'result': None}
        if intro and intro.done:
            view['result'] = s.chapter_result()
        return view

    def _world(self):
        s, paths = self.session, []
        for rid, run in s.runs.items():
            stage = self._stage(run)
            if stage in ('done', 'failed', 'rejected'):
                continue
            aidc = {'hw_fault': 'fault', 'hw_repair': 'repairing', 'migration': 'repairing'}.get(stage, 'ok')
            link = 'degraded' if stage == 'net_fault' else 'ok'
            paths.append({'rid': rid, 'code': COUNTRY_CODES.get(run.mission['country'], '??'),
                          'tone': 'incoming' if stage == 'incoming' else 'active', 'focus': rid == s.selected_id,
                          'segments': {'sea': link, 'landing': link, 'backbone': link, 'aidc': aidc}})
        return {'paths': paths}

    def snapshot(self):
        """Read-only view of the engine state and the saved journey."""
        s = self.session
        story = self._story()
        center = s.center
        healthy_gpu, healthy_power = s.servers.available()
        return {
            'api': API_VERSION, 'engine': 'python:session.GameSession', 'id': self.id, 'mode': s.mode,
            'modeLabel': MODE_LABELS[s.mode], 'kind': self.kind,
            'clock': {'minute': s.minute, 'label': s.time_label},
            'focus': s.selected_id,
            'requests': [self._request(rid, run) for rid, run in s.runs.items()],
            'servers': self._servers(),
            'datacenter': {'gpuTotal': center.gpu_total, 'gpuUsed': center.gpu_used, 'powerTotal': center.power_total,
                           'powerUsed': center.power_used, 'healthyFreeGpu': healthy_gpu, 'healthyFreePower': healthy_power},
            'canAdvance': any(run.state.allocated for run in s.runs.values()) or s.mode == 'free',
            'story': story,
            'free': ({'pending': s.pending_request_count, 'nextArrival': s.next_arrival_label} if s.mode == 'free' else None),
            'journey': self.journey.view(),
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
        rid = run.request['id']
        if not any(e['type'] == 'diagnose' and e.get('rid') == rid for e in self.journey.data['events']):
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
            self.journey.evaluate(self.facts())
            self.journey.save()
        except Exception as exc:
            # Journey facts of a refused action are undone (the engine already rolled itself back); only the
            # attempt itself is kept, so a wrong click never completes a step.
            self.journey.rollback(self._backup)
            if isinstance(exc, ValueError):
                self.journey.record('rejected', self._minute(), action=kind, message=str(exc)[:200])
                self.journey.misclick()
                self.journey.save()
            raise
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
        return {}

    def do_select_facility(self, a):
        if a.get('id') not in BUILDINGS:
            raise ActionError('알 수 없는 건물입니다.')
        self.journey.record('select_facility', self._minute(), id=a['id'], via=str(a.get('via', 'chip'))[:16],
                            route=self.journey.route)
        return {}

    def do_select_country(self, a):
        code = a.get('id')
        if code not in ('KR', *COUNTRY_CODES.values()):
            raise ActionError('알 수 없는 국가입니다.')
        self.journey.record('select_country', self._minute(), id=code)
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

    def do_inspect_rack(self, a):
        rack = a.get('rack')
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
                          'options': [_slices_payload(opt) for opt in o['options']]}
        return {'plans': modes}

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
        self.journey.set_selection(rid, {'mode': mode, 'index': index, 'slices': _slices_payload(parts),
                                         'label': run.state.plans[mode]['label'], 'minute': s.minute})
        s.inspect_story_preview(rid)   # engine: marks the plan review (onboarding 'reviewed') when the request was read
        return {'info': f'{run.state.plans[mode]["label"]} · 배정안 {index+1} 선택 (자원 미점유). 서버동에서 시작하세요.'}

    def do_diagnose(self, a):
        rid, run = self._run(a.get('rid'))
        s = self.session
        self.journey.record('diagnose', self._minute(), rid=rid)
        preview = s.migration_preview(run)
        return {'diagnosis': {
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

    def do_verify(self, a):
        rid, run = self._run(a.get('rid'))
        s = self.session
        allocation = s.servers.allocations.get(run.playthrough_id) if run.playthrough_id else None
        rack = a.get('rack')
        server = RACK_SERVERS.get(rack) if isinstance(rack, str) else None
        fault = self.journey.data['fault']
        target = server or (fault['server'] if fault else None)
        state = s.servers.hardware[target].state if target else None
        issues = s.hardware_status(run)
        ok = bool(target) and state == 'HEALTHY' and not issues and run.state.phase in ('running', 'finished')
        if fault and target != fault['server']:
            ok = False
            self.journey.record('verify', self._minute(), rid=rid, server=target, state=state, ok=False)
            return {'hint': f'장애가 났던 서버는 Server {fault["server"]}(랙 {fault["rack"]})입니다. 그 랙을 다시 확인하세요.'}
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
        self.journey.record('engine', self._minute(), name='confirm_briefing')
        self.session.confirm_story_arrival()
        return {}

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
        if s.mode != 'free' and not any(run.state.allocated for run in s.runs.values()):
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
        if self.journey.kind != 'tutorial' or self.journey.data['fault']:
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

    def _open(self, path, kind, fresh):
        db = Database(path)
        try:
            if fresh and (db.get_simulation() or db.get_requests()):
                raise ValueError('새 게임에 기존 기록을 사용할 수 없습니다.')
            db.claim_game()
            mode = 'free' if kind == 'free' else kind
            options = {'intro_flow': True} if fresh and kind in ('tutorial', 'story') else {}
            session = GameSession(db, mode=mode, **options)
            if fresh and kind == 'story':
                capture(session)   # chapter-start checkpoint, as the Python menu does for a new story
            journey = Journey(self._sidecar(path), kind)
            game = Game(Path(path).stem, path, kind, db, session, journey)
            journey.evaluate(game.facts())
            journey.save()
        except Exception:
            db.release_game()
            db.close()
            raise
        self.games[game.id] = game
        return game

    def new_game(self, mode):
        if mode not in ('tutorial', 'story', 'free'):
            raise ActionError('지원하지 않는 모드입니다.')
        with self.lock:
            path = self._reserve_free() if mode == 'free' else self.slots.reserve_new()
            return self._open(path, mode, fresh=True)

    def get(self, gid):
        with self.lock:
            if not isinstance(gid, str) or not GAME_ID.fullmatch(gid):
                raise KeyError(gid)
            if gid in self.games:
                return self.games[gid]
            path = self.dir / f'{gid}.db'
            if not path.is_file():
                raise KeyError(gid)
            kind = 'free' if FREE_PATTERN.fullmatch(path.name) else self.slots.category(path)
            if kind not in ('tutorial', 'story', 'free'):
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
                kind = 'free' if FREE_PATTERN.fullmatch(path.name) else self.slots.category(path)
                payload = self.slots.payload(path)
                out.append({'id': path.stem, 'kind': kind, 'label': MODE_LABELS.get(kind, kind),
                            'describe': self.slots.describe(path).lstrip(' ·') if kind != 'free' else '자유 운영',
                            'clock': game_time(payload['minute']) if 'minute' in payload else '',
                            'open': path.stem in self.games})
            return out

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
