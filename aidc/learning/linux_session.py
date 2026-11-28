"""Finite Linux learning atop the real Phase7 incident/session engine (separate saves).

Only valid observations are persisted. No shell or real equipment is accessible.
Old incidents, global shifts and Chapter5 do not instantiate this class.
"""
from contextlib import contextmanager
from copy import deepcopy
import hashlib

from aidc.incidents.session import IncidentSession, FINAL
from . import linux_catalog as catalog
from . import linux_curriculum as curriculum
from .linux_terminal import result, contexts, job_servers, server_ip, STORAGE_IP, PORTS

class LinuxSession(IncidentSession):
    SAVE_MODE = 'linux'
    MODES = IncidentSession.MODES + ('linux',)

    def __init__(self, db, shift=1, practice=None, seed=None):
        saved = db.get_simulation()
        if saved:
            value = saved.get('linux')
            if not isinstance(value, dict) or value.get('version') != curriculum.VERSION:
                raise ValueError('지원하지 않는 Linux 학습 저장 버전입니다. 기존 저장은 보존됩니다.')
            self.linux = deepcopy(value)
            if value.get('fingerprint') != self._fingerprint():
                raise ValueError('학습·명령 catalog가 저장 당시와 다릅니다. 같은 버전으로 이어하세요.')
        else:
            if type(shift) is not int or shift not in curriculum.SHIFTS:
                raise ValueError('Linux 근무는 1~5입니다.')
            if practice is not None and practice not in curriculum.CASES:
                raise ValueError('존재하지 않는 Linux 사건 연습입니다.')
            self.linux = {'version': curriculum.VERSION, 'fingerprint': self._fingerprint(),
                          'practice': practice, 'seq': 0, 'observations': [], 'interpretations': [], 'help': []}
        # Parent result wording ('연습'), adapter stamp and menus read IncidentBook.practice. The Linux curriculum still
        # owns shift_def/next_shift/briefing (overridden below), so the parent's Phase7 practice definitions are unused.
        super().__init__(db, shift=shift, practice=self.linux['practice'], seed=seed)
        if self.incident.practice != self.linux['practice']:
            raise ValueError('사건 연습 기록과 Linux 학습 기록이 일치하지 않습니다.')
        self._validate_learning()

    @staticmethod
    def _fingerprint():
        return curriculum.fingerprint() + ':' + catalog.fingerprint()

    def _has_shift(self, number):
        return number in curriculum.SHIFTS

    def _validate_learning(self):
        l = self.linux
        if type(l.get('seq')) is not int or l['seq'] < 0 or l.get('practice') not in (None, *curriculum.CASES):
            raise ValueError('학습 기록 형식이 올바르지 않습니다.')
        seen = set()
        for o in l.get('observations', []):
            if (not isinstance(o, dict) or o.get('command_id') not in catalog.BY_ID or
                    type(o.get('seq')) is not int or o['seq'] in seen or o['seq'] > l['seq'] or
                    o.get('incident') not in {r.id for r in self.incident.records}):
                raise ValueError('학습 관측 연결이 올바르지 않습니다.')
            seen.add(o['seq'])
        if not isinstance(l.get('interpretations'), list) or not isinstance(l.get('help'), list):
            raise ValueError('학습 해석·도움 기록이 올바르지 않습니다.')

    def _extra_payload(self):
        return {**super()._extra_payload(), 'linux': deepcopy(self.linux)}

    @contextmanager
    def _atomic(self):
        before = deepcopy(self.linux)
        try:
            with super()._atomic():
                yield
        except Exception:
            self.linux = before
            raise

    def shift_def(self, number=None):
        n = number or (self.global_.shift if hasattr(self, 'global_') else 1)
        return curriculum.shift_def(n, self.linux['practice'])

    def next_shift(self):
        n = self.global_.shift + 1
        return n if not self.linux['practice'] and n in curriculum.SHIFTS else None

    def shift_briefing(self):
        d = self.shift_def()
        return [('mentor' if self.global_.shift <= 2 else 'system', f'{d["title"]}\n역할: {d["role"]}'),
                ('mentor' if self.global_.shift == 1 else 'system', d['intro']),
                ('system', '클리어 조건: 모든 고객 업무 정상 종료 + 각 사건에서 보완적 CLI 증거 2종·출력 해석·원인 판단·승인된 대응·복구 뒤 새 관측·고객 보고. 명령 조회만으로 복구되지 않습니다. 가상 Linux이며 실제 컴퓨터에는 실행되지 않습니다.')]

    def token(self, rec):
        return f'{self.global_.shift}:{rec.id}:{rec.state}:{self.minute}:{self.linux["seq"]}'

    PRIVATE = ('eligible', 'status')

    @classmethod
    def public(cls, obs):
        """Client copy of an observation. Eligibility and the engine's incident-level probe status stay server-side:
        they follow one rule for every cause, and hiding them keeps any accidental difference from becoming a hint."""
        return {k: deepcopy(v) for k, v in obs.items() if k not in cls.PRIVATE}

    @staticmethod
    def choices(obs):
        spec = catalog.BY_ID[obs['command_id']]
        texts = [spec.correct, spec.wrong]
        if hashlib.sha256(f'{obs["incident"]}:{obs["seq"]}:{obs["command_id"]}'.encode()).digest()[0] % 2:
            texts.reverse()
        return [{'id': k, 'text': text} for k, text in zip(('a', 'b'), texts)]

    def cli(self, iid, line, node, token=None):
        rec = self._open(iid)
        if token is not None and token != self.token(rec):
            raise ValueError('오래된 화면입니다. 현재 사건·노드를 확인하고 다시 실행하세요.')
        try:
            out = result(self, rec, line, node)
        except catalog.CLIError as exc:
            return {'kind': 'error', 'code': exc.code, 'category': exc.category, 'output': str(exc)}
        if out['kind'] in ('help', 'clear'):
            return out
        with self._atomic():
            self.linux['seq'] += 1
            entry = {**out, 'seq': self.linux['seq'], 'incident': iid, 'node': node,
                     'line': line.strip(), 'minute': self.minute, 'after': rec.recovered is not None,
                     'incidentSeq': rec.seq, 'interpretation': None}
            self.linux['observations'].append(entry)
            # CLI is a simulated remote console on a selected node. BMS probes cannot
            # enter here. Site buttons for other probes are disabled in this subclass.
            entry['choices'] = self.choices(entry)
            if out['probe'] and out.get('eligible', True) and (not out.get('historical') or rec.recovered is None):
                probe = out['probe']
                # Node/target dependent probes become engine evidence only once the player compared the whole scope of
                # this request (same rule for every cause). The engine summary then states what those outputs showed.
                if not self.uncovered(rec, probe):
                    super().incident_observe(iid, probe, self.content.probes[probe]['location'])
        return self.public(entry)

    def interpret(self, iid, seq, answer, token=None):
        rec = self._open(iid)
        if token is not None and token != self.token(rec):
            raise ValueError('오래된 화면입니다. 현재 사건을 확인하고 다시 선택하세요.')
        obs = next((o for o in self.linux['observations'] if o['seq'] == seq and o['incident'] == iid), None)
        if obs is None:
            raise ValueError('이 사건에서 실제 실행한 관측을 선택하세요.')
        spec = catalog.BY_ID[obs['command_id']]
        choices = {c['id']: c['text'] for c in self.choices(obs)}
        if answer not in choices:
            raise ValueError('현재 관측의 해석 선택지를 골라 주세요.')
        correct = choices[answer] == spec.correct
        existing = next((x for x in self.linux['interpretations'] if x['seq'] == seq and x['incident'] == iid), None)
        if existing:
            # The first answer to an observation is final. Trying the other choice would turn the gate into guessing;
            # run the command again (a new observation) to answer again.
            return deepcopy(existing)
        with self._atomic():
            entry = {'incident': iid, 'seq': seq, 'answer': answer, 'correct': correct, 'minute': self.minute,
                     'feedback': ('관측의 범위에 맞는 해석입니다. 다른 계층은 추가 관측으로 확인하세요.' if correct else
                                  '관측 범위를 넘어선 추측입니다. ' + (spec.correct + '. ' if self.reveal_interpretation() else '') + '다른 도구로 추가 확인하세요.')}
            self.linux['interpretations'].append(entry)
            obs['interpretation'] = correct
        return deepcopy(entry)

    def reveal_interpretation(self):
        return self.global_.shift <= 2

    def incident_observe(self, iid, probe, location):
        if probe not in ('cooling', 'ups'):
            raise ValueError('이 근무의 Linux 증거는 내 모니터에서 명령을 실행해 수집하세요. BMS는 현장 계기를 사용합니다.')
        return super().incident_observe(iid, probe, location)

    def scope_of(self, rec, probe):
        """What must be compared for a node/target dependent probe: the request's storage and servers (ping,
        traceroute), its GPU servers (dcgm family) or their ToR uplink ports (tor_port). None = one reading suffices."""
        servers = job_servers(self, rec)
        if probe in ('ping', 'link_stats'):
            return {STORAGE_IP, *(server_ip(x) for x in servers)}
        if probe == 'dcgm':
            return {f'server-{x}' for x in servers}
        if probe == 'tor_port':
            return {port for port, rack in PORTS.items() if rack in servers}
        return None

    def uncovered(self, rec, probe):
        need = self.scope_of(rec, probe)
        if not need:
            return set()
        after = rec.recovered is not None
        # Same window as the engine's post-check: from 10 minutes after recovery while the job still runs.
        since = self.post_since(rec) if after else 0
        seen = {c for o in self.linux['observations'] if o['incident'] == rec.id and o.get('probe') == probe
                and o.get('eligible', True) and o['after'] == after and o['minute'] >= since
                for c in (o.get('covers') or [])}
        return need - seen

    def _proof(self, rec, after=False, cause=None):
        entries = [o for o in self.linux['observations'] if o['incident'] == rec.id and o.get('eligible', True) and
                   (not after or (o['after'] and o['minute'] >= rec.recovered and not o.get('historical')))]
        ids = {o['command_id'] for o in entries}
        rule = curriculum.CASES.get(cause or rec.type, {'groups': [['ping'], ['traceroute']]})
        return all(ids.intersection(group) for group in rule['groups'])

    def incident_hypothesis(self, iid, cause):
        rec = self._open(iid)
        # Same rejection for all causes: no oracle about the right diagnosis.
        if cause not in self.content.causes:
            raise ValueError('지원하지 않는 가설입니다.')
        if len({o['command_id'] for o in self.linux['observations'] if o['incident'] == iid}) < 2:
            raise ValueError('서로 다른 CLI 관측을 두 가지 이상 수집하세요. 한 출력만으로 원인을 확정할 수 없습니다.')
        if not any(x['incident'] == iid and x['correct'] for x in self.linux['interpretations']):
            raise ValueError('출력 한 가지에서 사실과 추측을 구분한 뒤 가설을 판단하세요.')
        if not self._proof(rec, cause=cause):
            raise ValueError('현재 관측만으로는 근거가 부족합니다. 다른 계층의 보완적 증거를 수집하세요.')
        partial = {p: self.uncovered(rec, p) for p in self.content.causes[cause]['probes']}
        partial = {p: left for p, left in partial.items() if left and any(
            o['incident'] == iid and o.get('probe') == p for o in self.linux['observations'])}
        if partial:
            # Depends only on the submitted cause and what was observed: never on the hidden cause.
            raise ValueError('영향 범위 전체를 비교해야 합니다. 아직 확인하지 않은 대상: '
                             + ', '.join(sorted({x for left in partial.values() for x in left}))
                             + ' — 한 노드·한 대상의 결과로 다른 노드를 판단하지 마세요.')
        return super().incident_hypothesis(iid, cause)

    def verify_blocker(self, rec):
        base = super().verify_blocker(rec)
        left = sorted(x for p in self.content.types[rec.type]['verify'] for x in self.uncovered(rec, p)) if rec.state == 'monitoring' else []
        if base and left and base.startswith('복구 뒤 다시 관측'):
            # The engine still lacks a post-check because part of the scope was not compared again.
            return base + ' · 영향 범위 중 아직 다시 확인하지 않은 대상: ' + ', '.join(left)
        if base:
            return base
        if not self._proof(rec, after=True):
            return '복구 뒤 보완적 CLI 지표 두 가지를 새로 조회하세요. 복구 전 출력·직전 컨테이너 보관 로그는 사후 검증이 아닙니다.'
        return ''

    def help_for(self, iid):
        rec = self._open(iid)
        with self._atomic():
            self.linux['help'].append({'incident': iid, 'minute': self.minute})
        # Process guidance, not the hidden cause or its exact commands.
        return '영향 범위를 확인하고 IP·이름·서비스·장치·저장공간을 분리해 보세요. 한 도구의 정상 결과로 다른 계층을 정상이라고 단정하지 마세요. help에는 허용 구문만 나옵니다.'

    def action_location(self, rec, action):
        group = self.content.actions.get(action, {}).get('group')
        if action == 'ask_consent':
            return 'noc'
        if action == 'ups_bypass':
            return 'UPS'
        if group == 'network':
            return 'NETWORK'
        if group in ('compute', 'storage'):
            return 'hall'
        if group == 'facility':
            return 'UPS' if rec.cause == 'ups' else 'COOLING'
        if group == 'platform':
            return 'noc'
        return None  # communication/escalation is possible at every site

    def incident_view(self, rec):
        view = super().incident_view(rec)
        if rec.state == 'investigating':
            view['why'] = ('내 모니터 Linux 탭에서 서로 다른 계층의 명령을 실행하고 출력의 의미를 해석하세요. '
                           '현장 BMS가 필요하면 해당 건물에서 별도로 확인합니다.')
        if self.global_.shift >= 3:
            view['hint'] = None
        return view

    def shift_result(self):
        base = super().shift_result()
        d = self.shift_def()
        ids = {r.id for r in self.shift_records()}
        entries = [o for o in self.linux['observations'] if o['incident'] in ids]
        interp = [x for x in self.linux['interpretations'] if x['incident'] in ids]
        independent = base['cleared'] and self.global_.shift == 5 and not self.linux['practice']
        base['linux'] = {'version': curriculum.VERSION, 'role': d['role'], 'rank': d['rank'] if base['cleared'] else '재훈련',
                         'graduated': independent, 'practice': bool(self.linux['practice']),
                         'observations': len(entries), 'commands': len({o['command_id'] for o in entries}),
                         'interpreted': sum(x['correct'] for x in interp), 'misinterpretations': sum(not x['correct'] for x in interp),
                         'help': sum(x['incident'] in ids for x in self.linux['help'])}
        if self.linux['practice']:
            base['linux']['rank'] = '연습 · 승급 없음'
        base['feedback'].append('Linux 학습: 조회 성공과 시스템 정상은 다릅니다. 보완적 증거·승인·사후 새 관측·고객 보고를 연결했습니다.' if base['cleared'] else '남은 사건과 승인·사후 확인 기록을 검토하고 새 슬롯으로 재훈련하세요.')
        return base

    def learning_view(self):
        d = self.shift_def()
        records = [r for r in self.shift_records() if r.state != 'armed']
        ids = {r.id for r in records}
        observations = [self.public(o) for o in self.linux['observations'] if o['incident'] in ids]
        # Catalog always contains every tool, never a cause-dependent command menu.
        specs = [{k: v for k, v in {**c.view(), 'example': catalog.example(c)}.items() if k not in ('correct', 'wrong', 'source_key')}
                 for c in catalog.COMMANDS]
        return {'version': curriculum.VERSION, 'catalogVersion': catalog.VERSION, 'shift': self.global_.shift,
                'shiftCount': len(curriculum.SHIFTS), 'title': d['title'], 'role': d['role'], 'inputMode': d['input'],
                'practice': self.linux['practice'], 'rank': d['rank'], 'maxLine': catalog.MAX_LINE,
                'commands': specs, 'arguments': catalog.ARGUMENTS, 'observations': observations[-120:],
                'interpretations': [deepcopy(x) for x in self.linux['interpretations'] if x['incident'] in ids][-120:],
                'contexts': {r.id: contexts(self, r) for r in records}, 'tokens': {r.id: self.token(r) for r in records},
                'actionLocations': {r.id: {a: self.action_location(r, a) for a in self.content.actions} for r in records if r.cause},
                'feedback': deepcopy(self.global_.result.get('linux')) if self.global_.result else None,
                'help': [deepcopy(x) for x in self.linux['help'] if x['incident'] in ids][-20:],
                'notice': '교육용 가상 Linux · 실제 OS/네트워크 실행 없음 · 수치·주소·컨테이너는 가상 설정 · BMS 조작은 시설 담당 화면'}
