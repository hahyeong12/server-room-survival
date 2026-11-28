// Phase 10 browser QA: the new operating rules through the real UI. Headless by default (pass --headed to watch);
// installed Chrome with a throw-away profile, its own ports (8793/5193) and an OS temp save folder. Only real clicks,
// selects and keys change games; window.worldQA and SQLite (read-only) are checks. User Chrome/saves are never touched.
//   1 shared UPS incident (seed 4 challenge): two customers, one notice for both, forecast shows the battery risk
//   2 forecast of quick workaround vs root fix equals the real completion; engine state unchanged by the forecast
//   3 responsible handoff: ends the shift, never a resolution, fixed across engine restart, retry keeps source bytes
//   4 neglect handoff (no scope, no notice) is recorded as neglect with the reason
//   5 layouts of the forecast table / handoff panel / goal shortcut at 1366x768, 1920x1080, 1280x720@1.5, 911x512@1.5
//   6 repeated movement through every space: WebGL resources and JS heap stay flat
import {chromium} from 'playwright-core';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {mkdir,readFile,writeFile} from 'node:fs/promises';
import {resolve,join} from 'node:path';
import {DatabaseSync} from 'node:sqlite';
import {startStack,CHROME,settle} from './qa-lib.mjs';
import * as U from './phase7-ui.mjs';
import {createFlows} from './phase9-flows.mjs';

