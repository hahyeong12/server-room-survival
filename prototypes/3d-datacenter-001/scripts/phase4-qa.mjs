// Issue #5 (Phase 4) browser QA. Real Chrome (headed), Playwright CDP mouse/keyboard, isolated contexts, and an
// isolated stack (Python engine + temporary save folder, own Vite). Every state change is a real UI event on the
// actual world / campus / desk / server hall / monitor / rack / response controls; window.worldQA is read-only.
// There is no "next" button that acts for the player, so no test can pass by clicking one repeatedly.
// Windows display scaling is EMULATED with deviceScaleFactor (not a real OS change).
import {chromium} from 'playwright-core';
import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {startStack,settle,snap,CHROME} from './qa-lib.mjs';

// --out=<dir> keeps the Phase 4 evidence untouched when the suite is re-run as a regression (Phase 5+).
const out=resolve(process.argv.find(x=>x.startsWith('--out='))?.slice(6)||'../../docs/3d-world-expansion/qa/phase4');await mkdir(out,{recursive:true});
const only=process.argv.find(x=>x.startsWith('--only='))?.slice(7);
const report={issue:5,mode:'Chrome headed / Playwright CDP / isolated contexts / isolated engine+saves',checks:[],errors:[],consoleErrors:[],screenshots:[],steps:[],viewports:[],performance:[],startedAt:new Date().toISOString()};
let browser,stack;
async function check(name,fn){if(only&&!name.includes(only))return;const t=Date.now();try{await fn();report.checks.push({name,pass:true,ms:Date.now()-t});console.log(`PASS ${name}`);}catch(e){report.checks.push({name,pass:false,error:e.message});console.log(`FAIL ${name}: ${e.message.split('\n')[0]}`);}}
async function open({width=1920,height=1080,dpr=1,opening=false}={}){
  const ctx=await browser.newContext({viewport:{width,height},deviceScaleFactor:dpr});
  if(!opening)await ctx.addInitScript(()=>{try{localStorage.setItem('srs3d.opening.seen.v1','1');}catch{}});
  const page=await ctx.newPage();page.on('pageerror',e=>report.errors.push(e.message));page.on('console',m=>{if(m.type()==='error')report.consoleErrors.push(m.text());});
  page.on('dialog',d=>d.accept());
  await page.goto(stack.url,{waitUntil:'domcontentloaded'});await page.waitForFunction(()=>!!window.worldQA);await page.waitForTimeout(1200);
  const shot=async name=>{await page.screenshot({path:resolve(out,name)});report.screenshots.push(name);};
  return {ctx,page,shot};
}
const S=page=>snap(page);
const step=async page=>(await S(page)).game?.journey?.current?.id??null;
async function clickSel(page,sel){await page.locator(sel).first().click();await settle(page);}
async function places(page,route){await clickSel(page,`#places [data-route=${route}]`);await page.waitForTimeout(1300);}
async function canvasClick(page,kind,id,{dbl=false}={}){
  const p=await page.evaluate(([k,i])=>k==='rack'?worldQA.projectAsset(i):worldQA.projectWorld(i),[kind,id]);
  assert.ok(p?.visible,`${kind} ${id} is on screen`);
  if(dbl)await page.mouse.dblclick(p.x,p.y);else await page.mouse.click(p.x,p.y);await settle(page,350);return p;
}
async function toastText(page){return page.evaluate(()=>{const t=document.querySelector('#toast');return t.hidden?'':t.textContent;});}
// Coach evidence for a step: which real element / 3D object is highlighted.
async function coachEvidence(page){const s=await S(page);return {step:s.game?.journey?.current?.id,spot:s.coach?.spotSelector,ring:s.coach?.ring,bubble:s.coach?.bubble};}
async function logStep(page,label,extra={}){const s=await S(page);report.steps.push({label,clock:s.game?.clock?.label,step:s.game?.journey?.current?.id??null,stage:s.game?.requests?.map(r=>`${r.id}:${r.stage}:${r.progress}`).join(','),coach:s.coach,...extra});}

