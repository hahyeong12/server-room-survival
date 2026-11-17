# chapter5-ux-001 — 제5장 학습 UX 보완

[chapter5-001](../chapter5-001/report.md) QA에서 남긴 UX 항목 두 가지만 고쳤습니다.

1. Engineering Lab 상단의 긴 고객·업무 헤더가 잘리는 문제
2. Stage 5 학습 통과와 고객 작업 완료가 결과창에서 구분되지 않던 문제

새 장애·명령·학습 과제·숙련도/등급은 추가하지 않았습니다. Stage 5 통과 조건, 게임 시간·점수·GPU/전력 원장·고객 동의·저장 형식(새 저장 필드·SQL 변경 없음)도 그대로입니다. 흰 프레임과 전역 DPI는 기존 미해결 사항으로 남겨 두었습니다.

**결과:** 헤더 잘림이 13건에서 0건으로 줄었습니다(3개 모드 × 4개 크기 × 탭). 전체 회귀 **1,069 PASS / FAIL·ERROR·skip 0**, 비GUI 전체 **765 PASS**, 관련 Tk **23 PASS**, 네이티브 입력 집중 검사 **76 PASS / FAIL 0**입니다. 사용자 저장·잠금 24개의 목록과 SHA-256은 작업 전후 동일합니다. [요약](summary.json)

## 시작 상태

- `main`과 `origin/main` 모두 `14a950c`, 작업 트리 깨끗함, fetch 후 ahead/behind 0/0.
- Windows, Python 3.14.6(기존 `C:/anaconda3/python.exe`), Tk 8.6.15, 125% 배율(논리 화면 1536×864). DPI 설정은 바꾸지 않았습니다.
- 사용자 저장 DB 12개와 잠금 12개를 [작업 전](user-data-before.json)에 해시했고, chapter5-001 종료 시점 해시와 같았습니다.

## 1. Lab 헤더 가시성

**원인:** 첫 줄에 `ENGINEERING LAB` 제목, 모드, 요청·고객·국가·업무, 시각, 상태 칩이 한 줄로 모두 들어가 있었습니다. 가운데 칸 폭이 1060px 창에서 398px, 900px 창에서 238px뿐이어서, 500~640px 길이의 문구 뒤쪽이 잘렸습니다. 같은 헤더를 쓰는 제3장(Chapter 3a) 관찰 미리보기도 마찬가지였고, 900px 창에서는 고정 폭(760px)으로 줄바꿈하던 안내 문구까지 잘렸습니다.

**수정**([engineering_lab.py](../../../engineering_lab.py), `05bb769`):

- 모드(`심화 연수` / `연습 · 정규 기록 아님` / `Chapter 3a · 미션 A · 관찰 미리보기`)는 제목 옆 작은 칩으로 옮겼습니다.
- `요청 #N · 고객 / 국가 · 업무`는 창 전체 폭을 쓰는 둘째 줄로 옮겼습니다. 창 폭에 맞춰 줄바꿈하므로 업무명이 더 길어져도 잘리지 않습니다.
- 안내 문구는 [새로고침]·[관제실로 돌아가기] 버튼 옆에 남은 폭에 맞춰 줄바꿈합니다(최대 760px 유지).

| 측정(실제 Tk) | 수정 전 | 수정 후 |
| --- | --- | --- |
| 잘린 문구 | 정규 1060·900 / 연습 1060·900·1280 / 미리보기 1060·900·1280 → 13건 | 모든 크기·모드 0건 |
| 헤더 높이 | 110px | 138px(모든 크기에서 같음) |
| 관제실 복귀 버튼 | 창 안 | 창 안 |
| [연수 진행] 하단 실행 버튼 | 보임 | 보임(900×620 포함) |

[크기별 측정값](header-metrics.json). 헤더가 정보 한 줄만큼(28px) 높아졌고, 그만큼 탭 영역이 줄었습니다. 이 때문에 네이티브 fixture에서 Stage 과제 영역의 답변 버튼을 화면에 보이게 하려는 스크롤바 클릭이 12회 늘었습니다(아래 참고). 넓은 창에서는 첫 줄 가운데가 비지만 빈 줄이 새로 생기지는 않았습니다. 알림이 없을 때도 자리를 차지하는 빈 알림 줄은 기존 구조 그대로 두었습니다.

