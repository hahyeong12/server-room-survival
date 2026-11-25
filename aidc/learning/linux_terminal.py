"""Pure virtual command results from the incident engine. No host operations or I/O.

Static configuration and bounded numeric telemetry are educational fixtures v1.
Each incident probe remains the source for the status, summary and error log text.
"""
from .linux_catalog import BY_ID, COMMANDS, MAX_OUTPUT, CLIError, example, parse

NODES = {'noc': '관제 모니터', 'network': '가상 네트워크 Linux 노드',
         'cluster': '가상 Kubernetes 관리 컨텍스트',
         **{f'server-{k}': f'GPU Server {k}' for k in 'ABCD'}}

def context_kind(node):
    return 'worker' if isinstance(node, str) and node in NODES and node.startswith('server-') else node

def job_servers(session, rec):
    current = session._job_servers(session.runs[rec.rid])
    # Completed work returned its resources. The simulated console retains the
    # last job-node telemetry for post-completion verification, labelled below.
    return current or (list(rec.servers) if session.runs[rec.rid].state.phase == 'finished' else [])

def contexts(session, rec):
    assigned = job_servers(session, rec)
    return [{'id': key, 'label': label, 'available': (key != 'cluster' or rec.type == 'crashloop'),
             'assigned': key.startswith('server-') and key[-1] in assigned} for key, label in NODES.items()]

def check_context(session, rec, command, node):
    if node not in NODES:
        raise CLIError('존재하지 않는 가상 노드입니다.', 'context', 2)
    if node == 'cluster' and rec.type != 'crashloop':
        raise CLIError('이 업무에는 Kubernetes 클러스터가 없습니다(kubeconfig 없음).', 'environment', 1)
    need = command.context
    kind = context_kind(node)
    if need != 'any' and kind != need:
        raise CLIError(f'이 도구는 {need} 컨텍스트에서만 제공됩니다. 노드를 선택하세요.', 'environment', 127)
    if kind == 'worker' and node[-1] not in job_servers(session, rec):
        raise CLIError('이 요청에 배정되지 않은 서버입니다. 다른 작업의 증거를 섞을 수 없습니다.', 'permission', 126)
    if kind == 'noc' and command.probe in ('dcgm', 'storage_space', 'storage_latency'):
        raise CLIError('관제 단말에는 해당 장치가 없습니다. 배정된 서버를 선택하세요.', 'environment', 127)

