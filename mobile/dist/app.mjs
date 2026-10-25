import {createSession,suggestions,colleges,HINTS} from './engine.mjs';
const $=id=>document.getElementById(id);
let boardSettings=null;
let rows=[],stars=[],session=null,namePool=[],collegePool=[],activeSuggestion=-1,suggestionNames=[];
const modeNames={'one-player':'Complete the roster','player-teams':'Find the teams',college:'Guess the college','all-stars':'East / West All-Stars'};
const help={'one-player':'Name every player with 250+ team minutes. One hint button reveals jersey, height, PPG, college and age.',
 'player-teams':'Player-seasons need 250 minutes and 15 MPG. Choose from season-correct team buttons. Five wrong picks maximum.',
 college:'A fixed 25 career MPG and 2,000 career minutes minimum. Any listed college is accepted. Incomplete careers are excluded.',
 'all-stars':'Complete East and West. Supports 1976–2017 except 1999, plus 2024; other game formats are skipped. Team filter ignored.'};
const show=v=>v==null||v===''?'—':String(v);
function el(tag,text,className){const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(className)node.className=className;return node;}
function updateMode(){$('mode-help').textContent=help[$('mode').value];$('goal-container').hidden=$('mode').value!=='player-teams';$('team').disabled=$('mode').value==='all-stars';}
$('mode').onchange=updateMode;updateMode();
function closeSuggestions(){$('suggestions').hidden=true;$('suggestions').replaceChildren();$('guess').setAttribute('aria-expanded','false');$('guess').removeAttribute('aria-activedescendant');activeSuggestion=-1;}
function chooseSuggestion(name){$('guess').value=name;closeSuggestions();$('guess').focus({preventScroll:true});}
$('guess').oninput=()=>{
 const pool=session?.mode==='college'?collegePool:namePool;const matches=suggestions(pool,$('guess').value);suggestionNames=matches.slice(0,100);activeSuggestion=-1;
 $('suggestions').replaceChildren();if(!suggestionNames.length){closeSuggestions();return;}
 for(const [i,name] of suggestionNames.entries()){const option=el('button',name);option.type='button';option.id=`suggestion-${i}`;option.setAttribute('role','option');option.onclick=()=>chooseSuggestion(name);$('suggestions').append(option);}
 if(matches.length>100)$('suggestions').append(el('p','Type more letters to narrow the results.','small'));
 $('suggestions').hidden=false;$('guess').setAttribute('aria-expanded','true');
};
$('guess').onkeydown=event=>{if($('suggestions').hidden)return;if(['ArrowDown','ArrowUp'].includes(event.key)){event.preventDefault();activeSuggestion=(activeSuggestion+(event.key==='ArrowDown'?1:-1)+suggestionNames.length)%suggestionNames.length;for(const [i,node] of [...$('suggestions').querySelectorAll('button')].entries())node.setAttribute('aria-selected',String(i===activeSuggestion));const node=$(`suggestion-${activeSuggestion}`);$('guess').setAttribute('aria-activedescendant',node.id);node.scrollIntoView({block:'nearest'});}else if(event.key==='Enter'&&activeSuggestion>=0){event.preventDefault();chooseSuggestion(suggestionNames[activeSuggestion]);}else if(event.key==='Escape'){event.preventDefault();closeSuggestions();}};
document.addEventListener('click',event=>{if(!event.target.closest('.autocomplete'))closeSuggestions();});
function startBoard(settings){try{const nextSession=createSession(rows,settings.mode,settings.start,settings.end,settings.team,settings.goal,Math.random,stars);session=nextSession;boardSettings={...settings};$('menu').hidden=true;$('game').hidden=false;$('game-mode').textContent=modeNames[session.mode];$('guess').value='';$('feedback').textContent='';$('feedback').className='';closeSuggestions();const a=session.anchor;
 $('prompt').textContent=session.mode==='college'?`Which college did ${a.player_name} attend?`:session.mode==='all-stars'?`Name the East and West All-Stars in ${a.season_end}.`:session.mode==='player-teams'?`Name ${session.goal==='one'?'one team':'all teams'} ${a.player_name} played for in ${a.season}.`:`Complete ${a.team_name}’s ${a.season} roster.`;
 $('stats').textContent=session.mode==='college'?`${a.team_name}, ${a.season}. Career: ${session.career.mpg.toFixed(1)} MPG / ${session.career.minutes.toLocaleString()} minutes. Any listed college wins.`:session.mode==='all-stars'?'Team(s), age and college describe the season. Includes selected injured players and their replacements.':session.mode==='one-player'?'Every player with at least 250 minutes for this team. Rows ordered by PPG. Unlimited guesses.':(()=>{const stats=session.stats();return `${stats.games} games · ${show(stats.minutes)} minutes. Approximate season averages: ${['ppg','rpg','apg','spg','bpg'].map(k=>`${k.toUpperCase()} ${stats[k]}`).join(' · ')}. Five wrong guesses allowed.`;})();
 $('guess-label').textContent=session.mode==='college'?'College name':'Player name';buildTeamButtons();render();window.scrollTo(0,0);
 }catch(error){if($('game').hidden)$('status').textContent=error.message;else $('feedback').textContent=error.message;}}
