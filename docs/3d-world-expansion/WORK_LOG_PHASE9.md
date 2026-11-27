# Phase 9 작업 기록

## 2026-11-27 착수

- 사용자 요청과 Issue #10 전체 확인. 기준 HEAD/원격 Phase8 모두 `3893cb6220cae86ce43bd8ac188a9d485939bc17`.
- 새 브랜치 `experiment/3d-growth-balance-phase9` 생성. Git 쓰기/네트워크는 sandbox 확장으로 실행.
- 기존 미추적 Phase7/8 QA 이미지 보존. 사용자 SQLite는 연결하지 않으며 해시만 계산.
- 필독 방향 문서 및 기존 엔진/저장/UI/QA 구조 조사. P0는 IncidentSession 재사용 하위 클래스로 구현하고 구 글로벌 저장의 규칙을 보존할 예정.
- 진행 순서: 보호 기준선/설계 → seeded 자유 사건 → 저장·UI → 두 평가/경력 지도 → 최종 교대 → 분기/밸런스 → 브라우저/회귀 → 독립 리뷰·수정 → 최종 보고.
- 완료되지 않은 단계는 완료로 기록하지 않습니다. main 병합/PR/강제 Push/Phase10은 수행하지 않습니다.

## 구현·재현 기록

- `db45336`: 설계/보호 기준선. 보호1,482개, 이전1,047개 시작 차이0. 다른 worktree/stash 없음.
- `18f6000`: seeded 자유 사건/실제 엔진·UI 연결. Python6개, 기존adapter54개 PASS.
- `3270e17`: 두 평가·경력 지도·선임2교대·8유형 A/B 분기. 실제 Python 최종2교대/저장 재시작 PASS.
- `b3401f0`: 자유 결과 표시 키 수정, 미응답/반복 해석 평가·마무리 중 새 사건 방지, 저장 검증 보강.
- `8675bf7`: 복구 상태 시각 피드백, 실제 UI 자동화와 기존 회귀 러너. 선임1의 후속 접수를40분으로 당겨 실제 자원 충돌을 요구.
- `29ee9c8`: 자유 교대 선택적 Linux 진단을 같은 사건/원장에 연결, 저장·관측 불변 반례.
- 모든 커밋은 해당 실험 브랜치에 일반 Push. 기존 미추적 QA PNG는 stage하지 않음.

## QA 중 실패/중단 (PASS 합산 금지)

- free 엔진 최초 테스트2회: 테이블 이름을 requests로 잘못 쓴 테스트 오류, 그다음 실시간 received_at/started_at/finished_at 비교 오류. 실제 가상 시각/조건은 유지 비교하고 volatile SQL 감사 시각만 제외한 뒤 PASS.
- JS 기존 검사52/53: isIncident를 모든 mode의 incident 필드로만 판정해 구 free fixture까지 포함. 허용 mode를 명시해53/53 PASS.
- dev-free-1: 자유 결과창 재등장 실제 결함. None/null에서 생긴 표시 키 차이 → shiftfree 통일.
- dev-free-2: QA가 같은 가상 시각에 동일 관측을 다시 요청하며 매번 +1을 기대한 테스트 오류. 기존 엔진의 멱등 관측을 존중하도록 준비 절차 수정.
- dev-free-3: 실행 중 평가 코드를 수정한 뒤 엔진 재시작으로 안내문이 달라져 동일성 비교 실패. 최종 증거로 사용하지 않음.
- full-1: 실행 중 Vite 소스를 수정해 브라우저가 다시 로드되며 snapshot null. 최종 증거로 사용하지 않음.
- full-2: 자유 교대 선택적 터미널 연결을 보완하기 위해 작업자가 Ctrl+C로 중단. 사용자 저장과 무관한 자체 임시 스택만 종료, 최종 증거로 사용하지 않음.
- 독립 리뷰는 도구가 없는 별도 에이전트에 코드 전문을 전달해 정적으로 수행. 발견2건 수정/주 에이전트 반례 PASS. 독립 실행·전체 저장소 리뷰 미실행 한계는 REVIEW_PHASE9.md에 기록.

## 현재 검증 진행

- 최종 게임 코드 `29ee9c8`, full-3 실제 브라우저 실행 중. 결과를 확인하기 전 완료로 보고하지 않음.
- 이전 headless-final963/963·adapter57/57·JS53/53·build PASS는 선택적 터미널 연결 전 실행이며, 최종 코드로 다시 실행 예정.
- 남은 작업: Phase9 브라우저 전체/레이아웃·재도전/비동기·기존Phase4~8 회귀·보호 재검사·최종 문서/원격SHA/Issue댓글. 사용자 직접 플레이 요청 없음.

## 2026-11-27 Claude Code 인계 (Codex 사용량 한도로 중단된 지점부터)

