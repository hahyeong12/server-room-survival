# GUI 회귀 기준선 정비 — gui-regression-001

제1~4장 UI 개편으로 낡아진 메뉴·결과창·입문 준비 테스트를 현재 문서와 코드에 맞췄습니다. **게임 소스는 수정하지 않았으며, 실제 작은 창 배치 실패는 검사에서 계속 드러나게 유지했습니다.** 이번 QA는 실제 Tk를 사용하는 회귀 fixture 검사입니다. 정규 제1~4장 전체 네이티브 자동 플레이를 반복하지 않았고, 제5장·Engineering Lab의 새 개발이나 자동 플레이도 시작하지 않았습니다. 전체 회귀에는 기존 Lab 단위/GUI fixture가 포함됩니다.

## 시작 상태와 보호

- 기준: `bca4d12`, `main`, 미커밋 변경 없음. 실제 권한으로 재Fetch한 원격도 `bca4d12`, 앞섬/뒤처짐 0/0이어서 Pull 불필요. 샌드박스의 `.git/FETCH_HEAD` 쓰기 제한은 권한 있는 Fetch로 해결했습니다.
- AGENTS와 PROJECT_VISION → DECISION_LOG → LEARNING_DESIGN → DEVELOPMENT_ROADMAP → README/CHANGELOG, PLAY_MODE_REORGANIZATION 및 [직전 UI QA](../ui-consistency-001/report.md)·[과거 실패 JSON](../ui-consistency-001/test-results.json)·[제4장 QA](../chapter4-001/report.md)를 확인했습니다. 오래된 문서의 당시 미실행 표기와 현재 구현을 구분했습니다.
- 기존 사용자 DB 12개(자유 운영1·스토리 슬롯11)와 잠금12개, **24개**를 파일명·크기·SHA-256으로 보존했습니다. 기존 체크포인트는 없었습니다. 검사 fixture는 메모리/시스템 임시 디렉터리만 사용합니다. 원본 DB를 복사해 게임을 진행하거나 내용을 수정하지 않았습니다.
- [작업 전 목록·해시](user-data-before.json)와 [작업 후 목록·해시](user-data-after.json)는 **파일명·크기·SHA-256 모두 동일**합니다. 각 실행 JSON에도 전후24개 비교가 있습니다. 기존 파일 누락·변경·새 사용자 저장 생성은 없습니다.
- 이전 QA 디렉터리·소스·기존 미추적 자료를 변경/삭제하지 않았습니다. Reset/Rebase/Stash/Force Push를 사용하지 않았습니다.

## 실행 환경과 재현 방법

Anaconda Python **3.14.6**, Tk **8.6.15**, Windows 데스크톱. 논리 화면 **1536×864**, 실제 ImageGrab **1920×1080**으로 물리/논리 비율 **1.25**입니다. Tk 자체 `scaling=1.33465`는 OS 배율1.25와 다른 수치입니다. 창 크기는 Tk 논리 좌표이며 1000×650 / 1280×680 / 1366×768 및 기존 최대화 검사를 사용했습니다. DPI 인식 API나 OS 배율 설정은 바꾸지 않았습니다.

샌드박스 첫 실행에서는 Preflight가 전경을 확보하지 못해 **테스트를 시작하기 전에** 중단했습니다([기록](preflight-sandbox.json)). 데스크톱 접근이 가능한 권한의 실행에서 실제 창 표시·전경·중앙점 가림 검사를 통과한 뒤 진행했습니다. 사용자 준비 질문이나 마우스 입력을 요구하지 않았습니다.

새 [GUI 회귀 러너](../../../tests/run_gui.py)는 실제 Git 작업 트리에서 실행해 `.git` 없는 사본 문제를 제거합니다. 게임 DB 연결과 새 슬롯 예약에 보호 검사를 걸어 저장소 루트의 사용자 저장 위치를 거부합니다. 검사 자체는 실제 Tk이며 모달 대화상자가 예기치 않게 열리면 오류로 드러나게 합니다. 테스트가 명시적으로 모킹하는 대화상자는 기존대로 검사합니다. Tk를 생성할 수 없을 때 조용히 전체 skip하는 성공 결과를 만들지 않으며, skip도 종료 실패로 취급합니다. 보호 경계3개와 기본 전체 탐색1개, 비GUI4개로 검증했습니다.

