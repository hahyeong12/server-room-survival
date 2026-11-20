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
