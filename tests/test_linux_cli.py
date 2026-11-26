"""CLI catalog forms + negative syntax + incident/session invariants (no real OS calls)."""
import ast
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

from aidc.learning import linux_catalog as C
from aidc.learning.linux_session import LinuxSession
from aidc.learning.linux_terminal import result
from tests.incident_support import Temp
from tests.linux_support import opened, command, diagnose, respond, close_out

class LinuxTests(unittest.TestCase):
    def setUp(self):
        self.temp = Temp()
        self.addCleanup(self.temp.cleanup)

    def test_catalog_has_distinct_28_calls_and_sources(self):
        self.assertEqual(len(C.COMMANDS), 28)
        self.assertEqual(len(C.BY_ID), 28)
        self.assertEqual(len({c.syntax for c in C.COMMANDS}), 28)
        self.assertTrue(all(c.source.startswith('https://') and c.correct != c.wrong for c in C.COMMANDS))

    def test_no_execution_or_network_imports(self):
        for name in ('linux_catalog', 'linux_terminal', 'linux_session', 'linux_curriculum'):
            tree = ast.parse((Path('aidc/learning') / (name + '.py')).read_text(encoding='utf-8'))
            for n in ast.walk(tree):
                if isinstance(n, ast.Import):
                    self.assertFalse({x.name.split('.')[0] for x in n.names} & {'os','subprocess','socket','requests','urllib'})
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
                    self.assertNotIn(n.func.id, ('eval','exec','compile','open','__import__'))

    def test_injections_quotes_and_paths_never_change_state(self):
        s,r = opened(self.temp)
        old = deepcopy(s._extra_payload())
        for line in ('ping -c 3 10.20.0.15; rm x','ip addr | x','ip addr\nrm x','$(whoami)',
                     '`id`','df -h > /data/work','sudo df -h','kill 1','systemctl restart worker.service',
                     'kubectl delete pod worker-0 -n aidc','du -sh /data/work/../../etc',
                     'kubectl get pods -n ../aidc','dig "oops','x'*241,'ping -c 999 10.20.0.15'):
            with self.subTest(line=line):
                out = s.cli(r.id,line,'noc')
                self.assertEqual(out['kind'],'error')
                self.assertEqual(s._extra_payload(),old)

    def test_wrong_context_permission_and_absent_cluster(self):
        s,r = opened(self.temp,'tor_uplink')
        for line,node,category in [('nvidia-smi','noc','environment'), ('df -h','server-D','permission'),
                                    ('kubectl get pods -n aidc','cluster','environment'),('ip addr','../noc','context')]:
            with self.subTest(line=line,node=node):
                old = deepcopy(s._extra_payload())
                out=s.cli(r.id,line,node)
                self.assertEqual(out['category'],category)
                self.assertEqual(s._extra_payload(),old)

    def test_review_unhashable_node_is_a_context_error(self):
        s,r=opened(self.temp)
        old=deepcopy(s._extra_payload())
        for node in ([],{},None,1):
            self.assertEqual(s.cli(r.id,'ip addr',node)['category'],'context')
        self.assertEqual(old,s._extra_payload())

    def test_review_no_answer_key_in_snapshot_or_command_response(self):
        s,r=opened(self.temp)
        obs=command(s,r,'ping')
        self.assertNotIn('correct',obs)
        self.assertNotIn('wrong',obs)
        self.assertEqual({x['id'] for x in obs['choices']},{'a','b'})
        for c in s.learning_view()['commands']:
            self.assertNotIn('correct',c)
            self.assertNotIn('wrong',c)

    def test_review_insufficient_proof_is_symmetric_for_submitted_causes(self):
        s,r=opened(self.temp,'dns')
        command(s,r,'ip_addr',interpret=True);command(s,r,'ip_route')
        errors=[]
        for cause in s.content.causes:
            with self.assertRaises(ValueError) as cm:
                s.incident_hypothesis(r.id,cause)
            errors.append(str(cm.exception))
        self.assertEqual(len(set(errors)),1)

    def test_review_cluster_is_deployment_metadata_not_hidden_cause(self):
        from aidc.learning.linux_terminal import cluster_exists
        s,r=opened(self.temp,'dns')
        self.assertTrue(cluster_exists(s,r))
        self.assertIn('Running',s.cli(r.id,'kubectl get pods -n aidc','cluster')['output'])
        self.assertEqual(s.cli(r.id,'kubectl logs worker-0 -n aidc --previous','cluster')['code'],1)

    def test_review_ping_target_scopes_the_evidence(self):
        s,r=opened(self.temp,'tor_uplink')
        storage=s.cli(r.id,'ping -c 3 10.20.0.15','noc')
        self.assertEqual(storage['code'],0)
        self.assertFalse(storage['eligible'])
        self.assertFalse(any(e['probe']=='ping' for e in r.evidence))
        rack=command(s,r,'ping')
        self.assertEqual(rack['code'],1)
        self.assertTrue(rack['eligible'])

    def test_review_count_and_journal_limits(self):
        s,r=opened(self.temp,'crashloop')
        for n in (1,3,10,20):
            out=s.cli(r.id,f'ping -c {n} 10.20.0.15','noc')
            self.assertIn(f'{n} packets transmitted',out['output'])
            out=s.cli(r.id,f'journalctl -u worker.service -n {n}','server-A')
            self.assertLessEqual(len(out['output'].splitlines()),n)

    def test_review_healthy_gpu_node_cannot_prove_another_nodes_fault(self):
        from aidc.core.server_resources import ServerSlice
        from tests.incident_support import start_open
        s=LinuxSession(self.temp.db('two_nodes.db'),practice='gpu_health',seed=5)
        s.confirm_shift_briefing()
        rid=next(iter(s.runs));s.select(rid);s.read_conversation(rid)
        s.choose_plan('performance',(ServerSlice('A',(0,1),2),ServerSlice('B',(0,1),1)))
        for _ in range(15):
            s.advance_time(10)
            if s.incident.records[0].state=='alert':break
        r=s.incident.records[0];s.incident_ack(r.id)
        normal=s.cli(r.id,'dcgmi health --check','server-B')
        self.assertFalse(normal['eligible']);self.assertEqual(normal['status'],'ok')
        self.assertFalse(any(e['probe']=='dcgm' for e in r.evidence))
        command(s,r,'journalctl',interpret=True)
        with self.assertRaisesRegex(ValueError,'보완적'):
            s.incident_hypothesis(r.id,'gpu_health')
        self.assertEqual(command(s,r,'dcgm')['status'],'bad')
        self.assertEqual(s.incident_hypothesis(r.id,'gpu_health')['verdict'],'confirmed')

    def test_review_interpretation_answer_order_varies(self):
        s,r=opened(self.temp)
        correct_ids=set()
        for _ in range(10):
            out=command(s,r,'ping')
            correct_ids.add(next(x['id'] for x in out['choices'] if x['text']==C.BY_ID['ping'].correct))
        self.assertEqual(correct_ids,{'a','b'})

    def test_ping_success_dns_failure_and_exit_zero_is_not_healthy(self):
        s,r=opened(self.temp,'dns')
        ping=command(s,r,'ping');dig=command(s,r,'dig');getent=command(s,r,'getent');curl=command(s,r,'curl')
        self.assertEqual((ping['code'],ping['status']),(0,'ok'))
        self.assertEqual((dig['code'],dig['status']),(0,'bad'))
        self.assertIn('SERVFAIL',dig['output'])
        self.assertEqual(getent['code'],2)
        self.assertEqual(curl['code'],6)
        self.assertTrue(r.cause_active)

    def test_crashloop_exit_status_and_previous_log(self):
        s,r=opened(self.temp,'crashloop')
        self.assertEqual(command(s,r,'systemctl')['code'],3)
        self.assertEqual(command(s,r,'curl')['code'],0)
        self.assertIn('503',s.cli(r.id,'curl -I http://worker.aidc.internal/health','noc')['output'])
        self.assertIn('CrashLoopBackOff',command(s,r,'pods')['output'])
        self.assertTrue(command(s,r,'pod_logs')['historical'])

    def test_two_complementary_evidence_and_interpretation_required(self):
        s,r=opened(self.temp,'dns')
        command(s,r,'ping');command(s,r,'ip_addr')
        with self.assertRaisesRegex(ValueError,'사실과 추측'):
            s.incident_hypothesis(r.id,'dns')
        command(s,r,'ip_route',interpret=True)
        with self.assertRaisesRegex(ValueError,'보완적'):
            s.incident_hypothesis(r.id,'dns')
        command(s,r,'dig')
        self.assertEqual(s.incident_hypothesis(r.id,'dns')['verdict'],'confirmed')
        with self.assertRaises(ValueError):
            s.incident_report(r.id)

    def test_wrong_interpretation_has_feedback_and_no_fake_diagnosis(self):
        s,r=opened(self.temp)
        out=command(s,r,'ping')
        interpreted=s.interpret(r.id,out['seq'],next(x['id'] for x in out['choices'] if x['text']==C.BY_ID['ping'].wrong))
        self.assertFalse(interpreted['correct'])
        self.assertIn('추측',interpreted['feedback'])
        self.assertIsNone(r.cause)

    def test_repeated_help_and_clear_are_not_evidence(self):
        s,r=opened(self.temp)
        old=deepcopy(s._extra_payload())
        self.assertIn('kubectl',s.cli(r.id,'help','noc')['output'])
        s.cli(r.id,'clear','noc')
        self.assertEqual(old,s._extra_payload())

    def test_stale_async_token_is_rejected(self):
        s,r=opened(self.temp)
        token=s.token(r)
        command(s,r,'ping')
        old=deepcopy(s._extra_payload())
        with self.assertRaisesRegex(ValueError,'오래된'):
            s.cli(r.id,'ip addr','noc',token)
        self.assertEqual(old,s._extra_payload())

    def test_cli_save_failure_rolls_back_both_books(self):
        s,r=opened(self.temp)
        old=deepcopy(s._extra_payload())
        with patch.object(s.db,'save_simulation',side_effect=RuntimeError('disk full')):
            with self.assertRaises(RuntimeError):
                command(s,r,'ping')
        self.assertEqual(old,s._extra_payload())

    def test_old_lab_catalog_is_unchanged(self):
        from aidc.learning.lab_terminal import SUPPORTED, parse_command
        self.assertEqual(SUPPORTED,('help','ping','ip addr','ip route','clear'))
        self.assertEqual(parse_command('ping -c 3 10.0.0.1').count,3)

    def test_bms_requires_real_site(self):
        s,r=opened(self.temp,'cooling')
        with self.assertRaisesRegex(ValueError,'장소'):
            s.incident_observe(r.id,'cooling','noc')
        with self.assertRaisesRegex(ValueError,'명령'):
            s.incident_observe(r.id,'dcgm','hall')

