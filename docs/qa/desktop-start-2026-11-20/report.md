# 데스크톱 개발 시작 점검 — 2026-11-20

**판정: 3D 프로토타입 착수 보류.** 실제 데스크톱 세션의 GUI Preflight가 전경 확보에 실패했습니다. 이는 알려진 DPI 레이아웃 실패와 다릅니다. 검사를 우회하거나 기대값·게임 코드를 변경하지 않았습니다. 독립 프로토타입 구현, 엔진 연결, main 병합·push는 하지 않았습니다.

## Git 및 프로젝트

- 실제 경로: `C:\Users\hahye\Desktop\server-room-survival`
- 시작 브랜치: `main`
- 로컬 HEAD / fetch 후 origin/main / `ls-remote`의 main: 모두 `d46671a0f7b4e7304e2d78ea18c4a1743a5dfc0e`
- ahead/behind: 0/0. 시작 시 추적 파일 변경·미추적 파일·stash 없음.
- Git 제외 파일: 실제 사용자 DB·잠금 파일과 Python 캐시. 기존 artifacts 및 docs/qa 산출물 508개 별도 보호 목록 작성.
- 최초 fetch는 샌드박스 `.git/FETCH_HEAD` 쓰기 제한으로 실패했고, 권한 확장 실행은 성공했습니다. 원격 조회 역시 권한 확장 실행으로 확인했습니다.
- 점검 결과는 `experiment/3d-datacenter-prototype-001` 브랜치에 기록합니다. 기존 Python/Tkinter 코드·테스트·DPI 기본값은 변경하지 않았습니다.
- AGENTS.md, PROJECT_VISION.md, DECISION_LOG.md, LEARNING_DESIGN.md, DEVELOPMENT_ROADMAP.md, README.md, CHANGELOG.md, DEV_NOTES.md와 실제 테스트 러너를 확인했습니다.

## 하드웨어와 개발 환경

| 항목 | 실제 확인 |
| --- | --- |
| CPU | Intel Core Ultra 7 265KF |
| GPU | NVIDIA GeForce RTX 5070, 드라이버 610.88 |
| 전용 VRAM | NVIDIA-SMI 기준 12,227MiB. Win32_VideoController의 32비트 AdapterRAM 값은 사용하지 않음 |
| RAM | OS 가용 총 33,053,120KiB = 약 31.52GiB. 최초 측정 사용 약 12.70GiB, 여유 약 18.82GiB. 시점별 변동 있음 |
| Windows | Windows 11 Home, 10.0.26300 / build 26300 |
| 디스플레이 | 보고된 활성 화면 1920×1080, 진단 프로세스 System DPI 96 = 100%. 개별 다중 모니터 DPI는 미검증 |
| Python | `C:\Users\hahye\anaconda3\python.exe`, 3.14.6. PATH의 python.exe는 WindowsApps 별칭 |
| 노트북 경로 | `C:\anaconda3\python.exe` 없음 |
| Tcl / Tk | Tcl patchlevel 8.6.15, Tk 인터페이스 8.6. GUI Preflight를 통과한 Tk 화면 검증은 확보하지 못함 |
| SQLite | 3.53.2 |
| Python 의존성 | 기존 게임은 표준 라이브러리 기반. 설치 목록 `python-packages.json`. 진단에 사용한 websocket-client 및 Pillow 확인 |
| Node.js / npm | PATH 및 조사한 표준 설치 경로에서 독립 실행 도구를 찾지 못함. 시스템 전체 부재를 단정하지 않음. 임의 설치하지 않음 |
| Git | 2.55.0.windows.5, 원격 HTTPS fetch 및 HEAD 조회 성공 |
| 브라우저 | Chrome 157.0.8103.80, Edge 157.0.4341.60 설치 확인 |
| 3D 도구 | Three.js 프로젝트·빌드 환경 미구성. Playwright/Selenium Python 패키지 없음 |

### 브라우저 렌더링

`probe_browser.py`는 기존 Chrome 사용자 프로필과 분리된 임시 프로필을 사용합니다. Chrome headless 진단만 수행했으며 GPU를 강제로 켜거나 소프트웨어 렌더링으로 대체하는 플래그는 쓰지 않았습니다. 생성한 브라우저 프로세스는 종료하고 임시 프로필을 정리했습니다. 시스템·브라우저 설정은 변경하지 않았습니다.

- WebGL 1 / WebGL 2: 모두 context 생성 성공.
- 실제 renderer: `ANGLE (NVIDIA, NVIDIA GeForce RTX 5070 (0x00002F04) Direct3D11 vs_5_0 ps_5_0, D3D11)`.
- GPU compositing / rasterization / WebGL: enabled.
- 최대 texture size: 16,384.
- 세부 증거: `browser-gpu.json`. headless의 800×600 화면·DPR 1은 물리 모니터 측정값이 아닙니다.
- 사용자가 평소 쓰는 브라우저 프로필의 가속 설정과 실제 표시 창 조작은 미검증입니다.