처음 전체 실행을 호출했을 때 새 러너가 `tests`를 일반 패키지로 가정해 **테스트 시작 전에** 탐색 오류로 중단됐습니다([기록](discovery-error.json)). `tests`는 `__init__.py` 없는 namespace 디렉터리이므로 기존 headless와 같은 탐색 방식으로 수정했고, 기본 탐색에 GUI/파일 제외 검사가 함께 포함되는 smoke 검사를 추가했습니다. 이 중단은 게임 FAIL이나 전체 스위트 실행으로 세지 않습니다. 수정 후 비GUI 전체를 다시 실행했습니다.

```powershell
# 전체 GUI 포함 스위트 — 마지막에 한 번
python -m tests.run_gui --output artifacts/gui-results.json

# 모듈/개별 메서드 집중 재현
python -m tests.run_gui --output artifacts/focused.json tests.test_story_slots

# Tk 생성을 차단하는 전체 비GUI 회귀
python -m tests.run_headless

# 배치 실패 fixture 계측과 실제 화면 캡처
python tests/qa/inspect_regression_layout.py
```

이 환경에서는 WindowsApps의 `python` 별칭이 샌드박스에서 실행되지 않아 기존 `C:/anaconda3/python.exe`를 명시했습니다. 패키지를 설치하지 않았습니다. 공개 JSON은 **개인/임시/실행 환경의 절대 경로만 비식별화**했으며 결과·판정·traceback 내용은 유지했습니다.

## 과거 실패와 현재 결과 구분

이전 **1,046개 / 32 FAIL·9 ERROR / 서로 다른29개**는 그때의 중간 코드와 Git 없는 사본에서 나온 결과입니다. 현재 실패 수로 재사용하지 않았습니다.

현재 시작 코드 `bca4d12`에서 같은29개를 먼저 실행했습니다. **5 PASS, 실패 테스트24개**이며 하위 검사까지 **30 FAIL·6 ERROR**, unittest 본체 **93.134초**입니다. 5개는 직전 QA에서 이미 수정한 입문 준비3개·제3장 제목1개와, 올바른 Git 환경에서 통과한 파일 제외 검사1개입니다. [수정 전 실행 JSON](historical-before.json).

29개 모두의 **재현 명령·조건·기존 기대·현재 의도·수정 여부·전후 결과**는 [개별 분류표](failure-classification.md)와 [기계 판독 JSON](failure-classification.json)에 기록했습니다. D로 시작했던 항목 중 완료창2개는 실제로는 삭제된 버튼 키를 참조한 A였고, 한 페이지 대화창 가시성도 마지막 페이지의 의도적 버튼 숨김을 빠뜨린 기대값 오류였습니다. 배치 실패를 일괄적으로 오래된 테스트로 처리하지 않았습니다.

## 테스트 정비 내용과 유지한 불변조건