def valid_case(spec):
    def test(self):
        s,r=opened(self.temp,'crashloop')
        out=command(s,r,spec.command_id)
        self.assertEqual(out['command_id'],spec.command_id)
        self.assertTrue(out['output'])
        self.assertLessEqual(len(out['output']),C.MAX_OUTPUT)
        self.assertEqual(out['code'],3 if spec.command_id=='systemctl' else 0)
        self.assertEqual(s.linux['observations'][-1]['node'],out['node'])
        if spec.probe:
            self.assertIn(s.reading(r,spec.probe)['summary'],out['output']) if spec.command_id not in ('curl','pod_logs','nvidia_query','du') else None
        self.assertTrue(r.cause_active)
        self.assertIsNone(r.cause)
    return test

def invalid_case(spec):
    def test(self):
        s,r=opened(self.temp,'crashloop')
        old=deepcopy(s._extra_payload())
        out=s.cli(r.id,C.example(spec)+' --not-supported','noc')
        self.assertEqual(out['kind'],'error')
        self.assertEqual(out['code'],2)
        self.assertEqual(old,s._extra_payload())
    return test

for spec in C.COMMANDS:
    setattr(LinuxTests,'test_valid_'+spec.command_id,valid_case(spec))
    setattr(LinuxTests,'test_invalid_'+spec.command_id,invalid_case(spec))

def incident_case(cause):
    def test(self):
        s,r=opened(self.temp,cause)
        command(s,r,__import__('aidc.learning.linux_curriculum',fromlist=['CASES']).CASES[cause]['distractor'])
        self.assertEqual(diagnose(s,r)['verdict'],'confirmed')
        respond(s,r)
        with self.assertRaises(ValueError):
            s.incident_verify(r.id)
        close_out(s,r)
        self.assertEqual((r.state,r.outcome),('closed','resolved'))
        self.assertGreaterEqual(len({o['command_id'] for o in s.linux['observations'] if o['after']}),2)
        self.assertTrue(all(e['after'] for e in r.evidence if e['minute'] >= r.recovered))
    return test

from aidc.learning.linux_curriculum import CASES
for cause in CASES:
    setattr(LinuxTests,'test_complete_'+cause,incident_case(cause))

if __name__=='__main__':
    unittest.main()
