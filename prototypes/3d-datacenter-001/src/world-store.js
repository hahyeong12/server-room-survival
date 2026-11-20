import { createFacility, selectAsset } from './model.js';
import { applyDemoAction } from './demo-actions.js';

function freeze(value) { Object.values(value).forEach(v => { if (v && typeof v === 'object') freeze(v); }); return Object.freeze(value); }
export const LOCATIONS = freeze({ world: { title:'세계 운영 지도', parent:null, subtitle:'GLOBAL OPERATIONS' }, noc:{ title:'울산 관제실', parent:'world', subtitle:'NETWORK OPERATIONS CENTER' }, campus:{ title:'데이터센터 시설', parent:'noc', subtitle:'ULSAN AIDC / CAMPUS' }, hall:{ title:'서버실 01', parent:'campus', subtitle:'COMPUTE HALL / 24 RACKS' } });
export const COUNTRIES = freeze({ KR:{ name:'대한민국 · 울산', short:'ULSAN AIDC', lon:129.31, lat:35.54 }, SG:{ name:'싱가포르', short:'SINGAPORE', lon:103.82, lat:1.35 }, JP:{ name:'일본', short:'JAPAN', lon:139.69, lat:35.68 }, US:{ name:'미국', short:'UNITED STATES', lon:-122.42, lat:37.77 } });
export const FACILITIES = freeze({ NOC:{ name:'관제동', code:'NOC / 01', x:-9,z:5, description:'요청 접수·시설 상태·고객 결과를 한곳에서 확인합니다.', target:'noc' }, 'HALL-01':{ name:'서버동 01', code:'COMPUTE / 24 RACKS', x:0,z:-2, description:'싱가포르 요청의 대상 랙 D-06이 있는 서버홀입니다.', target:'hall' }, POWER:{ name:'전력동', code:'POWER / A·B', x:-10,z:-5, description:'전력 공급과 배전 구역입니다. 전기 계통은 모식이며 실제 설계가 아닙니다.' }, UPS:{ name:'UPS 구역', code:'UPS / BACKUP', x:-10,z:-.5, description:'정전 시 공급 연속성을 돕는 무정전 전원 설비의 모식 구역입니다.' }, COOLING:{ name:'냉각 플랜트', code:'COOLING / 01', x:10,z:-4, description:'서버의 열을 외부로 옮기는 팬·열교환기·배관을 볼 수 있습니다.' }, NETWORK:{ name:'네트워크동', code:'NETWORK / CORE', x:9,z:5, description:'고객과 서버동의 가상 통신 경로가 연결되는 지점입니다.' } });
export const FIXTURE = freeze({ id:'SG-2026-001', customerId:'SG-LINK-01', customerName:'싱가포르 AIDC LINK', country:'SG', facilityId:'ULSAN-AIDC-01', buildingId:'HALL-01', rackId:'D-06', workload:'AI 추론 배치 처리', terms:{ gpu:8, powerKW:20, networkGbps:40, mode:'고성능', deadline:'시연 완료 시점에 결과 확인' } });
export const PHASES = freeze({ new:'새 요청', reviewed:'요청 확인', accepted:'접수 완료', running:'작업 진행 중', fault:'업링크 장애', repairing:'복구 중', awaiting:'사후 확인 대기', recovered:'정상 재개', completed:'처리 완료', reported:'결과 확인 완료' });

export function breadcrumbs(route) {
  if (!Object.hasOwn(LOCATIONS,route)) return [];
  const result=[];
  for(let id=route; id; id=LOCATIONS[id].parent) result.unshift({id,title:LOCATIONS[id].title});
  return result;
}
export function createWorldStore() {
  const state={ navigation:{route:'world',country:'SG',facility:'HALL-01'}, facility:createFacility(), request:{...FIXTURE,terms:FIXTURE.terms,phase:'new',progress:0,steps:0,history:[]}, notice:'' };
  const listeners=new Set();
  function notify() { for(const listener of listeners) listener(); }
  function navigate(route) { if(!Object.hasOwn(LOCATIONS,route)) return false; state.navigation.route=route; notify(); return true; }
  return {
    state, navigate,
    back(){const parent=LOCATIONS[state.navigation.route].parent;return parent?navigate(parent):false;},
    selectCountry(id){if(!Object.hasOwn(COUNTRIES,id))return false;state.navigation.country=id;notify();return true;},
    selectFacility(id){if(!Object.hasOwn(FACILITIES,id))return false;state.navigation.facility=id;notify();return true;},
    selectRack(id){if(!selectAsset(state.facility,id))return false;notify();return true;},
    act(action){const result=applyDemoAction(state,action);state.notice=result.reason;notify();return result;},
    subscribe(listener){listeners.add(listener);return()=>listeners.delete(listener);},
    snapshot(){return structuredClone(state);},
    domainSnapshot(){const {selectedId,...facility}=state.facility;return structuredClone({request:state.request,facility});},
  };
}
