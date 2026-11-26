# Phase 8 구현 계획 및 인터페이스

기준: Issue #9 전체 지시서, `origin/experiment/3d-incident-response-phase7` = `287eba4fcc5078eb5815e0b6223f6985f18de8a2`. 작업 브랜치: `experiment/3d-linux-learning-phase8`.

## 보존 경계

기존 사건 v1, 글로벌 카탈로그 v1, 제1~5장 Lab 해석기·훈련·저장 형식을 유지한다. 새 기능은 `aidc/learning/linux_*`와 새 `mode=linux`, `aidc_3d_linux_NNN.db`로 격리한다. 사용자 DB는 열지 않는다. 시작 시 추적 파일 변경 0, 기존 Phase7 미추적 QA PNG는 보존한다. 원격 기준 SHA는 fetch 후 확인했다. 글로벌 자유 운영의 무작위 장애는 여전히 미구현이며 Issue #8을 변경하지 않는다.

## 구현 순서

1. 보호 해시와 계획 기록 → 버전 1 명령 registry/안전 parser/판독 renderer.
2. `LinuxSession(IncidentSession)`에 5개 유한 근무, 명령 증거·해석·사후 새 관측·승급을 추가. 기존 사건의 실제 영향·승인·고객 동의·복구·보고를 그대로 호출한다.
3. 어댑터에 전용 저장/이어하기/새 슬롯 재도전, 명령 실행·해석 행동과 읽기 전용 학습 뷰 연결.
4. 내 모니터 Linux 탭: 초반 도구 선택, 중반 옵션·대상 조립, 후반 직접 입력. 컨텍스트 선택, 내부 스크롤 출력, 항상 보이는 입력·현재 목표. 시설 BMS는 현장에서만 관측.
5. Python 반례/저장/10종 완주, 브라우저 실제 클릭·입력 완주·재시작·레이아웃·성능. Phase4~7/lab 회귀와 Python 비GUI·어댑터·JS·build.
6. 독립 리뷰 → 지적 수정·재시험 → 문서와 Issue #9 결과 댓글. 기능별 커밋과 일반 push, 원격 SHA 확인. main/PR/force push 없음.

## 단일 상태와 API

명령 catalog는 command_id, 허용 tokens/target, context, probe, 해석/오해, 한국어 설명, 공식 source의 단일 원본이다. 순수 함수 parser는 정확한 허용 구문만 받으며 실제 OS/네트워크 실행 경로가 없다. renderer는 `IncidentSession.reading()` 및 서버 원장/가상 시계/작업 상태를 사용한다. 유효한 조회만 학습 기록에 저장하고 사건 근거는 같은 판독으로 기록한다. 잘못된 구문·대상·권한은 사건을 변경하지 않는다.

후속 학습 기록은 별도 선택 JSON 블록에 version/fingerprint를 저장한다. 기존 사건 schema는 변경하지 않는다. 명령 전후 기록은 사건 ID·node·가상 시각·단조 seq로 묶고, 복구 이후 새 관측을 요구한다. 결과/승급은 Python에서 계산한다. 비동기 응답은 기존 API 직렬화/게임 ID 보호를 유지한다.

## QA 계획

- catalog 각 명령 유효/잘못된 구문/내용/exit status, injection·quote·길이·namespace 탈출·잘못된 node·미설치/권한.
- 10종 각각 보완적 CLI 증거 2개, 혼동하는 정상 판독, 가설·승인된 조치·새 관측·보고. ping 성공과 DNS 실패, OOM과 장치 오류, 용량과 I/O 지연 구분.
- 학습/복구/승급 3지점 저장 후 재시작. 재도전은 새 파일, 이전 파일 불변. 저장 실패 원자성.
- 새 E2E 진행은 실제 UI만 사용. 준비 fixture는 OS 임시 폴더에만 생성하고 기록한다. 1366×768/1920×1080/150% 에뮬레이션, Enter·히스토리·복사·포커스·움직임 줄이기.
- Tk GUI 311개는 실행하지 않는다. PASS는 실제 실행 결과만 기록한다.

## 구현된 구조

```text
incidents_v1.json + catalog_v1.json (기존 정의·지문 유지)
       ↓ 기존 실제 작업 영향·자원 원장·승인·고객 조건
LinuxSession(IncidentSession) ← linux_curriculum v1 (근무 5개·사건별 증거 요건)
       ↓ reading(rec, probe), 실제 작업·서버·가상 시계
linux_catalog v1 → 안전한 parse → linux_terminal.result (읽기 전용)
       ↓ 유효 관측만 같은 atomic 단위에 저장
linux JSON 블록 (관측·해석·도움) + 기존 incident/global JSON
       ↓ 3D 어댑터의 읽기 전용 snapshot / 기존 사건 대응 action
Linux 탭 (선택·조립·입력) ↔ 사건 탭 ↔ 현장 콘솔/BMS ↔ 결과·승급
```

