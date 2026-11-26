from copy import deepcopy
import unittest
from unittest.mock import patch

from database import Database
from aidc.learning.linux_session import LinuxSession
from aidc.learning.linux_curriculum import SHIFTS, CASES
from tests.incident_support import Temp, start_open
from tests.linux_support import opened, command, evidence, diagnose, respond, close_out, observe_probe

class CurriculumTests(unittest.TestCase):
    def setUp(self):
        self.temp = Temp()
        self.addCleanup(self.temp.cleanup)

    def play(self,s):
        s.confirm_shift_briefing()
        for _ in range(85):
            start_open(s)
            for r in s.shift_records():
                if r.state == 'alert':
                    s.incident_ack(r.id)
                    diagnose(s,r)
                    s.incident_act(r.id,'notify_customer')
                    respond(s,r)
                if r.state == 'monitoring' and s.minute >= r.recovered + 10:
                    # no nested time progression; keep handling overlapping cases
                    evidence(s,r,after=True)
                    from aidc.learning.linux_catalog import BY_ID
                    from tests.incident_support import where
                    for p in s.content.types[r.type]['verify']:
                        if p in ('ups','cooling'):
                            s.incident_observe(r.id,p,where(p))
                        elif not any(e['probe']==p and e['after'] for e in r.evidence):
                            observe_probe(s,r,p)
                    s.incident_verify(r.id)
                    s.incident_report(r.id)
            if s.global_.result is not None:
                return s.global_.result
            s.advance_time(10)
        self.fail(str([(r.id,r.state) for r in s.shift_records()]))

    def test_review_kubernetes_environment_is_uniform_inside_every_regular_shift(self):
        from aidc.learning.linux_curriculum import CLUSTER_TEMPLATES, SHIFTS, shift_def
        for n in SHIFTS:
            present={tid in CLUSTER_TEMPLATES for _,tid in shift_def(n)['arrivals']}
            self.assertEqual(len(present),1,(n,shift_def(n)['arrivals']))

    def test_review_practice_has_its_own_metadata(self):
        from aidc.learning.linux_session import LinuxSession
        from aidc.learning.linux_curriculum import shift_def
        d=shift_def(1,'gpu_oom')
        self.assertEqual(d['code'],'LP')
        self.assertIn('연습',d['title'])
        self.assertNotIn('OOM',d['title'])
        self.assertEqual(d['input'],'terminal')
        self.assertEqual(shift_def(1,'dns')['input'],'choice')
        s=LinuxSession(self.temp.db('practice_meta.db'),practice='gpu_oom',seed=5)
        self.assertEqual(s.incident.practice,'gpu_oom')
        path=s.db.path;s.db.close()
        again=LinuxSession(self.temp.db(path))
        self.assertEqual((again.incident.practice,again.linux['practice']),('gpu_oom','gpu_oom'))

    def test_five_shifts_promote_and_finish(self):
        s=LinuxSession(self.temp.db('campaign.db'),seed=5)
        done=[]
        for number in range(1,6):
            res=self.play(s)
            self.assertTrue(res['cleared'],(number,res))
            self.assertEqual(res['linux']['graduated'],number==5)
            done.extend(r.type for r in s.shift_records())
            if number<5:
                self.assertEqual(s.start_next_shift(),number+1)
        self.assertEqual(set(done),set(CASES))
        self.assertIsNone(s.next_shift())
        with self.assertRaises(ValueError):
            s.start_next_shift()
        self.assertEqual(len(s.global_.history),4)

    def test_exam_is_new_combination_without_automatic_hints(self):
        s,r=opened(self.temp,shift=5,practice=False)
        phase7=s.content.shift_def(3)
        self.assertNotEqual(s.shift_def()['arrivals'],phase7['arrivals'])
        self.assertNotEqual(s.shift_def()['incidents'],phase7['incidents'])
        self.assertIsNone(s.incident_view(r)['hint'])
        view=s.learning_view()
        self.assertNotIn('cases',view)
        self.assertNotIn('groups',str(view.keys()))
        self.assertFalse(any(o.get('type') in CASES for o in view['observations']))

    def test_learning_resume_keeps_valid_evidence_and_interpretation(self):
        s,r=opened(self.temp,'dns')
        command(s,r,'ping',interpret=True)
        before=deepcopy(s._extra_payload())
        path=s.db.path
        s.db.close()
        resumed=LinuxSession(self.temp.db(path))
        self.assertEqual(resumed._extra_payload(),before)
        self.assertEqual(resumed.record(r.id).state,'investigating')

    def test_recovery_resume_keeps_actual_timer(self):
        s,r=opened(self.temp,'cooling')
        diagnose(s,r);respond(s,r)
        self.assertEqual(r.state,'recovering')
        before=deepcopy(s._extra_payload());path=s.db.path
        s.db.close()
        resumed=LinuxSession(self.temp.db(path))
        self.assertEqual(resumed._extra_payload(),before)
        close_out(resumed,resumed.record(r.id))
        self.assertEqual(resumed.record(r.id).state,'closed')

    def test_clear_resume_and_practice_never_promotes(self):
        s,r=opened(self.temp,'dns')
        diagnose(s,r);respond(s,r);close_out(s,r)
        for _ in range(30):
            if s.global_.result is not None: break
            s.advance_time(10)
        self.assertTrue(s.global_.result['cleared'])
        self.assertEqual(s.global_.result['linux']['rank'],'연습 · 승급 없음')
        self.assertFalse(s.global_.result['linux']['graduated'])
        old=deepcopy(s._extra_payload());path=s.db.path;s.db.close()
        resumed=LinuxSession(self.temp.db(path))
        self.assertEqual(resumed._extra_payload(),old)

    def test_version_or_catalog_change_rejects_without_rewriting(self):
        s,r=opened(self.temp)
        path=s.db.path;s.db.close()
        before=path.read_bytes()
        with patch.object(LinuxSession,'_fingerprint',return_value='foreign'):
            with self.assertRaisesRegex(ValueError,'저장 당시'):
                LinuxSession(self.temp.db(path))
        self.assertEqual(path.read_bytes(),before)

    def test_incorrect_action_costs_time_and_approval_stays_in_engine(self):
        s,r=opened(self.temp,'cooling')
        diagnose(s,r)
        self.assertEqual(s.incident_act(r.id,'standby_pump')['result'],'refused')
        self.assertTrue(r.cause_active)
        self.assertEqual(s.incident_act(r.id,'restart_service')['result'],'none')
        self.assertGreater(r.busy_until,s.minute)

    def test_old_output_cannot_satisfy_post_verification(self):
        s,r=opened(self.temp,'dns')
        diagnose(s,r);respond(s,r)
        while r.state!='monitoring': s.advance_time(10)
        s.advance_time(10)
        self.assertIn('다시 관측',s.verify_blocker(r))
        command(s,r,'getent');command(s,r,'journalctl')
        self.assertIn('보완적',s.verify_blocker(r))
        command(s,r,'ping')
        self.assertEqual(s.verify_blocker(r),'')

if __name__=='__main__':
    unittest.main()
