"""기존 운영 회귀 시나리오에 신규 요청의 실제 동의 절차를 준비합니다."""


def start_with_consent(owner, mode):
    """GUI 또는 세션을 통해 시작하되, 고객 조건을 바꾸지 않고 필요한 동의를 받습니다."""
    session = getattr(owner, 'session', owner)
    run = session.current
    if (run.request['status'] in ('new', 'review', 'waiting') and run.conditions
            and mode not in run.conditions['allowed_modes'] and not run.proposals):
        session.propose_alternative()
        if not session.review_alternative():
            raise AssertionError('이 시나리오는 고객이 거절한 모드로 시작할 수 없습니다.')
    return owner.choose_plan(mode)


def start_legacy_plan(owner, mode):
    """최초 조건이 없던 이전 저장의 운영 시나리오를 명시적으로 구성합니다."""
    session = getattr(owner, 'session', owner)
    session.current.conditions = {}
    return owner.choose_plan(mode)


def dismiss_story_popups(app, root):
    """안내/결과 창만 닫습니다. 실제 교육 확인이나 게임 행동을 대신하지 않습니다."""
    for _ in range(4):
        root.update()
        feedback = getattr(app, 'feedback_window', None)
        guide = app.story_window
        if feedback is not None and feedback.winfo_exists():
            feedback.close_button.invoke()
        elif guide is not None and guide.winfo_exists():
            guide.close_button.invoke()
        else:
            break
    root.update()


def start_via_dialog(app, index=None):
    """v0.9-2b-1: 메인 [배정 설정·선택]은 설정창을 열기만 합니다. 창에서 계획(없으면 자동 추천)을 직접 고르고 시작합니다."""
    app.action_buttons['start'].invoke()
    dialog = app.allocation_window
    app.root.update()
    (dialog.auto_button if index is None else dialog.plan_buttons[index]).invoke()
    dialog.start_button.invoke()
    app.root.update()
    return dialog


def reveal_scroll_widget(area, widget):
    """스크롤 본문의 개별 요소가 실제 화면에 닿는지 확인하기 위한 표시 조작입니다."""
    area.update_idletasks()
    top = widget.winfo_rooty()-area.body.winfo_rooty()
    height = area.body.winfo_height()
    maximum = max(0, height-area.canvas.winfo_height())
    area.canvas.yview_moveto(min(top, maximum)/max(1, height))
    area.update_idletasks()


def assert_tree_row_visible(case, tree, item, boundary):
    """외곽 테두리 대신 실제 행의 끝·클릭 좌표가 부모 안에서 노출되는지 검사합니다."""
    box = tree.bbox(item)
    case.assertTrue(box, f'표시되지 않은 행: {item}')
    x, y, width, height = box
    left, top = tree.winfo_rootx()+x, tree.winfo_rooty()+y
    case.assertGreaterEqual(left, boundary.winfo_rootx())
    case.assertGreaterEqual(top, boundary.winfo_rooty())
    case.assertLessEqual(left+width, boundary.winfo_rootx()+boundary.winfo_width())
    case.assertLessEqual(top+height, boundary.winfo_rooty()+boundary.winfo_height())
    case.assertIs(tree.winfo_containing(left+width//2, top+height//2), tree)
    case.assertIs(tree.winfo_containing(left+width//2, top+height-1), tree)
    case.assertEqual(tree.identify_row(y+height//2), str(item))
    return box


def complete_onboarding(s, mode='performance'):
    """v0.9-4b 메뉴의 [튜토리얼]/[스토리 새로 시작]은 새 입문(onboarding: 튜토리얼 1건, 첫 근무 3건) 흐름입니다.
    구형 10단계 교육용 test_story_patch.prepare()/finish()는 'Inspector 확인' 단계를 가정하므로 이 흐름에 맞지 않습니다.
    실제 세션 행동(도착 확인 → 요청 열람 → 미리보기 → 배정 → 시간 진행)만으로 입문을 끝냅니다."""
    assert s.story.onboarding is not None, '구형 저장에는 test_story_patch.prepare()/finish()를 사용하세요.'
    if s.story.ui_step == 'arrival':
        s.confirm_story_arrival()
    for _ in range(6):
        if s.story.ui_done:
            return
        rid = s.story.onboarding.rid
        s.read_conversation(rid)
        s.inspect_story_preview(rid)
        s.choose_plan(mode)
        for _ in range(30):
            if not s.runs[rid].state.allocated:
                break
            s.advance_time(10)
    raise AssertionError('입문 업무가 끝나지 않습니다.')
