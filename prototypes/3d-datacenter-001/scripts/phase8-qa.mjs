// Issue #9: real mouse/select/typing QA. No seeding and no mutating API calls.
// Even the prerequisite Chapter1->5 graduation is played through the existing UI.
import {chromium} from 'playwright-core';
import assert from 'node:assert/strict';
import {mkdir,writeFile,readFile} from 'node:fs/promises';
import {resolve,join} from 'node:path';
import {createHash} from 'node:crypto';
import {DatabaseSync} from 'node:sqlite';
import {startStack,CHROME,settle} from './qa-lib.mjs';
import * as U from './phase7-ui.mjs';
import * as C from './campaign-flows.mjs';

const out=resolve(process.argv.find(x=>x.startsWith('--out='))?.slice(6)??'../../docs/3d-world-expansion/qa/phase8');
await mkdir(out,{recursive:true});
const dev=process.argv.includes('--practice-only');
const only=process.argv.find(x=>x.startsWith('--only='))?.slice(7);
const report={issue:9,mode:'real Chrome mouse/select/typing; no seed/no API progression; OS temporary saves',developmentOnly:dev,
  checks:[],errors:[],consoleErrors:[],commands:[],actions:[],shifts:[],truth:[],resumes:[],layouts:[],performance:[],screenshots:[],startedAt:new Date().toISOString()};
let stack,browser,page,ctx,career;
const shot=async name=>{await page.screenshot({path:join(out,name)});report.screenshots.push(name);};
async function check(name,fn){if(only&&!name.includes(only))return;const t=Date.now();try{await fn();report.checks.push({name,pass:true,ms:Date.now()-t});console.log(`PASS ${name}`);}catch(e){try{await shot(`FAIL-${report.checks.length}.png`);}catch{}report.checks.push({name,pass:false,error:e.stack});console.log(`FAIL ${name}: ${e.message}`);throw e;}}
async function open({width=1920,height=1080,dpr=1}={}){
  ctx=await browser.newContext({viewport:{width,height},deviceScaleFactor:dpr,reducedMotion:'reduce',permissions:['clipboard-read','clipboard-write']});
  await ctx.addInitScript(()=>localStorage.setItem('srs3d.opening.seen.v1','1'));
  page=await ctx.newPage();page.on('pageerror',e=>report.errors.push(e.message));page.on('console',m=>{if(m.type()==='error')report.consoleErrors.push(m.text());});
  page.on('dialog',d=>d.accept());await page.goto(stack.url);await page.waitForFunction(()=>!!window.worldQA);await page.waitForTimeout(800);
}
async function select(sel,value){await page.selectOption(sel,String(value));await settle(page,50);}
async function linuxTab(id){await U.tab(page,'linux');if(await page.locator('[data-linux-incident]').count())await select('[data-linux-incident]',id);}
const GROUPS={dns:['ping','getent','journalctl'],tor_uplink:['ip_link','ping'],congestion:['traceroute','ping'],gpu_health:['dcgm','journalctl'],
  gpu_oom:['journalctl','nvidia_smi','systemctl'],storage_full:['df','journalctl'],storage_latency:['iostat','df'],cooling:['nvidia_smi','journalctl'],ups:['journalctl','ps'],crashloop:['pods','journalctl']};
const SEMANTIC={ping:'ICMP 응답',getent:'설정된 이름 조회',dig:'응답 코드',ip_addr:'선택한 노드의 주소',ip_route:'다음 홉 설정',ethtool:'link detected',ip_link:'carrier 상태',traceroute:'각 홉의 응답',
  journalctl:'선택 서비스가 남긴',nvidia_smi:'GPU 메모리·온도',nvidia_query:'장치 상태와 ECC',dcgm:'사전 구성된 passive',df:'블록 공간',iostat:'await·util',
  systemctl:'가상 worker 서비스',ps:'선택 노드의 프로세스',pods:'가상 namespace의 상태',df_inode:'inode 수',free:'호스트 RAM 가용량',top:'단일 표본'};
