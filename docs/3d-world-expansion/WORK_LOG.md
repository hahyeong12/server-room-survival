# 3D 세계 확장 작업 기록 — Issue #1

범위: Phase 0~2. Phase 3 사용자 평가 전에 중단. 작업 브랜치 `experiment/3d-world-skeleton-001`.

## 시작 사실 확인 (2026-11-20 KST)

- 공식 지시: https://github.com/hahyeong12/server-room-survival/issues/1 (전체 본문 및 댓글 확인, 시작 시 댓글 0).
- 로컬 시작: `experiment/3d-datacenter-prototype-001`, HEAD `95cec7c`, 작업 트리·stash 비어 있음. `4de7bb2` 선행 점검 커밋 유지.
- 원격 읽기 전용 `git ls-remote --heads origin`: main `d46671a0f7b4e7304e2d78ea18c4a1743a5dfc0e`만 존재. 로컬 실험 브랜치는 실제 존재하며 새 브랜치가 이를 계승함. push·merge·reset 없음.
- Node `26.13.1`, npm `11.20.0` (`npm.cmd` 사용). 기존 Three.js 0.180.0 / Vite 7.3.8 / Playwright Core 재사용. 새 프레임워크·의존성 설치 없음.
- AGENTS·헌장·결정 기록·학습 설계·로드맵·README·CHANGELOG와 실제 시제품 코드 확인.
- 실행 에이전트: Codex / GPT-6 계열(시스템 제공 식별). 현재 루트 세션의 정확한 모델·추론 설정을 전환하거나 GPT-6.1 Sol / High 사용을 검증하는 API가 없어 권장 모델 사용을 주장하지 않음.
- Claude Code: PATH와 사용자 표준 `.local/bin`, npm 전역 shim, `.claude/local` 설치 경로에서 실행 도구 미발견. 임의 설치·로그인 없이 독립 리뷰 미실행으로 기록. 인증 파일 내용은 조회하지 않음.

## Phase 0 — 감사·설계·시각 자료

- 기존 460줄 `src/scene.js`: 24랙·UPS·CRAC·코어·관제실, 인스턴싱, 절차적 텍스처, OrbitControls, PBR 환경·SSAO·bloom·FXAA, 레이캐스트와 선택 테두리, 비동기 GPU 타이머를 재사용.
- `src/model.js`의 장비·센서·장애 상태와 `tests/model.test.mjs` 유지. 이전 `src/main.js`의 자동 6초 복구는 독립 실험실에만 남기고 세계 시연은 명시적 클릭으로만 처리.
- 기존 QA 캡처·측정 기록은 보존하고 신규 결과로 재사용하지 않음. 기존 정상 736 전체 pass draw calls는 새 장면의 성능 기준선 참고일 뿐 새 실측 아님.
- 렌더러/장면을 하나만 생성하고 각 공간을 Group으로 전환. 관제실은 기존 공간의 운영자 중심 시점을 재사용. 새 세계지도·단지는 같은 렌더러에 연결.
- 정보 구조·상태 계약·참고 출처는 DESIGN.md / REFERENCES.md 참조.

## 커밋과 검증

아래에는 완료한 작업, 실제 검증 명령, 커밋 SHA를 순서대로 누적합니다. 현재 커밋 자체의 SHA는 다음 기록 또는 최종 QA 보고서에서 보충합니다.

### 설계 기준선 완료

- `npm.cmd test`: 기존 모델 6 PASS.
- 실제 Chrome headed 1920×1080: 28장비(24랙), D-06 Canvas 클릭, 관제실 시점 전환 PASS, runtime error 0. `qa/baseline.json`, `qa/00-baseline-noc.png`에 신규 실행 증거 보관.
- `python docs/3d-world-expansion/protect.py before`: 751개 해시 기준선 생성. DB 연결 없음.
- NOC, Google 단지 항공·냉각 배관 사진을 실제 이미지로 열어 배치·조명·정비 통로 분석. Google의 축소 URL 두 건은 404여서 갤러리 원래 URL로 다시 확인 성공. 사진은 OS 임시 폴더에만 저장하며 Git/제품에는 없음.
- 다음: 세계지도·공통 상태/라우팅 → 관제실·단지 → 서버실 연결 → SG 세로 시연 → 회귀·성능·독립 리뷰 가용성·최종 보고.

