import {injectFault,startRepair,advance,verify,REPAIR_SECONDS} from './model.js';

// `route` is where the step is primarily done (and where guidance points); `routes` lists every allowed space.
const STEPS=Object.freeze({
  new:{id:'review',label:'싱가포르 요청 확인',route:'noc',routes:Object.freeze(['noc','world']),next:'reviewed',progress:0,note:'내 모니터에 들어온 싱가포르 요청의 원래 GPU·전력·대역폭 조건을 확인하세요. 세계지도에서 고객 위치와 가상 회선도 볼 수 있습니다.',objective:'내 모니터의 새 요청을 확인하세요'},
  reviewed:{id:'accept',label:'요청 접수 · 배정 확정',route:'noc',next:'accepted',progress:0,note:'배정 검토(서버동 01 · 랙 D-06)를 확인하고 내 자리에서 요청을 접수하세요.',objective:'내 자리에서 접수와 배정을 검토하세요'},
  accepted:{id:'start',label:'시연 작업 시작',route:'hall',next:'running',progress:25,note:'관제동에서 연결 통로를 지나 서버동 01로 이동해 랙 D-06을 확인하세요. 선택한 랙에서만 시작합니다.',objective:'서버동 01의 랙 D-06에서 작업을 시작하세요'},
  running:{id:'advance',label:'다음 작업 단계',route:'hall',next:'fault',progress:40,note:'작업 진행 예시를 확인합니다. 다음 클릭에서 업링크 장애가 발생합니다.',objective:'작업 진행과 네트워크 상태를 관찰하세요'},
  fault:{id:'repair',label:'업링크 복구 시작',route:'hall',next:'repairing',progress:40,note:'업링크 단절로 처리량이 줄었습니다. 내 모니터·네트워크동·세계지도에서도 같은 장애를 확인할 수 있습니다.',objective:'같은 장애가 모든 공간에 표시되는지 확인하세요'},
  repairing:{id:'repair-complete',label:'복구 처리 완료',route:'hall',next:'awaiting',progress:40,note:'복구는 클릭으로만 진행합니다. 처리 후에도 사후 확인이 필요합니다.',objective:'복구 처리와 사후 확인을 구분하세요'},
  awaiting:{id:'verify',label:'사후 상태 확인',route:'hall',next:'recovered',progress:60,note:'복구된 업링크와 센서를 확인하고 작업을 정상 재개합니다.',objective:'사후 상태를 확인하고 정상 재개하세요'},
  recovered:{id:'finish',label:'시연 작업 완료',route:'hall',next:'completed',progress:100,note:'다음 클릭으로 작업을 완료합니다. 이후 내 자리에서 고객 결과를 확인하세요.',objective:'작업 완료 후 고객 결과를 확인하세요'},
  completed:{id:'report',label:'고객 결과 확인',route:'noc',next:'reported',progress:100,note:'관제동 내 자리로 돌아와 같은 요청의 처리 위치·원래 조건·복구 확인 결과를 확인하세요.',objective:'내 자리에서 처리 결과를 확인하세요'},
});
export function nextDemoStep(state){return STEPS[state.request.phase]||null;}
export function demoBlocker(state,action){
  const step=nextDemoStep(state);
  if(!step||action!==step.id)return '현재 단계에서 수행할 수 없는 조작입니다.';
  if(!(step.routes||[step.route]).includes(state.navigation.route))return '이 조작은 해당 운영 공간에서 진행해 주세요.';
  if(action==='review'&&state.navigation.route==='world'&&state.navigation.country!=='SG')return '이번 시연의 싱가포르 고객을 선택해 주세요.';
  if(step.route==='hall'&&state.facility.selectedId!==state.request.rackId)return `요청 대상 랙 ${state.request.rackId}을 선택해 주세요.`;
  const target=state.facility.assets.find(a=>a.id===state.request.rackId);
  if(!target)return '요청 대상 랙을 찾을 수 없습니다.';
  const expected={start:'normal',advance:'normal',repair:'fault','repair-complete':'repairing',verify:'awaiting',finish:'verified'};
  if(expected[action]&&target.state!==expected[action])return '요청과 장비 상태가 일치하지 않아 진행할 수 없습니다.';
  return '';
}
export function applyDemoAction(state,action){
  const blocker=demoBlocker(state,action);if(blocker)return {ok:false,reason:blocker};
  const step=nextDemoStep(state),facility=state.facility;
  if(action==='advance')injectFault(facility,'network');
  if(action==='repair')startRepair(facility);
  if(action==='repair-complete')advance(facility,REPAIR_SECONDS);
  if(action==='verify')verify(facility);
  Object.assign(state.request,{phase:step.next,progress:step.progress,steps:state.request.steps+1});
  state.request.history.push({step:state.request.steps,action,phase:step.next,progress:step.progress});
  return {ok:true,reason:''};
}
