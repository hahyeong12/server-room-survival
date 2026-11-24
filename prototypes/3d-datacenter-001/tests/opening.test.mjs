import {test} from 'node:test';
import assert from 'node:assert/strict';
import {OPENING,OPENING_SECONDS,DESK_POSE,OPENING_STORAGE_KEY} from '../src/opening.js';
import {COUNTRIES} from '../src/world-store.js';

test('opening is 8-15 s and follows world -> Ulsan -> district/campus -> my desk',()=>{
  assert.ok(OPENING_SECONDS>=8&&OPENING_SECONDS<=15,`${OPENING_SECONDS}s`);
  assert.deepEqual(OPENING.map(k=>k.location),['world','world','campus','campus','noc']);
  assert.deepEqual(OPENING.at(-1).to,DESK_POSE,'ends seated at my desk');
  for(let i=1;i<OPENING.length;i++)if(OPENING[i].location===OPENING[i-1].location)assert.deepEqual(OPENING[i].from,OPENING[i-1].to,'continuous camera within a space');
  assert.ok(Object.isFrozen(OPENING)&&OPENING_STORAGE_KEY.startsWith('srs3d.'));
});
test('captions mark the network and site as virtual; Ulsan pin is Nam-gu Hwangseong/Yongyeon, not Dong-gu',()=>{
  const text=OPENING.map(k=>k.title+' '+k.sub).join(' ');
  for(const word of ['가상','실제 해저케이블 경로 아님','황성동','용연','실제 부지'])assert.ok(text.includes(word),word);
  const {lon,lat}=COUNTRIES.KR;assert.ok(lon>129.3&&lon<129.4&&lat>35.45&&lat<35.52,'Nam-gu industrial area, west of the Dong-gu shipyards (~129.42E)');
});
test('opening is neutral: no customer country is shown as sending a request before the game starts (Issue #5)',()=>{
  const text=OPENING.map(k=>k.title+' '+k.sub).join(' ');
  for(const name of ['싱가포르','일본','미국','SG-','요청이 가상 회선'])assert.ok(!text.includes(name),name);
  assert.ok(text.includes('아직 도착한 요청 없음'));
});