### 세계 뼈대와 내비게이션

- 설계 기준선 커밋: `faec783`.
- 원본 HTML을 `lab.html`로 보존. 기존 `scene.js`에 선택적 world mode를 추가하고 같은 renderer/composer/기존 geometry를 재사용. 기존 `model.js`, `main.js`는 변경하지 않음.
- Natural Earth 육지 윤곽·가상 연결·국가 거점, 자체 시설 단지, 기존 NOC/서버실을 공통 경로·breadcrumb·상위 복귀로 연결. 모든 화면에 시연 표시와 동일 ID·원래 조건 제공.
- `node --test tests/model.test.mjs tests/world-store.test.mjs`: 9 PASS.
- `node scripts/world-qa.mjs --phase1`: 실제 Chrome headed 6 PASS. 네 공간 이동·대기 후 domain 동일, breadcrumb/복귀·세계 거점 Canvas 클릭·시설 선택·D-06 Canvas 클릭·오류 없음. 신규 장면 캡처 4장 보관.
- `npm.cmd run build`: 성공(Three.js 크기 안내만). lab도 빌드 입력에 포함.
- QA 최초 시도는 실행 전 로컬 서버 종료를 발견: 지도 파일 다운로드 순간 Vite watcher EBUSY로 중단. 다운로드 완료 후 같은 서버 재시작해 통과. 게임 회귀가 아닌 개발 서버 파일 감시 오류로 분리.
- 다음: NOC 시점과 시설 초점 조작 다듬기 → SG 단계별 버튼·검증.

### 관제실·시설 탐색 다듬기

- 세계 뼈대 커밋 `085020e`.
- NOC 카메라를 운영자 눈높이에 가깝게 낮춰 천장 조명이 화면 벽을 가리던 구도를 개선. 기존 관제실 geometry·모니터 월·운영석 재사용.
- 세계 거점 및 관제/서버/전력/UPS/냉각/네트워크 시설에 선택 초점 이동 추가. 시설 선택은 원래 요청 조건·시간·진행을 변경하지 않음.
- `node --test tests/world-store.test.mjs`: 3 PASS. `npm.cmd run build`: 성공.
- 실제 Chrome: NOC 시점 캡처, 냉각 시설 선택·초점 이동·domain 불변 PASS. `qa/facility-focus.json`, `noc-operator.png`, `campus-cooling.png` 보관.

## Claude Code 인계·독립 리뷰·Phase 2 마무리 (2026-11-20 KST)

- 실행 에이전트: **Claude Code (VS Code 확장) / 모델 Claude Opus 5.5 (`claude-opus-5-5`)**. 추론(effort/thinking) 수준은 세션 설정을 따르며 에이전트 내부에서 정확한 값을 조회할 수단이 없어 '확인 불가'로 기록합니다. 위 시작 기록의 "Claude Code 미발견·리뷰 미실행"은 Codex 시점의 사실이며, 이 절부터 Claude Code가 실제로 리뷰·구현했습니다.

### 인계 시점 상태 (Codex가 사용량 한계로 중단)