// Real-UI handlers for each tutorial step. A handler must move the journey forward by itself; misclicks first where useful.
const HANDLERS={
  async briefing(page){while(await page.locator('#talk-next').count()){await clickSel(page,'#talk-next');}assert.equal(await step(page),'briefing','turning dialogue pages changes nothing');await clickSel(page,'#coach-start');},
  async 'campus-info'(page){await places(page,'campus');assert.equal(await step(page),'campus-info','opening the campus alone is not the step');await canvasClick(page,'world','COOLING');},
  async enter(page){await canvasClick(page,'world','COOLING',{dbl:true});await page.waitForTimeout(1200);assert.equal((await S(page)).state.navigation.route,'room');},
  async back(page){await clickSel(page,'#back');await page.waitForTimeout(1000);},
  async world(page){await places(page,'world');},
  async origin(page){
    const before=(await S(page)).game.journey.misclicks;
    await canvasClick(page,'world','JP');assert.match(await toastText(page),/도착한 요청이 없습니다/);assert.equal(await step(page),'origin','wrong country does not advance');
    assert.equal((await S(page)).game.journey.misclicks,before+1);
    await canvasClick(page,'world','SG');},
  async read(page){await places(page,'noc');await clickSel(page,'[data-ws-tab=inbox]');await clickSel(page,'[data-read-request]');},
  async compare(page){await clickSel(page,'[data-ws-tab=plan]');await page.waitForSelector('[data-plan-option="performance:1"]');},
  async choose(page){
    const eco=await page.locator('.mode-card[data-mode=economy]').textContent();assert.match(eco,/고객 동의 필요/);assert.equal(await page.locator('[data-plan-option^="economy"]').count(),0,'no economy plan without consent');
    await clickSel(page,'[data-plan-option="performance:1"]');},
  async hall(page){await places(page,'hall');},
  async rack(page){
    const g=(await S(page)).game,plan=g.requests[0].selection.slices.map(p=>p.rack),unused=['A-01','B-01','C-01','D-01'].find(r=>!plan.includes(r));
    await canvasClick(page,'rack','B-04');assert.match(await toastText(page),/장식 랙/);
    if(unused){await clickSel(page,'#equipment-select');await page.selectOption('#equipment-select',unused);await settle(page);assert.match(await toastText(page),/배정안에 없습니다/);
      assert.equal(await page.locator('[data-start-job]').count(),0,'no start button on a rack outside the plan');}
    assert.equal(await step(page),'rack');await clickSel(page,'[data-camera=overview]');await page.waitForTimeout(1400);const hit=await canvasClick(page,'rack',plan[0]);report.steps.push({label:'rack canvas click',want:plan[0],got:(await S(page)).state.facility.selectedId,at:hit});},
  async start(page){const before=(await S(page)).game.datacenter.gpuUsed;assert.equal(before,0);await clickSel(page,'[data-start-job]');assert.equal((await S(page)).game.datacenter.gpuUsed,7);},
  async time(page){await clickSel(page,'[data-advance="10"]');const g=(await S(page)).game;assert.equal(g.requests[0].stage,'hw_fault');assert.equal(g.requests[0].progress,0);},
  async diagnose(page){await places(page,'noc');await clickSel(page,'[data-ws-tab=diagnosis]');await page.waitForSelector('[data-responses]');},
  async respond(page){
    const before=(await S(page)).game,fault=before.journey.fault.server;
    for(const sel of ['[data-respond=reroute]','[data-migrate]',`[data-repair=${['A','B','C','D'].find(k=>k!==fault&&before.requests[0].allocation.some(p=>p.server===k))}]`]){await clickSel(page,sel);assert.equal(await step(page),'respond',`misjudgement ${sel} does not advance`);}
    const after=(await S(page)).game;assert.deepEqual(after.servers,before.servers);assert.equal(after.clock.label,before.clock.label);
    report.steps.push({label:'misjudgements refused by the engine',journeyMisclicks:after.journey.misclicks});
    await clickSel(page,`[data-repair=${fault}]`);},
  async recover(page){await clickSel(page,'[data-advance="10"]');assert.equal(await step(page),'recover','10 of 20 repair minutes');await clickSel(page,'[data-advance="10"]');},
  async verify(page){const f=(await S(page)).game.journey.fault;await places(page,'hall');await page.waitForTimeout(400);await canvasClick(page,'rack',f.rack);await clickSel(page,`[data-verify="${f.rack}"]`);},
  async finish(page){await clickSel(page,'[data-advance="10"]');},
  async report(page){await places(page,'noc');await clickSel(page,'[data-ws-tab=result]');await clickSel(page,'[data-report]');},
};
async function playTutorial(page,{until=null,shot=null}={}){
  for(let guard=0;guard<40;guard++){
    const id=await step(page);if(!id||id===until)return id;
    const ev=await coachEvidence(page);assert.ok(ev.spot||ev.ring||id==='briefing',`step ${id} highlights a real element or 3D object (${JSON.stringify(ev)})`);
    await HANDLERS[id](page);await settle(page,300);
    const next=await step(page);assert.notEqual(next,id,`step ${id} completed by its real action`);
    await logStep(page,`tutorial ${id} → ${next}`,{evidence:ev});
    if(shot)await shot(id,page);
  }
  throw new Error('tutorial did not finish');
}
async function startMode(page,mode){await clickSel(page,`[data-new=${mode}]`);await page.waitForTimeout(800);return (await S(page)).gameId;}
async function storyJob(page,rid){
  await places(page,'noc');await clickSel(page,'[data-ws-tab=inbox]');await clickSel(page,`[data-request-row="${rid}"]`);await clickSel(page,'[data-read-request]');
  await clickSel(page,'[data-ws-tab=plan]');await page.waitForSelector('[data-plan-option="performance:0"]');await clickSel(page,'[data-plan-option="performance:0"]');
  const r=(await S(page)).game.requests.find(x=>x.id===rid);await places(page,'hall');await page.waitForTimeout(400);await canvasClick(page,'rack',r.selection.slices[0].rack);await clickSel(page,'[data-start-job]');
  for(let i=0;i<12&&(await S(page)).game.requests.find(x=>x.id===rid).stage!=='done';i++){await clickSel(page,'[data-advance="10"]');}
  assert.equal((await S(page)).game.requests.find(x=>x.id===rid).stage,'done');
}

