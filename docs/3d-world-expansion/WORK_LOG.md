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

## Phase 3.1 — Issue #2 사용자 플레이 피드백 반영 (2026-11-20 KST, Claude Code / Claude Opus 5.5)

- 공식 지시: https://github.com/hahyeong12/server-room-survival/issues/2 (공개 API로 본문 확인, 댓글 0). 시작 시 작업 트리 깨끗, HEAD `606ca1d`, stash/추가 worktree 없음. 새 브랜치 `experiment/3d-ux-phase3-1`에서 진행.
- 추론 수준은 세션 설정을 따르며 정확한 값은 조회 불가.

### 커밋

| SHA | 내용 |
| --- | --- |
| `2988a16` | 캠퍼스 계층(세계 > 울산 캠퍼스 > 관제동 / 서버동), 내 자리에서 시작, 모니터에서 요청 확인, `facility-ops.js`(보조 냉각·전력·UPS·네트워크 공통 상태), 울산 핀 남구 황성동·용연 |
| `3f8fa87` | 오프닝 경로 데이터, 산업단지 재구성, 연결 통로, 세계 회선 패킷, 냉각 플랜트 시각 상태 |
| `f9aed1a` | 관제동/서버동 분리(클리핑·경계벽), 내 자리(강조·명패·상태 연동 책상 모니터), 동료 실루엣, 오프닝 카메라 재생 |
| `b0cc001` | 내 모니터 업무 화면, 건물별 운영 패널, 냉각 배지, 이동 안내, 오프닝 UI(건너뛰기·다시 보기·1회 자동) |
| `3df2618` | 오프닝 단위 테스트, Issue #2 브라우저 QA(`npm run qa:ux`), Phase 2 QA 갱신 |
| (이 커밋) | 학습 연결 설계, 참고 자료, QA 보고서, 작업 기록, README |

### 설계 판단

