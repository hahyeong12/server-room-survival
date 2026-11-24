# Phase 5 아키텍처 — 스토리 1~5장 3D 캠페인 (Issue #6)

작성: 2026-11-24, Claude Code (Claude Opus 5.5). 상위 로드맵 Issue #4, 선행 Phase 4(Issue #5, `9209431`).

## 결론

```text
브라우저 (Three.js, src/*)                               Python (표준 라이브러리만)
  내 모니터 탭 · 서버동 랙 · 세계지도 · 선배 대화 ──/api──▶ engine/server.py  (127.0.0.1)
  판정 없음: 스냅샷을 그리고 실제 조작을 보냄               ├ engine/adapter.py   GameHost / Game (행동 → GameSession 메서드)
                                                         ├ engine/campaign.py  장별 조회 전용 스냅샷 (신규)
                                                         └ session.GameSession · StoryProgress · Chapter2/3/3b · TrainingProgress
                                                           · lab_model.observe · lab_terminal.run_command  ← 기존 규칙, 수정 없음
```

- **규칙은 기존 Python 하나뿐입니다.** 장 진행·해금·클리어/실패 판정, 고객 조건·동의, GPU/전력 원장, 기한·점수, 네트워크/서버 장애·진단·조치, Lab Stage 통과 판정은 모두 기존 엔진이 계산합니다. JS에는 판정 로직이 없습니다. JS는 엔진 결과를 고르고 문장을 배치할 뿐입니다(`campaign-view.js`도 순수 표시 함수).
- **기존 Python 파일 무수정**: 보호 해시 753개가 작업 전후 동일합니다(`qa/phase5/protection-result.json`).
- **내부 장 ID ↔ 표시 번호**: 1·2·3·`3b`·`lab` ↔ 제1장~제5장(`aidc/story/chapters.py`의 `CHAPTERS`). 화면은 번호/제목만 씁니다.

## 스냅샷 API v2 (`GET /api/games/<id>`) — v1 필드는 그대로

`api: 2`, `apiCompat: [1]`. 제1장·튜토리얼의 Phase 4 필드(`story.kind/step/card/objective/pages/done/jobsDone/jobsTotal/chapter/result`)는 같은 의미로 유지합니다. 추가 필드:

| 필드 | 출처 (엔진, 조회 전용) |
| --- | --- |
| `story.chapterKey`, `uiStep`, `practice` | `current_chapter`, `StoryProgress.ui_step`, `practice` |
| `story.chapter.state/text` | `chapter_state()` (진행 중 / 클리어 / 실패) |
| `story.objective` | `session.story_objective()` (제5장은 `training_objective`) |
| `story.dialogue` | `StoryProgress.dialogue` · `dialogue_event` · `dialogue_seen` (선배/신입/시스템 화자) |
| `story.campaign[]` | 제1~5장 잠김/시작 가능/진행 중/클리어/실패. 해금 사유는 `chapter3_unlock_reason`·`chapter3b_unlock_reason`·`training_unlock_reason`(제2장은 `start_chapter2`의 조건을 표시용으로만 반영, 시작은 엔진이 재검사) |
| `story.next` / `story.retry` / `story.graduation` | 다음 장(해금 사유), 체크포인트 존재 여부, 5장 모두 클리어 시 각 장 엔진 결과 요약 |
| `story.result` | 장 종료 시 `chapter_result`/`chapter2_result`/`chapter3_result`/`chapter3b_result`/`training_result` |
| `story.chapter2` | 두 요청 비교(`chapter2_comparison_lines`), 모드별 브리핑, 고객별 판정, 확정 실패 기록·선배 피드백 |
| `story.chapter3` / `chapter3b` | 진단 여부, 장애·대응 기록, 결과 카드(`chapter3_card`/`chapter3b_card`), 한 번만 보여 줄 카드 |
| `story.training` | `training_status()`(Stage 지도·준비 상태·답변 기록), 질문(정답 키 제외), 명령/블록 설명, 가상 주소, **Stage 1 통과 전·Stage 5 판단 전에는 구간 상태를 숨김** |
| `world.paths[].link/linkNote` | 근거 기반 전송 상태: `symptom`(진단 전) → `primary_down`/`congested`(제3장 진단 후) · `rerouted` · `recovering`. 자유 운영은 기존 규칙(대역폭 부족)과 수치 |
| `requests[].network.hidden` | 제5장 연수 사건 중에는 필요/가용 대역폭을 보내지 않음(Python 관제 화면과 같은 규칙) |

엔진 문장의 Tk 화면 이름(AIDC LINK, [배정 설정·선택], [Engineering Lab], [가상 터미널] 등)은 3D 위치 이름으로 바꿔 보냅니다(`campaign.WORDS`, 의미·수치 불변). 진단 탭 이름은 장마다 엔진 문장과 같게 표시합니다(장비 진단 / 네트워크 진단 / 진단).

## 행동 API (`POST /api/games/<id>/actions`) — 추가분

