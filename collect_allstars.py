"""Collect verified East/West All-Star rosters without changing the main CSVs."""
import argparse
from pathlib import Path
from nba_trivia.allstars import east_west_year,parse_allstars,write_allstars
from nba_trivia.scraper import Client,SourceError

ROOT=Path(__file__).resolve().parent

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start',type=int,default=1976)
    parser.add_argument('--end',type=int,default=2026)
    args=parser.parse_args()
    client=Client(ROOT/'data/cache');rows=[]
    try:
        for year in range(args.start,args.end+1):
            if not east_west_year(year):continue
            print(f'All-Star roster {year}',flush=True)
            rows.extend(parse_allstars(client.get(f'/allstar/NBA_{year}.html'),year))
        if not rows:raise SourceError('No supported East/West All-Star years selected')
        write_allstars(ROOT/'data/allstars.csv',rows)
        print(f'Saved {len(rows)} All-Star selections separately to data/allstars.csv')
    except SourceError as error:parser.exit(1,f'{error}\n')

if __name__=='__main__':main()