| 대상 | 정비 이유와 유지한 검사 |
| --- | --- |
| `tests/support.py`, `test_story_patch.prepare()` | 새 입문 `complete_onboarding()`과 onboarding 필드 없는 구형10단계 `prepare()/finish()`에 서로 반대 흐름을 받으면 실패하는 guard 추가. 기존 구형 진행·저장 호환 검사는 유지 |
| `test_story_slots.py` | 메뉴 새 스토리는 선배→신입의 새 첫 근무. SG→JP→US 각30분을 실제 Tk 위젯으로 시작/진행하고, 매번 선택 슬롯 일치·조회 무점유·완료·전량 반환·기록3건·구 저장 바이트 불변 확인. 구형 슬롯은 Server A 실클릭→Inspector→운영 확인→완료를 별도 GUI 검사로 보존. 슬롯별 시간·점수·부분 진행·이어하기 분리 유지 |
| `test_chapter2_gui.py`, `test_allocation_flow_gui.py` | 성공창은 다음 장·장 선택·메뉴, 실패창은 재도전·장 선택·메뉴. 실제 action_bar와 별칭 버튼을 구분. 성공 결과·상세 펼치기·기존 관제실 재도전의 새 연습 세션 유지. 실패 안내는 실제 회사/판정/원인 카드로 검사하고 기존 작업 계속 진행 검사 유지 |
| `test_story_patch.py`, `test_v091e.py` | 완료창의 제거된 free/status/review 키 대신 현재 행동3개. 자유 운영은 메인 메뉴→자유·연습→자유 운영의 실제 위젯 경로. 기존 자유 진행·스토리 저장, 저장 실패 시 창/타이머/DB 유지, 실제 점수·반환·현황·중앙 배치 검사 유지 |
| `test_console.py`, `test_story.py` | 시간 안내는 `시간 빨리감기` 묶음과 실제 +10 버튼을 따로 검사. 완료는 옛 고정 문구 대신 실제 회사와 `chapter_result()` 일치 검사. 시간·작업량·저장·자원 검사는 유지 |
| `test_conditions.py` | 요청 폭179에는 여백도 포함. 실제162px 버튼에 글자153px·테두리·최소 여백이 들어가는지 검사. 모든 협의/동의/부족/거절/이전 저장 단계, 높이·창 경계 검사 유지 |
| `test_story_patch.py` 완료 배치 | 700×510 결과창은 본문 스크롤 구조. 요약표와 다음 단계가 각각 실제 viewport에 들어오는지 스크롤 후 검사하고, 하단 행동은 항상 창 안에 보이는지 유지 |
| `test_tutorial_ux.py` 대화 배치 | 마지막 페이지는 중복 종료/마지막 안내를 숨긴다는 정책을 명시 검사. 실제 보이는 버튼·초상화·중앙 좌표·작업 영역 검사는 유지 |

테스트를 삭제하거나 skip하지 않았습니다. 메서드 이름2개는 현재 검사 의미로 바꾸고 분류표에 이전/현재 ID를 함께 연결했습니다. 기존1,046개에 **구형 슬롯 GUI1개 + 러너 비GUI4개**만 추가해 최종 탐색은1,051개입니다. 게임 규칙·자원·점수·시간·고객 동의·SQL/JSON 저장 형식은 변경하지 않았습니다.

## 실제 배치 관측과 후속 수정안

전체 [계측 JSON](layout-observations.json), [캡처 SHA-256 목록](screenshots.json). 화면은 실제 ImageGrab을 물리/논리 배율에 맞춰 게임 클라이언트 영역만 잘랐으며 재구성하지 않았습니다. 아래의 **수정안은 제안이며 미구현**입니다.