$('settings').onsubmit=event=>{event.preventDefault();startBoard({mode:$('mode').value,start:Number($('start').value),end:Number($('end').value),team:$('team').value,goal:$('goal').value});};
$('next').onclick=()=>{if(boardSettings)startBoard(boardSettings);};
function buildTeamButtons(){$('team-buttons').replaceChildren();if(session.mode!=='player-teams')return;for(const [id,name] of session.teamOptions){const b=el('button',name,'secondary');b.type='button';b.dataset.team=id;b.onclick=()=>{const message=session.guess(id);$('feedback').textContent=message;b.disabled=true;b.classList.add(session.found.has(id)?'correct-team':'wrong-team');render();};$('team-buttons').append(b);}}
function makeTable(headings,values,className=''){
 const table=el('table',undefined,className),head=el('thead'),header=el('tr');for(const title of headings)header.append(el('th',title));head.append(header);table.append(head);const body=el('tbody');
 for(const row of values){const tr=el('tr');if(row.star)tr.classList.add('all-star');if(row.reveal)tr.classList.add('revealed-answer');row.values.forEach((value,i)=>{const td=el('td',show(value));td.dataset.label=headings[i];if(i===0&&row.star){const star=el('span','★','star');star.setAttribute('aria-label','All-Star that season');td.prepend(star);}tr.append(td);});body.append(tr);}table.append(body);return table;
}
function render(){const s=session,over=!!s.outcome;$('tables').replaceChildren();$('progress').textContent=`${s.found.size} / ${s.answers.length} found${s.mode==='player-teams'?` · ${s.wrong}/5 incorrect`:''}`;
 if(s.mode==='all-stars'){
  const panels=el('div',undefined,'conferences');const counts=[];
  for(const conference of ['East','West']){const roster=s.answers.filter(r=>r.conference===conference);const panel=el('section');panel.append(el('h3',`${conference} All-Stars`));panel.append(makeTable(['Player','NBA team(s)','Age','College'],roster.map(r=>({values:[over||s.found.has(r.player_id)?r.player_name:'________',r.teams,r.age,r.college],reveal:over&&!s.found.has(r.player_id)})),'allstar-table'));panels.append(panel);counts.push(`${conference}: ${roster.filter(r=>s.found.has(r.player_id)).length}/${roster.length}`);}
  $('tables').append(panels);$('progress').textContent=counts.join(' · ');
 }else if(s.mode==='college'){$('tables').append(makeTable(['College'],[{values:[over?s.collegeAnswers.join(', '):'________________'],reveal:over&&s.outcome!=='victory'}]));
 }else if(s.mode==='player-teams'){$('tables').append(makeTable(['Team','Games'],s.answers.map(r=>({values:[over||s.found.has(r.team_id)?r.team_name:'________________',r.games],reveal:over&&!s.found.has(r.team_id)}))));
 }else{
  const titles=['Player','Position','Games','Traded','Jersey','Height','PPG','College','Age'];
  $('tables').append(makeTable(titles,s.answers.map(r=>{const found=s.found.has(r.player_id),visible=over||found;return {values:[visible?r.player_name:'________________',r.position,r.games,s.traded(r)?'Yes':'No',...HINTS.map(k=>visible||s.revealed.includes(k)?k==='height_inches'&&r[k]!=null?`${Math.floor(r[k]/12)}′ ${r[k]%12}″`:r[k]:'Hidden')],star:r.is_all_star===1,reveal:over&&!found};}),'roster-table'));
 }
 $('star-legend').hidden=s.mode!=='one-player';$('team-buttons').hidden=s.mode!=='player-teams';$('guess-form').hidden=over||s.mode==='player-teams';$('hint').hidden=s.mode!=='one-player'||over;$('hint').disabled=s.revealed.length>0;$('hint').textContent=s.revealed.length?'Hints revealed':'Reveal all hints';$('quit').hidden=over;$('back').hidden=!over;
 if(over){$('feedback').className='win';$('feedback').textContent={victory:'Victory! You know your basketball.',quit:'Answers revealed in red.',failure:'Game over — five incorrect guesses.'}[s.outcome];for(const b of $('team-buttons').querySelectorAll('button'))b.disabled=true;closeSuggestions();}
}
$('guess-form').onsubmit=event=>{event.preventDefault();if(session.outcome)return;const message=session.guess($('guess').value);$('feedback').textContent=message;if(message==='Correct!')$('guess').value='';closeSuggestions();render();};$('hint').onclick=()=>{session.hint();render();};$('quit').onclick=()=>{session.quit();render();};$('back').onclick=()=>{$('game').hidden=true;$('menu').hidden=false;session=null;closeSuggestions();window.scrollTo(0,0);};
$('share').onclick=async()=>{const url=new URL('./',location.href).href;try{if(navigator.share)await navigator.share({title:'Courtside · NBA Trivia',url});else{await navigator.clipboard.writeText(url);$('share-status').textContent='Game link copied. Send it to a friend—no files needed.';}}catch(error){if(error.name!=='AbortError')$('share-status').textContent=`Share this link: ${url}`;}};
async function init(){try{const responses=await Promise.all([fetch('./rosters.json'),fetch('./allstars.json')]);if(responses.some(r=>!r.ok))throw Error('The game data could not load. Reload online; if you own this site, run make website and upload the complete docs folder.');[rows,stars]=await Promise.all(responses.map(r=>r.json()));
 const years=rows.map(r=>r.season_end),first=Math.max(1976,Math.min(...years)),last=Math.max(...years);for(let y=first;y<=last;y++)for(const id of ['start','end'])$(id).add(new Option(String(y),String(y)));$('end').value=String(last);
 const teams=new Map();for(const r of rows){if(!teams.has(r.team_id))teams.set(r.team_id,new Set());teams.get(r.team_id).add(r.team_name);}for(const [id,names] of [...teams].sort((a,b)=>[...a[1]][0].localeCompare([...b[1]][0])))$('team').add(new Option(`${[...names].sort().join(' / ')} (${id})`,id));
 namePool=rows.map(r=>r.player_name).concat(stars.map(r=>r.player_name));collegePool=rows.flatMap(r=>colleges(r.college));$('status').textContent=`${rows.length.toLocaleString()} season records · ${new Set(stars.map(r=>r.year)).size} East/West All-Star years · Ready to play.`;$('start-button').disabled=false;
 if('serviceWorker'in navigator)navigator.serviceWorker.register('./sw.js').catch(()=>{});
 }catch(error){$('status').textContent=error.message;}}
init();
