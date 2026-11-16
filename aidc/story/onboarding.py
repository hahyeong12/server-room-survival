"""새 입문/첫 근무 진행. 기존 슬롯의 첫 업무 판정과 별도로 저장합니다."""
from dataclasses import dataclass, field

COUNTRIES = ('싱가포르', '일본', '미국')
STEPS = ('arrival', 'request', 'preview', 'allocation', 'time', 'complete')
EVENTS = tuple(f'intro_{kind}_{n}_{step}' for kind in ('tutorial', 'shift')
               for n in range(1, 4) for step in (*STEPS, 'closed'))


@dataclass
class OnboardingProgress:
    kind: str
    request_ids: list[int] = field(default_factory=list)
    introduced: bool = False
    read: list[int] = field(default_factory=list)
    reviewed: list[int] = field(default_factory=list)
    completed: list[int] = field(default_factory=list)
    step: str = 'arrival'

    def __post_init__(self):
        if self.kind not in ('tutorial', 'shift') or type(self.introduced) is not bool:
            raise ValueError('입문 진행 구분이 올바르지 않습니다.')
        for values in (self.request_ids, self.read, self.reviewed, self.completed):
            if not isinstance(values, list) or any(type(v) is not int or v < 1 for v in values) or len(set(values)) != len(values):
                raise ValueError('입문 요청 이력이 올바르지 않습니다.')
        if (len(self.request_ids) > self.total or self.step not in (*STEPS, 'closed')
                or not set(self.read + self.reviewed + self.completed) <= set(self.request_ids)
                or self.completed != self.request_ids[:len(self.completed)]
                or (self.done and len(self.completed) != self.total)):
            raise ValueError('입문 단계와 업무 이력이 일치하지 않습니다.')

    @property
    def total(self):
        return 1 if self.kind == 'tutorial' else 3

    @property
    def rid(self):
        return self.request_ids[-1] if self.request_ids else None

    @property
    def done(self):
        return self.step == 'complete'

    @property
    def event(self):
        return f'intro_{self.kind}_{max(1, len(self.request_ids))}_{self.step}'

    @property
    def objective(self):
        prefix = '짧은 입문' if self.kind == 'tutorial' else f'첫 근무 · 업무 {len(self.request_ids)}/{self.total}'
        text = {'arrival': '근무 안내를 확인하고 시작하세요.', 'request': '고객 요청에서 조건과 기한을 확인하세요.',
                'preview': '배정 설정에서 운영 모드와 서버 배정안을 선택하세요.',
                'allocation': '선택한 배정으로 작업을 시작하세요.',
                'time': '시간을 빠르게 진행해 다음 상황을 확인해 보세요.',
                'complete': '업무 완료 · 결과를 확인하세요.', 'closed': '요청 종료 · 실패 원인과 재도전 방법을 확인하세요.'}[self.step]
        return prefix + ' — ' + text

    @property
    def dialogue(self):
        if self.step == 'arrival':
            return ('관제실 첫걸음입니다. 고객 요청을 읽고 배정안을 고른 뒤 시간을 진행해 보세요. 짧은 업무 한 건이면 입문이 끝납니다.'
                    if self.kind == 'tutorial' else
                    '기본 조작을 익힌 신입의 첫 근무입니다. 싱가포르, 일본, 미국 고객의 업무를 한 건씩 맡아 주세요. 조건 확인부터 자원 반환까지 직접 마치면 다음 장으로 갑니다.')
        if self.done:
            return '수고하셨습니다. 이제 스토리 도전에서 첫 근무를 시작해 보세요.' if self.kind == 'tutorial' else '세 업무를 마쳤습니다. 다음 근무에는 고객 요청이 겹칩니다. 제2장에서 한정된 자원을 나누는 판단을 시작합니다.'
        return self.objective

    def update(self, runs):
        if not self.request_ids:
            return
        run = runs[self.rid]
        if run.request['status'] == 'completed' and run.state.succeeded:
            if self.rid not in self.completed:
                self.completed.append(self.rid)
            self.step = 'complete' if len(self.completed) == self.total else 'time'
        elif run.request['status'] == 'rejected' or (run.state.phase == 'finished' and run.followup_closed):
            self.step = 'closed'
        elif not self.introduced:
            self.step = 'arrival'
        elif run.state.allocated:
            self.step = 'time'
        elif self.rid not in self.read:
            self.step = 'request'
        elif self.rid not in self.reviewed:
            self.step = 'preview'
        else:
            self.step = 'allocation'
