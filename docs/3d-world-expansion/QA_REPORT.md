# 3D 세계 시연 QA 보고서 — Issue #1 Phase 0~2

실행: 2026-11-20 KST, Claude Code (Claude Opus 5.5). 브랜치 `experiment/3d-world-skeleton-001`.
환경: Windows 11, NVIDIA GeForce RTX 5070, Chrome 157(headed, 격리 임시 프로필), 뷰포트 1920×1080, DPR 1, Node 26.13.1, Vite 7.3.8 dev 서버.
3D 캔버스 실제 크기는 1540×801입니다(오른쪽 380px 패널·상하단 HUD 제외).

## 결과 요약

| 구분 | 명령 | 결과 |
| --- | --- | --- |
| 단위 테스트 | `node --test tests/*.test.mjs` | 13 PASS / 0 FAIL |
| 세계 시연 브라우저 QA | `node scripts/world-qa.mjs` | 10 PASS / 0 FAIL ([world-qa.json](qa/world-qa.json)) |
| 기존 실험실 회귀 | `node scripts/browser-qa.mjs --url=http://127.0.0.1:5173/lab.html --output=…` | 15 PASS / 0 FAIL ([browser-qa.json](qa/lab-regression/browser-qa.json)) |
| 프로덕션 빌드 | `npm.cmd run build` | 성공 |
| 보호 파일 해시 | `python docs/3d-world-expansion/protect.py after` | 751개 동일 ([protection-result.json](qa/protection-result.json)) |

## 세계 QA 검사 항목 (실제 UI 이벤트)

1. 하드웨어 WebGL(RTX 5070) 사용
2. 페이지 제목 정상, 요청 카드 조건·처리 위치가 상태에서 렌더(25px), 새 요청 단계 SG 거점 금색
3. 네 공간 전환 + 대기 후 도메인 상태 불변
4. breadcrumb 4단계와 상위 복귀, 최상위에서 복귀 비활성
5. 세계지도 Canvas 실제 클릭으로 거점 선택
6. 시설 선택 → 서버동 진입 → Canvas 클릭으로 랙 D-06 선택
7. 장면별 성능 실측(평균 60 FPS 이상 조건)
8. 10회 반복 이동 후 geometry·texture 수, 도메인 불변, JS heap 증가 32 MiB 미만
9. SG 클릭 전용 9단계: 단계마다 요청·고객·랙 ID와 원래 조건 불변, 장애/복구 중/확인 대기에서 1.2초 대기 및 네 공간 이동 후 도메인 불변·같은 단계 칩, 장애 시 D-06 네트워크 흐름 중지·세계지도 SG 빨강, 완료 후 결과 카드(이력 9건·원래 조건) 화면 안 표시, 세계지도에서도 같은 결과
10. 런타임·콘솔 오류 0

## 성능 실측 (world-qa.json `performance`)

| 공간 | 평균 FPS | p95 프레임 | GPU 시간(비동기 타이머) | draw calls | 삼각형 |
| --- | --- | --- | --- | --- | --- |
| 세계지도 | 239.8 | 4.3 ms | 0.64 ms | 460 | 50,794 |
| 관제실 | 235.3 | 4.3 ms | 1.02 ms | 306 | 110,048 |
| 시설 지도 | 240.0 | 4.3 ms | 0.93 ms | 191 | 21,378 |
| 서버실 | 236.2 | 4.3 ms | 0.69 ms | 736 | 126,794 |
| 기존 실험실(회귀) | 234.5–236.9 | — | — | 736 | 126,794 |

- FPS는 약 240에서 일정해 **모니터 주사율 상한(vsync)** 으로 보입니다. GPU 시간이 프레임당 약 1 ms 이하이므로 여유가 큽니다. 다른 GPU·해상도에서는 미측정입니다.
- 반복 이동: geometry 469 → 469, texture 69 → 69, JS heap 35.4 → 44.7 MiB(GC 시점에 따라 변동, 기준 이내).
- nvidia-smi 값은 다른 앱을 포함한 GPU 전체 표본이며 시제품 단독 점유가 아닙니다.
- 과거 시제품의 236.9 FPS 기록은 재사용하지 않았고, 위 값은 모두 이번 실행의 새 측정입니다.

## 캡처

| 파일 | 내용 |
| --- | --- |
| `qa/phase1-world.png` / `phase1-noc.png` / `phase1-campus.png` / `phase1-hall.png` | 네 공간 기본 화면 |
| `qa/demo-reviewed.png` → `demo-reported.png` | SG 요청 9단계 진행 |
| `qa/sync-fault-world.png` / `-noc` / `-campus` / `-hall` | 같은 업링크 장애가 네 공간에 동일 표시 |
| `qa/demo-result-noc.png`, `qa/demo-result-world.png` | 관제실·세계지도의 같은 처리 결과 카드 |
| `qa/lab-regression/*.png` | 기존 실험실 회귀 대표 화면 |

## 미검증·한계

- 사람의 물리 마우스 조작, 실제 Windows 배율(125/150%) 변경, 다른 GPU/저사양 환경은 미검증입니다.
- 3D 라벨(Canvas 스프라이트)의 작은 글씨 가독성은 자동 판정하지 않았습니다. 핵심 정보는 2D 패널에 있습니다.
- 카메라 충돌 판정 없음(기존 시제품과 동일).
- 기존 Tkinter 게임의 DPI QA 실패 기록과는 별개의 검사입니다.
- Codex 시점의 실패 기록(`qa/*-attempt1.json`)은 QA 도중 소스 수정에 따른 Vite 재로딩으로 인한 일시적 실패로 판단했으며, 동일 코드 재실행에서 재현되지 않았습니다.
