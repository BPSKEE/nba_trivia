"""Build a self-contained desktop release without touching the collector."""
import argparse
import subprocess
import sys
from pathlib import Path

from nba_trivia.data import read_csv, write_csv

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, default=ROOT / 'data/rosters.csv')
    args = parser.parse_args()
    if not args.data.is_file():
        parser.exit(1, 'Roster CSV is not ready. Let the scraper finish, then run make again. '
                    'For a different file: .venv/bin/python build_app.py --data /path/to/rosters.csv\n')
    try:
        rows = read_csv(args.data)
    except (ValueError, OSError) as error:
        parser.exit(1, f'Cannot bundle roster CSV: {error}\n')
    # Build from a validated snapshot, leaving the source CSV unchanged.
    snapshot = ROOT / 'build/bundled_data/rosters.csv'
    write_csv(snapshot, rows)
    separator = ';' if sys.platform == 'win32' else ':'
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--windowed',
               '--onefile' if sys.platform == 'win32' else '--onedir',
               '--name', 'NBA Trivia', '--add-data', f'{snapshot}{separator}data',
               'run_desktop.py']
    subprocess.run(command, cwd=ROOT, check=True)
    if sys.platform == 'darwin':
        output = ROOT / 'dist/NBA Trivia.zip'
        subprocess.run(['ditto', '-c', '-k', '--sequesterRsrc', '--keepParent',
                        str(ROOT / 'dist/NBA Trivia.app'), str(output)], check=True)
    elif sys.platform == 'win32':
        output = ROOT / 'dist/NBA Trivia.exe'
    else:
        output = ROOT / 'dist/NBA Trivia'
    print(f'Release ready: {output}\nBundled {len(rows):,} roster records. No separate CSV is needed.')


if __name__ == '__main__':
    main()
