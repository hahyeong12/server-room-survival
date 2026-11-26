"""Phase8 CLI catalog v1. Exact supported forms, meaning and evidence live here only.

This is a virtual Linux subset, not a shell. Existing Chapter5 catalog is unchanged.
"""
from dataclasses import asdict, dataclass
import hashlib
import json
import shlex

VERSION = 1
MAX_LINE = 240
MAX_OUTPUT = 6000
SOURCES = {
    'ip': 'https://man7.org/linux/man-pages/man8/ip.8.html',
    'ping': 'https://github.com/iputils/iputils/blob/master/doc/ping.xml',
    'ss': 'https://man7.org/linux/man-pages/man8/ss.8.html',
    'getent': 'https://man7.org/linux/man-pages/man1/getent.1.html',
    'dig': 'https://bind9.readthedocs.io/en/latest/manpages.html#dig-dns-lookup-utility',
    'resolve': 'https://www.freedesktop.org/software/systemd/man/latest/resolvectl.html',
    'ethtool': 'https://man7.org/linux/man-pages/man8/ethtool.8.html',
    'curl': 'https://curl.se/docs/manpage.html',
    'trace': 'https://man7.org/linux/man-pages/man8/traceroute.8.html',
    'systemctl': 'https://www.freedesktop.org/software/systemd/man/latest/systemctl.html',
    'journal': 'https://www.freedesktop.org/software/systemd/man/latest/journalctl.html',
    'ps': 'https://man7.org/linux/man-pages/man1/ps.1.html',
    'free': 'https://man7.org/linux/man-pages/man1/free.1.html',
    'top': 'https://man7.org/linux/man-pages/man1/top.1.html',
    'smi': 'https://docs.nvidia.com/deploy/nvidia-smi/index.html',
    'dcgm': 'https://docs.nvidia.com/datacenter/dcgm/latest/learn/modules/health-monitoring.html',
    'df': 'https://www.gnu.org/software/coreutils/manual/html_node/df-invocation.html',
    'du': 'https://www.gnu.org/software/coreutils/manual/html_node/du-invocation.html',
    'lsblk': 'https://man7.org/linux/man-pages/man8/lsblk.8.html',
    'iostat': 'https://github.com/sysstat/sysstat/blob/master/man/iostat.in',
    'findmnt': 'https://man7.org/linux/man-pages/man8/findmnt.8.html',
    'pods': 'https://kubernetes.io/docs/tasks/debug/debug-application/debug-running-pod/',
    'logs': 'https://kubernetes.io/docs/reference/kubectl/generated/kubectl_logs/',
}

@dataclass(frozen=True)
class Command:
    command_id: str
    syntax: str
    context: str
    probe: str | None
    label: str
    correct: str
    wrong: str
    source_key: str

    @property
    def tokens(self):
        return tuple(self.syntax.split())

    @property
    def source(self):
        return SOURCES[self.source_key]

    @property
    def tool(self):
        return self.tokens[0]

    def view(self):
        return {**asdict(self), 'tool': self.tool, 'source': self.source}