| 화면 | 수정 전 | 수정 후 |
| --- | --- | --- |
| 정규 1060×700 | [전](shots/before_regular_header_1060x700_training.png) | [후](shots/after_regular_header_1060x700_training.png) |
| 정규 900×620 | [전](shots/before_regular_header_900x620_training.png) | [후](shots/after_regular_header_900x620_training.png) |
| 연습 1060×700 | [전](shots/before_practice_header_1060x700_training.png) | [후](shots/after_practice_header_1060x700_training.png) |
| 연습 900×620 | [전](shots/before_practice_header_900x620_training.png) | [후](shots/after_practice_header_900x620_training.png) |
| 미리보기 900×620 | [전](shots/before_preview_header_900x620_operations.png) | [후](shots/after_preview_header_900x620_operations.png) |
| 정규 1366×768 터미널 | — | [후](shots/after_regular_header_1366x768_terminal.png) |

## 2. 학습 완료와 고객 작업 완료 구분

**원인:** 사후 ping 응답(3/3)을 확인하면 Stage 5가 통과되고 결과창이 열립니다. 이때 고객 작업은 대개 `recovering`(복구 준비 10분) 상태입니다. 그런데 결과창 제목이 `심화 연수 완료`였고, 고객 작업은 열 때 계산한 `진행 50%`로 굳어 있었습니다. 수정 전에는 창을 연 채 작업이 정상 완료돼도 [`고객 작업 진행 50%`가 그대로](shots/before_regular_5_job_finished_result_live.png) 남았습니다.

**수정**([session.py](../../../session.py)·[engineering_lab.py](../../../engineering_lab.py)·[main.py](../../../main.py), `884ccad`):

- 새 조회 전용 함수 `GameSession.training_job_status()`는 연수 요청의 **현재** 상태에서 네트워크 문구, 고객 작업 상태(배정 전 / 작업 중단 · 장애 조치 전 / 복구 준비 중 · N분 남음 / 진행 중 / 정상 완료 · 기한 준수·초과 / 실패 등)와 진행률을 계산합니다. 자원 반환 여부는 실제 서버 원장에서 확인합니다. 저장·시간·자원은 바꾸지 않습니다.
- 결과창 제목을 `심화 연수 · Stage 5 / 5 통과`로 바꾸고, 맨 위에 **현재 상태** 표(심화 연수 / 네트워크 / 고객 작업 / 남은 업무)를 추가했습니다. 연습 모드는 기존처럼 `다섯 Stage 체험 · 정규 기록 아님`으로 표시합니다.
- 결과창을 연 채 관제실에서 시간을 진행하면 `SimulatorApp.refresh()`가 표를 다시 읽습니다. 다시 열거나 저장 후 이어하기를 해도 같은 함수로 계산합니다.
- Stage 5 안내 줄에서 굳어 있던 `고객 작업 진행 N%`를 뺐습니다. `training_result()['stage5']['job']` 값은 호환을 위해 남겨 두었습니다.
- Lab 목표 카드와 관제실 목표도 작업이 끝나지 않았으면 `학습 기록은 완료됐지만 고객 작업(요청 #N)은 아직 …`이라고 안내하고, 끝난 뒤에는 기존 문구로 돌아갑니다.

| 시점 | 실제 상태 | 결과창 고객 작업 | 남은 업무 | 화면 |
| --- | --- | --- | --- | --- |
| ① Stage 5 미통과(원인 판단 후) | `incident`, 학습 4/5 | 결과창 없음 | — | [Lab](shots/after_regular_1_stage5_pending_lab.png) |
| ② 우회 버튼 직후 | `recovering`, 아직 미통과 | 결과창 없음 | — | [Lab](shots/after_regular_2_after_reroute_lab.png) |
| ③ 사후 ping, 5/5 | `recovering` 10분, 50% | 복구 준비 중 · 10분 남음 | 관제실에서 시간 진행 | [결과](shots/after_regular_3_stage5_passed_result_live.png) · [Lab](shots/after_regular_3_stage5_passed_lab.png) |
| ④ 준비 종료 | `running` 50% | 진행 중 · 작업 진행률 50% | 관제실에서 시간 진행 | [결과(연 채 갱신)](shots/after_regular_4_recovery_done_running_result_live.png) |
| ⑤ 최종 완료 | `finished`, 원장 반환, GPU·전력 0 | 정상 완료 · 기한 준수, D1 18:40 완료 · GPU·전력 반환 완료 | 없음 | [연 채](shots/after_regular_5_job_finished_result_live.png) · [다시 열기](shots/after_regular_5_job_finished_result_reopened.png) |

연습 모드도 같은 순서로 확인했습니다: [③](shots/after_practice_3_stage5_passed_result_live.png), [⑤](shots/after_practice_5_job_finished_result_live.png). 각 시점의 문구·상태 전체는 [timeline.json](timeline.json)에 있습니다. 모든 시점에서 화면 조회 전후의 게임 상태 스냅샷이 같았습니다.

## 3. 검증

