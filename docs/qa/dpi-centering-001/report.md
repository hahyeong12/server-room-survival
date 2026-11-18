# dpi-centering-001 — 배정창 중앙 정렬 오차 수정

기준 커밋 `88d057c`, 기능 커밋 `9856ab8`. [이전 QA의 F-1](../dpi-acceptance-001/report.md)을 수정합니다. 검증 환경은 Windows 11 / 125% / 단일 모니터, `C:\anaconda3\python.exe` 3.14.6 / Tk 8.6.15입니다.

## 수정 내용

`centered_bounds`의 반환 좌표는 클라이언트 영역 기준인데, 이전 계산은 오른쪽에 좌우 테두리 합계, 아래쪽에 제목줄과 아래 테두리 합계를 다시 예약했습니다. 높이가 작업 영역에 가까운 배정창은 실제로 중앙에 들어가도 위로 밀렸습니다.

창 크기 제한은 유지하고, 좌우·아래에는 테두리 한쪽 두께, 위에는 제목줄과 위 테두리를 예약하도록 바꿨습니다. 중앙에 들어가는 창은 부모 최상위 창의 중심에 맞추고, 부족하면 창틀과 여백까지 작업 영역 안에 들어가도록 제한합니다. 기존 실제 좌표 측정·보정·하단 넘침 방어는 그대로 사용합니다.

공용 함수의 호출 관계를 확인했습니다. 교육/복습, 고객 요청/사유, 배정/이전, 장 결과/실패, 네트워크/장비 진단, Lab/연수 결과, 현황 창이 `center_dialog`를 사용합니다. 인접 피드백 배치와 메인 창 배치는 바꾸지 않았습니다.

## 수정 전후 위치

정규 제1장 고객 3명의 배정창을 같은 기존 네이티브 QA의 **±8px** 기준으로 측정합니다.

| DPI 모드 | 이전 세로 오차 | 수정 후 세로 오차 | 고객 수 |
| --- | ---: | ---: | ---: |
| 기본 비인식 | −6px | +1px | 3/3 |
| `SRS_DPI_AWARE=system` | −11px | 0px | 3/3 |

기본 모드의 실제 클라이언트 중심 차이는 Tk 좌표에서 +0.5px입니다. 기존 네이티브 도구는 부모와 자식 높이를 각각 정수로 반 나누므로 +1px, `placement_record`는 최종 중심 차이를 반올림하므로 0px로 기록합니다. 홀수/짝수 크기로 인한 반 픽셀 차이이며, 테스트 허용치를 바꾸지 않았습니다.

별도 실제 화면 캡처에서는 교육창·배정창·장비 진단창·결과 카드·Lab이 두 모드 모두 `(0, 0)px`, 관제실을 포함한 6개 화면이 모두 작업 영역 안에 있었습니다. [측정 JSON](popup-measurements.json), [배정창 비교 이미지](shots/compare_allocation.png)(위: 비인식, 아래: 인식).

## 검증

| 검사 | 기본 비인식 | System DPI Aware |
| --- | ---: | ---: |
| 관련 집중 테스트 | 113 PASS (111 + 추가 GUI 2) | 113 PASS |
| 실제 입력 Lab 집중 검사 | 76 PASS / 0 FAIL | 76 PASS / 0 FAIL |
| 정규 제1~5장 실제 GUI 플레이 | 321 PASS / 0 FAIL | 321 PASS / 0 FAIL |
| GUI 포함 전체 회귀 | 1,092 PASS / 실패·오류·skip 0 | 1,092 PASS / 실패·오류·skip 0 |

비GUI 전체는 781 PASS입니다. 정규 플레이는 임시 정규 슬롯 하나에서 결과창의 실제 다음 장 버튼으로 제1→5장에 진급했습니다. 실제 마우스, 요청함 휠, Lab 터미널의 Unicode 키보드 입력·Enter, 전경·클릭 소유 확인을 사용했습니다. 각 실행의 캡처 가림은 0건입니다.

전체 회귀는 각각 GUI 311개와 비GUI 781개입니다. 실행 시간은 기본 743.235초, 인식 783.9초입니다. [전체 요약](summary.json), [기본 전체 회귀](full-unaware.json), [인식 전체 회귀](full-system.json), [기본 정규 플레이 판정](checks-unaware-regular.json), [인식 정규 플레이 판정](checks-system-regular.json)에 결과를 보관했습니다.