try{
  stack=await startStack();report.url=stack.url;report.saveDir='(temporary, removed after QA)';
  browser=await chromium.launch({executablePath:CHROME,headless:false,args:['--window-size=1920,1080']});report.browserVersion=browser.version();

  await check('neutral opening: no game, no lit path or request badge, whatever is selected; first request lights only its own path',async()=>{
    const {ctx,page,shot}=await open({opening:true});
    await page.waitForFunction(()=>worldQA.snapshot().opening.active);const samples=[];
    for(let i=0;i<5;i++){await page.waitForTimeout(500);const s=await S(page);samples.push(s.network);}
    await shot('opening-world-neutral.png');
    for(const n of samples.filter(Boolean)){assert.deepEqual(n.lit,[]);assert.deepEqual(n.requestBadges,[]);assert.equal(n.packetsVisible,false);assert.equal(n.faultBadge,false);for(const c of ['SG','JP','US'])assert.equal(n.markers[c],'#6d8ea3',`${c} marker neutral`);}
    const text=await page.locator('#opening-sub').textContent();assert.ok(!/싱가포르|일본|미국/.test(text));
    await page.keyboard.press('Escape');await page.waitForTimeout(800);assert.equal((await S(page)).ui.menu,true,'opening ends at the mode menu');
    // Browse the world with a selected country before any game: still nothing lit.
    await page.evaluate(()=>document.querySelector('#menu').hidden=true);await places(page,'world');for(const c of ['SG','JP','US'])await canvasClick(page,'world',c);
    let s=await S(page);assert.deepEqual(s.network.lit,[]);assert.equal(s.state.navigation.country,'US');
    await page.evaluate(()=>document.querySelector('#menu-open').click());await page.waitForSelector('[data-new=tutorial]');await startMode(page,'tutorial');
    await places(page,'world');s=await S(page);assert.deepEqual(s.network.lit,['SG']);assert.deepEqual(s.network.requestBadges,['SG']);assert.equal(s.network.markers.JP,'#6d8ea3');assert.equal(s.network.markers.US,'#6d8ea3');
    await shot('world-request-arrived.png');await ctx.close();
  });

  let completionPage=null;
  await check('tutorial: every step completed by its own real action on world / campus / desk / hall / monitor / rack / responses',async()=>{
    const {ctx,page,shot}=await open();assert.equal(await page.locator('#primary-action,.coach-target').count(),0,'the old single big button is gone');
    await page.waitForSelector('[data-new=tutorial]');const gid=await startMode(page,'tutorial');assert.match(gid,/^aidc_story_slot_/);
    const shots=new Set(['briefing','origin','choose','rack','time','respond','verify','report']);
    await playTutorial(page,{shot:async id=>{if(shots.has(id))await shot(`tutorial-${id}.png`);}});
    const s=await S(page);assert.equal(s.game.journey.completed,true);assert.equal(s.game.story.done,true);
    assert.equal(s.game.requests[0].stage,'done');assert.equal(s.game.datacenter.gpuUsed,0);assert.ok(s.game.servers.every(x=>x.state==='HEALTHY'));
    await page.waitForSelector('#screen-dialog[open] [data-next=story]');assert.equal(s.screens.open,'tutorial-complete');await shot('tutorial-complete.png');
    report.tutorial={gameId:gid,misclicks:s.game.journey.misclicks,score:s.game.story.result.score,clock:s.game.clock.label};
    completionPage={ctx,page,shot,gid};
  });

  await check('tutorial completion → new story save → first job started, run and finished on the engine → chapter clear → other mode',async()=>{
    assert.ok(completionPage,'needs the completed tutorial');const {ctx,page,shot,gid}=completionPage;
    await clickSel(page,'[data-next=story]');await page.waitForTimeout(800);let s=await S(page);
    assert.notEqual(s.gameId,gid);assert.equal(s.game.mode,'story');assert.equal(s.game.story.step,'arrival');
    while(await page.locator('#talk-next').count())await clickSel(page,'#talk-next');await shot('story-briefing.png');await clickSel(page,'#coach-start');
    s=await S(page);assert.equal(s.game.story.step,'request');assert.equal(s.coach.active,false,'no tutorial coach in the story');
    const first=s.game.requests[0].id;await storyJob(page,first);await page.waitForSelector('#screen-dialog[open][open]');s=await S(page);
    assert.equal(s.screens.open,'job-done');assert.equal(s.game.story.jobsDone,1);assert.deepEqual(s.game.requests.map(r=>r.code),['SG','JP']);await shot('story-first-job-done.png');
    await clickSel(page,'[data-next=stay]');await places(page,'world');s=await S(page);assert.deepEqual(s.network.lit,['JP']);await shot('story-next-request-world.png');
    for(const code of ['JP','US']){const r=(await S(page)).game.requests.find(x=>x.code===code);await storyJob(page,r.id);if(code==='JP'){await page.waitForSelector('#screen-dialog[open]');await clickSel(page,'[data-next=stay]');}}
    await page.waitForSelector('#screen-dialog[open] [data-next=free]');s=await S(page);assert.equal(s.screens.open,'chapter-clear');assert.equal(s.game.story.chapter.state,'cleared');await shot('story-chapter-clear.png');
    report.story={gameId:s.gameId,clock:s.game.clock.label,result:s.game.story.result.summary};
    const storyId=s.gameId;await clickSel(page,'[data-next=free]');await page.waitForTimeout(800);s=await S(page);assert.equal(s.game.mode,'free');
    // Re-entering a tutorial after the story starts a new tutorial save; the story save keeps its clear.
    await page.evaluate(()=>document.querySelector('#menu-open').click());await page.waitForSelector('[data-new=tutorial]');await startMode(page,'tutorial');s=await S(page);assert.equal(s.game.journey.current.id,'briefing');
    const saves=await page.evaluate(()=>fetch('/api/saves').then(r=>r.json()));const story=saves.saves.find(x=>x.id===storyId);assert.ok(story,'story save listed');
    const again=await page.evaluate(id=>fetch(`/api/games/${id}`).then(r=>r.json()),storyId);assert.equal(again.game.story.done,true);assert.equal(again.game.story.jobsDone,3);
    await ctx.close();
  });

  await check('reload and browser back/forward keep the engine state and journey; nothing advances by itself',async()=>{
    const {ctx,page}=await open();await page.waitForSelector('[data-new=tutorial]');await startMode(page,'tutorial');
    await playTutorial(page,{until:'hall'});const a=await S(page);
    await page.reload({waitUntil:'domcontentloaded'});await page.waitForFunction(()=>window.worldQA?.snapshot().gameId);await settle(page,800);
    const b=await S(page);assert.equal(b.gameId,a.gameId);assert.equal(b.game.journey.current.id,'hall');assert.equal(b.game.clock.label,a.game.clock.label);assert.deepEqual(b.game.requests[0].selection,a.game.requests[0].selection);
    await page.goBack().catch(()=>{});await page.waitForTimeout(600);await page.goForward().catch(()=>{});await page.waitForFunction(()=>window.worldQA?.snapshot().gameId).catch(()=>{});await settle(page,800);
    const c=await S(page);assert.equal(c.game.journey.current.id,'hall');assert.equal(c.game.journey.doneSteps,a.game.journey.doneSteps);assert.equal(c.game.datacenter.gpuUsed,0);
    // Dialogue replay / help do not change anything either.
    await clickSel(page,'#help-open');await page.keyboard.press('Escape');assert.equal((await S(page)).game.journey.doneSteps,a.game.journey.doneSteps);
    await ctx.close();
  });

  await check('skip: guide off, recorded as not completed, engine untouched; completion screen offers real modes',async()=>{
    const {ctx,page,shot}=await open();await page.waitForSelector('[data-new=tutorial]');await startMode(page,'tutorial');await playTutorial(page,{until:'origin'});
    const before=(await S(page)).game;await clickSel(page,'#coach-skip');await page.waitForSelector('#screen-dialog[open] [data-next=story]');const s=await S(page);
    assert.equal(s.screens.open,'tutorial-skipped');assert.equal(s.game.journey.completed,false);assert.equal(s.game.journey.skipped,true);
    assert.deepEqual(s.game.requests.map(r=>[r.status,r.stage]),before.requests.map(r=>[r.status,r.stage]));assert.equal(s.game.datacenter.gpuUsed,0);assert.equal(s.game.clock.label,before.clock.label);
    await shot('tutorial-skipped.png');await ctx.close();
  });

  await check('customer consent: economy needs consent; proposal and reply come from the engine customer',async()=>{
    const {ctx,page,shot}=await open();await page.waitForSelector('[data-new=tutorial]');await startMode(page,'tutorial');await playTutorial(page,{until:'compare'});
    await places(page,'noc');await clickSel(page,'[data-ws-tab=plan]');await page.waitForSelector('[data-propose]');await clickSel(page,'[data-propose]');
    let r=(await S(page)).game.requests[0];assert.equal(r.proposal.status,'pending');assert.match(r.modes.find(m=>m.key==='performance').reason,/협의 중/);
    await clickSel(page,'[data-ws-tab=plan]');await page.waitForSelector('[data-check-reply]');await clickSel(page,'[data-check-reply]');
    r=(await S(page)).game.requests[0];assert.ok(['accepted','rejected'].includes(r.proposal.status));
    await clickSel(page,'[data-ws-tab=plan]');await page.waitForTimeout(500);await shot('consent-after-reply.png');
    if(r.proposal.status==='accepted')assert.ok(await page.locator('[data-plan-option^="economy"]').count()>0,'economy selectable only after consent');
    assert.equal((await S(page)).game.datacenter.gpuUsed,0,'consent alone allocates nothing');await ctx.close();
  });

  await check('free mode runs the existing free rules (time-based arrivals) from the menu',async()=>{
    const {ctx,page}=await open();await page.waitForSelector('[data-new=free]');await startMode(page,'free');let s=await S(page);assert.equal(s.game.mode,'free');
    for(let i=0;i<3;i++)await clickSel(page,'[data-advance="30"]');s=await S(page);assert.equal(s.game.clock.label,'D1 10:30');assert.ok(s.game.requests.length>=2,'new requests arrived over time');
    await ctx.close();
  });

  for(const [width,height,dpr,label] of [[1366,768,1,'1366x768'],[1920,1080,1,'1920x1080'],[1920,1080,1.5,'1920x1080@150%']]){
    await check(`layout ${label}: highlighted control and coach visible without scrolling, no overlay overlap`,async()=>{
      const w=Math.round(width/dpr),h=Math.round(height/dpr);const {ctx,page,shot}=await open({width:w,height:h,dpr});
      await page.waitForSelector('[data-new=tutorial]');await startMode(page,'tutorial');const states=[];
      for(const stop of ['read','choose','rack','start','respond','verify']){
        await playTutorial(page,{until:stop});await page.waitForTimeout(500);
        const st=await page.evaluate(()=>{const sp=document.querySelector('.coach-spot'),c=document.querySelector('#coach'),inView=r=>r.top>=0&&r.left>=0&&r.bottom<=innerHeight&&r.right<=innerWidth;
          const res={spot:null,coach:null,pageScroll:document.documentElement.scrollHeight>innerHeight+2||document.documentElement.scrollWidth>innerWidth+2,timeButtons:[...document.querySelectorAll('[data-advance]')].every(b=>inView(b.getBoundingClientRect()))};
          if(sp){const r=sp.getBoundingClientRect(),big=r.height>innerHeight*.35,probe={x:r.left+Math.min(r.width/2,60),y:r.top+Math.min(r.height/2,24)},top=document.elementFromPoint(probe.x,probe.y);
            // Large containers (e.g. the plan list) must start on screen; small controls must be fully on screen.
            res.spot={big,inView:big?r.top>=0&&r.left>=0&&r.top<innerHeight-60&&r.right<=innerWidth:inView(r),topmost:sp===top||sp.contains(top)};}
          if(!c.hidden){const r=c.getBoundingClientRect();res.coach={inView:inView(r)};if(sp){const s=sp.getBoundingClientRect();res.coach.coversSpot=r.left<s.right&&s.left<r.right&&r.top<s.bottom&&s.top<r.bottom;}}
          const ws=document.querySelector('#workstation');if(ws&&!ws.hidden){const p=ws.querySelector('.ws-pane');res.workstation={tabsInView:[...ws.querySelectorAll('[data-ws-tab]')].every(b=>inView(b.getBoundingClientRect())),paneScroll:p.scrollHeight>p.clientHeight+2};}
          return res;});
        const s=await S(page);st.step=s.game.journey.current.id;st.ring=s.coach.ring;states.push(st);await shot(`layout-${label.replace('@','-').replace('%','pct')}-${stop}.png`);
        assert.equal(st.pageScroll,false,`${stop}: no page scroll`);assert.ok(st.timeButtons,`${stop}: time buttons visible`);
        if(st.spot){assert.ok(st.spot.inView,`${stop}: highlighted control in view`);assert.ok(st.spot.topmost,`${stop}: highlighted control not covered`);}else assert.ok(st.ring,`${stop}: 3D target ring shown`);
        if(st.coach){assert.ok(st.coach.inView,`${stop}: coach in view`);assert.ok(!st.coach.coversSpot,`${stop}: coach does not cover the target`);}
        if(st.workstation)assert.ok(st.workstation.tabsInView,`${stop}: monitor tabs in view`);
      }
      report.viewports.push({label,css:`${w}x${h}`,dpr,states});await ctx.close();
    });
  }

  await check('regression: 8 spaces navigate, campus cooling ops consistent, rack canvas picking from hall views, interiors',async()=>{
    const {ctx,page}=await open();await page.waitForSelector('[data-new=free]');await startMode(page,'free');
    const routes=[];for(const r of ['world','campus','noc','hall'])routes.push((await places(page,r),(await S(page)).renderer.location));assert.deepEqual(routes,['world','campus','noc','hall']);
    for(const view of ['overview','hall']){await clickSel(page,`[data-camera=${view}]`);await page.waitForTimeout(1300);await canvasClick(page,'rack','C-01');assert.equal((await S(page)).state.facility.selectedId,'C-01',`pick in ${view}`);await canvasClick(page,'rack','A-03');assert.equal((await S(page)).state.facility.selectedId,'A-03');}
    await places(page,'campus');await clickSel(page,'[data-facility=COOLING]');for(const [a,m]of [['cooling-off','off'],['cooling-on','on'],['cooling-warn','warn'],['cooling-reset','on']]){await clickSel(page,`[data-ops=${a}]`);await page.waitForTimeout(300);assert.equal((await S(page)).cooling.mode,m);}
    const rooms=[];for(const id of ['COOLING','POWER','UPS','NETWORK']){await places(page,'campus');await clickSel(page,`[data-facility=${id}]`);await clickSel(page,'#enter-building');await page.waitForTimeout(1300);rooms.push((await S(page)).interior?.room);}
    assert.deepEqual(rooms,['COOLING','POWER','UPS','NETWORK']);
    await clickSel(page,'#back');await clickSel(page,'[data-facility=NOC]');await clickSel(page,'#enter-building');await page.waitForTimeout(1000);assert.equal((await S(page)).state.navigation.route,'noc');
    await ctx.close();
  });

  await check('performance per space incl. interiors (avg >= 60 FPS), no long freeze, 10 navigation cycles keep resources bounded',async()=>{
    const {ctx,page}=await open();await page.waitForSelector('[data-new=free]');await startMode(page,'free');
    const spaces=[['world'],['campus'],['noc'],['hall'],['room','COOLING'],['room','NETWORK']];
    for(const [r,room]of spaces){if(r==='room'){await places(page,'campus');await clickSel(page,`[data-facility=${room}]`);await clickSel(page,'#enter-building');}else await places(page,r);await page.waitForTimeout(2600);const s=await S(page);report.performance.push({space:room||r,fps:+s.stats.fps.toFixed(1),p95:+s.stats.p95FrameMs.toFixed(2),max:+(s.stats.maxFrameMs??0).toFixed(1),calls:s.renderer.calls});assert.ok(s.stats.fps>=60,`${room||r} ${s.stats.fps}`);}
    const res=async()=>{const s=await S(page);return {g:s.renderer.geometries,t:s.renderer.textures};};await places(page,'world');const first=await res();
    for(let i=0;i<10;i++)for(const r of ['campus','noc','hall','world']){await clickSel(page,`#places [data-route=${r}]`);await page.waitForTimeout(250);}
    await page.waitForTimeout(1500);const last=await res();report.resources={first,last};assert.ok(last.g<=first.g+5&&last.t<=first.t+5,JSON.stringify({first,last}));
    await ctx.close();
  });

  await check('no runtime or console errors',async()=>{assert.deepEqual(report.errors,[]);assert.deepEqual(report.consoleErrors.filter(e=>!/favicon/.test(e)),[]);});
}catch(e){report.fatal=e.stack;console.error(e);}
finally{report.finishedAt=new Date().toISOString();await browser?.close();await stack?.stop();
  await writeFile(resolve(out,'phase4-qa.json'),JSON.stringify(report,null,2));const failed=report.checks.filter(c=>!c.pass).length;
  console.log(`${report.checks.length-failed} PASS / ${failed} FAIL`);process.exitCode=failed||report.fatal?1:0;}
