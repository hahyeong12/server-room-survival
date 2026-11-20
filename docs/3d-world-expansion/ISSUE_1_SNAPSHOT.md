# Issue #1 원문 스냅샷

URL: https://github.com/hahyeong12/server-room-survival/issues/1
수신 updated_at: 2026-11-20T10:57:19Z

## 목적
**서버실 생존기 (Server Room Survival)**의 기존 Three.js 3D 서버실 시제품을 보존하면서 **세계 운영 지도 → 울산 관제실 → 데이터센터 시설 지도 → 서버실/랙**을 하나의 탐색형 게임 세계로 연결하고, **싱가포르 요청 1건**으로 끝까지 따라가는 **시연 모드(가상 데이터)**를 완성한다. 사용자가 직접 플레이·평가하기 전에는 Python 엔진 연동, 나라/업무/스토리/터미널 콘텐츠 확대를 하지 않는다.

### 기준과 책임
- 프로젝트 지침: 루트 `AGENTS.md`, `PROJECT_VISION.md`, `docs/DECISION_LOG.md`, `docs/LEARNING_DESIGN.md`, `docs/DEVELOPMENT_ROADMAP.md`; 인수인계: 사용자 제공 ‘서버실 생존기 — 3D 세계 확장 개발 인수인계 및 시작 지시’.
- **ChatGPT**: 방향·범위·QA 기준·리뷰 결과 판단. **Codex**: 단계적 구현과 자동 검증. **Claude Code**: 후속 독립 코드/UX/회귀 리뷰. 두 에이전트가 **동시에 같은 작업 트리를 수정하지 않는다**. **사용자**: Phase 3에서 직접 플레이·최종 승인.
- Codex는 사용자 선호 **GPT-6.1 Sol / High**를 우선 사용(미지원이면 사용 모델/추론 수준 기록). Claude Code는 설치·인증된 환경의 실제 모델과 thinking 설정을 보고한다.
- **Phase 0~2는 이 작업 범위 내에서 자동 진행 가능**. 사용자 개입은 작업 범위·기존 규칙·저장 형식·메인 브랜치 변경 등 본질적 결정 및 Phase 3 직접 평가에만 요구한다.

## 시작 전 사실 확인 — 필수
2026-11-20 원격 GitHub 조회: `main` HEAD `d46671a0f7b4e7304e2d78ea18c4a1743a5dfc0e`; 원격 브랜치는 `main`만 확인됨. 인수인계 문서의 로컬 가능성 있는 브랜치 `experiment/3d-datacenter-prototype-001`, 커밋 `95cec7c`는 **원격에서 찾지 못함**. 이는 삭제 증거가 아니며 **사용자 Windows 로컬 저장소에서 확인**해야 한다.

1. `C:\Users\hahye\Desktop\server-room-survival`에서 `pwd`, `git status --porcelain=v1`, `git branch -avv`, `git log -1 --oneline`, `git remote -v`, `git stash list`, 파일/실행 환경 및 잠금·저장 슬롯 확인. 사용자 미추적·수정 파일 보존.
2. `prototypes/3d-datacenter-001/`과 해당 README·QA·실제 Three.js 코드가 있는지, 24랙/관제실/Inspector/카메라가 실제 동작하는지 확인. 없다면 원격 `main`만 보고 새로 재구현하지 말고 **BLOCKED**로 보고.
3. 별도 안전한 실험 브랜치/작업 트리(`experiment/3d-world-skeleton-001` 등)에서만 진행. 기존 브랜치·사용자 파일을 덮어쓰지 말 것. Python/SQLite 코드·실제 사용자 DB/스토리 슬롯/잠금 파일 수정·초기화 금지. 원본 저장 파일 해시를 필요시 비교. 기존 `main` 푸시·병합·force push·hard reset·위험한 rebase 금지.
4. 원격 Push는 별도 범위 확인 전 보류. **로컬 기능 단위 커밋은 자율적으로 자주 생성**하되, 단계 완료/검증 성공 후 진행하고 사용자 기존 변경은 커밋에 포함하지 않는다.

## Phase 0 — 설계와 이미지 참고
- 기존 3D 코드를 감사하여 재사용할 장면, 렌더러, 카메라, Inspector, 에셋, 테스트, 빌드 방식과 현재 성능·병목을 기록.
- 세계 운영 지도(한국 울산·싱가포르·일본·미국), AIDC 관제실(NOC), 시설 지도(관제·서버·전력·UPS·냉각·네트워크), 기존 서버실/랙의 4계층 정보 구조 및 이동 동선 설계. 카메라/탐색은 게임 시간·점수·자원을 변화시키지 않는다.
- 구현 전 웹/이미지 검색: `global submarine cable map`, `Asia Pacific submarine cable network`, `dark futuristic strategy world map UI`, `data center NOC control room`, `hyperscale data center campus isometric`, `data center UPS electrical room`, `data center cooling plant chillers`, `GPU server rack data center`; 한국어 검색어도 병행. 실물 사진/배치/조명/조작 UX를 분석하여 3D 시제품의 짙은 남색·차콜·청록 고급형 톤과 통일. **검색어·주요 참고 URL·선택 이유·저작권 유의점을 문서화**. 타인의 사진/지도/3D 에셋을 무단 복제하지 말고 직접 만든 지오메트리·UI와 적법 에셋만 사용.
- 간단한 장면 구조도와 ‘단일 시연 데이터 상태 저장소’·라우팅 설계, 화면별 필요한 데이터/행동/복귀, 단계별 QA 표 작성. 과한 프레임워크 교체나 새 의존성 도입은 피한다.

