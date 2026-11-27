// Phase 9 shared real-UI play routines (same steps as phase9-qa.mjs, which stays the unchanged main evidence script).
// Every state change is a real click / select / key on the page. window.worldQA and SQLite are read-only checks.
import assert from 'node:assert/strict';
import * as U from './phase7-ui.mjs';
import * as P6 from './phase6-ui.mjs';
import {createLinuxPlayer} from './phase9-ui.mjs';

const PROBES={dns:['ping','dns'],tor_uplink:['tor_port'],congestion:['link_stats'],gpu_health:['dcgm'],gpu_oom:['job_log','dcgm'],storage_full:['storage_space'],storage_latency:['storage_latency','storage_space'],cooling:['cooling'],ups:['ups'],crashloop:['service_events','job_log']};
const VERIFY={dns:['dns','ping'],tor_uplink:['tor_port','ping'],congestion:['link_stats'],gpu_health:['dcgm'],gpu_oom:['job_log','dcgm'],storage_full:['storage_space','job_log'],storage_latency:['storage_latency','storage_space'],cooling:['cooling'],ups:['ups'],crashloop:['service_events','job_log']};
const PATH={dns:['dns_failover'],tor_uplink:['escalate_network'],congestion:['qos_adjust'],gpu_health:['gpu_repair'],gpu_oom:['ask_consent','reduce_batch'],storage_full:['cleanup_temp'],storage_latency:['storage_path'],cooling:['escalate_facility','+10','standby_pump'],ups:['escalate_facility'],crashloop:['escalate_platform','+10','rollback_deploy']};
const ORDER={1:{0:[['start','KR-SEL','performance'],['start','US-SFO','performance']],30:[['start','DE-FRA','performance']],40:[['wait','US-SEA']],60:[['start','JP-OSA','performance']],70:[['start','US-SEA','performance']]},2:{0:[['propose','US-IAD',false],['start','US-IAD','performance'],['propose','IN-BLR',true],['start','IN-BLR','economy']],20:[['wait','KR-PUS']],50:[['wait','GB-LON']],80:[['start','GB-LON','performance'],['start','NL-AMS','performance']],90:[['wait','TW-TPE']],100:[['start','TW-TPE','performance']],120:[['start','KR-PUS','performance']]},3:{0:[['propose','KR-DJN',true],['propose','AU-SYD',true],['start','KR-DJN','economy'],['start','AU-SYD','economy']],20:[['start','SG-SIN','performance']],40:[['wait','IN-BOM']],60:[['start','US-NYC','economy']],90:[['start','FR-PAR','performance']],120:[['start','IN-BOM','performance']]}};
const OPEN=r=>!['armed','closed','void','failed'].includes(r.state);

