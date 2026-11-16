"""v0.9-4b UI 리디자인의 표시 규칙. 창을 만들지 않는 순수 함수와 가짜 객체만 사용합니다."""
import unittest
from types import SimpleNamespace as NS

from aidc.story.onboarding import CARD_STEPS, OnboardingProgress
from aidc.ui.goal_card import pip_text
from aidc.ui.result_presentation import complete_actions, success_headline, success_mentor_lines, success_tiles
from aidc.ui.window_placement import frame_offset
from allocation_dialog import mode_badges


def noop():
    return None


class SuccessViewTests(unittest.TestCase):
    def result(self, **extra):
        data = {'score': 92, 'on_time': True, 'gpu': 4, 'power': 3}
        data.update(extra)
        return data

    def test_tiles_show_score_deadline_and_returned_resources(self):
        tiles = success_tiles(self.result())
        self.assertEqual([t[0] for t in tiles], ['운영 점수', '완료 기한', '반환 자원'])
        self.assertEqual(tiles[0][1:], ('92점', 'green'))
        self.assertEqual(tiles[1][1:], ('기한 내 완료', 'green'))
        self.assertIn('GPU 4', tiles[2][1])

    def test_deadline_tile_uses_red_for_late_and_gray_for_not_evaluated(self):
        self.assertEqual(success_tiles(self.result(on_time=False))[1][1:], ('기한 초과', 'red'))
        self.assertEqual(success_tiles(self.result(on_time=None))[1][1:], ('평가 제외', 'gray'))

    def test_headline_distinguishes_tutorial_shift_and_single_job(self):
        self.assertIn('입문', success_headline(self.result(), tutorial=True))
        self.assertIn('3건', success_headline(self.result(jobs=[1, 2, 3])))
        self.assertIn('업무 완료', success_headline(self.result()))

    def test_mentor_text_is_short(self):
        for tutorial in (True, False):
            lines = success_mentor_lines(tutorial)
            self.assertLessEqual(len(lines), 2)
            self.assertTrue(all(len(line) <= 60 for line in lines))


class ResultButtonTests(unittest.TestCase):
    def keys(self, entries):
        return [e[0] for e in entries]

    def test_tutorial_keeps_only_retry_learning_and_main_menu(self):
        entries = complete_actions(True, None, '', noop, noop, noop)
        self.assertEqual(self.keys(entries), ['retry', 'modes'])
        self.assertEqual([e[1] for e in entries], ['다시 학습', '메인 메뉴'])
        self.assertEqual([e[3] for e in entries], [False, True])

    def test_success_with_next_chapter_has_next_as_the_only_primary(self):
        entries = complete_actions(False, noop, '제2장 · 시작', noop, noop, noop)
        self.assertEqual(self.keys(entries), ['next', 'chapters', 'modes'])
        self.assertEqual([e[3] for e in entries], [True, False, False])

    def test_failure_makes_retry_primary_without_free_mode_or_review_buttons(self):
        entries = complete_actions(False, None, '', noop, noop, noop, failed=True)
        self.assertEqual(self.keys(entries), ['retry', 'chapters', 'modes'])
        self.assertEqual([e[3] for e in entries], [True, False, False])
        self.assertEqual(entries[0][1], '체크포인트부터 다시 도전')
        self.assertNotIn('free', self.keys(entries))

    def test_practice_failure_uses_new_slot_wording(self):
        entry = complete_actions(False, None, '', noop, None, noop, failed=True, practice=True)[0]
        self.assertEqual(entry[1], '다시 도전 · 새 슬롯')

    def test_never_more_than_three_buttons_and_exactly_one_primary(self):
        for tutorial in (True, False):
            for nxt in (None, noop):
                for retry in (None, noop):
                    for chapter in (None, noop):
                        for failed in (False, True):
                            entries = complete_actions(tutorial, nxt, 'next', retry, chapter, noop, failed=failed)
                            self.assertLessEqual(len(entries), 3)
                            self.assertEqual(sum(e[3] for e in entries), 1, (tutorial, nxt, retry, chapter, failed))