## Phase 1 — 플레이 가능한 세계 뼈대
- 세계지도: Ulsan AIDC 중심, SG/JP/US 고객 국가, 요청 알림 및 가상 네트워크 경로. 실제 케이블 지리·실제 기업 연결이라고 주장하지 말 것.
- 관제실: 기존 퀄리티와 어울리는 NOC 공간 + 선명한 2D 요청함, 자원/네트워크 상태 패널, 연결 시설 선택.
- 시설 지도: 관제동, 서버동, 전력/UPS, 냉각, 네트워크 시설을 직관적인 전체 단지로 표시하고 서버동으로 진입.
- 서버실: 기존 24랙 Three.js 시제품·기존 카메라/선택/Inspector 최대한 재사용. 랙 선택 시 관련 업무/상태 표시.
- 모든 장소에서 일관된 내비게이션, 상위 공간으로 복귀, 현재 위치 breadcrumb, 선택/초점 이동, 읽기 쉬운 HUD. 기존 장면의 시각 품질을 유지한다. 핵심 숫자/버튼을 조그만 3D 모니터에만 가두지 않는다.

## Phase 2 — 싱가포르 고객 세로형 시연
- 전용 deterministic fixture와 단일 상태 저장소 사용. **'시연 모드 · 가상 요청 데이터'**를 UI에 상시 분명히 표시.
- 흐름: SG 새 요청 세계지도 알림 → 국가/요청 확인 → 울산 관제실 요청 접수/검토 → 시설/서버동 위치 추적 → 해당 랙 강조/Inspector → 시연 작업 진행·장애/상태 예시(가능한 최소한) → 관제실/지도 동일 상태 → 결과 확인.
- 동일 요청 ID, 고객 ID, 랙 ID를 전 화면에서 일치시키고 원본 요청 조건 보존. 시연용 UI에서 실제 GPU 점유·게임 점수·시계·SQLite 저장을 변경하면 안 된다. **Python/SQLite 엔진 연동은 Phase 3 승인 후 별도 설계**한다.
- 네비게이션만으로 상태·시간이 증가하지 않아야 한다. 시연 진행은 명시적 클릭만. 관제실 운영자 시점에서 정보와 상호작용이 이해되는지 확인.

## QA 및 완료 조건
- 1920×1080 / 100% DPI 데스크톱 기준, 4개 세계 화면·상하위 복귀·랙 선택·요청 단계와 상태 동기화 실제 테스트.
- 자동 테스트: 장면 전환, breadcrumb/복귀, 클릭·상태 동기화, 유효하지 않은 ID, 시연 데이터 범위, navigation 무부작용, 기존 서버실 핵심 기능 회귀. 기존 Python 로직이 수정되지 않았다는 diff 확인.
- 실제 브라우저 캡처(각 장면·SG 요청 흐름), 클릭 기반 smoke QA, 브라우저 오류, 측정 가능한 FPS/프레임 시간/해상도·설정 기록. FPS를 실측하지 못하면 '미측정'으로 표시. 과거 시제품 236.9 FPS를 새 버전 성능으로 재사용하지 말 것.
- 외부 앱/GUI 가림·포커스 실패 시 가짜 PASS 금지. 실제 자동 테스트/수동 QA/정적 검사 구분. 원격/로컬에서 할 수 없는 검증은 항목별 미실행 사유 기록.
- 기존 Tkinter 게임의 known DPI 문제(100%에서 2건, 150%에서 10건 QA 실패 보고)와 이번 3D QA를 혼동하지 말 것.

## 작은 커밋과 에이전트 인계
최소 다음 완료 단위로 분리: `docs(3d): baseline and design references`, `feat(3d): world map and shared navigation`, `feat(3d): noc and campus views`, `feat(3d): server room integration`, `feat(3d): singapore demo flow`, `test(3d): navigation and state regression`, `docs(qa): 3d world walkthrough results` (실제 구현에 따라 조정 가능).
- 각 커밋 전 관련 검사, `git diff --check`, 변경 파일 범위 확인. 기존 파일/미추적물 보존.
- `docs/3d-world-expansion/WORK_LOG.md`에 커밋 SHA, 구현 범위, 실제 실행한 테스트 명령과 결과, 검증 못 한 항목, 참조 출처, 다음 작업을 누적 기록.
- Codex 구현 후 **Claude Code가 읽기 중심 독립 리뷰**: 기존 3D 재사용, UX, 상태 일관성, 성능, 테스트, 저장 파일 무결성, 저작권, 민감 변경 탐지. 리뷰 개선은 Codex가 반영하고 관련 테스트 후 별도 커밋. Claude가 설치/인증되지 않았으면 무단 설치·로그인 없이 ‘Claude 리뷰 미실행’으로 남긴다.
- 최종 보고: 작업 브랜치·로컬/원격 SHA·커밋 목록·변경 파일·실제 캡처·실행 명령·PASS/FAIL/미실행·남은 한계·사용자가 직접 시험해 볼 5~10분짜리 조작 순서.
- **Phase 3 직전 반드시 중단**하고 사용자 직접 플레이와 평가를 기다린다. 신규 국가/업무/명령어/챕터, Python 엔진 연동, `main` 병합·Push는 자동 시작하지 않는다.
