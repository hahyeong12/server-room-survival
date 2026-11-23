import {test} from 'node:test';
import assert from 'node:assert/strict';
import {CENTER_LON,HALF_WIDTH,wrapLon,toMap,unwrap,copyOffsets} from '../src/geo.js';
import {LANDING,BACKGROUND_LINKS,REQUEST_PATHS,requestPathStatus} from '../src/network-data.js';
import {COUNTRIES,createWorldStore} from '../src/world-store.js';

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
test('request path: sea route ends at a coastal landing station, never at the AIDC; status follows the shared phase',()=>{
  const sg=REQUEST_PATHS.SG;assert.deepEqual(sg.sea.at(-1),LANDING[sg.landing].lonLat);assert.deepEqual(sg.segments.map(s=>s.id),['sea','landing','backbone','aidc']);
  assert.notDeepEqual(sg.sea.at(-1),[COUNTRIES.KR.lon,COUNTRIES.KR.lat]);assert.ok(BACKGROUND_LINKS.length>=10&&Object.isFrozen(BACKGROUND_LINKS));
  const s=createWorldStore();assert.equal(requestPathStatus(s.state).tone,'incoming');
  s.act('review');s.act('accept');s.navigate('hall');s.selectRack('D-06');s.act('start');assert.equal(requestPathStatus(s.state).tone,'active');
  s.act('advance');const f=requestPathStatus(s.state);assert.deepEqual(f.segments,{sea:'ok',landing:'ok',backbone:'ok',aidc:'fault'});assert.match(f.message,/국제 구간 정상/);
  s.act('repair');assert.equal(requestPathStatus(s.state).aidc,'repairing');
});
