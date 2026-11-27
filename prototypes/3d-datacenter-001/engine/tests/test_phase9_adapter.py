import unittest
import tempfile
from pathlib import Path
from engine.adapter import GameHost, ActionError
from aidc.global_ops.session import GlobalSession
from aidc.learning.senior_session import SeniorSession
from database import Database


class Phase9AdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='srs3d-phase9-')
        self.addCleanup(self.temp.cleanup)
        self.host = GameHost(Path(self.temp.name))
        self.addCleanup(self.host.shutdown)

    def test_free_options_restart_retry_and_briefing(self):
        g = self.host.new_game('global_free', options={'seed': 42, 'difficulty': 'challenge'})
        snap = g.snapshot()
        self.assertFalse(snap['canAdvance'])
        self.assertEqual(snap['global']['seed'], 42)
        self.assertIsNotNone(snap['incident'])
        # Phase9 sessions state the real cost of quick workarounds; the legacy incident mode does not.
        self.assertIn('임시 우회', snap['incident']['tradeoff'])
        legacy = self.host.new_game('incident_practice', chapter='dns').snapshot()
        self.assertIsNone(legacy['incident']['tradeoff'])
        g.act({'type': 'confirm_briefing'})
        self.assertTrue(g.snapshot()['canAdvance'])
        before = g.session.db.get_simulation()
        gid = g.id
        self.host.close(gid)
        restored = self.host.get(gid)
        self.assertEqual(before, restored.session.db.get_simulation())
        retry = self.host.retry(gid)
        self.assertNotEqual(gid, retry.id)
        self.assertEqual(retry.session.seed, 42)
        self.assertEqual(retry.session.free_incidents['difficulty'], 'challenge')

    def test_old_global_free_never_migrates_or_gains_incidents(self):
        path = self.host.dir / 'aidc_3d_global_001.db'
        db = Database(path)
        GlobalSession(db, kind='free', seed=8)
        before = db.get_simulation()
        db.close()
        g = self.host._open(path, 'global_free', fresh=False)
        self.assertIsNone(g.snapshot()['incident'])
        self.assertEqual(before, g.session.db.get_simulation())

    def test_senior_requires_regular_proofs_and_no_one_click_ending(self):
        with self.assertRaises(ActionError):
            self.host.new_game('senior')
        self.assertFalse(self.host.career()['seniorAvailable'])
        g = self.host._new_senior(1)  # isolated fixture, no fake user completion
        self.assertIsInstance(g.session, SeniorSession)
        snap = g.snapshot()
        self.assertEqual(snap['global']['shiftCount'], 2)
        self.assertFalse(snap['senior']['ending'])
        self.assertEqual(snap['linux']['inputMode'], 'terminal')
        self.assertIsNotNone(snap['incident'])
        with self.assertRaises(ValueError):
            g.act({'type': 'start_next_shift', 'shift': '2'})
        self.assertFalse(self.host.career()['ending'])


    def test_senior_slot_that_fails_to_open_is_removed(self):
        from unittest.mock import patch
        before = sorted(p.name for p in Path(self.temp.name).iterdir())
        with patch.object(GameHost, '_open', side_effect=RuntimeError('boom')):
            with self.assertRaises(RuntimeError):
                self.host._new_senior(1)
        self.assertEqual(sorted(p.name for p in Path(self.temp.name).iterdir()), before)


if __name__ == '__main__':
    unittest.main()
