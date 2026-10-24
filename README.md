# NBA trivia framework

Python 3.10+; install with `python3 -m pip install -e .`. The runtime uses certifi for trusted HTTPS certificate roots in addition to the platform defaults. Run commands from this directory. Includes terminal and native desktop interfaces.

```sh
# At startup, build all historical data if the CSV is missing, then play:
python3 -m nba_trivia

# Recommended first collection: one complete season:
python3 -m nba_trivia scrape --start 2024 --end 2024

# Full BAA/NBA history through the latest completed season:
python3 -m nba_trivia scrape

python3 -m nba_trivia play --offline --mode guess-player
python3 -m nba_trivia play --offline --mode guess-team
python3 -m nba_trivia play --offline --mode higher-stat --season 2024
python3 -m nba_trivia query --offline --season 2024 --team BOS --sort ppg --descending
python3 -m unittest discover -s tests -v
```

The default output is `data/rosters.csv`; use `--data` and `--cache` for other locations. Years mean season **ending** years: 2024 is 2023–24. Default collection starts with the season ending in 1976. Earlier BAA/NBA data remains available through an explicit CLI `--start` argument. ABA, playoffs, and the unfinished current season are excluded. Team identifiers come from each historical season, preserving defunct and renamed teams.

## CSV contract

UTF-8 with headers, deterministically sorted by `(season_end, league, team_id, player_id)`. Each row is one player on one team's season roster. A traded player has separate team rows and team-specific statistics. Do not sum per-game rates across rows. No league-wide combined/TOT records are inserted.

| Fields | Meaning |
| --- | --- |
| `season_end`, `season`, `league` | Integer ending year, display season, BAA/NBA |
| `team_id`, `team_name` | Historical source abbreviation and name |
| `player_id`, `player_name` | Stable source player ID and display name |
| `position`, `jersey_number` | Roster strings; keep jersey numbers as text (`00` differs from `0`) |
| `height_inches`, `weight_lbs` | Numeric roster measurements |
| `games`, `minutes_total` | Regular-season team games played and total minutes |
| `ppg`, `rpg`, `apg`, `spg`, `bpg` | Team totals divided by games played, rounded to one decimal |
| `source_url` | Team-season source page |

Empty numeric cells mean **unknown/unrecorded**, not zero. For example, older seasons lack steals and blocks. Players on the roster without a matching totals record remain in the CSV with empty stats. Measurements are those displayed by the source roster, not independently verified measurements taken that season. The source may not capture every jersey number worn during a season.

`nba_trivia.data.read_csv()` restores numeric types and nulls, validates headers and duplicate keys. `Catalog` provides player and team-season indexes plus filters and sorting. Missing values always sort last. CSV writes are atomic: an interrupted or failed full collection preserves the previous file. A successful explicitly limited scrape **replaces** the CSV with that selected range; it does not append to an existing dataset.

## Collection behavior

The collector discovers team URLs from each league season page and joins roster and totals tables by player ID, including HTML-comment-wrapped tables. It uses sequential requests at least four seconds apart, respects robots.txt and its crawl delay, and stops on access errors. Thousands of historical team pages can take hours on the initial run. Page caching allows an interrupted run to resume without refetching completed pages; rerun the same command. There is no partial CSV publication.

Normal startup reuses an existing CSV. `--refresh` rebuilds it from cached pages; to fetch newer versions, remove the relevant cache entries or choose a new `--cache` directory. Refresh failure during play/query falls back to an existing CSV and reports the failure. `--offline` guarantees no network access.

Basketball Reference may block automated collection. The collector does not bypass blocks, retry aggressively, or disable TLS certificate verification. Review the source's current [bot policy](https://www.sports-reference.com/bot-traffic.html) and [data-use policy](https://www.sports-reference.com/data_use.html), including permissions needed for distribution. A source block requires authorized data access or a compatible CSV obtained separately.

**Verification:** fixture tests cover parsing, CSV handling, game modes, and TLS verification. After adding certifi, a live request successfully fetched robots.txt and the 2024 season index and began collecting team pages. Full historical coverage remains unverified. Explicit `SSL_CERT_FILE` / `SSL_CERT_DIR` settings are respected; configure these for a private trusted CA if needed.

## Game and executable extension

`game.py` separates question generation from input/output. The modes currently provide guess-player, guess-team, and higher-PPG comparisons. Filters apply before question generation; restrictive filters may leave too few candidates. Guess-team excludes another valid team for traded players from distractors. Questions can repeat between rounds; richer question selection, persistent history and richer question selection are future work.

For a distributable executable, install PyInstaller in a virtual environment and build on the target operating system:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install pyinstaller
.venv/bin/python -m PyInstaller --onefile --name nba-trivia run_game.py
```

Run `dist/nba-trivia --data /writable/location/rosters.csv --cache /writable/location/cache`. First startup collects data when missing; ship a separately authorized CSV and use `--offline` for an entirely local game. Build once per target OS; packaging has not been verified in this environment.

## Desktop interface

Run `python3 run_desktop.py` for the native desktop menu. Choose a game mode, first and last season ending years (inclusive, minimum 1976), and number of questions, then press **Start game**. Each question has clickable answers, feedback, and a score; the results screen returns to the menu.

Use **Choose roster CSV…** to load an existing CSV matching the schema above. The archive CSVs are not compatible directly. Missing selected seasons produce a visible message instead of silently narrowing the range. First startup without a roster CSV collects 1976 through the latest completed season in the background; existing data is reused. Closing during collection retains cached pages, though the in-flight request may need to be repeated next launch.

For a clickable macOS `.app` (or Windows `.exe` when built on Windows):

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[build]'
.venv/bin/python -m PyInstaller --noconfirm --windowed --onedir --name 'NBA Trivia' run_desktop.py
```

Open `dist/NBA Trivia.app` on macOS. Packaged builds store writable roster data and cache in `~/Library/Application Support/NBA Trivia` on macOS, `%LOCALAPPDATA%/NBA Trivia` on Windows, or the XDG data directory on Linux. The **Choose roster CSV…** button can load your existing dataset instead. File selection currently lasts for that application session. Source launches use the project's `data/` folder. Builds are local and unsigned.
