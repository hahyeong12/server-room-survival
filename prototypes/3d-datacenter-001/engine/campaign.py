"""Read-only campaign views for the 3D client (Issue #6, Phase 5).

Every value here comes from the existing Python engine (session.GameSession, StoryProgress, the chapter
progress classes, TrainingProgress and the Engineering Lab model). Nothing in this module changes a session,
a ledger, a save or a score; it only selects and serialises what the engine already decided.

Chapter keys are the engine's internal ids (1, 2, 3, '3b', 'lab'); the client shows the player-facing
number/title from aidc.story.chapters.CHAPTERS (제1장 … 제5장).
"""
from __future__ import annotations

import dataclasses
from copy import deepcopy

from aidc.story.chapters import CHAPTERS, current_chapter, chapter_state, STATE_LABELS
from aidc.story.chapter2 import is_finished
from aidc.story.chapter3 import mission_over
from aidc.learning.lab_model import observe, LAB_NETWORK, LAB_NOTICE, job_symptom
from aidc.learning.lab_terminal import COMMAND_SPECS, BLOCKS, CHOICE_QUESTION, CHOICE_FIT, SUPPORTED
from aidc.learning.training import STAGES, STAGE_INFO, QUESTIONS
from story import SPEAKERS, chapter2_failure_pages, chapter3_feedback_pages

ORDER = (1, 2, 3, '3b', 'lab')
FIELDS = {2: 'chapter2', 3: 'chapter3', '3b': 'chapter3b', 'lab': 'training'}
# Display-only: the label a cleared campaign earns. It names the engine's own verdict (all five chapters
# cleared in one regular save); it is not a new score and has no formula.
GRADUATION = {'title': '운영 엔지니어 수료', 'note': '교육용 가상 등급 · 실제 자격이 아닙니다',
              'from': '신입 엔지니어 · 운영석 03'}


def jsonable(value):
    """Engine results hold tuples, dataclasses and int keys; make them plain JSON without changing values."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return jsonable(dataclasses.asdict(value))
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [jsonable(v) for v in value]
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


def chapter_meta(chapter, practice=False):
    return {'key': chapter.key, 'number': chapter.number, 'label': chapter.label, 'title': chapter.title,
            'heading': chapter.heading + (' · 연습' if practice else ''), 'intro': chapter.intro}


def pages(dialogue):
    return [[d.role, SPEAKERS.get(d.role, d.role), _player_words(d.text)] for d in dialogue]


def _field(story, key):
    return getattr(story, FIELDS[key]) if key in FIELDS else None


def unlock_reason(session, key):
    """Why the next chapter cannot start yet ('' = it can). The engine's own unlock checks where they exist;
    Chapter 2 has none, so this mirrors start_chapter2's guards for display only (starting re-checks in the engine)."""
    story = session.story
    if session.mode != 'story' or story is None:
        return '스토리 도전에서만 장을 이어서 시작할 수 있습니다.'
    if story.practice:
        return '연습 저장은 진급 기록이 아닙니다. 다음 장은 정규 스토리 저장에서만 이어집니다.'
    if key == 2:
        if story.chapter2 is not None:
            return '이미 제2장을 시작했습니다.'
        return '' if story.chapter1_cleared else '제1장의 세 업무를 정상 완료한 뒤 제2장을 시작할 수 있습니다.'
    reason = {3: session.chapter3_unlock_reason, '3b': session.chapter3b_unlock_reason,
              'lab': session.training_unlock_reason}[key]()
    return _player_words(reason)


# The engine text names Tkinter screens and internal chapter ids. The 3D client shows the same sentence with the
# 3D place names and player-facing chapter numbers (wording only: no meaning, number or verdict changes).
WORDS = (
    ('Chapter 3b', '제4장'), ('Chapter 3a(네트워크 장애)', '제3장'), ('Chapter 3a', '제3장'), ('Chapter 3', '제3장'),
    ('Chapter 2', '제2장'), ('Chapter 1', '제1장'),
    ('AIDC LINK의 [요청 확인]', '내 모니터 요청함의 [요청서 열기]'), ('AIDC LINK에서', '내 모니터 요청함에서'),
    ('AIDC LINK', '내 모니터 요청함'),
    ('[배정 계획 비교·선택]', '[배정 계획] 탭'), ('[배정 설정·선택]', '[배정 계획] 탭 → 서버동 랙의 [작업 시작]'),
    ('[Engineering Lab 연습]', '메뉴의 [장 연습 · 제5장 Lab]'), ('[Engineering Lab]', '[연수 · Lab] 탭'),
    ('Engineering Lab에서', '[연수 · Lab] 탭에서'), ('(Engineering Lab)', '([연수 · Lab] 탭)'),
    ('[네트워크 구조] 탭', '[연수 · Lab] 탭의 구조도'), ('[명령어 학습] 탭', '[연수 · Lab] 탭'),
    ('[가상 터미널] 탭', '[연수 · Lab] 탭의 터미널'), ('[가상 터미널]', '[연수 · Lab] 탭의 터미널'),
    ('관제실의 기존 대응 버튼', '내 모니터 [진단] 탭의 대응 버튼'), ('관제실에서', '내 모니터 [진단] 탭에서'),
    ('시간 빨리감기(+10/+30/+60분)', '위쪽 ⏩ 시간 버튼(+10/+30/+60분)'), ('시간 빨리감기', '위쪽 ⏩ 시간 버튼'),
)


