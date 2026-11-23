// Issue #2 (Phase 3.1) browser QA: opening, my desk, separate buildings, facility panels, cooling feedback.
// Real Chrome, headed, 1920x1080 DPR1, isolated profile. State changes only through real UI events;
// window.worldQA is read-only (state copies, projections, visual flags).
import {chromium} from 'playwright-core';
import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
const exec=promisify(execFile);
const url=process.argv.find(x=>x.startsWith('--url='))?.slice(6)||'http://127.0.0.1:5173';
const out=resolve('../../docs/3d-world-expansion/qa/phase3-1');await mkdir(out,{recursive:true});
const report={issue:2,mode:'Chrome headed / Playwright CDP mouse+keyboard / isolated profile / 1920x1080 DPR1',url,checks:[],errors:[],consoleErrors:[],screenshots:[],performance:[],timings:{},startedAt:new Date().toISOString()};
let browser,page;
const snap=()=>page.evaluate(()=>window.worldQA.snapshot());
const requestOf=s=>JSON.stringify(s.domain.request);
async function check(name,fn){try{await fn();report.checks.push({name,pass:true});console.log(`PASS ${name}`);}catch(e){report.checks.push({name,pass:false,error:e.message});console.log(`FAIL ${name}: ${e.message}`);throw e;}}
async function shot(name){await page.screenshot({path:resolve(out,name)});report.screenshots.push(name);}
async function go(route){await page.locator(`#places [data-route="${route}"]`).click();await page.waitForTimeout(1500);}
async function perf(label,seconds=4){await page.waitForTimeout(1500);const samples=[];for(let i=0;i<seconds;i++){await page.waitForTimeout(1000);const s=await snap();samples.push({fps:+s.stats.fps.toFixed(1),p95:+s.stats.p95FrameMs.toFixed(2),gpuMs:s.stats.gpuMs==null?null:+s.stats.gpuMs.toFixed(2),calls:s.renderer.calls,triangles:s.renderer.triangles});}
  const fps=samples.map(x=>x.fps),summary={label,fpsAvg:+(fps.reduce((a,b)=>a+b,0)/fps.length).toFixed(1),fpsMin:Math.min(...fps),p95Max:Math.max(...samples.map(x=>x.p95)),gpuMsAvg:samples.every(x=>x.gpuMs!=null)?+(samples.reduce((a,x)=>a+x.gpuMs,0)/samples.length).toFixed(2):null,calls:samples.at(-1).calls,triangles:samples.at(-1).triangles};
  report.performance.push({...summary,samples});console.log(`PERF ${JSON.stringify(summary)}`);return summary;}
