import {chromium} from 'playwright-core';
import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';

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
  await page.goto(url,{waitUntil:'networkidle'});await page.waitForFunction(()=>!!window.worldQA);await page.waitForTimeout(3000);report.url=url;
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
  await check('breadcrumb and upper return through all four levels',async()=>{
    assert.equal(await page.locator('[data-crumb]').count(),4);
    for(const route of ['campus','noc','world']){await page.locator('#back').click();await page.waitForTimeout(1300);assert.equal((await snap()).state.navigation.route,route);}
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