def _player_words(text):
    if not isinstance(text, str):
        return text
    for old, new in WORDS:
        text = text.replace(old, new)
    return text


def words_deep(value):
    """Apply the 3D wording to every string inside an engine result (lists / dicts)."""
    if isinstance(value, str):
        return _player_words(value)
    if isinstance(value, list):
        return [words_deep(v) for v in value]
    if isinstance(value, dict):
        return {k: words_deep(v) for k, v in value.items()}
    return value


def next_key(key):
    index = ORDER.index(key)
    return ORDER[index + 1] if index + 1 < len(ORDER) else None


def campaign(session):
    """Chapter list for the regular story: locked / available / in_progress / cleared / failed (engine verdicts)."""
    story = session.story
    if session.mode != 'story' or story is None or story.practice:
        return []
    current = current_chapter(story).key
    state, text = chapter_state(session)
    out = []
    for key in ORDER:
        chapter = CHAPTERS[key]
        row = chapter_meta(chapter)
        started = key == 1 or _field(story, key) is not None
        if key == current:
            row.update(state=state, stateLabel=STATE_LABELS[state], text=_player_words(text))
        elif started:
            # An earlier chapter that a later one followed: the engine only unlocks after a success.
            row.update(state='cleared', stateLabel=STATE_LABELS['cleared'], text='다음 장으로 진급한 기록')
        else:
            reason = unlock_reason(session, key) if key == next_key(current) and state == 'cleared' else (
                f'{CHAPTERS[ORDER[ORDER.index(key) - 1]].label}을(를) 클리어하면 열립니다.')
            row.update(state='available' if not reason else 'locked', stateLabel='시작 가능' if not reason else '잠김',
                       text=reason or '이 저장에서 바로 시작할 수 있습니다.')
        out.append(row)
    return out


def objective(session):
    story = session.story
    return _player_words(session.story_objective() if story else '')


def jobs_progress(session):
    """(done, total) for the strip. Chapter 1 counts customer jobs, chapters 2-4 count their two requests,
    the Lab counts passed stages. Values come from the engine's progress objects."""
    story = session.story
    key = current_chapter(story).key
    if key == 1:
        intro = story.onboarding
        return (len(intro.completed), intro.total) if intro else (int(bool(story.chapter_completed)), 1)
    if key == 2:
        return sum(1 for rid in story.chapter2.request_ids if is_finished(session.runs[rid])), 2
    if key in (3, '3b'):
        progress = story.chapter3 if key == 3 else story.chapter3b
        return sum(1 for rid in progress.request_ids if mission_over(session.runs[rid])), 2
    return story.training.completed_count, len(STAGES)


def chapter_result(session, key):
    fn = {1: session.chapter_result, 2: session.chapter2_result, 3: session.chapter3_result,
          '3b': session.chapter3b_result, 'lab': session.training_result}[key]
    return words_deep(jsonable(fn()))


def chapter2_view(session):
    story = session.story
    c2 = story.chapter2
    view = {'requestIds': list(c2.request_ids), 'step': c2.step, 'completed': c2.completed,
            'comparison': session.chapter2_comparison_lines(),
            'briefing': {str(rid): session.chapter2_briefing_lines(session.runs[rid]) for rid in c2.request_ids},
            'jobs': {str(rid): list(session.chapter2_job_state(session.runs[rid])) for rid in c2.request_ids},
            'evaluation': session.chapter2_evaluation_lines(),
            'failure': jsonable(deepcopy(c2.failure)), 'failurePending': session.chapter2_failure_pending,
            'failurePages': pages(chapter2_failure_pages(c2.failure)) if c2.failure else [],
            'retryAvailable': session.chapter2_retry_available}
    return view


