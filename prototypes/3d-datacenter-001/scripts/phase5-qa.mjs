// Issue #6 (Phase 5) browser QA: the regular story chapters 1 -> 5 played through the real 3D UI in Chrome
// (Playwright CDP mouse/keyboard on the canvas, monitor tabs, rack card, time buttons, senior dialogue, result
// screens, Engineering Lab terminal). Isolated stack: Python engine on a temporary save folder + its own Vite.
// The API is used only to READ state before/after (window.worldQA and file hashes); no state is set directly.
// After every chapter clear the engine PROCESS is restarted and the save is resumed from the menu.
// Failure / retry checks start from the chapter-start points through the menu's chapter select (a new slot).
import {chromium} from 'playwright-core';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {mkdir,writeFile,readFile,readdir} from 'node:fs/promises';
import {resolve,join} from 'node:path';
import {startStack,settle,CHROME,tempSaveDir,python} from './qa-lib.mjs';
import {execFileSync} from 'node:child_process';
import {DatabaseSync} from 'node:sqlite';
import {S,story,req,click,places,canvasClick,toastText,screenOpen,readTalk,readAllTalk,closeScreen,drainScreens,tab,readRequest,choosePlan,startInHall,job,advance,advanceUntil,diagnose} from './phase5-ui.mjs';

const out=resolve(process.argv.find(x=>x.startsWith('--out='))?.slice(6)||'../../docs/3d-world-expansion/qa/phase5');   // Phase 7: --out= keeps a regression run apartawait mkdir(out,{recursive:true});
const only=process.argv.find(x=>x.startsWith('--only='))?.slice(7);
const report={issue:6,mode:'Chrome headed / Playwright CDP / isolated contexts / isolated engine+saves (temporary)',checks:[],errors:[],consoleErrors:[],screenshots:[],chapters:[],resumes:[],retries:[],performance:[],resources:[],startedAt:new Date().toISOString()};
let browser,stack,campaignId=null,currentPage=null;
async function check(name,fn){if(only&&!name.includes(only))return;const t=Date.now();try{await fn();report.checks.push({name,pass:true,ms:Date.now()-t});console.log(`PASS ${name}`);}catch(e){
  const shotName=`fail-${report.checks.length+1}.png`;let state=null;try{await currentPage?.screenshot({path:resolve(out,shotName)});const s=await currentPage.evaluate(()=>worldQA.snapshot());state={step:s.game?.story?.uiStep,dialogue:s.game?.story?.dialogue,screen:s.screens.open,clock:s.game?.clock?.label,route:s.state.navigation.route,actions:await currentPage.evaluate(()=>worldQA.actions().slice(-8))};}catch{}
  report.checks.push({name,pass:false,error:e.stack?.split('\n').slice(0,4).join(' | '),failShot:shotName,state});console.log(`FAIL ${name}: ${e.message.split('\n')[0]}`);}}
async function open({width=1920,height=1080,dpr=1}={}){
  const ctx=await browser.newContext({viewport:{width,height},deviceScaleFactor:dpr});
  await ctx.addInitScript(()=>{try{localStorage.setItem('srs3d.opening.seen.v1','1');}catch{}});
  const page=await ctx.newPage();currentPage=page;page.on('pageerror',e=>report.errors.push(e.message));page.on('console',m=>{if(m.type()==='error')report.consoleErrors.push(m.text());});
  page.on('dialog',d=>d.accept());
  await page.goto(stack.url,{waitUntil:'domcontentloaded'});await page.waitForFunction(()=>!!window.worldQA);await page.waitForTimeout(1200);
  const shot=async name=>{await page.screenshot({path:resolve(out,name)});report.screenshots.push(name);};
  return {ctx,page,shot};
}
const sha=async p=>createHash('sha256').update(await readFile(p)).digest('hex');
// Game records of a save, read-only (node:sqlite): simulation payload, requests, events, playthroughs, logs.
// Display-only flags (which senior pages / cards were shown) are left out of the comparison.
function records(p){const db=new DatabaseSync(p,{readOnly:true});try{const payload=JSON.parse(db.prepare('SELECT payload FROM simulation_state WHERE id=1').get().payload);
  const strip=o=>{if(o&&typeof o==='object'){for(const k of ['dialogue_seen','failure_seen','feedback_seen'])delete o[k];for(const v of Object.values(o))strip(v);}return o;};
  const tables=Object.fromEntries(db.prepare("SELECT name FROM sqlite_master WHERE type='table' AND name<>'simulation_state'").all().map(t=>[t.name,db.prepare(`SELECT * FROM ${t.name}`).all()]));
  return JSON.stringify({payload:strip(payload),tables});}finally{db.close();}}
