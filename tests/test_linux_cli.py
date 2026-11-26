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
from tests.linux_support import opened, command, diagnose, respond, close_out, scoped
from aidc.learning.linux_terminal import job_servers
from aidc.learning.linux_curriculum import CASES

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
        s,r = opened(self.temp,'gpu_oom')
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
        # Scope is one rule for every cause: this request's storage and its own servers. Out-of-scope targets never
        # become evidence, whatever the hidden cause is.
        s,r=opened(self.temp,'tor_uplink')
        outside=next(x for x in 'ABCD' if x not in job_servers(s,r))
        far=s.cli(r.id,f'ping -c 3 10.20.{11+"ABCD".index(outside)}.15','noc')
        self.assertEqual(far['code'],0)
        self.assertIn('영향 범위 밖',far['output'])
        self.assertFalse(s.linux['observations'][-1]['eligible'])
        self.assertFalse(any(e['probe']=='ping' for e in r.evidence))
        rack=command(s,r,'ping')
        self.assertEqual(rack['code'],1)
        self.assertIn('0 received, 100% packet loss',rack['output'])
        self.assertTrue(s.linux['observations'][-1]['eligible'])

    def test_review_public_observations_never_carry_eligibility_or_probe_status(self):
        s,r=opened(self.temp,'tor_uplink')
        out=command(s,r,'ping')
        view=s.learning_view()['observations']
        for o in [out,*view]:
            self.assertNotIn('eligible',o)
            self.assertNotIn('status',o)

    def test_review_out_of_scope_and_healthy_node_outputs_do_not_depend_on_hidden_cause(self):
        import re
        far,healthy={},{}
        for cause in CASES:
            s,r=opened(self.temp,cause)
            job=job_servers(s,r)
            outside=next(x for x in 'ABCD' if x not in job)
            out=s.cli(r.id,f'ping -c 10 10.20.{11+"ABCD".index(outside)}.15','noc')['output']
            far[cause]=out.replace(f'10.20.{11+"ABCD".index(outside)}.15','IP')
            other=[x for x in job if x!=r.primary]
            if other and cause not in ('cooling',):   # cooling throttles every server in the zone (warn on all nodes)
                healthy[cause]=re.sub(r'Server [ABCD]','Server X',s.cli(r.id,'dcgmi health --check',f'server-{other[0]}')['output'])
        self.assertEqual(len(set(far.values())),1,far)
        self.assertGreaterEqual(len(healthy),2)
        self.assertEqual(len(set(healthy.values())),1,healthy)

    def _two_servers(self,cause):
        from aidc.core.server_resources import ServerSlice
        s=LinuxSession(self.temp.db(f'two_{cause}_{len(self.temp.dbs)}.db'),practice=cause,seed=5)
        s.confirm_shift_briefing()
        rid=next(iter(s.runs));s.select(rid);s.read_conversation(rid)
        s.choose_plan('performance',(ServerSlice('A',(0,1),2),ServerSlice('B',(0,1),1)))
        for _ in range(15):
            s.advance_time(10)
            if s.incident.records[0].state=='alert':break
        r=s.incident.records[0];s.incident_ack(r.id)
        return s,r

    def test_review_healthy_node_alone_never_becomes_engine_evidence(self):
        # Coverage rule is the same for every cause: one node/target is not the scope of this request.
        for cause in ('gpu_health','storage_full','tor_uplink','dns'):
            s,r=opened(self.temp,cause)
            nodes=job_servers(s,r)
            s.cli(r.id,'dcgmi health --check',f'server-{nodes[-1]}')
            s.cli(r.id,'ping -c 3 10.20.0.15','noc')
            if len(nodes)>1:
                self.assertFalse(any(e['probe']=='dcgm' for e in r.evidence),cause)
            self.assertFalse(any(e['probe']=='ping' for e in r.evidence),cause)

    def test_review_gpu_fault_needs_its_own_server_and_records_what_was_seen(self):
        s,r=self._two_servers('gpu_health')
        healthy='B' if r.primary=='A' else 'A'
        s.cli(r.id,'dcgmi health --check',f'server-{healthy}')
        command(s,r,'journalctl',interpret=True,node=f'server-{healthy}')
        with self.assertRaisesRegex(ValueError,f'server-{r.primary}'):
            s.incident_hypothesis(r.id,'gpu_health')
        s.cli(r.id,'dcgmi health --check',f'server-{r.primary}')
        dcgm=[e for e in r.evidence if e['probe']=='dcgm']
        self.assertEqual(len(dcgm),1)
        self.assertIn('Xid 79',dcgm[0]['summary'])        # the aggregate equals the two outputs the player compared
        self.assertIn('다른 GPU PASS',dcgm[0]['summary'])
        self.assertEqual(s.incident_hypothesis(r.id,'gpu_health')['verdict'],'confirmed')

    def test_review_tor_ping_aggregate_matches_the_compared_targets(self):
        s,r=opened(self.temp,'tor_uplink')
        scoped(s,r,'ping')
        ping=[e for e in r.evidence if e['probe']=='ping']
        self.assertEqual(len(ping),1)
        self.assertEqual(ping[0]['status'],'bad')
        self.assertIn('다른 랙은 정상',ping[0]['summary'])
        outs=[o for o in s.linux['observations'] if o['command_id']=='ping']
        self.assertEqual(sum(o['code']==1 for o in outs),1)    # exactly the cut-off rack failed among the compared targets

    def test_review_partial_scope_message_does_not_depend_on_hidden_cause(self):
        messages=set()
        for cause in ('dns','tor_uplink','congestion','crashloop'):
            s,r=opened(self.temp,cause)
            self.assertEqual(job_servers(s,r),['A','B'])
            command(s,r,'ping',interpret=True,target='10.20.0.15')
            command(s,r,'dig')
            with self.assertRaises(ValueError) as cm:
                s.incident_hypothesis(r.id,'dns')
            messages.add(str(cm.exception))
        self.assertEqual(len(messages),1,messages)
        self.assertIn('10.20.11.15',messages.pop())

    def test_review_lost_gpu_only_on_its_own_server(self):
        from aidc.core.server_resources import ServerSlice
        s=LinuxSession(self.temp.db('lost.db'),practice='gpu_health',seed=5)
        s.confirm_shift_briefing()
        rid=next(iter(s.runs));s.select(rid);s.read_conversation(rid)
        s.choose_plan('performance',(ServerSlice('A',(0,1),2),ServerSlice('B',(0,1),1)))
        for _ in range(15):
            s.advance_time(10)
            if s.incident.records[0].state=='alert':break
        r=s.incident.records[0];s.incident_ack(r.id)
        healthy='B' if r.primary=='A' else 'A'
        lost=s.cli(r.id,'nvidia-smi',f'server-{r.primary}')
        self.assertEqual(lost['code'],15)
        self.assertIn('GPU is lost',lost['output'])
        self.assertEqual(s.cli(r.id,'nvidia-smi',f'server-{healthy}')['code'],0)
        self.assertIn('Xid 79',s.cli(r.id,'dcgmi health --check',f'server-{r.primary}')['output'])

    def test_review_tor_outputs_agree_with_each_other(self):
        s,r=opened(self.temp,'tor_uplink')
        affected=f'10.20.{11+"ABCD".index(r.primary)}.15'
        for line in ('ip addr','ip link show'):
            self.assertIn('<NO-CARRIER,BROADCAST,MULTICAST,UP>',s.cli(r.id,line,'network')['output'])
        port=f'swp{1+"ABCD".index(r.primary)}'
        self.assertIn('Link detected: no',s.cli(r.id,f'ethtool {port}','network')['output'])
        self.assertIn('Link detected: yes',s.cli(r.id,'ethtool eth0','network')['output'])   # management port stays up
        self.assertEqual(s.cli(r.id,'ping -c 3 10.20.0.15','network')['code'],0)                # so the switch node itself reaches storage
        self.assertIn('From 10.20.',s.cli(r.id,'ping -c 3 10.20.0.15',f'server-{r.primary}')['output'])
        # cut-off rack: ping and traceroute both fail at the last hop; a healthy in-scope target answers both
        self.assertEqual(s.cli(r.id,f'ping -c 3 {affected}','noc')['code'],1)
        self.assertIn(' 3  * * *',s.cli(r.id,f'traceroute {affected}','noc')['output'])
        self.assertEqual(s.cli(r.id,'ping -c 10 10.20.0.15','noc')['code'],0)
        self.assertNotIn('* * *\n',s.cli(r.id,'traceroute 10.20.0.15','noc')['output'].split('별표')[0])
        # from the affected server itself only its ToR gateway answers
        own=s.cli(r.id,'traceroute 10.20.0.15',f'server-{r.primary}')['output']
        self.assertIn(' 1  10.20.','\n'+own.split('\n',1)[1])
        self.assertIn(' 2  * * *',own)
        self.assertEqual(s.cli(r.id,'ping -c 3 10.20.0.15',f'server-{r.primary}')['code'],1)

    def test_review_ping_statistics_are_self_consistent(self):
        import re
        for cause in ('congestion','dns','tor_uplink'):
            s,r=opened(self.temp,cause)
            for n in (1,3,10,20):
                out=s.cli(r.id,f'ping -c {n} 10.20.0.15','noc')['output']
                sent,got,loss=map(int,re.search(r'(\d+) packets transmitted, (\d+) received, (\d+)% packet loss',out).groups())
                self.assertEqual(sent,n)
                self.assertEqual(loss,round(100*(sent-got)/sent))
                self.assertEqual(out.count('packets transmitted'),1)

    def test_review_previous_container_only_while_crash_looping(self):
        for cause in ('dns','crashloop'):
            s,r=opened(self.temp,cause)
            before=s.cli(r.id,'kubectl logs worker-0 -n aidc --previous','cluster')
            self.assertEqual(before['code'],0 if cause=='crashloop' else 1)
            diagnose(s,r);respond(s,r)
            for _ in range(15):
                if r.recovered is not None:break
                s.advance_time(10)
            after=s.cli(r.id,'kubectl logs worker-0 -n aidc --previous','cluster')
            self.assertEqual(after['code'],1,cause)
            self.assertIn('not found',after['output'])
            self.assertIn('Running            0',s.cli(r.id,'kubectl get pods -n aidc','cluster')['output'])

    def test_review_first_interpretation_is_final(self):
        s,r=opened(self.temp,'dns')
        out=command(s,r,'ping')
        wrong=next(x['id'] for x in out['choices'] if x['text']==C.BY_ID['ping'].wrong)
        right=next(x['id'] for x in out['choices'] if x['text']==C.BY_ID['ping'].correct)
        self.assertFalse(s.interpret(r.id,out['seq'],wrong)['correct'])
        self.assertFalse(s.interpret(r.id,out['seq'],right)['correct'])
        self.assertEqual(len(s.linux['interpretations']),1)
        scoped(s,r,'ping');command(s,r,'dig')
        with self.assertRaisesRegex(ValueError,'사실과 추측'):
            s.incident_hypothesis(r.id,'dns')
        again=command(s,r,'ping',interpret=True)
        self.assertTrue(s.linux['interpretations'][-1]['correct'])
        self.assertEqual(s.incident_hypothesis(r.id,'dns')['verdict'],'confirmed')
        with self.assertRaisesRegex(ValueError,'오래된'):
            s.interpret(r.id,again['seq'],right,'stale-token')

    def test_review_mutating_and_active_commands_are_explained(self):
        s,r=opened(self.temp,'crashloop')
        old=deepcopy(s._extra_payload())
        for line in ('nvidia-smi -r','nvidia-smi -pm 1','systemctl stop worker.service','systemctl kill worker.service',
                     'kubectl scale deploy worker --replicas=0 -n aidc','kubectl drain server-A','kubectl cordon server-A',
                     'kubectl exec worker-0 -n aidc','kubectl rollout undo deploy/worker -n aidc','ethtool -s eth0 speed 1000',
                     'journalctl --vacuum-size=1G','poweroff','halt','dd if=/dev/zero of=/dev/vdb','mkfs.ext4 /dev/vdb',
                     'mkfs /dev/vdb','iptables -F','kill -9 4815'):
            with self.subTest(line=line):
                out=s.cli(r.id,line,'noc')
                self.assertEqual((out['kind'],out['category'],out['code']),('error','mutation',126),line)
        diag=s.cli(r.id,'dcgmi diag -r 3','noc')
        self.assertEqual(diag['category'],'mutation')
        self.assertIn('dcgmi health --check',diag['output'])
        self.assertEqual(s.cli(r.id,'ss -s','noc')['category'],'option')
        self.assertEqual(s._extra_payload(),old)

    def test_review_process_and_gpu_follow_the_real_job_state(self):
        s,r=opened(self.temp,'ups')
        self.assertIsNone(s._job_hold(s.runs[r.rid]))
        ps=command(s,r,'ps')['output']
        self.assertIn(' 65.0 ',ps)
        self.assertIn(' R ',ps)
        s,r=opened(self.temp,'dns')
        node=f'server-{job_servers(s,r)[0]}'
        self.assertIn('   0%',s.cli(r.id,'nvidia-smi',node)['output'])
        self.assertIn(' S ',s.cli(r.id,'ps aux',node)['output'])

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
        healthy='B' if r.primary=='A' else 'A'
        normal=s.cli(r.id,'dcgmi health --check',f'server-{healthy}')
        self.assertIn(f'Server {healthy}: 감시 항목 경고 없음 · 건강 검사 PASS',normal['output'])
        self.assertNotIn('Xid',normal['output'])
        bad=s.cli(r.id,'dcgmi health --check',f'server-{r.primary}')
        self.assertIn('Xid 79',bad['output'])
        command(s,r,'journalctl',interpret=True)
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
        self.assertEqual(ping['code'],0)
        self.assertIn('3 received, 0% packet loss',ping['output'])
        self.assertEqual(dig['code'],0)
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
        scoped(s,r,'ping');command(s,r,'ip_addr')
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

