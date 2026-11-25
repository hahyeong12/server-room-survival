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
