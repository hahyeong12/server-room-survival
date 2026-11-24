"""Regression tests for the Phase 5 independent review findings. Temporary save folders only."""
import unittest
from pathlib import Path
from unittest import mock

from engine import server
from engine.adapter import ActionError, MissingSave
from engine.tests.test_adapter import Base
from engine.tests.test_campaign import Driver, req


class Phase5ReviewTests(Base):
    def test_briefing_can_be_confirmed_even_after_its_pages_were_marked_read(self):
        game = self.host.new_game('practice', 2)
        d = Driver(self, game)
        d.ok(type='mark_dialogue', event='c2_briefing')            # pages read, briefing not yet confirmed
        st = d.story()
        self.assertTrue(st['dialogue']['seen'])
        self.assertEqual(st['uiStep'], 'c2_briefing', 'reading pages never confirms the briefing')
        d.ok(type='confirm_briefing')
        self.assertEqual(d.story()['uiStep'], 'c2_requests')

    def test_free_mode_incident_states_the_free_rule_with_numbers(self):
        game = self.host.new_game('free')
        rid = game.snapshot()['requests'][0]['id']
        run = game.session.runs[rid]
        # Adapter display unit: a free-mode incident (no chapter-3 cause model) in memory only, nothing saved.
        with mock.patch.object(run.state, 'phase', 'incident'), mock.patch.object(run.state, 'incident_kind', None):
            link, note = game._link(run, 'net_fault')
        self.assertEqual(link, 'congested')
        self.assertIn('필요', note)

    def test_retry_of_a_free_save_is_a_plain_refusal(self):
        game = self.host.new_game('free')
        with self.assertRaises(ActionError):
            self.host.retry(game.id)

    def test_chapter_values_of_the_wrong_type_are_refused(self):
        game = self.host.new_game('story')
        for bad in ([2], {'x': 1}, True, None, '9'):
            with self.assertRaises(ActionError):
                self.host.start_checkpoint(game.id, bad)
            with self.assertRaises(ActionError):
                self.host.new_game('practice', bad)

    def test_only_a_missing_save_is_404(self):
        with self.assertRaises(server.NotFound):
            server.guarded(lambda gid: (_ for _ in ()).throw(MissingSave(gid)), 'aidc_story_slot_404')
        with self.assertRaises(KeyError) as ctx:
            server.guarded(lambda gid: {}['internal'], 'aidc_story_slot_001')
        self.assertNotIsInstance(ctx.exception, server.NotFound)
        with self.assertRaises(server.NotFound):
            server.lookup(self.host, 'aidc_story_slot_999')

    def test_a_failed_checkpoint_start_leaves_no_orphan_slot(self):
        game = self.host.new_game('story')
        before = sorted(p.name for p in Path(self.tmp.name).iterdir())
        with mock.patch.object(self.host, '_open', side_effect=ValueError('broken')):
            with self.assertRaises(ValueError):
                self.host.start_checkpoint(game.id, '1')
        self.assertEqual(sorted(p.name for p in Path(self.tmp.name).iterdir()), before)


if __name__ == '__main__':
    unittest.main()
