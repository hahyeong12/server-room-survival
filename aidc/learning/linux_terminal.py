"""Pure virtual command results from the incident engine. No host operations or I/O.

Static configuration and bounded numeric telemetry are educational fixtures v1.
Each incident probe remains the source for the status, summary and error log text.
Every special case depends on what the player observed (node, target, job state), never on the hidden type alone,
so the presence of an output line cannot tell the cause apart.
"""
from .linux_catalog import BY_ID, COMMANDS, MAX_OUTPUT, CLIError, example, parse
from .linux_curriculum import CLUSTER_TEMPLATES

NODES = {'noc': '관제 모니터', 'network': '가상 네트워크 Linux 노드',
         'cluster': '가상 Kubernetes 관리 컨텍스트',
         **{f'server-{k}': f'GPU Server {k}' for k in 'ABCD'}}
STORAGE_IP = '10.20.0.15'

def context_kind(node):
    return 'worker' if isinstance(node, str) and node in NODES and node.startswith('server-') else node

def job_servers(session, rec):
    current = session._job_servers(session.runs[rec.rid])
    # Completed work returned its resources. The simulated console retains the
    # last job-node telemetry for post-completion verification, labelled below.
    return current or (list(rec.servers) if session.runs[rec.rid].state.phase == 'finished' else [])

def contexts(session, rec):
    assigned = job_servers(session, rec)
    return [{'id': key, 'label': label, 'available': (key != 'cluster' or cluster_exists(session, rec)),
             'assigned': key.startswith('server-') and key[-1] in assigned} for key, label in NODES.items()]

def cluster_exists(session, rec):
    return session.runs[rec.rid].conditions.get('catalog', {}).get('template') in CLUSTER_TEMPLATES

def check_context(session, rec, command, node):
    if not isinstance(node, str) or node not in NODES:
        raise CLIError('존재하지 않는 가상 노드입니다.', 'context', 2)
    if node == 'cluster' and not cluster_exists(session, rec):
        raise CLIError('이 업무에는 Kubernetes 클러스터가 없습니다(kubeconfig 없음).', 'environment', 1)
    need = command.context
    kind = context_kind(node)
    if need != 'any' and kind != need:
        raise CLIError(f'이 도구는 {need} 컨텍스트에서만 제공됩니다. 노드를 선택하세요.', 'environment', 127)
    if kind == 'worker' and node[-1] not in job_servers(session, rec):
        raise CLIError('이 요청에 배정되지 않은 서버입니다. 다른 작업의 증거를 섞을 수 없습니다.', 'permission', 126)
    if kind == 'noc' and command.probe in ('dcgm', 'storage_space', 'storage_latency'):
        raise CLIError('관제 단말에는 해당 장치가 없습니다. 배정된 서버를 선택하세요.', 'environment', 127)

def server_ip(letter):
    return f'10.20.{11 + "ABCD".index(letter)}.15'

def node_ip(node):
    """Virtual addresses: NOC desk 10.20.0.10, network node 10.20.0.2, GPU server X = its ping target 10.20.1X.15."""
    if node.startswith('server-'):
        return server_ip(node[-1])
    return '10.20.0.2' if node == 'network' else '10.20.0.10'

def in_scope(session, rec, host):
    """Evidence scope is one rule for every hidden cause: this request's storage and its own GPU servers."""
    return host == STORAGE_IP or host in {server_ip(x) for x in job_servers(session, rec)}

def path(fault, rec, node, host, scope):
    """One path model shared by ping and traceroute so the two never contradict each other.
    ok / down_local (this node's rack uplink is down: only its ToR gateway answers) /
    down_remote (the target rack is cut off) / congested (this job's data path over the saturated edge link)."""
    affected = server_ip(rec.primary or 'A') if fault == 'tor_uplink' else None
    own = node[-1] if node.startswith('server-') else None
    if affected:
        if own == rec.primary and host != affected:
            return 'down_local'
        if host == affected and own != rec.primary:
            return 'down_remote'
    if fault == 'congestion' and scope:
        return 'congested'
    return 'ok'