# Commands whose output is shaped like the real tool instead of quoting the engine summary.
GROUNDED = {'ping': r'3 packets transmitted, 3 received, 0% packet loss', 'traceroute': r' 3  10\.20\.0\.15  0\.8 ms',
            'getent': r'^10\.20\.0\.15 +storage-api', 'dig': r'status: NOERROR[\s\S]*ANSWER SECTION',
            'nvidia_smi': r'   0%\n', 'dcgm': r'Server [AB]: 감시 항목 경고 없음 · 건강 검사 PASS', 'top': r' 2\.0 wa',
            'ps': r' S 09:00', 'pod_logs': r'FATAL|모델 경로', 'nvidia_query': r'HW Thermal Slowdown : Not Active',
            'ip_link': r'swp1: <BROADCAST,MULTICAST,UP,LOWER_UP>[\s\S]*alias ToR-A uplink', 'ethtool': r'Link detected: yes'}

def valid_case(spec):
    def test(self):
        s,r=opened(self.temp,'crashloop')
        out=command(s,r,spec.command_id)
        self.assertEqual(out['command_id'],spec.command_id)
        self.assertTrue(out['output'])
        self.assertLessEqual(len(out['output']),C.MAX_OUTPUT)
        self.assertEqual(out['code'],3 if spec.command_id=='systemctl' else 0)
        self.assertEqual(s.linux['observations'][-1]['node'],out['node'])
        if spec.command_id in GROUNDED:
            # Content basis: real-tool-shaped output computed from this incident's engine state (crashloop, job stopped)
            self.assertRegex(out['output'],GROUNDED[spec.command_id])
        elif spec.probe:
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