# Contexts: noc = monitoring workstation; network = simulated Linux network node;
# worker = one of this job's assigned GPU servers; cluster exists only for Kubernetes cases.
# $host/$name/$url/$path/$unit/$pod/$ns/$count are exact bounded virtual arguments.
ROWS = (
    ('ping','ping -c $count $host','any','ping','IP 도달성','ICMP 응답·손실만 확인했다','ping 성공이면 DNS와 서비스도 정상이다','ping'),
    ('ip_addr','ip addr','any',None,'주소·서브넷','선택한 노드의 주소 설정이다','주소가 있으면 원격 서비스도 정상이다','ip'),
    ('ip_route','ip route','any',None,'로컬 경로','선택한 노드의 다음 홉 설정이다','경로가 있으면 종단 통신도 성공한다','ip'),
    ('ip_link','ip link show','network','tor_port','링크 상태','이 네트워크 노드 업링크의 carrier 상태다','UP이면 모든 애플리케이션이 정상이다','ip'),
    ('ss','ss -tuln','worker',None,'수신 포트','선택 노드의 TCP·UDP 수신 소켓이다','LISTEN이면 원격 요청도 성공한다','ss'),
    ('getent','getent hosts $name','any','dns','NSS 이름 조회','설정된 이름 조회 경로의 결과다','IP ping 실패가 DNS 오류를 입증한다','getent'),
    ('dig','dig $name','any','dns','DNS 질의','응답 코드와 DNS 응답을 확인했다','dig 종료 코드 0이면 SERVFAIL도 정상이다','dig'),
    ('resolvectl','resolvectl status','any',None,'리졸버 설정','리졸버 주소와 사용 링크 설정이다','설정된 DNS 주소는 반드시 응답한다','resolve'),
    ('ethtool','ethtool eth0','network','tor_port','물리 링크 조회','이 인터페이스의 link detected 값이다','링크 UP이면 혼잡은 없다','ethtool'),
    ('curl','curl -I $url','any',None,'HTTP 헤더','이 URL의 이름 해석·연결·HTTP 응답을 구분했다','HTTP 503이어도 curl 종료 0이면 정상이다','curl'),
    ('traceroute','traceroute $host','any','link_stats','경로 응답·지연','각 홉의 응답 지연을 관측했다','별표 하나가 곧 그 라우터의 고장이다','trace'),
    ('systemctl','systemctl status $unit','worker','service_events','서비스 상태','가상 worker 서비스의 실행 상태다','active이면 작업 로그도 오류가 없다','systemctl'),
    ('journalctl','journalctl -u $unit -n $count','worker','job_log','서비스 최근 로그','선택 서비스가 남긴 최근 오류·상태다','로그의 OOM은 GPU 장치 손상을 입증한다','journal'),
    ('ps','ps aux','worker',None,'프로세스','선택 노드의 프로세스·작업 대기 상태다','프로세스가 존재하면 작업이 진행한다','ps'),
    ('free','free -h','worker',None,'호스트 RAM','호스트 RAM 가용량이며 GPU VRAM과 다르다','호스트 RAM이 남으면 CUDA OOM은 불가능하다','free'),
    ('top','top -b -n 1','worker','storage_latency','단일 자원 스냅샷','CPU·I/O wait의 단일 표본이다','CPU가 낮으면 저장장치 대기도 없다','top'),
    ('nvidia_smi','nvidia-smi','worker','dcgm','GPU 사용·메모리','GPU 메모리·온도·활용률의 현재 표본이다','VRAM 부족은 반드시 GPU 물리 결함이다','smi'),
    ('nvidia_query','nvidia-smi -q','worker','dcgm','GPU 상세·오류','장치 상태와 ECC·온도를 함께 확인했다','Xid 없이 CUDA OOM만으로 장치 교체한다','smi'),
    ('dcgm','dcgmi health --check','worker','dcgm','수동 건강 결과 조회','사전 구성된 passive health watch의 보관 표본 평가다','passive 조회는 부하를 거는 활성 진단이다','dcgm'),
    ('df','df -h','worker','storage_space','볼륨 용량','블록 공간 사용률이다','공간이 남으면 I/O 지연도 정상이다','df'),
    ('df_inode','df -i','worker',None,'inode 사용량','inode 수 사용률이며 byte 용량과 다르다','inode 여유는 데이터 공간 여유를 입증한다','df'),
    ('du','du -sh $path','worker','storage_space','허용 경로 합계','허용된 작업 경로의 가상 사용량이다','du와 df는 항상 같은 범위를 잰다','du'),
    ('lsblk','lsblk -f','worker',None,'파일시스템 구성','블록 장치·파일시스템·마운트 관계다','장치 목록이 있으면 I/O 성능도 정상이다','lsblk'),
    ('iostat','iostat -xz','worker','storage_latency','디바이스 I/O','await·util은 가상 장치의 대기·점유 지표다','util 하나만으로 모든 장치 병목을 확정한다','iostat'),
    ('findmnt','findmnt','worker',None,'마운트 조회','이 노드의 가상 마운트 연결이다','마운트 존재가 쓰기 성공을 보장한다','findmnt'),
    ('pods','kubectl get pods -n $ns','cluster','service_events','Pod 목록','가상 namespace의 상태·재시작 횟수다','CrashLoopBackOff 자체가 근본 원인이다','pods'),
    ('pod_describe','kubectl describe pod $pod -n $ns','cluster','service_events','Pod 상세 이벤트','종료 이유·이벤트와 배포 변경을 확인했다','재시작 횟수만으로 DNS 원인을 확정한다','pods'),
    ('pod_logs','kubectl logs $pod -n $ns --previous','cluster','job_log','직전 컨테이너 로그','직전 종료 컨테이너의 로그다','현재 컨테이너 정상만으로 직전 오류도 사라진다','logs'),
)
COMMANDS = tuple(Command(*r) for r in ROWS)
BY_ID = {c.command_id: c for c in COMMANDS}
ARGUMENTS = {'$host': ('10.20.0.15', '10.20.11.15', '10.20.12.15', '10.20.13.15', '10.20.14.15'), '$name': ('storage-api.aidc.internal',),
             '$url': ('http://storage-api.aidc.internal/health', 'http://worker.aidc.internal/health'), '$path': ('/data/work',),
             '$unit': ('worker.service',), '$pod': ('worker-0',), '$ns': ('aidc',),
             '$count': ('1', '3', '10', '20')}
