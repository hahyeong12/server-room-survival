import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {chapterGoal,talkFor,resultRows,resultNotes,missionOf,cardRows,isLaterChapter} from '../src/campaign-view.js';
import {activePaths,pathStatus} from '../src/network-data.js';

// Real snapshots produced by the unmodified Python engine through the 3D adapter (python -m engine.tests.make_fixtures).
const S=JSON.parse(readFileSync(new URL('./fixtures/snapshots.json',import.meta.url),'utf8'));

test('chapter 1 and the tutorial keep the Phase 4 views; chapters 2-5 use the campaign views',()=>{
  assert.equal(isLaterChapter(S.story_new),false);assert.equal(chapterGoal(S.ch1_clear),null);assert.equal(talkFor(S.tutorial_new),null);
  assert.equal(isLaterChapter(S.ch2_briefing),true);
  const g=chapterGoal(S.ch2_briefing);assert.equal(g.title,'선배 브리핑');assert.match(g.label,/제2장 — 한정된 자원 · 업무 0\/2/);assert.match(g.where,/선배 대화/);
  assert.equal(g.what,S.ch2_briefing.story.objective,'the goal sentence is the engine objective');
});
test('the senior pages come from the engine; the last page of a briefing is the briefing action',()=>{
  const t=talkFor(S.ch2_briefing);assert.equal(t.event,'c2_briefing');assert.equal(t.briefing,true);assert.ok(t.pages.length>=3);
  for(const [role,text,speaker]of t.pages){assert.ok(['mentor','player','system','customer'].includes(role));assert.ok(text&&speaker);}
  assert.doesNotMatch(JSON.stringify(t.pages),/AIDC LINK|\[배정 설정·선택\]/,'Tk screen names are shown with the 3D place names');
  const done=talkFor(S.ch2_clear);assert.equal(done?.briefing??false,false);
});
test('chapter clear / failure screens read the engine result and its verdict only',()=>{
  const st=S.ch2_clear.story;assert.equal(missionOf(st),'success');assert.equal(st.chapter.state,'cleared');
  const rows=Object.fromEntries(resultRows(st));assert.equal(rows['미션 판정'],st.result.summary.verdict);assert.equal(rows['종합 평가'],`${st.result.overall}/100`);
  assert.ok(resultNotes(st).length>0);assert.equal(st.next.key,3);assert.equal(st.next.available,true);assert.equal(st.retry.available,true);
  const f=S.ch2_failed_done.story;assert.equal(missionOf(f),'failed');assert.equal(f.chapter.state,'failed');assert.equal(f.next,null,'practice: no next chapter');
  assert.equal(f.retry.kind,'practice');assert.deepEqual(f.campaign,[],'practice saves have no campaign');
  assert.equal(S.ch2_failure.story.chapter2.failurePending,true);assert.ok(S.ch2_failure.story.chapter2.failurePages.length);
});
test('campaign list: cleared / available / locked from the engine unlock rules',()=>{
  assert.deepEqual(S.ch1_clear.story.campaign.map(c=>c.state),['cleared','available','locked','locked','locked']);
  assert.deepEqual(S.ch2_clear.story.campaign.map(c=>[c.label,c.state]),[['제1장','cleared'],['제2장','cleared'],['제3장','available'],['제4장','locked'],['제5장','locked']]);
});
test('chapter 3: the world shows a symptom before the diagnosis and the engine evidence after it',()=>{
  const before=activePaths({game:S.ch3_symptom}).map(pathStatus)[0],after=activePaths({game:S.ch3_diagnosed}).map(pathStatus)[0];
  assert.equal(before.cause,'symptom');assert.equal(before.aidc,'ok');assert.doesNotMatch(before.message,/대역폭|단절|케이블/);
  assert.equal(after.cause,'primary_down');assert.equal(after.aidc,'ok');
  const card=S.ch3_diagnosed.story.chapter3;assert.deepEqual(card.diagnosed,[S.ch3_diagnosed.focus]);
  assert.deepEqual(cardRows({rows:[['원인','x'],['결과',1]]}),[['원인','x'],['결과','1']]);
});
test('chapter 5 Lab view never ships an answer key or hidden fault position',()=>{
  const t=S.lab_practice.story.training,json=JSON.stringify(t);
  for(const q of Object.values(t.questions)){assert.equal(q.correct,undefined);}
  assert.doesNotMatch(json,/"correct":"(blocked|icmp|path_down)"/);
  assert.ok(Object.values(t.network.segments).every(v=>v===null),'segments hidden before Stage 1 is passed');
  assert.equal(t.status.practice,true);assert.equal(t.prompt,'engineer@sg-edge:~$');
  for(const s of Object.values(S))for(const r of s.requests)assert.equal(r.incidentKind,undefined,'no incident cause in any request snapshot');
});
