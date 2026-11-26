"""Versioned finite follow-up curriculum. Incident v1 and catalog v1 are immutable."""
from copy import deepcopy
import hashlib
import json
from aidc.incidents.content import load

VERSION = 1
# Deployment environment is a property of the pre-existing virtual workload,
# independent of its hidden fault. These templates can suffer DNS/I/O/congestion too.
CLUSTER_TEMPLATES = ('sin-merbau-research', 'sfo-bayfog-video', 'bom-marine-batch')
# Two complementary CLI evidence families per cause, plus a deliberate non-proof.
# BMS probes stay physically on site. CLI cannot inspect or change a pump/UPS directly.
CASES = {
    'dns': {'groups': [['ping'], ['getent', 'dig']], 'distractor': 'ip_route'},
    'tor_uplink': {'groups': [['ip_link', 'ethtool'], ['ping']], 'distractor': 'getent'},
    'congestion': {'groups': [['traceroute'], ['ping']], 'distractor': 'df'},
    'gpu_health': {'groups': [['dcgm', 'nvidia_query'], ['journalctl']], 'distractor': 'free'},
    'gpu_oom': {'groups': [['journalctl'], ['nvidia_smi', 'dcgm']], 'distractor': 'free'},
    'storage_full': {'groups': [['df', 'du'], ['journalctl']], 'distractor': 'df_inode'},
    'storage_latency': {'groups': [['iostat', 'top'], ['df']], 'distractor': 'ping'},
    'cooling': {'groups': [['nvidia_smi', 'nvidia_query'], ['journalctl']], 'distractor': 'ping', 'bms': 'cooling'},
    'ups': {'groups': [['journalctl'], ['ps']], 'distractor': 'ping', 'bms': 'ups'},
    'crashloop': {'groups': [['pods', 'pod_describe', 'systemctl'], ['pod_logs', 'journalctl']], 'distractor': 'ping'},
}

# Cases 1-4 run sequentially to focus on a new skill. Last shift combines the familiar
# telemetry on different customers, order, trigger fractions and overlapping arrival times.
# It is a new fixed exam scenario, not Phase7 shift C and not random/free incidents.
SHIFTS = {
    1: {'title': 'Linux 근무 1 · 같은 증상, 다른 계층', 'role': '신입 관제 담당', 'input': 'choice',
        'coaching': 'full', 'rank': '신입', 'cases': ['tor_uplink', 'dns'],
        'intro': '선배와 함께 서버동의 경보를 확인합니다. 관제동 내 자리 → 내 모니터의 Linux 탭에서 도구를 직접 고르세요. IP 응답과 이름 조회는 다른 증거입니다.'},
    2: {'title': 'Linux 근무 2 · 저장장치의 두 얼굴', 'role': '주니어 운영 담당', 'input': 'assemble',
        'coaching': 'short', 'rank': '주니어', 'cases': ['storage_latency', 'storage_full'],
        'intro': '명령·옵션·대상을 조립하고, 출력에서 사실과 추측을 구분합니다. 용량과 I/O 지연은 별도로 조사하세요.'},
    3: {'title': 'Linux 근무 3 · GPU와 작업 프로세스', 'role': 'GPU 운영 담당', 'input': 'terminal',
        'coaching': 'none', 'rank': '주니어', 'cases': ['gpu_oom', 'gpu_health'],
        'intro': '배정된 가상 GPU 서버를 선택해 명령어를 입력합니다. 호스트 RAM, VRAM, 장치 건강 상태를 구분하고 조건 변경은 고객 동의를 받으세요.'},
    4: {'title': 'Linux 근무 4 · 현장과 관제의 분업', 'role': '교대 조정 담당', 'input': 'terminal',
        'coaching': 'none', 'rank': '운영 엔지니어', 'cases': ['ups', 'cooling'],
        'intro': 'Linux에서 작업 증상을 확인하고 설비 현장에서 BMS를 별도로 관측하세요. 전원·펌프는 담당팀만 조작합니다. 고객 영향 안내와 제한 시간을 관리하세요.'},
    5: {'title': 'Linux 근무 5 · 독립 대응 평가', 'role': '독립 관제 엔지니어 평가', 'input': 'terminal',
        'coaching': 'none', 'rank': '독립 관제 엔지니어', 'cases': ['crashloop', 'congestion', 'storage_latency'],
        'intro': '새로운 고객 조합과 겹친 증상입니다. 필요한 장비·명령·증거를 직접 선택하고 가설, 승인된 대응, 복구 뒤 새 관측, 최종 보고까지 완주하세요. 도움은 요청할 때만 제공합니다.'},
}

def fingerprint():
    return hashlib.sha256(json.dumps({'version': VERSION, 'shifts': SHIFTS, 'cases': CASES, 'cluster': CLUSTER_TEMPLATES},
                                    sort_keys=True, ensure_ascii=False).encode()).hexdigest()

def shift_def(number, practice=None):
    spec = deepcopy(SHIFTS[number])
    content = load()
    types = [practice] if practice else spec['cases']
    # Exam deliberately recombines clients. Two simultaneous cases plus a later one.
    templates = ([content.practice['storage_full'], content.practice['dns'], content.practice['crashloop']]
                 if number == 5 and not practice else [content.practice[t] for t in types])
    arrivals = [[0 if i == 0 or number == 5 else 170 * i, tid] for i, tid in enumerate(templates)]
    if number == 5 and len(arrivals) == 3:
        arrivals[2][0] = 80
    n = len(types)
    return {**spec, 'code': f'L{number}', 'subtitle': spec['role'],
            'arrivals': arrivals, 'incidents': [[i, t, 0.2 if number == 5 else 0.3] for i, t in enumerate(types)],
            'goal': {'minResolved': n, 'minSuccess': n, 'maxExpired': 0, 'notifyBeforeRecovery': False}}