DEFAULTS = {k: v[0] for k, v in ARGUMENTS.items()}
DEFAULTS['$count'] = '3'

def example(command):
    return ' '.join(DEFAULTS.get(t, t) for t in command.tokens)

def fingerprint():
    value = {'version': VERSION, 'commands': [c.view() for c in COMMANDS], 'args': ARGUMENTS}
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()

# Change/active operations are refused with an explanation (never executed). Options are tool-specific so read-only
# forms (for example ss -s) are not mislabelled.
MUTATING_TOOLS = ('sudo', 'su', 'rm', 'kill', 'killall', 'pkill', 'shutdown', 'reboot', 'poweroff', 'halt', 'exec',
                  'python', 'python3', 'sh', 'bash', 'dd', 'mkfs', 'fdisk', 'parted', 'iptables', 'nft', 'mount', 'umount',
                  'chmod', 'chown', 'mv', 'cp', 'tee', 'truncate', 'service')
MUTATING_WORDS = ('restart', 'delete', 'apply', 'set', 'add', 'flush', 'edit', 'run', 'stop', 'start', 'reload', 'enable',
                  'disable', 'mask', 'isolate', 'scale', 'drain', 'cordon', 'uncordon', 'rollout', 'patch', 'label', 'annotate',
                  'create', 'replace', 'del', 'change')
MUTATING_OPTIONS = {
    'nvidia-smi': ('-r', '--gpu-reset', '-pm', '--persistence-mode', '-pl', '--power-limit', '-ac', '-rac', '-lgc', '-rgc',
                   '-e', '--ecc-config', '-c', '--compute-mode'),
    'ethtool': ('-s', '--change', '-K', '--features', '-G', '--set-ring', '-A', '--pause', '-r', '--negotiate'),
    'journalctl': ('--vacuum-size', '--vacuum-time', '--vacuum-files', '--rotate', '--flush'),
    'kubectl': ('exec', 'cp', 'port-forward'),
    'systemctl': ('kill',),
}

class CLIError(ValueError):
    def __init__(self, message, category='syntax', code=2):
        super().__init__(message)
        self.category, self.code = category, code

def parse(line):
    if not isinstance(line, str) or len(line) > MAX_LINE:
        raise CLIError(f'입력은 최대 {MAX_LINE}자입니다.', 'length')
    if any(ord(c) < 32 or ord(c) == 127 or c in '|;&<>`$\\' for c in line):
        raise CLIError('셸 기능·파이프·연결·치환·리디렉션은 지원하지 않습니다.', 'shell')
    try:
        tokens = tuple(shlex.split(line))
    except ValueError:
        raise CLIError('따옴표가 닫히지 않았습니다.', 'quote') from None
    if tokens in (('help',), ('clear',)):
        return tokens[0], {}
    if not tokens:
        raise CLIError('조회 명령 하나를 입력하세요.')
    if tokens[:2] == ('dcgmi', 'diag'):
        raise CLIError('dcgmi diag는 GPU에 부하를 거는 활성 진단입니다. 운영 중인 작업 서버에서는 실행하지 않고, '
                       '수동(passive) 건강 결과는 dcgmi health --check로 조회합니다.', 'mutation', 126)
    if tokens[0].split('.')[0] in MUTATING_TOOLS or any(t in MUTATING_WORDS for t in tokens) or (
            tokens[0] in MUTATING_OPTIONS and any(t.split('=')[0] in MUTATING_OPTIONS[tokens[0]] for t in tokens[1:])):
        raise CLIError('변경 명령은 실행하지 않습니다. 승인된 현장 대응 화면을 사용하세요.', 'mutation', 126)
    candidates = [c for c in COMMANDS if c.tool == tokens[0]]
    if not candidates:
        raise CLIError('가상 환경에 없는 도구입니다. help로 지원 범위를 확인하세요.', 'tool', 127)
    for command in candidates:
        if len(command.tokens) != len(tokens):
            continue
        args = {}
        for expected, actual in zip(command.tokens, tokens):
            if expected in ARGUMENTS:
                if actual not in ARGUMENTS[expected]:
                    break
                args[expected] = actual
            elif actual != expected:
                break
        else:
            # ping/journal use a bounded count; journal is at most 20 lines.
            return command, args
    # Distinguish a recognized form with an invalid target from an unsupported flag/form.
    if any(len(c.tokens) == len(tokens) and all(e.startswith('$') or e == a for e, a in zip(c.tokens, tokens)) for c in candidates):
        raise CLIError('허용되지 않은 대상·개수입니다. 이 가상 환경의 고정 대상만 조회할 수 있습니다.', 'target')
    raise CLIError('지원하지 않는 옵션·인수 순서입니다. help의 유효 구문을 확인하세요.', 'option')