def result(session, rec, line, node):
    """Read-only: valid syntax does not imply a healthy system or process exit 0."""
    command, args = parse(line)
    if isinstance(command, str):
        return {'kind': command, 'code': 0, 'category': 'utility', 'output':
                ('\n'.join(f'{example(c)} — {c.label} [{c.context}]' for c in COMMANDS) if command == 'help' else ''),
                'command_id': command, 'probe': None, 'status': None}
    check_context(session, rec, command, node)
    readings = {p: session.reading(rec, p) for p in session.content.probes}
    reading = readings.get(command.probe)
    active = rec.cause_active
    fault = rec.type if active else None
    run = session.runs[rec.rid]
    # Use the same affected scope and job state as 3D. These fixtures model sampled telemetry, not real hardware.
    assigned = job_servers(session, rec)
    allocation = session._alloc(run)
    gpu = sum(len(x.gpu_slots) for x in allocation.slices) if allocation else 0
    net = 10 + ('ABCD'.index(node[-1]) + 1) if node.startswith('server-') else 0
    service_bad = fault == 'crashloop'
    space = {'storage_full': 100, 'storage_latency': 61, 'gpu_health': 54, 'gpu_oom': 48}.get(fault, 46)
    latency = 85 if fault == 'storage_latency' else 4
    vram = 39 if fault == 'gpu_oom' else 12 if run.state.allocated else 0
    temp = 89 if fault == 'cooling' else 48
    ident = command.command_id
    code = 0
    log = readings['job_log']['summary'] + '\n' + '\n'.join(readings['job_log']['lines'])
    if fault == 'cooling':
        log += '\nworker: thermal throttling detected; ask facilities to inspect BMS (pump not controllable here)'
    if fault == 'ups':
        log += '\nworker: site power alert received from facilities; waiting for safe-stop instruction (BMS confirmation required)'
    values = {
        'ip_addr': f'2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500\n    inet 10.20.{net}.10/24 scope global eth0',
        'ip_route': f'default via 10.20.{net}.1 dev eth0\n10.20.{net}.0/24 dev eth0 proto kernel scope link',
        'ip_link': f'2: eth0: <BROADCAST,MULTICAST,{"NO-CARRIER" if fault == "tor_uplink" else "UP,LOWER_UP"}> mtu 1500 state {"DOWN" if fault == "tor_uplink" else "UP"}\n' + readings['tor_port']['summary'],
        'ss': 'Netid State  Recv-Q Send-Q Local Address:Port Peer Address:Port\ntcp   LISTEN 0      128    0.0.0.0:8080     0.0.0.0:*\nudp   UNCONN 0      0      0.0.0.0:5353     0.0.0.0:*',
        'resolvectl': 'Global\nProtocols: +DefaultRoute\nCurrent DNS Server: ' + ('10.20.1.53' if rec.recovered is not None and rec.type == 'dns' else '10.20.0.53') + '\nDNS Servers: 10.20.0.53 10.20.1.53\nDNS Domain: aidc.internal\n설정 조회만으로 리졸버 응답을 보장하지 않습니다.',
        'ethtool': 'Settings for eth0:\n    Speed: 10000Mb/s\n    Duplex: Full\n    Link detected: ' + ('no' if fault == 'tor_uplink' else 'yes') + '\n' + readings['tor_port']['summary'],
        'systemctl': '● worker.service - AIDC worker\n   Loaded: loaded (/etc/systemd/system/worker.service; enabled)\n   Active: ' + ('failed (Result: exit-code)' if service_bad else 'active (running)') + '\n' + readings['service_events']['summary'],
        'journalctl': log,
        'ps': f'USER PID %CPU %MEM VSZ RSS TTY STAT START TIME COMMAND\naidc 4815 {0 if fault else 65}.0 12.0 8388608 4194304 ? {"D" if fault == "storage_latency" else "S" if fault else "R"} 09:00 0:40 worker --request {rec.rid}\n작업 진행률 {run.state.progress:.1f}% · 상태 {run.state.phase} · 사건 영향 {"있음" if session.incidents_for(rec.rid) else "없음"}',
        'free': '               total used free shared buff/cache available\nMem:           64Gi  16Gi 40Gi 1Gi    8Gi        46Gi\nSwap:           0B    0B   0B\n호스트 RAM이며 GPU VRAM은 별도입니다.',
        'top': f'top - 가상 시각 {session.minute} min\nTasks: 12 total, 1 running\n%Cpu(s): 12 us, 3 sy, {65 if fault == "storage_latency" else 2} wa\nPID USER %CPU %MEM COMMAND\n4815 aidc 12.0 12.0 worker\n' + readings['storage_latency']['summary'],
        'nvidia_smi': f'NVIDIA-SMI (교육용 v1; 실제 제품 성능 아님)\nGPU Name Temp Memory-Usage GPU-Util\n0 Virtual-GPU {temp}C {vram}GiB / 40GiB {0 if fault in ("gpu_health", "gpu_oom") else 70}%\n작업 GPU 슬롯 {gpu} · 서버 {"·".join(assigned) or "반환됨"}\n' + readings['dcgm']['summary'],
        'nvidia_query': f'==============NVSMI LOG (가상)==============\nGPU 00000000:01:00.0\n    Temperature : {temp} C\n    FB Memory Usage : {vram} GiB / 40 GiB\n    ECC Uncorrectable : {8 if fault == "gpu_health" else 0}\n' + readings['dcgm']['summary'],
        'dcgm': 'Health Monitor Systems (사전 구성된 passive watch)\n' + readings['dcgm']['summary'] + '\n부하 테스트를 실행하지 않았습니다. 감시된 항목의 보관 표본만 조회합니다.',
        'df': f'Filesystem Size Used Avail Use% Mounted on\n/dev/vdb 100G {space}G {100-space}G {space}% /data\n' + readings['storage_space']['summary'],
        'df_inode': 'Filesystem Inodes IUsed IFree IUse% Mounted on\n/dev/vdb 6553600 131072 6422528 2% /data',
        'du': f'{85 if fault == "storage_full" else 31}G\t/data/work\n해당 디렉터리의 가상 합계이며 다른 경로·열린 삭제 파일은 포함하지 않습니다.',
        'lsblk': 'NAME FSTYPE FSVER LABEL UUID MOUNTPOINTS\nvda\n└─vda1 ext4 1.0 root sim-root /\nvdb ext4 1.0 work sim-work /data',
        'iostat': f'Linux virtual-node (가상 표본)\nDevice r/s w/s r_await w_await aqu-sz %util\nvdb 40.0 10.0 {latency}.0 {latency}.0 {8.1 if latency > 4 else 0.2} {99 if latency > 4 else 20}.0\n' + readings['storage_latency']['summary'],
        'findmnt': 'TARGET SOURCE FSTYPE OPTIONS\n/ /dev/vda1 ext4 rw,relatime\n└─/data /dev/vdb ext4 rw,relatime',
        'pods': 'NAME READY STATUS RESTARTS AGE\nworker-0 ' + ('0/1 CrashLoopBackOff 9' if service_bad else '1/1 Running 0') + ' 12m\n' + readings['service_events']['summary'],
        'pod_describe': 'Name: worker-0\nNamespace: aidc\nNode: ' + (assigned[0] if assigned else 'completed') + '\nState: ' + ('Waiting\nReason: CrashLoopBackOff\nLast State: Terminated\nReason: Error\nExit Code: 1\nEvents: BackOff restarting failed container' if service_bad else 'Running\nEvents: Started container') + '\n' + '\n'.join(readings['service_events']['lines']) + '\n' + readings['service_events']['summary'],
        'pod_logs': ('Previous terminated container (읽기 전용 보관 로그; 현재 상태 검증 아님)\n' + '\n'.join(
            [session.content.types['crashloop']['readings']['job_log']['summary'], *session.content.types['crashloop']['readings']['job_log'].get('lines', [])])
            if service_bad or rec.recovered is not None else 'Error from server (BadRequest): previous terminated container not found'),
    }
    if ident == 'ping':
        count = int(args['$count'])
        lost = readings['ping']['status'] == 'bad'
        code = 1 if lost else 0
        output = f'PING 10.20.0.15\n{count} packets transmitted, {0 if lost else count} received, {100 if lost else 0}% packet loss (이번 3회 이하 표본)\n' + readings['ping']['summary']
    elif ident in ('getent', 'dig'):
        bad = readings['dns']['status'] == 'bad'
        code = 2 if bad and ident == 'getent' else 0  # dig can exit 0 on a received SERVFAIL reply
        output = (';; ->>HEADER<<- opcode: QUERY, status: ' + ('SERVFAIL' if bad else 'NOERROR') + '\n' if ident == 'dig' else '')
        output += ('이름 조회 결과 없음\n' if bad else '10.20.0.15 storage-api.aidc.internal\n') + readings['dns']['summary']
    elif ident == 'curl':
        if fault == 'dns':
            code, output = 6, 'curl: (6) Could not resolve host: storage-api.aidc.internal'
        elif fault == 'tor_uplink':
            code, output = 7, 'curl: (7) Failed to connect to storage-api.aidc.internal port 80'
        elif service_bad:
            output = 'HTTP/1.1 503 Service Unavailable\nContent-Length: 0\n-I는 HTTP 오류 상태 자체로 종료 코드를 실패로 만들지 않습니다.'
        else:
            output = 'HTTP/1.1 200 OK\nContent-Type: application/json\nContent-Length: 16'
    elif ident == 'traceroute':
        output = 'traceroute to 10.20.0.15, 30 hops max\n1 10.20.0.1 0.2 ms\n2 10.20.2.1 ' + ('28 ms' if fault == 'congestion' else '0.5 ms') + '\n3 10.20.0.15 ' + ('42 ms' if fault == 'congestion' else '* * *' if fault == 'tor_uplink' else '0.8 ms') + '\n' + readings['link_stats']['summary']
    else:
        output = values[ident]
        if ident == 'systemctl' and service_bad:
            code = 3
        if ident == 'pod_logs' and not service_bad and rec.recovered is None:
            code = 1
    return {'kind': 'output', 'command_id': ident, 'code': code, 'category': 'observation',
            'probe': command.probe, 'status': reading['status'] if reading else 'ok',
            'output': output[:MAX_OUTPUT], 'label': command.label, 'correct': command.correct, 'wrong': command.wrong,
            'historical': ident == 'pod_logs', 'completedJob': run.state.phase == 'finished'}