class ModeBadgeTests(unittest.TestCase):
    def row(self, **extra):
        data = {'on_time': True, 'due_label': '11:30', 'late_minutes': 0, 'agreed': True, 'status': '고객 원래 요청'}
        data.update(extra)
        return data

    def test_deadline_and_consent_are_marked_by_symbol_and_color(self):
        self.assertEqual(mode_badges(self.row()), [('✔ 기한 11:30 준수', 'green'), ('✔ 고객 원래 요청', 'cyan')])
        late = mode_badges(self.row(on_time=False, late_minutes=10, agreed=False, status='고객 동의 필요'))
        self.assertEqual(late, [('✖ 기한 11:30보다 10분 늦음', 'red'), ('⚠ 고객 동의 필요', 'amber')])

    def test_no_deadline_badge_when_the_request_has_no_deadline(self):
        self.assertEqual(mode_badges(self.row(on_time=None)), [('✔ 고객 원래 요청', 'cyan')])


class TutorialStepTests(unittest.TestCase):
    def test_five_named_steps(self):
        self.assertEqual(len(CARD_STEPS), 5)
        self.assertEqual([k for k, _ in CARD_STEPS], ['arrival', 'request', 'preview', 'allocation', 'time'])

    def progress(self, step, kind='tutorial', **extra):
        data = {'kind': kind, 'step': step}
        if step != 'arrival':
            data.update(request_ids=[1], introduced=True)
        data.update(extra)
        return OnboardingProgress(**data)

    def test_card_marks_done_current_and_todo_steps_with_one_action(self):
        card = self.progress('preview', read=[1]).card
        self.assertEqual((card['step_no'], card['total'], card['title']), (3, 5, '배정 검토'))
        self.assertEqual([state for _, state in card['pips']], ['done', 'done', 'current', 'todo', 'todo'])
        self.assertIn('배정 설정', card['action'])
        self.assertTrue(card['mentor'])

    def test_first_step_and_shift_job_counter(self):
        card = OnboardingProgress(kind='shift').card
        self.assertEqual((card['step_no'], card['job']), (1, (0, 3)))
        self.assertEqual([state for _, state in card['pips']], ['current', 'todo', 'todo', 'todo', 'todo'])

    def test_completed_tutorial_has_no_action_and_all_steps_done(self):
        progress = self.progress('complete', read=[1], reviewed=[1], completed=[1])
        card = progress.card
        self.assertTrue(card['done'])
        self.assertEqual(card['action'], '')
        self.assertTrue(all(state == 'done' for _, state in card['pips']))

    def test_arrival_dialogue_is_a_short_conversation(self):
        for kind in ('tutorial', 'shift'):
            pages = OnboardingProgress(kind=kind).pages
            self.assertEqual([role for role, _ in pages], ['mentor', 'player', 'mentor', 'mentor'])
            for _, text in pages:
                # 문장마다 줄을 나누므로 한 줄은 짧고, 페이지 전체도 몇 줄을 넘지 않습니다.
                self.assertTrue(all(len(line) <= 40 for line in text.split('\n')), text)
                self.assertLessEqual(text.count('\n'), 8)

    def test_numbered_steps_are_each_on_their_own_line(self):
        for kind, items in (('tutorial', ('① 요청 확인', '② 배정 검토', '③ 작업 시작', '④ 시간 빨리감기')),
                            ('shift', ('① 싱가포르', '② 일본', '③ 미국'))):
            text = OnboardingProgress(kind=kind).pages[2][1]
            lines = text.split('\n')
            for item in items:
                self.assertIn(item, lines)
            self.assertIn('', lines)  # 안내 문장과 목록 사이의 빈 줄(문단 구분)

    def test_later_steps_show_a_single_goal_page(self):
        self.assertEqual(len(self.progress('request').pages), 1)

    def test_every_step_names_one_click_target(self):
        for key, _ in CARD_STEPS[1:]:
            self.assertIn(key, ('request', 'preview', 'allocation', 'time'))
            card = self.progress(key, read=[1] if key != 'request' else [],
                                 reviewed=[1] if key in ('allocation', 'time') else []).card
            self.assertTrue(card['action'].startswith('[') or '[' in card['action'])


