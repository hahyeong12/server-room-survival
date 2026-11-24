import {test} from 'node:test';
import assert from 'node:assert/strict';
import {CENTER_LON,HALF_WIDTH,wrapLon,toMap,unwrap,copyOffsets} from '../src/geo.js';
import {LANDING,BACKGROUND_LINKS,REQUEST_PATHS,activePaths,pathStatus,focusPath} from '../src/network-data.js';
import {COUNTRIES} from '../src/world-store.js';

test('Korea (Ulsan) is the centre; Japan and the US stay east, Singapore south-west, no break at the date line',()=>{
  const kr=toMap(COUNTRIES.KR.lon,COUNTRIES.KR.lat);assert.ok(Math.abs(kr[0])<.01);
  const jp=toMap(COUNTRIES.JP.lon,COUNTRIES.JP.lat),us=toMap(COUNTRIES.US.lon,COUNTRIES.US.lat),sg=toMap(COUNTRIES.SG.lon,COUNTRIES.SG.lat);
  assert.ok(jp[0]>0&&us[0]>jp[0]&&us[0]<HALF_WIDTH,'Pacific continuous to the east');assert.ok(sg[0]<0&&sg[2]>kr[2],'SG west and south');
  assert.ok(wrapLon(179.9)-wrapLon(-179.9)<0||Math.abs(toMap(179.9,0)[0]-toMap(-179.9,0)[0])<.05,'date line is not a seam');
  for(const lon of [-180,-50.64,0,129.36,180])assert.ok(wrapLon(lon)>=-180&&wrapLon(lon)<180);
});
test('rings crossing the Atlantic seam are made continuous and duplicated for clipping',()=>{
  const ring=unwrap([[-60,10],[-45,10],[-40,0]]);for(let i=1;i<ring.length;i++)assert.ok(Math.abs(ring[i][0]-ring[i-1][0])<180);
  assert.deepEqual(copyOffsets(ring.map(p=>p[0])).sort(),[0,-360].sort());assert.deepEqual(copyOffsets([0,10]),[0]);
});
test('request paths: every customer sea route ends at a coastal landing station, never at the AIDC',()=>{
  for(const [code,p] of Object.entries(REQUEST_PATHS)){
    assert.deepEqual(p.sea.at(-1),LANDING[p.landing].lonLat,code);assert.deepEqual(p.segments.map(s=>s.id),['sea','landing','backbone','aidc']);
    assert.notDeepEqual(p.sea.at(-1),[COUNTRIES.KR.lon,COUNTRIES.KR.lat]);
  }
  assert.deepEqual(Object.keys(REQUEST_PATHS).sort(),['JP','SG','US']);assert.ok(BACKGROUND_LINKS.length>=10&&Object.isFrozen(BACKGROUND_LINKS));
});
// Regression (Issue #5): the opening and an initial UI state with a selected country never light a request path.
test('no engine request -> nothing lit, whatever country is selected; only arrived requests light their own path',()=>{
  for(const country of [null,'SG','JP','US']){
    const state={navigation:{country},game:null};assert.deepEqual(activePaths(state),[]);assert.equal(focusPath(state),null);
    assert.deepEqual(activePaths({navigation:{country},game:{world:{paths:[]}}}),[]);
  }
  const game={world:{paths:[{rid:1,code:'SG',tone:'incoming',focus:true,segments:{sea:'ok',landing:'ok',backbone:'ok',aidc:'ok'}}]}};
  const state={navigation:{country:'JP'},game};
  assert.deepEqual(activePaths(state).map(p=>p.code),['SG']);assert.equal(focusPath(state).tone,'incoming');assert.match(focusPath(state).message,/싱가포르 새 요청 도착/);
  assert.deepEqual(activePaths({game:{world:{paths:[{rid:2,code:'XX',tone:'active'}]}}}),[],'unknown origins are never drawn');
});
test('a server fault changes only the AIDC segment; a network incident is not placed on a guessed segment',()=>{
  const hw=pathStatus({rid:1,code:'SG',tone:'active',segments:{sea:'ok',landing:'ok',backbone:'ok',aidc:'fault'}});
  assert.deepEqual(hw.segments,{sea:'ok',landing:'ok',backbone:'ok',aidc:'fault'});assert.match(hw.message,/네트워크 문제 아님/);
  assert.equal(pathStatus({rid:1,code:'SG',tone:'active',segments:{sea:'ok',landing:'ok',backbone:'ok',aidc:'repairing'}}).aidc,'repairing');
  const net=pathStatus({rid:3,code:'US',tone:'active',segments:{sea:'degraded',landing:'degraded',backbone:'degraded',aidc:'ok'}});
  assert.equal(net.link,'degraded');assert.equal(net.aidc,'ok');assert.match(net.message,/구간 위치를 모델링하지 않음/);
});