const savePath=id=>join(stack.saveDir,`${id}.db`);
async function chapterRecord(page,label){const s=await S(page),st=s.game.story;report.chapters.push({label,id:s.gameId,clock:s.game.clock.label,chapter:st.chapter.heading,state:st.chapter.state,
  result:st.result?.summary?.verdict??st.result?.score??null,gpuUsed:s.game.datacenter.gpuUsed,servers:s.game.servers.map(x=>`${x.key}:${x.state}`).join(' '),campaign:st.campaign.map(c=>`${c.label}:${c.state}`).join(' ')});}
async function perf(page,label){await page.waitForTimeout(1300);const s=await S(page);report.performance.push({label,fps:+s.stats.fps.toFixed(1),p95:+(s.stats.p95FrameMs??0).toFixed(2),heapMiB:s.heap?+(s.heap.used/1048576).toFixed(1):null,geometries:s.renderer.geometries,textures:s.renderer.textures,calls:s.renderer.calls});}
// Engine process restart + resume from the menu, with the chapter state compared before/after.
async function restartAndResume(ctx,page,label){
  const before=(await S(page)).game,id=before.id;await ctx.close();
  await stack.restartEngine();
  const {ctx:ctx2,page:page2,shot}=await open();
  await page2.evaluate(()=>{try{sessionStorage.clear();}catch{}});
  if(!(await page2.evaluate(()=>!document.querySelector('#menu').hidden)))await click(page2,'#menu-open');
  await page2.waitForSelector(`[data-resume="${id}"]`);await click(page2,`[data-resume="${id}"]`);await page2.waitForTimeout(800);
  const after=(await S(page2)).game;
  for(const k of ['clock','requests','servers','datacenter'])assert.deepEqual(after[k],before[k],`${label}: ${k} kept after engine restart`);
  for(const k of ['chapterKey','uiStep','campaign','result','next','retry','jobsDone'])assert.deepEqual(after.story[k],before.story[k],`${label}: story.${k} kept`);
  report.resumes.push({label,id,clock:after.clock.label,chapter:after.story.chapter.heading,state:after.story.chapter.state,next:after.story.next?.heading??null});
  return {ctx:ctx2,page:page2,shot};
}

