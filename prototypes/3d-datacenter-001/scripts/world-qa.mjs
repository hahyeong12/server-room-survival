import {chromium} from 'playwright-core';
import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';

const phase1=process.argv.includes('--phase1'),out=resolve('../../docs/3d-world-expansion/qa');await mkdir(out,{recursive:true});
const report={mode:'Chrome headed / CDP mouse and keyboard / isolated profile',checks:[],errors:[],consoleErrors:[],screenshots:[],performance:[],startedAt:new Date().toISOString()};
let browser,page;
const snap=()=>page.evaluate(()=>window.worldQA.snapshot());
async function check(name,fn){try{await fn();report.checks.push({name,pass:true});console.log(`PASS ${name}`);}catch(e){report.checks.push({name,pass:false,error:e.message});throw e;}}
async function shot(name){await page.screenshot({path:resolve(out,name),fullPage:true});report.screenshots.push(name);}
async function go(route){await page.locator(`[data-route="${route}"]`).click();await page.waitForTimeout(1500);}
try{
  browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:false,args:['--window-size=1920,1080']});report.browserVersion=browser.version();
  page=await browser.newPage({viewport:{width:1920,height:1080},deviceScaleFactor:1});page.on('pageerror',e=>report.errors.push(e.message));page.on('console',m=>{if(m.type()==='error')report.consoleErrors.push(m.text());});
  await page.goto('http://127.0.0.1:5173',{waitUntil:'networkidle'});await page.waitForFunction(()=>!!window.worldQA);await page.waitForTimeout(3000);
  report.initial=await snap();
  await check('hardware WebGL on RTX 5070',async()=>assert.match(report.initial.renderer.renderer,/RTX 5070/));
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
  await check('no runtime or console errors',async()=>{assert.deepEqual(report.errors,[]);assert.deepEqual(report.consoleErrors,[]);});
  report.final=await snap();
}catch(e){report.failure=e.stack||e.message;process.exitCode=1;console.error(e);}
finally{if(browser)await browser.close();report.finishedAt=new Date().toISOString();await writeFile(resolve(out,phase1?'phase1.json':'world-qa.json'),JSON.stringify(report,null,2));console.log(JSON.stringify({passed:report.checks.filter(c=>c.pass).length,failed:report.checks.filter(c=>!c.pass).length,failure:report.failure}));}
