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

## 2026-11-28 재개 → 최종 검증 완료 (작업 마감)

### 재개 후 커밋
| 커밋 | 내용 |
| --- | --- |
| `d99f9e1` | 3차 독립 재리뷰 결함 3건·의심 2건 수정(동의·배치 축소 10분 올림 `ceil10`, 평가 v3 정책 목록·모든 출처 첫 답, 자유 지문에 평가 지문, 선임 슬롯 열기 실패 정리). 마지막 게임·엔진 코드 커밋 |
| `b80aeef` | QA: Linux 추론의 BMS 보완 관측, UX 보완 QA `phase9-ux-qa.mjs`, 공용 흐름 `phase9-flows.mjs` |
| `9a04394` | QA: 같은 가상 분에 이미 있는 BMS 관측은 다시 요청하지 않음 |
| `11479b8` | QA: 정책 위반 거부로 정직한 선임 실패, seed 변화 QA `phase9-seed-qa.mjs` |
| `77757a9` | QA: 재도전 원본 바이트 검사 순서(표시 기록 먼저, Phase 8과 같음) |
| (이 기록 커밋) | `QA_REPORT_PHASE9.md`, 리뷰/아키텍처/작업 기록/AGENTS 인계, QA 증거(JSON·로그·PNG, DB 없음) |

### 최종 결과 (상세: `QA_REPORT_PHASE9.md`)
- Phase 9 주 UI `cc-final-2` 9/9, seed `cc-seed-1` 4/4, UX `cc-ux-3` 9/9 — 모두 최종 게임 코드, 오류 0.
- 직렬 회귀 `cc-final` 10/10: Phase8 13/13·Phase7 12/12·Phase6 16/16·Phase5 9/9·Phase4 13/13·lab 15/15·Python 976/976·adapter 58/58·JS 53/53·build.
- 보호 해시 1,482개 변경 0. Tk GUI 311 미실행.
- 실패/중단 실행 `cc-full-1~4`·`cc-final-1`·`cc-ux-1~2`는 모두 QA 스크립트 원인이며 보고서 5절에 분리 기록.

### 정리
- 분리 검증 worktree 2개(`scratchpad/review-wt` = `d99f9e1` 내용, 이전 `scratchpad/wt` = `a922a7b` 내용)를 커밋 코드와 파일 단위 동일 확인 후 `git worktree remove`.
- 기존 미추적 Phase7/8 PNG는 이전 Phase 산출물이라 stage하지 않음.

### GitHub 댓글 (도구 없음 → 본문 보존)
`gh` 미설치, 자격 증명 토큰 사용은 권한 확인에서 거부되어 시도하지 않았습니다(설치·로그인 하지 않음). 아래 본문을 사용자가 직접 게시할 수 있습니다.

