// Phase 9 supplementary browser QA (Issue #10 §6): the new Phase 9 screens at 1366x768 / 1920x1080 / 150 percent,
// keyboard-only free-shift setup, wrap-up double click, result shown once across reload and engine restart, a delayed
// reply interrupted by a page reload, honest senior failure -> new-slot retry (source bytes preserved) -> ending.
// Only real UI actions change games; window.worldQA and SQLite (read-only, OS temp saves) are checks.
import {chromium} from 'playwright-core';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {mkdir,readFile,writeFile} from 'node:fs/promises';
import {resolve,join} from 'node:path';
import {DatabaseSync} from 'node:sqlite';
import {startStack,CHROME,settle} from './qa-lib.mjs';
import * as U from './phase7-ui.mjs';
import * as C from './campaign-flows.mjs';
import {createFlows} from './phase9-flows.mjs';

const out=resolve(process.argv.find(x=>x.startsWith('--out='))?.slice(6)??'../../docs/3d-world-expansion/qa/phase9/ux-1');
await mkdir(out,{recursive:true});
const report={issue:10,kind:'phase9-ux',checks:[],errors:[],consoleErrors:[],commands:[],actions:[],shifts:[],layouts:[],resumes:[],notes:[],startedAt:new Date().toISOString()};
let stack,browser,page,ctx;
const F=createFlows(()=>page,report);
const shot=async name=>page.screenshot({path:join(out,name)});
async function check(name,fn){const t=Date.now();try{await fn();report.checks.push({name,pass:true,ms:Date.now()-t});console.log(`PASS ${name}`);}catch(e){await shot(`FAIL-${report.checks.length}.png`).catch(()=>{});report.checks.push({name,pass:false,error:e.stack});console.log(`FAIL ${name}: ${e.message}`);throw e;}finally{await writeFile(join(out,'phase9-ux-qa.json'),JSON.stringify(report,null,2));}}
async function open(){ctx=await browser.newContext({viewport:{width:1920,height:1080},reducedMotion:'reduce'});await ctx.addInitScript(()=>localStorage.setItem('srs3d.opening.seen.v1','1'));page=await ctx.newPage();page.on('pageerror',e=>report.errors.push(e.message));page.on('console',m=>{if(m.type()==='error')report.consoleErrors.push(m.text());});page.on('dialog',d=>d.accept());await page.goto(stack.url);await page.waitForFunction(()=>!!window.worldQA);await page.waitForTimeout(1000);}
async function menu(){await U.drain(page);if(await page.locator('#screen-dialog[open]').count()){await U.click(page,'#screen-dialog [data-next=menu]');await settle(page);}if(!await page.locator('#menu:not([hidden])').count())await U.click(page,'#menu-open');await page.waitForSelector('[data-new=global_free]');}
function payload(id){const db=new DatabaseSync(join(stack.saveDir,id+'.db'),{readOnly:true});try{return JSON.parse(db.prepare('SELECT payload FROM simulation_state WHERE id=1').get().payload);}finally{db.close();}}
const bytes=async id=>createHash('sha256').update(await readFile(join(stack.saveDir,`${id}.db`))).digest('hex');
const SIZES=[[1366,768,1],[1920,1080,1],[1280,720,1.5],[911,512,1.5]];
let cdp=null;
async function emulate(width,height,dpr){await page.setViewportSize({width,height});cdp??=await ctx.newCDPSession(page);await cdp.send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:dpr,mobile:false});await page.waitForTimeout(300);assert.equal(await page.evaluate(()=>devicePixelRatio),dpr,'emulated device pixel ratio');}
async function reset(){await emulate(1920,1080,1);}
// Measure a control before any scrolling; if it is off-screen, scroll its own container and measure again.
// `pageScroll` reports whether the document itself had to scroll (only panel-internal scrolling is acceptable).
async function measure(sel){
  const m=()=>page.evaluate(s=>{const e=document.querySelector(s);if(!e)return {selector:s,missing:true};const b=e.getBoundingClientRect(),x=b.x+b.width/2,y=b.y+b.height/2;
    return {selector:s,x:Math.round(b.x),y:Math.round(b.y),w:Math.round(b.width),h:Math.round(b.height),visible:b.width>0&&b.height>0&&b.y>=0&&b.bottom<=innerHeight&&b.x>=0&&b.right<=innerWidth,hit:e.contains(document.elementFromPoint(x,y)),disabled:!!e.disabled};},sel);
  const first=await m();if(first.missing||first.visible&&first.hit)return {...first,scrolled:false,pageScroll:false};
  await page.locator(sel).first().scrollIntoViewIfNeeded();await page.waitForTimeout(150);const second=await m();
  const pageScroll=await page.evaluate(()=>scrollX!==0||scrollY!==0);return {...second,scrolled:true,pageScroll};
}
async function layoutCheck(label,sels,{strict=[]}={}){
  for(const [w,h,dpr]of SIZES){await emulate(w,h,dpr);if(label.startsWith('hud'))await U.incidentTab(page,report.hudIncident);const boxes=[];for(const s of sels)boxes.push(await measure(s));
    // CDP capture: a Playwright screenshot would reset the emulated device pixel ratio (Phase 8 final-5 finding).
    assert.equal(await page.evaluate(()=>devicePixelRatio),dpr,'DPR kept while measuring');
    report.layouts.push({label,width:w,height:h,dpr,boxes});{const {data}=await cdp.send('Page.captureScreenshot',{format:'png'});await writeFile(join(out,`p9-${label}-${w}x${h}-${dpr}.png`),Buffer.from(data,'base64'));}
    for(const b of boxes){assert.ok(!b.missing,`${label} ${w}x${h}@${dpr} ${b.selector} missing`);assert.ok(b.visible&&b.hit,`${label} ${w}x${h}@${dpr} ${JSON.stringify(b)}`);assert.equal(b.pageScroll,false,`${label} ${b.selector} scrolled the page`);
      if(strict.includes(b.selector))assert.equal(b.scrolled,false,`${label} ${w}x${h}@${dpr} ${b.selector} needs scrolling`);}
    if(cdp){await cdp.detach();cdp=null;}
  }
  await reset();
}
async function restart(label){const before=await U.G(page);await stack.restartEngine();await page.reload();await page.waitForFunction(()=>!!window.worldQA?.snapshot().game);await settle(page);const after=await U.G(page);for(const k of ['clock','requests','servers','global','incident','linux','senior','assessment'])assert.deepEqual(after[k],before[k],label+' '+k);report.resumes.push({label,id:after.id,minute:after.clock.minute});}
const screenOpen=async()=>(await U.S(page)).screens.open;

