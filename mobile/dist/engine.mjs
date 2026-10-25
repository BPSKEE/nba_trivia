const equivalents = {'ø':'o','ł':'l','đ':'d','ð':'d','þ':'th','æ':'ae','œ':'oe','ı':'i','ħ':'h','ŋ':'n','ŧ':'t','ß':'ss','’':"'",'‘':"'",'ʼ':"'",'‐':'-','‑':'-','–':'-'};
export const normalize = value => value.toLowerCase().normalize('NFKD').replace(/\p{M}/gu,'').replace(/[øłđðþæœıħŋŧß’‘ʼ‐‑–]/gu,c=>equivalents[c]).trim();
const numeric = ['season_end','height_inches','weight_lbs','games','minutes_total','ppg','rpg','apg','spg','bpg'];
export function parseCSV(text) {
  const records=[]; let row=[], field='', quoted=false;
  text=text.replace(/^\uFEFF/,'');
  for(let i=0;i<text.length;i++) { const c=text[i];
    if(c==='"') { if(quoted && text[i+1]==='"'){field+='"';i++;} else quoted=!quoted; }
    else if(c===','&&!quoted){row.push(field);field='';}
    else if(c==='\n'&&!quoted){row.push(field.replace(/\r$/,''));records.push(row);row=[];field='';}
    else field+=c;
  }
  if(quoted) throw Error('Unclosed quote in CSV.');
  if(field||row.length){row.push(field.replace(/\r$/,''));records.push(row);}
  const header=records.shift();
  for(const key of ['season_end','season','league','team_id','team_name','player_id','player_name',...numeric])
    if(!header?.includes(key)) throw Error(`Roster CSV is missing ${key}. Use the completed scraper output.`);
  const seen=new Set();
  const rows=records.filter(r=>r.some(Boolean)).map(r=>{
    if(r.length!==header.length) throw Error('Malformed CSV row.');
    const obj=Object.fromEntries(header.map((k,i)=>[k,r[i]]));
    for(const k of numeric){obj[k]=obj[k]===''?null:Number(obj[k]);if(obj[k]!==null&&!Number.isFinite(obj[k]))throw Error(`Invalid number: ${k}`);}
    for(const k of ['age','is_all_star']){obj[k]=obj[k]===undefined||obj[k]===''?null:Number(obj[k]);if(obj[k]!==null&&!Number.isFinite(obj[k]))throw Error(`Invalid number: ${k}`);}obj.college??='';
    const key=[obj.season_end,obj.league,obj.team_id,obj.player_id].join('|');
    if(seen.has(key))throw Error('Duplicate player/team/season record.');seen.add(key);return obj;
  });
  if(!rows.length)throw Error('CSV contains no players.');return rows;
}
export const HINTS=['jersey_number','height_inches','ppg','college','age'];
export const colleges = text => (text||'').split(',').map(x=>x.trim()).filter(Boolean);
export function suggestions(names,text){const q=normalize(text);return q?[...new Set(names)].filter(name=>{const key=normalize(name);return key.startsWith(q)||key.split(/\s+/).some(word=>word.startsWith(q));}).sort((a,b)=>normalize(a).localeCompare(normalize(b))):[];}
const choose=(items,rng)=>items[Math.floor(rng()*items.length)];
const group=(rows,key)=>{const m=new Map();for(const r of rows){const k=key(r);if(!m.has(k))m.set(k,[]);m.get(k).push(r);}return m;};
export function careerIndex(data){const rows=data.filter(r=>r.league==='NBA'),first=Math.min(...rows.map(r=>r.season_end));const result=new Map();for(const [pid,history] of group(rows,r=>r.player_id)){
 if(history.some(r=>r.season_end===first||r.games==null||r.games<0||(r.games>0&&(r.minutes_total==null||r.minutes_total<0))))continue;
 const played=history.filter(r=>r.games>0),games=played.reduce((s,r)=>s+r.games,0),minutes=played.reduce((s,r)=>s+r.minutes_total,0);
 if(games)result.set(pid,{games,minutes,mpg:minutes/games});}return result;}