| type | 엔진 메서드 |
| --- | --- |
| `confirm_briefing` | 장에 따라 `confirm_story_arrival` / `confirm_chapter2_briefing` / `confirm_chapter3_briefing` / `confirm_chapter3b_briefing` |
| `mark_dialogue` | `mark_story_dialogue(event)` (표시 사실만) |
| `start_next_chapter {chapter}` | `start_chapter2/3/3b` · `start_training` → 성공 후 `checkpoints.capture()` (Python 메뉴와 같은 장 시작 지점). 화면의 장이 최신이 아니면 거부(중복 클릭 방지) |
| `wait_request`, `reject_request {reason}` | `wait_request`, `reject_request` |
| `diagnose` | 제3장 요청이면 `view_network_diagnosis`, 제4장 장애면 `view_hardware_diagnosis`(진단창을 연 기록 = 조치 잠금 해제). 제5장 연수 요청은 증상만 반환 |
| `ack_feedback {kind,key}` | `mark_chapter2_failure_seen` / `mark_chapter3_feedback_seen` / `mark_chapter3b_feedback_seen` |
| `lab_segment`, `lab_answer`, `lab_command`, `lab_next_stage`, `lab_focus_stage`, `lab_restart_incident` | `training_select_segment`, `training_answer`, `training_command`(choice/blocks/terminal → `run_command`), `start_next_stage`, `focus_training_stage`, `restart_training_incident` |
| `lab_blocks_preview` | `block_feedback()` (조회 전용, 기록 없음) |

시간 진행은 제2장부터 열린 요청이 있으면 허용합니다(기다리기가 실제 선택지). 제1장·튜토리얼은 Phase 4 규칙(작업 시작 후)을 유지합니다.

## 저장 · 체크포인트 · 재도전

- `POST /api/games {mode:'practice', chapter}` → `GameSession(start_chapter=2|3|'3b'|'lab')`의 새 연습 슬롯(진급 기록 아님, 체크포인트 없음).
- `POST /api/games/<id>/retry` → 현재 장의 체크포인트를 `checkpoints.restore()`로 **새 독점 슬롯**에 복사하고 그 슬롯의 장 시작 체크포인트도 남깁니다. 원본 슬롯은 읽기만 합니다(어댑터 행동은 이미 매번 저장되므로 저장 호출 없음). 연습/튜토리얼은 같은 종류의 새 저장.
- `POST /api/games/<id>/checkpoint {chapter}` → 메뉴의 "장 선택": 기록을 고르고 장 시작 지점을 새 슬롯으로 시작.
- 3D 전용 사이드카(`<slot>.3d.json`)는 엔진 DB를 기준으로 정합을 맞춥니다(없는 요청의 선택 기록 제거, 엔진 장/시각 스탬프). 손상된 슬롯은 파일을 건드리지 않고 400으로 알리고, 다른 프로세스가 연 슬롯은 잠금으로 거부합니다. 실패한 장 시작은 그 호출이 만든 파일(슬롯 복사본·사이드카·잠금)만 지웁니다.

## 화면 구성

- **내 모니터**: 요청함(제2장 두 요청 비교 카드, 대기/거절), 배정 계획(모드별 완료 예측, 각 배정안이 다른 고객에게 남기는 영향), 진단(제3장 네트워크 진단표, 제4장 복구 vs 이전 비교표, 제5장 증상만), 연수·Lab(제5장), 결과.
- **서버동**: 엔진 서버 A~D ↔ 랙 A-01~D-01. 두 고객 동시 배정, 장애/복구/이전 상태가 랙 색과 카드에 그대로 표시됩니다.
- **세계지도·네트워크동**: 고객 전송 경로와 AIDC 내부 업링크를 분리 표시. 진단 전에는 "원인 미확인".
- **선배 대화**: 단계마다 엔진 대사를 화면 아래에 보여 주고, [다음]은 페이지만 넘깁니다. 브리핑의 마지막 버튼만 실제 브리핑 확인 행동입니다. 결과 화면이 열려 있으면 대화는 기다립니다.
- **결과 화면**: 장 클리어/실패(엔진 판정), [다음 장 시작](해금 시), [현재 장 재도전 (새 슬롯)], 제2장 확정 실패 피드백, 제3/4장 결과 카드, 5장 완료 후 **운영 엔지니어 수료**(교육용 가상 등급 — 각 장의 엔진 결과를 나열할 뿐 새 점수 공식 없음).
- **힌트 감소**: 제2장은 위치를 모두 안내, 제3·4장은 탭 이름만, 제5장 Stage 5는 위치 안내 없음(엔진도 구조도 답을 숨김).

## 다음 Phase(6) 인계

- 새 고객·국가는 `network-data.js` 경로, 어댑터 `COUNTRY_CODES`, 스토어 `COUNTRIES` 세 곳을 함께 늘립니다.
- 새 장은 엔진에 장 진행 클래스와 `start_*`·`*_result`·`*_unlock_reason`이 생기면 `campaign.py`의 `ORDER/FIELDS`, `story_view`의 장별 뷰, `campaign-view.js`의 단계 제목/위치 표만 추가하면 됩니다.
- Lab 명령은 `lab_terminal.SUPPORTED`가 늘면 화면에 자동 반영됩니다(지원/미구현 목록을 스냅샷에서 읽음).
