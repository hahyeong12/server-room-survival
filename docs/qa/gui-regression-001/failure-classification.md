# 과거 실패 29개 개별 분류

A=메뉴·문구 기대값, B=구형 교육 준비, C=실행 환경, D=배치·가시성, E=실제 UI 결함 또는 의심. 복합 원인은 함께 표시합니다.

아래 전/후 결과는 해당 테스트 메서드 단위입니다. 하위 assertion 수와 다릅니다. 전체 traceback은 [JSON](failure-classification.json)에 있습니다.

## 1. B · PASS → PASS

`tests.test_play_modes_gui.PlayModesGuiTests.test_tutorial_finish_cannot_offer_next_story_chapter`

- 재현: `python -m tests.run_gui --output artifacts/reproduce.json tests.test_play_modes_gui.PlayModesGuiTests.test_tutorial_finish_cannot_offer_next_story_chapter`
- 조건: Windows125%·실제 Tk, 해당 테스트의 메모리/임시 DB fixture (C는 Git 없는 사본에서 발생)
- 기존 기대: 구형 prepare로 메뉴 튜토리얼 완료
- 현재 의도: 새 튜토리얼 1건 완료 후 본편 진급 차단
- 수정 필요/처리: 이전 QA에서 complete_onboarding으로 수정됨; 현재 PASS

## 2. B · PASS → PASS

`tests.test_play_modes_gui.PlayModesGuiTests.test_next_chapter_creates_boundary_checkpoint_and_heading`

- 재현: `python -m tests.run_gui --output artifacts/reproduce.json tests.test_play_modes_gui.PlayModesGuiTests.test_next_chapter_creates_boundary_checkpoint_and_heading`
- 조건: Windows125%·실제 Tk, 해당 테스트의 메모리/임시 DB fixture (C는 Git 없는 사본에서 발생)
- 기존 기대: 구형 prepare로 새 스토리 완료
- 현재 의도: 새 첫 근무 3건 완료 후 제2장 경계 보존
- 수정 필요/처리: 이전 QA 수정 유지; 현재 PASS

## 3. B · PASS → PASS

`tests.test_play_modes_gui.PlayModesGuiTests.test_checkpoint_failure_after_chapter_start_keeps_committed_story`

- 재현: `python -m tests.run_gui --output artifacts/reproduce.json tests.test_play_modes_gui.PlayModesGuiTests.test_checkpoint_failure_after_chapter_start_keeps_committed_story`
- 조건: Windows125%·실제 Tk, 해당 테스트의 메모리/임시 DB fixture (C는 Git 없는 사본에서 발생)
- 기존 기대: 구형 prepare 후 체크포인트 저장 실패 주입
- 현재 의도: 새 입문 완료 후 장 시작 실패도 기존 저장 보존
- 수정 필요/처리: 이전 QA 수정 유지; 현재 PASS

## 4. A · PASS → PASS

`tests.test_chapter3_gui.Chapter3PlayGuiTests.test_wrong_response_shows_observed_feedback_and_keeps_the_mission_open`

- 재현: `python -m tests.run_gui --output artifacts/reproduce.json tests.test_chapter3_gui.Chapter3PlayGuiTests.test_wrong_response_shows_observed_feedback_and_keeps_the_mission_open`
- 조건: Windows125%·실제 Tk, 해당 테스트의 메모리/임시 DB fixture (C는 Git 없는 사본에서 발생)
- 기존 기대: Chapter 3 제목
- 현재 의도: 제3장 제목; 제4장과 구분
- 수정 필요/처리: 이전 QA에서 수정됨; 현재 PASS

## 5. B · ERROR → PASS

`tests.test_story_slots.SlotMenuGuiTests.test_two_new_slots_keep_time_resources_score_and_progress_separate`