export function createSession(data,mode,start,end,team='',goal='all',rng=Math.random,allstars=[]){
 if(!Number.isInteger(start)||!Number.isInteger(end)||start<1976||end<start)throw Error('Choose a valid range starting in 1976 or later.');
 if(mode==='all-stars'){
  const groups=group(allstars.filter(r=>r.year>=start&&r.year<=end),r=>r.year);
  const years=[...groups.keys()].filter(year=>['East','West'].every(c=>groups.get(year).filter(r=>r.conference===c).length>=5));
  if(!years.length)throw Error('No East/West All-Star game in this range. Choose 1976–2017 (except 1999), or 2024.');
  const year=choose(years.sort((a,b)=>a-b),rng);
  const answers=groups.get(year).map(r=>({...r,season_end:year,season:`${year-1}-${String(year).slice(-2)}`,team_id:r.conference,team_name:r.conference}));
  return new Session(answers,answers,mode,goal);
 }
 const rows=data.filter(r=>r.league==='NBA'&&r.season_end>=start&&r.season_end<=end);
 for(let y=start;y<=end;y++)if(!rows.some(r=>r.season_end===y))throw Error(`Dataset has no NBA records for ${y}. Choose a covered range.`);
 let candidates=[],career;
 if(mode==='one-player'){
  for(const roster of group(rows,r=>`${r.team_id}|${r.season_end}`).values()){
   if(team&&roster[0].team_id!==team)continue;
   const answers=roster.filter(r=>r.minutes_total!=null&&r.minutes_total>=250).sort((a,b)=>(a.ppg==null)-(b.ppg==null)||(b.ppg??0)-(a.ppg??0)||a.player_id.localeCompare(b.player_id));
   if(answers.length)candidates.push(answers);
  }
 }else if(mode==='player-teams'){
  for(const history of group(rows,r=>`${r.player_id}|${r.season_end}`).values()){
   if(history.some(r=>r.games==null))continue;
   const played=history.filter(r=>r.games>0);
   if(!played.length||played.some(r=>r.minutes_total==null)||!played.some(r=>!team||r.team_id===team))continue;
   const games=played.reduce((s,r)=>s+r.games,0),minutes=played.reduce((s,r)=>s+r.minutes_total,0);
   if(minutes>=250&&minutes/games>=15)candidates.push(played);
  }
 }else if(mode==='college'){
  career=careerIndex(data);
  for(const history of group(rows.filter(r=>r.games>0&&colleges(r.college).length&&(!team||r.team_id===team)),r=>r.player_id).values()){
   const stats=career.get(history[0].player_id);
   if(stats&&stats.mpg>=25&&stats.minutes>=2000)candidates.push([choose(history,rng)]);
  }
 }else throw Error('Unknown game mode.');
 if(!candidates.length)throw Error(mode==='college'?'No eligible players: college mode requires 25 career MPG and 2,000 career minutes. Incomplete careers are excluded.':mode==='player-teams'?'No eligible player-seasons with 250 minutes and 15 MPG.':'No roster players with 250 team minutes in this selection.');
 const session=new Session(rows,choose(candidates,rng),mode,goal);
 if(career)session.career=career.get(session.anchor.player_id);
 return session;
}
export class Session {
 constructor(rows,answers,mode,goal){Object.assign(this,{rows,answers,mode,goal,wrong:0,outcome:null});this.found=new Set();this.revealed=[];}
 id(r){return this.mode==='player-teams'?r.team_id:r.player_id;}
 label(r){return this.mode==='player-teams'?r.team_name:this.mode==='college'?this.collegeAnswers.join(', '):r.player_name;}
 get anchor(){return this.answers[0];}
 get collegeAnswers(){return [...new Set(this.rows.filter(r=>r.player_id===this.anchor.player_id).flatMap(r=>colleges(r.college)))].sort();}
 get teamOptions(){return [...new Map(this.rows.filter(r=>r.season_end===this.anchor.season_end).map(r=>[r.team_id,r.team_name]))].sort((a,b)=>a[1].localeCompare(b[1]));}
 guess(text){
  if(this.outcome)return 'This game has ended.';
  const value=normalize(text);if(!value)return 'Enter a name before submitting.';
  if(this.mode==='college'){
   if(this.collegeAnswers.some(name=>normalize(name)===value)){this.found.add(this.anchor.player_id);this.outcome='victory';return 'Correct!';}
   return `${text.trim()} is not a listed college for ${this.anchor.player_name}. Try again.`;
  }
  const matches=this.answers.filter(r=>(this.mode==='player-teams'?[r.team_name,r.team_id]:[r.player_name]).some(v=>normalize(v)===value));
  if(matches.length){const fresh=matches.filter(r=>!this.found.has(this.id(r)));if(!fresh.length)return 'You already found that answer.';fresh.forEach(r=>this.found.add(this.id(r)));const needed=this.mode==='player-teams'&&this.goal==='one'?1:this.answers.length;if(this.found.size>=needed)this.outcome='victory';return 'Correct!';}
  const a=this.anchor;
  if(this.mode==='player-teams'){if(++this.wrong>=5)this.outcome='failure';return `${a.player_name} did not play for ${text.trim()} in ${a.season_end}. Incorrect guesses: ${this.wrong}/5.`;}
  if(this.mode==='all-stars')return `${text.trim()} was not on either All-Star roster in ${a.season_end}.`;
  if(this.rows.some(r=>normalize(r.player_name)===value&&r.team_id===a.team_id&&r.season_end===a.season_end))return `${text.trim()} was on ${a.team_name} but did not meet the 250-minute requirement.`;
  return `${text.trim()} was not on ${a.team_name} in ${a.season_end}.`;
 }
 hint(){if(this.outcome||this.mode!=='one-player'||this.revealed.length)return;this.revealed=[...HINTS];}
 quit(){if(!this.outcome)this.outcome='quit';}
 traded(row){return new Set(this.rows.filter(r=>r.player_id===row.player_id&&r.season_end===row.season_end&&r.games>0).map(r=>r.team_id)).size>1;}
 stats(){const games=this.answers.reduce((s,r)=>s+r.games,0),minutes=this.answers.every(r=>r.minutes_total!=null)?this.answers.reduce((s,r)=>s+r.minutes_total,0):null;return {games,minutes,...Object.fromEntries(['ppg','rpg','apg','spg','bpg'].map(k=>[k,this.answers.every(r=>r[k]!=null)?(this.answers.reduce((s,r)=>s+r[k]*r.games,0)/games).toFixed(1):'—']))};}
}