| 항목 | 재현·판단 | 이번 처리 / 다음 수정안 |
| --- | --- | --- |
| **구형 교육 Inspector/확인 버튼** | [1000×650 실제 화면](screenshots/legacy_highlight_minimum.png). Inspector 요구190px가132px로 줄며 전력 게이지·장비 설명이 잘리고, `GPU·전력 정보 확인`이 unmapped. 1280×680에서도 확인 버튼이 unmapped, 1366×768에서는 표시. 본문 스크롤 없음. **기존 저장의 교육 진행을 막는 실제 UI 결함** | 관련2개 테스트의 기존 가시성 assertion을 유지. 창 확대가 우회 방법. 다음에는 확인 조작의 공간을 먼저 보장하고 Inspector 본문을 필요한 경우 스크롤하는 범위를 검토. 새 입문과 구형 저장 모두 재검증 필요 |
| **구형 배정 미리보기** | 1000×650의 preview 단계에서 강조 대상이 unmapped라는 기존 검사도 남음. Inspector와 같은 오른쪽 패널의 높이 부족 경로 | 실패 유지. 위 패널 수정 시 비교 버튼·모드·계획 선택까지 함께 재검증할 대상. 모든 상태의 수동 접근성은 미검증 |
| **자유·연습 메뉴** | 저장 소개가 있는 fixture에서 content 높이712, 최소 창650 → y=-31; 1280×680에서도 y=-16. [최소 창](screenshots/menu_practice.png). 버튼·선택 목록·뒤로가기는 접근 가능하나 위 장식과 아래 버전 영역이 잘림. 1366×768에서는 content가 들어옴. 이 화면에는 스크롤 없음 | content 전체 포함 assertion 유지. 핵심 기능 차단과 구분되는 실제 장식/정보 잘림. 다음에는 하위 메뉴의 제목 여백 축소나 내용 스크롤을 검토. 큰 재배치는 이번에 하지 않음 |
| **활성 목록의 부모 경계1px 초과** | 자동 접수/서버 배정 검사에서 목록 끝493 > body 끝492. 추가로 동일 fixture를 위치만 옮겨 측정한 결과 [행 가시성 JSON](boundary-observations.json)의 목록 끝515 > body514이나 **실제 행 끝513 < body514**, 마지막 행 픽셀의 `winfo_containing()`도 Treeview 자신. [자동 접수 화면](screenshots/notice_tree_boundary.png)·[배정 화면](screenshots/allocated_tree_boundary.png). **두 재현 상태에서 실제 내용은 가리지 않고 외곽1px만 초과** | 사용자 기능 차단과 구분되는 엄격한 경계 기대값2건. 임의1px 허용치나 assertion 제거로 통과시키지 않고 현재 FAIL로 보존. 후속 정비는 전체 위젯 사각형 대신 실제 행·스크롤·클릭 가시성을 검사하는 방향이 적절. 다른 다중 행 상태까지 이 결론을 일반화하지 않음 |
| **버튼 요청 폭** | [실제 최소 창](screenshots/condition_minimum.png). 수락 버튼 실제162, 요구179, 글자153으로 글자가 들어감. 위젯 요청 폭과 글자 잘림은 다름 | 기대값 오류 정비, 7상태의 글자·높이·창 경계 검사 통과 |
| **완료창 스크롤** | [위쪽](screenshots/completion_scroll_top.png)·[아래쪽](screenshots/completion_scroll_bottom.png). 요약표/선배 카드/다음 단계는 스크롤로 노출되고 행동3개는 하단 고정 | 구조에 맞게 가시성 검사를 강화. 실제로 잘리는 확인 버튼과 구분 |

**흰색 프레임과 DPI 흐림은 별도 미해결 항목입니다.** 이전 QA의 흰 프레임 관측과 원인 미확정을 그대로 유지합니다. 이번 회귀가 통과한 화면이 있다고 해결로 판정하지 않았고, 흰 프레임을 재계측하는 실험도 추가하지 않았습니다. 125%에서 논리 창 높이 부족의 결과를 확인했지만 **실제100%/150% 및 다른 모니터는 미검증**이므로 DPI가 유일한 원인이라고 단정하지 않습니다. DPI 인식 방식 변경은 별도 합의 대상입니다.

## 검증 결과

| 실행 | 결과 |
| --- | --- |
| 시작 코드의 과거29개 | 5 PASS / 실패 메서드24개, 하위검사 포함30 FAIL·6 ERROR / skip0. 93.134초 |
| 1차 정비 후 집중30개 | 21 PASS / 실패 메서드9개, 하위검사 포함21 FAIL·0 ERROR / skip0. 구형 슬롯 GUI1개 포함. [기록](focused-after-1.json) |
| 관련 모듈 집중125개 | **122 PASS / 실패 메서드3개**, 하위검사 포함6 FAIL·0 ERROR / skip0. unittest 본체317.239초. [기록](related-modules.json) |
| 전체 비GUI (기본 탐색 검사 추가 전) | 758 PASS / FAIL0·ERROR0, GUI 등292개 제외. 17.462초 |
| 최종 전체 비GUI | **759 PASS / FAIL0·ERROR0**, GUI 등292개 제외. 17.958초. Tk/Toplevel 생성을 차단한 기존 headless 러너 사용 |
| 최종 전체 GUI 포함 | **1,051개 중 1,046 PASS / 실패 메서드5개**, 하위검사 포함 **8 FAIL·0 ERROR·skip0**. unittest 본체616.214초, Preflight 포함 러너617.041초. [전체 결과](full-suite.json) |
| 위 전체 중 GUI 부분 | **292개 중287 PASS / 실패 메서드5개**. 비GUI759개와 겹치지 않으며 독립 재실행한 수치가 아니라 전체 결과의 GUI 분류. [요약 JSON](summary.json) |

위 실행은 겹치는 테스트가 있으므로 합산하지 않습니다. FAIL 수는 unittest가 기록한 하위검사 건수이며, 실패한 메서드 수와 구분합니다. 초기29개 집중 실행과 관련 모듈 검사 후 **최종 전체 실행은 한 번만** 진행했습니다.