- `linux_catalog.py`: 28개 진단 호출의 정확한 구문·인수 허용 목록·맥락·probe·한국어 목적·해석/오해·공식 출처. 도움말과 조립 UI도 이 목록을 읽는다. `help`/`clear`는 진단 호출 수에 포함하지 않는다.
- `linux_terminal.py`: 실제 실행 없이 현재 사건 판독·원장·작업 상태와 가상 fixture에서 결과를 생성한다. NOC/네트워크 Linux 노드/배정된 GPU 서버/업무 배포 환경의 Kubernetes 맥락을 구분한다. 다른 작업 서버는 거절하며, 같은 작업의 정상 GPU와 고장 GPU도 구분한다. storage IP와 랙 IP를 구별하여 무관한 ping을 고장 랙의 증거로 쓰지 않는다.
- `linux_curriculum.py`: 기존 v1 사건을 새 고객·도착 일정·발생 지점으로 엮은 유한 근무 5개. 1 도구 선택(네트워크), 2 조립(스토리지), 3 직접 입력(GPU), 4 현장 분업(시설), 5 새로운 고객 조합·동시 증상의 독립 평가. 최종 평가는 Phase7 근무 C를 복제하지 않는다.
- `linux_session.py`: 별도 `mode=linux`, 선택 `linux` JSON v1, 커리큘럼·명령 지문. 기존 SQL 및 incident schema 변경 없음. 학습과 실제 사건 기록은 부모 `_atomic()`과 함께 롤백한다. 결과/승급은 기존 사건 종료와 고객 작업의 실제 결과에서 계산한다. 연습은 승급하지 않는다.
- 기존 파일의 규칙 변경은 `GlobalSession._has_shift()` / `IncidentSession._has_shift()` 확장 훅뿐이다. 기본 구현은 각각 기존 카탈로그의 근무 번호만 허용한다. 새 하위 세션만 1~5를 허용한다.

## 학습과 운영의 연결

| 사건 | 보완적 CLI 증거(최소 2종) | 혼동하기 쉬운 결과 | 추가 현장 확인 |
| --- | --- | --- | --- |
| DNS | IP ping + getent/dig | 로컬 route가 있어도 DNS 정상 아님 | 네트워크동에서 리졸버 대응 |
| ToR 업링크 | 네트워크 노드 ethtool/ip link + 해당 랙 IP ping | storage IP ping·DNS는 정상일 수 있음 | 네트워크동 포트·우회/담당 호출 |
| 회선 혼잡 | traceroute 지연 + ping 응답 추세 | df 공간 정상은 회선 증거 아님 | 네트워크동 QoS 대응 |
| GPU 장치 오류 | DCGM/SMI 상세 + worker 로그 | 호스트 free 정상은 장치 보증 아님 | 랙에서 격리·이전/수리 |
| CUDA OOM | worker 로그 + VRAM/건강 조회 | 호스트 RAM 여유는 VRAM 여유 아님 | 고객 동의·GPU/플랫폼 대응 |
| 용량 소진 | df/du + 쓰기 실패 로그 | inode 여유가 블록 공간 여유 아님 | 서버동의 허용된 정리·확장 |
| I/O 지연 | iostat/top + df 여유 | ping 정상은 스토리지 성능 증거 아님 | 서버동 대체 경로 |
| 냉각 | GPU 온도/제한 + worker 경고 | ping 정상은 냉각 정상 아님 | 냉각 플랜트 BMS + 시설팀 승인 |
| UPS | worker의 시설 경고 + 작업 프로세스 | ping 정상이어도 전원 보호 시간은 줄어듦 | UPS BMS + 전원팀·계획 중단 |
| CrashLoop | Pod/서비스 이벤트 + 직전/현재 로그 | ping 정상은 서비스 정상 아님 | 관제의 플랫폼 승인·롤백 |

모든 가설은 **제출한 후보 자체의** 보완적 명령 요건을 먼저 확인한 뒤 기존 판정을 호출한다. 숨은 정답 여부에 따라 오류 종류를 바꾸지 않는다. 최소 1회 출력 해석도 요구한다. 후반 해석 오답에는 정답 문장을 직접 주지 않는다. 선택지 ID와 순서는 관측별로 달라지고 정답 매핑은 Python에 남는다.

복구 전 출력은 사후 확인에 재사용할 수 없다. 기존 10분 정상 관찰·v1 verify 지표 외에도 복구 뒤 보완적 CLI 조회를 새로 요구한다. `kubectl logs --previous`는 보관 로그이므로 사후 검증에서 제외한다. 물리 장비 조작은 현장 화면에서만 승인 절차로 요청하며 CLI 조회가 복구를 대신하지 않는다.

## 외부 인터페이스와 저장