const out=resolve(process.argv.find(x=>x.startsWith('--out='))?.slice(6)??'../../docs/3d-world-expansion/qa/phase10/qa-1');
const headed=process.argv.includes('--headed');
await mkdir(out,{recursive:true});
const report={phase:10,kind:'phase10',headless:!headed,checks:[],errors:[],consoleErrors:[],commands:[],actions:[],shifts:[],layouts:[],resources:[],forecasts:[],notes:[],startedAt:new Date().toISOString()};
let stack,browser,page,ctx,cdp=null;
const F=createFlows(()=>page,report);
const shot=async name=>{const {data}=await (cdp??=await ctx.newCDPSession(page)).send('Page.captureScreenshot',{format:'png'});await writeFile(join(out,name),Buffer.from(data,'base64'));};
async function check(name,fn){const t=Date.now();try{await fn();report.checks.push({name,pass:true,ms:Date.now()-t});console.log(`PASS ${name}`);}catch(e){await shot(`FAIL-${report.checks.length}.png`).catch(()=>{});report.checks.push({name,pass:false,error:e.stack});console.log(`FAIL ${name}: ${e.message}`);throw e;}finally{await writeFile(join(out,'phase10-qa.json'),JSON.stringify(report,null,2));}}
async function open(){ctx=await browser.newContext({viewport:{width:1920,height:1080},reducedMotion:'reduce'});await ctx.addInitScript(()=>localStorage.setItem('srs3d.opening.seen.v1','1'));page=await ctx.newPage();cdp=null;page.on('pageerror',e=>report.errors.push(e.message));page.on('console',m=>{if(m.type()==='error')report.consoleErrors.push(m.text());});page.on('dialog',d=>d.accept());await page.goto(stack.url);await page.waitForFunction(()=>!!window.worldQA);await page.waitForTimeout(1000);}
async function menu(){await U.drain(page);if(await page.locator('#screen-dialog[open]').count()){await U.click(page,'#screen-dialog [data-next=menu]');await settle(page);}if(!await page.locator('#menu:not([hidden])').count())await U.click(page,'#menu-open');await page.waitForSelector('[data-new=global_free]');}
async function fresh(mode,options){await menu();if(options?.seed!==undefined){await page.locator('[data-free-seed]').fill(String(options.seed));await page.selectOption('[data-free-difficulty]',options.difficulty);}if(options?.practice){await page.selectOption('[data-incident-practice]',options.practice);}await U.click(page,`[data-new=${mode}]`);await page.waitForTimeout(600);}
function payload(id){const db=new DatabaseSync(join(stack.saveDir,id+'.db'),{readOnly:true});try{return JSON.parse(db.prepare('SELECT payload FROM simulation_state WHERE id=1').get().payload);}finally{db.close();}}
const bytes=async id=>createHash('sha256').update(await readFile(join(stack.saveDir,`${id}.db`))).digest('hex');
const SIZES=[[1366,768,1],[1920,1080,1],[1280,720,1.5],[911,512,1.5]];
async function emulate(width,height,dpr){await page.setViewportSize({width,height});cdp??=await ctx.newCDPSession(page);await cdp.send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:dpr,mobile:false});await page.waitForTimeout(300);assert.equal(await page.evaluate(()=>devicePixelRatio),dpr);}
async function measure(sel){
  const m=()=>page.evaluate(s=>{const e=document.querySelector(s);if(!e)return {selector:s,missing:true};const b=e.getBoundingClientRect(),x=b.x+Math.min(b.width/2,40),y=b.y+Math.min(b.height/2,12);
    return {selector:s,x:Math.round(b.x),y:Math.round(b.y),w:Math.round(b.width),h:Math.round(b.height),visible:b.width>0&&b.height>0&&b.y>=0&&b.y<innerHeight&&b.x>=0&&b.x<innerWidth,hit:e.contains(document.elementFromPoint(x,y)),disabled:!!e.disabled};},sel);
  const first=await m();if(first.missing||first.visible&&first.hit)return {...first,scrolled:false,pageScroll:false};
  await page.locator(sel).first().scrollIntoViewIfNeeded();await page.waitForTimeout(150);const second=await m();
  return {...second,scrolled:true,pageScroll:await page.evaluate(()=>scrollX!==0||scrollY!==0)};
}
async function layoutCheck(label,sels,{prepare=async()=>{}}={}){
  for(const [w,h,dpr]of SIZES){await emulate(w,h,dpr);await prepare();const boxes=[];for(const s of sels)boxes.push(await measure(s));
    report.layouts.push({label,width:w,height:h,dpr,boxes});await shot(`p10-${label}-${w}x${h}-${dpr}.png`);
    for(const b of boxes){assert.ok(!b.missing,`${label} ${w}x${h}@${dpr} ${b.selector} missing`);assert.ok(b.visible&&b.hit,`${label} ${w}x${h}@${dpr} ${JSON.stringify(b)}`);assert.equal(b.pageScroll,false,`${label} ${b.selector} scrolled the page`);}
  }
  await emulate(1920,1080,1);
}
async function restart(label){const before=await U.G(page);await stack.restartEngine();await page.reload();await page.waitForFunction(()=>!!window.worldQA?.snapshot().game);await settle(page);const after=await U.G(page);for(const k of ['clock','requests','servers','global','incident'])assert.deepEqual(after[k],before[k],label+' '+k);}
async function untilAlert(n=40){for(let i=0;i<n;i++){await F.startAvailable();const g=await U.G(page);const a=g.incident.records.find(r=>r.state==='alert');if(a)return a;await U.advance(page,10);}throw new Error('no alert');}
const engineState=g=>JSON.stringify([g.clock,g.datacenter,g.servers,g.requests.map(r=>[r.id,r.progress,r.stage,r.status]),g.incident.records.map(r=>[r.id,r.state,r.actions.length,r.evidence.length])]);
async function forecast(id){await U.incidentTab(page,id);const before=engineState(await U.G(page));await U.click(page,`[data-forecast-run="${id}"]`);await page.waitForSelector(`[data-forecast="${id}"] table`);
  assert.equal(engineState(await U.G(page)),before,'forecast changes no engine state');
  const rows=await page.$$eval(`[data-forecast="${id}"] tr[data-forecast-option]`,trs=>trs.map(tr=>({option:tr.dataset.forecastOption,text:tr.innerText,jobs:[...tr.querySelectorAll('[data-risk]')].map(j=>({risk:j.dataset.risk,text:j.innerText}))})));
  report.forecasts.push({id,rows});return rows;}
const finishOf=text=>text.match(/완료 (\d\d:\d\d)/)?.[1]??null;