- 브랜치 `experiment/3d-world-skeleton-001`, HEAD `db8d272`. worktree 1개, stash 없음. 다른 작업 트리 없음.
- 미커밋: SG 시연 흐름 전체(`src/demo-actions.js`, store `act()`, 패널 단계 버튼, 서버실 요청 랙 표시, 시설 라벨, 테스트 `tests/demo-flow.test.mjs`, QA 스크립트 확장, `package.json` 스크립트)와 QA 결과물.
- Codex 마지막 QA: 세계 QA `finish` 단계 locator 시간 초과, 실험실 회귀 레이어 토글 실패. **재실행 시 둘 다 재현되지 않아(세계 7/7, 실험실 15/15)** Codex가 QA 실행 중 소스를 수정하여 Vite가 페이지를 다시 읽은 일시적 실패로 판단합니다. 실패 증거는 `qa/world-qa-attempt1.json`, `qa/lab-regression-attempt1.json`으로 보존합니다.
- Codex의 dev 서버(20:09 시작, 같은 폴더)를 종료하지 않고 그대로 사용. 미커밋 파일 34개는 수정 전 세션 임시 폴더에 백업한 뒤 작업했습니다.

### 독립 리뷰 결과와 조치

| 발견 | 판단 | 조치 / 커밋 |
| --- | --- | --- |
| Codex 미커밋 SG 흐름 | 단일 store·클릭 전용·잘못된 단계/장소/국가/랙 거부 구조가 설계 계약과 일치. 재작성 불필요 | 원형 보존 커밋 `7422eba` |
| `index.html` 제목·설명이 실제 `?` 바이트로 저장(커밋 `085020e`) | 브라우저 탭 제목 손상 | 복구 `49b5759` |
| 세계지도 SG 거점·경로가 매 프레임 청록으로 덮여 범례의 금색 "요청" 알림이 보이지 않음 | 요청 발생 알림 누락 | new/reviewed 금색·맥동, 이후 단계색 `49b5759` |
| 요청 카드 조건·처리 위치가 HTML에 하드코딩 | 단일 상태 원칙 위반(중복 진실) | `state.request`에서 렌더 `49b5759` |
| 관제실 결과 확인이 한 줄 텍스트 | Phase 2 "관제실 결과 확인" 부족 | 기록된 history 기반 결과 카드·요청함 단계 표시 `21cde91` |
| 세계 QA `performance: []` | FPS 미측정 상태 | 장면별 FPS/p95/GPU/draw call·10회 반복 이동 자원 검사 `45d4854` |

리뷰에서 문제없음으로 판단한 항목: 렌더러·composer 하나를 공유하고 Group 가시성만 전환(반복 이동 후 geometry 469·texture 69 불변), 시각 시간과 도메인 시간 분리, 기존 `model.js`/`main.js` 미변경, 실험실 원본 보존, Natural Earth(Public Domain)만 외부 데이터로 사용.

### 검증 (모두 이 세션에서 실제 실행)

- `node --test tests/*.test.mjs`: **13 PASS / 0 FAIL** (모델 6, 세계 store 3, SG 흐름 4).
- `node scripts/world-qa.mjs` (실제 Chrome 157 headed, 1920×1080 DPR1, CDP 마우스·키보드): **10 PASS / 0 FAIL** — `qa/world-qa.json`.
- `node scripts/browser-qa.mjs --url=…/lab.html` (기존 실험실 회귀): **15 PASS / 0 FAIL** — `qa/lab-regression/browser-qa.json`.
- `npm.cmd run build`: 성공 (three 청크 500 kB 초과 안내만).
- `python docs/3d-world-expansion/protect.py after`: **751개 해시 동일**, differences 없음 — `qa/protection-result.json`. Python/SQLite/스토리 슬롯 파일 변경 없음.
- 성능 상세는 [QA_REPORT.md](QA_REPORT.md).

### 미실행·한계

- GitHub Issue #1 댓글: 이 환경에 `gh` CLI가 없고 인증 수단을 임의로 설치·로그인하지 않아 **미게시**. 게시용 요약은 최종 보고에 포함.
- 물리 마우스·실제 Windows 배율 변경·사람의 플레이 평가는 자동 QA와 별개이며 Phase 3 사용자 평가 대상.
- 원격 Push·main 병합 미실행(승인 전 보류).
