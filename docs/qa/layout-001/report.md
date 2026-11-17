# layout-001 — 작은 창의 GUI 접근성

시작 코드 `b548278`에서 기존 실패 5개를 다시 재현한 뒤, 작은 창에서 교육을 막는 결함과 내용이 정상인 외곽선 기대값을 구분해 수정했습니다. 게임 규칙·시간·GPU·전력·점수·고객 동의·SQL/JSON 저장 구조는 변경하지 않았습니다.

최종 **1,057 PASS / FAIL 0 / ERROR 0 / skip 0**입니다. 이 중 GUI는298개, 비GUI는759개입니다. 기존 실패5개가 모두 통과했고 사용자 저장·잠금24개의 목록과 SHA-256도 전부 일치합니다. [전체 결과](full-suite.json), [요약](summary.json), [사용자 데이터 비교](user-data-comparison.json).

## 환경과 보호 조치

- AGENTS.md, 프로젝트 방향·학습 설계·로드맵·README·CHANGELOG, 이전 [보고서](../gui-regression-001/report.md)·[분류표](../gui-regression-001/failure-classification.md)·[배치 계측](../gui-regression-001/layout-observations.json)·[행 경계 계측](../gui-regression-001/boundary-observations.json), `tests/run_gui.py`와 관련 구현을 확인했습니다.
- 시작 작업 트리는 깨끗했고 `main`과 `origin/main`은 `b548278`, ahead/behind 0/0이었습니다. fetch 후 차이가 없어 pull하지 않았습니다. 기존 QA 디렉터리를 수정하지 않았습니다.
- Windows, Python 3.14.6, Tk 8.6.15, Tk scaling 1.334646962233169, 논리 화면 1536×864, 기존 125% 배율 환경입니다. 1000×650 / 1280×680 / 1366×768은 게임 클라이언트 논리 크기입니다. 이미지에는 기존 물리 배율이 반영됩니다.
- 기존 Preflight로 표시·전경·자체 창의 좌표 소유권을 확인했습니다. 네이티브 클릭도 매번 PID와 실제 대상 위젯을 검사했고 다른 프로그램을 조작하지 않았습니다. 전체 회귀는 임시 DB/슬롯 경로만 허용하고 예상하지 않은 모달 창을 실패로 처리하는 기존 러너를 사용했습니다.
- 사용자 DB 12개와 잠금 파일 12개, 총 24개의 이름·SHA-256을 [작업 전](user-data-before.json)과 [작업 후](user-data-after.json)에 비교했습니다. 추가·삭제·변경 모두0개입니다. 테스트는 메모리 DB 또는 임시 폴더만 사용하며 사용자 저장으로 진행을 준비하지 않습니다. 기존 파일·체크포인트·잠금 파일을 삭제하거나 초기화하지 않았습니다.

## 기존 5개 실패의 원인과 처리

| 테스트 (`tests.` 접두어 생략) | 수정 전 / 의도한 검사 | 처리 |
| --- | --- | --- |
| `test_story.StoryGuiTests.test_actual_tk_three_resolutions_through_all_tutorial_stages` | Inspector 요구 높이190이 작은 창에서132/162로 줄어 정보가 잘림. 실제 교육 정보와 조작이 보여야 함 | 버튼 공간을 먼저 예약하고 본문을 스크롤. 기존190px 검사·모든 교육 단계 유지 |
| `test_tutorial_ux.TutorialGuiTests.test_each_target_fits_three_resolutions_and_maximized_game` | resources 1000/1280과 preview 1000에서 강조 대상 미표시. 현재 실제 조작 대상이 보여야 함 | Inspector 확인·비교 버튼 고정. 대상 동일성·타이머·가시성 검사 유지 |
| `test_play_modes_gui.PlayModesGuiTests.test_all_menu_buttons_fit_three_resolutions` | 자유·연습 content 높이712가650 창을 넘어 y=-31. 제목/버전까지 접근 가능해야 함 | 작은 창 하위 메뉴의 제목 글꼴과 여백만 축소. 콘텐츠 전체 포함 검사 유지 |
| `test_console.ConsoleTests.test_automatic_notice_opens_matching_request_without_advancing_time` | Treeview 외곽 끝493 > 부모492. 이전 계측에서는 실제 행은 정상 | 외곽 포함 대신 실제 행 전체·마지막 픽셀·hit-test·행 식별 검사. 자동 접수·요청 일치·시간 불변 유지 |
| `test_server_allocation.ServerConsoleTests.test_layout_and_chip_text_at_three_resolutions` | 같은 외곽1px 기대값. 뒤의 상태들은 첫 실패 때문에 충분히 검사되지 않았음 | 실제 행 가시성으로 정비하자 다른 상태에서 실제3px 잘림과 낮은 랙의 글자 잘림 발견. 둘 다 수정. 모든 상태·해상도·Canvas 텍스트 경계 검사 유지 |