#### Issue #10 최종 보고 (게시용 본문)
```
## Phase 9 최종 검증 완료 보고

브랜치 `experiment/3d-growth-balance-phase9` (마지막 게임 코드 `d99f9e1`, 이후 QA 스크립트·문서만 변경)

### 구현
- P0 `FreeShiftSession`: 글로벌 자유 교대에 seed + 난도(무사건/편안한/표준/도전)로 기존 사건 10종을 가상 10분 경계에서 추첨. 버전형 `free_incidents` JSON v1(규칙 지문·cursor·이력), 재시작·새로고침·지연 응답·이중 클릭에도 중복/유실/재추첨 없음. [교대 마무리·결과 보기], 자유 결과는 진급 미반영.
- P1 `career.assess()` 운영/학습 분리 평가(v3), `SeniorSession` 선임 평가 2교대, 경력 지도(신입→담당→선임 직무와 교육 수료 분리), 엔딩.
- P2 `OperatingRules`: 임시 우회(짧은 정지+감속 운전) vs 근본 조치(긴 정지+정상 속도). 감속은 서버 원장 기준으로 진행률·완료 시각에 반영.

### 검증 (최종 코드)
- Chrome 실제 UI: Phase 9 주 9/9, seed 변화 4/4(seed 91/3/17/2026 서로 다른 사건, 7종 도달, 같은 seed 재현 동일), UX 9/9(1366×768·1920×1080·150% 에뮬 2종, 키보드, 지연 응답+새로고침, 마무리 이중 클릭, 정직한 선임 실패→새 슬롯 원본 불변, 엔딩)
- 회귀: Phase8 13/13, Phase7 12/12, Phase6 16/16, Phase5 9/9, Phase4 13/13, lab 15/15, Python 비GUI 976/976, adapter 58/58, JS 53/53, build
- 보호 파일 1,482개 변경 0. Tk GUI 311 미실행.

### 독립 리뷰
2차 7건(`a922a7b`), 3차 결함 3건+의심 2건(`d99f9e1`) 수정, 각 회귀 테스트는 수정 전 코드에서 실패 확인.

### 남은 위험 / Phase 10 인계
- 무시된 사건은 근무를 끝내지 않음(Phase 7 기존 규칙)
- Phase 7 사건/Linux 동의 판정의 내림 식 유지(Phase 9 덧층만 수정)
- 공유 범위 사건 자유 적격성, 감속형 사건 완료 시각 동일 가능
- 150%는 Chrome 에뮬레이션, 사람 플레이 테스트 미실시

상세: docs/3d-world-expansion/QA_REPORT_PHASE9.md, REVIEW_PHASE9.md
```

#### Issue #8 검증 결과 (게시용 본문)
```
## Phase 7 미구현 항목(글로벌 자유 운영 seed/난도 사건) — Phase 9에서 구현·검증

Phase 7 QA 보고서 6절에 미구현으로 남겼던 "자유 운영에는 설정된 난도/선택적 seed 난수로 사건" 항목을 Phase 9 (#10) P0로 구현했습니다.

- 구현: `aidc/global_ops/free_session.py` `FreeShiftSession` — 새 글로벌 자유 교대만 seed + 난도로 기존 10종 사건을 가상 10분 경계에서 추첨(`random.Random(f'{seed}:free-incidents-v1:{cursor}')`), 버전형 저장 블록, 브리핑 전 변이 잠금, 동시 상한·간격, 기존 자유 저장은 사건 없이 기존 규칙 그대로.
- Python: 같은 seed·같은 행동 → DB 동등, 10종 도달·seed별 차이, 재시작 후 일정·영향 동일, cursor 원자성/롤백, 같은 틱 중복 불가·중첩 상한, 무사건, 마무리 후 신규 사건 없음.
- Chrome 실제 UI: seed 91/3/17/2026 도전 난도에서 서로 다른 사건(7종 도달)을 진단·복구·사후 확인·보고로 종료, 같은 seed 재실행 동일, 진행 중 엔진 재시작 이어하기, 지연 응답 중 새로고침에도 시간·추첨 1회, 마무리 이중 클릭 멱등.
- Phase 7 회귀 12/12, Phase 6 16/16 등 최종 코드 전체 회귀 통과.

Phase 7 보고서에 남은 다른 한계(명령어 예시 → Phase 8에서 가상 명령 구현, 150% 에뮬레이션, Tk GUI 미실행)는 이 Issue의 필수 QA 범위를 막지 않는 기록입니다. 이 Issue의 미구현 항목이 해소되었으므로 닫아도 된다고 판단합니다(최종 결정은 저장소 소유자).
```

### Issue #8 판단
Phase 7 QA 보고서가 #8에서 유일하게 '미구현'으로 남긴 항목이 seed 기반 자유 사건이었고, Phase 9에서 Python·브라우저 증거로 충족했습니다. **닫기를 권고**하지만, 댓글/닫기 도구가 없어 실제로 닫지 않았습니다.

### Phase 10 인계
- 사용자 결정 필요: 무시된 사건의 근무 종료 규칙, Phase 7 동의 내림 식 수정 여부, Windows 실제 150% 배율 확인, 사람 플레이 테스트(재미·난도), Tk GUI 311 실행 여부.
- 사용자 요청 없이 Phase 10을 시작하지 않습니다.
