"""Build an independent GitHub Pages website, with all data included."""
import argparse
import hashlib
import json
import shutil
import zipfile
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from nba_trivia.data import read_csv
from nba_trivia.allstars import read_allstars

ROOT=Path(__file__).resolve().parent
ASSETS=('index.html','app.mjs','engine.mjs','style.css','sw.js','manifest.webmanifest','icon.svg','apple-touch-icon.png')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data',type=Path,default=ROOT/'data/rosters_enriched.csv')
    args=parser.parse_args()
    if not args.data.is_file() or not (ROOT/'data/allstars.csv').is_file():
        parser.exit(1,'Build requires the enriched roster CSV and data/allstars.csv. Existing data is never modified.\n')
    rows=[r for r in read_csv(args.data) if r.league=='NBA' and r.season_end>=1976]
    if not rows:parser.exit(1,'No NBA records from 1976 onward.\n')
    source=ROOT/'mobile/dist';output=ROOT/'docs';output.mkdir(exist_ok=True)
    lookup=defaultdict(list)
    for r in rows:lookup[(r.season_end,r.player_id)].append(r)
    stars=[]
    for r in read_allstars(ROOT/'data/allstars.csv'):
        matches=lookup[(r.year,r.player_id)]
        stars.append({**asdict(r),'teams':' / '.join(sorted({m.team_name for m in matches})) or '—',
                      'age':next((m.age for m in matches if m.age is not None),None),
                      'college':' / '.join(sorted({m.college for m in matches if m.college}))})
    for name,value in [('rosters.json',[asdict(r) for r in rows]),('allstars.json',stars)]:
        text=json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False)
        (source/name).write_text(text,encoding='utf-8')
    for name in (*ASSETS,'rosters.json','allstars.json'):shutil.copyfile(source/name,output/name)
    digest=hashlib.sha256(b''.join((output/name).read_bytes() for name in (*ASSETS,'rosters.json','allstars.json'))).hexdigest()[:12]
    (output/'sw.js').write_text((source/'sw.js').read_text().replace('courtside-standalone-v4','courtside-standalone-'+digest),encoding='utf-8')
    (output/'.nojekyll').write_text('')
    archive=ROOT/'dist/NBA Trivia Website.zip';archive.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for path in sorted(output.iterdir()):
            if path.is_file():z.write(path,'docs/'+path.name)
    print(f'Website ready: {output}\n{len(rows):,} season records and {len(stars):,} All-Star selections included.\nUpload-ready archive: {archive}\nNo ChatGPT services, account, server or separate CSV needed.')

if __name__=='__main__':main()
