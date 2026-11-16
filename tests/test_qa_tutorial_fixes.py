"""QA tutorial-001에서 발견한 문제(Q-01~Q-07)의 수정 검증. 창을 만들지 않는 비GUI 테스트입니다.

실제 화면 동작은 tests/qa/autoplay_tutorial.py(실제 마우스 입력 자동 플레이)로 따로 확인합니다.
"""
import re
import unittest
from unittest.mock import patch

from aidc.story.onboarding import GUIDED_LABELS, STEP_ACTIONS, guided_target
from aidc.ui import window_placement as wp
from server_console import rack_layout
from story_dialog import last_page_hides
from tutorial_highlight import clip_rect, mostly_visible
from ui import MessageDialog

AREA = (0, 0, 1536, 816)  # 125% 배율 1920x1080 노트북의 작업 영역(논리 좌표)
FRAME = (8, 31)          # Windows 11 창틀: 왼쪽 테두리, 제목줄+위 테두리


class FakeParent:
    """최대화된 관제실: 클라이언트 (0, 23) 1536x793, 창틀 좌표 (-8, -8)."""
    def winfo_toplevel(self): return self
    def update_idletasks(self): pass
    def winfo_rootx(self): return 0
    def winfo_rooty(self): return 23
    def winfo_width(self): return 1536
    def winfo_height(self): return 793
    def winfo_x(self): return -8
    def winfo_y(self): return -8


class FakeDialog:
    """숨긴 동안에는 Windows 기본(계단식) 위치를 root 좌표로 돌려주고 x/y는 (0, 0)인 Tk 대화창의 동작을 흉내 냅니다."""
    def __init__(self, default_root):
        self.default_root, self.outer, self.size, self.shown = default_root, (0, 0), (0, 0), False

    def geometry(self, spec):
        match = re.fullmatch(r'(?:(\d+)x(\d+))?([+-]\d+)([+-]\d+)', spec)
        if match.group(1):
            self.size = (int(match.group(1)), int(match.group(2)))
        self.outer = (int(match.group(3)), int(match.group(4)))

    def minsize(self, *_): pass
    def deiconify(self): self.shown = True
    def update_idletasks(self): pass
    def title(self): return 'fake'
    def winfo_viewable(self): return self.shown
    def winfo_rootx(self): return self.outer[0]+FRAME[0] if self.shown else self.default_root[0]
    def winfo_rooty(self): return self.outer[1]+FRAME[1] if self.shown else self.default_root[1]
    def winfo_x(self): return self.outer[0] if self.shown else 0
    def winfo_y(self): return self.outer[1] if self.shown else 0


class DialogPlacementTests(unittest.TestCase):
    """Q-02: 고객 요청서(880x660)가 기본 위치와 관계없이 관제실 중앙·작업 영역 안에 놓입니다."""
    # tutorial-001 실행에서 실제로 관측한 숨긴 창의 기본 root 좌표들
    DEFAULTS = [(164, 187), (60, 83), (34, 57), (138, 161), (8, 31), (0, 0)]

    def place(self, default_root, size=(880, 660)):
        dialog = FakeDialog(default_root)
        with patch.object(wp, 'work_area', return_value=AREA):
            wp.center_dialog(dialog, FakeParent(), size=size, minimum=(740, 560))
        return dialog

    def test_hidden_dialog_uses_parent_frame_offset(self):
        dialog = FakeDialog((164, 187))
        self.assertEqual(wp.frame_offset(dialog, FakeParent()), FRAME)  # 이전에는 (164, 187)

    def test_shown_dialog_uses_own_frame_offset(self):
        dialog = FakeDialog((164, 187))
        dialog.geometry('+100+50'); dialog.deiconify()
        self.assertEqual(wp.frame_offset(dialog, FakeParent()), FRAME)

    def test_request_dialog_same_centered_position_for_every_default(self):
        positions = set()
        for default in self.DEFAULTS:
            dialog = self.place(default)
            self.assertTrue(dialog.placement['inside_work_area'], default)
            client_bottom = dialog.winfo_rooty()+660
            self.assertLessEqual(client_bottom+8, AREA[3], default)  # 하단 버튼이 작업 표시줄에 가리지 않음
            positions.add((dialog.winfo_rootx(), dialog.winfo_rooty()))
            # 세로 중심 차이는 작업 영역 경계 때문에 생기는 몇 px 이내(이전: 110px)
            self.assertLessEqual(abs(dialog.placement['offset'][1]), 8, default)
            self.assertEqual(dialog.placement['offset'][0], 0, default)
        self.assertEqual(len(positions), 1)  # 여러 번 열어도 같은 위치

    def test_other_dialog_sizes_stay_inside(self):
        for size in ((820, 470), (1000, 740), (820, 640)):
            for default in self.DEFAULTS:
                dialog = self.place(default, size)
                self.assertTrue(dialog.placement['inside_work_area'], (size, default))

    def test_overflow_shift_moves_up_only_when_needed(self):
        self.assertEqual(wp.overflow_shift((328, 90), (880, 660), AREA), 0)
        self.assertEqual(wp.overflow_shift((328, 199), (880, 660), AREA), 812-(199+660+8))
        # 위쪽 경계 아래로는 올리지 않습니다.
        self.assertEqual(wp.overflow_shift((10, 6), (880, 900), AREA), 4-6)