| 검사 | 결과 | 기록 |
| --- | --- | --- |
| 신규 비GUI `tests/test_chapter5_ux.py` | 6개: 정규·연습 다섯 시점, 조회가 상태를 바꾸지 않음, 조회를 섞은 플레이와 섞지 않은 플레이의 시간·점수·GPU·전력·원장·스토리 저장 동일, 디스크 저장 후 이어하기 세 시점, 배정 전 상태 | — |
| 신규 실제 Tk `tests/test_chapter5_ux_gui.py` | 6개: 정규·연습·미리보기 헤더 4개 크기, 결과창 다섯 시점(연 채 갱신·다시 열기), 디스크 이어하기 세 시점의 [연수 결과], 연습 결과창 | — |
| 관련 Tk 집중(신규 12 + 기존 `test_training_gui`·`test_engineering_lab_gui` 11) | **23 PASS** / 0 | [related-tk.json](related-tk.json) |
| 비GUI 전체(`python -m tests.run_headless`, Tk 생성 차단) | **765 PASS** / 0 (GUI 304 제외) | [headless.txt](headless.txt) |
| GUI 포함 전체(`python -m tests.run_gui`, Preflight 포함) | **1,069 PASS** / FAIL·ERROR·skip 0, 659.9초 | [full-regression.json](full-regression.json) |
| 네이티브 입력 집중(`autoplay_chapter5.py --focus`, 연습 슬롯) | **76 PASS / FAIL 0**, 실제 클릭 151·키보드 290 | [native-focus.json](native-focus.json) |

- **테스트 수 변화:** 기준선 1,057 → 1,069. 신규 비GUI 6개와 GUI 6개를 더한 결과이며, 기존 테스트는 삭제하거나 건너뛰지 않았습니다.
- 전체 회귀에는 제1~4장 결과창 GUI·비GUI 테스트가 모두 포함됩니다. 제1~4장 결과창 코드(`chapter_dialog.py`, `result_summary.py`)는 수정하지 않았습니다.
- 네이티브 집중 검사는 수정 후 코드(`e75efe0`)에서 기존 Preflight로 한 번 실행했고, 정상이어서 별도 준비 확인을 요구하지 않았습니다. 직전(chapter5-001)과 같은 76개 검사를 통과했습니다. 클릭 수가 139회에서 151회로 늘어난 12회는 모두 Stage 과제 영역 스크롤바 클릭입니다(헤더가 28px 높아진 영향). 답변 버튼의 좌표도 그만큼 이동했습니다. 정규 제1→5장 전체 네이티브 플레이는 다시 하지 않았습니다.
- 수정 전후 화면은 같은 캡처 스크립트([tests/qa/capture_chapter5_ux.py](../../../tests/qa/capture_chapter5_ux.py))로 만들었습니다. 수정 전은 `git archive HEAD`로 임시 폴더에 푼 `14a950c` 코드를 썼습니다. 이 스크립트는 메모리 DB를 쓰고, 학습 단계 준비를 기존 테스트 도우미(엔진 직접 호출)로 하므로 **네이티브 입력 실적이 아닙니다.** 캡처 23장의 SHA-256은 [screenshots.json](screenshots.json)에 있습니다.

## 4. 사용자 데이터

사용자 저장 24개(DB 12·잠금 12)를 [작업 전](user-data-before.json)과 [작업 후](user-data-after.json)에 비교했습니다. **추가·삭제·변경 0개**입니다([비교](user-data-comparison.json)). 모든 테스트와 캡처는 메모리 DB나 임시 폴더만 사용했고, `run_gui`·네이티브 fixture의 자체 사전·사후 검사도 동일하다고 보고했습니다.

## 5. 남은 사항(이번 범위 밖)

- **흰 프레임·전역 DPI:** 기존 미해결 상태 그대로입니다.
- **Lab 목표 카드 진행률 게이지 글자 겹침:** `진행률`과 `통과한 Stage`/`체험한 Stage`가 겹쳐 보입니다. 수정 전 캡처에도 있던 기존 표시 문제이며 이번 요청 범위가 아니어서 고치지 않았습니다.
- **빈 알림 줄:** 알림이 없을 때도 Lab 헤더의 알림 줄이 자리를 차지합니다. 기존 구조이며, 줄이면 알림이 뜰 때 화면이 위아래로 움직이므로 이번에는 손대지 않았습니다.
- 다른 실제 배율·모니터와 정규 전체 네이티브 재플레이는 이번에 다시 검증하지 않았습니다.

## 커밋

- `05bb769` fix(lab): 긴 업무 헤더를 자르지 않고 줄바꿈
- `884ccad` feat(training): Stage 5 통과와 고객 작업 상태를 따로 표시
- `e75efe0` test(training): 헤더 맞춤과 학습/고객 작업 상태 검증, 전후 캡처 스크립트
- 이 보고서와 실행 증거, CHANGELOG는 별도 문서 커밋입니다.
