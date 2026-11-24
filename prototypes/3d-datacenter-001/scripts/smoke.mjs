// Quick developer smoke: open the page, optionally start a mode through the real menu, screenshot, print errors.
// node scripts/smoke.mjs [--mode=tutorial] [--out=dir] [--w=1920 --h=1080 --dpr=1]
import {chromium} from 'playwright-core';
import {mkdir} from 'node:fs/promises';
import {resolve} from 'node:path';
const arg=(k,d)=>process.argv.find(x=>x.startsWith(`--${k}=`))?.split('=')[1]??d;
const out=resolve(arg('out','.qa-saves/smoke'));await mkdir(out,{recursive:true});
const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:arg('headless','0')==='1'});
const ctx=await browser.newContext({viewport:{width:+arg('w',1920),height:+arg('h',1080)},deviceScaleFactor:+arg('dpr',1)});
await ctx.addInitScript(()=>{try{localStorage.setItem('srs3d.opening.seen.v1','1');}catch{}});
const page=await ctx.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
await page.goto(arg('url','http://127.0.0.1:5173/'),{waitUntil:'domcontentloaded'});try{await page.waitForFunction(()=>!!window.worldQA,null,{timeout:15000});}catch(e){console.log("PAGE ERRORS",errors);await page.screenshot({path:resolve(out,"error.png")});await browser.close();process.exit(1);}await page.waitForTimeout(1500);
await page.screenshot({path:resolve(out,'menu.png')});
const mode=arg('mode','');
if(mode){await page.click(`[data-new=${mode}]`);await page.waitForTimeout(1500);await page.screenshot({path:resolve(out,`${mode}-start.png`)});}
console.log(JSON.stringify({errors,snap:await page.evaluate(()=>{const s=worldQA.snapshot();return {gameId:s.gameId,engine:s.engine,route:s.state.navigation.route,step:s.game?.journey?.current?.id,menu:s.ui.menu};})},null,1));
await browser.close();
