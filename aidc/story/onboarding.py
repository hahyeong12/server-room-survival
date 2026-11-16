"""새 입문/첫 근무 진행. 기존 슬롯의 첫 업무 판정과 별도로 저장합니다."""
from dataclasses import dataclass, field

COUNTRIES = ('싱가포르', '일본', '미국')
STEPS = ('arrival', 'request', 'preview', 'allocation', 'time', 'complete')
# 화면 위쪽 목표 카드의 5단계(짧은 튜토리얼도 단계감 있게). 각 단계는 '지금 할 행동 하나'를 가리킵니다.
CARD_STEPS = (('arrival', '안내 확인'), ('request', '요청 확인'), ('preview', '배정 검토'),
              ('allocation', '작업 시작'), ('time', '시간 빨리감기'))
STEP_ACTIONS = {'arrival': '안내 창에서 [다음]을 눌러 시작하세요',
                'request': '[요청 확인]을 눌러 고객 조건과 기한을 읽으세요',
                'preview': '[배정 설정·선택]에서 운영 모드와 배정안을 고르세요',
                'allocation': '[배정 설정·선택] 창에서 배정안을 확인하고 [선택한 계획으로 작업 시작]을 누르세요',
                'time': '[⏩ 시간 빨리감기]로 작업을 끝까지 진행하세요'}
STEP_MENTOR = {'arrival': '천천히 해도 괜찮아요. 한 번에 한 단계씩만 해요.',
               'request': '고객이 원하는 자원과 기한부터 확인해요.',
               'preview': '고르기만 해서는 자원을 쓰지 않아요. 편하게 비교해 봐요.',
               'allocation': '좋아요. 이제 선택한 안으로 시작해요.',
               'time': '시간을 흘려보내면 진행률이 올라가요. 완료되면 자원이 돌아와요.'}
# 새 튜토리얼의 금색 강조 대상(관제실이 실제 위젯으로 바꿉니다)과 그 버튼 이름. 목표 카드 문구(STEP_ACTIONS)에는 그 단계에서
# 강조될 수 있는 모든 버튼 이름이 들어 있어야 합니다(QA tutorial-001 Q-04: 카드와 강조가 서로 다른 곳을 가리킴).
GUIDED_LABELS = {'arrival_button': '요청 확인', 'allocation_button': '배정 설정·선택', 'plan_card': '배정안',
                 'dialog_start': '선택한 계획으로 작업 시작', 'time_buttons': '시간 빨리감기'}


def guided_target(step, window_open=False, start_ready=False):
    """새 튜토리얼 단계에서 강조할 대상 이름(순수 함수). window_open: 배정 설정창이 열림, start_ready: 창의 시작 버튼 활성."""
    if step == 'request':
        return 'arrival_button'
    if step in ('preview', 'allocation'):
        if not window_open:
            return 'allocation_button'
        return 'dialog_start' if step == 'allocation' and start_ready else 'plan_card'
    if step == 'time':
        return 'time_buttons'
    return None


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
    def pages(self):
        """시작 대화(역할, 짧은 문장) 목록. 한 페이지에 한 가지 말만 합니다."""
        if self.done:
            return [('mentor', self.dialogue)]
        if self.step != 'arrival':
            return [('mentor', self.objective)]
        # 의미 단위로 줄을 나눕니다: 문장이 끝나면 새 줄, 화제가 바뀌면 빈 줄, 순서 안내는 항목마다 한 줄.
        if self.kind == 'tutorial':
            return [('mentor', '첫 출근을 환영해요!\n오늘은 고객 요청 하나를 처음부터 끝까지 처리해 볼 거예요.'),
                    ('player', '네, 잘 부탁드립니다!\n처음이라 조금 긴장되네요.'),
                    ('mentor', '순서는 네 단계예요.\n\n① 요청 확인\n② 배정 검토\n③ 작업 시작\n④ 시간 빨리감기'),
                    ('mentor', '화면 위쪽 목표 카드가 지금 할 일 하나만 알려 줘요.\n\n천천히 따라오세요.')]
        return [('mentor', '기본 조작은 익혔죠?\n오늘은 고객 세 곳의 업무를 한 건씩 맡아요.'),
                ('player', '세 곳이요?\n순서대로 하나씩 해 볼게요.'),
                ('mentor', '순서는 이렇습니다.\n\n① 싱가포르\n② 일본\n③ 미국\n\n앞 업무가 끝나고 자원이 돌아와야 다음 요청이 와요.'),
                ('mentor', '세 건을 정상 완료하면 다음 장으로 가요.\n\n위쪽 목표 카드를 따라가 보세요.')]

    @property
    def card(self):
        """목표 카드용 조회 전용 값: 단계 번호, 지금 할 행동 하나, 단계 표시. 게임 상태를 바꾸지 않습니다."""
        keys = [key for key, _ in CARD_STEPS]
        current = len(keys) if self.done else keys.index(self.step) if self.step in keys else len(keys)-1
        pips = [(name, 'done' if index < current else 'current' if index == current and not self.step == 'closed' else 'todo')
                for index, (_, name) in enumerate(CARD_STEPS)]
        key = keys[min(current, len(keys)-1)]
        return {'kind': self.kind, 'step_no': min(current+1, len(keys)), 'total': len(keys), 'done': self.done,
                'closed': self.step == 'closed', 'title': CARD_STEPS[min(current, len(keys)-1)][1],
                'action': '' if self.done else '요청이 종료되었습니다. 실패 결과를 확인하세요' if self.step == 'closed' else STEP_ACTIONS[key],
                'mentor': '' if self.done or self.step == 'closed' else STEP_MENTOR[key], 'pips': pips,
                'job': (len(self.request_ids), self.total) if self.kind == 'shift' else None}

    @property
    def dialogue(self):
        if self.step == 'arrival':
            return ('관제실 첫걸음입니다.\n고객 요청을 읽고 배정안을 고른 뒤 시간을 진행해 보세요.\n\n짧은 업무 한 건이면 입문이 끝납니다.'
                    if self.kind == 'tutorial' else
                    '기본 조작을 익힌 신입의 첫 근무입니다.\n싱가포르, 일본, 미국 고객의 업무를 한 건씩 맡아 주세요.\n\n'
                    '조건 확인부터 자원 반환까지 직접 마치면 다음 장으로 갑니다.')
        if self.done:
            return ('수고하셨습니다.\n\n이제 스토리 도전에서 첫 근무를 시작해 보세요.' if self.kind == 'tutorial' else
                    '세 업무를 마쳤습니다.\n\n다음 근무에는 고객 요청이 겹칩니다.\n제2장에서 한정된 자원을 나누는 판단을 시작합니다.')
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
