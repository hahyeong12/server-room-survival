import {chromium} from 'playwright-core';
import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
const exec=promisify(execFile);

const phase1=process.argv.includes('--phase1'),out=resolve('../../docs/3d-world-expansion/qa');await mkdir(out,{recursive:true});
const url=process.argv.find(x=>x.startsWith('--url='))?.slice(6)||'http://127.0.0.1:5173';
const report={mode:'Chrome headed / CDP mouse and keyboard / isolated profile',checks:[],errors:[],consoleErrors:[],screenshots:[],performance:[],startedAt:new Date().toISOString()};
let browser,page;
const snap=()=>page.evaluate(()=>window.worldQA.snapshot());
async function check(name,fn){try{await fn();report.checks.push({name,pass:true});console.log(`PASS ${name}`);}catch(e){report.checks.push({name,pass:false,error:e.message});throw e;}}
async function shot(name){await page.screenshot({path:resolve(out,name),fullPage:true});report.screenshots.push(name);}
async function go(route){await page.locator(`[data-route="${route}"]`).click();await page.waitForTimeout(1500);}
try{
  browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:false,args:['--window-size=1920,1080']});report.browserVersion=browser.version();
  page=await browser.newPage({viewport:{width:1920,height:1080},deviceScaleFactor:1});page.on('pageerror',e=>report.errors.push(e.message));page.on('console',m=>{if(m.type()==='error')report.consoleErrors.push(m.text());});
  await page.goto(url,{waitUntil:'networkidle'});await page.waitForFunction(()=>!!window.worldQA);await page.waitForTimeout(1000);report.url=url;
  // Phase 3.1: a fresh profile plays the opening once; this regression suite skips it (ux-qa.mjs tests it).
  if(await page.locator('#opening-skip').isVisible())await page.locator('#opening-skip').click();await page.waitForTimeout(2000);
  report.initial=await snap();
  await check('hardware WebGL on RTX 5070',async()=>assert.match(report.initial.renderer.renderer,/RTX 5070/));
  await check('readable title, request card rendered from state, gold incoming SG marker',async()=>{
    assert.equal(await page.title(),'서버실 생존기 · 3D World');
    const r=report.initial.state.request;
    for(const key of ['gpu','powerKW','networkGbps']){const term=page.locator(`[data-term="${key}"]`);assert.equal(await term.innerText(),String(r.terms[key]));assert.equal(await term.evaluate(e=>getComputedStyle(e).fontSize),'25px');}
    assert.equal(await page.locator('#request-location').innerText(),`${r.facilityId} / ${r.buildingId} / ${r.rackId}`);
    assert.equal(report.initial.state.request.phase,'new');assert.equal((await snap()).worldMarkers.SG,'f3c37b');
  });
  await check('four scenes and unchanged domain after navigation and idle',async()=>{
    const before=(await snap()).domain;
    for(const route of ['world','noc','campus','hall']){await go(route);const s=await snap();assert.equal(s.renderer.location,route);assert.equal(s.state.navigation.route,route);assert.deepEqual(s.domain,before);await shot(`phase1-${route}.png`);}
  });
  await check('breadcrumb and upper return: hall > campus > world',async()=>{
    assert.equal(await page.locator('[data-crumb]').count(),3);
    for(const route of ['campus','world']){await page.locator('#back').click();await page.waitForTimeout(1300);assert.equal((await snap()).state.navigation.route,route);}
    assert.equal(await page.locator('#back').isDisabled(),true);
  });
  await check('map node selection uses real canvas click',async()=>{
    const p=await page.evaluate(()=>worldQA.projectWorld('JP'));await page.mouse.click(p.x,p.y);assert.equal((await snap()).state.navigation.country,'JP');
    await page.locator('[data-country="SG"]').click();assert.equal((await snap()).state.navigation.country,'SG');
  });
  await check('campus building and original rack selection',async()=>{
    await go('campus');await page.locator('[data-facility="COOLING"]').click();assert.equal((await snap()).state.navigation.facility,'COOLING');await page.locator('[data-facility="HALL-01"]').click();await page.locator('#enter-building').click();await page.waitForTimeout(1600);
    const p=await page.evaluate(()=>worldQA.projectAsset('D-06'));await page.mouse.click(p.x,p.y);assert.equal((await snap()).state.facility.selectedId,'D-06');
  });
  if(!phase1){
    await check('per-scene FPS / frame time / GPU timer measured on the real canvas (avg >= 60 FPS)',async()=>{
      for(const route of ['world','noc','campus','hall']){
        await go(route);await page.waitForTimeout(2000);const samples=[];
        for(let n=0;n<5;n++){await page.waitForTimeout(1000);const s=await snap();samples.push({...s.stats,heapMiB:s.heap?+(s.heap.used/1048576).toFixed(1):null,calls:s.renderer.calls,triangles:s.renderer.triangles,geometries:s.renderer.geometries,textures:s.renderer.textures,canvas:`${s.renderer.width}x${s.renderer.height}`,dpr:s.renderer.dpr});}
        let nvidia=null;try{nvidia=(await exec('nvidia-smi',['--query-gpu=name,utilization.gpu,memory.used,memory.total','--format=csv,noheader,nounits'],{windowsHide:true})).stdout.trim();}catch(e){nvidia=`미측정: ${e.message}`;}
        const fps=samples.map(x=>x.fps),summary={fpsAvg:+(fps.reduce((a,b)=>a+b,0)/fps.length).toFixed(1),fpsMin:+Math.min(...fps).toFixed(1),p95FrameMsMax:+Math.max(...samples.map(x=>x.p95FrameMs)).toFixed(2),gpuMsAvg:samples.every(x=>x.gpuMs!=null)?+(samples.reduce((a,x)=>a+x.gpuMs,0)/samples.length).toFixed(2):null,calls:samples.at(-1).calls,triangles:samples.at(-1).triangles,canvas:samples.at(-1).canvas,nvidiaSmiWholeGpu:nvidia};
        report.performance.push({route,summary,samples});console.log(`PERF ${route} ${JSON.stringify(summary)}`);
        assert.ok(summary.fpsAvg>=60,`${route} avg FPS ${summary.fpsAvg}`);
      }
    });
    await check('10 navigation cycles keep geometries/textures bounded and domain unchanged',async()=>{
      await go('hall');await page.waitForTimeout(1000);const before=await snap();
      for(let i=0;i<10;i++)for(const route of ['world','noc','campus','hall']){await page.locator(`[data-route="${route}"]`).click();await page.waitForTimeout(250);}
      await page.waitForTimeout(1500);const after=await snap();
      report.stability={cycles:10,before:{geometries:before.renderer.geometries,textures:before.renderer.textures,heapMiB:before.heap&&+(before.heap.used/1048576).toFixed(1)},after:{geometries:after.renderer.geometries,textures:after.renderer.textures,heapMiB:after.heap&&+(after.heap.used/1048576).toFixed(1)}};
      assert.equal(after.renderer.geometries,before.renderer.geometries);assert.equal(after.renderer.textures,before.renderer.textures);assert.deepEqual(after.domain,before.domain);
      if(before.heap)assert.ok(after.heap.used-before.heap.used<32*1048576,'JS heap growth < 32 MiB');
    });
    await check('SG click-only walkthrough with immutable IDs, terms and synchronized scenes',async()=>{
      await go('world');await page.locator('[data-country="SG"]').click();
      const initial=(await snap()).state.request;
      for(const [action,route,phase]of [['review','world','reviewed'],['accept','noc','accepted'],['start','hall','running'],['advance','hall','fault'],['repair','hall','repairing'],['repair-complete','hall','awaiting'],['verify','hall','recovered'],['finish','hall','completed'],['report','noc','reported']]){
        await go(route);
        if(route==='hall')await page.locator('#equipment-select').selectOption('D-06');
        const button=page.locator(`[data-action="${action}"]`);assert.equal(await button.isEnabled(),true);await button.click();await page.waitForTimeout(300);
        const state=(await snap()).state;assert.equal(state.request.phase,phase);assert.equal(state.request.id,initial.id);assert.equal(state.request.customerId,initial.customerId);assert.equal(state.request.rackId,initial.rackId);assert.deepEqual(state.request.terms,initial.terms);
        await shot(`demo-${phase}.png`);
        if(['fault','repairing','awaiting'].includes(phase)){
          const before=(await snap()).domain;
          await page.waitForTimeout(1200);assert.deepEqual((await snap()).domain,before);
          for(const place of ['world','noc','campus','hall']){await go(place);assert.deepEqual((await snap()).domain,before);assert.equal(await page.locator('#phase-chip').innerText(),({fault:'업링크 장애',repairing:'복구 중',awaiting:'사후 확인 대기'})[phase]);if(phase==='fault')await shot(`sync-fault-${place}.png`);}
          const s=await snap();if(phase==='fault'){assert.equal(s.visuals['D-06'].networkFlow,false);assert.equal(s.state.facility.assets.find(a=>a.id==='D-06').state,'fault');assert.equal(s.worldMarkers.SG,'ff657d');}
        }
      }
      assert.equal((await snap()).state.request.steps,9);assert.equal(await page.locator('#demo-result').count(),1);
      assert.equal((await snap()).worldMarkers.SG,'68dfce');
      assert.equal(await page.locator('#demo-result li').count(),9);assert.match(await page.locator('#demo-result').innerText(),/GPU 8 · 20 kW · 40 Gbps/);
      assert.match(await page.locator('.inbox-row').innerText(),/결과 확인 완료/);await page.waitForTimeout(300);
      const box=await page.locator('#demo-result').boundingBox();assert.ok(box.y>=0&&box.y+box.height<=1080,`result card in view: ${JSON.stringify(box)}`);await shot('demo-result-noc.png');
      await page.locator('#result-world').click();await page.waitForTimeout(1500);assert.equal((await snap()).state.navigation.route,'world');assert.equal(await page.locator('#demo-result').isVisible(),true);assert.equal(await page.locator('#result-world').count(),0);await shot('demo-result-world.png');
    });
  }
  await check('no runtime or console errors',async()=>{assert.deepEqual(report.errors,[]);assert.deepEqual(report.consoleErrors,[]);});
  report.final=await snap();
}catch(e){report.failure=e.stack||e.message;process.exitCode=1;console.error(e);}
finally{if(browser)await browser.close();report.finishedAt=new Date().toISOString();await writeFile(resolve(out,phase1?'phase1.json':'world-qa.json'),JSON.stringify(report,null,2));console.log(JSON.stringify({passed:report.checks.filter(c=>c.pass).length,failed:report.checks.filter(c=>!c.pass).length,failure:report.failure}));}
