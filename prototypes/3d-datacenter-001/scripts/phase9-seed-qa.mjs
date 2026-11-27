// Phase 9 supplementary browser QA: different seeds produce different REAL incidents (not "none vs some"), each one is
// diagnosed, recovered, verified and reported through the UI, and the same seed replays the same incidents.
// Only real UI actions change games; window.worldQA and SQLite (read-only, OS temp saves) are checks.
import {chromium} from 'playwright-core';
import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import {resolve,join} from 'node:path';
import {DatabaseSync} from 'node:sqlite';
import {startStack,CHROME,settle} from './qa-lib.mjs';
import * as U from './phase7-ui.mjs';
import {createFlows} from './phase9-flows.mjs';

const out=resolve(process.argv.find(x=>x.startsWith('--out='))?.slice(6)??'../../docs/3d-world-expansion/qa/phase9/seed-1');
await mkdir(out,{recursive:true});
const report={issue:10,kind:'phase9-seed',checks:[],errors:[],consoleErrors:[],commands:[],actions:[],shifts:[],runs:[],startedAt:new Date().toISOString()};
let stack,browser,page,ctx;
const F=createFlows(()=>page,report);
async function check(name,fn){const t=Date.now();try{await fn();report.checks.push({name,pass:true,ms:Date.now()-t});console.log(`PASS ${name}`);}catch(e){await page.screenshot({path:join(out,`FAIL-${report.checks.length}.png`)}).catch(()=>{});report.checks.push({name,pass:false,error:e.stack});console.log(`FAIL ${name}: ${e.message}`);throw e;}finally{await writeFile(join(out,'phase9-seed-qa.json'),JSON.stringify(report,null,2));}}
function payload(id){const db=new DatabaseSync(join(stack.saveDir,id+'.db'),{readOnly:true});try{return JSON.parse(db.prepare('SELECT payload FROM simulation_state WHERE id=1').get().payload);}finally{db.close();}}
async function menu(){await U.drain(page);if(await page.locator('#screen-dialog[open]').count()){await U.click(page,'#screen-dialog [data-next=menu]');await settle(page);}if(!await page.locator('#menu:not([hidden])').count())await U.click(page,'#menu-open');await page.waitForSelector('[data-new=global_free]');}
// One free shift: start every request, handle every incident through the UI, wrap up after `ticks` ten-minute steps.
async function play(seed,difficulty,ticks=12){
  await menu();await page.locator('[data-free-seed]').fill(String(seed));await page.selectOption('[data-free-difficulty]',difficulty);await U.click(page,'[data-new=global_free]');await page.waitForTimeout(500);
  await U.talkThrough(page);
  for(let n=0;n<ticks;n++){await F.startAvailable();await F.handleOpen();if((await U.G(page)).global.done)break;await U.advance(page,10);}
  if(!(await U.G(page)).global.closing)await U.click(page,'[data-free-end]');
  let g=await U.G(page);for(let i=0;i<40&&!g.global.done;i++){await F.startAvailable();await F.handleOpen();g=await U.G(page);if(!g.global.done){await U.advance(page,10);g=await U.G(page);}}
  assert.equal(g.global.done,true);const p=payload(g.id);assert.deepEqual(p.global.result,g.global.result);
  const events=p.free_incidents.events.map(e=>({type:e.type,minute:e.minute,rid:e.rid}));
  for(const r of g.incident.records)assert.equal(r.state,'closed',`${r.id} ${r.type} closed through the UI`);
  report.runs.push({seed,difficulty,id:g.id,events,result:{success:g.global.result.success,total:g.global.result.total,resolved:g.global.result.resolved}});
  await page.screenshot({path:join(out,`free-${seed}-${difficulty}-${report.runs.length}.png`)});return events;
}
try{
  stack=await startStack({enginePort:8792,vitePort:5192,log:s=>console.log(s.trim())});browser=await chromium.launch({executablePath:CHROME,headless:false,args:['--no-first-run']});report.browserVersion=browser.version();
  ctx=await browser.newContext({viewport:{width:1920,height:1080},reducedMotion:'reduce'});await ctx.addInitScript(()=>localStorage.setItem('srs3d.opening.seen.v1','1'));page=await ctx.newPage();page.on('pageerror',e=>report.errors.push(e.message));page.on('console',m=>{if(m.type()==='error')report.consoleErrors.push(m.text());});page.on('dialog',d=>d.accept());await page.goto(stack.url);await page.waitForFunction(()=>!!window.worldQA);await page.waitForTimeout(1000);
  let base;
  await check('seed 91 challenge: incidents happen and are all closed through the UI',async()=>{base=await play(91,'challenge');assert.ok(base.length>0);});
  await check('other seeds at the same difficulty give a different non-empty incident layout',async()=>{
    const distinct=[];for(const seed of [3,17,2026]){const ev=await play(seed,'challenge');if(ev.length&&JSON.stringify(ev)!==JSON.stringify(base))distinct.push({seed,ev});}
    assert.ok(distinct.length>=2,'at least two other seeds produce real, different incidents: '+JSON.stringify(report.runs.map(r=>[r.seed,r.events])));
    const kinds=new Set(report.runs.flatMap(r=>r.events.map(e=>e.type)));report.types=[...kinds];assert.ok(kinds.size>=3,'several incident types reached in the browser: '+[...kinds]);
  });
  await check('same seed and same actions replay the same incidents',async()=>{const again=await play(91,'challenge');assert.deepEqual(again,base);});
  await check('no page errors or renderer crashes',async()=>{assert.deepEqual(report.errors,[]);assert.deepEqual(report.consoleErrors,[]);});
}catch(e){report.failure=e.stack;console.error(e.stack);process.exitCode=1;}
finally{report.finishedAt=new Date().toISOString();report.summary={pass:report.checks.filter(c=>c.pass).length,total:report.checks.length};await writeFile(join(out,'phase9-seed-qa.json'),JSON.stringify(report,null,2));await ctx?.close();await browser?.close();await stack?.stop();}
