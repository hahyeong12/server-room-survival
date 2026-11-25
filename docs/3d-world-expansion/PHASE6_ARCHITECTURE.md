# Phase 6 아키텍처 — 글로벌 고객·실무형 AI 업무·교대 근무 (Issue #7)

작성: 2026-11-25, Claude Code (Claude Opus 5.5). 상위 로드맵 Issue #4, 선행 Phase 5(Issue #6, `c6c0140`).
브랜치 `experiment/3d-global-operations-phase6` (시작점 `origin/experiment/3d-campaign-phase5` = `c6c0140`).

> 이 문서는 단계마다 갱신합니다. 1절은 작업 전 분석(커밋 1), 이후 절은 구현 결과입니다.

## 1. 작업 전 기준선과 확장 가능성 분석

### 1.1 기준선 (작업 전, 같은 PC에서 실행)

| 항목 | 명령 | 결과 |
| --- | --- | --- |
| Python 비GUI 회귀 | `python -m tests.run_headless` | 781/781 |
| 엔진 어댑터 | `python -m unittest discover -s engine/tests -t .` | 38/38 |
| JS 단위 | `npm.cmd test` | 38/38 |
| 보호 해시(작업 전) | `python scripts/protect_phase6.py before` | 사용자 데이터 579개 + 원본 소스 140개 기록, 원래 사용자 기준선 53개·기존 QA 기준선 508개 변경 0 |

Tk GUI 테스트(311개)는 사용자 지침(요청 없이 GUI 테스트 실행 금지)에 따라 이번에도 실행하지 않습니다.

### 1.2 현재 구조에서 국가가 규칙에 묶여 있는 곳

| 위치 | 현재 | Phase 6에서의 처리 |
| --- | --- | --- |
| `game.CUSTOMER_PLANS` / `WORK_TOTAL` / `REQUEST_WINDOWS` | 국가 이름(싱가포르·일본·미국)으로 자원·작업량·기한을 고름 | **그대로 둠.** 신규 요청은 모두 `scenario` 이름이 있으므로 이 표를 읽지 않습니다(`GameState.plans/work_total`, `request_terms`가 scenario 우선). |
| `game.request_conditions` | `country == '미국'`이면 유연형(두 모드 허용) | **최소 확장**: scenario에 `flexible` 값이 있을 때만 그 값을 사용. 기존 scenario에는 키가 없어 결과가 같습니다. |
| `session.GameSession.__init__` | 모드 `free/story/tutorial`만 허용 | **최소 확장**: 허용 모드를 클래스 속성 `MODES`로 옮겨 하위 클래스가 `global`을 추가. |
| `session.GameSession._persist` | 스토리일 때만 `mode/story` 저장 | **최소 확장**: `_extra_payload()` 훅(기본 `{}`)으로 글로벌 진행을 같은 `simulation_state` JSON에 저장. |
| `session.retry` | Chapter 3/3b가 아니면 scenario를 지움 | 글로벌 세션에서 재정의(재처리 차단·명시 메시지). 원본 수정 없음. |
| 3D `adapter.COUNTRY_CODES`, `world-store.COUNTRIES`, `network-data.REQUEST_PATHS` | 같은 국가 목록을 세 파일에서 수동으로 맞춤 | **단일 카탈로그**(`aidc/global_ops/catalog_v1.json`)에서 파생. 옛 `SG/JP/US` 코드는 카탈로그의 legacy 사이트로 유지(이전 저장·요청 ID 그대로). |

### 1.3 결정

- 새 고객 요청은 화면 데이터가 아니라 **기존 엔진 경로**로 처리합니다: `missions` 행(고객·업무) → `_receive`(조건·기한 고정, 요청 메시지) → `allocation_options`/`choose_plan`(동의·원장·서버 조각 검증) → `advance_time`(진행·기한·만료) → `_finish_if_needed`(반환·점수·고객 반응) → `_persist`(저장).
- 카탈로그의 업무 템플릿은 **버전이 붙은 새 scenario 키**(`global_v1:<templateId>`)로 `game.SCENARIOS`에 등록합니다. 기존 키는 재할당하지 않으며, 같은 버전 키의 내용은 테스트가 해시로 고정합니다(바꾸려면 새 버전 키).
- 글로벌 근무는 별도 저장(`aidc_3d_global_NNN.db`, 3D 저장 폴더)과 별도 모드(`global`)입니다. 정규 스토리 1~5장·튜토리얼·자유 운영·Lab의 수치와 순서는 바꾸지 않습니다.
- 새 장애 원인·Linux 명령은 Phase 7/8 범위입니다. 글로벌 근무의 장애 확률은 0이며(자원·동의·기한·경합이 이번 판단 대상), 이 사실을 화면과 문서에 적습니다.
