# 3D 시뮬레이션 ↔ Linux 명령어 학습 연결 설계 (Issue #2, 설계만)

상태: **설계 문서. 이번 범위에서 구현하지 않음.** 새 명령어 엔진, 가상 터미널, Python 엔진 연동은 사용자 승인 후 별도 이슈에서 진행합니다.
작성: 2026-11-20, Claude Code (Claude Opus 5.5). 기준: `PROJECT_VISION.md`, `docs/LEARNING_DESIGN.md`, 기존 Python `aidc/learning/*`, 3D 시제품 `prototypes/3d-datacenter-001`.

## 1. 원칙

1. **하나의 사건, 하나의 상태.** 3D 화면·내 모니터·터미널 출력이 모두 같은 관찰 스냅샷에서 계산됩니다. 화면마다 따로 진실을 만들지 않습니다(현재 3D 시연의 `world-store` 단일 상태, Python의 `observe(session, rid)` → 불변 `LabObservation`과 같은 원칙).
2. **난이도는 표현만 바꿉니다.** 같은 장애를 입문자는 3D 강조와 버튼으로, 고급자는 직접 입력한 명령과 로그로 진단합니다. 판정 근거(관찰값)는 동일합니다.
3. **조회와 조치는 분리합니다.** 진단 명령은 읽기 전용입니다. 복구는 기존 게임 대응(Python `respond()` / 3D 시연의 명시적 단계)만 사용합니다.
4. **실제와 게임을 혼동시키지 않습니다.** 가상 주소·장치명은 "교육용 가상 설정"으로 표시하고, 허용 목록 밖의 명령·셸 기능은 거부합니다(현재 `lab_terminal.run_command`와 동일: os/subprocess/eval 미사용).

## 2. 난이도 단계와 기존 연수 Stage의 대응

| 3D 학습 단계 | 플레이어 행동 | 같은 사건에서 보이는 것 | 기존 Python 연수 Stage(`training.STAGES`) |
| --- | --- | --- | --- |
| L0 입문 | 내 자리 알림 → 3D에서 강조된 랙/장비 클릭 → 버튼 대응 | 빨간 랙 테두리, 끊긴 업링크 흐름, 냉각 아이콘 경고 | `structure` (구간 DOWN 선택 + 영향 질문) |
| L1 초중급 | 상황에 맞는 진단 명령을 **객관식으로 선택** | 선택한 명령의 결과 화면(예: ping 100% 손실) | `tool` (ping 선택 + 한계 질문) |
| L2 중급 | 명령 + 옵션 + 대상을 **블록으로 조립** | 조립 결과의 실제 출력, 잘못된 옵션 피드백 | `assemble` (`-c`·서버 주소 ping 조립) |
| L3 고급 | **격리된 가상 터미널에 직접 입력**, 로그 분석 | 허용 목록 명령 출력 + 가상 로그(journal) | `terminal` → `independent` (증거→원인→조치→재확인) |

3D 쪽은 L0만 현재 구현되어 있습니다(Phase 2/3.1 시연). L1~L3의 엔진은 Python에 일부 존재합니다(아래 표).

## 3. 연결 인터페이스 (제안)

### 3.1 관찰 스냅샷 `IncidentObservation` (읽기 전용)

```text
IncidentObservation {
  incidentId      : 'SG-2026-001:uplink'          # 요청 ID + 사건 종류
  kind            : 'uplink' | 'aux-cooling' | 'power' | 'hardware'
  location        : { building: 'HALL-01', rack: 'D-06', device: 'tor-d06' }
  phase           : 'fault' | 'repairing' | 'awaiting' | 'recovered'
  signals         : { uplinkUp: false, lossPct: 100, inletC: 24.7, coolantLpm: 12, ... }
  virtualNetwork  : { hostIp: '10.20.6.11', gateway: '10.20.6.1', ... }  # 교육용 가상 설정 표시
  timeline        : [{ seq, event }]                # 이미 기록된 사실만
}
```

- 현재 3D 시연에서는 `world-store.state`(request + facility + ops)로부터, 미래의 실제 게임 연동에서는 Python `observe()` 결과로부터 **어댑터**가 만듭니다. 3D 화면은 이 스냅샷만 읽습니다.
- 관찰 생성은 시간·점수·자원을 바꾸지 않습니다(현재 `navigation 무부작용` 테스트와 같은 성질로 검증).

