"""Reparse cached source pages to a separate enriched CSV, without network requests."""
import argparse
import hashlib
from pathlib import Path
from nba_trivia.scraper import BASE, SourceError, collect
from nba_trivia.data import read_csv

ROOT = Path(__file__).resolve().parent

class CacheOnly:
    def __init__(self, directory):
        self.directory = Path(directory)

    def get(self, path):
        key = hashlib.sha256((BASE + path).encode()).hexdigest()
        cached = self.directory / (key + '.html')
        if not cached.is_file():
            raise SourceError(f'Missing cached page: {path}. No network requests were made.')
        return cached.read_text(encoding='utf-8')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'data/rosters_enriched.csv')
    args = parser.parse_args()
    original = ROOT/'data/rosters.csv'
    if args.output.resolve() == original.resolve():
        parser.exit(1, 'Choose a separate output; original rosters.csv is protected.\n')
    rows = read_csv(original)
    years = [row.season_end for row in rows]
    collect(CacheOnly(ROOT/'data/cache'), min(years), max(years), args.output)
    print(f'Enriched CSV written to {args.output}. Original CSV untouched.')

if __name__ == '__main__':
    main()
