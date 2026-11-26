// Serial Windows/portable regression runner. Existing evidence is never overwritten.
import {spawn} from 'node:child_process';
import {mkdir,readFile,writeFile} from 'node:fs/promises';
import {resolve,join} from 'node:path';
import {python,ROOT} from './qa-lib.mjs';

const out=resolve('../../docs/3d-world-expansion/qa/phase8');await mkdir(out,{recursive:true});
// --tag=NAME writes NAME-phaseN folders, NAME-*.log and NAME-results.json so an earlier run is never overwritten.
const tag=process.argv.find(x=>x.startsWith('--tag='))?.slice(6)??'regression';
const results={startedAt:new Date().toISOString(),tag,checks:[]};
async function run(label,command,args,{cwd=ROOT,reportFile,expected}={}){
  console.log(`START ${label}`);const start=Date.now();let log='';
  const p=spawn(command,args,{cwd,windowsHide:true,env:{...process.env,PYTHONIOENCODING:'utf-8'}});
  for(const stream of [p.stdout,p.stderr])stream.on('data',d=>{log+=d;process.stdout.write(d);});
  const code=await new Promise((accept,reject)=>{p.once('error',reject);p.once('exit',accept);});
  await writeFile(join(out,tag==='regression'?`${label}.log`:`${tag}-${label}.log`),log);
  let summary=null;
  if(reportFile){const data=JSON.parse(await readFile(join(out,reportFile),'utf8'));summary=data.summary??{pass:data.checks?.filter(x=>x.pass).length,total:data.checks?.length};}
  const pass=code===0&&(!expected||(summary?.pass===expected&&summary?.total===expected));
  results.checks.push({label,command:[command,...args],code,pass,summary,ms:Date.now()-start});
  await writeFile(join(out,`${tag}-results.json`),JSON.stringify(results,null,2));
  console.log(`${pass?'PASS':'FAIL'} ${label}`);return pass;
}
let vite;
try{
  if(process.argv.includes('--after-phase8')){
    console.log('Waiting for the final Phase8 UI run to release Chrome before serial regressions');
    for(;;){try{const r=JSON.parse(await readFile(join(out,'final/phase8-qa.json'),'utf8'));if(r.finishedAt)break;}catch{}await new Promise(r=>setTimeout(r,1000));}
    await new Promise(r=>setTimeout(r,1500));
  }
  for(const [phase,expected]of [[7,12],[6,16],[5,9],[4,13]])await run(`phase${phase}`,process.execPath,[`scripts/phase${phase}-qa.mjs`,`--out=${join(out,`${tag}-phase${phase}`)}`],{reportFile:`${tag}-phase${phase}/phase${phase}-qa.json`,expected});
  console.log('START isolated lab Vite on 5199');
  // Check before spawn, and Vite itself binds with strictPort. No unrelated server is stopped.
  const net=await import('node:net');await new Promise((ok,bad)=>{const s=net.createServer();s.once('error',bad);s.listen({port:5199,host:'127.0.0.1',exclusive:true},()=>s.close(ok));});
  vite=spawn(process.execPath,['node_modules/vite/bin/vite.js','--host','127.0.0.1','--port','5199','--strictPort'],{cwd:ROOT,windowsHide:true,env:{...process.env,SRS3D_VITE_CACHE:'.qa-saves/vite-cache-lab-phase8'}});
  for(let i=0;i<100;i++){try{if((await fetch('http://127.0.0.1:5199/lab.html')).ok)break;}catch{}await new Promise(r=>setTimeout(r,200));}
  await run('lab',process.execPath,['scripts/browser-qa.mjs','--url=http://127.0.0.1:5199/lab.html',`--output=${join(out,`${tag}-lab`)}`]);
  vite.kill();vite=null;
  await run('python-headless',python(),['-X','utf8','-m','tests.run_headless'],{cwd:resolve(ROOT,'../..')});
  await run('python-adapter',python(),['-X','utf8','-m','unittest','discover','-s','engine/tests','-t','.','-q']);
  await run('javascript',process.execPath,['--test','tests/*.test.mjs']);
  await run('build',process.execPath,['node_modules/vite/bin/vite.js','build']);
}catch(e){results.failure=e.stack;process.exitCode=1;}
finally{vite?.kill();results.finishedAt=new Date().toISOString();results.summary={pass:results.checks.filter(x=>x.pass).length,total:results.checks.length};if(results.summary.pass!==results.summary.total||results.failure)process.exitCode=1;await writeFile(join(out,`${tag}-results.json`),JSON.stringify(results,null,2));console.log(JSON.stringify(results.summary));}