async function coolingEverywhere(mode,label){
  // campus panel, 3D plant, right mini status, my monitor tile, server-building chip: same state, text + icon (not colour only)
  const s=await snap();assert.equal(s.state.ops.cooling.mode,mode);assert.equal(s.cooling.mode,mode);
  assert.equal(s.cooling.flowVisible,mode!=='off');assert.equal(s.cooling.fanSpeed>0,mode!=='off');assert.equal(s.cooling.icon,mode);
  assert.match(await page.locator('#cooling-status').innerText(),new RegExp(label));
  if(await page.locator('[data-panel="COOLING"]').count())assert.equal(await page.locator('[data-panel="COOLING"] .cool-badge').getAttribute('data-mode'),mode);
}
try{
  browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:false,args:['--window-size=1920,1080']});report.browserVersion=browser.version();
  const context=await browser.newContext({viewport:{width:1920,height:1080},deviceScaleFactor:1});page=await context.newPage();
  page.on('pageerror',e=>report.errors.push(e.message));page.on('console',m=>{if(m.type()==='error')report.consoleErrors.push(m.text());});
  await page.goto(url,{waitUntil:'domcontentloaded'});await page.waitForFunction(()=>!!window.worldQA);
  const t0=Date.now();

  await check('first visit plays the opening: world traffic -> Ulsan -> industrial district -> campus -> my desk',async()=>{
    let s=await snap();assert.equal(s.opening.active,true);assert.equal(await page.locator('#opening').isVisible(),true);assert.equal(await page.locator('#opening-skip').isVisible(),true);
    const before=JSON.stringify(s.domain),seen=new Set();
    const shotAt=new Set();
    while(s.opening.active){
      const idx=s.opening.state?.index;if(idx!=null){seen.add(s.renderer.location);
        if(!shotAt.has(idx)&&s.opening.state.t>.9){shotAt.add(idx);await shot(`opening-${idx+1}-${s.renderer.location}.png`);
          if(idx===2)report.performance.push({label:'opening (campus/district segment)',fps:+s.stats.fps.toFixed(1),p95:+s.stats.p95FrameMs.toFixed(2),calls:s.renderer.calls,triangles:s.renderer.triangles});}}
      await page.waitForTimeout(120);s=await snap();}
    report.timings.openingShots=[...shotAt];
    await page.waitForFunction(()=>!window.worldQA.snapshot().opening.active,null,{timeout:20000});s=await snap();
    report.timings.openingNatural=s.opening.result;assert.equal(s.opening.result.how,'completed');assert.ok(s.opening.result.seconds>=8&&s.opening.result.seconds<=15,`opening ${s.opening.result.seconds}s`);
    for(const loc of ['world','campus','noc'])assert.ok(seen.has(loc),`opening visited ${loc}`);
    assert.equal(s.state.navigation.route,'noc');assert.equal(s.state.navigation.nocView,'desk');assert.equal(JSON.stringify(s.domain),before,'opening never changes request/facility/ops');
    assert.equal(await page.locator('#workstation').isVisible(),true);report.timings.firstDeskAfterLoadMs=Date.now()-t0;if(await page.locator('#coach-skip').isVisible())await page.locator('#coach-skip').click();await page.waitForTimeout(800);await shot('desk-start.png');
  });
  await check('my desk is the work entry point: role, what to do now, request from state, facility watch',async()=>{
    const s=await snap(),r=s.state.request;
    for(const text of ['지금 할 일',r.id,r.customerName,`GPU ${r.terms.gpu} · ${r.terms.powerKW} kW · ${r.terms.networkGbps} Gbps`,'배정 검토','시설 감시'])assert.ok((await page.locator('#workstation').innerText()).includes(text),`workstation shows ${text}`);
    assert.equal(await page.locator('#ws-todo').innerText(),'요청 국가 확인');assert.ok((await page.locator('#workstation').innerText()).includes('오른쪽 아래 [요청 국가 보기]'),'monitor points to the single primary button');
    assert.equal(await page.locator('#primary-action').isEnabled(),true);
    assert.match(s.deskScreen,/^new:0:on:192$/,'3D desk monitors show the same request and cooling state');
    const box=await page.locator('#workstation').boundingBox();assert.ok(box.width>=900&&box.y>=0&&box.y+box.height<=1080,'monitor fully on screen');
  });
  await check('opening is not forced again; replay works and Esc skips straight to my desk',async()=>{
    await page.reload({waitUntil:'domcontentloaded'});await page.waitForFunction(()=>!!window.worldQA);await page.waitForTimeout(1500);
    let s=await snap();assert.equal(s.opening.active,false);assert.equal(s.state.navigation.route,'noc');assert.equal(await page.locator('#workstation').isVisible(),true);
    await page.locator('#opening-replay').click();await page.waitForTimeout(3000);s=await snap();assert.equal(s.opening.active,true);
    await page.keyboard.press('Escape');await page.waitForTimeout(400);s=await snap();assert.equal(s.opening.active,false);assert.equal(s.opening.result.how,'skipped');
    assert.equal(s.state.navigation.route,'noc');assert.equal(s.renderer.nocView,'desk');assert.equal(s.renderer.cinematic,false);
    await page.locator('#opening-replay').click();await page.waitForTimeout(1200);await page.locator('#opening-skip').click();await page.waitForTimeout(400);assert.equal((await snap()).opening.active,false);
    report.timings.replay='Esc and skip button both end at my desk';
  });
  await check('desk and wide NOC views are both reachable; the control room reads as staffed',async()=>{
    await page.locator('#noc-tools [data-noc-view="overview"]').click();await page.waitForTimeout(1500);let s=await snap();assert.equal(s.renderer.nocView,'overview');assert.equal(await page.locator('#workstation').isVisible(),false);await shot('noc-overview.png');
    await page.locator('#noc-tools [data-noc-view="desk"]').click();await page.waitForTimeout(1500);s=await snap();assert.equal(s.renderer.nocView,'desk');assert.equal(await page.locator('#workstation').isVisible(),true);
  });
  await check('request arrives on my monitor; review and accept at my desk; world map overlay optional',async()=>{
    await page.locator('#primary-action').click();await page.waitForTimeout(1500);let s=await snap();assert.equal(s.state.navigation.route,'world');assert.equal(s.state.navigation.country,'SG');assert.equal(s.worldMarkers.SG,'f3c37b');await shot('world-sg-request.png');
    await go('noc');s=await snap();assert.equal(s.state.navigation.nocView,'desk');
    await page.locator('#secondary-actions [data-action="review"]').click();await page.waitForTimeout(300);await page.locator('#primary-action[data-action="accept"]').click();await page.waitForTimeout(300);
    s=await snap();assert.equal(s.state.request.phase,'accepted');assert.equal(s.state.request.steps,2);await shot('desk-accepted.png');
  });
  await check('control and server buildings are distinct: clipping, boundary wall, transit card, different roles',async()=>{
    const pre=await page.evaluate(()=>({route:worldQA.snapshot().state.navigation.route,phase:worldQA.snapshot().state.request.phase,btn:document.querySelector('#primary-action').dataset.target}));await page.locator('#primary-action[data-target="hall"]').click();await page.waitForTimeout(250);const post=await page.evaluate(()=>({route:worldQA.snapshot().state.navigation.route,hidden:document.querySelector('#transit').hidden}));assert.equal(await page.locator('#transit').isVisible(),true,JSON.stringify({pre,post}));assert.match(await page.locator('#transit').innerText(),/연결 통로/);await shot('transit-to-hall.png');
    await page.waitForTimeout(1500);let s=await snap();assert.equal(s.state.navigation.route,'hall');assert.deepEqual(s.renderer.clip,[{normal:[-1,0,0],constant:4.2},{normal:[0,-1,0],constant:3.93}]);assert.equal(await page.locator('#hall-tools').isVisible(),true);assert.equal(await page.locator('#workstation').isVisible(),false);
    await go('noc');s=await snap();assert.deepEqual(s.renderer.clip,[{normal:[1,0,0],constant:-4.12}]);assert.equal(await page.locator('#hall-tools').isVisible(),false);assert.equal(await page.locator('#workstation').isVisible(),true);
    const crumbsHall=['world','campus','hall'];await go('hall');assert.deepEqual(await page.locator('[data-crumb]').evaluateAll(n=>n.map(x=>x.dataset.crumb)),crumbsHall);
    await go('campus');s=await snap();assert.deepEqual(s.renderer.clip,[]);assert.equal(s.renderer.fog,true);
  });
  await check('every campus building is clickable in 3D and opens a working panel',async()=>{
    const before=requestOf(await snap()),picked={};
    for(const id of ['NOC','HALL-01','POWER','UPS','COOLING','NETWORK']){
      await page.locator(`[data-facility="${id}"]`).click();await page.waitForTimeout(400);
      await go('campus');const p=await page.evaluate(id=>worldQA.projectWorld(id),id);await page.mouse.click(p.x,p.y);await page.waitForTimeout(1300);
      picked[id]=(await snap()).state.navigation.facility;
      await page.locator(`[data-facility="${id}"]`).click();await page.waitForTimeout(1300);
      assert.equal(await page.locator(`[data-panel="${id}"]`).isVisible(),true);
      const actions=await page.locator(`[data-panel="${id}"] button, #enter-building`).count();assert.ok(actions>=1,`${id} has an action`);
    }
    report.canvasPicks=picked;const hits=Object.entries(picked).filter(([k,v])=>k===v).length;assert.ok(hits>=4,`canvas picks hit ${hits}/6: ${JSON.stringify(picked)}`);
    await page.locator('[data-facility="POWER"]').click();await page.locator('[data-ops="power-check"]').click();assert.match(await page.locator('[data-panel="POWER"] .ops-result').innerText(),/전력 계통 점검 완료/);await shot('facility-power.png');
    await page.locator('[data-facility="UPS"]').click();await page.locator('[data-ops="ups-test"]').click();assert.match(await page.locator('[data-panel="UPS"] .ops-result').innerText(),/UPS 자가진단 정상/);await shot('facility-ups.png');
    await page.locator('[data-facility="NETWORK"]').click();await page.locator('[data-ops="network-lookup"]').click();assert.match(await page.locator('[data-panel="NETWORK"] .ops-result').innerText(),/활성 네트워크 장애 없음/);await shot('facility-network-ok.png');
    await page.locator('[data-facility="HALL-01"]').click();assert.match(await page.locator('[data-panel="HALL-01"]').innerText(),/D-06/);
    await page.locator('[data-facility="NOC"]').click();await page.locator('#enter-building').click();await page.waitForTimeout(1500);assert.equal((await snap()).state.navigation.route,'noc');
    assert.equal(requestOf(await snap()),before,'facility checks never change the request');
  });
  await check('auxiliary cooling ON / OFF / WARN: instant, consistent icon + LED + text + numbers in plant, panel, my monitor, server building',async()=>{
    await go('campus');await page.locator('[data-facility="COOLING"]').click();await page.waitForTimeout(1500);
    await coolingEverywhere('on','켜짐');await shot('cooling-on.png');const before=requestOf(await snap());
    const steps=[['cooling-off','off','꺼짐'],['cooling-on','on','켜짐'],['cooling-warn','warn','경고']];
    report.timings.coolingFeedbackMs={};
    for(const [action,mode,label]of steps){
      const t=Date.now();await page.locator(`[data-ops="${action}"]`).click();
      await page.waitForFunction(m=>{const s=window.worldQA.snapshot();return s.cooling?.mode===m&&document.querySelector('[data-panel="COOLING"] .cool-badge')?.dataset.mode===m;},mode);report.timings.coolingFeedbackMs[mode]=Date.now()-t;
      await coolingEverywhere(mode,label);
      const panel=await page.locator('[data-panel="COOLING"]').innerText();assert.ok(panel.includes(`보조 냉각 ${label}`));
      if(mode==='off')assert.match(panel,/냉각수 유량\s+0 L\/min/);if(mode==='warn'){assert.match(panel,/12 L\/min/);assert.match(panel,/진단: 냉각수 유량 저하/);}
      await page.waitForTimeout(700);await shot(`cooling-${mode}${mode==='on'?'-again':''}.png`);
      await go('noc');assert.equal(await page.locator('[data-ws-tile="COOLING"] .cool-badge').getAttribute('data-mode'),mode);assert.match(await page.locator('[data-ws-tile="COOLING"]').innerText(),new RegExp(label));
      assert.match((await snap()).deskScreen,new RegExp(`:${mode}:`));if(mode!=='on')await shot(`desk-cooling-${mode}.png`);
      await go('hall');assert.equal(await page.locator('#cooling-status').getAttribute('data-mode'),mode);if(mode==='warn')await shot('hall-cooling-warn.png');
      await go('campus');await page.locator('[data-facility="COOLING"]').click();await page.waitForTimeout(300);
    }
    await page.locator('[data-ops="cooling-reset"]').click();await coolingEverywhere('on','켜짐');
    assert.equal(requestOf(await snap()),before,'cooling demo never changes the request');
    assert.ok(Object.values(report.timings.coolingFeedbackMs).every(ms=>ms<1000),'feedback < 1 s');
  });
  await check('SG request end to end from my desk: hall work, fault, network cause lookup, repair, result on my monitor',async()=>{
    await go('noc');await page.locator('#primary-action[data-target="hall"]').click();await page.waitForTimeout(1700);
    await page.locator('#equipment-select').selectOption('D-06');
    for(const a of ['start','advance']){await page.locator(`[data-action="${a}"]`).click();await page.waitForTimeout(250);}
    let s=await snap();assert.equal(s.state.request.phase,'fault');
    await go('noc');assert.equal(await page.locator('[data-ws-tile="NETWORK"]').getAttribute('class'),'ws-tile bad');await shot('desk-fault.png');
    await go('campus');await page.locator('[data-facility="NETWORK"]').click();await page.locator('[data-ops="network-lookup"]').click();
    assert.match(await page.locator('[data-panel="NETWORK"] .ops-result').innerText(),/D-06 ToR 업링크 단절/);assert.match(await page.locator('[data-panel="NETWORK"]').innerText(),/싱가포르 회선\s+처리량 0/);await shot('facility-network-fault.png');
    await page.locator('#network-to-hall').click();await page.waitForTimeout(1600);assert.equal((await snap()).state.navigation.route,'hall');
    for(const a of ['repair','repair-complete','verify','finish']){await page.locator(`[data-action="${a}"]`).click();await page.waitForTimeout(250);}
    await go('noc');
    await page.locator('#primary-action[data-action="report"]').click();await page.waitForTimeout(500);s=await snap();
    assert.equal(s.state.request.phase,'reported');assert.equal(s.state.request.steps,9);assert.equal(await page.locator('#demo-result').isVisible(),true);assert.equal(await page.locator('#demo-result .result-timeline li').count(),9);
    await shot('desk-result.png');await page.locator('#result-close').click();
  });
  await check('performance per space incl. district and desk (avg >= 60 FPS) and 10-cycle resource stability',async()=>{
    await page.locator('#noc-tools [data-noc-view="desk"]').click();const results=[await perf('noc desk')];
    await page.locator('#noc-tools [data-noc-view="overview"]').click();results.push(await perf('noc overview'));
    for(const r of ['campus','hall','world']){await go(r);results.push(await perf(r));}
    for(const r of results)assert.ok(r.fpsAvg>=60,`${r.label} ${r.fpsAvg} FPS`);
    try{report.nvidiaSmiWholeGpu=(await exec('nvidia-smi',['--query-gpu=name,utilization.gpu,memory.used,memory.total','--format=csv,noheader,nounits'],{windowsHide:true})).stdout.trim();}catch(e){report.nvidiaSmiWholeGpu=`미측정: ${e.message}`;}
    await go('hall');const before=await snap();
    for(let i=0;i<10;i++)for(const r of ['world','campus','noc','hall']){await page.locator(`#places [data-route="${r}"]`).click();await page.waitForTimeout(220);}
    await page.waitForTimeout(1500);const after=await snap();
    report.stability={cycles:10,before:{geometries:before.renderer.geometries,textures:before.renderer.textures,heapMiB:+(before.heap.used/1048576).toFixed(1)},after:{geometries:after.renderer.geometries,textures:after.renderer.textures,heapMiB:+(after.heap.used/1048576).toFixed(1)}};
    assert.equal(after.renderer.geometries,before.renderer.geometries);assert.equal(after.renderer.textures,before.renderer.textures);assert.deepEqual(after.domain,before.domain);
  });
  await check('no runtime or console errors',async()=>{assert.deepEqual(report.errors,[]);assert.deepEqual(report.consoleErrors,[]);});
}catch(e){report.failure=e.stack||e.message;process.exitCode=1;}
finally{if(browser)await browser.close();report.finishedAt=new Date().toISOString();await writeFile(resolve(out,'ux-qa.json'),JSON.stringify(report,null,2));console.log(JSON.stringify({passed:report.checks.filter(c=>c.pass).length,failed:report.checks.filter(c=>!c.pass).length,failure:report.failure?.split('\n')[0]}));}
