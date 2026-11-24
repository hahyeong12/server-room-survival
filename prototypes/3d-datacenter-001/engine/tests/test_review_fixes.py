"""Regression tests for the independent review findings (Phase 4). Temporary save folders only."""
import unittest
from unittest import mock

from engine.tests.test_adapter import Base, play_tutorial_until


class ReviewFixTests(Base):
    def test_verify_still_possible_after_the_job_already_finished(self):
        game = self.host.new_game('tutorial')
        rid = play_tutorial_until(self, game, stop='respond')
        fault = game.journey.data['fault']
        self.assertTrue(self.act(game, type='begin_repair', rid=rid, server=fault['server'])['ok'])
        self.assertTrue(self.act(game, type='advance_time', minutes=60)['ok'])     # repair and job both finish
        snap = game.snapshot()
        self.assertEqual(snap['requests'][0]['stage'], 'done')
        self.assertEqual(snap['journey']['current']['id'], 'verify')
        self.assertEqual(snap['journey']['verifyRacks'], [fault['rack']])
        self.act(game, type='navigate', route='hall')
        self.assertTrue(self.act(game, type='verify', rid=rid, rack=fault['rack'])['ok'])
        self.act(game, type='report', rid=rid)
        self.assertTrue(game.snapshot()['journey']['completed'])

    def test_migration_path_can_be_verified_on_the_new_servers(self):
        game = self.host.new_game('tutorial')
        rid = play_tutorial_until(self, game, stop='choose')
        self.assertTrue(self.act(game, type='propose_alternative', rid=rid)['ok'])
        self.assertTrue(self.act(game, type='check_reply', rid=rid)['ok'])
        self.assertEqual(game.snapshot()['requests'][0]['proposal']['status'], 'accepted')
        self.assertTrue(self.act(game, type='select_plan', rid=rid, mode='economy', index=0)['ok'])
        sel = game.snapshot()['requests'][0]['selection']
        self.act(game, type='navigate', route='hall')
        self.act(game, type='inspect_rack', rack=sel['slices'][0]['rack'])
        self.assertTrue(self.act(game, type='start_job', rid=rid, rack=sel['slices'][0]['rack'])['ok'])
        self.act(game, type='advance_time', minutes=10)
        fault = game.journey.data['fault']
        self.act(game, type='diagnose', rid=rid)
        self.assertTrue(self.act(game, type='migrate', rid=rid, index=0)['ok'])
        self.act(game, type='advance_time', minutes=10)                 # 10-minute migration preparation
        snap = game.snapshot()
        self.assertEqual(snap['journey']['current']['id'], 'verify')
        new = snap['journey']['verifyRacks']
        self.assertNotIn(fault['rack'], new)
        r = self.act(game, type='verify', rid=rid, rack=fault['rack'])   # the old server is still FAULT
        self.assertIn('새 서버', r['hint'])
        self.assertTrue(self.act(game, type='verify', rid=rid, rack=new[0])['ok'])
        self.assertEqual(game.snapshot()['journey']['current']['id'], 'finish')

    def test_a_diagnosis_before_the_fault_does_not_open_the_gate(self):
        game = self.host.new_game('tutorial')
        rid = play_tutorial_until(self, game, stop='time')
        self.assertTrue(self.act(game, type='diagnose', rid=rid)['ok'])   # before the fault
        self.act(game, type='advance_time', minutes=10)
        fault = game.journey.data['fault']
        r = self.act(game, type='begin_repair', rid=rid, server=fault['server'])
        self.assertFalse(r['ok'])
        self.assertIn('장비 진단', r['message'])
        self.act(game, type='diagnose', rid=rid)
        self.assertTrue(self.act(game, type='begin_repair', rid=rid, server=fault['server'])['ok'])

    def test_a_stale_plan_card_is_refused_not_replaced(self):
        game = self.host.new_game('tutorial')
        rid = play_tutorial_until(self, game, stop='choose')
        plans = game.act({'type': 'view_plans', 'rid': rid})['plans']['performance']['options']
        wrong = plans[1]
        r = self.act(game, type='select_plan', rid=rid, mode='performance', index=0, slices=wrong)
        self.assertFalse(r['ok'])
        self.assertIn('다시 조회', r['message'])
        self.assertIsNone(game.snapshot()['requests'][0]['selection'])
        self.assertTrue(self.act(game, type='select_plan', rid=rid, mode='performance', index=0, slices=plans[0])['ok'])

    def test_skip_also_stops_the_scripted_training_fault(self):
        game = self.host.new_game('tutorial')
        rid = play_tutorial_until(self, game, stop='time')
        self.act(game, type='skip_tutorial')
        self.act(game, type='advance_time', minutes=10)
        snap = game.snapshot()
        self.assertTrue(all(s['state'] == 'HEALTHY' for s in snap['servers']))
        self.assertEqual(snap['requests'][0]['stage'], 'done')

    def test_facility_cabinets_in_the_hall_are_information_not_misclicks(self):
        game = self.host.new_game('free')
        r = self.act(game, type='inspect_rack', rack='UPS-01')
        self.assertTrue(r['ok'])
        self.assertEqual(game.snapshot()['journey']['misclicks'], 0)

    def test_journey_save_failure_after_an_engine_commit_keeps_the_facts(self):
        game = self.host.new_game('tutorial')
        rid = play_tutorial_until(self, game, stop='read')
        with mock.patch.object(game.journey, 'save', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                game.act({'type': 'read_request', 'rid': rid})
        self.assertIn(game.journey.current_step()['id'], ('compare',))   # the engine read is kept in the journey
        game.journey.save()


if __name__ == '__main__':
    unittest.main()