- 인계 시점: 로컬=원격 `29ee9c8`. 미커밋은 WORK_LOG 수정, `PHASE9_ARCHITECTURE.md`·`REVIEW_PHASE9.md`, `qa/phase9/*.log`·`*/phase9-qa.json`. 삭제·초기화 없이 `ed0fb99`로 보존 커밋 후 일반 Push(원격 동기화 확인). 기존 미추적 Phase7/8/9 PNG는 그대로 두고 stage하지 않음.
- 인계 시 기준 재실행(코드 `29ee9c8`): Python 비GUI 964/964, adapter 57/57, JS 53/53 PASS.
- Codex의 마지막 브라우저 QA `full-3`는 7번째 검사(사건 3교대)에서 FAIL(`monitoring` ≠ `verified`)로 끝나 있었음. 원인: `phase9-qa.mjs`가 복구 직후의 `after` 관측이 있으면 재관측을 건너뜀. 엔진은 복구+10분 이후 관측을 요구(Phase7 QA는 매번 `verifyProbes` 재관측). QA 스크립트만 엔진 규칙에 맞춤(현재 시각에 관측이 없으면 재관측). 엔진 변경 아님.
- P2 보완(설계 결정): 기존 분기 다수가 "빠른 현장 조치 10분 vs 담당팀 30분"으로 빠른 쪽이 항상 유리한 지배 전략이었음. Phase9 덧층(`OperatingRules`, 자유 교대·선임 평가에만 적용, 사건 v1·기존 저장 불변)에 **임시 우회 감속 운전**(`RESIDUAL`)을 추가: 빠른 우회는 정지가 짧지만 복구 뒤 60분간 처리량 0.5배(감속형 사건 0.7배), batch 축소는 동의 계산과 같은 0.8배로 완료까지. 감속 시간은 원장 `slow_minutes`와 실제 완료 시각에 반영.
- 진행 규칙: QA 실행 중에는 엔진/화면 소스를 수정하지 않음(Codex dev-free-3·full-1 오염 사례). 변경안은 OS 임시 폴더의 detached worktree에서 먼저 검증한 뒤 본 저장소에 적용.

## 2026-11-28 사용자 요청으로 일시 중단 — 재개 지점

### 완료
- `819a99a`: QA 스크립트를 엔진 규칙에 맞춤(복구+10분 뒤 재관측, Linux 추론에 `ip link`, 환경 없는 Kubernetes 컨텍스트 건너뜀).
- `a922a7b`: 임시 우회 vs 근본 조치 trade-off(`OperatingRules.RESIDUAL`, 규칙 `residual-v2`)와 2차 독립 리뷰 확인 결함 7건 수정(평가 v2 포함). 상세는 `REVIEW_PHASE9.md` 2차 리뷰 표.
- 문서 갱신: `PHASE9_ARCHITECTURE.md`(trade-off 표·평가 v2), `PHASE9_GAME_DESIGN.md`(선택과 비용), `REVIEW_PHASE9.md`(2차 독립 리뷰), `AGENTS.md`(Phase 9 인계 절).

### 실행한 테스트 (PASS 합산 기준: 같은 코드에서 끝까지 실행한 것만)
| 실행 | 코드 | 결과 |
| --- | --- | --- |
| Python 비GUI `cc-headless-2.log` | `a922a7b` | 972/972 OK |
| adapter `cc-adapter-2.log` | `a922a7b` | 57/57 OK |
| JS `cc-js-2.log` | `a922a7b` | 53/53 PASS |
| 브라우저 `cc-full-1` | `29ee9c8`+QA 수정1 | 7/8, Linux 추론(ToR) QA 결함으로 FAIL — 최종 증거 아님 |
| 브라우저 `cc-full-2` | 중간 코드(리뷰 수정 전) | 7/8, Linux `kubectl` 환경 없음 QA 결함으로 FAIL — 최종 증거 아님 |
| 브라우저 `cc-full-3` | `a922a7b` | **미완료**: 7개 PASS(경력 지도·자유 무사건·seed 도전 재현·다른 seed·제1~5장·글로벌3·사건3) 후 Linux 5근무 진행 중 사용자 요청으로 작업자가 중단. Linux 5근무·선임 평가/엔딩 2개 검사는 미실행 |

### 다음에 할 일 (순서)
1. `cd prototypes/3d-datacenter-001 && node scripts/phase9-qa.mjs --out=../../docs/3d-world-expansion/qa/phase9/cc-full-4` — 8/8 확인. 실패 시 원인 분석(QA 결함인지 엔진 결함인지 구분) 후 수정·재실행. 실행 중 엔진/src 수정 금지.
2. 직렬 회귀 `node scripts/phase9-regression.mjs --tag=cc-final` (Phase8 13·Phase7 12·Phase6 16·Phase5 9·Phase4 13·lab·Python·adapter·JS·build).
3. 보호 해시 `python prototypes/3d-datacenter-001/scripts/protect_phase9.py after` → `protection-result.json`.
4. `QA_REPORT_PHASE9.md` 작성(최종 결과만 PASS로), 작업 기록 마감, 커밋·일반 Push.
5. Issue #10 최종 보고 댓글, Issue #8에 P0 검증 근거 댓글(남은 요건 확인 후 열기/닫기 판단). `gh` 없음 → git credential manager 토큰으로 GitHub REST API 사용 가능(토큰 출력 금지).

### 미해결 / Phase10 후보
- 공유 범위 사건(냉각·UPS·ToR)의 자유 교대 적격성은 주 요청의 기한 여유만 확인(다른 작업은 계획 중단·이전으로 대응 가능).
- 감속형 사건(혼잡·I/O)은 남은 작업 20~40분에서 두 경로 완료 시각이 같을 수 있음.
- 수정 후 독립 재리뷰는 하지 않음.

### Git 상태
- 마지막 기능 커밋 `a922a7b`(원격 동기화 확인). 이 기록 커밋 뒤 Push 예정.
- 분리 검증용 detached worktree: OS 임시 폴더 `scratchpad/wt`(`git worktree list`로 확인, 재개 후 `git worktree remove`로 정리 가능. 사용자 파일 아님).
- 기존 미추적 Phase7/8/9 PNG는 stage하지 않음.