try{
  stack=await startStack({enginePort:8793,vitePort:5193,log:()=>{}});
  browser=await chromium.launch({executablePath:CHROME,headless:!headed,args:['--no-first-run','--use-angle=d3d11','--enable-gpu','--ignore-gpu-blocklist']});
  report.browserVersion=browser.version();await open();

  await check('shared UPS incident: both customers in scope, one notice reaches both, forecast shows the battery risk, both protected and reported',async()=>{
    await fresh('global_free',{seed:4,difficulty:'challenge'});await U.talkThrough(page);
    const a=await untilAlert();const id=a.id;await U.ack(page,id);let rec=await U.inc(page,id);
    assert.equal(rec.scope.jobs.length,2,'two jobs on the same UPS feed');assert.equal(rec.customers.length,2);
    assert.ok(rec.customers.every(c=>!c.notified.length));
    await U.notify(page,id);rec=await U.inc(page,id);assert.ok(rec.customers.every(c=>c.notified.length===1),JSON.stringify(rec.customers));
    const line=await page.locator(`.inc-card[data-incident="${id}"] .inc-status`).innerText();assert.match(line,/영향 고객 안내/);assert.equal((line.match(/✓/g)||[]).length,2,line);
    await U.observe(page,id,'ups');assert.equal((await U.hypothesis(page,id,'ups')).verdict,'confirmed');
    const rows=await forecast(id);const root=rows.find(r=>r.option==='escalate_facility');assert.ok(root,'facility repair is a recovery path');
    assert.equal(root.jobs.length,2);assert.ok(root.jobs.every(j=>j.risk==='fail'),'battery runs out before the 30-minute repair for every affected job: '+JSON.stringify(root.jobs));
    await layoutCheck('forecast',[`[data-forecast="${id}"] table`,`[data-forecast-run="${id}"]`],{prepare:()=>U.incidentTab(page,id)});
    for(const j of rec.scope.jobs)await U.act(page,id,'planned_pause',j.rid);
    assert.notEqual((await U.act(page,id,'escalate_facility')).result,'refused');
    for(let i=0;i<8&&(await U.inc(page,id)).state!=='monitoring';i++)await U.advance(page,10);
    await U.advance(page,10);rec=await U.inc(page,id);
    if(!rec.evidence.some(e=>e.probe==='ups'&&e.minute===(await U.G(page)).clock.minute))await U.observe(page,id,'ups');
    assert.equal((await U.verify(page,id)).state,'verified');assert.equal((await U.report(page,id)).state,'closed');
    const g=await U.G(page);for(const j of rec.scope.jobs)assert.notEqual(g.requests.find(r=>r.id===j.rid).stage,'failed','paused jobs survived');
    rec=await U.inc(page,id);assert.ok(rec.customers.every(c=>c.beforeRecovery),'every affected customer told before recovery');
    await shot('p10-shared-ups-closed.png');report.notes.push({sharedIncident:id,customers:rec.customers});
  });

  await check('forecast: quick workaround vs root fix shown per job; the chosen path finishes at the forecast time',async()=>{
    await fresh('incident_practice',{practice:'dns'});await U.talkThrough(page);const a=await untilAlert();const id=a.id;
    await U.ack(page,id);for(const p of ['ping','dns'])await U.observe(page,id,p);assert.equal((await U.hypothesis(page,id,'dns')).verdict,'confirmed');await U.notify(page,id);
    const rows=await forecast(id);assert.deepEqual(rows.map(r=>r.option),['none','dns_failover','escalate_network']);
    assert.equal(rows[0].jobs[0].risk,'stuck','doing nothing never ends a blocking incident');
    const quick=finishOf(rows[1].jobs[0].text),root=finishOf(rows[2].jobs[0].text);assert.ok(quick&&root,'both paths finish within the forecast');
    // double click on the forecast is harmless (read-only)
    await page.locator(`[data-forecast-run="${id}"]`).dblclick();await settle(page,300);
    await U.act(page,id,'dns_failover');const rid=(await U.inc(page,id)).rid;
    for(let i=0;i<40&&(await U.G(page)).requests.find(r=>r.id===rid).stage!=='done';i++){await F.handleOpen();if((await U.G(page)).requests.find(r=>r.id===rid).stage==='done')break;await U.advance(page,10);}
    const done=(await U.G(page)).requests.find(r=>r.id===rid);assert.equal(done.terms.completed,quick,'real completion = forecast');
    report.notes.push({forecastQuick:quick,forecastRoot:root,completed:done.terms.completed});
  });

  await check('responsible handoff: ends the shift, not a resolution, fixed after engine restart; retry keeps the source bytes',async()=>{
    await fresh('incident_practice',{practice:'storage_full'});await U.talkThrough(page);const a=await untilAlert();const id=a.id;
    await U.ack(page,id);await U.notify(page,id);await U.drain(page);
    await page.waitForSelector('[data-handoff-shortcut]');
    await layoutCheck('goal-shortcut',['[data-handoff-shortcut]','[data-advance="10"]']);
    await U.click(page,'[data-handoff-shortcut]');await page.waitForSelector('[data-handoff-confirm]');
    assert.equal(await page.locator('[data-handoff-class=handover]').count(),1);
    await layoutCheck('handoff',['[data-handoff-confirm]','[data-handoff-cancel]'],{prepare:async()=>{await U.incidentTab(page);if(!await page.locator('[data-handoff-confirm]').count())await U.click(page,'[data-handoff-open]');}});
    // double click on the confirm: one result, the second click is refused by the engine
    await page.locator('[data-handoff-confirm]').dblclick();await settle(page,400);
    let g=await U.G(page);assert.equal(g.global.done,true);assert.equal(g.global.result.cleared,false);assert.equal(g.global.result.resolved,0);
    assert.equal(g.global.result.handoff.handedOver,1);assert.equal(g.canAdvance,false);
    assert.notEqual((await U.inc(page,id)).state,'closed','the incident stays unresolved, not hidden');
    assert.equal(payload(g.id).global.result.handoff.handedOver,1);
    const events=JSON.stringify(payload(g.id));assert.ok(events.includes('다음 교대에 인계'),'handoff logged in the incident timeline');
    await shot('p10-handoff-result.png');
    await restart('after handoff');g=await U.G(page);assert.equal(g.incident.handedOff,true);assert.equal(g.canAdvance,false);
    await U.drain(page);if(await page.locator('#screen-dialog[open]').count()){await U.click(page,'#screen-dialog[open] [data-next=stay]').catch(()=>{});await settle(page);}
    const src=g.id,h0=await bytes(src);await U.incidentTab(page);await U.click(page,'[data-ws-tab=inbox]');
    await page.waitForSelector('[data-retry-shift]');await U.click(page,'[data-retry-shift]');await page.waitForTimeout(800);
    g=await U.G(page);assert.notEqual(g.id,src,'retry is a new slot');assert.equal(await bytes(src),h0,'source save bytes unchanged by retry');
  });

  await check('neglect handoff: no scope check and no customer notice is recorded as neglect with the reason',async()=>{
    await fresh('incident_practice',{practice:'crashloop'});await U.talkThrough(page);await untilAlert();
    await U.click(page,'[data-handoff-shortcut]');await page.waitForSelector('[data-handoff-class=neglect]');
    assert.match(await page.locator('[data-handoff-class=neglect]').innerText(),/범위 확인 안 함/);
    await U.click(page,'[data-handoff-confirm]');const g=await U.G(page);
    assert.equal(g.global.result.handoff.neglected,1);assert.ok(g.global.result.feedback.some(l=>l.includes('방치')));
    assert.deepEqual(g.assessment.neglected,g.global.result.handoff.incidents.map(x=>x.id));
    await shot('p10-neglect-result.png');
  });

  await check('repeated movement through every space keeps WebGL resources and the JS heap flat',async()=>{
    await U.drain(page);if(await page.locator('#screen-dialog[open]').count())await U.click(page,'#screen-dialog[open] [data-next=stay]').catch(()=>{});
    const sample=async()=>{await page.waitForTimeout(500);const s=await U.S(page);return {geometries:s.renderer.geometries,textures:s.renderer.textures,heap:s.heap?.used??null,fps:+s.stats.fps.toFixed(1)};};
    const cycle=async()=>{for(const r of ['world','campus','noc','hall'])await U.places(page,r);return sample();};
    const first=await cycle();for(let i=0;i<8;i++)report.resources.push(await cycle());const last=await cycle();report.resources.unshift(first);report.resources.push(last);
    assert.ok(last.geometries<=first.geometries+5&&last.textures<=first.textures+2,`no WebGL growth: ${JSON.stringify([first,last])}`);
    if(first.heap&&last.heap)assert.ok(last.heap<first.heap*1.5+20*1048576,`heap flat: ${first.heap} -> ${last.heap}`);
  });

  await check('no page or console errors',async()=>{assert.deepEqual(report.errors,[]);assert.deepEqual(report.consoleErrors,[]);});
}finally{
  report.finishedAt=new Date().toISOString();await writeFile(join(out,'phase10-qa.json'),JSON.stringify(report,null,2));
  await browser?.close().catch(()=>{});await stack?.stop();
  const passed=report.checks.filter(c=>c.pass).length;console.log(`phase10 QA: ${passed}/${report.checks.length} passed`);
}