[수정 전 집중 실행](focused-before.json): **5개 모두 실패**, 하위검사 포함 **8 FAIL / ERROR 0 / skip 0**. 과거 수치를 그대로 현재 결과로 옮기지 않았습니다. 이번에 테스트를 삭제하거나 skip하지 않았고 임의의1px 허용치를 추가하지 않았습니다.

## P0 — 구형 교육 Inspector와 미리보기

원인은 `pack` 순서였습니다. 스크롤 없는 본문이 먼저 높이를 소모한 뒤 하단 버튼을 배치해 작은 부모에서 버튼이 사라지거나 높이가 줄었습니다. Inspector190px를 더 줄이는 대신, 하단 조작 영역을 먼저 pack하고 기존 `ScrollArea` 안에 본문을 넣었습니다. 미리보기 비교 버튼도 먼저 고정합니다.

| 크기 | 수정 전 Inspector 실제 높이 / 확인 버튼 | 수정 후 Inspector / 본문 viewport / 확인 버튼 | 비교 버튼 전 → 후 |
| --- | --- | --- | --- |
| 1000×650 | 109px / 미표시 | 190px / 57px / 26px 전체 표시 | 미표시 → 34px 전체 표시 |
| 1280×680 | 162px / 미표시 | 190px / 110px / 26px 전체 표시 | 16px로 잘림 → 34px 전체 표시 |
| 1366×768 | 190px / 표시 | 190px / 198px / 26px 전체 표시 | 34px → 34px |

이 표는 같은 캡처 fixture의 전후 값입니다. 집중 테스트의 초기132px와 캡처의109px는 그때의 부모 공간 상태가 달라 구분해서 기록했습니다. 오른쪽 패널 폭은 모든 크기에서244px로 유지합니다. 본문이 viewport보다 길 때만 스크롤바가 나타나며, 더 큰 창에서는 viewport가 함께 커집니다. GPU·전력 각 텍스트를 스크롤로 노출한 뒤 경계와 실제 hit-test를 확인했습니다.

고정 버튼 위에 떠 있던 구형 화살표 안내가 작은 viewport의 전력 설명을 덮는 것도 캡처에서 발견했습니다. 확인·비교 버튼은 목표 문구와 금색 테두리로 안내하고 이 두 버튼의 떠 있는 안내만 사용하지 않습니다. Inspector/미리보기 **탭 이동 안내**, 다른 단계의 화살표·실제 대상·강조 타이머는 유지됩니다. 버튼을 누르기 전에는 완료 상태를 바꾸지 않습니다.

- Inspector: [최소 창 수정 전](before/screenshots/inspector_1000x650.png) / [수정 후 상단](after-final/screenshots/inspector_1000x650.png) / [전력까지 실제 스크롤](after-final/screenshots/native_inspector_power_1000x650.png).
- 미리보기: [최소 창 수정 전](before/screenshots/preview_1000x650.png) / [수정 후](after-final/screenshots/preview_1000x650.png) / [1280×680](after-final/screenshots/preview_1280x680.png) / [1366×768](after-final/screenshots/preview_1366x768.png).
- 일반 창: [Inspector 1366×768 전](before/screenshots/inspector_1366x768.png) / [후](after-final/screenshots/inspector_1366x768.png). 작은 창에서의 스크롤 처리로 큰 창의 패널을 고정 축소하지 않았습니다.

