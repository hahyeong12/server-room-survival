"""Two finite senior evaluations, using the existing incident/CLI/contract engines."""
from copy import deepcopy
import hashlib
import json

from aidc.learning.linux_session import LinuxSession
from aidc.learning import linux_curriculum, linux_catalog
from aidc.learning.career import assess, FINGERPRINT as ASSESSMENT_FINGERPRINT
from aidc.incidents.operating_rules import OperatingRules, FINGERPRINT

SHIFTS = {
    1: {'title': '선임 평가 1 · 계약과 공유 자원', 'role': '담당 엔지니어 · 선임 평가',
        'cases': ['dns', 'gpu_oom', 'storage_full'],
        'arrivals': [[0, 'sin-merbau-research'], [0, 'bom-marine-batch'], [110, 'sfo-bayfog-video']],
        'intro': '연구 배치와 유연형 추론이 공유 자원을 사용합니다. 계약을 지키며 두 작업의 이상을 구분하고, 후속 영상 작업까지 처리하세요. 원인과 명령은 직접 선택합니다.'},
    2: {'title': '선임 평가 2 · 동시 사건과 팀 조정', 'role': '담당 엔지니어 · 최종 교대',
        'cases': ['crashloop', 'storage_latency', 'congestion'],
        'arrivals': [[0, 'tyo-tsukiji-vision'], [0, 'osa-naniwa-batch'], [100, 'bom-marine-batch']],
        'intro': '서비스 반복 종료와 I/O 지연이 겹칩니다. 담당팀 승인·출력 해석·고객 소통으로 우선순위를 정하고 뒤이어 접수되는 회선 문제까지 검증하세요. 모든 업무를 끝내면 최종 동료 평가가 나옵니다.'},
}


class SeniorSession(OperatingRules, LinuxSession):
    SAVE_MODE = 'senior'
    MODES = LinuxSession.MODES + ('senior',)
    SHIFT_COUNT = 2

    def __init__(self, db, shift=1, seed=None):
        super().__init__(db, shift=shift, seed=seed)

    @staticmethod
    def _fingerprint():
        definition = json.dumps(SHIFTS, sort_keys=True, ensure_ascii=False)
        return 'senior-v1:' + ASSESSMENT_FINGERPRINT + ':' + FINGERPRINT + ':' + hashlib.sha256(definition.encode()).hexdigest() + ':' + linux_curriculum.fingerprint() + ':' + linux_catalog.fingerprint()

    def _has_shift(self, number):
        return number in SHIFTS

    def shift_def(self, number=None):
        n = number or (self.global_.shift if hasattr(self, 'global_') else 1)
        if n not in SHIFTS:
            raise ValueError('선임 평가는 1~2교대입니다.')
        spec = deepcopy(SHIFTS[n])
        return {**spec, 'code': f'S{n}', 'subtitle': spec['role'], 'input': 'terminal', 'coaching': 'none',
                'rank': '선임 평가 중', 'incidents': [[i, t, 0.2] for i, t in enumerate(spec['cases'])],
                'goal': {'minSuccess': 3, 'minResolved': 3, 'maxExpired': 0, 'notifyBeforeRecovery': True}}

    def next_shift(self):
        return 2 if self.global_.shift == 1 else None

    def reveal_interpretation(self):
        return False

    def shift_briefing(self):
        d = self.shift_def()
        return [('system', f'{d["title"]}\n역할: {d["role"]}\n{d["intro"]}'),
                ('system', '통과: 고객 3건 기한 내 완료·사건 3건 복구 검증/보고·복구 전 고객 안내·운영/학습 각각 70점 이상·안전 정책 위반 시도 없음. 실제 OS를 조작하지 않는 가상 평가입니다.')]

    def incident_view(self, rec):
        view = super().incident_view(rec)
        view['hint'] = None
        return view

    def learning_view(self):
        view = super().learning_view()
        view.update(shiftCount=2, rank='직무 평가 · 교육 수료와 별도')
        return view

    def shift_result(self):
        result = super().shift_result()
        evaluation = assess(self)
        scores_ok = all(evaluation[k]['score'] is not None and evaluation[k]['score'] >= 70 for k in ('operations', 'learning'))
        result['cleared'] = (result['cleared'] and all(r['outcome'] == 'on_time' for r in result['rows'])
                             and scores_ok and not evaluation['unsafe'])
        result['assessment'] = evaluation
        result['senior'] = {'version': 1, 'role': '선임 엔지니어' if result['cleared'] and self.global_.shift == 2 else '담당 엔지니어',
                            'ending': result['cleared'] and self.global_.shift == 2,
                            'qualification': '독립 관제 엔지니어 (기존 교육 수료 기록 보존)'}
        result['linux'].update(graduated=False, rank='직무 평가 · 기존 Linux 수료와 별도')
        result['feedback'].append('운영과 학습 각각 70점 이상, 기한 내 완료와 안전 정책을 함께 충족했습니다.' if result['cleared'] else
                                  '기한·복구 전 고객 안내·두 평가 항목·안전 규칙을 확인하고 새 슬롯에서 다시 도전하세요. 결과의 항목별 근거로 전략을 바꿀 수 있습니다.')
        return result