- 관제동과 서버동은 기존 한 장면의 유리 칸막이(x = 4.15) 양쪽을 **전역 클리핑 평면**으로 잘라 별도 건물로 보이게 했습니다. 기존 지오메트리를 재사용하고 새 실내 모델을 만들지 않아 품질·성능을 유지합니다. NOC에서는 랙 선택(레이캐스트)을 막았습니다.
- 공간 계층을 세계 > 캠퍼스 > {관제동, 서버동}으로 바꿨습니다(Issue #2의 "별도 동/구역" 요구). Phase 2 테스트의 breadcrumb 기대값만 갱신했고 요청 ID·조건·단계 순서는 그대로입니다. 요청 확인 단계는 내 자리와 세계지도 **둘 다** 허용합니다.
- 오프닝 1회 재생 여부만 브라우저 `localStorage`(`srs3d.opening.seen.v1`)에 저장합니다. 게임 상태·저장과 무관하며, 접근 불가 시 매번 재생될 뿐 오류가 나지 않습니다.
- 보조 냉각은 "교육용 보조 계통(AUX-C1)"으로 한정했습니다. 주 냉각은 항상 운전 가정, 고정 수치, 물리 모델 없음.

### 검증 (이 세션에서 실제 실행)

- 단위 21/21, Issue #2 QA 11/11, Phase 2 QA 10/10, 실험실 15/15, 빌드 성공. 상세는 [QA_REPORT_PHASE3_1.md](QA_REPORT_PHASE3_1.md).
- 보호 해시: 기존 751개 동일. 신규 `aidc_story_slot_020.db`/`.lock`(20:45:53)은 사용자가 Python 게임을 직접 플레이하며 만든 새 슬롯으로 판단(이 작업은 Python 게임을 실행하지 않음, Git 제외 대상, 수정·삭제하지 않음).
- 참고 자료 조사: Issue #2 지정 URL 5건 텍스트 확인 → [REFERENCES.md](REFERENCES.md) Issue #2 절.

### 미실행·다음 단계 (승인 필요)

- 사용자 직접 플레이 평가(10초 이해, 분위기, 피로도), 물리 마우스·배율 변경 검증.
- 학습 연결은 [LEARNING_LINK_DESIGN.md](LEARNING_LINK_DESIGN.md) 설계만. 명령어 엔진·터미널·Python 연동·추가 국가/챕터는 시작하지 않음.
- Push·main 병합 보류. Issue #2 댓글은 `gh` CLI 부재로 미게시.

## Phase 3.2 — Issue #3 UX 개선 (2026-11-23 KST, Claude Code / Claude Opus 5.5)

- 공식 지시: https://github.com/hahyeong12/server-room-survival/issues/3 (공개 API로 본문 확인, 댓글 0). 시작 시 브랜치 `experiment/3d-ux-phase3-1`, HEAD `587095b`, 작업 트리 깨끗, stash/추가 worktree 없음. 새 브랜치 `experiment/3d-ux-phase3-2`.
- 사용자 평가 반영 원칙: 기존 3D 디자인·세계 구조는 유지하고, 정보 계층·발견성·조작 피드백만 재설계. 새 나라·챕터·점수·터미널·Python 연동 없음.

### 커밋

| SHA | 내용 |
| --- | --- |
| `5bf9e70` | 5개 목표·단일 다음 행동 모델(`guide.js`), 건물 내부 경로(`room`) |
| `01d64bc` | 오른쪽 패널 재설계: 목표 → 요약 → 공간 카드 → 접힌 상세 → 하단 고정 기본 버튼 1개, 행동 피드백, 5단계 표시 |
| `c4080fa` | 행동 기반 튜토리얼 코치(대상 1개 강조·한 문장·건너뛰기·다시 하기·오클릭 힌트) |
| `f5331d4` | 한국 중심 세계지도, 직접 그린 가상 국제망, 요청 경로만 점등, 장애 구간 표시 |
| `10543a0` | 건물 한 번/두 번 클릭, 4개 기능성 내부 공간, 랙 가림 해결(천장 컷·항상 위 윤곽·핀) |
| `7ef989c` | 건물 이동 시 셰이더 재컴파일 멈춤 수정, 기존 QA를 새 UI에 맞게 갱신 |
| `8d8832b` | Issue #3 브라우저 QA, 랙 클릭 정확도 수정 |
| (이 커밋) | 짧은 화면 겹침 수정, 겹침 자동 검사, 참고 자료·설계·QA 보고서·작업 기록 |

### 검증 (모두 이 세션에서 새로 실행)

단위 29/29, Issue #3 QA 10/10, Issue #2 QA 11/11, Phase 2 QA 10/10, 실험실 15/15, 빌드 성공. 첫 사용자 시뮬레이션 14클릭·스크롤 없음. 4가지 해상도/배율(125·150%는 에뮬레이션)에서 기본 버튼 가림·패널 스크롤·오버레이 겹침 없음. 상세: [QA_REPORT_PHASE3_2.md](QA_REPORT_PHASE3_2.md).

### QA로 찾아 고친 결함

1. 관제동 → 서버동 이동 때 약 1.5 s 멈춤(전역 클리핑 평면 개수 변화 → 셰이더 전체 재컴파일).
2. 모든 랙 클릭 영역 확대가 뒷줄 랙 선택을 방해.
3. 짧은 화면의 제목·탭·모니터 겹침.
4. Chrome "Target crashed" 1회 — 재현되지 않음, 원인 미확정.

### 미실행·다음 단계 (승인 필요)

- 사람의 첫 플레이 평가(2~3분 안에 첫 업무 완료 여부, 발견 시간, 오클릭), 실제 Windows 배율·물리 마우스.
- Push·main 병합 보류. Issue #3 댓글은 `gh` CLI 부재로 미게시.

## Phase 4 — Issue #5 실제 행동 튜토리얼 · 본편 첫 업무 · 중립 오프닝 (2026-11-24 KST, Claude Code / Claude Opus 5.5)

- 공식 지시: https://github.com/hahyeong12/server-room-survival/issues/5 (상위 #4, 공개 API로 본문 확인). 시작 시 `experiment/3d-ux-phase3-2` = origin = `1547c2f`, 작업 트리 깨끗. 새 브랜치 `experiment/3d-playable-phase4`.
- 기준선: 보호 해시 753개(`qa/phase4/protected-before.json`), Python 비GUI 781 통과, JS 29 통과.
- 이번 세션에서 Codex 구현분은 없었고 구현·QA를 Claude Code가 직접 했습니다. 독립 리뷰는 별도 실행한 `/code-review high`로 대신했고 발견 10건을 모두 수정했습니다.

### 커밋

| SHA | 내용 |
| --- | --- |
| `ccf8126` | headless 엔진 어댑터(`engine/`)와 loopback JSON API, 여정(journey), Vite `/api` 프록시, `npm run play`, 보호 기준선, 아키텍처 문서 |
| `305489e` | 중립 오프닝, 고객 거점 중립 마커, 실제 도착 요청 경로만 점등 + 회귀 테스트 |
| `77686a8` | 3D에서 엔진 플레이: 내 모니터 4탭, 서버 랙 카드, 시계·시간 버튼, 모드 메뉴, 선배 브리핑, 큰 버튼 시연 폐기 |
| `be64099` | 튜토리얼 코치(실제 컨트롤 강조, 대신 실행 없음) |
| `2d3c4af` | 튜토리얼 완료 → 새 스토리, 업무·장 클리어·실패·건너뛰기 화면 |
| `0f4b8a5` | 격리 스택 브라우저 QA, 시연 전용 QA 폐기 |
| `9e65a9a` | 독립 리뷰 발견 수정 + 회귀 테스트 |
| (이 커밋) | QA 결과·보고서·작업 기록·README |

### 설계 판단 (근거는 PHASE4_ARCHITECTURE.md)

- 규칙 엔진을 JS로 복제하지 않고 기존 `GameSession`을 headless로 쓰는 Python 표준 라이브러리 HTTP 어댑터를 택했습니다. Python 파일은 무수정(해시 동일)이고 어댑터는 `prototypes/` 아래에 있습니다.
- 튜토리얼은 기존 `mode='tutorial'`(싱가포르 1건)을 쓰고, 장애·진단·복구 교육을 위해 첫 시간 진행 때 기존 교육용 `inject_server_fault`를 한 번 호출합니다(화면에 '교육용 훈련 장애'). 싱가포르 GPU 7은 정상 서버 GPU 6으로 옮길 수 없다는 엔진 사실이 판단 근거가 됩니다.
- 3D 전용 사실(이동·클릭·조회)은 `<slot>.3d.json`에만 저장하고, 단계는 자기 차례에 실제 사실이 참일 때만 완료됩니다.

### 검증 · 미실행 · 다음 단계

- 결과는 [QA_REPORT_PHASE4.md](QA_REPORT_PHASE4.md): 엔진 22/22, JS 29/29, 브라우저 13/13, 실험실 15/15, Python 비GUI 781/781, 빌드 성공, 보호 해시 753 동일.
- 미실행: Python Tk GUI 테스트(요청 없이 실행하지 않음), 실제 Windows 배율·물리 마우스, 사람 플레이 평가(최종 통합본에서).
- GitHub Issue 댓글: `gh` CLI가 없어 미게시. main 병합·PR 없음.

## Phase 5 — Issue #6 스토리 1~5장 3D 캠페인 (2026-11-24 KST, Claude Code / Claude Opus 5.5)

- 기준: `origin/experiment/3d-playable-phase4` `9209431` → 새 브랜치 `experiment/3d-campaign-phase5`. 작업 전 보호 해시 753개(`qa/phase5/protected-before.json`), Python 비GUI 781 통과 기준선 기록.
- 먼저 엔진만으로 제1~5장을 headless로 끝까지 실행해 필요한 조작 순서를 확인했습니다(제2장 일본 고성능+미국 절약형 동시 성공, 제3장 우회/압축, 제4장 이전/복구, 제5장 Stage 1~5). 엔진 수정 없이 모두 가능했습니다.
- 어댑터 API v2(`engine/campaign.py` 신규): 장별 조회 전용 스냅샷, 다음 장 시작(+장 시작 체크포인트), 재도전(체크포인트 → 새 슬롯), 장 연습, 장 선택, 브리핑/대화/결과 카드 확인, 제3·4장 진단창, Lab 행동. 진단 전 네트워크는 "원인 미확인", 제5장 연수 사건은 원인 수치 비공개.
- 3D 화면: 내 모니터(비교 카드·대기/거절·배정 영향·네트워크/장비 진단표·연수 Lab 탭·가상 터미널), 장별 목표·위치 안내(장마다 감소), 선배 대화, 장 클리어/실패/재도전/수료 화면, 메뉴 장 선택·장 연습.
- 브라우저 QA(`scripts/phase5-qa.mjs`, `phase5-ui.mjs`)로 장마다 엔진 재시작·이어하기를 포함한 1→5장 완주, 장별 실패·재도전, 연습, 3개 해상도, 자원 순환을 실제 UI로 검증. QA가 찾은 결함 7건과 독립 코드 리뷰 9건(중요 3)을 수정하고 회귀 테스트를 추가했습니다.
- `npm run play`는 포트가 이미 쓰이면 다른 프로세스를 종료하지 않고 안내합니다.
- Phase 4 QA를 회귀로 다시 돌릴 때 Phase 4 증거 파일이 덮어써진 것을 발견해 원래 커밋 상태로 되돌리고, 재실행 결과는 `qa/phase5/phase4-regression/`에 두었습니다(`--out` 옵션 추가).
- 최종 결과: Phase 5 QA 9/9, Phase 4 QA 13/13, lab.html 15/15, 엔진 38/38, JS 38/38, Python 비GUI 781/781, 빌드 성공, 보호 해시 753개 동일. Tk GUI 311개는 미실행. 상세: [QA_REPORT_PHASE5.md](QA_REPORT_PHASE5.md), 구조: [PHASE5_ARCHITECTURE.md](PHASE5_ARCHITECTURE.md).