- 재현: `python -m tests.run_gui --output artifacts/reproduce.json tests.test_story_slots.SlotMenuGuiTests.test_two_new_slots_keep_time_resources_score_and_progress_separate`
- 조건: Windows125%·실제 Tk, 해당 테스트의 메모리/임시 DB fixture (C는 Git 없는 사본에서 발생)
- 기존 기대: 새 슬롯도 Inspector 확인이 필요한 구형 prepare
- 현재 의도: 새 첫 근무 3건 완료와 별도 슬롯의 부분 진행; 구 슬롯 호환은 독립 검사
- 수정 필요/처리: complete_onboarding 사용 및 새 슬롯 부분 준비·기록 3건 기대; 구형 GUI 검사 추가

## 6. C · PASS → PASS

`tests.test_story_slots.SlotFilesTests.test_git_ignores_slots_journal_wal_shm_and_lease`

- 재현: `python -m tests.run_gui --output artifacts/reproduce.json tests.test_story_slots.SlotFilesTests.test_git_ignores_slots_journal_wal_shm_and_lease`
- 조건: Windows125%·실제 Tk, 해당 테스트의 메모리/임시 DB fixture (C는 Git 없는 사본에서 발생)
- 기존 기대: Git 없는 임시 사본에서도 git check-ignore 성공
- 현재 의도: 실제 Git 작업 트리에서 슬롯·보조·잠금 파일 제외 검사
- 수정 필요/처리: Git 작업 트리 러너 사용; 현재 PASS, .gitignore 변경 없음

## 7. A · FAIL → PASS

`tests.test_allocation_flow_gui.ResultButtonsGuiTests.test_success_result_keeps_retry_button_visible`

- 재현: `python -m tests.run_gui --output artifacts/reproduce.json tests.test_allocation_flow_gui.ResultButtonsGuiTests.test_success_result_keeps_next_chapter_and_menu_buttons_visible`
- 조건: Windows125%·실제 Tk, 해당 테스트의 메모리/임시 DB fixture (C는 Git 없는 사본에서 발생)
- 기존 기대: 성공 결과창에 항상 retry
- 현재 의도: 성공은 다음 장·장 선택·메뉴; 실패는 재도전·장 선택·메뉴
- 수정 필요/처리: 실제 action_bar 버튼 집합·가시성 유지

## 8. A · ERROR → PASS

`tests.test_chapter2_gui.FailureFeedbackGuiTests.test_us_first_does_not_show_failure_until_the_request_is_actually_lost`

- 재현: `python -m tests.run_gui --output artifacts/reproduce.json tests.test_chapter2_gui.FailureFeedbackGuiTests.test_us_first_does_not_show_failure_until_the_request_is_actually_lost`
- 조건: Windows125%·실제 Tk, 해당 테스트의 메모리/임시 DB fixture (C는 Git 없는 사본에서 발생)
- 기존 기대: 실패 교육창 full_text와 close_button
- 현재 의도: ChapterFailureDialog의 실패 판정·회사·원인 카드; 현재 작업은 계속 가능
- 수정 필요/처리: 실제 카드/판정 위젯 검사; 계속 진행 불변조건 유지

## 9. A · FAIL → PASS

`tests.test_chapter2_gui.PracticeAndRetryGuiTests.test_result_dialog_has_retry_and_retry_opens_a_new_practice_slot`

- 재현: `python -m tests.run_gui --output artifacts/reproduce.json tests.test_chapter2_gui.PracticeAndRetryGuiTests.test_result_dialog_has_retry_and_retry_opens_a_new_practice_slot`
- 조건: Windows125%·실제 Tk, 해당 테스트의 메모리/임시 DB fixture (C는 Git 없는 사본에서 발생)
- 기존 기대: 성공창 retry 버튼으로 연습 재시작
- 현재 의도: 성공창은 다음 장 우선, 기존 관제실 재도전 기능은 새 연습 슬롯
- 수정 필요/처리: 현재 버튼 집합과 retry_chapter2 결과를 각각 검사

## 10. A · FAIL → PASS

`tests.test_chapter2_gui.PracticeAndRetryGuiTests.test_story_menu_offers_chapter_one_chapter_two_and_continue`

