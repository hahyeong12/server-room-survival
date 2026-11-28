"""Phase 10 through the 3D adapter: read-only forecast, explicit handoff (confirm required), fixed result, old saves."""
import unittest
import tempfile
from pathlib import Path

from engine.adapter import GameHost, ActionError
from tests.incident_support import start_open, diagnose
from tests.phase10_support import strip_phase10


def alert(s):
    start_open(s)
    rec = s.incident.records[0]
    for _ in range(60):
        if rec.state == 'alert':
            return rec
        s.advance_time(10)
    raise AssertionError(rec.state)


def engine_view(snap):
    return {k: v for k, v in snap.items() if k != 'journey'}


class Phase10AdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='srs3d-phase10-')
        self.addCleanup(self.temp.cleanup)
        self.host = GameHost(Path(self.temp.name))
        self.addCleanup(self.host.shutdown)

    def test_forecast_is_read_only_and_needs_a_diagnosis(self):
        g = self.host.new_game('incident_practice', chapter='storage_full')
        g.act({'type': 'confirm_briefing'})
        rec = alert(g.session)
        snap = g.snapshot()
        self.assertTrue(snap['incident']['rules10'])
        with self.assertRaises(ValueError):
            g.act({'type': 'incident_forecast', 'incident': rec.id})
        diagnose(g.session, rec)
        before = engine_view(g.snapshot())
        out = g.act({'type': 'incident_forecast', 'incident': rec.id})
        options = {o['action']: o for o in out['incident']['forecast']['options']}
        self.assertEqual(set(options), {'cleanup_temp', 'expand_storage'})
        self.assertEqual(engine_view(g.snapshot()), before, 'forecast never changes the engine state')
        self.assertEqual(g.journey.data['events'][-1]['name'], 'forecast')

    def test_handoff_needs_confirmation_fixes_the_result_and_survives_reopen(self):
        g = self.host.new_game('incident_practice', chapter='dns')
        g.act({'type': 'confirm_briefing'})
        rec = alert(g.session)
        g.act({'type': 'incident_ack', 'incident': rec.id})
        g.act({'type': 'incident_act', 'incident': rec.id, 'action': 'notify_customer'})
        self.assertTrue(g.snapshot()['incident']['handoff']['available'])
        with self.assertRaises(ActionError):
            g.act({'type': 'handoff_shift'})
        self.assertIsNone(g.session.global_.result)
        out = g.act({'type': 'handoff_shift', 'confirm': True})
        self.assertEqual(out['handoff']['handedOver'], 1)
        snap = g.snapshot()
        self.assertFalse(snap['canAdvance'])
        self.assertTrue(snap['incident']['handedOff'])
        self.assertFalse(snap['global']['result']['cleared'])
        with self.assertRaises(ValueError):
            g.act({'type': 'advance_time', 'minutes': 10})
        with self.assertRaises(ValueError):
            g.act({'type': 'handoff_shift', 'confirm': True})
        gid = g.id
        self.host.close(gid)
        again = self.host.get(gid)
        self.assertTrue(again.snapshot()['incident']['handedOff'])
        self.assertFalse(again.snapshot()['canAdvance'])

    def test_linux_and_senior_sessions_can_hand_off_too(self):
        g = self.host.new_game('linux_practice', chapter='crashloop')
        g.act({'type': 'confirm_briefing'})
        rec = alert(g.session)
        g.act({'type': 'incident_ack', 'incident': rec.id})
        out = g.act({'type': 'handoff_shift', 'confirm': True})
        self.assertEqual(out['handoff']['neglected'], 1, 'no customer notice: recorded as neglect')
        senior = self.host._new_senior(1)
        senior.act({'type': 'confirm_briefing'})
        srec = alert(senior.session)
        senior.act({'type': 'incident_ack', 'incident': srec.id})
        senior.act({'type': 'incident_act', 'incident': srec.id, 'action': 'notify_customer'})
        self.assertIn('도착 예정', senior.snapshot()['incident']['handoff']['reason'], 'the 40-minute arrival is still due')
        while len(senior.session.global_.delivered) < 3:
            senior.session.advance_time(10)
        for r in senior.session.shift_records():
            if r.state == 'alert':
                senior.act({'type': 'incident_ack', 'incident': r.id})
                senior.act({'type': 'incident_act', 'incident': r.id, 'action': 'notify_customer'})
        senior.act({'type': 'handoff_shift', 'confirm': True})
        result = senior.snapshot()['global']['result']
        self.assertFalse(result['cleared'])
        self.assertFalse(senior.snapshot()['senior']['ending'])

    def test_old_incident_save_opens_without_phase10_features(self):
        from database import Database
        g = self.host.new_game('incident_practice', chapter='dns')
        path, gid = g.path, g.id
        self.host.close(gid)
        db = Database(path)
        strip_phase10(db)          # the file now has the shape of a save written before Phase 10
        db.close()
        old = self.host.get(gid)
        snap = old.snapshot()
        self.assertFalse(snap['incident']['rules10'])
        self.assertIsNone(snap['incident']['handoff'])
        with self.assertRaises(ValueError):
            old.act({'type': 'handoff_shift', 'confirm': True})
        self.assertTrue(path.exists())


if __name__ == '__main__':
    unittest.main()