try{
  stack=await startStack({enginePort:8791,vitePort:5191,log:s=>console.log(s.trim())});browser=await chromium.launch({executablePath:CHROME,headless:false,args:['--no-first-run']});report.browserVersion=browser.version();await open();

  await check('menu: career map, senior lock and free seed/difficulty/start reachable at 1366x768, 1920x1080 and 150 percent',async()=>{
    await menu();await layoutCheck('menu',['[data-career]','[data-new=senior]','[data-free-seed]','[data-free-difficulty]','[data-new=global_free]']);
    assert.equal(await page.locator('[data-new=senior]').isDisabled(),true);assert.match(await page.locator('[data-career]').innerText(),/신입/);
  });

  await check('keyboard only: Tab to seed, type it, arrow-select difficulty, Enter starts that free shift',async()=>{
    await menu();await page.evaluate(()=>{document.activeElement?.blur();scrollTo(0,0);});
    let found=false;for(let i=0;i<120&&!found;i++){await page.keyboard.press('Tab');found=await page.evaluate(()=>document.activeElement?.matches('[data-free-seed]'));}
    assert.ok(found,'Tab reaches the seed field');await page.keyboard.type('91');
    await page.keyboard.press('Tab');assert.ok(await page.evaluate(()=>document.activeElement?.matches('[data-free-difficulty]')),'Tab reaches difficulty');
    await page.keyboard.press('ArrowDown');assert.equal(await page.locator('[data-free-difficulty]').inputValue(),'challenge');
    await page.keyboard.press('Tab');assert.ok(await page.evaluate(()=>document.activeElement?.matches('[data-new=global_free]')),'Tab reaches the start button');
    await page.keyboard.press('Enter');await page.waitForFunction(()=>window.worldQA.snapshot().game?.global?.kind==='free');await settle(page);
    const g=await U.G(page);assert.equal(g.global.seed,91);assert.equal(payload(g.id).free_incidents.difficulty,'challenge');report.freeId=g.id;
  });

  await check('free shift HUD: wrap-up, time and incident actions reachable at all four sizes without page scroll',async()=>{
    await U.talkThrough(page);let id=null;
    for(let n=0;n<14&&!id;n++){await F.startAvailable();const r=(await U.G(page)).incident.records.find(x=>x.state==='alert');if(r)id=r.id;else await U.advance(page,10);}
    assert.ok(id,'seed 91 challenge produced an incident through real time steps');report.hudIncident=id;
    await layoutCheck('hud',['[data-free-end]','[data-advance="10"]','[data-ws-tab=incident]',`[data-incident-ack="${id}"]`],{strict:['[data-free-end]','[data-advance="10"]']});
  });

  await check('delayed reply interrupted by reload: the 10 minutes and the incident draw happen exactly once',async()=>{
    const g0=await U.G(page),p0=payload(g0.id);let delayed=false,fetched=false,release;const held=new Promise(r=>release=r);
    // The engine handles the request (route.fetch), but the reply is held back until after the page has reloaded.
    const handler=async route=>{const body=route.request().postDataJSON();if(!delayed&&body?.type==='advance_time'){delayed=true;const res=await route.fetch();fetched=true;await held;try{await route.fulfill({response:res});}catch{}return;}await route.continue();};
    await page.route('**/api/games/*/actions',handler);await page.locator('[data-advance="10"]').click();
    for(let i=0;i<100&&!fetched;i++)await page.waitForTimeout(100);
    assert.equal(fetched,true,'engine handled the held request');await page.reload();release();await page.waitForFunction(()=>!!window.worldQA?.snapshot().game);await settle(page);await page.unroute('**/api/games/*/actions',handler);
    const g1=await U.G(page),p1=payload(g1.id);assert.equal(g1.id,g0.id);assert.equal(g1.clock.minute,g0.clock.minute+10,'advanced once');
    assert.equal(p1.free_incidents.last,g0.clock.minute+10,'the new 10-minute boundary was handled');assert.ok(p1.free_incidents.cursor-p0.free_incidents.cursor<=1,'at most one draw');const ids=g1.incident.records.map(r=>r.id);assert.equal(new Set(ids).size,ids.length,'no duplicate incident');
    assert.ok(p1.free_incidents.events.length>=p0.free_incidents.events.length);assert.ok(p1.free_incidents.events.length-p0.free_incidents.events.length<=1,'at most one draw for one boundary');
    report.notes.push({delayedReload:{before:g0.clock.minute,after:g1.clock.minute,events:[p0.free_incidents.events.length,p1.free_incidents.events.length]}});
  });

  await check('wrap-up double click, result shown once, not again after reload or engine restart, result tab reopens it',async()=>{
    await U.incidentTab(page);await page.locator('[data-free-end]').dblclick();await settle(page,300);let g=await U.G(page);assert.equal(g.global.closing,true);
    // end_free_shift is idempotent in the engine: a second click while closing changes nothing.
    const ends=(await page.evaluate(()=>window.worldQA.actions())).filter(a=>a.action.type==='end_free_shift');report.notes.push({wrapUpClicks:ends.length});assert.ok(ends.length>=1);
    assert.deepEqual(payload(g.id).free_incidents.closing,true);
    assert.equal(await page.locator('[data-free-end]').count(),0,'the wrap-up control disappears once closing');
    for(let i=0;i<50&&!g.global.done;i++){await F.startAvailable();await F.handleOpen();g=await U.G(page);if(!g.global.done){await U.advance(page,10);g=await U.G(page);}}
    assert.equal(g.global.done,true);await page.waitForFunction(()=>window.worldQA.snapshot().screens.open==='shift-free');await shot('p9-free-result.png');
    await layoutCheck('free-result',['#screen-dialog [data-next=global-free]','#screen-dialog [data-next=menu]']);
    await U.click(page,'#screen-dialog [data-next=stay]');await settle(page,300);assert.equal(await screenOpen(),null);
    await page.reload();await page.waitForFunction(()=>!!window.worldQA?.snapshot().game);await settle(page,600);assert.equal(await screenOpen(),null,'not shown again after reload');
    await restart('free result seen');await settle(page,600);assert.equal(await screenOpen(),null,'not shown again after engine restart');
    await U.tab(page,'result');await U.click(page,'[data-free-result]');assert.equal(await screenOpen(),'shift-free','result tab reopens it');
    assert.deepEqual(payload(g.id).global.result,g.global.result);
  });

  await check('prerequisites through real UI: chapters 1 to 5, global 3, incident 3, Linux 5',async()=>{
    await menu();await U.click(page,'[data-new=story]');await page.waitForTimeout(500);await C.chapter1(page);for(const [key,fn]of [['2',C.chapter2],['3',C.chapter3],['3b',C.chapter4],['lab',C.chapter5]]){await C.startNext(page,key);await fn(page);}
    await menu();await U.click(page,'[data-new=global]');await page.waitForTimeout(500);for(let n=1;n<=3;n++){await F.globalShift(n);if(n<3)await U.click(page,'[data-next=next-shift]');}
    await menu();await U.click(page,'[data-new=incident]');await page.waitForTimeout(500);for(let n=1;n<=3;n++){await F.workShift();if(n<3)await U.click(page,'[data-next=next-incident]');}
    await menu();await U.click(page,'[data-new=linux]');await page.waitForTimeout(500);for(let n=1;n<=5;n++){await F.workShift();if(n<5)await U.click(page,'[data-next=next-linux]');}
    await menu();assert.equal(await page.locator('[data-new=senior]').isDisabled(),false);
  });

  await check('senior evaluation fails honestly when incidents are ignored; retry opens a new slot and preserves the source bytes',async()=>{
    await U.click(page,'[data-new=senior]');await page.waitForTimeout(500);await U.talkThrough(page);let g=await U.G(page);
    for(let i=0;i<60&&!g.global.done;i++){await F.startAvailable();g=await U.G(page);if(g.global.done)break;assert.ok(g.canAdvance,`not done but time cannot advance at ${g.clock.label}`);await U.advance(page,10);g=await U.G(page);}
    assert.equal(g.global.done,true,'an ignored senior shift still ends');assert.equal(g.global.result.cleared,false);assert.equal(g.senior.ending,false);
    report.notes.push({seniorFailure:{operations:g.global.result.assessment.operations.score,learning:g.global.result.assessment.learning.score,rows:g.global.result.rows.map(r=>r.outcome),incidents:g.global.result.incidents.map(r=>r.outcome)}});
    await page.waitForSelector('#screen-dialog[open] [data-next=retry-incident]');await shot('p9-senior-failed.png');
    await layoutCheck('senior-failed',['#screen-dialog [data-next=retry-incident]','#screen-dialog [data-next=menu]']);
    const source=g.id,before=await bytes(source);await U.click(page,'#screen-dialog [data-next=retry-incident]');await page.waitForTimeout(500);
    const n=await U.G(page);assert.notEqual(n.id,source);assert.equal(n.mode,'senior');assert.equal(n.global.shift,1);assert.equal(await bytes(source),before,'source save unchanged byte for byte');
    report.resumes.push({label:'senior retry source bytes preserved',source,newSlot:n.id});
  });

  await check('senior retry slot: two shifts cleared, ending and free branch reachable at all sizes, career map shows the role',async()=>{
    await F.workShift();await restart('senior retry first result');await U.click(page,'#screen-dialog [data-next=next-linux]');await F.workShift();
    const g=await U.G(page);assert.equal(g.senior.ending,true);assert.deepEqual(payload(g.id).global.result,g.global.result);
    await page.waitForSelector('[data-ending]');await layoutCheck('ending',['#screen-dialog [data-ending]','#screen-dialog [data-next=global-free]','#screen-dialog [data-next=menu]']);
    await U.click(page,'#screen-dialog [data-next=menu]');await page.waitForSelector('[data-career]');const text=await page.locator('[data-career]').innerText();report.notes.push({careerAfterEnding:text});
    assert.match(text,/선임 엔지니어/);assert.match(await page.locator('[data-new=senior]').innerText(),/다시 도전/);
  });

  await check('no page errors or renderer crashes',async()=>{assert.deepEqual(report.errors,[]);assert.deepEqual(report.consoleErrors,[]);});
}catch(e){report.failure=e.stack;console.error(e.stack);process.exitCode=1;}
finally{report.finishedAt=new Date().toISOString();report.summary={pass:report.checks.filter(c=>c.pass).length,total:report.checks.length};await writeFile(join(out,'phase9-ux-qa.json'),JSON.stringify(report,null,2));await ctx?.close();await browser?.close();await stack?.stop();}