- 재현: `python -m tests.run_gui --output artifacts/reproduce.json tests.test_chapter2_gui.PracticeAndRetryGuiTests.test_story_menu_offers_chapter_one_chapter_two_and_continue`
- 조건: Windows125%·실제 Tk, 해당 테스트의 메모리/임시 DB fixture (C는 Git 없는 사본에서 발생)
- 기존 기대: 스토리 메뉴 new/continue/back만
- 현재 의도: 장 선택 chapters 추가; 공개 연습은 자유·연습 하위 메뉴
- 수정 필요/처리: chapters 포함한 정확한 키 집합 검사

## 11. D · FAIL → PASS

`tests.test_conditions.ConditionGuiTests.test_mode_labels_fit_minimum_window_during_negotiation_and_shortage`

- 재현: `python -m tests.run_gui --output artifacts/reproduce.json tests.test_conditions.ConditionGuiTests.test_mode_labels_fit_minimum_window_during_negotiation_and_shortage`
- 조건: Windows125%·실제 Tk, 해당 테스트의 메모리/임시 DB fixture (C는 Git 없는 사본에서 발생)
- 기존 기대: 최소 창의 버튼 폭 >= 여백을 포함한 요청 폭 179
- 현재 의도: 글자153px와 테두리가 실제162px 버튼 안에 표시
- 수정 필요/처리: 실제 폰트 글자 폭+테두리+최소 여백 검사; 높이·창 경계 검사는 유지

## 12. D · FAIL → FAIL

`tests.test_console.ConsoleTests.test_automatic_notice_opens_matching_request_without_advancing_time`

- 재현: `python -m tests.run_gui --output artifacts/reproduce.json tests.test_console.ConsoleTests.test_automatic_notice_opens_matching_request_without_advancing_time`
- 조건: Windows125%·실제 Tk, 해당 테스트의 메모리/임시 DB fixture (C는 Git 없는 사본에서 발생)
- 기존 기대: 자동 접수 후 목록 전체가 body 하단 이내
- 현재 의도: 목록의 실제 행과 조작이 부모에 가리지 않아야 함
- 수정 필요/처리: 외곽1px만 초과. 행 끝513<부모514, 마지막 픽셀 hit도 Treeview라 내용 차단 없음 확인. 엄격한 기존 assertion은 유지; 향후 실제 내용 기준으로 정비할 항목

## 13. A · FAIL → PASS

`tests.test_console.ConsoleTests.test_japan_time_button_updates_progress_clock_and_saved_allocation`

- 재현: `python -m tests.run_gui --output artifacts/reproduce.json tests.test_console.ConsoleTests.test_japan_time_button_updates_progress_clock_and_saved_allocation`
- 조건: Windows125%·실제 Tk, 해당 테스트의 메모리/임시 DB fixture (C는 Git 없는 사본에서 발생)
- 기존 기대: 업무 안내 본문에 +10
- 현재 의도: 본문은 시간 빨리감기 묶음을 안내; +10은 실제 버튼
- 수정 필요/처리: 본문과 실제 +10 버튼을 모두 검사; 시간·저장·자원 검사는 유지

## 14. D/E · FAIL → FAIL

`tests.test_play_modes_gui.PlayModesGuiTests.test_all_menu_buttons_fit_three_resolutions`

- 재현: `python -m tests.run_gui --output artifacts/reproduce.json tests.test_play_modes_gui.PlayModesGuiTests.test_all_menu_buttons_fit_three_resolutions`
- 조건: Windows125%·실제 Tk, 해당 테스트의 메모리/임시 DB fixture (C는 Git 없는 사본에서 발생)
- 기존 기대: 세 메뉴의 content 전체가 창 안
- 현재 의도: 핵심 버튼은 접근 가능; 제목 장식·버전도 잘리지 않는 것이 바람직
- 수정 필요/처리: 자유·연습 content 712px>최소650px; 버튼은 보이지만 장식/버전 잘림. assertion 유지

## 15. D · FAIL → FAIL

