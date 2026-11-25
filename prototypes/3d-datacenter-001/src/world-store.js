import { createFacility, selectAsset } from './model.js';
import { createOps, applyOpsAction } from './facility-ops.js';
import { sceneRequest, syncFacility } from './game-view.js';
import { AIDC, LEGACY, SITES, isKnownCode } from './catalog.js';

function freeze(value) { Object.values(value).forEach(v => { if (v && typeof v === 'object') freeze(v); }); return Object.freeze(value); }
// The control building and the server building are separate buildings on the same campus (Issue #2).
export const LOCATIONS = freeze({ world: { title:'세계 운영 지도', parent:null, subtitle:'GLOBAL OPERATIONS' }, campus:{ title:'울산 AIDC 캠퍼스', parent:'world', subtitle:'ULSAN AIDC / CAMPUS' }, noc:{ title:'관제동 · 내 자리', parent:'campus', subtitle:'CONTROL BUILDING / NOC' }, hall:{ title:'서버동 01', parent:'campus', subtitle:'COMPUTE BUILDING 01 / ENGINE SERVERS A–D' }, room:{ title:'시설 내부', parent:'campus', subtitle:'FACILITY INTERIOR' } });
// Facilities with their own small functional interior (double-click on the campus map).
export const ROOMS = Object.freeze(['COOLING','POWER','UPS','NETWORK']);
export const ROUTE_ORDER = Object.freeze(['world','campus','noc','hall','room']);
export const NOC_VIEWS = Object.freeze(['desk','overview']);
// Ulsan pin: Nam-gu Hwangseong-dong / Yongyeon area (not Dong-gu shipyards). Map precision is illustrative only.
// Phase 6: derived from the catalog. The legacy keys (KR, SG, JP, US) keep their names and coordinates.
export const COUNTRIES = freeze({ KR:{ name:AIDC.name, short:AIDC.short, lon:AIDC.lon, lat:AIDC.lat },
  ...Object.fromEntries(Object.entries(LEGACY).map(([code,l])=>[code,{ name:code==='US'?'미국':l.name, short:l.short, lon:l.lon, lat:l.lat, site:l.site }])) });
// Every catalog city (siteId) the world map can show; a request from a city lights only that city.
export const MAP_SITES = freeze(Object.fromEntries(Object.entries(SITES).map(([id,s])=>[id,{ name:`${s.city} · ${s.countryName}`, short:s.cityEn.toUpperCase(), lon:s.lon, lat:s.lat, cluster:s.cluster, domestic:!!s.domestic }])));
export const FACILITIES = freeze({ NOC:{ name:'관제동', code:'NOC / 01', x:-9,z:5, description:'내 자리와 업무 모니터가 있는 운영 건물입니다. 요청 접수·배정 계획·장비 진단·결과 확인을 여기서 합니다.', target:'noc' }, 'HALL-01':{ name:'서버동 01', code:'COMPUTE / ENGINE A–D', x:0,z:-2, description:'엔진 서버 A~D(1번 열 랙 A-01~D-01)가 있는 현장 건물입니다. 배정한 서버에서 작업을 시작하고 사후 확인을 합니다.', target:'hall' }, POWER:{ name:'전력동', code:'POWER / A·B', x:-10,z:-5, description:'A/B 이중 수전과 배전 구역의 모식입니다. 실제 전기 설계가 아닙니다.' }, UPS:{ name:'UPS 구역', code:'UPS / BACKUP', x:-10,z:-.5, description:'정전 순간의 공급 연속성을 맡는 무정전 전원 설비의 모식입니다.' }, COOLING:{ name:'냉각 플랜트', code:'COOLING / 01', x:10,z:-4, description:'교육용 보조 냉각 계통(AUX-C1)의 켜짐·꺼짐·경고와 유량·온도를 확인합니다. 주 냉각 계통은 항상 운전하는 것으로 가정합니다.' }, NETWORK:{ name:'네트워크동', code:'NETWORK / CORE', x:9,z:5, description:'국제 가상 회선과 서버동 업링크가 모이는 곳입니다. 요청 경로의 상태를 조회합니다.' } });

export function breadcrumbs(route) {
  if (!Object.hasOwn(LOCATIONS,route)) return [];
  const result=[];
  for(let id=route; id; id=LOCATIONS[id].parent) result.unshift({id,title:LOCATIONS[id].title});
  return result;
}
// Client state: where the player is looking (view-only) plus the last engine snapshot (read-only copy).
// Game rules never run here; `setGame` only stores what the Python engine returned.
export function createWorldStore() {
  // A work day starts at my desk in the control building. No country is pre-selected (Issue #5).
  const state={ navigation:{route:'noc',nocView:'desk',country:null,facility:'NOC',room:'COOLING'}, facility:createFacility(), ops:createOps(), game:null, request:sceneRequest(null), notice:'' };
  const listeners=new Set();
  function notify() { for(const listener of listeners) listener(); }
  function navigate(route) { if(!Object.hasOwn(LOCATIONS,route)) return false; state.navigation.route=route; notify(); return true; }
  return {
    state, navigate,
    back(){const parent=LOCATIONS[state.navigation.route].parent;return parent?navigate(parent):false;},
    // Enter a building's own space: control building -> my desk, server building -> racks, others -> interior.
    enterFacility(id){if(!Object.hasOwn(FACILITIES,id))return false;state.navigation.facility=id;if(id==='NOC'){state.navigation.nocView='desk';return navigate('noc');}if(id==='HALL-01')return navigate('hall');state.navigation.room=id;return navigate('room');},
    setNocView(view){if(!NOC_VIEWS.includes(view))return false;state.navigation.nocView=view;notify();return true;},
    selectCountry(id){if(typeof id!=='string'||!isKnownCode(id))return false;state.navigation.country=id;notify();return true;},
    selectFacility(id){if(!Object.hasOwn(FACILITIES,id))return false;state.navigation.facility=id;notify();return true;},
    selectRack(id){if(!selectAsset(state.facility,id))return false;notify();return true;},
    setGame(snapshot){state.game=snapshot?structuredClone(snapshot):null;state.request=sceneRequest(state.game);syncFacility(state.facility,state.game);notify();},
    setNotice(text){state.notice=text||'';notify();},
    ops(action){const result=applyOpsAction(state,action);state.notice=result.reason;notify();return result;},
    subscribe(listener){listeners.add(listener);return()=>listeners.delete(listener);},
    snapshot(){return structuredClone(state);},
    domainSnapshot(){const {selectedId,...facility}=state.facility;return structuredClone({game:state.game,facility,ops:state.ops});},
  };
}
