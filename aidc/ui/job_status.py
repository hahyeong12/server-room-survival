"""작업 상태 표시의 공통 기준(조회 전용, Tk·저장 없음).

장비 장애는 네트워크 단계(state.phase)와 독립이라 작업이 'running'으로 남습니다. 그래서 단계만 보면 장비 FAULT·복구·
작업 이전 준비 중에도 '정상 실행 중'으로 보였습니다(ui-consistency-001). 이 모듈은 서버 원장·장비 상태·이전 준비 시간을
읽어 관제실 배지·진행 목록·요청함·Inspector가 같은 문구와 색 역할(ui_kit.TONES 키)을 쓰게 합니다.
게임 상태(시간·작업량·장애·원장)는 바꾸지 않습니다.
"""

# key -> 진행 목록/요청함에 쓰는 짧은 이름
SHORT = {'hw_fault': '장비 장애', 'hw_repair': '장비 복구', 'migration': '이전 준비', 'resumed': '정상 실행 중'}
INBOX_SHORT = {'hw_fault': '장비', 'hw_repair': '장비', 'migration': '이전'}


def job_status(session, run):
    """장비/이전과 관련된 작업 상태. 관련이 없으면 None(기존 네트워크·요청 상태 표시를 그대로 사용).

    반환: {'key', 'short', 'label', 'detail', 'brief', 'tone', 'interrupted'} (brief는 좁은 카드용 한 줄)
      hw_fault   장비 장애로 작업 중단(FAULT)           tone 'fault'
      hw_repair  장비 복구 중, 작업은 아직 중단(REPAIRING) tone 'recover'
      migration  작업 이전 준비 중, 작업은 아직 중단       tone 'recover'
      resumed    장비 장애 대응 뒤 정상 실행 재개          tone 'ok'
    """
    state = run.state
    servers = session.hardware_servers(run)
    network = state.phase in ('incident', 'paused')
    if servers:
        health = {key: session.servers.hardware[key] for key in servers}
        faulted = [key for key, value in health.items() if value.state == 'FAULT']
        if faulted:
            result = {'key': 'hw_fault', 'label': '장비 장애 · 작업 중단', 'tone': 'fault',
                      'detail': f'Server {", ".join(faulted)} FAULT · 하드웨어 중단 {run.hardware_downtime}분',
                      'brief': f'장비 장애 · 작업 중단 (Server {", ".join(faulted)})'}
        else:
            left = max(value.repair_left for value in health.values())
            result = {'key': 'hw_repair', 'label': '장비 복구 중 · 작업 중단', 'tone': 'recover',
                      'detail': f'Server {", ".join(servers)} 복구 {left}분 남음 · 하드웨어 중단 {run.hardware_downtime}분',
                      'brief': f'장비 복구 중 · {left}분 남음'}
    elif state.allocated and run.migration_left:
        result = {'key': 'migration', 'label': '작업 이전 준비 중 · 작업 중단', 'tone': 'recover',
                  'detail': f'준비 {run.migration_left}분 남음 · 준비 후 새 서버에서 재개',
                  'brief': f'작업 이전 준비 중 · {run.migration_left}분 남음'}
    elif state.allocated and state.phase == 'running' and (run.hardware_downtime or run.migration_downtime):
        how = '작업 이전 후 재개' if run.migration_downtime else '장비 복구 후 재개'
        return {'key': 'resumed', 'short': SHORT['resumed'], 'label': '정상 실행 중', 'tone': 'ok',
                'detail': how, 'brief': f'정상 실행 중 · {how}', 'interrupted': False}
    else:
        return None
    if network:
        result['detail'] += ' / 네트워크 장애도 있음'
    return {**result, 'short': SHORT[result['key']], 'interrupted': True}


def chip_label(status):
    """하단 상태 배지 문구."""
    return status['label']+' · '+status['detail']