`tests.test_server_allocation.ServerConsoleTests.test_layout_and_chip_text_at_three_resolutions`

- 재현: `python -m tests.run_gui --output artifacts/reproduce.json tests.test_server_allocation.ServerConsoleTests.test_layout_and_chip_text_at_three_resolutions`
- 조건: Windows125%·실제 Tk, 해당 테스트의 메모리/임시 DB fixture (C는 Git 없는 사본에서 발생)
- 기존 기대: 활성 목록 전체가 body 하단 이내
- 현재 의도: 랙 글자·컨트롤·목록의 내용이 실제로 보여야 함
- 수정 필요/처리: 외곽1px만 초과, 실제 행 끝513<부모514 및 마지막 픽셀 Treeview hit 확인. 기능 차단 없는 엄격한 기대값으로 분류; 기존 assertion 유지

## 16. D/E+A · FAIL → FAIL

`tests.test_story.StoryGuiTests.test_actual_tk_three_resolutions_through_all_tutorial_stages`

- 재현: `python -m tests.run_gui --output artifacts/reproduce.json tests.test_story.StoryGuiTests.test_actual_tk_three_resolutions_through_all_tutorial_stages`
- 조건: Windows125%·실제 Tk, 해당 테스트의 메모리/임시 DB fixture (C는 Git 없는 사본에서 발생)
- 기존 기대: Inspector 높이190px와 옛 완료 문구
- 현재 의도: 구형 저장에서 전력·확인 조작이 보여야 하고 완료 결과는 실제 회사/기록
- 수정 필요/처리: 완료 문구를 실제 결과 비교로 정비; Inspector132/162px 잘림은 FAIL 유지

## 17. D · FAIL → PASS

`tests.test_story_patch.PatchGuiTests.test_completion_all_controls_fit_three_resolutions_and_minimum_dialog`

- 재현: `python -m tests.run_gui --output artifacts/reproduce.json tests.test_story_patch.PatchGuiTests.test_completion_all_controls_fit_three_resolutions_and_minimum_dialog`
- 조건: Windows125%·실제 Tk, 해당 테스트의 메모리/임시 DB fixture (C는 Git 없는 사본에서 발생)
- 기존 기대: 결과 본문 전체가 스크롤 없이 창 안
- 현재 의도: 본문은 스크롤 가능, 하단 행동은 고정
- 수정 필요/처리: 요약표/다음 단계 각각 실제 viewport에 드러난 뒤 경계 검사; 행동 고정 검사는 유지

## 18. A · FAIL → PASS

`tests.test_story_patch.PatchGuiTests.test_completion_screen_uses_actual_results_and_four_actions`

- 재현: `python -m tests.run_gui --output artifacts/reproduce.json tests.test_story_patch.PatchGuiTests.test_completion_screen_uses_actual_results_and_current_actions`
- 조건: Windows125%·실제 Tk, 해당 테스트의 메모리/임시 DB fixture (C는 Git 없는 사본에서 발생)
- 기존 기대: 완료창 free/status/review/retry 등 6키
- 현재 의도: 성공 행동은 next/chapters/modes 3개, chapter2는 next 별칭
- 수정 필요/처리: 현재 action_bar 3개와 별칭·실제 결과·자원 반환 검사

## 19. A · ERROR → PASS

`tests.test_story_patch.PatchGuiTests.test_direct_free_transition_resumes_its_own_existing_game`

- 재현: `python -m tests.run_gui --output artifacts/reproduce.json tests.test_story_patch.PatchGuiTests.test_direct_free_transition_resumes_its_own_existing_game`
- 조건: Windows125%·실제 Tk, 해당 테스트의 메모리/임시 DB fixture (C는 Git 없는 사본에서 발생)
- 기존 기대: 완료창 free 버튼 직접 전환
- 현재 의도: 메인 메뉴 → 자유·연습 → 자유 운영
- 수정 필요/처리: 실제 메뉴 위젯 경로로 전환; 기존 자유 운영 진행/스토리 저장 보존 검사 유지

