import assert from 'node:assert/strict';
import {settle} from './qa-lib.mjs';
import * as U from './phase7-ui.mjs';
export function createLinuxPlayer(page,report){
async function select(sel,value){await page.selectOption(sel,String(value));await settle(page,50);}
async function linuxTab(id){await U.tab(page,'linux');if(await page.locator('[data-linux-incident]').count())await select('[data-linux-incident]',id);}
const GROUPS={dns:['ping','getent','journalctl'],tor_uplink:['ip_link','ping'],congestion:['traceroute','ping'],gpu_health:['dcgm','journalctl'],
  gpu_oom:['journalctl','nvidia_smi','systemctl'],storage_full:['df','journalctl'],storage_latency:['iostat','df'],cooling:['nvidia_smi','journalctl'],ups:['journalctl','ps'],crashloop:['pods','journalctl']};
const SEMANTIC={ping:'ICMP 응답',getent:'설정된 이름 조회',dig:'응답 코드',ip_addr:'선택한 노드의 주소',ip_route:'다음 홉 설정',ethtool:'link detected',ip_link:'carrier 상태',traceroute:'각 홉의 응답',
  journalctl:'선택 서비스가 남긴',nvidia_smi:'GPU 메모리·온도',nvidia_query:'장치 상태와 ECC',dcgm:'사전 구성된 passive',df:'블록 공간',iostat:'await·util',
  systemctl:'가상 worker 서비스',ps:'선택 노드의 프로세스',pods:'가상 namespace의 상태',df_inode:'inode 수',free:'호스트 RAM 가용량',top:'단일 표본'};
function primary(g,id){return g.linux.contexts[id].find(n=>n.assigned)?.id??'server-A';}
async function command(id,ident,{interpret=false,line=null,node=null,target=null,forceTyping=false}={}){
  await linuxTab(id);let g=await U.G(page);const spec=g.linux.commands.find(c=>c.command_id===ident);assert.ok(spec,ident);
  node??=spec.context==='worker'?primary(g,id):spec.context==='any'?'noc':spec.context;
  await select('[data-linux-node]',node);g=await U.G(page);
  const n=g.linux.observations.length,old=JSON.stringify([g.clock,g.datacenter,g.servers,g.requests.map(r=>[r.id,r.progress,r.stage])]);
  const args=Object.fromEntries(Object.entries(g.linux.arguments).map(([k,v])=>[k,v[0]]));args.$count='3';if(target){if(spec.syntax.includes('$iface'))args.$iface=target;else args.$host=target;}
  const text=line??spec.syntax.split(' ').map(t=>args[t]??t).join(' ');
  if(g.linux.inputMode==='choice'&&!forceTyping&&!line){await select('[data-linux-command]',ident);if(await page.locator('[data-linux-target]').count())await select('[data-linux-target]',args.$host);if(await page.locator('[data-linux-iface]').count())await select('[data-linux-iface]',args.$iface);await U.click(page,'[data-linux-choice]');}
  else if(g.linux.inputMode==='assemble'&&!forceTyping&&!line){await select('[data-linux-command]',ident);for(const [i,t]of spec.syntax.split(' ').entries())if(i)await select(`[data-linux-part="${i}"]`,args[t]??t);await U.click(page,'[data-linux-assemble]');}
  else{await page.locator('[data-linux-input]').fill('');await page.locator('[data-linux-input]').pressSequentially(text,{delay:1});await page.locator('[data-linux-input]').press('Enter');await settle(page,150);}
  const after=await U.G(page);assert.equal(after.linux.observations.length,n+1,`${id} ${text} records valid CLI observation`);
  assert.equal(JSON.stringify([after.clock,after.datacenter,after.servers,after.requests.map(r=>[r.id,r.progress,r.stage])]),old,'diagnostic CLI does not repair or move time/resources');
  const entry=after.linux.observations.at(-1);assert.equal(entry.command_id,ident);assert.equal(entry.node,node);
  assert.ok(await page.locator(`[data-linux-observation="${entry.seq}"]`).count());
  if(interpret){const choices=await page.locator('[data-linux-answer]').allTextContents(),needle=SEMANTIC[ident];const choice=choices.findIndex(t=>t.includes(needle));assert.ok(choice>=0,`${ident} meaning on UI`);await U.click(page,`[data-linux-answer="${choice===0?'a':'b'}"]`);assert.equal((await U.G(page)).linux.interpretations.at(-1).correct,true);}
  report.commands.push({id,command:ident,line:text,node,code:entry.code,status:entry.status,after:entry.after,seq:entry.seq});return entry;
}
async function act(id,action,rid){
  await U.incidentTab(page,id);const away=page.locator(`.inc-card [data-action-goto="${action}"]`);
  if(await away.count()){await away.click();await settle(page,300);await page.waitForTimeout(850);}
  const scope=page.locator(`[data-incident-actions="${id}"]`);
  if(rid!==undefined&&await scope.locator('[data-incident-rid]').count())await select(`[data-incident-actions="${id}"] [data-incident-rid]`,rid);
  await scope.locator(`[data-incident-action="${action}"]`).click();await settle(page,160);
  const entry=(await U.inc(page,id)).actions.at(-1);assert.equal(entry.action,action);report.actions.push({id,action,result:entry.result,at:(await U.S(page)).state.navigation.route});return entry;
}
// The engine records node/target dependent evidence only once the whole scope of the request was compared:
// storage + every job server for ping/traceroute, every job server for the GPU health family.
function scopeOf(g,id){const servers=g.linux.contexts[id].filter(n=>n.assigned).map(n=>n.id.slice(-1));
  return {targets:['10.20.0.15',...servers.map(x=>`10.20.${11+'ABCD'.indexOf(x)}.15`)],nodes:servers.map(x=>`server-${x}`)};}
async function scoped(id,ident,{interpret=false}={}){
  const g=await U.G(page),spec=g.linux.commands.find(c=>c.command_id===ident),{targets,nodes}=scopeOf(g,id);let out;
  if(['ping','traceroute'].includes(ident)){for(const [i,t]of targets.entries())out=await command(id,ident,{interpret:interpret&&i===0,target:t});return out;}
  if(spec.probe==='dcgm'){for(const [i,n]of nodes.entries())out=await command(id,ident,{interpret:interpret&&i===0,node:n});return out;}
  return command(id,ident,{interpret});
}
async function bms(id,type){if(type==='cooling'||type==='ups')await U.observe(page,id,type);}
function targetIP(rec){const server=rec.scope.jobs.find(j=>j.rid===rec.rid)?.servers?.[0]??'A';return `10.20.${11+'ABCD'.indexOf(server)}.15`;}
async function evidence(id,type,post=false){for(const ident of GROUPS[type])await scoped(id,ident,{interpret:!post});await bms(id,type);}
// For the final exam infer from the output, not from a hidden engine type or a seeded result.
async function independentEvidence(id){
  const rows=[];for(const ident of ['ping','getent','journalctl','df','iostat','traceroute','pods'])rows.push(await scoped(id,ident,{interpret:ident==='journalctl'}));
  const own=ident=>rows.find(r=>r.command_id===ident)?.output??'';
  if(/CrashLoopBackOff\s+9/.test(own('pods')))return 'crashloop';
  if(/vdb\s+40\.0\s+10\.0\s+85\.0/.test(own('iostat')))return 'storage_latency';
  if(/ 3  \S+  42\.1 ms/.test(own('traceroute')))return 'congestion';
  throw new Error('Could not explain this exam incident from its visible output');
}

return {command,act,scoped,evidence,linuxTab};
}