class MainFrameBoundsTests(unittest.TestCase):
    """Q-01·Q-07: 메인 창은 작업 영역 안에 놓이고, 작업 영역이 작으면 그 안으로 줄어듭니다."""
    def check_inside(self, area, size):
        width, height, x, y = wp.main_window_bounds(area, size)
        self.assertGreaterEqual(x, area[0]); self.assertGreaterEqual(y, area[1])
        self.assertLessEqual(x+width+16, area[2]); self.assertLessEqual(y+height+39, area[3])
        return width, height

    def test_laptop_125_percent(self):
        width, height = self.check_inside(AREA, (1280, 860))
        self.assertEqual(width, 1280)
        self.assertGreaterEqual(height, 740)  # 이전 680보다 커져 본문 공간 확보

    def test_desktop_keeps_requested_size(self):
        self.assertEqual(self.check_inside((0, 0, 1920, 1032), (1280, 860)), (1280, 860))

    def test_mode_selection_and_offset_work_area(self):
        self.check_inside(AREA, (1000, 650))
        self.check_inside((-1920, 40, 0, 1080), (1280, 860))  # 왼쪽 보조 모니터·위쪽 작업 표시줄


class ConfirmButtonTests(unittest.TestCase):
    """Q-03: 마지막 페이지의 확인 버튼은 글자 타이핑 중에도 한 번에 그 행동을 합니다."""
    class Fake:
        next, _finish = MessageDialog.next, MessageDialog._finish

        def __init__(self, pages, index, shown, confirm=None):
            self.steps, self.index, self.shown, self.confirm = [('고객', 'x'*50)]*pages, index, shown, confirm
            self.full_text = 'x'*50
            self.revealed = self.destroyed = False
            self.rendered = 0

        def reveal(self): self.revealed, self.shown = True, len(self.full_text)
        def render(self): self.rendered += 1
        def destroy(self): self.destroyed = True

    def test_last_page_closes_on_first_click_while_typing(self):
        dialog = self.Fake(1, 0, shown=6)
        dialog.next()
        self.assertTrue(dialog.revealed and dialog.destroyed)

    def test_last_page_confirm_runs_once_while_typing(self):
        calls = []
        dialog = self.Fake(2, 1, shown=3, confirm=('고객 답변 확인', lambda: calls.append(1)))
        dialog.next()
        self.assertEqual(calls, [1])
        self.assertFalse(dialog.destroyed)  # 확인 행동은 기존 콜백이 처리합니다(동의 규칙 불변)

    def test_middle_page_first_click_only_reveals(self):
        dialog = self.Fake(3, 0, shown=3)
        dialog.next()
        self.assertTrue(dialog.revealed)
        self.assertEqual((dialog.index, dialog.destroyed), (0, False))
        dialog.next()
        self.assertEqual((dialog.index, dialog.rendered), (1, 1))


class StepTargetTests(unittest.TestCase):
    """Q-04: 새 튜토리얼에서 목표 카드 문구와 금색 강조 대상이 항상 같은 버튼을 가리킵니다."""
    def test_every_possible_target_is_named_in_goal_card(self):
        for step in ('request', 'preview', 'allocation', 'time'):
            for window_open in (False, True):
                for start_ready in (False, True):
                    name = guided_target(step, window_open, start_ready)
                    self.assertIn(GUIDED_LABELS[name], STEP_ACTIONS[step], (step, window_open, start_ready))

    def test_preview_points_to_allocation_button_not_inspector_tab(self):
        self.assertEqual(guided_target('preview'), 'allocation_button')
        self.assertEqual(guided_target('preview', window_open=True), 'plan_card')
        self.assertEqual(guided_target('allocation', True, True), 'dialog_start')
        self.assertEqual(guided_target('time'), 'time_buttons')


class HighlightVisibilityTests(unittest.TestCase):
    """Q-01: 상위 영역에 잘린(가려진) 대상에는 테두리를 그리지 않습니다."""
    def test_clipped_button_from_tutorial_001_is_not_visible(self):
        button = (190, 635, 198, 38)                        # [요청 확인]의 화면 좌표
        body, root = (176, 489, 1256, 82), (164, 187, 1280, 680)  # 82px로 눌린 본문 영역
        self.assertIsNone(clip_rect(button, [body, root]))
        self.assertFalse(mostly_visible(button, [body, root]))

    def test_visible_and_partly_cut(self):
        self.assertTrue(mostly_visible((10, 10, 100, 40), [(0, 0, 200, 200)]))
        self.assertFalse(mostly_visible((10, 180, 100, 40), [(0, 0, 200, 200)]))  # 절반만 보임
        self.assertEqual(clip_rect((10, 180, 100, 40), [(0, 0, 200, 200)]), (10, 180, 100, 20))


class RackAndDialogLayoutTests(unittest.TestCase):
    def test_rack_layout_tiers_avoid_overlap(self):
        # Q-06: 큰 숫자 배치는 모듈(아래 끝 107px)과 글자 블록(104px)이 겹치지 않는 높이에서만 씁니다.
        self.assertEqual(rack_layout(4, 260), 'tall')
        self.assertEqual(rack_layout(4, 214), 'tall_mid')
        self.assertEqual(rack_layout(4, 145), 'tall_mid')
        self.assertEqual(rack_layout(4, 120), 'wide')
        self.assertEqual(rack_layout(4, 80), 'compact')
        self.assertEqual(rack_layout(2, 120), 'wide')
        for rh in range(145, 215):  # 중간 배치: 모듈 아래 끝 < 요약 줄 위쪽
            modules_end = 46+32+27 if rh >= 175 else 46+24+20
            self.assertLess(modules_end, rh-49, rh)  # 요약 줄은 y+rh-49부터

    def test_last_page_hides_duplicate_buttons_only(self):
        self.assertTrue(last_page_hides(3, 4))
        self.assertFalse(last_page_hides(2, 4))
        self.assertTrue(last_page_hides(0, 1))


if __name__ == '__main__':
    unittest.main()