## 20. A · FAIL → PASS

`tests.test_story_patch.PatchGuiTests.test_status_offers_chapter_two_start_button_after_chapter_one`

- 재현: `python -m tests.run_gui --output artifacts/reproduce.json tests.test_story_patch.PatchGuiTests.test_status_offers_chapter_two_start_button_after_chapter_one`
- 조건: Windows125%·실제 Tk, 해당 테스트의 메모리/임시 DB fixture (C는 Git 없는 사본에서 발생)
- 기존 기대: 제1장 첫 출근 제목과 옛 결과 버튼
- 현재 의도: 제1장 첫 근무·제2장 시작 가능, 현재 결과 행동 3개
- 수정 필요/처리: 현황 제목·정확한 버튼 집합 갱신

## 21. A · ERROR → PASS

`tests.test_story_patch.PatchGuiTests.test_transition_save_failure_keeps_window_timer_and_database_open`

- 재현: `python -m tests.run_gui --output artifacts/reproduce.json tests.test_story_patch.PatchGuiTests.test_transition_save_failure_keeps_window_timer_and_database_open`
- 조건: Windows125%·실제 Tk, 해당 테스트의 메모리/임시 DB fixture (C는 Git 없는 사본에서 발생)
- 기존 기대: 삭제된 free 버튼에서 저장 실패
- 현재 의도: 메인 메뉴로 나갈 때도 저장 실패면 현재 게임 유지
- 수정 필요/처리: modes 버튼에서 저장 오류 주입; 창/타이머/DB 불변조건 유지

## 22. A/B · FAIL → PASS

`tests.test_story_slots.SlotMenuGuiTests.test_new_story_character_emphasis_and_events_are_unchanged`

- 재현: `python -m tests.run_gui --output artifacts/reproduce.json tests.test_story_slots.SlotMenuGuiTests.test_new_story_character_emphasis_and_events_are_unchanged`
- 조건: Windows125%·실제 Tk, 해당 테스트의 메모리/임시 DB fixture (C는 Git 없는 사본에서 발생)
- 기존 기대: 신입 화자 시작, Server A→Inspector
- 현재 의도: 새 첫 근무는 선배→신입, 시작 안내 후 요청 단계; 서버 선택만으로 진전 없음
- 수정 필요/처리: 화자/비활성 초상화·안내 종료·중복 재표시 방지 검사; 구형 별도 검사

## 23. B · FAIL → PASS

`tests.test_story_slots.SlotMenuGuiTests.test_new_story_full_chapter_through_real_widgets_preserves_old_record`

- 재현: `python -m tests.run_gui --output artifacts/reproduce.json tests.test_story_slots.SlotMenuGuiTests.test_new_story_full_chapter_through_real_widgets_preserves_old_record`
- 조건: Windows125%·실제 Tk, 해당 테스트의 메모리/임시 DB fixture (C는 Git 없는 사본에서 발생)
- 기존 기대: 새 첫 근무도 Server A·운영 확인과 120분1건
- 현재 의도: 새 첫 근무는 SG→JP→US 각30분; 매번 반환 후 다음 접수
- 수정 필요/처리: 세 건을 실제 GUI 위젯으로 처리; 원장·선택 슬롯·점수·구 저장 바이트 보존; 구형10단계 별도 검사

## 24. A/B · FAIL → PASS

`tests.test_story_slots.SlotMenuGuiTests.test_new_story_starts_at_first_monologue_even_with_legacy_completion`

- 재현: `python -m tests.run_gui --output artifacts/reproduce.json tests.test_story_slots.SlotMenuGuiTests.test_new_story_starts_at_first_monologue_even_with_legacy_completion`
- 조건: Windows125%·실제 Tk, 해당 테스트의 메모리/임시 DB fixture (C는 Git 없는 사본에서 발생)
- 기존 기대: 새 스토리 첫 신입 독백
- 현재 의도: 새 첫 근무 안내는 선배 시작; 이전 완료 저장은 그대로
- 수정 필요/처리: 입문 pages의 실제 첫 대사/화자 검사; 시간·자원·기록·구 저장 보존 유지

