# Phase 8 작업 기록

## 2026-11-26 시작

- AGENTS 및 비전/결정/학습/로드맵, README/CHANGELOG, Phase7 구조/QA, 사건·Lab·어댑터·3D·테스트를 조사했다.
- Issue #9 전체를 GitHub 도구로 읽었다. 로컬/원격 기준 SHA `287eba4fcc5078eb5815e0b6223f6985f18de8a2` 확인 후 새 브랜치 생성.
- 추적 파일 변경 없음. 이전 QA의 미추적 PNG는 보존한다.
- .git 쓰기가 sandbox에서 막혀 사용자 요청 범위의 git 작업에 실행 권한을 사용했다.
- 공식 iproute2/systemd/Kubernetes/DCGM 문서 열람. GNU df 문서는 첫 요청 timeout으로 재시도 예정.
- 구현/QA 계획: PHASE8_ARCHITECTURE.md. 승인이나 사용자 중간 플레이 요청 없이 진행한다.

## 구현과 첫 검증

- `15eb28c` 계획·보호 기준선, `4bc4a40` 명령 registry/결과 생성기, `962a4b7` 사건 엔진 연동·5개 근무·별도 저장을 커밋하고 일반 Push했다.
- 기존 보호 파일 1,047개(사용자 DB/잠금/체크포인트·기존 QA 포함)의 읽기 전용 SHA-256 기준선을 만들었다. 중간 재검사 변경 0.
- 명령 28개(유틸리티 help/clear 제외). DCGM 공식 문서의 `--fetch`/`--check` 차이를 확인하고 수동 건강 평가는 `--check`로 정정했다. GNU df/du 본문 fetch timeout은 공식 페이지 검색 결과와 GNU 문서로 보완했다.
- 첫 비GUI 전체 926/926(당시 신규 87), 기존 어댑터 47/47, 기존 JS 48/48, build 성공. 테스트 추가 후 수치는 최종 보고서에서 다시 기록한다.
- 브라우저 개발 실행에서 메뉴 카드 목록에 Linux 항목이 누락된 것을 발견해 수정했다. 이후 개발 UI 6/6. 승인 요청 없이 실제 Chrome 입력으로 확인했다.
- 첫 전체 Phase8 브라우저 실행 `full-attempt-1`: 11/11. seed/API 진행 대체 없이 제1~5장 148초 + Linux 5개 근무 301초 완주, 유효 명령 93회, 실제 28종 명령, 학습/시설 복구/승급 재시작, 실패→새 슬롯, 4개 뷰포트, WebGL 반복 이동 확인.
- 독립 정적 리뷰 9건 및 자체 점검을 수정했다(`REVIEW_PHASE8.md`). 현재 수정 후 전체 UI 재검증과 Phase4~7/Lab·Python/JS/build 직렬 회귀를 수행한다.
- 사용자 사용량 제한 후 재개 요청을 받아 Issue #9 전체·브랜치·작업 기록·실행 결과를 다시 확인했다. 원래 범위와 미완료 항목은 유지했다.

## 최종 UI 재검증

- `f49572f`: 실제 클릭·타이핑 QA, 직렬 회귀 러너, 포트/임시 저장 소유 확인, Phase7 출력 경로 분리와 구현 문서를 커밋·일반 Push했다.
- 수정 후 최종 Phase8 Chrome QA **12/12 PASS** (`qa/phase8/final/phase8-qa.json`, 16:04~16:13 KST). 제1~5장 149초, Linux 5근무 305초, 10유형 11사건 종료. helper 로그 93개 명령·28종 전부 실행, 3지점 프로세스 재시작, 원본 DB 바이트 불변 재도전.
- 새 비동기 지연 검사와 사건별 clear, 실제 DPR1.5를 확인한 CDP 150% 에뮬레이션 포함. 6회 세계/캠퍼스/서버동/관제 순환에서 geometries536/textures84 고정, FPS236.8~237.6, p954.3ms. page/console 오류0.
- 독립 리뷰 에이전트에 수정 사항을 다시 전달했다. 추가 확정 중대 결함 없음. 정상 노드 `eligible=False`의 부모 증거·CLI `_proof` 제외는 실제 Python 회귀가 검사한다. 리뷰 에이전트 자체 실행은 없었다.
- 보호 재검사 1,047개 변경0. 이제 Phase7→6→5→4→lab→비GUI Python→adapter→JS→build의 최종 직렬 회귀를 수행 중이다. 미실행 결과를 PASS로 기록하지 않는다.
- 16:28 KST 기존 Phase7 전체 브라우저 회귀 **12/12 PASS**, 오류/크래시0. 새 `regression-phase7` 폴더에 증거를 분리했다. 원래 global/incident v1·Lab/training·game/session/database 코드와 lab.html은 기준점 대비 변경0. README/학습/로드맵에는 역사적 Tk 범위와 실험 3D 범위를 구분했다.
- 16:40 KST 기존 Phase6 전체 브라우저 회귀 **16/16 PASS**, page/console 오류0. 제1~5장, 글로벌3교대, 실패/새 슬롯, 이전 모드 저장 재시작, 자유 운영, 5개 레이아웃, 움직임 줄이기와 반복 자원 검사. Phase5를 이어서 시작했다.
- 16:46 KST 기존 Phase5 전체 브라우저 회귀 **9/9 PASS**, page/console 오류0. 제1~5장 각 재시작과 수료, 2/3/4장 실패·새 슬롯 재도전, 별도 연습, 세 해상도와 자원 순환을 확인했다. Phase4 회귀 진행 중.