def chapter3_view(session):
    c3 = session.story.chapter3
    pending = session.chapter3_pending_feedback()
    feedback = session.chapter3_feedback()
    return {'requestIds': list(c3.request_ids), 'step': c3.step, 'completed': c3.completed,
            'diagnosed': list(c3.diagnosed), 'records': jsonable(c3.records),
            'cards': {str(rid): words_deep(jsonable(session.chapter3_card(rid))) for rid in c3.request_ids},
            'pending': ({'key': pending[0], 'kind': pending[1], 'rid': int(pending[0].split(':')[0]),
                         'pages': pages(feedback[1]) if feedback else []} if pending else None),
            'retryAvailable': session.chapter3_retry_available}


def chapter3b_view(session):
    c = session.story.chapter3b
    pending = session.chapter3b_pending_feedback()
    return {'requestIds': list(c.request_ids), 'step': c.step, 'completed': c.completed,
            'diagnosed': list(c.diagnosed), 'records': jsonable(c.records),
            'cards': {str(rid): words_deep(jsonable(session.chapter3b_card(rid))) for rid in c.request_ids},
            'pending': {'key': pending, 'rid': int(pending.split(':')[0])} if pending else None,
            'retryAvailable': session.chapter3b_retry_available}


def _segments_visible(t):
    """The Python Lab hides DOWN marks until Stage 1 is passed, and Stage 5 forbids reading the fault position
    from the structure map before the player's own cause decision. Same rule here."""
    if 'structure' not in t.completed:
        return False
    return not (t.current == 'independent' and not t.done and not t.answered('independent', 'cause', t.rid))


def training_view(session):
    t = session.story.training
    status = session.training_status()
    obs = observe(session, t.rid)
    visible = _segments_visible(t)
    questions = {f'{stage}:{question}': {'prompt': q['prompt'], 'options': [list(o) for o in q['options']]}
                 for (stage, question), q in QUESTIONS.items()}   # the 'correct' key is never sent
    return {
        'status': words_deep(jsonable(status)), 'objective': objective(session),
        'jobStatus': words_deep(jsonable(session.training_job_status())),
        'stages': [{'key': k, 'no': STAGE_INFO[k]['no'], 'title': STAGE_INFO[k]['title'], 'short': STAGE_INFO[k]['short'],
                    'goal': STAGE_INFO[k]['goal'], 'cta': STAGE_INFO[k]['cta'], 'tab': STAGE_INFO[k]['tab']} for k in STAGES],
        'questions': questions, 'choiceQuestion': CHOICE_QUESTION, 'choices': list(COMMAND_SPECS),
        'choiceFit': {k: list(v) for k, v in CHOICE_FIT.items()},
        'specs': jsonable(COMMAND_SPECS), 'blocks': jsonable(BLOCKS), 'supported': list(SUPPORTED),
        'targets': {'routers': {k: v['address'] for k, v in LAB_NETWORK['routers'].items()},
                    'gateway': LAB_NETWORK['aidc_gateway']['address'], 'servers': dict(LAB_NETWORK['servers'])},
        'prompt': f'{LAB_NETWORK["user"]}@{LAB_NETWORK["host"]}:~$', 'hostLabel': LAB_NETWORK['host_label'],
        'notice': LAB_NOTICE,
        'network': {'segments': ({k: v for k, v in obs.network.segments.items()} if visible
                                 else {k: None for k in obs.network.segments}),
                    'revealed': visible, 'symptom': job_symptom(obs),
                    'phaseLabel': obs.phase_label, 'tone': obs.tone, 'progress': round(obs.progress, 1)},
        'unsupported': ['traceroute', 'ss', 'systemctl', 'nvidia-smi', 'journalctl', 'tcpdump'],
    }


