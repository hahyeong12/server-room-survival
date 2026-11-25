// Phase 6 (Issue #7) QA precondition: a regular story save graduated through the REAL UI (chapters 1 -> 5).
// Verbatim copy of the chapter flows in phase5-qa.mjs (that script is left unchanged). Real clicks only.
import assert from 'node:assert/strict';
import {settle} from './qa-lib.mjs';
import {S,story,req,click,places,canvasClick,toastText,screenOpen,readTalk,readAllTalk,drainScreens,tab,readRequest,choosePlan,startInHall,job,advanceUntil,diagnose} from './phase5-ui.mjs';
export async function chapter1(page,shot){
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
export async function startNext(page,key){
  const before=(await S(page)).game;
  await click(page,'#screen-dialog[open] [data-next=next-chapter]');await page.waitForTimeout(500);
  const st=await story(page);assert.equal(String(st.chapterKey),key,`chapter ${key} started by the engine`);
  assert.equal(before.id,(await S(page)).gameId,'the next chapter continues in the same save');
}
export async function chapter2(page,shot){
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
export async function chapter3(page,shot){
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
export async function chapter4(page,shot){
  assert.equal((await readTalk(page))?.event,'c3b_briefing');
  const jp=(await story(page)).chapter3b.requestIds[0];await hardwareIncident(page,jp,'migrate',shot,'ch4-a');
  const sg=(await story(page)).chapter3b.requestIds[1];await hardwareIncident(page,sg,'repair',shot,'ch4-b');
  await page.waitForSelector('#screen-dialog[open] [data-next=next-chapter]');assert.equal((await story(page)).result.mission,'success');if(shot)await shot('ch4-clear.png');
}
async function term(page,stage,line){const i=page.locator(`[data-terminal-input=${stage}]`);await i.click();await i.fill(line);await page.keyboard.press('Enter');await settle(page,250);}
const lab=async page=>(await story(page)).training.status;
export async function chapter5(page,shot){
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