PORTS = {f'swp{i + 1}': x for i, x in enumerate('ABCD')}

def ping_output(host, count, state, source='10.20.0.10'):
    lost = count if state.startswith('down') else count // 20 if state == 'congested' else 0
    got = count - lost
    rtt = (38.4, 42.1, 61.7, 7.9) if state == 'congested' else (0.6, 0.8, 1.1, 0.1)
    lines = [f'PING {host} ({host}) 56(84) bytes of data.']
    if state == 'down_local':
        lines.append(f'From {source} icmp_seq=1 Destination Host Unreachable')
    lines += [f'--- {host} ping statistics ---',
              f'{count} packets transmitted, {got} received, {round(100 * lost / count)}% packet loss']
    if got:
        lines.append('rtt min/avg/max/mdev = ' + '/'.join(f'{x:.1f}' for x in rtt) + ' ms')
    # iputils ping: exit 1 when no reply at all arrived with -c; partial loss still exits 0.
    return (1 if not got else 0), '\n'.join(lines)

def trace_output(node, host, state):
    if host == node_ip(node):
        return f'traceroute to {host} ({host}), 30 hops max, 60 byte packets\n 1  {host}  0.0 ms'
    gw = '.'.join(node_ip(node).split('.')[:3]) + '.1'
    hop2 = '* * *' if state == 'down_local' else f'10.20.2.1  {"28.3" if state == "congested" else "0.5"} ms'
    hop3 = '* * *' if state.startswith('down') else f'{host}  {"42.1" if state == "congested" else "0.8"} ms'
    return (f'traceroute to {host} ({host}), 30 hops max, 60 byte packets\n 1  {gw}  0.2 ms\n 2  {hop2}\n 3  {hop3}\n'
            '별표(* * *)는 그 홉이 응답하지 않았다는 뜻일 뿐, 그 장비의 고장을 단독으로 입증하지 않습니다.')

def port_lines(down_rack):
    """`ip link show` on the switch node: management eth0 plus one uplink port per ToR, with its alias."""
    rows = [f'1: eth0: {link_flags(False)}\n    alias management']
    for i, (port, rack) in enumerate(PORTS.items()):
        rows.append(f'{i + 2}: {port}: {link_flags(rack == down_rack)}\n    alias ToR-{rack} uplink')
    return '\n'.join(rows)

def link_flags(down):
    # Admin state stays UP (configured up); only the carrier is missing, as iproute2 prints it.
    return ('<NO-CARRIER,BROADCAST,MULTICAST,UP> mtu 1500 qdisc mq state DOWN' if down else
            '<BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc mq state UP')

