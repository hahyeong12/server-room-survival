// DEVELOPMENT probe (not the reported QA): one incident practice played through the real UI, screenshots to scratch.
import {chromium} from 'playwright-core';
import {startStack,CHROME,settle} from './qa-lib.mjs';
import * as U from './phase7-ui.mjs';
const out=process.argv.find(x=>x.startsWith('--out='))?.slice(6)||'.';const type=process.argv.find(x=>x.startsWith('--type='))?.slice(7)||'cooling';
const stack=await startStack({enginePort:8797,vitePort:5197});const browser=await chromium.launch({executablePath:CHROME,headless:false,args:['--window-size=1920,1080']});
const errors=[];
try{
  const ctx=await browser.newContext({viewport:{width:1920,height:1080}});await ctx.addInitScript(()=>{try{localStorage.setItem('srs3d.opening.seen.v1','1');}catch{}});
  const page=await ctx.newPage();page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
  await page.goto(stack.url);await page.waitForFunction(()=>!!window.worldQA);await page.waitForTimeout(1200);
  await page.waitForSelector('[data-incident-practice]');await page.selectOption('[data-incident-practice]',type);await U.click(page,'[data-new=incident_practice]');await page.waitForTimeout(800);
  await page.screenshot({path:`${out}/dev-1-briefing.png`});
  await U.talkThrough(page);
  const rid=(await U.G(page)).requests[0].id;await U.startJob(page,rid,'performance');
  await U.until(page,g=>g.incident.records[0].state!=='armed');
  const id=(await U.incs(page))[0].id;await U.incidentTab(page,id);await page.screenshot({path:`${out}/dev-2-alert.png`});
  await U.ack(page,id);await page.screenshot({path:`${out}/dev-3-scope.png`});
  const ev=await U.observe(page,id,'cooling');await page.screenshot({path:`${out}/dev-4-room.png`});console.log('ev',ev.status,ev.summary);
  console.log('h',(await U.hypothesis(page,id,'gpu_health')).verdict);
  console.log('h',(await U.hypothesis(page,id,'cooling')).verdict);
  console.log('a',(await U.act(page,id,'standby_pump'))?.result);
  console.log('a',(await U.act(page,id,'escalate_facility'))?.result);await U.advance(page,10);
  console.log('a',(await U.act(page,id,'standby_pump'))?.result);await page.screenshot({path:`${out}/dev-5-actions.png`});
  await U.until(page,g=>g.incident.records[0].state==='monitoring');await U.advance(page,10);
  await U.observe(page,id,'cooling');await U.observe(page,id,'dcgm');
  console.log('v',(await U.verify(page,id)).state);console.log('r',(await U.report(page,id)).state);
  await U.until(page,g=>g.global.done,20);await page.waitForTimeout(500);await page.screenshot({path:`${out}/dev-6-result.png`});
  console.log('screen',(await U.S(page)).screens.open,'errors',errors);
}catch(e){console.log('ERR',e.message);}finally{await browser.close();await stack.stop();}
console.log('errors',errors);
