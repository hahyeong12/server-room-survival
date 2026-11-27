# Phase 9 독립 리뷰 기록

2026-11-27. 사용자 요청에 따라 별도 리뷰 에이전트가 수행했습니다. 리뷰 에이전트에는 파일/실행 도구가 노출되지 않았으므로, 주 에이전트가 전달한 `career.py`, `senior_session.py` 전문과 `FreeShiftSession` 전체 동작 코드를 정적으로 검토했습니다. UI 문자열/공백을 줄인 전달본의 한계가 있습니다. 저장소 전체 파일 직접 읽기·독립 실행 테스트는 **미실행**입니다. 주 에이전트의 테스트와 독립 실행을 혼동하지 않습니다.

| 독립 지적 | 처리 | 주 에이전트 재현/검증 |
| --- | --- | --- |
| 사건이 있는데 해석 미응답을 평가 기회 없음으로 빼면 오답보다 유리해짐 | 사건별 최초 해석 평가, 미응답0, 반복 정답으로 점수 채우기 차단. 평가 지문 저장 | `test_unanswered_interpretation_is_zero_and_repeats_cannot_farm_score` |
| 교대 마무리 후 `_arm()`이 새 사건을 계속 만들 수 있음 | closing이면 신규 추첨 중단, 부모 복구 타이머는 계속 진행 | `test_wrapup_stops_new_incidents_but_finishes_running_work` |
| 저장 이력 검증이 얕음(방어 보완) | 규칙 지문·시각 범위·이력 길이·cursor 순서·사건/요청/유형/발생 시각 연결 검증 | 정상 재시작·잘못된 모드·지문/이력 검사 |

리뷰어는 seed+영속 cursor로 RNG를 독립 생성하고 같은 원자 단위에서 추가 블록을 복원하는 구조의 일관성을 확인했습니다. 최종 판정의 부모 완료 게이트·기한 준수·두 점수·안전 기록 결합도 확인했습니다. 부모/어댑터/UI 전체를 독립 검증한 것으로 주장하지 않습니다.

주 에이전트의 실제 브라우저 검증에서는 Python None/JS null 결과 표시 키 차이로 자유 결과창이 다시 열리는 결함을 발견해 `shiftfree` 공통 키로 수정했습니다. 이것은 독립 리뷰 발견으로 기록하지 않습니다.

## 2차 독립 리뷰 (2026-11-28, Claude Code 인계 후)

Codex 1차 리뷰의 한계(도구 없는 정적 전달본)를 보완하기 위해, 파일·실행 도구가 있는 별도 리뷰 에이전트가 **OS 임시 폴더의 분리 worktree**(`ed0fb99` + 미커밋 임시 우회 변경)에서 수행했습니다. 본 저장소·사용자 DB·브라우저·포트는 사용하지 않았습니다.

- 전체 직접 읽음: `free_session.py`, `operating_rules.py`(커밋본·변경본), `career.py`, `senior_session.py`, `linux_session.py`, `incidents/session.py`, `global_ops/session.py`, Phase9 테스트 3개. 부분: 루트 `session.py` 훅·`game.py`. diff로: adapter·incident_view·global_view·server·screens/world-main/career-view/incident-pane/api/game-view.
- 리뷰어가 실제 실행: Phase9 18+3, 사건/카탈로그/교대 58, Linux 110, adapter 54 모두 OK. 재현 스크립트 6개(trade-off, ToR 이전, 자유 학습 점수, OOM 동의, 감속 중복, 이전 규칙 지문).

| # | 확인된 지적(재현) | 처리 | 회귀 테스트 |
| --- | --- | --- | --- |
| 1 | 감속이 작업 위치가 아니라 요청 번호를 따라감(이전한 작업이 감속, 같은 랙 다른 작업은 누락) | 서버 원장 기준 `_residual_jobs` | `test_residual_follows_the_job_location_not_the_request_number` |
| 2 | 자유 교대에서 선택 CLI를 한 번 쓰면 모든 사건 해석이 0점 | 평가 v2: 사건별 출처 | `test_optional_cli_scores_per_incident_source` |
| 3 | 감속 구간이 표시(60분)보다 10분 짧음(시계는 구간 끝 시각) | 끝 시각 포함 비교 | `test_residual_window_matches_displayed_minutes` |
| 4 | 실제로 생기는 남은 작업량(≥20분)에서 우회가 이기는 경우가 거의 없어 "지배 전략 없음" 주장이 거짓 | 0.7/0.75배·90분으로 재조정, 도달 가능한 20/100분에서 7유형 측정 | `test_workaround_vs_root_fix_depends_on_remaining_work` |
| 5 | 동의 뒤 지연되면 기한 여유 없이 배치 축소 가능 | 실행 시점 기한 재확인(조건 거부) | `test_reduce_batch_rechecks_deadline_after_consent` |
| 6 | 이전 규칙 저장을 엉뚱한 오류 문구로 거부 | 원인을 밝히는 문구(자유·선임) | `test_outdated_rule_save_is_refused_with_a_clear_reason` |
| 7 | 정지와 겹친 구간을 감속 분으로 중복 기록 | 감속이 실제 적용 배율일 때만 기록 | 위 trade-off/창 테스트(원장 값) |

| 의심 지적(코드 읽기) | 처리 |
| --- | --- |
| 작업 종료 뒤에도 감속 표시, 다른 유형에 우회 문구, 판독은 정상인데 감속 | 실행 중 작업만 표시, 진단 후 해당 유형 문구만, 판독에 임시 우회 줄 추가 |
| 계약 분모에 진행 중 요청, 조건 확인 거부까지 안전 감점 | 결론 난 요청만, 정책·승인/동의 전 시도만 감점. 거절한 요청은 계약 미이행으로 계속 셈(보수적, 의도) |
| 변조된 저장의 빈 `next` | 근무 중 빈 일정 거부. 난도 변조는 저장 파일 직접 편집에 한정되어 범위 밖 |
| 공유 범위(냉각·UPS·ToR) 사건이 다른 작업의 기한 여유를 보지 않음 | **미수정, Phase10 인계.** 계획 중단·부하 이전으로 대응 가능해 필연적 실패는 아님 |

리뷰어는 seed+cursor 결정성, 같은 분 재호출 차단, 마무리 뒤 신규 차단, 동시 상한, 원자 롤백, 구 글로벌 저장 불변, MRO 우회 범위, 진급 증거가 정규 결과만 쓰는 점을 확인했습니다. 수정 후 재리뷰는 하지 않았고, 수정은 주 에이전트 테스트로 검증했습니다.