def result(session, rec, line, node):
    """Read-only: valid syntax does not imply a healthy system or process exit 0.

    Evidence eligibility (`eligible`) is the same rule for every cause (target inside this request's scope) and is
    kept server-side: LinuxSession strips it before an observation reaches the client."""
    command, args = parse(line)
    if isinstance(command, str):
        return {'kind': command, 'code': 0, 'category': 'utility', 'output':
                ('\n'.join(f'{example(c)} — {c.label} [{c.context}]' for c in COMMANDS) if command == 'help' else ''),
                'command_id': command, 'probe': None, 'status': None}
    check_context(session, rec, command, node)
    reading = session.reading(rec, command.probe) if command.probe else None
    fault = rec.type if rec.cause_active else None
    run = session.runs[rec.rid]
    assigned = job_servers(session, rec)
    allocation = session._alloc(run)
    gpu = sum(len(x.gpu_slots) for x in allocation.slices) if allocation else 0
    own = node[-1] if node.startswith('server-') else None
    ip = node_ip(node)
    net = '.'.join(ip.split('.')[:3])
    running = run.state.phase == 'running'
    hold = session._job_hold(run) if running else None
    job = 'stopped' if not running or hold == 0 else 'slow' if hold is not None else 'running'
    service_bad = fault == 'crashloop'
    space = 100 if fault == 'storage_full' else 61 if fault == 'storage_latency' else 46
    latency = 85 if fault == 'storage_latency' else 4
    vram = 39 if fault == 'gpu_oom' else 12 if run.state.allocated else 0
    temp = 89 if fault == 'cooling' else 48
    util = 0 if job == 'stopped' or not run.state.allocated else 35 if job == 'slow' else 70
    lost_gpu = fault == 'gpu_health' and own is not None and own == rec.primary
    uplink_down = fault == 'tor_uplink'
    ident = command.command_id
    code = 0
    eligible = True
    down_rack = rec.primary if uplink_down else None
    covers = None
    if ident in ('ping', 'traceroute'):
        host = args['$host']
        scope = in_scope(session, rec, host)
        eligible = scope
        covers = [host]
        state = path(fault, rec, node, host, scope)
        if ident == 'ping':
            code, output = ping_output(host, int(args['$count']), state, ip)
        else:
            output = trace_output(node, host, state)
        output += '\n(교육용 가상 표본 · 실제 패킷 없음)'
        if not scope:
            output += f'\n{host}는 이 요청의 작업 서버·스토리지가 아닙니다. 영향 범위 밖 관측은 이 사건의 증거로 기록하지 않습니다.'
    elif ident in ('getent', 'dig'):
        bad = session.reading(rec, 'dns')['status'] == 'bad'
        if ident == 'getent':
            code = 2 if bad else 0  # getent(1): 2 = one or more keys not found
            output = '(출력 없음 · 이름을 찾지 못함)' if bad else f'{STORAGE_IP}      storage-api.aidc.internal'
        else:  # dig exits 0 whenever a reply arrived, even a SERVFAIL reply
            resolver = '10.20.1.53' if rec.type == 'dns' and rec.recovered is not None else '10.20.0.53'
            output = (f'; <<>> DiG <<>> storage-api.aidc.internal\n;; ->>HEADER<<- opcode: QUERY, status: {"SERVFAIL" if bad else "NOERROR"}, id: 4242\n'
                      + ('' if bad else f';; ANSWER SECTION:\nstorage-api.aidc.internal. 300 IN A {STORAGE_IP}\n')
                      + f';; SERVER: {resolver}#53({resolver}) (UDP)')
    elif ident == 'curl':
        if fault == 'dns':
            code, output = 6, 'curl: (6) Could not resolve host: storage-api.aidc.internal'
        elif uplink_down and own == rec.primary:
            code, output = 7, 'curl: (7) Failed to connect to storage-api.aidc.internal port 80 after 3001 ms: Could not connect to server'
        elif service_bad and 'worker.aidc.internal' in args['$url']:
            output = ('HTTP/1.1 503 Service Unavailable\nContent-Length: 0\n'
                      '--fail(-f) 없이 실행했으므로 HTTP 오류 상태여도 curl 종료 코드는 0입니다. 상태 줄을 읽어야 합니다.')
        else:
            output = 'HTTP/1.1 200 OK\nContent-Type: application/json\nContent-Length: 16'
    elif ident == 'pod_logs':
        # A previous terminated container exists only while the pod is actually crash-looping. After the rollback the
        # pod is recreated (restarts 0), so --previous has nothing to show, whatever the incident was.
        if service_bad:
            crash = session.content.types['crashloop']['readings']['job_log']
            output = 'Previous terminated container (읽기 전용 보관 로그; 현재 상태 검증 아님)\n' + '\n'.join([crash['summary'], *crash.get('lines', [])])
        else:
            code, output = 1, 'Error from server (BadRequest): previous terminated container "worker" in pod "worker-0" not found'
    elif ident == 'ethtool':
        port = args['$iface']
        rack = PORTS.get(port)
        covers = [port]
        output = (f'Settings for {port}:\n\tSpeed: {"1000" if port == "eth0" else "100000"}Mb/s\n\tDuplex: Full\n'
                  f'\tLink detected: {"no" if rack and rack == down_rack else "yes"}\n'
                  + (f'(포트 별칭: ToR-{rack} uplink)' if rack else '(관리 포트)'))
    elif ident in ('nvidia_smi', 'nvidia_query') and lost_gpu:
        # nvidia-smi return value 15: the GPU has fallen off the bus or otherwise become inaccessible.
        code = 15
        output = ('Unable to determine the device handle for GPU0: 0000:01:00.0: GPU is lost.  Reboot the system to recover this GPU\n'
                  '(가상 장치 · 같은 서버의 다른 GPU 정보는 이 교육 모델에서 생략)')
    else:
        job_log = session.reading(rec, 'job_log')
        log = job_log['summary'] + '\n' + '\n'.join(job_log['lines'])
        if fault == 'cooling':
            log += '\nworker: thermal throttling detected; ask facilities to inspect BMS (pump not controllable here)'
        if fault == 'ups':
            log += '\nworker: site power alert received from facilities; waiting for safe-stop instruction (BMS confirmation required)'
        events = session.reading(rec, 'service_events')
        dcgm = session.reading(rec, 'dcgm')
        # Per-node health: the failing device is reported only on its own server; any other healthy server prints the
        # same PASS line in every incident type.
        if (dcgm['status'] == 'bad' and own == rec.primary) or dcgm['status'] == 'warn':
            health = dcgm['summary']
        else:
            health = f'Server {own}: 감시 항목 경고 없음 · 건강 검사 PASS'
        resolver = '10.20.1.53' if rec.type == 'dns' and rec.recovered is not None else '10.20.0.53'
        values = {
            'ip_addr': (f'1: eth0: {link_flags(False)}\n    inet {ip}/24 brd {net}.255 scope global eth0'
                        + (''.join(f'\n{i + 2}: {port}: {link_flags(rack == down_rack)}' for i, (port, rack) in enumerate(PORTS.items()))
                           if node == 'network' else '')),
            'ip_route': f'default via {net}.1 dev eth0\n{net}.0/24 dev eth0 proto kernel scope link src {ip}',
            'ip_link': port_lines(down_rack),
            'ss': 'Netid State  Recv-Q Send-Q Local Address:Port Peer Address:Port\ntcp   LISTEN 0      128    0.0.0.0:8080     0.0.0.0:*\nudp   UNCONN 0      0      0.0.0.0:5353     0.0.0.0:*',
            'resolvectl': (f'Global\n       Protocols: +DefaultRoute\nCurrent DNS Server: {resolver}\n       DNS Servers: {resolver}\n        DNS Domain: aidc.internal\n'
                           '설정 조회만으로 리졸버의 실제 응답을 보장하지 않습니다.'),
            'systemctl': '● worker.service - AIDC worker\n     Loaded: loaded (/etc/systemd/system/worker.service; enabled)\n     Active: ' + ('failed (Result: exit-code)' if service_bad else 'active (running)') + '\n' + events['summary'],
            'journalctl': log,
            'ps': (f'USER  PID %CPU %MEM     VSZ     RSS TTY STAT START TIME COMMAND\naidc 4815 {0 if job == "stopped" else 30 if job == "slow" else 65}.0 12.0 8388608 4194304 ?   '
                   f'{"S" if job == "stopped" else "D" if fault == "storage_latency" else "R"} 09:00 0:40 worker --request {rec.rid}\n'
                   f'작업 진행률 {run.state.progress:.1f}% · 상태 {run.state.phase}'),
            'free': '               total        used        free      shared  buff/cache   available\nMem:            64Gi        18Gi        38Gi       1.0Gi       8.0Gi        46Gi\nSwap:             0B          0B          0B\n호스트 RAM이며 GPU VRAM은 별도입니다.',
            'top': f'top - 가상 시각 {session.minute} min\nTasks:  12 total,   1 running\n%Cpu(s): 12.0 us,  3.0 sy, {65 if fault == "storage_latency" else 2}.0 wa\n  PID USER  %CPU %MEM COMMAND\n 4815 aidc  12.0 12.0 worker',
            'nvidia_smi': (f'NVIDIA-SMI (교육용 가상 v1; 실제 제품 수치 아님)\nGPU  Name         Temp  Memory-Usage      GPU-Util\n  0  Virtual-GPU  {temp}C   {vram}GiB / 40GiB   {util}%\n'
                           f'작업 GPU 슬롯 {gpu} · 작업 서버 {"·".join(assigned) or "반환됨"}'),
            'nvidia_query': (f'==============NVSMI LOG (가상)==============\nGPU 00000000:01:00.0\n    Temperature\n        GPU Current Temp : {temp} C\n'
                             f'    FB Memory Usage\n        Total : 40 GiB\n        Used : {vram} GiB\n    ECC Errors\n        Volatile Uncorrectable : 0\n'
                             f'    Clocks Event Reasons\n        HW Thermal Slowdown : {"Active" if fault == "cooling" else "Not Active"}'),
            'dcgm': 'Health Monitor Systems (사전 구성된 passive watch)\n' + health + '\n부하 테스트를 실행하지 않았습니다. 감시된 항목의 보관 표본만 평가합니다.',
            'df': f'Filesystem      Size  Used Avail Use% Mounted on\n/dev/vdb        100G  {space}G  {100 - space}G  {space}% /data\n' + session.reading(rec, 'storage_space')['summary'],
            'df_inode': 'Filesystem      Inodes  IUsed   IFree IUse% Mounted on\n/dev/vdb       6553600 131072 6422528    2% /data',
            'du': f'{85 if fault == "storage_full" else 31}G\t/data/work\n해당 디렉터리의 가상 합계이며 다른 경로·열린 삭제 파일은 포함하지 않습니다.',
            'lsblk': 'NAME   FSTYPE FSVER LABEL    UUID     MOUNTPOINTS\nvda\n└─vda1 ext4   1.0   root     sim-root /\nvdb    ext4   1.0   work     sim-work /data',
            'iostat': (f'Linux virtual-node (가상 표본)\nDevice   r/s   w/s r_await w_await aqu-sz  %util\nvdb     40.0  10.0  {latency}.0  {latency}.0  '
                       f'{8.1 if latency > 4 else 0.2}  {99 if latency > 4 else 20}.0\n' + session.reading(rec, 'storage_latency')['summary']),
            'findmnt': 'TARGET SOURCE    FSTYPE OPTIONS\n/      /dev/vda1 ext4   rw,relatime\n└─/data /dev/vdb ext4   rw,relatime',
            'pods': ('NAME       READY   STATUS             RESTARTS   AGE\nworker-0   '
                     + ('0/1     CrashLoopBackOff   9          12m' if service_bad else '1/1     Running            0          12m') + '\n' + events['summary']),
            'pod_describe': ('Name:         worker-0\nNamespace:    aidc\nNode:         ' + (f'server-{assigned[0]}' if assigned else 'completed') + '\nState:        '
                             + ('Waiting\n  Reason:     CrashLoopBackOff\nLast State:   Terminated\n  Reason:     Error\n  Exit Code:  1\nEvents:  Warning  BackOff  restarting failed container'
                                if service_bad else 'Running\nEvents:  Normal  Started  Started container worker')
                             + '\n' + '\n'.join(events['lines']) + '\n' + events['summary']),
        }
        output = values[ident]
        if ident == 'ip_link':
            covers = list(PORTS)
        elif command.probe == 'dcgm':
            covers = [node]
        if ident == 'journalctl':
            output = '\n'.join(output.splitlines()[-int(args['$count']):])
        if ident == 'systemctl' and service_bad:
            code = 3  # LSB status: program is not running
    return {'kind': 'output', 'command_id': ident, 'code': code, 'category': 'observation',
            'probe': command.probe, 'status': reading['status'] if reading else 'ok',
            'output': output[:MAX_OUTPUT], 'label': command.label, 'eligible': eligible,
            'historical': ident == 'pod_logs', 'completedJob': run.state.phase == 'finished', 'covers': covers}