// ---------- chapter flows (real UI only) ----------
async function chapter1(page,shot){
  while(await page.locator('#talk-next').count())await click(page,'#talk-next');
  assert.equal((await story(page)).step,'arrival','pages alone do not start the shift');await click(page,'#coach-start');
  for(let i=0;i<3;i++){
    const g=(await S(page)).game,r=g.requests.find(x=>x.stage==='incoming');
    await job(page,r.id,r.conditions.requestedMode);
    await advanceUntil(page,s=>s.game.requests.find(x=>x.id===r.id).stage==='done');
    if(i<2)await drainScreens(page);
  }
  await page.waitForSelector('#screen-dialog[open] [data-next=next-chapter]');assert.equal(await screenOpen(page),'chapter-clear');
  if(shot)await shot('ch1-clear.png');
}
async function startNext(page,key){
  const before=(await S(page)).game;
  await click(page,'#screen-dialog[open] [data-next=next-chapter]');await page.waitForTimeout(500);
  const st=await story(page);assert.equal(String(st.chapterKey),key,`chapter ${key} started by the engine`);
  assert.equal(before.id,(await S(page)).gameId,'the next chapter continues in the same save');
}
async function chapter2(page,shot){
  assert.deepEqual(await readAllTalk(page).then(x=>x.slice(0,1)),['c2_briefing']);
  let st=await story(page);assert.equal(st.uiStep,'c2_requests','the briefing was confirmed by the last dialogue button');
  const [jp,us]=st.chapter2.requestIds;
  await tab(page,'inbox');assert.ok(await page.locator('[data-compare]').count(),'the two requests are compared on the monitor');
  if(shot)await shot('ch2-compare.png');
  for(const rid of [jp,us])await readRequest(page,rid);
  await readAllTalk(page);
  // Japan high performance first: the plan card shows what each option leaves for the US customer.
  await choosePlan(page,jp,'performance',0);
  assert.match(await page.locator('[data-plan-option="performance:0"]').textContent(),/다른 고객: 미국/);
  if(shot)await shot('ch2-plan-impacts.png');
  await startInHall(page,jp);
  // An impossible plan is refused by the rules: US high performance no longer fits next to Japan.
  await tab(page,'inbox');await click(page,`[data-request-row="${us}"]`);await tab(page,'plan');await page.waitForSelector('.mode-card[data-mode=performance]');
  assert.equal(await page.locator('[data-plan-option^="performance"]').count(),0,'no option for a plan that does not fit');
  assert.match(await page.locator('.mode-card[data-mode=performance]').textContent(),/부족|할 수 없|불가/);
  await choosePlan(page,us,'economy',0);await startInHall(page,us);
  await places(page,'hall');if(shot)await shot('ch2-hall-two-customers.png');
  const s=await S(page);assert.equal(s.game.datacenter.gpuUsed,8);assert.ok(s.game.servers.some(x=>x.slots.includes(jp))&&s.game.servers.some(x=>x.slots.includes(us)),'both customers on the racks');
  await advanceUntil(page,s=>s.game.story.done,{minutes:30,onEach:async()=>{await readAllTalk(page);await drainScreens(page);}});
  await drainScreens(page);
  st=await story(page);assert.equal(st.result.mission,'success');assert.equal(st.chapter.state,'cleared');
  await page.waitForSelector('#screen-dialog[open] [data-next=next-chapter]');if(shot)await shot('ch2-clear.png');
}
async function networkIncident(page,rid,wrong,right,shot,tag){
  const r=await req(page,rid);await job(page,rid,r.conditions.requestedMode);
  await advanceUntil(page,s=>s.game.requests.find(x=>x.id===rid).stage==='net_fault',{onEach:()=>readAllTalk(page)});
  let s=await S(page);const path=s.game.world.paths.find(p=>p.rid===rid);
  assert.equal(path.link,'symptom','before the diagnosis the world shows a symptom only');assert.equal(path.segments.aidc,'ok','server building not blamed');
  await places(page,'world');s=await S(page);assert.equal(s.network.cause,'symptom');if(shot)await shot(`${tag}-world-symptom.png`);
  await readAllTalk(page);await diagnose(page,rid);await page.waitForSelector('[data-net-diagnosis]');
  if(shot)await shot(`${tag}-diagnosis.png`);
  s=await S(page);const link=s.game.world.paths.find(p=>p.rid===rid).link;assert.ok(['primary_down','congested'].includes(link),`evidence after the diagnosis (${link})`);
  if(tag==='ch3-a'){
    // Network building: the AIDC internal uplink stays normal; only the customer transit is reported (review fix).
    await places(page,'campus');await click(page,'[data-facility=NETWORK]');await click(page,'#enter-building');await page.waitForTimeout(1300);
    const v=(await S(page)).interior;assert.equal(v.room,'NETWORK');assert.equal(v.faultPortsBlinking,false);assert.equal(v.transitDown,true);
    assert.match(await page.locator('#context-card').textContent(),/AIDC 내부\)정상|AIDC 내부\) ?정상/);if(shot)await shot('ch3-network-room.png');
    await diagnose(page,rid);await page.waitForSelector('[data-net-diagnosis]');   // back to the monitor (a re-view)
  }
  await click(page,`[data-respond=${wrong}]`);await page.waitForSelector('#screen-dialog[open]');assert.equal(await screenOpen(page),'chapter3-card');
  assert.equal((await req(page,rid)).stage,'net_fault','the wrong response did not recover the job');await click(page,'#screen-dialog[open] [data-next=continue]');
  await readAllTalk(page);await diagnose(page,rid);await click(page,`[data-respond=${right}]`);await page.waitForSelector('#screen-dialog[open]');
  assert.equal((await req(page,rid)).stage,'recovering');if(shot)await shot(`${tag}-recovered-card.png`);await click(page,'#screen-dialog[open] [data-next=continue]');
  await advanceUntil(page,s=>s.game.requests.find(x=>x.id===rid).stage==='done',{minutes:30,onEach:()=>readAllTalk(page)});
  await drainScreens(page);await readAllTalk(page);
}
async function chapter3(page,shot){
  assert.equal((await readTalk(page))?.event,'c3_briefing');
  const a=(await story(page)).chapter3.requestIds[0];await networkIncident(page,a,'compress','reroute',shot,'ch3-a');
  const b=(await story(page)).chapter3.requestIds[1];assert.ok(b,'mission B arrived after A');await networkIncident(page,b,'reroute','compress',shot,'ch3-b');
  await page.waitForSelector('#screen-dialog[open] [data-next=next-chapter]');assert.equal((await story(page)).result.mission,'success');if(shot)await shot('ch3-clear.png');
}
async function hardwareIncident(page,rid,choice,shot,tag){
  const r=await req(page,rid);await job(page,rid,r.conditions.requestedMode);
  await advanceUntil(page,s=>s.game.requests.find(x=>x.id===rid).stage==='hw_fault',{onEach:()=>readAllTalk(page)});
  const s=await S(page),server=s.game.servers.find(x=>x.state==='FAULT');assert.ok(server,'the engine fault is on a real server');
  assert.equal(s.state.facility.assets.find(a=>a.id===server.rack).state,'fault',`3D rack ${server.rack} shows the engine fault`);
  await places(page,'hall');await click(page,'[data-camera=overview]');await page.waitForTimeout(1200);await canvasClick(page,'rack',server.rack);if(shot)await shot(`${tag}-hall-fault.png`);
  await readAllTalk(page);await diagnose(page,rid);await page.waitForSelector('[data-hw-diagnosis]');if(shot)await shot(`${tag}-diagnosis.png`);
  const text=await page.locator('[data-hw-diagnosis]').textContent();
  if(choice==='repair'&&/작업 이전불가/.test(text.replace(/\s/g,''))){
    const before=(await S(page)).game.servers;await click(page,'[data-migrate]');assert.match(await toastText(page),/GPU/,'an impossible migration is explained and refused');
    assert.deepEqual((await S(page)).game.servers,before);
  }
  await click(page,choice==='migrate'?'[data-migrate]':`[data-repair=${server.key}]`);
  await page.waitForSelector('#screen-dialog[open]');assert.equal(await screenOpen(page),'chapter3b-card');if(shot)await shot(`${tag}-card.png`);await click(page,'#screen-dialog[open] [data-next=continue]');
  await advanceUntil(page,s=>['done','failed'].includes(s.game.requests.find(x=>x.id===rid).stage),{onEach:async()=>{await readAllTalk(page);await drainScreens(page);}});
  await drainScreens(page);await readAllTalk(page);
  return server;
}
async function chapter4(page,shot){
  assert.equal((await readTalk(page))?.event,'c3b_briefing');
  const jp=(await story(page)).chapter3b.requestIds[0];await hardwareIncident(page,jp,'migrate',shot,'ch4-a');
  const sg=(await story(page)).chapter3b.requestIds[1];await hardwareIncident(page,sg,'repair',shot,'ch4-b');
  await page.waitForSelector('#screen-dialog[open] [data-next=next-chapter]');assert.equal((await story(page)).result.mission,'success');if(shot)await shot('ch4-clear.png');
}
async function term(page,stage,line){const i=page.locator(`[data-terminal-input=${stage}]`);await i.click();await i.fill(line);await page.keyboard.press('Enter');await settle(page,250);}
const lab=async page=>(await story(page)).training.status;
async function chapter5(page,shot){
  assert.equal((await readTalk(page))?.event,'t_structure');
  const rid=(await lab(page)).rid;
  await tab(page,'lab');assert.match(await page.locator('[data-lab-head]').textContent(),/준비|배정/,'Stage 1 needs a real incident first');
  if(await page.locator('[data-segment]').count()){await click(page,'[data-segment=primary-wan]');assert.equal((await lab(page)).segment,null,'no answer recorded without a real fault');}
  const r=await req(page,rid);await job(page,rid,r.conditions.requestedMode);
  await advanceUntil(page,s=>s.game.requests.find(x=>x.id===rid).stage==='net_fault');
  assert.equal((await req(page,rid)).network.available,null,'chapter 5 shows no cause numbers');
  await diagnose(page,rid);assert.ok(await page.locator('[data-training-symptom]').count());
  await click(page,'[data-respond=reroute]');assert.match(await toastText(page),/Stage 5|심화 연수/,'acting before Stage 5 is refused');
  // Stage 1: structure
  await tab(page,'lab');if(shot)await shot('ch5-stage1.png');
  await click(page,'[data-segment=edge-primary]');assert.equal((await lab(page)).segment.correct,false);
  await click(page,'[data-segment=primary-wan]');assert.equal((await lab(page)).segment.correct,true);
  await click(page,'[data-answer="structure:impact:gpu"]');await click(page,'[data-answer="structure:impact:blocked"]');
  assert.ok((await lab(page)).can_advance);await click(page,'[data-lab-next]');
  // Stage 2: tool choice (a partial tool first, then the right one) + limit
  await readTalk(page);await tab(page,'lab');
  await click(page,'[data-choice="ip addr"]');assert.equal((await lab(page)).can_advance,false);
  await click(page,'[data-choice=ping]');await click(page,'[data-answer="tool:limit:cause"]');await click(page,'[data-answer="tool:limit:icmp"]');if(shot)await shot('ch5-stage2.png');
  await click(page,'[data-lab-next]');
  // Stage 3: blocks (missing count first -> not a valid assembly), then -c 3 + server address
  await readTalk(page);await tab(page,'lab');
  await page.selectOption('[data-block=command]','ping');await settle(page);await page.selectOption('[data-block=target]','10.0.0.20');await settle(page);await click(page,'[data-run-blocks]');
  assert.equal((await lab(page)).assembly,null,'ping without -c is not the assembly the stage asks for');
  await page.selectOption('[data-block=option]','-c 3');await settle(page);await click(page,'[data-run-blocks]');
  const asm=(await lab(page)).assembly;assert.equal(asm.count,3);await click(page,`[data-answer="assemble:received:${asm.received}"]`);if(shot)await shot('ch5-stage3.png');
  await click(page,'[data-lab-next]');
  // Stage 4: typed commands (a refused one first), evidence, fact classification (one wrong first)
  await readTalk(page);await tab(page,'lab');
  await term(page,'terminal','rm -rf /');assert.ok(await page.locator('.lab-term .ws-warn, pre.lab-out').count());
  for(const line of ['ping -c 2 192.168.10.1','ping -c 2 10.0.0.20','ip route'])await term(page,'terminal',line);
  const st=await lab(page);assert.deepEqual(st.evidence,{near:true,remote:true,route:true});
  const truth={near:'confirmed',remote:'confirmed',route:'confirmed',line_cut:'unknown',server_down:'unknown'};
  for(const [k]of st.statements)await click(page,`[data-fact="${k}:${k==='line_cut'?'confirmed':truth[k]}"]`);await click(page,'[data-facts-submit]');assert.equal((await lab(page)).facts.correct,false);
  await click(page,'[data-fact="line_cut:unknown"]');await click(page,'[data-facts-submit]');assert.equal((await lab(page)).facts.correct,true);if(shot)await shot('ch5-stage4.png');
  await click(page,'[data-lab-next]');
  // Stage 5: independent — evidence, cause (wrong first), action on the monitor, re-check
  await readTalk(page);await tab(page,'lab');assert.ok(Object.values((await story(page)).training.network.segments).every(v=>v===null),'Stage 5 hides the structure answer');
  for(const line of ['ping -c 2 10.0.0.20','ping -c 2 192.168.10.1'])await term(page,'independent',line);
  await click(page,'[data-answer="independent:cause:server"]');await click(page,'[data-answer="independent:cause:path_down"]');
  await diagnose(page,rid);await click(page,'[data-respond=reroute]');assert.equal((await req(page,rid)).stage,'recovering');
  assert.equal((await story(page)).done,false,'acting is not verifying');
  await tab(page,'lab');await term(page,'independent','ping -c 2 10.0.0.20');if(shot)await shot('ch5-stage5-verified.png');
  await page.waitForSelector('#screen-dialog[open]');
}