새 튜토리얼은1000×650에서 실제 Tk 버튼으로 요청→배정안 선택→시작→10분 진행→완료·전량 반환을 확인했습니다. 구형10단계는 기존 전체 단계 검사를 그대로 실행하고, 새 디스크 이어하기 검사로 onboarding 없는 저장에서 resources→request 진행·시간/자원 보존·재저장을 확인했습니다. 새 입문과 구형 준비 함수를 합치지 않았습니다.

## P1 — 자유·연습 메뉴

1000×650과1280×680의 하위 메뉴에서 제목38pt를24pt로, 제목/구분선/하단 여백을 줄였습니다. 설명·버튼·저장 선택·버전 텍스트는 삭제하지 않았습니다. 카드 화면과 높이740 이상에서는 기존 글꼴·여백으로 복원됩니다. 이번 크기에서는 콘텐츠가 모두 들어와 추가 스크롤이 필요하지 않았습니다.

| 크기 | 자유·연습 content 높이 전 → 후 | 수정 후 창 안의 위/아래 여백 |
| --- | --- | --- |
| 1000×650 | 712 → 643 | 4 / 3px |
| 1280×680 | 712 → 643 | 19 / 18px |
| 1366×768 | 712 → 712 | 28 / 28px |

[최소 창 전](before/screenshots/menu_practice.png) / [후](after-final/screenshots/menu_practice.png), [1280×680 전](before/screenshots/menu_practice_1280x680.png) / [후](after-final/screenshots/menu_practice_1280x680.png), [1366×768 전](before/screenshots/menu_practice_1366x768.png) / [후](after-final/screenshots/menu_practice_1366x768.png). 제목 아이콘·문구·모든 버튼·뒤로가기·버전의 실제 전체 높이와 창 경계를 검사했습니다. 메뉴에서 기존 Lab 저장 소개를 표시하는 fixture만 사용했고 제5장/Lab을 플레이하지 않았습니다.

## P2 — 외곽선, 실제 행과 다중 작업

기존 두 재현의 외곽1px은 실제 행 가림이 아니었습니다. 이전 [원시 계측](../gui-regression-001/boundary-observations.json)의 body 끝514 / 외곽515 / 행 끝513과 [자동 접수 화면](../gui-regression-001/screenshots/notice_tree_boundary.png)·[배정 화면](../gui-regression-001/screenshots/allocated_tree_boundary.png)을 보존합니다. 해당 게임 레이아웃은 이번 시작 코드까지 동일했습니다.

새 `assert_tree_row_visible()`은 bbox가 존재하는지, 실제 행 전체가 부모 안인지, 행 중앙과 마지막 픽셀이 Treeview 자신에게 닿는지, 중앙 좌표가 해당 행을 식별하는지 검사합니다. 새 다중 행 검사는 글자 폭과 열 너비, 휠 이동, 실제 Tk 클릭 후 선택 유지까지 검사합니다. 외곽을 무조건 허용하는 조건은 없습니다.

이 검사로 바꾸자 기존 서버 테스트의 후속 상태에서 **행 끝491 > 부모488**인 실제3px 잘림이 드러났습니다([1차 수정 후](focused-after-1.json)). 왼쪽 패널의 세로 여백을5→2px로 줄여6px를 확보했습니다. 또 실제 행 클릭 직후 refresh가 목록을 재생성하면서 선택 표시가 사라지는 결함도 발견했습니다([확장 검사 1차](layout-tests-1.json)). 갱신 후 현재 작업의 선택/포커스를 복원하고, 선택이 같으면 기존 스크롤 위치를 유지합니다.

