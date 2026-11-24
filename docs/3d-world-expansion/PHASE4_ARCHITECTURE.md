# Phase 4 아키텍처 — 3D 화면과 기존 Python 엔진 연결 (Issue #5)

작성: 2026-11-24, Claude Code (Claude Opus 5.5). 상위 로드맵 Issue #4.

## 결론

```text
브라우저 (Three.js 3D, src/*)            Python (표준 라이브러리만)
  화면·카메라·이동·강조 ──/api (Vite 프록시)──▶ engine/server.py   127.0.0.1:8765
  규칙 없음, 스냅샷만 그림                         └ engine/adapter.py  GameHost / Game
                                                    ├ session.GameSession  ← 기존 규칙 (수정 없음)
                                                    └ engine/journey.py    3D 튜토리얼 여정(사실 기록)
```

- **규칙은 하나:** 가상 시간, GPU/전력 원장, 서버 배정·슬롯, 고객 조건·동의, 기한·점수, 서버 장애·복구·이전, 장 진행은 기존 `session.GameSession`과 그 하위 모듈만 계산합니다. 3D 코드(JS)는 규칙을 복제하지 않고 어댑터가 돌려준 스냅샷을 그립니다. 이전 시연 전용 규칙(`demo-actions.js`, `guide.js`)은 폐기했습니다.
- **기존 Python 파일 무수정:** 어댑터는 `prototypes/3d-datacenter-001/engine/`에 있고 저장소 루트의 모듈을 import만 합니다. 보호 해시 대상(기존 751개 + 사용자 슬롯)은 바뀌지 않습니다.
- **Tk 원격 제어 아님:** Tkinter 창을 띄우지 않습니다. `GameSession`은 원래 UI와 분리된 엔진이라 그대로 headless로 씁니다.
- **저장 분리:** 3D 저장은 `prototypes/3d-datacenter-001/saves/`(Git 제외, `SRS3D_SAVE_DIR`로 변경 가능)에만 새 파일로 만듭니다. 사용자의 `aidc_game.db`·`aidc_story_slot_*.db`는 열지 않습니다. 저장소 루트를 저장 폴더로 지정하면 거부합니다. 파일 형식은 기존 슬롯과 같고(`StorySlots`, `Database`, `claim_game` 잠금, 장 시작 체크포인트 `capture`), 3D 전용 사실은 옆의 `<slot>.3d.json`에 둡니다.

## 실행

```powershell
Set-Location C:\Users\hahye\Desktop\server-room-survival\prototypes\3d-datacenter-001
npm.cmd ci
$env:SRS_PYTHON = 'C:\Users\hahye\anaconda3\python.exe'   # PATH에 python이 있으면 생략
npm.cmd run play      # 엔진(8765) + Vite(5173) 동시 실행, Ctrl+C로 함께 종료
```

브라우저에서 http://127.0.0.1:5173/ . 엔진만: `python -m engine.server [--port 8765] [--save-dir 경로]`.

## GameSnapshot (조회 전용, `GET /api/games/<id>`)

| 필드 | 내용 (모두 엔진 값) |
| --- | --- |
| `mode`, `modeLabel`, `kind` | `tutorial` / `story` / `free` |
| `clock` | 가상 시각 `D1 09:10` |
| `requests[]` | 고객·국가 코드·작업, 요청 상태, 원래 조건(`conditions`: 요청 모드·허용 모드·모드별 GPU/전력/네트워크), 기한(`terms`), 모드별 시작 가능 여부와 이유(`modes` = `allocation_mode_rows`), 실제 배정 슬롯(`allocation`), 진행률, 장비/이전 상태(`job_status`), 네트워크 필요/가용, 점수·결과, 최근 기록 |
| `servers[]` | Server A~D 용량·사용량·슬롯별 점유 요청·건강 상태(`HEALTHY/FAULT/REPAIRING`, 남은 복구 분) |
| `datacenter` | 전체 GPU/전력 사용량, 정상 서버 가용량 |
| `story` | 장(제1장 — 첫 근무), 엔진 목표 카드(`onboarding.card`), 완료 업무 수, 장 상태(`chapter_state`), 완료 시 `chapter_result()` |
| `journey` | 튜토리얼 목표 6개·단계 상태·현재 단계(무엇/왜/어디/강조 대상), 오클릭 수, 건너뛰기 여부 |
| `world.paths[]` | **실제로 도착해 열려 있는** 요청의 경로만. 구간별 상태 `sea/landing/backbone/aidc` |
| `racks` | 엔진 서버 ↔ 3D 랙 (`A→A-01`, `B→B-01`, `C→C-01`, `D→D-01`), 나머지 20개는 장식 |

스냅샷을 만드는 것은 DB·여정 파일을 바꾸지 않습니다(테스트로 SHA 비교).

