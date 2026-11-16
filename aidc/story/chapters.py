"""표시용 장 번호·이야기. 저장 ID와 엔진의 성공/실패 조건은 바꾸지 않습니다."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Chapter:
    key: int | str
    number: int
    title: str
    intro: str

    @property
    def label(self):
        return f'제{self.number}장'

    @property
    def heading(self):
        return f'{self.label} — {self.title}'


CHAPTERS = {
    1: Chapter(1, 1, '첫 근무', '기본 조작을 익힌 신입의 첫 근무입니다. 세 고객의 업무를 한 건씩 맡으며 운영의 흐름에 적응해 보세요.'),
    2: Chapter(2, 2, '한정된 자원', '두 고객의 요청이 겹쳤습니다. 한정된 서버와 서로 다른 약속 사이에서 운영 계획을 세워야 합니다.'),
    3: Chapter(3, 3, '끊어진 연결', '작업 도중 통신이 흔들립니다. 보이는 증상과 확인한 사실을 연결해 원인을 찾아보세요.'),
    '3b': Chapter('3b', 4, '서버실의 경보', '이번 경보는 서버실에서 울립니다. 장비 상태와 진행 중인 업무를 함께 살펴야 합니다.'),
    'lab': Chapter('lab', 5, '홀로 선 엔지니어', '선배의 안내가 조금씩 줄어듭니다. 구조를 관찰하고 명령으로 조사하며 판단의 근거를 쌓아보세요.'),
}


def current_chapter(story):
    for key, field in (('lab', 'training'), ('3b', 'chapter3b'), (3, 'chapter3'), (2, 'chapter2')):
        if getattr(story, field) is not None:
            return CHAPTERS[key]
    return CHAPTERS[1]


def chapter_from_payload(story):
    for key, field in (('lab', 'training'), ('3b', 'chapter3b'), (3, 'chapter3'), (2, 'chapter2')):
        if isinstance(story.get(field), dict):
            return CHAPTERS[key]
    return CHAPTERS[1]


def heading(session):
    if session.mode == 'tutorial':
        return '튜토리얼 — 관제실 첫걸음'
    chapter = current_chapter(session.story)
    return chapter.heading + (' · 연습' if session.story.practice else '')


def chapter_state(session):
    """조회 전용. 안내 완료와 실제 클리어를 구분하고 기존 판정을 재사용합니다."""
    story = session.story
    chapter = current_chapter(story)
    if chapter.key == 'lab':
        return ('cleared', '학습 과제 1~5 통과') if story.training.done else ('in_progress', session.training_objective())
    if chapter.key == 1:
        if story.intro_active:
            if story.onboarding.done:
                return 'cleared', f'고객 업무 {story.onboarding.total}건 정상 완료'
            if story.onboarding.step == 'closed':
                run = session.runs[story.onboarding.rid]
                return 'failed', ('고객 요청을 거절했습니다.' if run.request['status'] == 'rejected' else
                                  run.state.result_text or '고객 요청이 정상 완료되지 않았습니다.')
            return 'in_progress', story.onboarding.objective
        if story.chapter_completed:
            return 'cleared', '첫 고객 업무 정상 완료'
        if story.mission_status == 'closed':
            run = session.runs[story.request_id]
            if run.request['status'] == 'rejected':
                return 'failed', '고객 요청을 거절하여 첫 업무가 종료되었습니다.'
            return 'failed', run.state.result_text or '첫 고객 요청을 정상 완료하지 못했습니다.'
        return 'in_progress', session.story_objective()
    if chapter.key == 2 and story.chapter2.failure:
        return 'failed', '고객 요청의 거절·만료·기한 초과 또는 처리 실패가 확정되었습니다.'
    if story.ui_done:
        result = {2: session.chapter2_result, 3: session.chapter3_result, '3b': session.chapter3b_result}[chapter.key]()
        return ('cleared', '이 장의 미션을 성공했습니다.') if result['mission'] == 'success' else ('failed', '이 장의 미션 성공 조건을 충족하지 못했습니다.')
    return 'in_progress', session.story_objective()


STATE_LABELS = {'in_progress': '진행 중', 'cleared': '클리어', 'failed': '실패'}
