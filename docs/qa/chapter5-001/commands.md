# 실제 입력·출력 기록

정규1회 플레이에서 GUI가 표시한 출력입니다. 프로그램이 생성한 교육용 출력이며 실제 Linux/장비 측정이 아닙니다.

## Stage 2 진단 도구 선택 · choice

```text
[가상 시각 D1 17:20 · 교육용 출력]
engineer@sg-edge:~$ ping -c 3 10.0.0.20
PING 10.0.0.20 (10.0.0.20) 56(84) bytes of data.

--- 10.0.0.20 ping statistics ---
3 packets transmitted, 0 received, 100% packet loss, time 2036ms
```

## Stage 3 명령어 조립 · blocks

```text
[가상 시각 D1 17:20 · 교육용 출력]
engineer@sg-edge:~$ ping -c 3 10.0.0.20
PING 10.0.0.20 (10.0.0.20) 56(84) bytes of data.

--- 10.0.0.20 ping statistics ---
3 packets transmitted, 0 received, 100% packet loss, time 2036ms
```

## Stage 4 터미널 직접 입력 · native keyboard

```text
engineer@sg-edge:~$ ping -z 192.168.10.1
[가상 시각 D1 17:20 · 교육용 출력]
ping: invalid option -- 'z'
입력 안내: [교육용 안내] 이 터미널의 ping은 -c(보낼 횟수) 옵션만 지원합니다.
```

## Stage 4 터미널 직접 입력 · native keyboard

```text
engineer@sg-edge:~$ ping -c 3 192.168.10.1
[가상 시각 D1 17:20 · 교육용 출력]
PING 192.168.10.1 (192.168.10.1) 56(84) bytes of data.
64 bytes from 192.168.10.1: icmp_seq=1 ttl=64 time=1.0 ms
64 bytes from 192.168.10.1: icmp_seq=2 ttl=64 time=1.4 ms
64 bytes from 192.168.10.1: icmp_seq=3 ttl=64 time=0.7 ms

--- 192.168.10.1 ping statistics ---
3 packets transmitted, 3 received, 0% packet loss, time 2009ms
rtt min/avg/max/mdev = 0.700/1.033/1.400/0.287 ms
```

## Stage 4 터미널 직접 입력 · native keyboard

```text
engineer@sg-edge:~$ ping -c 3 10.0.0.20
[가상 시각 D1 17:20 · 교육용 출력]
PING 10.0.0.20 (10.0.0.20) 56(84) bytes of data.

--- 10.0.0.20 ping statistics ---
3 packets transmitted, 0 received, 100% packet loss, time 2036ms
```

## Stage 4 터미널 직접 입력 · native keyboard

```text
engineer@sg-edge:~$ ip route
[가상 시각 D1 17:20 · 교육용 출력]
10.0.0.0/24 via 192.168.10.1 dev eth0 proto static
192.168.10.0/24 dev eth0 proto kernel scope link src 192.168.10.5
192.168.20.0/24 dev eth1 proto kernel scope link src 192.168.20.5
```

## Stage 5 독립 진단 시연 · native keyboard

```text
engineer@sg-edge:~$ ping -c 3 192.168.10.1
[가상 시각 D1 17:20 · 교육용 출력]
PING 192.168.10.1 (192.168.10.1) 56(84) bytes of data.
64 bytes from 192.168.10.1: icmp_seq=1 ttl=64 time=1.0 ms
64 bytes from 192.168.10.1: icmp_seq=2 ttl=64 time=1.4 ms
64 bytes from 192.168.10.1: icmp_seq=3 ttl=64 time=0.7 ms

--- 192.168.10.1 ping statistics ---
3 packets transmitted, 3 received, 0% packet loss, time 2009ms
rtt min/avg/max/mdev = 0.700/1.033/1.400/0.287 ms
```

## Stage 5 독립 진단 시연 · native keyboard

```text
engineer@sg-edge:~$ ping -c 3 10.0.0.20
[가상 시각 D1 17:20 · 교육용 출력]
PING 10.0.0.20 (10.0.0.20) 56(84) bytes of data.

--- 10.0.0.20 ping statistics ---
3 packets transmitted, 0 received, 100% packet loss, time 2036ms
```

## Stage 5 독립 진단 시연 · native keyboard

```text
engineer@sg-edge:~$ ip route
[가상 시각 D1 17:20 · 교육용 출력]
10.0.0.0/24 via 192.168.10.1 dev eth0 proto static
192.168.10.0/24 dev eth0 proto kernel scope link src 192.168.10.5
192.168.20.0/24 dev eth1 proto kernel scope link src 192.168.20.5
```

## Stage 5 독립 진단 시연 · native keyboard

```text
engineer@sg-edge:~$ ping -c 3 10.0.0.20
[가상 시각 D1 17:20 · 교육용 출력]
PING 10.0.0.20 (10.0.0.20) 56(84) bytes of data.
64 bytes from 10.0.0.20: icmp_seq=1 ttl=61 time=32.2 ms
64 bytes from 10.0.0.20: icmp_seq=2 ttl=61 time=32.6 ms
64 bytes from 10.0.0.20: icmp_seq=3 ttl=61 time=31.9 ms

--- 10.0.0.20 ping statistics ---
3 packets transmitted, 3 received, 0% packet loss, time 2009ms
rtt min/avg/max/mdev = 31.900/32.233/32.600/0.287 ms
```