과거29개는 **5 PASS→24 PASS**, 실패 메서드는24→5로 줄었습니다. 이번 정비로19개 메서드의 오래된 기대값/준비 오류를 해소했습니다. 아래5개 외의 새 실패는 없으며, 알려진 실패를 허용하거나 성공으로 바꾸는 러너 설정은 없습니다. 러너는 현재 전체 결과에 실패 종료 코드를 돌려줍니다.

| 최종 분류 | 테스트 / 남은 상태 |
| --- | --- |
| **PASS** | 전체1,046개, 이 중 GUI287·비GUI759. 저장 슬롯·모드·고객 동의·점수/시간/자원·체크포인트·구형 호환 회귀 포함 |
| **실제 UI 결함 FAIL** | `test_story.StoryGuiTests.test_actual_tk_three_resolutions_through_all_tutorial_stages` (Inspector 잘림2건), `test_tutorial_ux.TutorialGuiTests.test_each_target_fits_three_resolutions_and_maximized_game` (실제 조작 미표시3건). 같은 작은 패널 높이 문제의 두 검사 |
| **실제 UI 잘림 FAIL (핵심 조작 가능)** | `test_play_modes_gui.PlayModesGuiTests.test_all_menu_buttons_fit_three_resolutions` (content/장식·버전 잘림1건) |
| **엄격한 기존 기대값 FAIL** | `test_console.ConsoleTests.test_automatic_notice_opens_matching_request_without_advancing_time`, `test_server_allocation.ServerConsoleTests.test_layout_and_chip_text_at_three_resolutions` (외곽1px 각1건). 두 재현 상태의 실제 행 가시성은 추가 확인 완료. 기존 assertion은 보존했으므로 최종 전체 결과에는 FAIL로 남음 |
| **실행 환경 오류** | 최종 **0 ERROR**. Git 없는 사본, 샌드박스 전경, 신규 러너의 기본 탐색 오류는 각각 해결했으며 중단 기록은 별도 보존 |
| **미검증** | 다른 실제 DPI/모니터, 흰 프레임 원인·빈도, 다중 행·다른 상태에서1px 경계의 사용자 영향, 이번 회귀와 별개인 제5장 네이티브 전체 플레이 |

## 제5장 QA 전 필요한 후속 조치

1. 구형 슬롯의 작은 Inspector/미리보기 조작을 보이게 하는 제한된 배치 수정 범위를 합의한 뒤 실제 클릭과 저장/이어하기까지 재검증합니다. 구형 저장 지원을 폐기하는 것으로 해결하지 않습니다.
2. 자유·연습 메뉴의 장식/버전 잘림을 처리합니다. 활성 목록1px은 이번 두 재현에서 실제 행 가림이 없었으므로, 다중 행·스크롤 접근성을 보강한 뒤 내용 가시성을 기준으로 테스트를 정비하는 후속 항목입니다.
3. 흰 프레임과 DPI 흐림은 기존 미해결 목록을 유지하고, 다른 배율/모니터 검증과 DPI 처리 변경을 분리해 결정합니다.
4. 남은 실패가 있는 현재 결과를 **전부 통과한 기준선으로 사용하지 않습니다**. 제5장 QA 시 이번 known failure 목록과 새 실패를 비교해야 합니다. 제5장/Engineering Lab 개발·새 자동 플레이는 이번 작업에 포함하지 않습니다.

## 커밋·최종 저장 비교

테스트/러너/재현 코드는 `0e9367d` (`test: align GUI regression fixtures with current play modes`), 전체 탐색 보완은 `8f12fbd` (`fix(test): discover the full suite in the namespace tests directory`)입니다. 최종 전체 검사는 `8f12fbd`에서 실행했습니다. 이후 변경은 보고서·실행 증거뿐이며 게임/회귀 코드는 동일합니다. 사용자 저장24개는 최종 추가 계측 종료 후에도 전부 동일합니다. 보고서와 증거를 별도 커밋한 뒤 원격을 다시 확인하고 일반 Push합니다. 최종 커밋과 동기화 상태는 완료 응답에 전달합니다.
