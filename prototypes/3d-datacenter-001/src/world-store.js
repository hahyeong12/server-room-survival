import { createFacility, selectAsset } from './model.js';
import { applyDemoAction } from './demo-actions.js';
import { createOps, applyOpsAction } from './facility-ops.js';

function freeze(value) { Object.values(value).forEach(v => { if (v && typeof v === 'object') freeze(v); }); return Object.freeze(value); }
// The control building and the server building are separate buildings on the same campus (Issue #2).
export const LOCATIONS = freeze({ world: { title:'세계 운영 지도', parent:null, subtitle:'GLOBAL OPERATIONS' }, campus:{ title:'울산 AIDC 캠퍼스', parent:'world', subtitle:'ULSAN AIDC / CAMPUS' }, noc:{ title:'관제동 · 내 자리', parent:'campus', subtitle:'CONTROL BUILDING / NOC' }, hall:{ title:'서버동 01', parent:'campus', subtitle:'COMPUTE BUILDING 01 / 24 RACKS' } });
export const ROUTE_ORDER = Object.freeze(['world','campus','noc','hall']);
export const NOC_VIEWS = Object.freeze(['desk','overview']);
// Ulsan pin: Nam-gu Hwangseong-dong / Yongyeon area (not Dong-gu shipyards). Map precision is illustrative only.
export const COUNTRIES = freeze({ KR:{ name:'대한민국 · 울산', short:'ULSAN AIDC', lon:129.36, lat:35.49 }, SG:{ name:'싱가포르', short:'SINGAPORE', lon:103.82, lat:1.35 }, JP:{ name:'일본', short:'JAPAN', lon:139.69, lat:35.68 }, US:{ name:'미국', short:'UNITED STATES', lon:-122.42, lat:37.77 } });
export const FACILITIES = freeze({ NOC:{ name:'관제동', code:'NOC / 01', x:-9,z:5, description:'내 자리와 업무 모니터가 있는 운영 건물입니다. 요청 접수·시설 감시·결과 확인을 여기서 합니다.', target:'noc' }, 'HALL-01':{ name:'서버동 01', code:'COMPUTE / 24 RACKS', x:0,z:-2, description:'24랙 서버실이 있는 별도 건물입니다. 현장 확인과 랙 작업은 여기서 합니다.', target:'hall' }, POWER:{ name:'전력동', code:'POWER / A·B', x:-10,z:-5, description:'A/B 이중 수전과 배전 구역의 모식입니다. 실제 전기 설계가 아닙니다.' }, UPS:{ name:'UPS 구역', code:'UPS / BACKUP', x:-10,z:-.5, description:'정전 순간의 공급 연속성을 맡는 무정전 전원 설비의 모식입니다.' }, COOLING:{ name:'냉각 플랜트', code:'COOLING / 01', x:10,z:-4, description:'교육용 보조 냉각 계통(AUX-C1)의 켜짐·꺼짐·경고와 유량·온도를 확인합니다. 주 냉각 계통은 항상 운전하는 것으로 가정합니다.' }, NETWORK:{ name:'네트워크동', code:'NETWORK / CORE', x:9,z:5, description:'국제 가상 회선과 서버동 업링크가 모이는 곳입니다. 장애 원인을 조회합니다.' } });
export const FIXTURE = freeze({ id:'SG-2026-001', customerId:'SG-LINK-01', customerName:'싱가포르 AIDC LINK', country:'SG', facilityId:'ULSAN-AIDC-01', buildingId:'HALL-01', rackId:'D-06', workload:'AI 추론 배치 처리', terms:{ gpu:8, powerKW:20, networkGbps:40, mode:'고성능', deadline:'시연 완료 시점에 결과 확인' } });
export const PHASES = freeze({ new:'새 요청', reviewed:'요청 확인', accepted:'접수 완료', running:'작업 진행 중', fault:'업링크 장애', repairing:'복구 중', awaiting:'사후 확인 대기', recovered:'정상 재개', completed:'처리 완료', reported:'결과 확인 완료' });

export function breadcrumbs(route) {
  if (!Object.hasOwn(LOCATIONS,route)) return [];
  const result=[];
  for(let id=route; id; id=LOCATIONS[id].parent) result.unshift({id,title:LOCATIONS[id].title});
  return result;
}
export function createWorldStore() {
  // A work day starts at my desk in the control building.
  const state={ navigation:{route:'noc',nocView:'desk',country:'SG',facility:'NOC'}, facility:createFacility(), request:{...FIXTURE,terms:FIXTURE.terms,phase:'new',progress:0,steps:0,history:[]}, ops:createOps(), notice:'' };
  const listeners=new Set();
  function notify() { for(const listener of listeners) listener(); }
  function navigate(route) { if(!Object.hasOwn(LOCATIONS,route)) return false; state.navigation.route=route; notify(); return true; }
  return {
    state, navigate,
    back(){const parent=LOCATIONS[state.navigation.route].parent;return parent?navigate(parent):false;},
    setNocView(view){if(!NOC_VIEWS.includes(view))return false;state.navigation.nocView=view;notify();return true;},
    selectCountry(id){if(!Object.hasOwn(COUNTRIES,id))return false;state.navigation.country=id;notify();return true;},
    selectFacility(id){if(!Object.hasOwn(FACILITIES,id))return false;state.navigation.facility=id;notify();return true;},
    selectRack(id){if(!selectAsset(state.facility,id))return false;notify();return true;},
    act(action){const result=applyDemoAction(state,action);state.notice=result.reason;notify();return result;},
    ops(action){const result=applyOpsAction(state,action);state.notice=result.reason;notify();return result;},
    subscribe(listener){listeners.add(listener);return()=>listeners.delete(listener);},
    snapshot(){return structuredClone(state);},
    domainSnapshot(){const {selectedId,...facility}=state.facility;return structuredClone({request:state.request,facility,ops:state.ops});},
  };
}