export function createFlows(getPage,report){
  const page=()=>getPage();let player=null,playerPage=null;const types={};
  const P=()=>{if(playerPage!==page()){playerPage=page();player=createLinuxPlayer(playerPage,report);}return player;};
  async function startAvailable(){const pg=page();const g=await U.G(pg);for(const r of g.requests.filter(x=>x.stage==='incoming'&&(g.global.kind==='free'||g.global.requestIds.includes(x.id)))){await U.read(pg,r.id);await U.tab(pg,'plan');const mode=await pg.locator('[data-plan-option^="performance:"]').count()?'performance':await pg.locator('[data-plan-option^="economy:"]').count()?'economy':null;if(mode){await U.choose(pg,r.id,mode);await U.startHall(pg,r.id);}}}
function classify(ev){const text=p=>ev.filter(e=>e.probe===p).at(-1)?.summary??'';
    if(/SERVFAIL|이름 조회 실패/.test(text('dns')))return 'dns';
      if(/Xid|ECC|FAIL/.test(text('dcgm')))return 'gpu_health';
      if(/OOM|out of memory/i.test(text('job_log')))return 'gpu_oom';
      if(/CrashLoop|재시작 [1-9]/.test(text('service_events')))return 'crashloop';
      if(/9[89]%|100%|공간 소진/.test(text('storage_space')))return 'storage_full';
      if(/85 ms|지연 증가/.test(text('storage_latency')))return 'storage_latency';
      if(/DOWN/.test(text('tor_port')))return 'tor_uplink';
      if(/95%|98%|혼잡|드롭 [1-9]/.test(text('link_stats')))return 'congestion';
      if(/WARN|저하|유량 1|31.5/.test(text('cooling')))return 'cooling';
      if(/배터리 운전|입력 이상/.test(text('ups')))return 'ups';
      return null;}
  async function infer(id,linux){const pg=page();
    if(linux){for(const ident of ['ping','ip_link','getent','journalctl','df','iostat','traceroute','nvidia_smi','dcgm','pods']){const g=await U.G(pg);if(ident==='pods'&&!g.linux.contexts[id].some(n=>n.id==='cluster'&&n.available))continue;await P().scoped(id,ident,{interpret:ident==='journalctl'});}}
    else for(const probe of Object.keys((await U.G(pg)).incident.menu.probes.reduce((o,p)=>(o[p.id]=true,o),{})))await U.observe(pg,id,probe);
    // Cooling/UPS readings belong to the BMS (facilities), not the Linux hosts: when every CLI reading is normal the
  // player checks the cooling plant and the UPS panel too, as Phase 8 QA does.
  if(linux&&!classify((await U.inc(pg,id)).evidence))for(const probe of ['cooling','ups'])await U.observe(pg,id,probe);
  const ev=(await U.inc(pg,id)).evidence,type=classify(ev);if(type)return type;
    throw new Error('Cannot infer from visible evidence: '+JSON.stringify(ev));
  }
  async function handle(rec){const pg=page(),id=rec.id;let g=await U.G(pg);const linux=!!g.linux&&!g.linux.optional;
    if(rec.state==='alert'){
      await U.ack(pg,id);const type=await infer(id,linux);types[g.id+id]=type;
      if(linux)await P().evidence(id,type);else for(const p of PROBES[type])if(!(await U.inc(pg,id)).evidence.some(e=>e.probe===p))await U.observe(pg,id,p);
      const verdict=await U.hypothesis(pg,id,type);assert.equal(verdict.verdict,'confirmed',JSON.stringify(verdict));await U.notify(pg,id);
      const act=async(a,rid)=>g.linux?P().act(id,a,rid):U.act(pg,id,a,rid);
      for(const a of PATH[type]){if(a==='+10'){await U.advance(pg,10);continue;}const result=await act(a);assert.ok(result&&!['none','refused'].includes(result.result),`${id} ${a}: ${JSON.stringify(result)}`);}
      if(type==='ups')for(const j of (await U.inc(pg,id)).scope.jobs)await act('planned_pause',j.rid);
    }
    rec=await U.inc(pg,id);const type=types[(await U.G(pg)).id+id]??rec.cause;
    if(rec.state==='monitoring'&&!rec.verifyBlocker?.includes('10분')){
      if(linux)await P().evidence(id,type,true);
      const now=(await U.G(pg)).clock.minute;
      for(const p of rec.verifyProbes?.length?rec.verifyProbes:VERIFY[type]){rec=await U.inc(pg,id);if(!rec.evidence.some(e=>e.probe===p&&e.minute===now))await U.observe(pg,id,p);}
      assert.equal((await U.verify(pg,id)).state,'verified');assert.equal((await U.report(pg,id)).state,'closed');
    }
  }
  async function handleOpen(){for(const r of (await U.G(page())).incident.records.filter(OPEN))await handle(r);}
  async function workShift(){const pg=page();await U.talkThrough(pg);for(let n=0;n<80;n++){await startAvailable();await handleOpen();const g=await U.G(pg);if(g.global.done){assert.equal(g.global.result.cleared,true,JSON.stringify(g.global.result));report.shifts.push({kind:g.kind,shift:g.global.shift,result:g.global.result});return g;}await U.advance(pg,10);}throw new Error('Shift did not finish');}
  async function globalShift(n){const pg=page();await U.talkThrough(pg);const begin=(await U.G(pg)).clock.minute;for(let i=0;i<40;i++){const g=await U.G(pg);for(const [kind,site,arg]of ORDER[n][g.clock.minute-begin]??[]){const id=await P6.rid(pg,site);if(kind==='start')await P6.start(pg,id,arg);else if(kind==='wait')await P6.wait(pg,id);else assert.equal((await P6.negotiate(pg,id)).status,arg?'accepted':'rejected');}if((await U.G(pg)).global.done)break;await U.advance(pg,10);}assert.equal((await U.G(pg)).global.result.cleared,true);}
  return {startAvailable,handle,handleOpen,workShift,globalShift,OPEN};
}