첫 외곽 실패 뒤에 가려져 있던 완료 상태의 낮은 랙에서는 GPU/전력 글자 끝이 Canvas130px를 넘어140/142px였습니다. 높이75px 미만의 랙만 아이콘과 자원 수치를 좌우로 배치하고 이름·점유 고객 코드·상태·복구 남은 분·GPU/전력을 유지했습니다. 큰 랙의 기존 표현은 유지합니다. 관련 텍스트 경계 assertion은 그대로 통과했습니다.

실제 네이티브 검사에서는 작업3건을 준비한 뒤 기본 Treeview 휠 바인딩으로 행을 노출하고 운영체제 마우스로 각각 클릭했습니다. 1000×650에서1/2/3번 행을 찾는 데 휠0/1/2회가 필요했고, 행 끝488은 각 부모 끝492/488/488 안에 있었습니다. 모든 크기에서 선택한 요청ID와 선택 행이 일치했습니다. 이 목록은 기존처럼 별도 스크롤바 없이 휠을 사용합니다. Inspector 본문의 스크롤바는 별도로 실제 클릭했습니다.

다중 행 수정 후: [1000×650](after-final/screenshots/native_active_rows_1000x650.png) / [1280×680](after-final/screenshots/native_active_rows_1280x680.png) / [1366×768](after-final/screenshots/native_active_rows_1366x768.png). 모든 좌표·클릭·스크롤 횟수는 [최종 계측](after-final/observations.json)의 `native`에 있습니다.

## 검증 순서와 결과

전체 스위트를 반복하지 않고 기존5개→수정→관련 모듈→최종 집중/화면 확인→비GUI 전체→GUI 포함 전체 순으로 진행했습니다. 실제 화면은 ImageGrab으로 게임 클라이언트만 캡처했으며 재구성한 이미지가 아닙니다. [수정 전 계측](before/observations.json), [최종 계측](after-final/observations.json), [캡처69개 SHA-256 목록](screenshots.json)을 함께 보관합니다. 공개 로그·JSON은 개인/임시/실행 환경의 절대 경로만 비식별화했으며 판정·측정값·traceback은 유지했습니다.

| 실행 | 결과 (겹치는 실행은 합산하지 않음) |
| --- | --- |
| 시작 코드, 기존5개 | 0 PASS / 8 FAIL / ERROR0 / skip0. [JSON](focused-before.json) |
| P0 1차, 기존 교육2개 | 2 PASS. [JSON](p0-first.json) |
| 기대값 정비 후 기존5개 | 4 PASS / 실제 행 잘림1 FAIL. [JSON](focused-after-1.json) |
| 확장 검사 1차7개 | 4 PASS / 하위검사7 FAIL / fixture 정리1 ERROR. 선택 해제·낮은 랙 잘림과 임시DB 정리 순서 오류. [JSON](layout-tests-1.json) |
| 수정 후8개 | 8 PASS / FAIL·ERROR·skip0. [JSON](layout-tests-2.json) |
| 관련 모듈142개 | 142 PASS / FAIL·ERROR·skip0. [JSON](related-modules.json) |
| 최종 기존5개 + 새 접근성6개 | 11 PASS / FAIL·ERROR·skip0. [JSON](focused-final.json) |
| 세 해상도 네이티브 확인 | Inspector 스크롤바·확인, 비교창 열기/닫기·무점유, 작업3행 휠/실제 클릭 모두 성공. [계측](after-final/observations.json) |
| 최종 비GUI 전체 | **759 PASS / FAIL·ERROR·skip0**, GUI298개 제외. Tk/Toplevel 생성 차단, 45.213초. [요약](headless-final.json)·[로그](headless-final.txt) |
| 최종 GUI 포함 전체 | **1,057 PASS / FAIL·ERROR·skip0**, unittest649.706초 / Preflight 포함650.664초. [전체 JSON](full-suite.json) |
| 위 전체 중 GUI | **298 PASS / FAIL·ERROR·skip0**. 기존 분류 함수로 전체 결과에서 구분한 값이며 별도 중복 실행 수치가 아님 |

