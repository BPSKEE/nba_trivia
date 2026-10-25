"""Refresh the separate mobile site's dataset without changing desktop or scraper files."""
import argparse
import json
from dataclasses import asdict
from pathlib import Path
from nba_trivia.data import read_csv

ROOT = Path(__file__).resolve().parent

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, default=ROOT / 'data/rosters.csv')
    args = parser.parse_args()
    if not args.data.is_file():
        parser.exit(1, 'Roster CSV is not ready. Let the scraper finish, then run make mobile-data.\n')
    rows = [asdict(r) for r in read_csv(args.data) if r.league == 'NBA' and r.season_end >= 1976]
    if not rows:
        parser.exit(1, 'No NBA records from 1976 onward.\n')
    output = ROOT / 'mobile/dist/rosters.json'
    temporary = output.with_suffix('.tmp')
    temporary.write_text(json.dumps(rows, ensure_ascii=False, separators=(',', ':'), allow_nan=False), encoding='utf-8')
    temporary.replace(output)
    print(f'Mobile roster ready: {len(rows):,} records. Republish the mobile site to update the hosted game.')

if __name__ == '__main__':
    main()
