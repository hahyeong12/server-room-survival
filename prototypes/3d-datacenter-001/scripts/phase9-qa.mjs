// Phase9: only real UI actions mutate games; SQLite reads verify the isolated temporary saves.
import {chromium} from 'playwright-core';
import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import {resolve,join} from 'node:path';
import {DatabaseSync} from 'node:sqlite';
import {startStack,CHROME,settle} from './qa-lib.mjs';
import * as U from './phase7-ui.mjs';
import * as P6 from './phase6-ui.mjs';
import * as C from './campaign-flows.mjs';
import {createLinuxPlayer} from './phase9-ui.mjs';

const out=resolve(process.argv.find(x=>x.startsWith('--out='))?.slice(6)??'../../docs/3d-world-expansion/qa/phase9/browser-1');
await mkdir(out,{recursive:true});
const report={issue:10,checks:[],errors:[],consoleErrors:[],commands:[],actions:[],shifts:[],free:[],resumes:[],layouts:[],startedAt:new Date().toISOString()};
let stack,browser,page,ctx,player;
const types={};
const shot=async name=>page.screenshot({path:join(out,name)});
async function check(name,fn){try{await fn();report.checks.push({name,pass:true});console.log(`PASS ${name}`);}catch(e){await shot(`FAIL-${report.checks.length}.png`).catch(()=>{});report.checks.push({name,pass:false,error:e.stack});throw e;}finally{await writeFile(join(out,'phase9-qa.json'),JSON.stringify(report,null,2));}}
async function open(){ctx=await browser.newContext({viewport:{width:1920,height:1080},reducedMotion:'reduce'});await ctx.addInitScript(()=>localStorage.setItem('srs3d.opening.seen.v1','1'));page=await ctx.newPage();page.on('pageerror',e=>report.errors.push(e.message));page.on('console',m=>{if(m.type()==='error')report.consoleErrors.push(m.text());});page.on('dialog',d=>d.accept());await page.goto(stack.url);await page.waitForFunction(()=>!!window.worldQA);await page.waitForTimeout(1000);player=createLinuxPlayer(page,report);}
async function menu(){await U.drain(page);if(await page.locator('#screen-dialog[open]').count()){await U.click(page,'#screen-dialog [data-next=menu]');await settle(page);}if(!await page.locator('#menu:not([hidden])').count())await U.click(page,'#menu-open');await page.waitForSelector('[data-new=global_free]');}
async function fresh(mode,options){await menu();if(options){await page.locator('[data-free-seed]').fill(String(options.seed));await page.selectOption('[data-free-difficulty]',options.difficulty);}await U.click(page,`[data-new=${mode}]`);await page.waitForTimeout(500);}
async function restart(label){const before=await U.G(page);await stack.restartEngine();await page.reload();await page.waitForFunction(()=>!!window.worldQA?.snapshot().game);await settle(page);const after=await U.G(page);for(const k of ['clock','requests','servers','global','incident','linux','senior','assessment'])assert.deepEqual(after[k],before[k],label+' '+k);report.resumes.push({label,id:after.id,minute:after.clock.minute});}
function payload(id){const db=new DatabaseSync(join(stack.saveDir,id+'.db'),{readOnly:true});try{return JSON.parse(db.prepare('SELECT payload FROM simulation_state WHERE id=1').get().payload);}finally{db.close();}}
async function startAvailable(){let g=await U.G(page);for(const r of g.requests.filter(x=>x.stage==='incoming'&&(g.global.kind==='free'||g.global.requestIds.includes(x.id)))){await U.read(page,r.id);await U.tab(page,'plan');const mode=await page.locator('[data-plan-option^="performance:"]').count()?'performance':await page.locator('[data-plan-option^="economy:"]').count()?'economy':null;if(mode){await U.choose(page,r.id,mode);await U.startHall(page,r.id);}}}
const PROBES={dns:['ping','dns'],tor_uplink:['tor_port'],congestion:['link_stats'],gpu_health:['dcgm'],gpu_oom:['job_log','dcgm'],storage_full:['storage_space'],storage_latency:['storage_latency','storage_space'],cooling:['cooling'],ups:['ups'],crashloop:['service_events','job_log']};
const VERIFY={dns:['dns','ping'],tor_uplink:['tor_port','ping'],congestion:['link_stats'],gpu_health:['dcgm'],gpu_oom:['job_log','dcgm'],storage_full:['storage_space','job_log'],storage_latency:['storage_latency','storage_space'],cooling:['cooling'],ups:['ups'],crashloop:['service_events','job_log']};
async function infer(id,linux){
  if(linux){for(const ident of ['ping','getent','journalctl','df','iostat','traceroute','nvidia_smi','dcgm','pods']){const g=await U.G(page);if(ident==='pods'&&!g.linux.contexts[id].some(n=>n.id==='cluster'))continue;await player.scoped(id,ident,{interpret:ident==='journalctl'});}}
  else for(const probe of Object.keys((await U.G(page)).incident.menu.probes.reduce((o,p)=>(o[p.id]=true,o),{})))await U.observe(page,id,probe);
  const r=await U.inc(page,id),ev=r.evidence;
  const text=p=>ev.filter(e=>e.probe===p).at(-1)?.summary??'';
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
  throw new Error('Cannot infer from visible evidence: '+JSON.stringify(ev));
}
async function handle(rec){const id=rec.id;let g=await U.G(page),linux=!!g.linux;
  if(rec.state==='alert'){
    await U.ack(page,id);const type=await infer(id,linux);types[g.id+id]=type;
    if(linux)await player.evidence(id,type);else for(const p of PROBES[type])if(!(await U.inc(page,id)).evidence.some(e=>e.probe===p))await U.observe(page,id,p);
    const verdict=await U.hypothesis(page,id,type);assert.equal(verdict.verdict,'confirmed',JSON.stringify(verdict));await U.notify(page,id);
    const act=async(a,rid)=>linux?player.act(id,a,rid):U.act(page,id,a,rid);
    const path={dns:['dns_failover'],tor_uplink:['escalate_network'],congestion:['qos_adjust'],gpu_health:['gpu_repair'],gpu_oom:['ask_consent','reduce_batch'],storage_full:['cleanup_temp'],storage_latency:['storage_path'],cooling:['escalate_facility','+10','standby_pump'],ups:['escalate_facility'],crashloop:['escalate_platform','+10','rollback_deploy']}[type];
    for(const a of path){if(a==='+10'){await U.advance(page,10);continue;}const result=await act(a);assert.ok(result&&!['none','refused'].includes(result.result),`${id} ${a}: ${JSON.stringify(result)}`);}
    if(type==='ups')for(const j of (await U.inc(page,id)).scope.jobs)await act('planned_pause',j.rid);
  }
  rec=await U.inc(page,id);const type=types[(await U.G(page)).id+id]??rec.cause;
  if(rec.state==='monitoring'&&!rec.verifyBlocker?.includes('10분')){
    if(linux)await player.evidence(id,type,true);
    for(const p of VERIFY[type]){rec=await U.inc(page,id);if(!rec.evidence.some(e=>e.probe===p&&e.after))await U.observe(page,id,p);}
    assert.equal((await U.verify(page,id)).state,'verified');assert.equal((await U.report(page,id)).state,'closed');
  }
}
async function workShift(){await U.talkThrough(page);for(let n=0;n<80;n++){await startAvailable();let g=await U.G(page);for(const r of g.incident.records.filter(r=>!['armed','closed','void','failed'].includes(r.state)))await handle(r);g=await U.G(page);if(g.global.done){assert.equal(g.global.result.cleared,true,JSON.stringify(g.global.result));report.shifts.push({kind:g.kind,result:g.global.result});return;}await U.advance(page,10);}throw new Error('Shift did not finish');}
const ORDER={1:{0:[['start','KR-SEL','performance'],['start','US-SFO','performance']],30:[['start','DE-FRA','performance']],40:[['wait','US-SEA']],60:[['start','JP-OSA','performance']],70:[['start','US-SEA','performance']]},2:{0:[['propose','US-IAD',false],['start','US-IAD','performance'],['propose','IN-BLR',true],['start','IN-BLR','economy']],20:[['wait','KR-PUS']],50:[['wait','GB-LON']],80:[['start','GB-LON','performance'],['start','NL-AMS','performance']],90:[['wait','TW-TPE']],100:[['start','TW-TPE','performance']],120:[['start','KR-PUS','performance']]},3:{0:[['propose','KR-DJN',true],['propose','AU-SYD',true],['start','KR-DJN','economy'],['start','AU-SYD','economy']],20:[['start','SG-SIN','performance']],40:[['wait','IN-BOM']],60:[['start','US-NYC','economy']],90:[['start','FR-PAR','performance']],120:[['start','IN-BOM','performance']]}};
async function globalShift(n){await U.talkThrough(page);const begin=(await U.G(page)).clock.minute;for(let i=0;i<40;i++){const g=await U.G(page);for(const [kind,site,arg]of ORDER[n][g.clock.minute-begin]??[]){const id=await P6.rid(page,site);if(kind==='start')await P6.start(page,id,arg);else if(kind==='wait')await P6.wait(page,id);else assert.equal((await P6.negotiate(page,id)).status,arg?'accepted':'rejected');}if((await U.G(page)).global.done)break;await U.advance(page,10);}assert.equal((await U.G(page)).global.result.cleared,true);}
async function free(seed,difficulty){await fresh('global_free',{seed,difficulty});assert.equal((await U.G(page)).canAdvance,false);await U.talkThrough(page);for(let n=0;n<16;n++){await startAvailable();let g=await U.G(page);for(const r of g.incident.records.filter(r=>!['armed','closed','void','failed'].includes(r.state)))await handle(r);if(n===3)await restart('free midshift');if(n===5)await U.click(page,'[data-free-end]');g=await U.G(page);if(g.global.done)break;await U.advance(page,10);}let g=await U.G(page);for(let i=0;i<40&&!g.global.done;i++){await startAvailable();for(const r of g.incident.records.filter(r=>!['armed','closed','void','failed'].includes(r.state)))await handle(r);if(!(await U.G(page)).global.done)await U.advance(page,10);g=await U.G(page);}assert.equal(g.global.done,true);const p=payload(g.id);assert.deepEqual(p.global.result,g.global.result);report.free.push({seed,difficulty,events:p.free_incidents.events,result:g.global.result});await shot(`free-${seed}-${difficulty}.png`);return p;}
try{
 stack=await startStack({enginePort:8789,vitePort:5189,log:s=>console.log(s.trim())});browser=await chromium.launch({executablePath:CHROME,headless:false,args:['--no-first-run']});await open();
 await check('public career map and senior lock',async()=>{assert.equal(await page.locator('[data-new=senior]').isDisabled(),true);assert.match(await page.locator('[data-career]').innerText(),/신입/);});
 await check('free none: start, jobs, restart, finish',async()=>{const p=await free(42,'none');assert.equal(p.incident.records.length,0);});
 await check('seeded challenge: real incidents, recovery, report, finish; same seed replay',async()=>{const a=await free(91,'challenge'),b=await free(91,'challenge');assert.ok(a.incident.records.length>0);assert.deepEqual(a.free_incidents,b.free_incidents);assert.deepEqual(a.global.result,b.global.result);});
 await check('different seed standard produces distinct incident layout',async()=>{const p=await free(7,'standard');assert.notDeepEqual(p.free_incidents.events,report.free[1].events);});
 if(!process.argv.includes('--free-only')){
 await check('story chapters 1 to 5 through first public menu',async()=>{await fresh('story');await C.chapter1(page);for(const [key,fn]of [['2',C.chapter2],['3',C.chapter3],['3b',C.chapter4],['lab',C.chapter5]]){await C.startNext(page,key);await fn(page);}assert.equal((await U.S(page)).screens.open,'graduation');});
 await check('regular global three shifts through UI',async()=>{await fresh('global');for(let n=1;n<=3;n++){await globalShift(n);if(n<3)await U.click(page,'[data-next=next-shift]');}});
 await check('regular incident three shifts through UI',async()=>{await fresh('incident');for(let n=1;n<=3;n++){await workShift();if(n<3)await U.click(page,'[data-next=next-incident]');}});
 await check('Linux five shifts through UI, education remains separate',async()=>{await fresh('linux');for(let n=1;n<=5;n++){await workShift();if(n<5)await U.click(page,'[data-next=next-linux]');}assert.match(await page.locator('#screen-slot').innerText(),/독립 관제 엔지니어/);});
 await check('senior evaluation 1 and 2, restart, ending, free branch',async()=>{await fresh('senior');await workShift();await restart('senior first result');await U.click(page,'[data-next=next-linux]');await workShift();const g=await U.G(page);assert.equal(g.senior.ending,true);assert.deepEqual(payload(g.id).global.result,g.global.result);assert.ok(g.global.result.assessment.operations.score>=70);assert.ok(g.global.result.assessment.learning.score>=70);await page.waitForSelector('[data-ending]');await shot('senior-ending.png');await U.click(page,'[data-next=global-free]');assert.equal((await U.G(page)).kind,'global_free');});
 }
 assert.deepEqual(report.errors,[]);assert.deepEqual(report.consoleErrors,[]);
}catch(e){report.failure=e.stack;console.error(e.stack);process.exitCode=1;}
finally{report.finishedAt=new Date().toISOString();report.summary={pass:report.checks.filter(c=>c.pass).length,total:report.checks.length};await writeFile(join(out,'phase9-qa.json'),JSON.stringify(report,null,2));await ctx?.close();await browser?.close();await stack?.stop();}