### 3.2 진단 명령 레지스트리 `DiagnosticCommand`

| 명령 | 증거 | 사용 단계 | 현재 존재 여부 |
| --- | --- | --- | --- |
| `ping [-c N] <대상>` | 응답 수·손실률 | L1~L3 | **Python `lab_terminal`에 구현됨** |
| `ip addr [dev]`, `ip route` | 주소·기본 경로·우회 경로 | L1~L3 | **Python에 구현됨** |
| `help`, `clear` | — | L3 | **Python에 구현됨** |
| `ip -s link show <dev>` | 인터페이스 오류/드롭 카운터 | L2~L3 | 제안 |
| `sensors` | 유입·배기 온도(보조 냉각 상태 반영) | L1~L3 | 제안 (3D 냉각 시연과 연결) |
| `journalctl -u aux-cooling -n 20` | 유량 저하 경고 로그 | L3 | 제안 |
| `traceroute <대상>` | 끊긴 홉 위치(ToR) | L2~L3 | 제안 |

각 명령은 `(관찰 스냅샷, 파싱된 인자) → 출력 텍스트 + 증거 태그`의 **순수 함수**입니다. 증거 태그(`evidence_kind`, Python `training.py`에 유사 개념 존재)는 "조치 전 증거 확보"를 기록하는 데 씁니다.

### 3.3 3D 화면의 진입점 (UI 연결 위치)

| 위치 | L0 (현재) | L1~L3 (제안) |
| --- | --- | --- |
| 내 모니터(관제동) | 지금 할 일 + 단계 버튼, 시설 감시 타일 | [진단] 탭: 명령 선택/조립/터미널, 증거 목록 |
| 서버동 Inspector | 랙 상태·지표 | [이 장비에서 진단]: 대상 장치가 자동 채워진 터미널 |
| 네트워크동 패널 | 장애 원인 조회 버튼 | `ping`·`ip route`·`traceroute` 단계별 과제 |
| 냉각 플랜트 패널 | 켜짐/꺼짐/경고, 유량·온도·추세 | `sensors`·`journalctl` 과제 |

3D 강조(L0)는 고급 단계로 갈수록 줄입니다. L3에서는 랙 강조·원인 버튼을 숨기고 증거로 원인을 고르게 합니다.

## 4. 예시 흐름 — 싱가포르 업링크 장애

1. **알림:** 내 모니터에 "서버동 01 업링크 장애" 타일(빨강 + 텍스트).
2. **위치 확인:** L0은 3D에서 D-06 랙과 끊긴 업링크 흐름을 클릭. L1 이상은 Inspector에서 대상 장치 확인.
3. **진단:** L1 `ping` 선택 → 100% 손실. L2 `ping -c 4 10.20.6.1` 조립. L3 직접 입력 후 `ip route`로 기본 경로 확인, `ip -s link`로 오류 카운터 확인.
4. **원인 판단:** 증거 목록에서 "D-06 ToR 업링크 단절" 선택(L3는 근거 증거를 함께 제출).
5. **복구:** 기존 대응만 사용(3D 시연의 복구 시작 → 복구 처리 완료).
6. **재확인:** 같은 명령을 다시 실행해 응답 회복을 확인한 뒤 사후 확인 완료. 조치 전후 증거가 모두 있어야 단계 통과(Python `stage5_verified`와 같은 원칙).

보조 냉각 경고도 같은 틀입니다: 알림 → 냉각 플랜트 → `sensors`(유입 24.7 °C) → `journalctl`(유량 12 L/min) → 유량 점검 완료·재가동 → `sensors` 재확인.

## 5. 기록과 평가

- 학습 기록(어떤 단계에서 어떤 명령으로 어떤 증거를 얻었는가)은 운영 점수·저장과 분리합니다(Python `LabLearningTrace`는 메모리 전용).
- 저장이 필요해지면 기존 스토리 JSON의 선택 필드 방식(예: `training`)을 따르며 SQL을 변경하지 않습니다. **이 결정은 사용자 승인 사항**입니다.

## 6. 이번 범위에서 하지 않은 것

- 3D에 진단 탭·터미널·명령 해석기 구현, Python `lab_terminal` 호출, 저장 형식 추가.
- 실제 Linux 명령 실행, 실제 네트워크 접근.
- 추가 국가·챕터·업무.