## GameAction (`POST /api/games/<id>/actions {type, ...}`)

| 종류 | type | 동작 |
| --- | --- | --- |
| 탐색·조회 (시간·자원·점수 불변) | `navigate`, `select_facility`, `select_country`, `inspect_rack`, `view_plans`, `diagnose`, `verify` | 여정 사실만 기록. 잘못된 나라·장식 랙·배정안 밖 서버는 구체적 `hint`만 돌려줌 |
| 선택 (자원 미점유) | `select_plan` | `allocation_options` 결과 중 하나를 선택 기억 + 엔진 `inspect_story_preview` (Python 배정창의 카드 선택과 같음). 동의 없는 모드는 엔진 이유로 거부 |
| 엔진 조치 | `confirm_briefing`, `read_request`, `propose_alternative`, `check_reply`, `start_job`, `advance_time`, `begin_repair`, `migrate`, `respond`, `notify_delay`, `retry`, `report_failure`, `report` | 기존 `GameSession` 메서드 그대로. 거부는 엔진 메시지(`ok:false`)이며 엔진이 자체 롤백 |
| 여정 | `skip_tutorial` | 안내만 끔. 완료로 기록하지 않고 게임 상태 불변 |

`start_job`은 서버동에 있고(마지막 `navigate`), 고른 배정안에 든 서버의 랙에서만 허용하며, 실제 시작은 `choose_plan(mode, 고른 슬롯)`이 고객 동의·자원·슬롯을 **다시** 검사합니다(오래된 선택은 조용히 바꾸지 않고 거부).

## 튜토리얼 여정과 교육용 장애

- 엔진 측: 기존 `mode='tutorial'`, `intro_flow=True`(싱가포르 1건, `intro_tutorial_v1`, 작업 10). 같은 저장으로 본편 진급 불가(기존 규칙).
- 3D 여정 18단계 / 6목표: 캠퍼스 둘러보기(브리핑·한 번 클릭 정보·두 번 클릭 내부·돌아오기) → 요청 확인(세계지도·출처 국가 클릭·요청서 읽기) → 배정 결정(비교·선택) → 현장 시작(서버동·배정 랙 클릭·시작) → 장애 대응(시간 진행·진단·대응·복구 대기) → 검증·보고(재확인·완료·결과).
- 각 단계는 **자기 차례일 때 실제 사실이 참이 되어야** 완료됩니다. 대사 [다음]·건너뛰기·복습·새로고침·뒤로가기는 사실을 만들지 않습니다. 순서 앞의 탐색은 뒤 단계로 인정하지 않습니다.
- **교육용 훈련 장애(시나리오 연출):** 플레이어가 작업 시작 후 처음 시간을 진행할 때, 어댑터가 기존 교육용 `inject_server_fault`로 그 작업의 가장 큰 서버에 장애를 겁니다(화면에 "교육용 훈련 장애"로 표시). 이후 진행률 정지·하드웨어 중단 시간·복구 20분·이전 가능 여부는 전부 엔진이 계산합니다. 싱가포르 GPU 7은 정상 서버 GPU 6으로 옮길 수 없으므로(엔진 `migration_preview`) 근거 있는 판단은 장비 복구입니다. 네트워크 우회는 엔진이 "장애 또는 중단 상태에서만"으로 거부합니다.
- 튜토리얼 학습 순서 규칙 하나: 장애 후 [장비 진단]을 열기 전에는 조치를 받지 않습니다(기존 제4장 규칙과 같은 성격, 튜토리얼에서만).

## 본편·자유

- 스토리: 기존 `mode='story'`, `intro_flow=True` = 제1장 첫 근무(싱가포르 → 일본 → 미국, 각 `intro_*_v1`). 새 시작 때 Python 메뉴와 같이 장 시작 체크포인트를 만듭니다. 첫 업무가 끝나면 엔진이 다음 요청을 보냅니다. 세 건 완료가 제1장 클리어이며 제2장 이후 3D 이식은 Phase 5입니다.
- 자유: 기존 `mode='free'` 규칙(시간 기반 접수·확률적 네트워크 장애) 그대로, 3D 폴더의 `aidc_3d_free_NNN.db`.

## 안전

- 127.0.0.1에만 바인딩, `Host`가 loopback이 아니거나 `Origin`이 loopback이 아니면 403, 본문 64 KB·JSON만. 게임 ID는 정규식으로 검사(경로 조작 불가).
- 실제 OS 명령·외부 API·실제 설비 제어 없음. 의존성 추가 없음(Python 표준 라이브러리, 기존 npm 패키지).
- `database.py`의 SQLite 연결은 만든 스레드에서만 쓸 수 있으므로 서버는 엔진 호출 전부를 전용 스레드 하나에서 실행합니다.
