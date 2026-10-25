"""Actual East/West All-Star game rosters, separate from regular-season team data."""
import csv
import html
import os
import random
import re
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from .scraper import BASE, SourceError, tables, player_id, cell


def east_west_year(year):
    return (1976 <= year <= 2017 and year != 1999) or year == 2024


@dataclass(frozen=True)
class AllStarPlayer:
    year: int
    conference: str
    player_id: str
    player_name: str
    status: str
    source_url: str


def parse_allstars(source, year):
    parsed = tables(source)
    output = {}
    for conference in ('East','West'):
        if not parsed.get(conference):
            raise SourceError(f'No verified {conference} All-Star table for {year}')
        for row in parsed[conference]:
            pid = player_id(row)
            if pid:
                output[pid] = AllStarPlayer(year,conference,pid,cell(row,'player','name_display'),
                                           'game_roster',f'{BASE}/allstar/NBA_{year}.html')
    # Injury/replacement notes identify selected players omitted from box scores.
    pattern = r'<a\b[^>]*href="/players/[a-z]/([a-z0-9]+)\.html"[^>]*>((?:(?!</a>).)*)</a>\s*\((East|West)\)\s*:'
    for pid,name,conference in re.findall(pattern,source,re.S):
        name=html.unescape(re.sub('<[^>]+>','',name)).strip()
        output.setdefault(pid,AllStarPlayer(year,conference,pid,name,'selected_did_not_play',
                                           f'{BASE}/allstar/NBA_{year}.html'))
    for conference in ('East','West'):
        if sum(r.conference==conference for r in output.values()) < 5:
            raise SourceError(f'Incomplete {conference} roster for {year}')
    return sorted(output.values(), key=lambda r:(r.conference,r.player_name))


def write_allstars(path, rows):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd,temp=tempfile.mkstemp(dir=path.parent,suffix='.tmp')
    try:
        with os.fdopen(fd,'w',encoding='utf-8',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(AllStarPlayer.__dataclass_fields__))
            writer.writeheader()
            writer.writerows(asdict(r) for r in rows)
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):os.unlink(temp)


def read_allstars(path):
    with open(path,encoding='utf-8',newline='') as stream:
        rows=[];seen=set()
        for record in csv.DictReader(stream):
            record['year']=int(record['year']);row=AllStarPlayer(**record)
            if row.conference not in ('East','West') or not east_west_year(row.year):
                raise ValueError('Unsupported All-Star conference/year')
            key=(row.year,row.player_id)
            if key in seen:raise ValueError('Duplicate All-Star player/year')
            seen.add(key);rows.append(row)
        return rows


def make_allstar_session(rosters,start,end,rng=None,*,season_rows=()):
    from .data import PlayerSeason
    from .modes import Session
    rng=rng or random.Random()
    groups={}
    for row in rosters:
        if start<=row.year<=end:groups.setdefault(row.year,[]).append(row)
    years=[year for year,rs in groups.items() if all(sum(r.conference==c for r in rs)>=5 for c in ('East','West'))]
    if not years:
        raise ValueError('No East/West All-Star game in this range. Supported: 1976–2017 except 1999, and 2024. Other years used different formats or had no game.')
    year=rng.choice(sorted(years))
    rows=[PlayerSeason(year,f'{year-1}-{str(year)[-2:]}','NBA',r.conference,r.conference,
                       r.player_id,r.player_name,is_all_star=1,source_url=r.source_url)
          for r in groups[year]]
    session = Session(rows,rows,'all-stars','all',rng)
    session.all_star_details = {}
    for answer in rows:
        matches = [r for r in season_rows if r.league == 'NBA' and r.season_end == year
                   and r.player_id == answer.player_id]
        teams = sorted({r.team_name for r in matches})
        colleges = sorted({r.college for r in matches if r.college})
        age = next((r.age for r in matches if r.age is not None), None)
        session.all_star_details[answer.player_id] = {
            'teams': ' / '.join(teams) or '—', 'age': str(age) if age is not None else '—',
            'college': ' / '.join(colleges) or '—'}
    return session