function primary(g,id){return g.linux.contexts[id].find(n=>n.assigned)?.id??'server-A';}
async function command(id,ident,{interpret=false,line=null,node=null,target=null,forceTyping=false}={}){
  await linuxTab(id);let g=await U.G(page);const spec=g.linux.commands.find(c=>c.command_id===ident);assert.ok(spec,ident);
  node??=spec.context==='worker'?primary(g,id):spec.context==='any'?'noc':spec.context;
  await select('[data-linux-node]',node);g=await U.G(page);
  const n=g.linux.observations.length,old=JSON.stringify([g.clock,g.datacenter,g.servers,g.requests.map(r=>[r.id,r.progress,r.stage])]);
  const args=Object.fromEntries(Object.entries(g.linux.arguments).map(([k,v])=>[k,v[0]]));args.$count='3';if(target){if(spec.syntax.includes('$iface'))args.$iface=target;else args.$host=target;}
  const text=line??spec.syntax.split(' ').map(t=>args[t]??t).join(' ');
  if(g.linux.inputMode==='choice'&&!forceTyping&&!line){await select('[data-linux-command]',ident);if(await page.locator('[data-linux-target]').count())await select('[data-linux-target]',args.$host);if(await page.locator('[data-linux-iface]').count())await select('[data-linux-iface]',args.$iface);await U.click(page,'[data-linux-choice]');}
  else if(g.linux.inputMode==='assemble'&&!forceTyping&&!line){await select('[data-linux-command]',ident);for(const [i,t]of spec.syntax.split(' ').entries())if(i)await select(`[data-linux-part="${i}"]`,args[t]??t);await U.click(page,'[data-linux-assemble]');}
  else{await page.locator('[data-linux-input]').fill('');await page.locator('[data-linux-input]').pressSequentially(text,{delay:1});await page.locator('[data-linux-input]').press('Enter');await settle(page,150);}
  const after=await U.G(page);assert.equal(after.linux.observations.length,n+1,`${id} ${text} records valid CLI observation`);
  assert.equal(JSON.stringify([after.clock,after.datacenter,after.servers,after.requests.map(r=>[r.id,r.progress,r.stage])]),old,'diagnostic CLI does not repair or move time/resources');
  const entry=after.linux.observations.at(-1);assert.equal(entry.command_id,ident);assert.equal(entry.node,node);
  assert.ok(await page.locator(`[data-linux-observation="${entry.seq}"]`).count());
  if(interpret){const choices=await page.locator('[data-linux-answer]').allTextContents(),needle=SEMANTIC[ident];const choice=choices.findIndex(t=>t.includes(needle));assert.ok(choice>=0,`${ident} meaning on UI`);await U.click(page,`[data-linux-answer="${choice===0?'a':'b'}"]`);assert.equal((await U.G(page)).linux.interpretations.at(-1).correct,true);}
  report.commands.push({id,command:ident,line:text,node,code:entry.code,status:entry.status,after:entry.after,seq:entry.seq});return entry;
}
async function act(id,action,rid){
  await U.incidentTab(page,id);const away=page.locator(`.inc-card [data-action-goto="${action}"]`);
  if(await away.count()){await away.click();await settle(page,300);await page.waitForTimeout(850);}
  const scope=page.locator(`[data-incident-actions="${id}"]`);
  if(rid!==undefined&&await scope.locator('[data-incident-rid]').count())await select(`[data-incident-actions="${id}"] [data-incident-rid]`,rid);
  await scope.locator(`[data-incident-action="${action}"]`).click();await settle(page,160);
  const entry=(await U.inc(page,id)).actions.at(-1);assert.equal(entry.action,action);report.actions.push({id,action,result:entry.result,at:(await U.S(page)).state.navigation.route});return entry;
}
// The engine records node/target dependent evidence only once the whole scope of the request was compared:
// storage + every job server for ping/traceroute, every job server for the GPU health family.
function scopeOf(g,id){const servers=g.linux.contexts[id].filter(n=>n.assigned).map(n=>n.id.slice(-1));
  return {targets:['10.20.0.15',...servers.map(x=>`10.20.${11+'ABCD'.indexOf(x)}.15`)],nodes:servers.map(x=>`server-${x}`)};}
