# Phase 8 공식 자료와 가상화 범위

확인일: 2026-11-26. 아래는 실제 실행 결과가 아니라 공식 문법·의미를 조사한 기록입니다. 이 게임은 실제 OS, DNS, GPU, Kubernetes, 파일시스템에 접속하지 않습니다. 허용한 구문만 Python으로 해석합니다. 명령별 단일 원본은 `aidc/learning/linux_catalog.py` v1입니다.

| 채택한 구문 | 공식 출처 | 게임에서의 관측 및 한계 |
| --- | --- | --- |
| `ping -c N IP` | [iputils ping 원문](https://github.com/iputils/iputils/blob/master/doc/ping.xml) | 제한된 ICMP 표본. IP 대상은 storage와 Server A~D로 제한. 응답 성공은 DNS/HTTP 정상 증거가 아님. 사건의 장기 손실 추세와 짧은 표본을 구별. |
| `ip addr`, `ip route`, `ip link show` | [iproute2 ip(8)](https://man7.org/linux/man-pages/man8/ip.8.html) | 선택 노드의 주소/다음 홉/링크는 다른 조회. addr/route는 worker·NOC 설정, link는 가상 네트워크 Linux 노드의 업링크 조회. 서버 NIC와 ToR 업링크를 혼동하지 않음. 변경 subcommand는 거절. |
| `ss -tuln` | [ss(8)](https://man7.org/linux/man-pages/man8/ss.8.html) | TCP/UDP 수신 소켓과 숫자 주소. LISTEN은 종단 서비스 성공 보장이 아님. 가상 노드 프록시가 8080에서 수신. |
| `getent hosts NAME` | [getent(1)](https://man7.org/linux/man-pages/man1/getent.1.html) | NSS의 hosts 조회. 게임은 지정 이름 1개, 실패 종료 2. 실제 NSS의 모든 backend는 재현하지 않음. |
| `dig NAME` | [BIND dig 매뉴얼](https://bind9.readthedocs.io/en/latest/manpages.html#dig-dns-lookup-utility) | DNS 응답 코드. SERVFAIL 응답을 받는 경우 종료 0이어도 조회 내용은 실패. 실제 패킷을 보내지 않음. |
| `resolvectl status` | [systemd resolvectl](https://www.freedesktop.org/software/systemd/man/latest/resolvectl.html) | systemd-resolved를 쓰는 가상 배포판의 설정. 등록된 리졸버와 실제 응답은 별개. |
| `ethtool eth0` | [ethtool(8)](https://man7.org/linux/man-pages/man8/ethtool.8.html) | 네트워크 노드의 지정 인터페이스 링크 조회만 허용. NIC 설정/활성 시험 없음. |
| `curl -I URL` | [curl 공식 매뉴얼](https://curl.se/docs/manpage.html) | 고정 storage/worker health URL 헤더. 이름 실패 6, 연결 실패 7, HTTP 503은 `--fail` 없이 종료 0. HTTP 헤더는 작업 로그가 아니므로 로그 근거로 저장하지 않음. |
| `traceroute IP` | [traceroute(8)](https://man7.org/linux/man-pages/man8/traceroute.8.html) | 노드별 다음 홉과 가상 RTT 표본. 별표만으로 해당 라우터 고장을 확정하지 않음. 실제 전체 망·홉 수를 재현하지 않음. |
| `systemctl status worker.service` | [systemctl](https://www.freedesktop.org/software/systemd/man/latest/systemctl.html) | 가상 systemd 서비스. failed이면 종료 3, active와 작업의 정상 진행은 별개. restart 거절. |
| `journalctl -u worker.service -n N` | [journalctl](https://www.freedesktop.org/software/systemd/man/latest/journalctl.html) | 지정 unit의 최근 N줄(1/3/10/20). 시스템 전체 journal은 접근하지 않음. 냉각/전원 로그는 작업이 받은 간접 경고이며 BMS 확인을 대체하지 않음. |
| `ps aux` | [procps ps(1)](https://man7.org/linux/man-pages/man1/ps.1.html) | 프로세스 표본. D(대기)/S/R 및 실제 작업 진행률을 함께 표시. kill 없음. |
| `free -h` | [procps free(1)](https://man7.org/linux/man-pages/man1/free.1.html) | 호스트 RAM만 표시. CUDA OOM과 호스트 RAM 부족을 동일시하지 않음. |
| `top -b -n 1` | [procps top(1)](https://man7.org/linux/man-pages/man1/top.1.html) | batch 1회 표본, CPU와 I/O wait. 실제 인터랙티브 top은 미구현. |
| `nvidia-smi`, `nvidia-smi -q` | [NVIDIA SMI](https://docs.nvidia.com/deploy/nvidia-smi/index.html) | 기본 사용량·온도와 상세 장치 상태/ECC를 구분. VRAM은 가상 40GiB 장치이며 기존 GPU 슬롯 단위와 다름. Xid 79를 ECC 오류로 바꾸지 않음. |
| `dcgmi health --check` | [DCGM passive health](https://docs.nvidia.com/datacenter/dcgm/latest/learn/modules/health-monitoring.html), [dcgmi health](https://docs.nvidia.com/datacenter/dcgm/latest/reference/command-line-reference/dcgmi/dcgmi-health.html) | **Issue 후보 `--fetch`는 감시 설정을 조회하므로 건강 판정에 채택하지 않음.** `--check`는 사전 설정된 watch의 보관 표본을 평가하는 수동 조회. `health --set/--clear`, `dcgmi diag` 활성 부하 시험은 미지원. 정상 결과는 감시 범위 내 결과일 뿐 전체 장치 보증이 아님. |
| `df -h`, `df -i` | [GNU df](https://www.gnu.org/software/coreutils/manual/html_node/df-invocation.html) | 블록 용량과 inode 수를 별도 출력. GNU 본문 open은 timeout이었지만 같은 공식 페이지의 검색 결과에서 -h/-i 의미를 확인. 용량 소진은 I/O 지연과 별개. |
| `du -sh /data/work` | [GNU du](https://www.gnu.org/software/coreutils/manual/html_node/du-invocation.html), [GNU 공식 매뉴얼](https://www.gnu.org/s/coreutils/manual/coreutils.pdf) | 허용 경로 합계만 조회. df와 범위가 다르므로 값이 항상 같지 않음. 실제 파일 순회·삭제·경로 탈출 없음. |
| `lsblk -f`, `findmnt` | [util-linux lsblk](https://man7.org/linux/man-pages/man8/lsblk.8.html), [findmnt](https://man7.org/linux/man-pages/man8/findmnt.8.html) | 장치/파일시스템 관계와 마운트 연결. 목록 존재는 성능·쓰기 성공 증거가 아님. |
| `iostat -xz` | [sysstat 원문](https://github.com/sysstat/sysstat/blob/master/man/iostat.in) | 확장 장치 지표·유휴 장치 제외. 게임은 가상 누적 표본 1개와 사건 판독의 지연 추세를 보여 줌. 실제 interval sampling·특정 SSD 병목 판정은 구현하지 않음. |
| `kubectl get pods -n aidc`, `kubectl describe pod worker-0 -n aidc` | [Kubernetes Pod 디버깅](https://kubernetes.io/docs/tasks/debug/debug-application/debug-running-pod/) | Pod 상태/재시작과 상세 종료 이유/이벤트는 보완적 관측. CrashLoopBackOff는 증상이며 근본 원인은 로그에서 확인. 클러스터는 배포 환경을 가진 가상 업무에만 존재하며 DNS·용량·혼잡 사건도 그 환경에 생길 수 있어 환경 목록이 정답을 표시하지 않음. |
| `kubectl logs worker-0 -n aidc --previous` | [kubectl logs](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_logs/) | 직전 종료 컨테이너의 보관 로그. 현재 상태나 복구 후 정상 검증으로 인정하지 않음. 이전 인스턴스가 없으면 BadRequest/종료 1. 실제 Kubernetes API 호출 없음. |

## 의도적인 간소화

- 주소·노드·unit·Pod·namespace·경로·센서 수치·로그·RTT는 교육용 fixture v1이다. 사용자 컴퓨터의 패키지·권한·장치 존재 여부와 관계없으며 화면에 가상 환경임을 표시한다. 환경에 없는 도구는 environment/127, 다른 작업 서버 접근은 permission/126, 잘못된 옵션·대상은 2로 구별한다.
- worker는 `/data` 작업 볼륨과 GPU, NOC는 관제 단말, network는 랙 업링크를 관리하는 가상 Linux 네트워크 노드이다. 실제 스위치 CLI를 Linux eth0로 일반화하지 않는다. 물리 서버의 NIC 링크가 살아 있어도 상단 스위치 업링크가 끊길 수 있다.
- 원래 제5장의 ping/ip 3종과 문항·저장은 변경하지 않았다. 새 subset은 28개 진단 호출이며, help/clear는 개수에 포함하지 않는다. 플래그 순서·축약형·유효 대상도 제한되어 전체 Linux 호환 셸이 아니다.
- 냉각 펌프·UPS 계기와 팀 승인은 기존 시설 화면의 엔진 판독을 사용한다. Linux는 간접 증상을 보여 줄 뿐 설비를 가동하지 않는다. 실제 장비 제어·SSH·GPU API·소켓·파일 검색은 없다.
