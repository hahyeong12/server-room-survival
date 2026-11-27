const LABELS = {contracts:'기한 내 계약 이행',recovery:'복구·검증·보고',safety:'승인·동의·안전',communication:'복구 전 고객 소통',
  evidence:'보완적 증거',interpretation:'출력 해석',hypothesis:'근거 있는 가설',independence:'도움 없이 판단'};
export function assessmentCard(a,el){
  const box=el('div','ws-card career-scores');box.dataset.assessment='';
  for(const [key,label]of [['operations','운영 성과'],['learning','학습 성취']]){
    const part=el('section','career-score');part.dataset.score=key;part.append(el('strong','',`${label} ${a[key].score??'—'}/100`));
    for(const [id,value]of Object.entries(a[key].items))part.append(el('small','',`${LABELS[id]??id}: ${value??'평가 기회 없음'}${value==null?'':`/${a.weights[key][id]}`}`));
    box.append(part);
  }
  box.append(el('small','career-score-note',a.notice));return box;
}