async function scoped(id,ident,{interpret=false}={}){
  const g=await U.G(page),spec=g.linux.commands.find(c=>c.command_id===ident),{targets,nodes}=scopeOf(g,id);let out;
  if(['ping','traceroute'].includes(ident)){for(const [i,t]of targets.entries())out=await command(id,ident,{interpret:interpret&&i===0,target:t});return out;}
  if(spec.probe==='dcgm'){for(const [i,n]of nodes.entries())out=await command(id,ident,{interpret:interpret&&i===0,node:n});return out;}
  return command(id,ident,{interpret});
}
async function bms(id,type){if(type==='cooling'||type==='ups')await U.observe(page,id,type);}
function targetIP(rec){const server=rec.scope.jobs.find(j=>j.rid===rec.rid)?.servers?.[0]??'A';return `10.20.${11+'ABCD'.indexOf(server)}.15`;}
async function evidence(id,type,post=false){for(const ident of GROUPS[type])await scoped(id,ident,{interpret:!post});await bms(id,type);}
// For the final exam infer from the output, not from a hidden engine type or a seeded result.
async function independentEvidence(id){
  const rows=[];for(const ident of ['ping','getent','journalctl','df','iostat','traceroute','pods'])rows.push(await scoped(id,ident,{interpret:ident==='journalctl'}));
  const own=ident=>rows.find(r=>r.command_id===ident)?.output??'';
  if(/CrashLoopBackOff\s+9/.test(own('pods')))return 'crashloop';
  if(/vdb\s+40\.0\s+10\.0\s+85\.0/.test(own('iostat')))return 'storage_latency';
  if(/ 3  \S+  42\.1 ms/.test(own('traceroute')))return 'congestion';
  throw new Error('Could not explain this exam incident from its visible output');
}
const TYPES={1:['tor_uplink','dns'],2:['storage_latency','storage_full'],3:['gpu_oom','gpu_health'],4:['ups','cooling']};
const diagnosed={},step={},responsePlans={},seenTypes=new Set();let restartLearning=false,restartRecovery=false,wrongActionDone=false;
async function restart(label){
  const before=await U.G(page);await stack.restartEngine();await page.reload();
  try{await page.waitForFunction(()=>!!window.worldQA?.snapshot().game);}
  catch(e){const why=await page.evaluate(async id=>{const r=await fetch(`/api/games/${encodeURIComponent(id)}`);return `${r.status} ${await r.text()}`;},before.id).catch(x=>String(x));
    throw new Error(`${label}: resume after engine restart failed: ${why.slice(0,600)}`);}
  await page.waitForTimeout(500);
  const after=await U.G(page);for(const k of ['linux','incident','clock','servers','requests','global'])assert.deepEqual(after[k],before[k],`${label}: ${k} persisted`);report.resumes.push({label,id:after.id,minute:after.clock.minute});
}
async function handle(rec,number){
  const id=rec.id;
  if(rec.state==='alert'){
    await U.ack(page,id);
    const type=number===5?await independentEvidence(id):TYPES[number][rec.id.endsWith('1')?0:1];diagnosed[id]=type;seenTypes.add(type);
    if(number!==5)await evidence(id,type);
    if(number===1&&type==='dns'){
      await linuxTab(id);await page.locator('[data-linux-input]').fill('clear');await page.locator('[data-linux-input]').press('Enter');await settle(page);
      assert.equal(await page.locator('[data-linux-observation]').count(),0,'clear hides only this incident output');
      const other=(await U.G(page)).incident.records.find(r=>r.id!==id&&r.state==='closed');assert.ok(other);
      await select('[data-linux-incident]',other.id);assert.ok(await page.locator('[data-linux-observation]').count(),'clear preserves other incident output');
      await select('[data-linux-incident]',id);report.actions.push({id,action:'clear scoped to incident',result:'UI only'});
    }
    if(number===1&&type==='tor_uplink'){await command(id,'getent');const wrong=await U.hypothesis(page,id,'dns');assert.equal(wrong.verdict,'refuted');}
    if(!restartLearning){await shot('p8-learning-choice.png');await restart('learning before diagnosis');restartLearning=true;}
    const h=await U.hypothesis(page,id,type);assert.equal(h.verdict,'confirmed');
    if(type==='dns'&&!wrongActionDone){assert.equal((await act(id,'restart_service')).result,'none');await U.advance(page,10);wrongActionDone=true;}
    await U.notify(page,id);step[id]=0;
  }
  rec=await U.inc(page,id);const type=diagnosed[id];if(!type)return;
  const scripts={dns:['dns_failover'],tor_uplink:['reroute_uplink'],congestion:['qos_adjust'],gpu_health:['isolate_migrate'],gpu_oom:['ask_consent','reduce_batch'],storage_full:['cleanup_temp'],storage_latency:['storage_path'],cooling:['escalate_facility','wait','standby_pump'],ups:['escalate_facility','planned_pause'],crashloop:['escalate_platform','wait','rollback_deploy']};
  const script=responsePlans[id]??=scripts[type];
  while(step[id]<script.length&&['diagnosed','recovering'].includes(rec.state)){
    let a=script[step[id]];
    if(a==='wait'){if(!Object.values(rec.escalations).some(e=>e.ready))return;step[id]++;continue;}
    const r=await act(id,a);assert.ok(['fix','call','consent','pause','isolate_move','isolate_repair','refused'].includes(r.result),`${id} ${a} effect`);
    if(r.result==='refused'){
      if(a==='isolate_migrate')await act(id,'gpu_repair');
      else if(a==='reroute_uplink')await act(id,'escalate_network');
      else if(a==='reduce_batch'){script.splice(step[id]+1,0,'escalate_platform','wait','memory_saving');scripts[type]=script;}
      else throw new Error(`${id} ${a} unexpected refusal: ${r.text}`);
    }
    step[id]++;rec=await U.inc(page,id);
  }
  if(type==='cooling'&&rec.state==='recovering'&&!restartRecovery){await shot('p8-cooling-recovery.png');await restart('facility recovery timer');restartRecovery=true;}
  if(rec.state==='monitoring'&&!rec.verifyBlocker?.includes('10분')){
    await evidence(id,type,true);const v=await U.verify(page,id);assert.equal(v.state,'verified');const end=await U.report(page,id);assert.equal(end.state,'closed');
  }
}
function truth(g){const db=new DatabaseSync(join(stack.saveDir,`${g.id}.db`),{readOnly:true});try{const payload=JSON.parse(db.prepare('SELECT payload FROM simulation_state WHERE id=1').get().payload);assert.equal(payload.global.result.cleared,g.global.result.cleared);assert.deepEqual(payload.global.result.linux,g.global.result.linux);const rs=payload.incident.records.filter(r=>r.shift===g.global.shift);for(const r of rs){const visible=g.incident.records.find(x=>x.id===r.id);assert.equal(r.state,visible.state);assert.equal(r.evidence.length,visible.evidence.length);assert.equal(r.type,visible.cause);}
 report.truth.push({shift:g.global.shift,save:g.id,types:rs.map(r=>r.type),states:rs.map(r=>r.state),observations:payload.linux.observations.length});}finally{db.close();}}
