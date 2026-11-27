import unittest
from copy import deepcopy

from aidc.learning.senior_session import SeniorSession
from aidc.learning.career import assess
from tests.incident_support import Temp, start_open
from tests import linux_support as L


def play(s):
    s.confirm_shift_briefing()
    for _ in range(65):
        start_open(s)
        for rec in s.shift_records():
            if rec.state == 'alert':
                s.incident_ack(rec.id)
                L.diagnose(s, rec)
                s.incident_act(rec.id, 'notify_customer')
                L.respond(s, rec)
            if rec.state == 'monitoring' and s.minute >= rec.recovered + 10:
                L.evidence(s, rec, after=True)
                for p in s.content.types[rec.type]['verify']:
                    if not any(e['probe'] == p and e['after'] for e in rec.evidence):
                        L.observe_probe(s, rec, p)
                s.incident_verify(rec.id)
                s.incident_report(rec.id)
        if s.global_.result:
            return s.global_.result
        s.advance_time(10)
    raise AssertionError([(r.id, r.state) for r in s.shift_records()])


class SeniorCareerTests(unittest.TestCase):
    def setUp(self):
        self.temp = Temp()
        self.addCleanup(self.temp.cleanup)

    def test_two_finite_shifts_and_ending_from_real_records(self):
        s = SeniorSession(self.temp.db('senior.db'), seed=5)
        r1 = play(s)
        self.assertTrue(r1['cleared'], r1)
        self.assertFalse(r1['senior']['ending'])
        self.assertEqual(r1['assessment']['operations']['score'], 100)
        s.start_next_shift()
        r2 = play(s)
        self.assertTrue(r2['cleared'], r2)
        self.assertTrue(r2['senior']['ending'])
        self.assertEqual(s.next_shift(), None)
        self.assertEqual(len(s.global_.history), 1)
        before = deepcopy(s.db.get_simulation())
        s.db.close()
        restored = SeniorSession(self.temp.db('senior.db'))
        self.assertEqual(restored.db.get_simulation(), before)
        self.assertEqual(restored.global_.result, r2)
        self.assertFalse(r2['linux']['graduated'])

    def test_learning_and_operations_distinct_readonly_no_duplicate_reward(self):
        s = SeniorSession(self.temp.db(), seed=5)
        s.confirm_shift_briefing()
        start_open(s)
        for _ in range(5):
            s.advance_time(10)
            if s.incident.records[0].state == 'alert':
                break
        rec = s.incident.records[0]
        s.incident_ack(rec.id)
        L.evidence(s, rec)
        before = assess(s)
        s.help_for(rec.id)
        after = assess(s)
        self.assertEqual(before['operations'], after['operations'])
        self.assertLess(after['learning']['score'], before['learning']['score'])
        stored = deepcopy(s.db.get_simulation())
        self.assertEqual(assess(s), assess(s))
        self.assertEqual(stored, s.db.get_simulation())

    def test_failed_evaluation_no_ending_and_wrong_interpretation_no_answer(self):
        s = SeniorSession(self.temp.db(), seed=5)
        s.confirm_shift_briefing()
        start_open(s)
        s.advance_time(10)
        s.advance_time(10)
        rec = next(r for r in s.shift_records() if r.state == 'alert')
        s.incident_ack(rec.id)
        o = L.command(s, rec, 'journalctl')
        from aidc.learning.linux_catalog import BY_ID
        wrong = next(x['id'] for x in o['choices'] if x['text'] == BY_ID['journalctl'].wrong)
        result = s.interpret(rec.id, o['seq'], wrong)
        self.assertFalse(result['correct'])
        self.assertNotIn(BY_ID['journalctl'].correct, result['feedback'])
        # A safety-policy violation attempt is refused by the engine and must be visible to the evaluation.
        L.diagnose(s, rec)
        s.incident_act(rec.id, 'delete_data')
        self.assertTrue(assess(s)['unsafe'])


if __name__ == '__main__':
    unittest.main()