추가 회귀는 순수 계산 3개와 실제 Tk 2개입니다. 수정 전 순수 검사에서 5개 하위 판정이 실패했고, 수정 후 통과했습니다. 기존 가장자리 검사는 실제 클라이언트 좌표와 각 방향의 창틀에 맞는 엄격한 기대값으로 수정했습니다. 새 실제 Tk 검사는 주요 팝업 크기 6종의 중앙 오차를 **1px 이하**로 검사하며, 화면 밖 부모·화면보다 큰 창의 창틀 경계도 검사합니다.

## 저장 및 동작 비교

새 정규 플레이는 이전 QA가 보존한 `%TEMP%\srs_qa__v89675e`의 최종 DB를 `mode=ro&immutable=1`로 읽은 결과와 비교했습니다. 새 게임마다 `session.py:75`에서 `SystemRandom`으로 만드는 `simulation.seed`만 다릅니다. 두 모드 모두 나머지 simulation JSON 전체와 모든 요청 runtime JSON이 이전 QA와 **완전히 같으며**, 무결성은 `ok`입니다. 따라서 실제 점수·성공·기한·시간·작업량·장애/대응·배정 이력이 보존됩니다. 제1~5장 결과 객체도 두 모드 간 각각 완전히 같습니다. 사용자 기존 저장에는 이 비교를 위한 연결을 열지 않았습니다.

사용자 DB 12개와 잠금 12개의 파일 목록·SHA-256은 작업 전후 모두 동일합니다. 기존 미추적 `artifacts/` 19개 항목을 보존했으며, 기존 artifacts 파일 864개도 모두 같은 SHA-256입니다. 이전 QA 임시 폴더와 안의 7개 파일도 그대로입니다. 삭제하거나 Windows 배율을 변경하지 않았습니다. [보호 검증과 사용자 파일 해시](protection.json)에 기록했습니다. 새 증거만 별도 `artifacts/dpi-centering-001/`에 추가했습니다.

## 재현 방법

모든 GUI 검사는 순차 실행했습니다. 기존 회귀 러너의 사용자 저장 경로 차단, 임시 슬롯, 모달 오류 처리와 네이티브 하네스의 전경·소유 프로세스·입력 위치 검사를 유지합니다. 최초 샌드박스 실행은 전경 확보 Preflight에서 중단되어 권한이 확보된 환경에서 다시 실행했습니다. 전경 확인 조건을 낮추지 않았습니다.

```powershell
$srsPython = 'C:\anaconda3\python.exe'
$env:PYTHONIOENCODING = 'utf-8'
& $srsPython -m tests.run_headless
& $srsPython -m tests.run_gui --output <기본-회귀.json>
& $srsPython -m tests.run_gui --dpi system --output <인식-회귀.json>
& $srsPython tests/qa/capture_dpi.py <새-캡처-폴더>

& $srsPython tests/qa/autoplay_chapter5.py --focus <기본-집중-폴더>
& $srsPython tests/qa/autoplay_chapter5.py <기본-정규-폴더> <기본-집중-폴더>/result.json
$env:SRS_DPI_AWARE = 'system'
& $srsPython docs/qa/dpi-acceptance-001/run_aware.py tests/qa/autoplay_chapter5.py --focus <인식-집중-폴더>
& $srsPython docs/qa/dpi-acceptance-001/run_aware.py tests/qa/autoplay_chapter5.py <인식-정규-폴더> <인식-집중-폴더>/result.json
Remove-Item Env:SRS_DPI_AWARE
```

기존 네이티브 QA는 `main()` 대신 Tk를 직접 만드므로 인식 모드는 기존 `run_aware.py`로 같은 DPI 함수를 Tk 생성 전에 호출합니다. 게임/QA의 판정·입력·진행 소스는 변경하지 않았습니다. 원시 로그와 캡처는 로컬 `artifacts/dpi-centering-001/`에 있습니다.

## 범위와 한계

- DPI 인식 기본값 **OFF** 유지. 실험 모드는 프로세스에만 적용하며 실제 Windows 배율을 바꾸지 않았습니다.
- 게임 규칙·시간·자원·점수·기한·저장 형식은 변경하지 않았습니다.
- F-2(Lab 첫 표시 흰 프레임)는 미수정입니다.
- 다른 배율(100%/150%), 실제 다중 모니터, 실행 중 배율 변경은 검증하지 않았습니다. 음수 모니터 좌표는 순수 계산 회귀로 검사했습니다.
