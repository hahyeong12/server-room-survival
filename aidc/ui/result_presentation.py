"""결과창용 읽기 전용 요약. 확정 기록이 없는 원인은 추정하지 않습니다."""
from result_summary import outcome_key


def failure_explanation(result=None, run=None):
    if run is not None:
        key = outcome_key(run)
        who = run.mission['company_name']
        fact = run.state.result_text
        record = {}
    else:
        result = result or {}
        record = result.get('failure') or {}
        failed = next((j for j in result.get('jobs', []) if not j.get('success', j.get('state') == 'success')), {})
        job = failed.get('job', failed)
        key = record.get('reason') or job.get('key') or ('late' if job.get('on_time') is False else
                 'expired' if job.get('expired') else 'rejected' if job.get('outcome') == '거절' else 'failed')
        who = record.get('company') or failed.get('company', '고객')
        fact = ''
        if not record:
            record = failed.get('record') or {}
            choices = failed.get('choices') or failed.get('responses')
            if choices:
                fact = '선택한 대응: ' + ' → '.join(choices) + f' · 중단 {failed.get("downtime", 0)}분'
    messages = {
        'rejected': ('고객 요청을 거절했습니다.', '요청을 거절하여 정상 처리 목표를 달성하지 못했습니다.',
                     '다음에는 고객 조건과 배정 가능 여부를 확인한 뒤 수락 여부를 결정하세요.'),
        'expired': ('배정 기한 안에 작업을 시작하지 못했습니다.', '최종 배정 기한까지 미배정 상태로 남아 요청이 만료되었습니다.',
                    '완료 기한과 예상 처리 시간을 비교하고, 자원이 반환되면 대기 요청을 다시 확인하세요.'),
        'late': ('작업은 끝났지만 완료 기한을 넘겼습니다.', '실제 완료 시각이 고객에게 약속한 기한보다 늦었습니다.',
                 '대기·처리·복구에 필요한 시간을 함께 계산하고, 허용된 모드와 대응을 비교하세요.'),
        'failed': ('고객 작업을 정상 완료하지 못했습니다.', '작업이 실패하거나 처리 불가 보고로 종료되었습니다.',
                   '진단에서 확인한 원인과 대응 결과를 비교하고, 조치 뒤 작업이 재개됐는지 확인하세요.'),
    }
    headline, why, next_step = messages.get(key, messages['failed'])
    blocker, after = record.get('blocker'), record.get('after')
    if blocker:
        why += f' {blocker["company"]}의 배정이 필요한 자원을 점유했습니다.'
        if blocker.get('placement'):
            why += ' 총량뿐 아니라 서버별 배정 위치가 제약이었습니다.'
    elif after:
        why += f' {after["company"]}의 작업 완료({after["completed"]}) 뒤에 시작했습니다.'
    if record.get('late_minutes') is not None and key == 'late':
        why += f' 기한을 {record["late_minutes"]}분 넘겼습니다.'
    if fact:
        why += ' ' + fact
    return {'headline': f'{who} · {headline}', 'cause': headline, 'why': why, 'next': next_step}


def result_actions(retry, select_chapter, select_mode, retry_label='체크포인트부터 다시 도전'):
    entries = [('retry', retry_label, retry)] if retry else []
    if select_chapter:
        entries.append(('chapters', '장 선택', select_chapter))
    entries.append(('modes', '메인 메뉴', select_mode))
    return entries


def success_tiles(result):
    """성공 결과의 큰 타일 3개 (이름, 값, 색 역할). 실제 결과 기록에서 읽은 값만 씁니다."""
    on_time = result.get('on_time')
    deadline = ('기한 내 완료', 'green') if on_time is True else ('기한 초과', 'red') if on_time is False else ('평가 제외', 'gray')
    return [('운영 점수', f'{result["score"]}점', 'green'), ('완료 기한', deadline[0], deadline[1]),
            ('반환 자원', f'GPU {result["gpu"]} · 전력 {result["power"]}', 'cyan')]


def success_headline(result, tutorial=False):
    jobs = result.get('jobs')
    if tutorial:
        return '입문 완료 · 기본 흐름을 익혔습니다'
    if jobs and len(jobs) > 1:
        return f'첫 근무 완료 · 고객 업무 {len(jobs)}건 정상 처리'
    return '업무 완료 · 고객 작업을 마치고 자원을 반환했습니다'


def success_mentor_lines(tutorial=False):
    """짧은 선배 한마디(문장 두 개 이하)."""
    if tutorial:
        return ['요청 확인 → 배정 → 시간 진행 → 완료. 이 흐름이 모든 업무의 기본입니다.']
    return ['조건을 확인하고 배정한 뒤 끝까지 진행했습니다. 쓴 자원이 모두 돌아왔는지가 마무리입니다.']


def complete_actions(tutorial, start_next, next_label, retry, select_chapter, select_mode, failed=False, practice=False):
    """결과창 버튼 목록 [(key, 문구, 명령, 주요 여부)]. 주요 행동은 하나뿐이고 버튼은 최대 3개입니다."""
    entries = []
    if tutorial:
        if retry:
            entries.append(['retry', '다시 학습', retry, False])
        entries.append(['modes', '메인 메뉴', select_mode, True])
    else:
        if start_next:
            entries.append(['next', next_label, start_next, True])
        if retry and (failed or not start_next):
            entries.append(['retry', '다시 도전 · 새 슬롯' if (practice or not failed) else '체크포인트부터 다시 도전', retry, failed and not start_next])
        if select_chapter:
            entries.append(['chapters', '장 선택', select_chapter, False])
        entries.append(['modes', '메인 메뉴', select_mode, False])
        if not any(e[3] for e in entries):
            entries[0][3] = True
    return [tuple(e) for e in entries[:3]]