def story_view(session, path):
    """The `story` part of the snapshot for every chapter. Chapter 1 keeps the Phase 4 fields unchanged."""
    from aidc.storage.checkpoints import checkpoint_path
    story = session.story
    intro = story.onboarding
    if session.mode == 'tutorial':
        state = 'cleared' if intro and intro.done else 'in_progress'
        chapter = {'key': 'tutorial', 'number': 0, 'label': '튜토리얼', 'title': '관제실 첫걸음',
                   'heading': '튜토리얼 — 관제실 첫걸음', 'intro': '', 'state': state,
                   'stateLabel': STATE_LABELS.get(state, state), 'text': ''}
        key = 1
    else:
        chap = current_chapter(story)
        key = chap.key
        state, text = chapter_state(session)
        chapter = {**chapter_meta(chap, story.practice), 'state': state, 'stateLabel': STATE_LABELS.get(state, state),
                   'text': _player_words(text)}
    ch1 = key == 1
    done, total = jobs_progress(session)
    event = story.dialogue_event
    view = {
        # Phase 4 (chapter 1) fields — kept as they were for chapter 1 and the tutorial.
        'kind': intro.kind if intro else None,
        'step': (intro.step if intro else story.step) if ch1 else story.ui_step,
        'card': intro.card if intro and ch1 else None,
        'objective': (intro.objective if intro else story.objective) if ch1 else objective(session),
        'pages': [list(p) for p in intro.pages] if intro and ch1 and intro.step == 'arrival' else [],
        'done': bool(intro and intro.done) if ch1 else bool(story.ui_done),
        'jobsDone': done, 'jobsTotal': total,
        'chapter': chapter, 'result': None,
        # Phase 5 fields.
        'chapterKey': key, 'uiStep': story.ui_step, 'practice': bool(story.practice),
        'dialogue': {'event': event, 'seen': event in story.dialogue_seen, 'pages': pages(story.dialogue)},
        'campaign': campaign(session),
        'next': None, 'retry': None, 'graduation': None,
        'chapter2': chapter2_view(session) if story.chapter2 is not None and key == 2 else None,
        'chapter3': chapter3_view(session) if story.chapter3 is not None and key == 3 else None,
        'chapter3b': chapter3b_view(session) if story.chapter3b is not None and key == '3b' else None,
        'training': training_view(session) if story.training is not None and key == 'lab' else None,
    }
    finished = view['done'] if ch1 else bool(story.ui_done)
    if finished:
        view['result'] = chapter_result(session, key)
    if session.mode == 'story' and not story.practice:
        nxt = next_key(key)
        if nxt is not None and state == 'cleared':
            reason = unlock_reason(session, nxt)
            view['next'] = {**chapter_meta(CHAPTERS[nxt]), 'available': not reason, 'reason': reason}
        has_checkpoint = path is not None and checkpoint_path(path, key).is_file()
        view['retry'] = {'available': has_checkpoint, 'kind': 'checkpoint',
                         'reason': '' if has_checkpoint else '이 저장에는 현재 장의 시작 기록(체크포인트)이 없습니다.'}
        if key == 'lab' and state == 'cleared':
            view['graduation'] = graduation(session)
    elif session.mode == 'story' and story.practice:
        view['retry'] = {'available': key in (2, 3, '3b', 'lab'), 'kind': 'practice', 'reason': ''}
    else:
        view['retry'] = {'available': True, 'kind': 'tutorial', 'reason': ''}
    return view


def graduation(session):
    """Final summary of a fully cleared regular campaign: each chapter's own engine result, nothing recomputed."""
    rows = []
    for key in ORDER:
        # Chapter 1 of an onboarding save: the three-job shift summary (read-only engine method).
        result = (jsonable(session._onboarding_result()) if key == 1 and session.story.onboarding
                  else chapter_result(session, key))
        line = {1: lambda r: f'평균 운영 점수 {r["score"]}점 · 세 고객 정상 완료',
                2: lambda r: f'종합 평가 {r["overall"]:g}/100 · 두 고객 기한 내 완료' if r.get('overall') is not None else '미션 성공',
                3: lambda r: ' · '.join(f'{j["kind_label"]} → {", ".join(j["responses"])}' for j in r['jobs']),
                '3b': lambda r: ' · '.join(f'{j["country"]} {"/".join(j["choices"])}' for j in r['jobs']),
                'lab': lambda r: f'Stage {len(r["rows"])}개 통과 · 사건 재접수 {r["restarts"]}회'}[key](result)
        rows.append({**chapter_meta(CHAPTERS[key]), 'line': line})
    return {**GRADUATION, 'rows': rows, 'learned': [
        '고객 조건·동의를 지키며 GPU와 전력을 서버별로 배정한다',
        '한정된 자원에서 기한과 운영 모드를 비교해 계획한다',
        '네트워크 증상과 진단 결과를 구분하고 원인에 맞게 조치한다',
        '서버 장애에서 복구와 이전을 자원·시간으로 비교한다',
        '관측 → 판단 → 조치 → 재확인을 스스로 끝까지 진행한다']}