async function shift(number){
  await U.talkThrough(page);assert.equal((await U.G(page)).linux.inputMode,number===1?'choice':number===2?'assemble':'terminal');
  for(let i=0;i<85;i++){
    let g=await U.G(page);
    for(const r of g.requests.filter(x=>x.stage==='incoming'&&g.global.requestIds.includes(x.id))){await U.read(page,r.id);await U.tab(page,'plan');const mode=await page.locator('[data-plan-option^="performance"]').count()?'performance':'economy';await U.choose(page,r.id,mode);await U.startHall(page,r.id);}
    g=await U.G(page);for(const r of g.incident.records.filter(r=>!['armed','closed','failed','void'].includes(r.state)))await handle(r,number);
    if((await U.G(page)).global.done)break;
    await U.advance(page,10);
  }
  const g=await U.G(page);assert.ok(g.global.done&&g.global.result.cleared,`Linux shift ${number} cleared`);truth(g);report.shifts.push(g.global.result);career=g.id;await shot(`p8-shift-${number}-clear.png`);
  if(number<5){await U.click(page,'#screen-dialog[open] [data-next=next-linux]');}
}
async function practice(cause='dns'){
  if(await page.locator('#screen-dialog[open]').count())await U.click(page,'#screen-dialog [data-next=stay]');
  if(!await page.locator('#menu:not([hidden])').count())await U.click(page,'#menu-open');
  await select('[data-linux-practice]',cause);await U.click(page,'[data-new=linux_practice]');await U.talkThrough(page);
  let g=await U.G(page);const r=g.requests[0];await U.startJob(page,r.id,'performance');
  for(let i=0;i<15;i++){g=await U.G(page);if(g.incident.records[0].state==='alert')break;await U.advance(page,10);}
  const rec=(await U.G(page)).incident.records[0];await U.ack(page,rec.id);return rec;
}
async function layout(width,height,dpr){await page.setViewportSize({width,height});const cdp=await ctx.newCDPSession(page);await cdp.send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:dpr,mobile:false});await linuxTab((await U.G(page)).incident.records[0].id);await page.waitForTimeout(300);
  const boxes=await page.evaluate(()=>['[data-linux-input]','[data-linux-run]','[data-linux-back]','[data-linux-node]','[data-linux-output]','[data-ws-tab=incident]'].map(s=>{const e=document.querySelector(s),b=e.getBoundingClientRect();const x=b.x+b.width/2,y=b.y+b.height/2;return {selector:s,x:b.x,y:b.y,w:b.width,h:b.height,visible:b.y>=0&&b.bottom<=innerHeight&&b.x>=0&&b.right<=innerWidth,hit:e.contains(document.elementFromPoint(x,y))};}));
  assert.ok(boxes.every(b=>b.visible&&b.hit),JSON.stringify(boxes));const actualDpr=await page.evaluate(()=>devicePixelRatio);assert.equal(actualDpr,dpr);report.layouts.push({width,height,dpr:actualDpr,emulation:true,boxes});await shot(`p8-layout-${width}x${height}-${dpr}.png`);await cdp.detach();
}