처음 시도한 추가 네이티브 하네스는 마우스를 누른 채 Tk 처리를 기다려 멈췄습니다. 명령행을 확인한 자체 QA 프로세스만 종료하고 마우스 버튼을 해제했습니다([중단 기록](after/attempt.json)). 누름/뗌을 보낸 뒤 Tk를 처리하도록 고쳤습니다. 두 번째 시도는 일부만 노출된 Treeview bbox를 클릭 대상으로 삼아 자체 안전 검사에서 중단했습니다([기록](after-verified/observations.json)). 행 전체가 노출될 때까지 휠을 이동하도록 고친 최종 검사만 네이티브 성공으로 판정합니다. 앞선 시도의 화면과 오류도 삭제하지 않았습니다.

1차 확장 검사의 ERROR는 임시 폴더를 DB보다 먼저 정리한 테스트 코드 오류였습니다. cleanup을 DB 종료→루트 종료→임시 폴더 삭제 순으로 수정한 뒤 재검증했습니다. 게임 저장 오류로 분류하지 않습니다. PowerShell의 stderr 리다이렉션 때문에 일부 초기 로그에 `NativeCommandError` 래퍼가 붙지만 판정은 unittest 결과와 JSON의 failures/errors로 구분했습니다.

재현 명령(이 환경에서는 기존 `C:/anaconda3/python.exe` 사용):

```powershell
python -m tests.run_gui --output artifacts/layout-focused.json tests.test_layout_gui
python -m tests.run_headless
python -m tests.run_gui --output artifacts/layout-full.json
# 기존 계측을 덮어쓰지 않는 새 출력 디렉터리를 지정합니다.
python tests/qa/capture_layout.py artifacts/layout-capture --native
```

전체 회귀의 GUI 분류는 기존 `needs_window()`를 사용합니다. 전체 실행에 포함되는 기존 제5장/Lab 단위·GUI 회귀는 유지하지만 새로운 개발이나 전체 자동 플레이를 시작하지 않았습니다.

## 남은 항목과 커밋

최종 회귀에 남은 FAIL·ERROR·skip은 없습니다. 기존 외곽1px 기대값2건은 실제 행·클릭 검사로 대체했고, 확인된 실제 UI 결함은 수정했습니다. 하네스/fixture 중간 오류는 위 시도 기록과 구분하며 최종 실행 환경 오류도0개입니다.

흰 프레임의 원인·빈도와 DPI 흐림은 **별도 미해결**입니다. 전역 DPI 인식 설정을 바꾸지 않았습니다. 이번 결과는 기존125% 환경의 세 창 크기이며, 실제100%/150% 배율·다른 모니터의 접근성을 보장하지 않습니다. 제5장 QA 전에 별도 범위로 배율/모니터와 흰 프레임 검증 방식을 정해야 합니다. 이번 통과를 그 문제의 해결이나 제5장/Lab 전체 플레이 검증으로 확대 해석하지 않습니다.

기능별 코드 커밋:

1. `1140d6a` — 구형 교육 Inspector/미리보기 고정 조작과 본문 스크롤.
2. `a60141b` — 작은 창 하위 메뉴 제목/버전 잘림 수정.
3. `c3ad0d7` — 실제 작업 행·선택·낮은 랙 수정, 접근성6개와 캡처 하네스.

최종 전체 회귀 코드는 `c3ad0d7`입니다. 이후 변경은 CHANGELOG·QA 보고서·실행 증거만 포함합니다. 원격을 다시 fetch해 충돌 여부를 확인한 뒤 일반 Push하며, 최종 커밋과 동기화 결과는 완료 응답에 전달합니다. 제5장·Engineering Lab 다음 단계로 자동 진행하지 않습니다.
