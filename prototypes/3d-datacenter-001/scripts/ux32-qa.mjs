// Issue #3 (Phase 3.2) browser QA: first-time player run, no-scroll panel at several resolutions/scales,
// Korea-centred network map, rack targeting, single/double-click buildings + interiors, performance.
// Real Chrome (headed), Playwright CDP mouse/keyboard, isolated contexts. State changes only via UI events;
// window.worldQA is read-only. Windows display scaling is EMULATED with deviceScaleFactor (not a real OS change).
import {chromium} from 'playwright-core';
import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
const url=process.argv.find(x=>x.startsWith('--url='))?.slice(6)||'http://127.0.0.1:5173';
const out=resolve('../../docs/3d-world-expansion/qa/phase3-2');await mkdir(out,{recursive:true});
const report={issue:3,mode:'Chrome headed / Playwright CDP / isolated contexts',url,checks:[],errors:[],consoleErrors:[],screenshots:[],firstPlayer:null,viewports:[],performance:[],startedAt:new Date().toISOString()};
let browser;
async function check(name,fn){try{await fn();report.checks.push({name,pass:true});console.log(`PASS ${name}`);}catch(e){report.checks.push({name,pass:false,error:e.message});console.log(`FAIL ${name}: ${e.message.split('\n')[0]}`);}}
async function open({width=1920,height=1080,dpr=1,fresh=false,hash=''}={}){
  const ctx=await browser.newContext({viewport:{width,height},deviceScaleFactor:dpr});
  if(!fresh)await ctx.addInitScript(()=>{try{localStorage.setItem('srs3d.opening.seen.v1','1');localStorage.setItem('srs3d.tutorial.done.v1','1');}catch{}});
  const page=await ctx.newPage();page.on('pageerror',e=>report.errors.push(e.message));page.on('console',m=>{if(m.type()==='error')report.consoleErrors.push(m.text());});
  await page.goto(url+hash,{waitUntil:'domcontentloaded'});await page.waitForFunction(()=>!!window.worldQA);await page.waitForTimeout(1500);
  const snap=()=>page.evaluate(()=>window.worldQA.snapshot());
  const shot=async name=>{await page.screenshot({path:resolve(out,name)});report.screenshots.push(name);};
  return {ctx,page,snap,shot};
}
// Primary button must be fully on screen and topmost; the panel body must not need scrolling.
async function layoutState(page){
  return page.evaluate(()=>{const b=document.querySelector('#primary-action'),r=b.getBoundingClientRect(),top=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2),body=document.querySelector('#panel-body'),title=document.querySelector('#goal-title');
    return {inView:r.top>=0&&r.left>=0&&r.bottom<=innerHeight&&r.right<=innerWidth,topmost:top===b||b.contains(top),bodyNeedsScroll:body.scrollHeight>body.clientHeight+2,pageScroll:scrollY!==0||document.documentElement.scrollHeight>innerHeight+2,titleClipped:title.scrollWidth>title.clientWidth+1,rect:[Math.round(r.top),Math.round(r.bottom),innerHeight],label:b.textContent};});
}
try{
  browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:false,args:['--window-size=1920,1080']});report.browserVersion=browser.version();

  await check('first-time player: following only the single highlighted target finishes the first job (1920x1080)',async()=>{
    const {ctx,page,snap,shot}=await open({fresh:true});const t0=Date.now();
    assert.equal((await snap()).opening.active,true);await page.keyboard.press('Escape');await page.waitForTimeout(600);
    const fp={clicks:0,intentionalMisclicks:0,steps:[],scrollRequired:false};
    for(let i=0;i<30;i++){
      const s=await snap();if(s.guide.goal.done)break;
      const t=Date.now();await page.waitForFunction(()=>document.querySelectorAll('.coach-target').length===1&&!document.querySelector('#coach').hidden,null,{timeout:5000});
      const discoveryMs=Date.now()-t,coach=await page.locator('#coach-text').innerText(),lay=await layoutState(page);
      assert.ok(lay.inView&&lay.topmost,`target visible+clickable at step ${i}: ${JSON.stringify(lay)}`);if(lay.bodyNeedsScroll||lay.pageScroll)fp.scrollRequired=true;
      assert.ok(coach.length<=110,`one short sentence: ${coach}`);
      // One deliberate wrong click while looking for the rack: a specific hint, no progress, no penalty.
      if(s.guide.action.kind==='select-rack'&&!fp.intentionalMisclicks){
        await page.waitForTimeout(1200);const p=await page.evaluate(()=>worldQA.projectAsset('D-02'));await page.mouse.click(p.x,p.y);await page.waitForTimeout(300);
        const a=await snap();assert.equal(a.state.facility.selectedId,'D-02','a visible front-row rack is hit exactly');assert.equal(a.state.request.phase,s.state.request.phase);assert.equal(a.tutorial.misclicks,1);
        assert.match(await page.locator('#toast').innerText(),/D-06/);fp.intentionalMisclicks=1;await shot('fp-misclick-hint.png');
      }
      fp.steps.push({goal:s.guide.goal.index,action:s.guide.action.kind,label:lay.label,discoveryMs,route:s.state.navigation.route});
      await shot(`fp-step-${String(i+1).padStart(2,'0')}.png`);
      const box=await page.locator('.coach-target').boundingBox();await page.mouse.click(box.x+box.width/2,box.y+box.height/2);fp.clicks++;await page.waitForTimeout(1300);
    }
    const s=await snap();assert.equal(s.state.request.phase,'reported');assert.equal(s.guide.goal.done,true);assert.equal(await page.locator('#result-dialog').isVisible(),true);await shot('fp-result.png');
    assert.equal(s.tutorial.active,false);assert.equal(s.tutorial.ended,'completed');
    fp.totalSeconds=+((Date.now()-t0)/1000).toFixed(1);fp.maxDiscoveryMs=Math.max(...fp.steps.map(x=>x.discoveryMs));report.firstPlayer=fp;
    assert.equal(fp.scrollRequired,false,'no scrolling needed for any required action');assert.ok(fp.clicks<=16,`${fp.clicks} clicks`);
    console.log(`FIRSTPLAYER ${JSON.stringify({clicks:fp.clicks,seconds:fp.totalSeconds,maxDiscoveryMs:fp.maxDiscoveryMs,misclicks:fp.intentionalMisclicks})}`);
    await ctx.close();
  });

  for(const vp of [{width:1920,height:1080,dpr:1,label:'1920x1080 @100%'},{width:1366,height:768,dpr:1,label:'1366x768 @100%'},{width:1536,height:864,dpr:1.25,label:'1920x1080 @125% (emulated)'},{width:1280,height:720,dpr:1.5,label:'1920x1080 @150% (emulated)'}]){
    await check(`no scrolling for required actions, primary button visible and on top: ${vp.label}`,async()=>{
      const {ctx,page,snap,shot}=await open(vp);const rows=[];const tag=vp.label.replace(/[^0-9a-z]+/gi,'-');
      for(let i=0;i<20;i++){
        const s=await snap(),lay=await layoutState(page);rows.push({goal:s.guide.goal.index,label:lay.label,...lay});
        assert.ok(lay.inView&&lay.topmost,`${vp.label} step ${i}: ${JSON.stringify(lay)}`);assert.equal(lay.bodyNeedsScroll,false,`${vp.label} panel scroll at step ${i}`);assert.equal(lay.pageScroll,false);assert.equal(lay.titleClipped,false);
        if([0,4,8].includes(i))await shot(`vp-${tag}-step${i}.png`);
        if(s.guide.goal.done)break;await page.locator('#primary-action').click();await page.waitForTimeout(900);
        if(await page.locator('#result-dialog').isVisible()){await shot(`vp-${tag}-result.png`);const r=await page.locator('#result-close').boundingBox();assert.ok(r&&r.y+r.height<=vp.height,'result dialog button reachable');await page.locator('#result-close').click();}
      }
      assert.equal((await snap()).state.request.phase,'reported');report.viewports.push({...vp,steps:rows.length,maxButtonBottom:Math.max(...rows.map(r=>r.rect[1]))});await ctx.close();
    });
  }

  await check('Korea-centred map: dim background network, only the request path lit, fault only on the AIDC hop, reduced motion',async()=>{
    const {ctx,page,snap,shot}=await open({hash:'#world'});await page.waitForTimeout(1500);
    const geo=await page.evaluate(()=>{const c=document.querySelector('#viewport canvas').getBoundingClientRect(),k=worldQA.projectWorld('KR');return {cx:c.left+c.width/2,w:c.width,kx:k.x};});
    assert.ok(Math.abs(geo.kx-geo.cx)<geo.w*.1,`Ulsan near the horizontal centre of the visible map: ${JSON.stringify(geo)}`);
    let n=(await snap()).network;assert.equal(n.tone,'incoming');assert.equal(n.sea,'#f3c37b');assert.ok(n.background.links>=10&&n.background.opacity<=.6);assert.equal(n.packetsMoving,true);assert.equal(n.faultBadge,false);
    await shot('world-request-incoming.png');
    for(let i=0;i<7;i++){await page.locator('#primary-action').click();await page.waitForTimeout(900);}
    assert.equal((await snap()).state.request.phase,'fault');await page.locator('#places [data-route="world"]').click();await page.waitForTimeout(1600);
    n=(await snap()).network;assert.equal(n.hop,'#ff657d');assert.equal(n.sea,'#6fe7d2');assert.equal(n.faultBadge,true);assert.equal(n.aidcMarker,'#ff657d');
    assert.match(await page.locator('#route-chain [data-hop="aidc"]').getAttribute('class'),/bad/);assert.doesNotMatch(await page.locator('#route-chain [data-hop="sea"]').getAttribute('class'),/bad/);
    await shot('world-fault-aidc-hop.png');
    await page.locator('#motion-toggle').click();await page.waitForTimeout(300);assert.equal((await snap()).network.packetsMoving,false);
    await ctx.close();
  });

  await check('rack target: ceiling cut away, on-top outline + pin, canvas hits from several angles, keyboard and button alternatives, light not pickable',async()=>{
    const {ctx,page,snap,shot}=await open();for(let i=0;i<8&&(await snap()).guide.action.kind!=='select-rack';i++){await page.locator('#primary-action').click();await page.waitForTimeout(900);}
    let s=await snap();assert.equal(s.guide.action.kind,'select-rack');assert.equal(s.state.navigation.route,'hall');await page.waitForTimeout(1200);
    const rv=await snap();assert.deepEqual(rv.renderer.clip.map(c=>c.normal),[[-1,0,0],[0,-1,0]],'wall + ceiling cut');
    assert.equal(rv.rack.ceilingShown,false);assert.equal(rv.rack.targetOutline,true);assert.equal(rv.rack.targetOutlineOnTop,true);assert.equal(rv.rack.pin,true);assert.equal(rv.rack.pickVolumes,29,'28 exact bodies + 1 enlarged target volume');report.rackVisual=rv.rack;
    await page.locator('#ceiling-toggle').click();await page.waitForTimeout(500);await shot('rack-before-ceiling-shown.png');assert.deepEqual((await snap()).renderer.clip.map(c=>c.normal),[[-1,0,0]]);
    await page.locator('#ceiling-toggle').click();await page.waitForTimeout(500);await shot('rack-after-ceiling-cut.png');
    const hits={};
    for(const view of ['overview','hall']){
      await page.locator('#equipment-select').selectOption('A-01');await page.locator(`[data-camera="${view}"]`).click();await page.waitForTimeout(1600);
      const p=await page.evaluate(()=>worldQA.projectAsset('D-06'));await page.mouse.click(p.x,p.y);await page.waitForTimeout(300);hits[view]=(await snap()).state.facility.selectedId;await shot(`rack-hit-${view}.png`);
    }
    assert.deepEqual(hits,{overview:'D-06',hall:'D-06'});
    // overhead light position above row D: clicking it may only ever select a rack (lights are not pickable)
    await page.locator('#equipment-select').selectOption('A-01');const L=await page.evaluate(()=>worldQA.projectPoint([-6.6,4.33,5.5]));await page.mouse.click(L.x,L.y);await page.waitForTimeout(300);
    const afterLight=(await snap()).state.facility.selectedId;assert.match(afterLight,/^[A-D]-0[1-6]$/,'only racks are pickable');report.lightClickSelected=afterLight;
    // keyboard alternative: the equipment list
    await page.locator('#equipment-select').focus();await page.locator('#equipment-select').selectOption('D-06');assert.equal((await snap()).state.facility.selectedId,'D-06');
    await page.locator('#equipment-select').selectOption('A-01');await page.locator('#primary-action').click();await page.waitForTimeout(1500);
    s=await snap();assert.equal(s.state.facility.selectedId,'D-06');await shot('rack-focus-after-button.png');
    const panel=await page.locator('#context-card').innerText();assert.match(panel,/RACK D-06/);assert.match(panel,/요청 랙/);
    report.rackHits=hits;await ctx.close();
  });

  await check('buildings: single click informs without moving the camera; double click / Enter enters each own space; back returns',async()=>{
    const {ctx,page,snap,shot}=await open({hash:'#campus'});await page.waitForTimeout(1200);const r0=JSON.stringify((await snap()).domain.request);
    const expected={NOC:'noc','HALL-01':'hall',COOLING:'room',POWER:'room',UPS:'room',NETWORK:'room'},result={};
    for(const id of Object.keys(expected)){
      await page.locator('#places [data-route="campus"]').click();await page.waitForTimeout(1500);
      const cam=await page.evaluate(()=>worldQA.cameraState()),p=await page.evaluate(id=>worldQA.projectWorld(id),id);
      await page.mouse.click(p.x,p.y);await page.waitForTimeout(500);
      let s=await snap();assert.equal(s.state.navigation.facility,id,`single click selects ${id}`);assert.equal(s.state.navigation.route,'campus');
      assert.deepEqual(await page.evaluate(()=>worldQA.cameraState()),cam,'single click keeps the overview camera');
      assert.equal(await page.locator(`[data-panel="${id}"]`).isVisible(),true);assert.equal(await page.locator('#enter-building').isVisible(),true);await shot(`building-click-${id}.png`);
      await page.mouse.dblclick(p.x,p.y);await page.waitForTimeout(1700);s=await snap();
      assert.equal(s.state.navigation.route,expected[id]);if(expected[id]==='room'){assert.equal(s.state.navigation.room,id);assert.equal(s.interior.room,id);}
      result[id]={route:s.state.navigation.route,interior:s.interior};await shot(`building-inside-${id}.png`);
      if(id==='COOLING'){await page.locator('[data-ops="cooling-off"]').click();await page.waitForTimeout(400);s=await snap();assert.equal(s.interior.pumpsSpinning,false);assert.equal(s.interior.flowVisible,false);await shot('inside-cooling-off.png');await page.locator('[data-ops="cooling-on"]').click();await page.waitForTimeout(300);assert.equal((await snap()).interior.pumpsSpinning,true);}
      if(id==='POWER'){await page.locator('[data-ops="power-check"]').click();await page.waitForTimeout(300);assert.equal((await snap()).interior.checked,true);}
      if(id==='UPS'){await page.locator('[data-ops="ups-test"]').click();await page.waitForTimeout(300);assert.equal((await snap()).interior.checked,true);}
      if(id==='NETWORK'){const before=(await snap()).interior.display;await page.locator('[data-ops="network-lookup"]').click();await page.waitForTimeout(300);assert.notEqual((await snap()).interior.display,before);}
      await page.locator('#back').click();await page.waitForTimeout(1200);assert.equal((await snap()).state.navigation.route,'campus');
    }
    // keyboard alternative to double-click
    await page.locator('[data-facility="UPS"]').click();await page.locator('#viewport canvas').focus();await page.keyboard.press('Enter');await page.waitForTimeout(1200);
    let s=await snap();assert.equal(s.state.navigation.route,'room');assert.equal(s.state.navigation.room,'UPS');
    assert.equal(JSON.stringify(s.domain.request),r0,'buildings and interiors never change the request');report.buildings=result;await ctx.close();
  });

  await check('performance per space incl. four interiors (avg >= 60 FPS), no long freeze on building switch, 10-cycle stability',async()=>{
    const {ctx,page,snap}=await open();
    const measure=async label=>{await page.waitForTimeout(1800);const xs=[];for(let i=0;i<3;i++){await page.waitForTimeout(1000);xs.push((await snap()).stats);}const s=await snap();
      const row={label,fpsAvg:+(xs.reduce((a,x)=>a+x.fps,0)/xs.length).toFixed(1),p95Max:+Math.max(...xs.map(x=>x.p95FrameMs)).toFixed(2),maxFrameMs:+Math.max(...xs.map(x=>x.maxFrameMs)).toFixed(1),gpuMs:xs.at(-1).gpuMs==null?null:+xs.at(-1).gpuMs.toFixed(2),calls:s.renderer.calls,triangles:s.renderer.triangles};report.performance.push(row);console.log(`PERF ${JSON.stringify(row)}`);return row;};
    const rows=[];for(const r of ['noc','world','campus','hall'])
      {await page.locator(`#places [data-route="${r}"]`).click();rows.push(await measure(r));}
    for(const id of ['COOLING','POWER','UPS','NETWORK']){await page.locator('#places [data-route="campus"]').click();await page.waitForTimeout(800);await page.locator(`[data-facility="${id}"]`).click();await page.locator('#enter-building').click();rows.push(await measure(`room ${id}`));}
    for(const r of rows)assert.ok(r.fpsAvg>=60,`${r.label} ${r.fpsAvg}`);
    // the fixed freeze: control -> server building must not stall the main thread
    await page.locator('#places [data-route="noc"]').click();await page.waitForTimeout(2500);const t=Date.now();await page.locator('#places [data-route="hall"]').click();const clickMs=Date.now()-t;await page.waitForTimeout(400);
    const transit=await page.locator('#transit').isVisible();report.switchNocToHall={clickReturnMs:clickMs,transitVisibleAfter400ms:transit};assert.ok(clickMs<400&&transit,JSON.stringify(report.switchNocToHall));
    const before=await snap();for(let i=0;i<10;i++){for(const r of ['world','campus','noc','hall']){await page.locator(`#places [data-route="${r}"]`).click();await page.waitForTimeout(200);}await page.locator('[data-facility="COOLING"]').click().catch(()=>{});}
    await page.locator('#places [data-route="hall"]').click();await page.waitForTimeout(1500);const after=await snap();
    report.stability={cycles:10,before:{geometries:before.renderer.geometries,textures:before.renderer.textures,heapMiB:+(before.heap.used/1048576).toFixed(1)},after:{geometries:after.renderer.geometries,textures:after.renderer.textures,heapMiB:+(after.heap.used/1048576).toFixed(1)}};
    assert.equal(after.renderer.geometries,before.renderer.geometries);assert.equal(after.renderer.textures,before.renderer.textures);assert.deepEqual(after.domain.request,before.domain.request);
    await ctx.close();
  });
  await check('no runtime or console errors',async()=>{assert.deepEqual(report.errors,[]);assert.deepEqual(report.consoleErrors,[]);});
}catch(e){report.failure=e.stack||e.message;process.exitCode=1;}
finally{if(browser)await browser.close();report.finishedAt=new Date().toISOString();await writeFile(resolve(out,'ux32-qa.json'),JSON.stringify(report,null,2));
  const failed=report.checks.filter(c=>!c.pass).length;if(failed)process.exitCode=1;console.log(JSON.stringify({passed:report.checks.length-failed,failed}));}
