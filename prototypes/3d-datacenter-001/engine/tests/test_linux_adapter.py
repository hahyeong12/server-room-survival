"""Phase8 adapter trust boundary, separate slots and old Chapter5 compatibility."""
from copy import deepcopy
from unittest.mock import patch
from engine.adapter import GameHost, ActionError
from engine.tests.test_global_adapter import GlobalBase
from aidc.learning.linux_catalog import BY_ID

class LinuxAdapterTests(GlobalBase):
    def ok(self, game, **action):
        out=self.act(game,**action)
        self.assertTrue(out['ok'],out)
        return out

    def practice(self,cause='dns'):
        g=self.host.new_game('linux_practice',cause)
        self.ok(g,type='confirm_briefing')
        rid=g.snapshot()['requests'][0]['id']
        self.ok(g,type='read_request',rid=rid)
        opts=self.ok(g,type='view_plans',rid=rid)['plans']['performance']['options']
        self.ok(g,type='select_plan',rid=rid,mode='performance',index=0,slices=opts[0])
        self.ok(g,type='navigate',route='hall',via='tab')
        self.ok(g,type='start_job',rid=rid,rack=opts[0][0]['rack'])
        for _ in range(15):
            self.ok(g,type='advance_time',minutes=10)
            rec=g.session.incident.records[0]
            if rec.state!='armed': break
        self.ok(g,type='incident_ack',incident=rec.id)
        return g,rec

    def test_linux_gate_and_existing_graduate_save(self):
        self.assertFalse(self.host.unlocks()['linux']['available'])
        with self.assertRaises(ActionError):self.host.new_game('linux')
        story=self.graduate()
        before=story.db.path.read_bytes()
        self.assertTrue(self.host.unlocks()['linux']['available'])
        g=self.host.new_game('linux')
        self.assertEqual(g.snapshot()['linux']['shiftCount'],5)
        self.assertEqual(story.db.path.read_bytes(),before)
        self.assertFalse(g.snapshot()['canAdvance'])

    def test_location_and_required_fresh_token(self):
        g,r=self.practice()
        token=g.session.token(r)
        self.assertFalse(self.act(g,type='linux_command',incident=r.id,line='ping -c 3 10.20.0.15',node='noc',token=token)['ok'])
        self.ok(g,type='navigate',route='noc',via='tab')
        self.assertFalse(self.act(g,type='linux_command',incident=r.id,line='ip addr',node='noc')['ok'])
        out=self.ok(g,type='linux_command',incident=r.id,line='ping -c 3 10.20.0.15',node='noc',token=token)['linux']
        self.assertNotIn('correct',out)
        self.assertFalse(self.act(g,type='linux_command',incident=r.id,line='ip addr',node='noc',token=token)['ok'])

    def test_retry_new_slot_and_original_unchanged(self):
        g,r=self.practice()
        before=g.path.read_bytes();name=g.id
        retry=self.host.retry(name)
        self.assertNotEqual(retry.id,name)
        self.assertEqual(g.path.read_bytes(),before)
        self.assertEqual(retry.kind,'linux_practice')
        self.assertEqual(retry.session.linux['practice'],'dns')
        self.assertEqual(retry.session.linux['observations'],[])

    def test_disk_resume_and_mode_discovery(self):
        g,r=self.practice()
        self.ok(g,type='navigate',route='noc',via='tab')
        self.ok(g,type='linux_command',incident=r.id,line='ping -c 3 10.20.0.15',node='noc',token=g.session.token(r))
        before=g.snapshot();gid=g.id
        self.host.close(gid)
        resumed=self.host.get(gid)
        after=resumed.snapshot()
        for key in ('requests','incident','linux','servers','clock','global'):
            self.assertEqual(before[key],after[key],key)
        self.assertTrue(any(x['id']==gid and x['kind']=='linux_practice' for x in self.host.saves()))

    def test_command_error_preserves_python_incident_and_ledger(self):
        g,r=self.practice()
        self.ok(g,type='navigate',route='noc',via='tab')
        before=deepcopy(g.session._extra_payload())
        out=self.ok(g,type='linux_command',incident=r.id,line='systemctl restart worker.service',node='noc',token=g.session.token(r))['linux']
        self.assertEqual(out['kind'],'error')
        self.assertEqual(g.session._extra_payload(),before)

    def test_physical_response_must_use_approved_site(self):
        g,r=self.practice()
        self.ok(g,type='navigate',route='noc',via='tab')
        # the whole scope of the request (storage + both job servers) is compared before the engine records ping
        for line in ('ping -c 3 10.20.0.15','ping -c 3 10.20.11.15','ping -c 3 10.20.12.15','dig storage-api.aidc.internal'):
            out=self.ok(g,type='linux_command',incident=r.id,line=line,node='noc',token=g.session.token(r))['linux']
        answer=next(x['id'] for x in out['choices'] if x['text']==BY_ID['dig'].correct)
        self.assertFalse(self.act(g,type='linux_interpret',incident=r.id,seq=out['seq'],answer=answer)['ok'])
        self.assertFalse(self.act(g,type='linux_interpret',incident=r.id,seq=out['seq'],answer=answer,token='stale')['ok'])
        self.ok(g,type='linux_interpret',incident=r.id,seq=out['seq'],answer=answer,token=g.session.token(r))
        self.ok(g,type='incident_hypothesis',incident=r.id,cause='dns')
        self.assertFalse(self.act(g,type='incident_act',incident=r.id,action='dns_failover')['ok'])
        self.ok(g,type='navigate',route='campus',via='tab')
        self.ok(g,type='navigate',route='room',via='button',building='NETWORK')
        self.assertEqual(self.ok(g,type='incident_act',incident=r.id,action='dns_failover')['incident']['action']['result'],'fix')

    def test_new_slot_open_failure_cleans_only_created_files(self):
        old=self.host.new_game('linux_practice','dns')
        before=old.path.read_bytes()
        with patch.object(self.host,'_open',side_effect=RuntimeError('UI init')):
            with self.assertRaises(RuntimeError):self.host.new_game('linux_practice','dns')
        self.assertEqual(len(list(self.host.dir.glob('aidc_3d_linux_*.db'))),1)
        self.assertEqual(old.path.read_bytes(),before)