try{
  // --seed is a DEVELOPMENT shortcut for iterating the failure checks (campaign played through adapter actions).
  // The reported run never uses it: there the campaign itself is played through the browser UI.
  const seedDir=process.argv.includes('--seed')?tempSaveDir():undefined;
  if(seedDir){campaignId=execFileSync(python(),['-m','engine.tests.seed_campaign',seedDir],{encoding:'utf8',env:{...process.env,PYTHONIOENCODING:'utf-8'}}).trim().split(/\s+/).at(-1);report.seeded=true;}
  stack=await startStack(seedDir?{saveDir:seedDir}:{});report.url=stack.url;
  browser=await chromium.launch({executablePath:CHROME,headless:false,args:['--window-size=1920,1080']});report.browserVersion=browser.version();

  await check('regular story chapters 1 -> 5 through the real UI, engine restart + resume after every chapter, graduation',async()=>{
    let {ctx,page,shot}=await open();
    await page.waitForSelector('[data-new=story]');await click(page,'[data-new=story]');await page.waitForTimeout(800);
    campaignId=(await S(page)).gameId;await perf(page,'ch1 start (noc)');
    const res0=(await S(page)).renderer;report.resources.push({label:'start',geometries:res0.geometries,textures:res0.textures});
    await chapter1(page,shot);await chapterRecord(page,'ch1 clear');
    ({ctx,page,shot}=await restartAndResume(ctx,page,'after ch1'));await page.waitForSelector('#screen-dialog[open] [data-next=next-chapter]');
    await startNext(page,'2');await chapter2(page,shot);await chapterRecord(page,'ch2 clear');await perf(page,'ch2 hall');
    ({ctx,page,shot}=await restartAndResume(ctx,page,'after ch2'));await page.waitForSelector('#screen-dialog[open] [data-next=next-chapter]');
    await startNext(page,'3');await chapter3(page,shot);await chapterRecord(page,'ch3 clear');await perf(page,'ch3 world');
    ({ctx,page,shot}=await restartAndResume(ctx,page,'after ch3'));await page.waitForSelector('#screen-dialog[open] [data-next=next-chapter]');
    await startNext(page,'3b');await chapter4(page,shot);await chapterRecord(page,'ch4 clear');await perf(page,'ch4 hall');
    ({ctx,page,shot}=await restartAndResume(ctx,page,'after ch4'));await page.waitForSelector('#screen-dialog[open] [data-next=next-chapter]');
    await startNext(page,'lab');await chapter5(page,shot);await chapterRecord(page,'ch5 clear');
    assert.equal(await screenOpen(page),'graduation');await shot('graduation.png');
    const st=await story(page);assert.deepEqual(st.campaign.map(c=>c.state),['cleared','cleared','cleared','cleared','cleared']);
    const res1=(await S(page)).renderer;report.resources.push({label:'after campaign',geometries:res1.geometries,textures:res1.textures});
    ({ctx,page,shot}=await restartAndResume(ctx,page,'after ch5'));await page.waitForSelector('#screen-dialog[open]');assert.equal(await screenOpen(page),'graduation','a finished campaign reopens at its graduation');
    const files=(await readdir(stack.saveDir)).filter(f=>f.startsWith(`aidc_checkpoint_${campaignId}`)).sort();report.checkpoints=files;
    assert.equal(files.length,5,'one chapter-start checkpoint per chapter');
    await ctx.close();
  });
  // ---------- failure / retry / practice / layout / resources (each from a chapter-start point via the menu) ----------
  async function fromCheckpoint(page,key){
    if(!(await page.evaluate(()=>!document.querySelector('#menu').hidden)))await click(page,'#menu-open');
    await page.waitForSelector('[data-chapter-save]');await page.selectOption('[data-chapter-save]',campaignId);
    await page.waitForSelector(`[data-checkpoint="${campaignId}:${key}"]`);const before=(await S(page)).gameId;
    await click(page,`[data-checkpoint="${campaignId}:${key}"]`);await page.waitForTimeout(800);
    const s=await S(page);assert.notEqual(s.gameId,campaignId,'a chapter start point opens as a NEW slot');assert.notEqual(s.gameId,before);
    assert.equal(String(s.game.story.chapterKey),key);return s.gameId;
  }
  const campaignHash=async()=>records(savePath(campaignId));

  await check('chapter 2 failure through the UI: original conditions in a row are late → senior feedback → retry in a new slot (source unchanged)',async()=>{
    assert.ok(campaignId,'needs the campaign save');const source=await campaignHash();
    const {ctx,page,shot}=await open();const slot=await fromCheckpoint(page,'2');
    assert.equal((await readTalk(page))?.event,'c2_briefing');const [jp,us]=(await story(page)).chapter2.requestIds;
    for(const rid of [jp,us])await readRequest(page,rid);
    await job(page,jp,'performance');
    await advanceUntil(page,s=>s.game.requests.find(x=>x.id===jp).stage==='done',{onEach:()=>drainScreens(page)});await drainScreens(page);
    await job(page,us,'performance');
    await advanceUntil(page,s=>!!s.game.story.chapter2.failure,{onEach:async()=>{if(await screenOpen(page)==='job-done')await drainScreens(page);}});
    await page.waitForSelector('#screen-dialog[open] [data-next=retry]');assert.equal(await screenOpen(page),'chapter2-failure');await shot('ch2-failure-feedback.png');
    const st=await story(page);assert.equal(st.chapter2.failure.reason,'late');
    const slotRecords=records(savePath(slot));
    await click(page,'#screen-dialog[open] [data-next=retry]');await page.waitForTimeout(800);
    const s=await S(page);assert.notEqual(s.gameId,slot,'retry is a new slot');assert.equal(s.game.story.uiStep,'c2_briefing');
    assert.equal(records(savePath(slot)),slotRecords,'the failed slot keeps every game record after the retry');assert.equal(records(savePath(campaignId)),source,'the campaign save is unchanged');
    report.retries.push({chapter:'2',from:slot,to:s.gameId,reason:st.chapter2.failure.reason,clock:s.game.clock.label});
    await ctx.close();
  });

  await check('chapter 3 failure: three wrong responses → failed card → retry; responses before the diagnosis are not offered',async()=>{
    const {ctx,page,shot}=await open();const slot=await fromCheckpoint(page,'3');
    assert.equal((await readTalk(page))?.event,'c3_briefing');const a=(await story(page)).chapter3.requestIds[0];
    await job(page,a,'performance');await advanceUntil(page,s=>s.game.requests.find(x=>x.id===a).stage==='net_fault');
    await tab(page,'diagnosis');await page.waitForSelector('[data-net-diagnosis]');
    const failedCard=async()=>((await story(page)).chapter3.pending?.key||'').endsWith(':failed');
    for(let i=0;i<3;i++){
      if((await req(page,a)).phase==='finished')break;
      await tab(page,'diagnosis');await click(page,'[data-respond=ignore]');
      if((await req(page,a)).phase==='finished'||await failedCard())break;   // keep the final card open
      await drainScreens(page);
    }
    await advanceUntil(page,s=>s.game.requests.find(x=>x.id===a).phase==='finished',{minutes:30,onEach:async()=>{if(!await failedCard())await drainScreens(page);}});
    await page.waitForSelector('#screen-dialog[open] [data-next=retry]');assert.equal(await screenOpen(page),'chapter3-card');await shot('ch3-failed-card.png');
    const card=(await story(page)).chapter3.cards[String(a)];assert.equal(card.can_retry,true);
    await click(page,'#screen-dialog[open] [data-next=retry]');await page.waitForTimeout(800);
    const s=await S(page);assert.notEqual(s.gameId,slot);assert.equal(s.game.story.uiStep,'c3_briefing');
    report.retries.push({chapter:'3',from:slot,to:s.gameId,reason:card.title,clock:s.game.clock.label});
    await ctx.close();
  });

  await check('chapter 4 failure: repair on the tight deadline is late → chapter failed (no next chapter) → retry; impossible migration refused',async()=>{
    const {ctx,page,shot}=await open();const slot=await fromCheckpoint(page,'3b');
    assert.equal((await readTalk(page))?.event,'c3b_briefing');
    const jp=(await story(page)).chapter3b.requestIds[0];await hardwareIncident(page,jp,'repair',null,'ch4f-a');
    assert.equal((await req(page,jp)).summary.key,'late');
    const sg=(await story(page)).chapter3b.requestIds[1];await hardwareIncident(page,sg,'repair',null,'ch4f-b');
    await page.waitForSelector('#screen-dialog[open] [data-next=retry]');assert.equal(await screenOpen(page),'chapter-failed');
    assert.equal(await page.locator('#screen-dialog[open] [data-next=next-chapter]').count(),0,'a failed chapter offers no next chapter');
    assert.equal((await story(page)).campaign.find(c=>c.key==='lab').state,'locked');await shot('ch4-failed.png');
    await click(page,'#screen-dialog[open] [data-next=retry]');await page.waitForTimeout(800);
    const s=await S(page);assert.notEqual(s.gameId,slot);assert.equal(s.game.story.uiStep,'c3b_briefing');
    report.retries.push({chapter:'3b',from:slot,to:s.gameId,reason:'repair late',clock:s.game.clock.label});
    await ctx.close();
  });

  await check('chapter practice from the menu is a separate save: no campaign, no next chapter, free stage choice in the Lab',async()=>{
    const {ctx,page,shot}=await open();await page.waitForSelector('[data-practice=lab]');await click(page,'[data-practice=lab]');await page.waitForTimeout(800);
    let s=await S(page);assert.equal(s.game.kind,'practice');assert.deepEqual(s.game.story.campaign,[]);assert.equal(s.game.story.next,null);
    await readAllTalk(page);await tab(page,'lab');assert.ok(await page.locator('[data-lab-focus]').count(),'practice can pick any stage');
    await click(page,'[data-lab-focus=terminal]');assert.equal((await story(page)).training.status.current,'terminal');
    await readAllTalk(page);await tab(page,'lab');await page.locator('[data-terminal-input=terminal]').fill('ip addr');await page.keyboard.press('Enter');await settle(page);
    assert.match(await page.locator('pre.lab-out').last().textContent(),/eth0/);await shot('practice-lab-terminal.png');
    await click(page,'#menu-open');await page.waitForSelector('[data-practice="3b"]');await click(page,'[data-practice="3b"]');await page.waitForTimeout(800);
    s=await S(page);assert.equal(s.game.kind,'practice');assert.match(s.game.story.chapter.heading,/제4장.*연습/);
    const files=(await readdir(stack.saveDir)).filter(f=>f.includes(s.gameId)&&f.includes('checkpoint'));assert.deepEqual(files,[],'practice keeps no promotion checkpoint');
    await ctx.close();
  });

  for(const [w,h,dpr,label]of [[1366,768,1,'1366x768'],[1280,720,1.5,'150% of 1920x1080 (emulated)'],[1920,1080,1,'1920x1080']]){
    await check(`layout ${label}: talk, tabs, time, diagnosis responses, Lab controls and terminal reachable without page scroll`,async()=>{
      const {ctx,page,shot}=await open({width:w,height:h,dpr});const slot=await fromCheckpoint(page,'lab');
      const inView=async sel=>page.evaluate(s=>{const e=document.querySelector(s);if(!e)return {ok:false,why:'missing'};const r=e.getBoundingClientRect();
        const pane=e.closest('.ws-pane');const pr=pane?.getBoundingClientRect();const inPane=!pane||(r.top>=pr.top-1&&r.bottom<=pr.bottom+1);
        const top=document.elementFromPoint(r.left+r.width/2,r.top+Math.min(r.height/2,8));
        return {ok:r.width>0&&r.top>=0&&r.bottom<=innerHeight&&r.left>=0&&r.right<=innerWidth&&inPane&&(top===e||e.contains(top)),why:JSON.stringify({r:[r.left,r.top,r.right,r.bottom].map(Math.round),inPane,top:top?.className})};},sel);
      const need=async sel=>{const v=await inView(sel);assert.ok(v.ok,`${label}: ${sel} ${v.why}`);};
      await need('#talk:not([hidden]) #talk-next, #talk:not([hidden]) [data-talk-done]');await readAllTalk(page);
      await need('#clock [data-advance="10"]');await need('[data-ws-tab=lab]');await need('[data-ws-tab=diagnosis]');
      await tab(page,'lab');await need('[data-lab-head]');
      const rid=(await story(page)).training.status.rid,r=await req(page,rid);await job(page,rid,r.conditions.requestedMode);
      await advanceUntil(page,s=>s.game.requests.find(x=>x.id===rid).stage==='net_fault');
      await tab(page,'lab');await need('[data-segment=primary-wan]');await shot(`layout-${w}x${h}@${dpr}-lab.png`);
      await tab(page,'diagnosis');await page.locator('[data-respond=reroute]').scrollIntoViewIfNeeded();await need('[data-respond=reroute]');
      await ctx.close();
    });
  }

  await check('WebGL resources and heap stay flat while cycling every space three times in one page',async()=>{
    const {ctx,page}=await open();await click(page,'[data-new=free]');await page.waitForTimeout(800);
    const cycle=async()=>{for(const r of ['world','campus','noc','hall'])await places(page,r);await page.waitForTimeout(600);const s=await S(page);return {geometries:s.renderer.geometries,textures:s.renderer.textures,heap:s.heap?.used??null,fps:s.stats.fps};};
    const a=await cycle(),b=await cycle(),c=await cycle();report.resources.push({label:'space cycles',cycles:[a,b,c]});
    assert.ok(c.geometries<=a.geometries+5&&c.textures<=a.textures+2,`no growth: ${JSON.stringify([a,b,c])}`);
    await ctx.close();
  });
}finally{
  report.finishedAt=new Date().toISOString();report.pass=report.checks.every(c=>c.pass);
  // Only a full, unseeded run is the reported evidence; partial or seeded development runs go to another file.
  await writeFile(resolve(out,only||report.seeded?'phase5-qa-partial.json':'phase5-qa.json'),JSON.stringify(report,null,2));
  await browser?.close();await stack?.stop();
  console.log(`${report.checks.filter(c=>c.pass).length}/${report.checks.length} checks passed · errors ${report.errors.length} · console ${report.consoleErrors.length}`);
  process.exitCode=report.pass?0:1;
}