이 CPU·GPU·메모리는 고품질 Three.js 장면의 개발 후보로 충분한 여유가 있다고 판단합니다. 실제 장면이 없으므로 FPS를 보장하지는 않습니다. 그림자·후처리·고해상도 렌더 타깃의 VRAM 소비, draw call과 GPU 동기화가 향후 측정 대상입니다. 노트북 기준 품질 하향을 적용하지 않았습니다.

## 테스트 기준선

- 실제 발견: **1,092개 = 비GUI 781 + GUI 등 제외 311** (`environment.json`).
- `tests.run_headless`: **781개 PASS**, 15.277초, 종료 코드 0 (`headless.txt`).
- `tests.run_gui --output .../full-regression.json`: 종료 코드 1. **Preflight의 `GUI 표시/전경 확보 실패`로 테스트 실행 전 중단**.
- 진단 시 `GetForegroundWindow()`는 0. Python 창을 실제 데스크톱 전경으로 확보할 수 있는 실행 세션인지 추가 확인이 필요합니다. 원인은 실행 세션/데스크톱 접근 문제로 의심되지만 확정하지 않았습니다.
- `full-regression.json`의 `environment_error` 및 원본 로그 보관. GUI 실패 개수 311개로 집계하거나 전체 1,092개 통과로 간주하지 않습니다.
- DPI별 기존 레이아웃 실패는 이번 실행에서 재현 여부를 확인하지 못했습니다. 실험 DPI 모드도 실행하지 않았습니다.
- 기존 GUI 러너의 사용자 루트 DB 접근 차단·임시 슬롯 제한·사전/사후 해시 보호를 유지했습니다.

## 사용자 파일 및 기존 QA 보호

- 사용자 파일 **53개 = DB 33개(자유 운영 1 + 슬롯 19 + 체크포인트 13) + 잠금 20개**.
- `user-data-before.json`에 파일명·크기·SHA-256 기록. `user-data-after.json` 및 `protection-comparison.json`으로 종료 시 비교합니다.
- 기존 artifacts 및 docs/qa의 508개 파일도 별도 before/after 목록과 SHA-256으로 비교합니다. 기존 QA 파일은 수정·삭제하지 않았습니다.
- 종료 비교 결과: 사용자 파일 53개와 기존 QA 파일 508개 모두 목록·크기·SHA-256 일치(`protection-comparison.json`).
- 기존 게임 DB를 열거나 SQLite 내용을 변경하지 않았습니다. 사용자 DB는 해시 계산을 위한 바이트 읽기만 수행했습니다.

## 3D 구현·조작·성능 결과

착수 조건 미충족으로 `3d-datacenter-prototype-001` 구현을 시작하지 않았습니다. 첫 생성/수정 후 스크린샷, 카메라·랙·Inspector·공간 전환·장애/복구 조작 결과는 **없음/미검증**입니다. 제공된 사진 자료의 디자인 연구도 구현 단계로 보류했습니다.

- 프로토타입 FPS / JS heap / 장면 GPU 사용량: **측정 불가(장면 미구현)**.
- NVIDIA-SMI 최초 유휴 측정: GPU 1%, VRAM 989/12,227MiB, 47°C. 다른 실행 중인 앱을 포함한 시스템 전체 값이며 프로토타입 성능이 아닙니다. 후속 스냅샷은 `gpu-idle.csv` 참조.

## 재개 절차 및 직접 실행

우선 Windows의 실제 대화형 데스크톱에서 다음 명령으로 전경 확보 여부를 확인해야 합니다. 기존 GUI 러너를 우회하지 않습니다. 새 실행에서는 결과를 다른 새 폴더에 저장해 이번 기록을 보존합니다.

```powershell
Set-Location C:\Users\hahye\Desktop\server-room-survival
& 'C:\Users\hahye\anaconda3\python.exe' -m tests.run_headless
& 'C:\Users\hahye\anaconda3\python.exe' -m tests.run_gui --output docs/qa/desktop-start-retry/full-regression.json
```

기존 게임 실행 명령은 다음과 같습니다. 실제 저장을 사용하는 실행이므로 이번 점검에서는 실행하지 않았습니다.

```powershell
& 'C:\Users\hahye\anaconda3\python.exe' main.py
```

GUI 기준선을 확보하고 Node.js/npm 설치 위치를 확인하거나 개발 환경을 준비한 후, 같은 실험 브랜치의 독립 폴더에서 가상 상태만 사용하는 Three.js 첫 버전을 구현합니다. 엔진 통합 제안은 이 첫 버전의 실제 표시·조작·성능 검증 이후 읽기 전용 상태 어댑터부터 별도 합의하는 것입니다. 이번에는 통합을 진행하지 않습니다.

브라우저 작업 절차에는 [Sites 스킬](C:/Users/hahye/.codex/plugins/cache/openai-curated-remote/sites/1.1.7/skills/sites/SKILL.md)의 local-only 경로를 적용했습니다. 개발 보류는 스킬의 승인 요구가 아니라 사용자가 지정한 착수 조건에 따른 판단입니다.
