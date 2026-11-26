// Phase8: UI only. Parsing, telemetry, evidence, interpretation and promotion belong to Python.
export function buildCommand(spec, parts = {}) {
  return spec.syntax.split(' ').map((token, i) => i === 0 ? token : (parts[i] ?? '')).join(' ').trim();
}
// Expanded view is a per-player preference kept outside the per-shift terminal state so a new shift,
// a tab switch or a re-render never resets it. Draft, history and scroll stay in ui.linux.
export function toggleExpanded(ui, value = !ui.linuxExpanded) {
  ui.linuxExpanded = !!value;
  return ui.linuxExpanded;
}
// Choice level: the example line with the player's chosen IP target / switch port.
export function choiceLine(spec, {host, iface} = {}) {
  const example = spec.example.split(' ');
  return spec.syntax.split(' ').map((t, i) => t === '$host' ? (host ?? example[i]) : t === '$iface' ? (iface ?? example[i]) : example[i]).join(' ');
}
export function interpretationChoices(observation) {
  return observation.choices ?? [];
}
export function createLinuxPane({el, button, send, ui, render, toast}) {
  function pane(body, g) {
    const l = g.linux;
    body.classList.add('linux-pane');
    const expanded = !!ui.linuxExpanded;
    body.classList.toggle('linux-expanded', expanded);
    if (!l || !g.global.briefed) {body.append(el('p', '', '먼저 근무 브리핑을 확인하세요.')); return;}
    const recs = g.incident.records.filter(r => r.state !== 'armed');
    if (!recs.length) {body.append(el('p', '', '아직 경보가 없습니다. 요청함 → 배정 계획 → 서버동의 실제 랙에서 업무를 시작하고 시간을 진행하세요.')); return;}
    const key = `${g.id}:${l.shift}`;
    if (ui.linuxKey !== key) {ui.linuxKey = key; ui.linux = {draft:'', history:[], historyIndex:0, node:'noc', command:'ping', parts:{}, transient:[], scroll:null, clearSeqByIncident:{}};}
    const u = ui.linux;
    const rec = recs.find(r => r.id === u.incident) ?? recs.find(r => !['closed','failed','void'].includes(r.state)) ?? recs.at(-1);
    u.incident = rec.id;
    const open = !['closed','failed','void'].includes(rec.state);
    const head = el('div', 'linux-context');
    const incidents = el('select'); incidents.dataset.linuxIncident = ''; incidents.setAttribute('aria-label', '터미널 조사 사건');
    for (const r of recs) {const o=el('option','',`${r.id} · #${r.rid} · ${r.stateLabel}`);o.value=r.id;incidents.append(o);}
    incidents.value = rec.id; incidents.onchange = () => {u.incident=incidents.value; u.transient=[]; u.scroll=null; render();};
    incidents.disabled=!!u.busy;
    const nodes = el('select'); nodes.dataset.linuxNode = ''; nodes.setAttribute('aria-label', '가상 장비 컨텍스트'); nodes.dataset.focusKey='linux-node';
    for (const n of l.contexts[rec.id] ?? []) {const o=el('option','',`${n.label}${n.assigned?' · 이 작업 배정':''}${!n.available?' · 환경 없음':''}`); o.value=n.id; nodes.append(o);}
    nodes.value = u.node; nodes.onchange=()=>{u.node=nodes.value; render();};
    nodes.disabled=!!u.busy;
    head.append(incidents,nodes);body.append(head);
    const current = el('div','linux-current'); current.dataset.linuxCurrent='';
    current.append(el('strong','',`${l.role} · ${rec.next}`), el('small','', rec.state==='investigating' ? '서로 다른 계층의 증거 → 출력 해석 → [사건]에서 가설 판단' : rec.why));
    if (!rec.acknowledged && open) current.append(button('범위 확인 후 진단 시작',()=>send({type:'incident_ack',incident:rec.id}),'primary',{'data-linux-ack':rec.id}));
    const view = el('div', 'linux-viewbar');
    const toggle = button(expanded ? '⤡ 기본 크기 (Esc)' : '⤢ 터미널 확대', () => {toggleExpanded(ui); render();}, '', {'data-linux-expand': '', 'aria-pressed': String(expanded), title: expanded ? '터미널을 원래 크기로 줄입니다 (Esc)' : '출력을 더 많이 보도록 터미널을 확대합니다. 입력·기록은 그대로 유지됩니다.'});
    toggle.dataset.focusKey = 'linux-expand';
    if (expanded) {const text = `${rec.id} · ${rec.severity ?? ''} · ${rec.title} · 요청 #${rec.rid} ${rec.client ?? ''} · ${rec.stateLabel}${rec.scope?.text ? ` · 영향: ${rec.scope.text}` : ''}`; const s = el('span', 'linux-incident-summary', text); s.title = text; view.append(s);}
    view.append(toggle);
    current.append(view);
    body.append(current);
    const terminal = el('div', 'linux-terminal'); terminal.dataset.linuxOutput=''; terminal.tabIndex=0; terminal.setAttribute('role','log');terminal.setAttribute('aria-label','가상 터미널 출력 · 내부 스크롤');
    terminal.append(el('div','terminal-notice',`${l.notice}\n${rec.id} · 현재 선택 ${u.node} · 가상 시각 ${g.clock.label}`));
    const observations = l.observations.filter(o=>o.incident===rec.id && o.seq>(u.clearSeqByIncident[rec.id]??0));
    for (const o of observations) {
      const block=el('div','linux-output-entry'); block.dataset.linuxObservation=String(o.seq);
      block.append(el('b','terminal-prompt',`${o.node}$ ${o.line}`), el('pre','',o.output),el('small',o.code?'terminal-warn':'',`exit ${o.code} · ${o.after?'복구 후 새 관측':'조사 관측'} · ${o.minute}분${o.historical?' · 보관 로그':''}`));terminal.append(block);
    }
    for (const x of u.transient) terminal.append(el('pre',x.category==='observation'?'':'terminal-warn',x.output));
    terminal.onscroll=()=>{u.scroll=terminal.scrollTop;}; body.append(terminal);
    queueMicrotask(()=>{if(terminal.isConnected)terminal.scrollTop=u.scroll??terminal.scrollHeight;});
    const dock = el('div', 'linux-dock'); dock.dataset.linuxDock='';
    const run = async (line) => {
      if (u.busy || !rec.acknowledged || !open) return;
      u.busy=true;u.draft=line;u.scroll=null;
      const request = {type:'linux_command',incident:rec.id,line,node:u.node,token:l.tokens[rec.id]};
      render();
      const res=await send(request,{quiet:true});
      u.busy=false;
      if(res?.stale||ui.linux!==u)return;
      if(ui.linuxKey!==key||u.incident!==request.incident||u.node!==request.node){render();return;}
      const out=res?.result?.linux;
      if(out){
        u.history=[...u.history.filter(x=>x!==line),line].slice(-50);u.historyIndex=u.history.length;
        if(out.kind==='clear'){u.clearSeqByIncident[rec.id]=res.game.linux.observations.at(-1)?.seq??0;u.transient=[];}
        else if(out.kind==='help'||out.kind==='error'){u.transient=[...u.transient,{output:`${request.node}$ ${line}\n[${out.category}] exit ${out.code}\n${out.output}`,category:out.category}].slice(-12);}
        u.draft='';
      }
      render();
      if(!document.querySelector('#menu:not([hidden])'))document.querySelector('[data-linux-input]')?.focus({preventScroll:true});
    };
    if (l.inputMode !== 'terminal') {
      const builder=el('div','linux-builder'); const select=el('select');select.dataset.linuxCommand='';select.setAttribute('aria-label','진단 목적에 맞는 도구 선택');
      for(const c of l.commands){const o=el('option','',`${c.label} · ${c.tool}`);o.value=c.command_id;select.append(o);}
      select.value=u.command;select.onchange=()=>{u.command=select.value;u.parts={};render();};builder.append(select);
      const spec=l.commands.find(c=>c.command_id===u.command)??l.commands[0];
      if(l.inputMode==='choice'){
        if(spec.syntax.includes('$host')){const target=el('select');target.dataset.linuxTarget='';target.setAttribute('aria-label','조회할 IP 대상');for(const value of l.arguments.$host){const o=el('option','',value);o.value=value;target.append(o);}target.value=u.target??'10.20.0.15';target.onchange=()=>{u.target=target.value;};builder.append(target);}
        if(spec.syntax.includes('$iface')){const port=el('select');port.dataset.linuxIface='';port.setAttribute('aria-label','조회할 스위치 포트');for(const value of l.arguments.$iface){const o=el('option','',value);o.value=value;port.append(o);}port.value=u.iface??l.arguments.$iface[0];port.onchange=()=>{u.iface=port.value;};builder.append(port);}
        builder.append(button('선택한 도구로 조회',()=>run(choiceLine(spec,{host:u.target,iface:u.iface})),'primary',{'data-linux-choice':'',...(!rec.acknowledged||!open?{disabled:''}:{})}));
        // One line (full text on hover) so the action row below never leaves the monitor on short screens.
        const meaning=el('small','linux-tool-meaning',`${spec.label} · 환경 ${spec.context} · IP storage 10.20.0.15 / Server A~D 10.20.11~14.15 · swp1~4 = ToR-A~D 업링크 · 영향 범위 전체를 비교`);
        meaning.title=meaning.textContent;dock.append(builder,meaning);
      }else{
        const bits=el('div','linux-bits');bits.append(el('code','',spec.tool));
        spec.syntax.split(' ').slice(1).forEach((token, index)=>{
          const i=index+1, s=el('select');s.dataset.linuxPart=String(i);s.setAttribute('aria-label',`명령 조립 ${i} · ${token.startsWith('$')?'대상·개수':'옵션·하위 명령'}`);
          const opts=token.startsWith('$')?l.arguments[token]:[...new Set(l.commands.filter(c=>c.tool===spec.tool).map(c=>c.syntax.split(' ')[i]).filter(t=>t&&!t.startsWith('$')))];
          const empty=el('option','',token.startsWith('$')?'대상·개수 선택':'옵션 선택');empty.value='';s.append(empty);
          for(const value of opts){const o=el('option','',value);o.value=value;s.append(o);}s.value=u.parts[i]??'';
          s.onchange=()=>{u.parts[i]=s.value;};bits.append(s);
        });
        builder.append(bits,button('조립한 명령 조회',()=>run(buildCommand(spec,u.parts)),'primary',{'data-linux-assemble':''}));dock.append(builder);
      }
    }
    const form=el('form','linux-input-row');form.setAttribute('aria-label','가상 명령 입력');
    const prompt=el('span','terminal-prompt',`${u.node}$`),input=el('input');input.dataset.linuxInput='';input.dataset.focusKey='linux-input';input.setAttribute('aria-label','가상 Linux 명령어');input.placeholder=l.inputMode==='terminal'?'조회 명령 입력 · help로 문법 확인':'직접 입력도 가능 · help';input.maxLength=l.maxLine;input.autocomplete='off';input.spellcheck=false;input.value=u.draft;
    input.oninput=()=>{u.draft=input.value;};
    input.onkeydown=e=>{if(e.key==='ArrowUp'||e.key==='ArrowDown'){e.preventDefault();u.historyIndex=Math.max(0,Math.min(u.history.length,u.historyIndex+(e.key==='ArrowUp'?-1:1)));input.value=u.history[u.historyIndex]??'';u.draft=input.value;}};
    input.disabled=!rec.acknowledged||!open||!!u.busy;
    const submit=button('조회',()=>{},'primary',{'data-linux-run':''});submit.type='submit';submit.disabled=input.disabled||!!u.busy;
    form.onsubmit=e=>{e.preventDefault();run(input.value);};form.append(prompt,input,submit);dock.append(form);
    const last = [...l.observations].reverse().find(o=>o.incident===rec.id);
    if(last && open){
      const interpretation=el('div','linux-interpret');interpretation.append(el('small','',`관측 #${last.seq}의 의미 · 사실과 추측 중 선택`));
      // One answer per observation (the engine keeps the first). Run the command again to answer a new observation.
      const feedback=l.interpretations.find(x=>x.seq===last.seq&&x.incident===rec.id);
      for(const choice of interpretationChoices(last)) interpretation.append(button(choice.text,()=>send({type:'linux_interpret',incident:rec.id,seq:last.seq,answer:choice.id,token:l.tokens[rec.id]}),feedback?.answer===choice.id?'active':'',{'data-linux-answer':choice.id,...(feedback?{disabled:'','aria-pressed':String(feedback.answer===choice.id)}:{})}));
      if(feedback)interpretation.append(el('small',feedback.correct?'ok':'terminal-warn',feedback.feedback));dock.append(interpretation);
    }
    const actions=el('div','linux-actions');
    actions.append(button('사건 판단·대응으로',()=>{ui.tab='incident';ui.incident=rec.id;render();},'',{'data-linux-back':''}),
      button('도움 요청',()=>send({type:'linux_help',incident:rec.id}),'link',{'data-linux-help':''}),
      button('출력 복사',async()=>{try{await navigator.clipboard.writeText(terminal.innerText);toast('터미널 출력을 복사했습니다.');}catch{toast('이 브라우저에서 복사가 허용되지 않습니다. 출력을 선택해 복사할 수 있습니다.','hint');}},'link',{'data-linux-copy':''}));
    const glossary=el('details','linux-glossary');glossary.append(el('summary','','용어·지원 구문·공식 자료'));
    glossary.append(el('p','','RTT: 왕복 시간 · NSS/DNS: 이름 조회 · inode: 파일 메타데이터 항목 · VRAM: GPU 메모리 · OOM: 메모리 할당 실패 · await: I/O 평균 대기 · passive: 부하 시험 없이 관측 자료 평가 · carrier: 물리 링크 신호. 가상 IP: storage 10.20.0.15 / Server A~D 10.20.11~14.15. 네트워크 노드는 가상 Linux 기반 스위치(eth0 관리 포트, swp1~4 = ToR-A~D 업링크). 한 노드·한 대상의 결과는 그 범위만 말합니다. 영향 범위 전체를 비교해야 엔진 증거로 기록됩니다.'));
    for(const c of l.commands){const p=el('p','',`${c.example} — ${c.label} [${c.context}]. `);const a=el('a','','공식 문서');a.href=c.source;a.target='_blank';a.rel='noopener noreferrer';p.append(a);glossary.append(p);}
    actions.append(glossary);dock.append(actions);
    if(u.busy)for(const control of dock.querySelectorAll('select,input,[data-linux-choice],[data-linux-assemble],[data-linux-answer],[data-linux-help],[data-linux-run]'))control.disabled=true;
    body.append(dock);
  }
  return {pane};
}