// Expanded terminal: real mouse clicks and keys. Draft, history and engine records must survive every toggle.
const visibleHit=sels=>page.evaluate(list=>list.map(s=>{const e=document.querySelector(s);if(!e)return {selector:s,missing:true};const b=e.getBoundingClientRect();const x=b.x+b.width/2,y=b.y+b.height/2;
  return {selector:s,x:b.x,y:b.y,w:b.width,h:b.height,visible:b.width>0&&b.y>=0&&b.bottom<=innerHeight&&b.x>=0&&b.right<=innerWidth,hit:e.contains(document.elementFromPoint(x,y))};}),sels);
const termHeight=()=>page.locator('[data-linux-output]').evaluate(e=>e.getBoundingClientRect().height);
const expandedNow=()=>page.locator('#workstation').evaluate(e=>e.classList.contains('ws-expanded'));
async function expandLayout(width,height,dpr){
  await page.setViewportSize({width,height});const cdp=await ctx.newCDPSession(page);
  const emulate=async()=>{await cdp.send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:dpr,mobile:false});assert.equal(await page.evaluate(()=>devicePixelRatio),dpr,'emulated device pixel ratio');};
  await emulate();
  const rec=(await U.G(page)).incident.records[0];await linuxTab(rec.id);await page.waitForTimeout(300);
  if(await expandedNow()){await page.locator('[data-linux-expand]').click();await settle(page,100);}
  const input=page.locator('[data-linux-input]'),small=await termHeight(),n=(await U.G(page)).linux.observations.length;
  await input.click();await input.fill('');await input.pressSequentially('ip route',{delay:1});
  await page.locator('[data-linux-expand]').click();await settle(page,100);
  assert.equal(await expandedNow(),true,'expand button enlarges the monitor');assert.equal(await page.locator('[data-linux-expand]').getAttribute('aria-pressed'),'true');
  const big=await termHeight();assert.ok((big>=small*1.3&&big-small>=90)||(small>=120&&big>small),`terminal grows ${small}→${big} at ${width}x${height}@${dpr}`);console.log(`  expanded ${width}x${height}@${dpr}: terminal ${Math.round(small)}→${Math.round(big)}px`);
  assert.equal(await input.inputValue(),'ip route','draft kept when expanding');
  const summary=await page.locator('.linux-incident-summary').innerText();assert.ok(summary.includes(rec.id),'incident info visible while expanded');
  const boxes=await visibleHit(['[data-linux-input]','[data-linux-run]','[data-linux-back]','[data-linux-node]','[data-linux-incident]','[data-linux-output]','[data-linux-expand]','[data-ws-tab=incident]','.linux-incident-summary','#goal-title']);
  assert.ok(boxes.every(b=>b.visible&&b.hit),JSON.stringify(boxes));
  await input.press('Enter');await settle(page,150);const g=await U.G(page);assert.equal(g.linux.observations.length,n+1,'command runs in expanded view');assert.equal(g.linux.observations.at(-1).command_id,'ip_route');
  assert.equal(await expandedNow(),true,'stays expanded after a command');assert.equal(await input.evaluate(e=>e===document.activeElement),true,'focus back on input');
  await input.press('ArrowUp');assert.equal(await input.inputValue(),'ip route','history kept');await input.fill('');
  // Capture through the same CDP session: Playwright's page.screenshot resets the emulated device metrics.
  {const name=`p8-expanded-${width}x${height}-${dpr}.png`,{data}=await cdp.send('Page.captureScreenshot',{format:'png'});await writeFile(join(out,name),Buffer.from(data,'base64'));report.screenshots.push(name);}
  assert.equal(await page.evaluate(()=>devicePixelRatio),dpr,'ratio kept after the capture');
  await input.pressSequentially('ping -c 1 10.20.0.15',{delay:1});await page.keyboard.press('Escape');await settle(page,100);
  assert.equal(await expandedNow(),false,'Esc returns to normal size');assert.equal(await input.inputValue(),'ping -c 1 10.20.0.15','draft kept after Esc');
  assert.equal((await U.G(page)).linux.observations.length,n+1,'collapse does not run or drop records');assert.ok(await page.locator(`[data-linux-observation="${g.linux.observations.at(-1).seq}"]`).count(),'output kept after collapse');
  await page.locator('[data-linux-expand]').focus();await page.keyboard.press('Enter');await settle(page,100);assert.equal(await expandedNow(),true,'keyboard Enter on the toggle expands');
  await page.locator('[data-linux-back]').click();await settle(page,100);assert.equal(await expandedNow(),false,'incident tab uses the normal monitor size');
  assert.ok(await page.locator(`.inc-card, [data-incident-actions="${rec.id}"]`).first().isVisible(),'incident card visible after return');
  await U.tab(page,'linux');assert.equal(await expandedNow(),true,'Linux tab restores the expanded preference');assert.equal(await input.inputValue(),'ping -c 1 10.20.0.15','draft kept across tabs');
  await page.locator('[data-linux-expand]').click();await settle(page,100);assert.equal(await expandedNow(),false);await input.fill('');
  assert.equal(await page.evaluate(()=>devicePixelRatio),dpr,'ratio kept through Esc/tab/collapse steps');
  report.layouts.push({width,height,dpr:await page.evaluate(()=>devicePixelRatio),emulation:true,expanded:{collapsedTerminal:Math.round(small),expandedTerminal:Math.round(big),boxes}});await cdp.detach();
}
try{
  stack=await startStack({enginePort:8808,vitePort:5208});report.url=stack.url;
  browser=await chromium.launch({executablePath:CHROME,headless:false,args:['--window-size=1920,1080']});report.browserVersion=browser.version();await open();
  await check('menu separates regular Linux training and ten ungraded incident practices',async()=>{assert.ok(await page.locator('[data-new=linux]').isDisabled());assert.equal(await page.locator('[data-linux-practice] option').count(),10);await shot('p8-menu.png');});
  if(!dev){
    await check('prerequisite Chapter1 to Chapter5 graduation through real 3D UI, no seed',async()=>{
      await C.click(page,'[data-new=story]');await C.chapter1(page);await C.startNext(page,'2');await C.chapter2(page);await C.startNext(page,'3');await C.chapter3(page);await C.startNext(page,'3b');await C.chapter4(page);await C.startNext(page,'lab');await C.chapter5(page);assert.equal((await U.S(page)).screens.open,'graduation');await U.click(page,'#screen-dialog [data-next=menu]');
    });
    await check('five finite shifts: choice to assembly to typing and independent diagnosis, all ten causes',async()=>{await U.click(page,'[data-new=linux]');for(let n=1;n<=5;n++)await shift(n);assert.equal(seenTypes.size,10);assert.equal((await U.G(page)).global.result.linux.graduated,true);assert.equal((await U.G(page)).global.next,null);});
    await check('promotion survives engine process restart and resume',async()=>{await U.click(page,'#screen-dialog [data-next=stay]');await restart('graduation');assert.equal((await U.G(page)).global.result.linux.graduated,true);});
  }
  await check('keyboard typing, errors, Enter, history, max length and clipboard in terminal',async()=>{
    const rec=await practice('dns');await linuxTab(rec.id);const before=(await U.G(page)).linux.observations.length;
    await page.locator('[data-linux-input]').pressSequentially('sudo rm /data/work');await page.locator('[data-linux-input]').press('Enter');await settle(page);assert.equal((await U.G(page)).linux.observations.length,before);assert.match(await page.locator('[data-linux-output]').innerText(),/변경 명령/);
    await command(rec.id,'ping',{forceTyping:true});assert.equal(await page.locator('[data-linux-input]').evaluate(e=>e===document.activeElement),true,'command result restores keyboard focus to the terminal input');await page.locator('[data-linux-input]').press('ArrowUp');assert.equal(await page.locator('[data-linux-input]').inputValue(),'ping -c 3 10.20.0.15');
    await page.locator('[data-linux-input]').fill('x'.repeat(300));assert.equal((await page.locator('[data-linux-input]').inputValue()).length,240);await page.locator('[data-linux-input]').fill('');
    await U.click(page,'[data-linux-copy]');assert.match(await page.evaluate(()=>navigator.clipboard.readText()),/PING/);await shot('p8-keyboard.png');
  });
  await check('real click targets at 1366x768, 1920x1080 and 150 percent emulation',async()=>{await layout(1366,768,1);await layout(1920,1080,1);await layout(1280,720,1.5);await layout(911,512,1.5);});
  await check('wrong interpretation and wrong node cannot create fake success',async()=>{
    await page.setViewportSize({width:1920,height:1080});const rec=(await U.G(page)).incident.records[0];await linuxTab(rec.id);
    const choices=await page.locator('[data-linux-answer]').allTextContents();const wrong=choices.findIndex(x=>x.includes('DNS와 서비스도 정상'));await U.click(page,`[data-linux-answer="${wrong===0?'a':'b'}"]`);assert.equal((await U.G(page)).linux.interpretations.at(-1).correct,false);
    const n=(await U.G(page)).linux.observations.length;await select('[data-linux-node]','server-D');await page.locator('[data-linux-input]').fill('df -h');await page.locator('[data-linux-input]').press('Enter');await settle(page);assert.equal((await U.G(page)).linux.observations.length,n);assert.match(await page.locator('[data-linux-output]').innerText(),/permission/);assert.equal((await U.inc(page,rec.id)).cause,null);
  });
  await check('delayed command response keeps input and context locked until the result arrives',async()=>{
    const rec=(await U.G(page)).incident.records[0];await linuxTab(rec.id);await select('[data-linux-node]','noc');
    let delayed=false;const handler=async route=>{const body=route.request().postDataJSON();if(!delayed&&body?.type==='linux_command'){delayed=true;await new Promise(r=>setTimeout(r,1000));}await route.continue();};
    await page.route('**/api/games/*/actions',handler);await page.locator('[data-linux-input]').fill('ip route');await page.locator('[data-linux-input]').press('Enter');
    assert.equal(await page.locator('[data-linux-input]').isDisabled(),true);assert.equal(await page.locator('[data-linux-node]').isDisabled(),true);assert.equal(await page.locator('[data-linux-incident]').isDisabled(),true);
    await settle(page,150);assert.equal(delayed,true);assert.equal(await page.locator('[data-linux-input]').isDisabled(),false);assert.equal(await page.locator('[data-linux-input]').inputValue(),'');
    assert.equal((await U.G(page)).linux.observations.at(-1).command_id,'ip_route');await page.unroute('**/api/games/*/actions',handler);
  });
  await check('expanded terminal at 1366x768, 1920x1080 and 150 percent: mouse/keyboard toggle keeps draft, history and records',async()=>{
    await expandLayout(1366,768,1);await expandLayout(1920,1080,1);await expandLayout(1280,720,1.5);await expandLayout(911,512,1.5);await page.setViewportSize({width:1920,height:1080});
  });
  await check('all 28 catalog commands execute through actual controls in a virtual Kubernetes workload',async()=>{
    const rec=await practice('crashloop'),specs=(await U.G(page)).linux.commands;
    for(const spec of specs)await command(rec.id,spec.command_id);
    const rows=(await U.G(page)).linux.observations;assert.equal(new Set(rows.map(x=>x.command_id)).size,28);await shot('p8-all-commands.png');
  });
  await check('failed UPS practice retries into a new slot and preserves the source DB byte for byte',async()=>{
    const rec=await practice('ups');for(let i=0;i<15&&!(await U.G(page)).global.done;i++)await U.advance(page,10);
    const g=await U.G(page);assert.equal(g.global.result.cleared,false);assert.equal((await U.inc(page,rec.id)).state,'failed');await shot('p8-failed-practice.png');
    await U.click(page,'#screen-dialog [data-next=stay]');const source=g.id;const before=createHash('sha256').update(await readFile(join(stack.saveDir,`${source}.db`))).digest('hex');
    await U.tab(page,'result');await U.click(page,'[data-retry-shift]');const after=await U.G(page);assert.notEqual(after.id,source);assert.equal(after.linux.practice,'ups');
    assert.equal(createHash('sha256').update(await readFile(join(stack.saveDir,`${source}.db`))).digest('hex'),before);report.resumes.push({label:'retry source bytes preserved',source,newSlot:after.id});await U.talkThrough(page);
  });
  await check('repeat world/campus/NOC/hall visits retain WebGL resources and reduced motion',async()=>{
    for(let i=0;i<6;i++){for(const route of ['world','campus','hall','noc'])await U.places(page,route);const s=await U.S(page);report.performance.push({i,fps:s.stats.fps,p95:s.stats.p95FrameMs,geometries:s.renderer.geometries,textures:s.renderer.textures,heap:s.heap?.used});}
    const geo=report.performance.slice(1).map(x=>x.geometries),tex=report.performance.slice(1).map(x=>x.textures);assert.ok(Math.max(...geo)-Math.min(...geo)<=2);assert.ok(Math.max(...tex)-Math.min(...tex)<=2);assert.equal(await page.evaluate(()=>matchMedia('(prefers-reduced-motion: reduce)').matches),true);await shot('p8-performance.png');
  });
  await check('no page errors or renderer crashes',async()=>{assert.deepEqual(report.errors,[]);assert.deepEqual(report.consoleErrors.filter(x=>!/favicon|status of 4\d\d/.test(x)),[]);});
}catch(e){report.failure=e.stack;process.exitCode=1;}
finally{report.finishedAt=new Date().toISOString();report.summary={pass:report.checks.filter(x=>x.pass).length,total:report.checks.length};await writeFile(join(out,'phase8-qa.json'),JSON.stringify(report,null,2));console.log(`Phase8 QA ${report.summary.pass}/${report.summary.total}`);try{await browser?.close();}catch{}try{await stack?.stop();}catch{}}
