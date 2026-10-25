import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {createSession,normalize,suggestions,HINTS} from '../dist/engine.mjs';
const row=(extra={})=>({league:'NBA',season_end:2024,season:'2023-24',team_id:'AAA',team_name:'Alpha',player_id:'one',player_name:'Nikola Jokić',games:80,minutes_total:2400,ppg:20,college:'College A',...extra});
const zero=()=>0;
test('roster eligibility, PPG ordering, one complete hint and unlimited guesses',()=>{
 const data=[row(),row({player_id:'two',player_name:'Other',ppg:30}),row({player_id:'low',minutes_total:249})];
 const s=createSession(data,'one-player',2024,2024,'','all',zero);
 assert.deepEqual(s.answers.map(r=>r.ppg),[30,20]);
 for(let i=0;i<10;i++)s.guess('wrong');assert.equal(s.outcome,null);
 s.hint();s.hint();assert.deepEqual(s.revealed,HINTS);
 s.guess('nikola jokic');assert.equal(s.outcome,null);s.guess('Other');assert.equal(s.outcome,'victory');
});
test('player teams requires 250 minutes and 15 MPG, preserves short stints and historical options',()=>{
 const data=[row({games:20,minutes_total:590}),row({team_id:'BBB',team_name:'Beta',games:1,minutes_total:10}),row({player_id:'low',games:80,minutes_total:1000}),row({player_id:'brief',games:10,minutes_total:249})];
 const s=createSession(data,'player-teams',2024,2024,'AAA','all',zero);
 assert.equal(s.anchor.player_id,'one');assert.equal(s.answers.length,2);assert.equal(s.teamOptions.length,2);
 s.guess('BBB');assert.equal(s.outcome,null);s.guess('Alpha');assert.equal(s.outcome,'victory');
 const q=createSession(data,'player-teams',2024,2024,'','one',zero);q.guess('Beta');assert.equal(q.outcome,'victory');
 const f=createSession(data,'player-teams',2024,2024,'','all',zero);for(let i=0;i<5;i++)f.guess('wrong');assert.equal(f.outcome,'failure');
});
test('college uses full loaded career, minimum 2000 and 25 MPG, excludes boundary careers',()=>{
 const data=[row({season_end:1976,player_id:'boundary'}),row(),row({season_end:2023,games:80,minutes_total:2400}),row({player_id:'brief',minutes_total:1999,games:60}),row({player_id:'slow',minutes_total:2000,games:81})];
 const s=createSession(data,'college',2024,2024,'','all',zero);
 assert.equal(s.anchor.player_id,'one');assert.equal(s.career.minutes,4800);assert.equal(s.career.mpg,30);
 s.guess('college a');assert.equal(s.outcome,'victory');
});
test('all star game needs both conferences, accepts all names and quit reveals state',()=>{
 const stars=['East','West'].flatMap(conference=>Array.from({length:5},(_,i)=>({year:2024,conference,player_id:conference+i,player_name:conference+i})));
 const s=createSession([],'all-stars',2024,2024,'','all',zero,stars);
 for(const r of stars)s.guess(r.player_name);assert.equal(s.outcome,'victory');
 const q=createSession([row()],'one-player',2024,2024);q.quit();assert.equal(q.outcome,'quit');
 assert.throws(()=>createSession([],'all-stars',2024,2024,'','all',zero,stars.slice(0,5)));
});
test('autocomplete and normalization handle accents and partial first names',()=>{
 assert.equal(normalize('Ömer Aşık'),'omer asik');assert.equal(normalize('Ø Ł Æ ß'),'o l ae ss');
 assert.deepEqual(suggestions(['Nikola Jokić','Other'], 'jok'),['Nikola Jokić']);
});
test('bundled data supports all four modes and includes enriched All-Star metadata',()=>{
 const rows=JSON.parse(fs.readFileSync(new URL('../../docs/rosters.json',import.meta.url)));
 const stars=JSON.parse(fs.readFileSync(new URL('../../docs/allstars.json',import.meta.url)));
 for(const mode of ['one-player','player-teams','college','all-stars'])assert.ok(createSession(rows,mode,2024,2024,'','all',zero,stars).answers.length);
 assert.ok(stars.every(r=>'age' in r && 'college' in r && 'teams' in r));
});