- 메뉴: 3D 제5장 수료 저장이 있으면 정규 Linux 연수 시작. 기존 수료 슬롯도 동일한 읽기 전용 해금 검사로 사용한다. 수료 여부와 관계없이 10종 사건별 연습은 별도 슬롯에서 시작할 수 있다. 기존 Tk DB를 가져오거나 수정하지 않는다.
- 저장 파일: `aidc_3d_linux_NNN.db` + 기존 3D sidecar. 새 시작·실패 재도전 모두 독점 생성한 새 파일. 재도전은 현재 근무/연습만 새로 시작하며 원본 DB를 덮어쓰지 않는다. 이전 Chapter5·글로벌·사건 저장의 모드/의미는 그대로다.
- 새 action: `linux_command(incident, line, node, token)`, `linux_interpret(incident, seq, answer)`, `linux_help(incident)`. 가설/조치/검증/보고는 기존 incident action을 호출한다. command API는 내 모니터 위치와 현재 token을 필수로 검사한다.
- 오류: 구문/옵션/대상/환경/권한/셸 기능/길이를 구분. 셸 연결·치환·경로 탈출·변경 명령·알 수 없는 도구는 실제 실행 없이 거절한다. 출력 최대 6,000자, 입력 최대 240자.
- UI: 출력 자체만 스크롤하고 입력/현재 목표/사건 복귀는 고정. Enter, 히스토리 50개, 복사, 용어/공식 출처를 제공한다. 요청 대기 중 입력·장비·사건 선택을 잠그고, 다른 게임/사건/노드로 바뀐 임시 응답은 새 화면에 적용하지 않는다. `clear`는 사건별 화면만 지우며 증거는 유지한다.

정확한 실행 결과·잔여 한계는 `QA_REPORT_PHASE8.md`, 공식 문법의 채택 근거와 가상화 한계는 `PHASE8_REFERENCES.md`를 확인한다.

## 인계 후 변경 (Claude Code, 2026-11-26)

Codex 사용량 한도로 작업을 인계받은 뒤 독립 리뷰 지적과 사용자 요청을 반영한 구조 변경입니다. 자세한 지적·수정 표는 `REVIEW_PHASE8.md`의 2차 리뷰를 확인합니다.

- **증거 범위 규칙:** 노드·대상 의존 관측(ping·traceroute → 이 요청의 스토리지와 모든 작업 서버, GPU 건강 3종 → 모든 작업 서버, ToR 포트 → 작업 서버 랙의 업링크 포트)은 `LinuxSession.scope_of()`의 범위를 모두 비교했을 때만 부모 `incident_observe()`로 엔진 증거가 됩니다(`uncovered()`). 엔진 요약은 그 범위 출력들의 종합과 같습니다. 부분 확인 상태의 가설·사후 확인은 남은 대상을 안내하며 이 안내는 숨은 원인과 무관합니다. 사후 범위는 엔진과 같은 "복구 10분 뒤부터" 창을 씁니다.
- **공개 필드:** 관측의 `eligible`(범위 판정)과 사건 단위 `status`는 서버에만 남고 `LinuxSession.public()`이 화면 사본에서 제거합니다.
- **한 경로 모델:** `linux_terminal.path()`가 ping·traceroute의 노드·대상별 상태(정상/자기 랙 업링크 단절/대상 랙 단절/혼잡)를 함께 계산합니다. 정상 노드·범위 밖 대상의 출력은 모든 원인에서 동일합니다.
- **가상 스위치 노드:** 네트워크 노드는 관리 포트 `eth0`과 ToR-A~D 업링크 포트 `swp1~4`를 가진 가상 Linux 기반 스위치입니다. `ethtool $iface`(catalog v1 수정, 미배포라 저장 영향 없음)와 선택 단계의 포트 선택을 제공합니다.
- **해석:** 관측당 첫 답만 인정하고 버튼을 잠급니다. 해석 요청도 화면 토큰을 검사합니다.
- **연습 메타데이터·환경 균일성:** 연습은 증상 제목·`LP` 코드·해당 근무의 입력 단계와 `IncidentBook.practice`를 사용합니다. 정규 근무마다 Kubernetes 환경 유무를 균일하게 맞췄습니다(근무 1·2·5 있음, 3·4 없음).
- **터미널 확대:** Linux 탭의 [⤢ 터미널 확대]는 작업창을 3D 화면 영역 전체로 넓히고(오른쪽 목표 패널은 유지) 한 줄 사건 요약을 보입니다. [⤡ 기본 크기]·Esc·다른 탭 이동으로 원래 크기로 돌아가며 Linux 탭으로 돌아오면 확대 설정을 복원합니다. 입력 초안·히스토리·스크롤·엔진 기록은 확대 상태와 분리되어 유지됩니다(`ui.linuxExpanded`).
- **저장 버전:** 커리큘럼·catalog v1 내용과 지문이 바뀌었습니다. Phase8은 아직 배포 전이고 저장소·저장 폴더 어디에도 `aidc_3d_linux_*.db`가 없어 기존 사용자 저장에는 영향이 없습니다. 이전 지문의 테스트 저장은 "catalog가 저장 당시와 다릅니다"로 거절되고 파일은 바뀌지 않습니다.