class Chapter1DialogueLayoutTests(unittest.TestCase):
    """제1장 교육 대화: 의미 단위 줄바꿈과 원래 안내(버튼 이름·수치·순서) 보존."""
    def pages(self):
        from story import GUIDES
        return [(key, line.text) for key, (_, lines) in GUIDES.items() for line in lines]

    def test_lines_are_short_and_paragraphs_are_separated(self):
        for key, text in self.pages():
            for line in text.split('\n'):
                self.assertLessEqual(len(line), 60, (key, line))
            self.assertNotIn('\n\n\n', text)
            self.assertEqual(text, text.strip(), key)

    def test_key_instructions_and_values_are_preserved(self):
        joined = '\n'.join(text for _, text in self.pages())
        for fact in ('[첫 업무 시작]', 'Server A: GPU 4개 · 전력 4단위', '[자원 정보 확인]', '[요청 확인]',
                     'GPU 7개', '최대 4개', '[배정 계획 비교·선택]', '배정안 1(추천)', '[선택한 계획으로 작업 시작]',
                     '+10분', '+30분 · +60분', '[운영 상태 확인]', '[Chapter 2 시작]'):
            self.assertIn(fact, joined)

    def test_no_number_or_version_is_split_across_lines(self):
        import re
        for key, text in self.pages():
            self.assertIsNone(re.search(r'\d[.:]\n\d', text), key)

    def test_ordered_items_start_their_own_line(self):
        for key, text in self.pages():
            for marker in ('①', '②', '③', '④', '· '):
                for line in text.split('\n'):
                    if marker in line and marker != '· ':
                        self.assertTrue(line.startswith(marker), (key, line))


class PipTextTests(unittest.TestCase):
    def test_state_is_not_color_only(self):
        self.assertEqual(pip_text('요청 확인', 'done')[0], '✔ 요청 확인')
        self.assertEqual(pip_text('요청 확인', 'current')[0], '▶ 요청 확인')
        self.assertEqual(pip_text('요청 확인', 'todo')[0], '○ 요청 확인')
        self.assertTrue(pip_text('x', 'current')[2])


class FrameOffsetTests(unittest.TestCase):
    def widget(self, root, frame, viewable=True):
        return NS(winfo_rootx=lambda: root[0], winfo_rooty=lambda: root[1], winfo_x=lambda: frame[0],
                  winfo_y=lambda: frame[1], winfo_viewable=lambda: viewable)

    def test_visible_dialog_uses_its_own_frame_offset(self):
        self.assertEqual(frame_offset(self.widget((108, 131), (100, 100)), self.widget((18, 41), (10, 10))), (8, 31))

    def test_withdrawn_dialog_borrows_the_parent_frame_offset(self):
        hidden = self.widget((100, 100), (100, 100), viewable=False)
        parent = self.widget((18, 41), (10, 10))
        self.assertEqual(frame_offset(hidden, parent), (8, 31))

    def test_correction_moves_the_outer_frame_by_the_measured_difference(self):
        from aidc.ui.window_placement import corrected_outer
        self.assertIsNone(corrected_outer((542, 261), (550, 292), (550, 292)))
        self.assertIsNone(corrected_outer((542, 261), (550, 292), (551, 291)))  # 1px 이내는 그대로
        self.assertEqual(corrected_outer((542, 261), (550, 292), (530, 300)), (562, 253))

    def test_record_compares_dialog_center_with_parent_center(self):
        from aidc.ui.window_placement import placement_record
        record = placement_record((0, 23, 1920, 1009), (820, 470), (550, 292), (550, 292))
        self.assertEqual(record['offset'], (0, 0))
        shifted = placement_record((0, 23, 1920, 1009), (820, 470), (550, 292), (420, 292))
        self.assertEqual(shifted['offset'], (-130, 0))  # 왼쪽 치우침을 수치로 드러냅니다.

    def test_never_negative(self):
        self.assertEqual(frame_offset(self.widget((0, 0), (5, 5)), self.widget((0, 0), (5, 5))), (0, 0))


class StatusToneTests(unittest.TestCase):
    def run_of(self, phase, succeeded=False, status='operating', expired=False):
        return NS(state=NS(phase=phase, succeeded=succeeded), request={'status': status}, terms={'expired': expired})

    def test_tones(self):
        from main import status_tone
        self.assertEqual(status_tone(self.run_of('running'), None), 'ok')
        self.assertEqual(status_tone(self.run_of('incident'), None), 'fault')
        self.assertEqual(status_tone(self.run_of('recovering'), None), 'recover')
        self.assertEqual(status_tone(self.run_of('finished', True), None), 'done')
        self.assertEqual(status_tone(self.run_of('finished', False), None), 'failed')
        self.assertEqual(status_tone(self.run_of('ready', status='waiting'), None), 'warn')
        self.assertEqual(status_tone(self.run_of('ready', status='new'), None), 'idle')
        self.assertEqual(status_tone(self.run_of('ready', expired=True), None), 'failed')


if __name__ == '__main__':
    unittest.main()