## 25. A · FAIL → PASS

`tests.test_story_slots.SlotMenuGuiTests.test_story_choice_and_back_open_no_database`

- 재현: `python -m tests.run_gui --output artifacts/reproduce.json tests.test_story_slots.SlotMenuGuiTests.test_story_choice_and_back_open_no_database`
- 조건: Windows125%·실제 Tk, 해당 테스트의 메모리/임시 DB fixture (C는 Git 없는 사본에서 발생)
- 기존 기대: 스토리 메뉴 3개 키
- 현재 의도: 장 선택 chapters 포함4개
- 수정 필요/처리: 정확한 현재 키와 DB를 열지 않는 불변조건 유지

## 26. D · FAIL → PASS

`tests.test_tutorial_ux.TutorialGuiTests.test_dialogues_center_on_game_at_three_resolutions_and_offsets`

- 재현: `python -m tests.run_gui --output artifacts/reproduce.json tests.test_tutorial_ux.TutorialGuiTests.test_dialogues_center_on_game_at_three_resolutions_and_offsets`
- 조건: Windows125%·실제 Tk, 해당 테스트의 메모리/임시 DB fixture (C는 Git 없는 사본에서 발생)
- 기존 기대: 한 페이지 교육창에도 보조 종료/마지막 안내가 모두 보임
- 현재 의도: 마지막 페이지에는 중복 종료/마지막 안내를 의도적으로 숨김
- 수정 필요/처리: 마지막 페이지 숨김을 명시 검사; 보이는 버튼·초상화·창 중심/작업영역 검사는 유지

## 27. D/E · FAIL → FAIL

`tests.test_tutorial_ux.TutorialGuiTests.test_each_target_fits_three_resolutions_and_maximized_game`

- 재현: `python -m tests.run_gui --output artifacts/reproduce.json tests.test_tutorial_ux.TutorialGuiTests.test_each_target_fits_three_resolutions_and_maximized_game`
- 조건: Windows125%·실제 Tk, 해당 테스트의 메모리/임시 DB fixture (C는 Git 없는 사본에서 발생)
- 기존 기대: 모든 구형 교육 대상이 작은 창에 표시
- 현재 의도: 구형 저장도 Inspector확인·비교 버튼을 조작할 수 있어야 함
- 수정 필요/처리: 1000x650/1280x680에서 resources 버튼 unmapped; 작은 preview 대상도 미표시. assertion 유지

## 28. A · ERROR → PASS

`tests.test_v091e.ChapterWindowTests.test_chapter_dialog_is_centered_on_game_window`

- 재현: `python -m tests.run_gui --output artifacts/reproduce.json tests.test_v091e.ChapterWindowTests.test_chapter_dialog_is_centered_on_game_window`
- 조건: Windows125%·실제 Tk, 해당 테스트의 메모리/임시 DB fixture (C는 Git 없는 사본에서 발생)
- 기존 기대: 완료창 free/status/review 버튼도 중앙 배치 검사
- 현재 의도: 결과창은 next/chapters/modes
- 수정 필요/처리: 현재 실제 행동 버튼으로 가시성 검사; 중앙 좌표 검사는 유지

## 29. A · ERROR → PASS

`tests.test_v091e.ChapterWindowTests.test_chapter_dialog_stays_inside_work_area_on_small_window`

- 재현: `python -m tests.run_gui --output artifacts/reproduce.json tests.test_v091e.ChapterWindowTests.test_chapter_dialog_stays_inside_work_area_on_small_window`
- 조건: Windows125%·실제 Tk, 해당 테스트의 메모리/임시 DB fixture (C는 Git 없는 사본에서 발생)
- 기존 기대: 작은 완료창의 free/status/review 버튼
- 현재 의도: 현재 행동3개가 작업 영역 안
- 수정 필요/처리: 현재 버튼으로 경계 검사; 작업영역 검사는 유지
