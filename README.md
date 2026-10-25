# NBA trivia framework

Python 3.10+; install with `python3 -m pip install -e .`. The runtime uses certifi for trusted HTTPS certificate roots in addition to the platform defaults. Run commands from this directory. Includes terminal and native desktop interfaces.

## Build and send the desktop app (macOS)

1. Let the scraper finish creating `data/rosters.csv`.
2. From this project folder, run:

   ```sh
   make
   ```

3. Send **only `dist/NBA Trivia.zip`**. The CSV and Python runtime are bundled inside the app.
4. The recipient extracts the ZIP and double-clicks **NBA Trivia.app**. No separate CSV or Python installation is needed.

This build is for Apple Silicon Macs. Windows requires its own build; see **Packaging and sharing** below. Run `make` again whenever you want to ship updated code or roster data. Building does not alter the scraper or its source CSV.

For first-time build setup, run `python3 -m venv .venv` and then `.venv/bin/python -m pip install -e '.[build]'` before `make`.

## Terminal commands

```sh
# At startup, build all historical data if the CSV is missing, then play:
python3 -m nba_trivia

# Recommended first collection: one complete season:
python3 -m nba_trivia scrape --start 2024 --end 2024

# Seasons ending in 1976 through the latest completed season:
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

## Desktop interface (Mac)

Open `dist/NBA Trivia.app` or run `python3 run_desktop.py`. The Mac interface uses the Courtside cream/green palette and serif headings, with two large mode buttons, editable year fields, and an always-visible team list. Type to filter the team list, then click a row. There are no popup selection menus. Years mean season-ending years: 1976 = 1975–76. The page and tables scroll when needed.

The desktop app only reads roster files. Use **Choose CSV…** or **Reload data** to select a completed normalized CSV. It never starts or changes the scraper. Mobile remains a separate version and currently retains its own mode set.

### Mac game modes

- **Complete the roster:** identify every player with at least 250 minutes for the selected team-season. Blank names are ordered by PPG descending (unknown PPG last). Position, games, and inferred traded status are shown initially. Each hint reveals all heights, jersey numbers, or PPG in random order without repeats. Correct guesses reveal that player's data. Unlimited guesses; incorrect input stays entered. This replaces the separate top-ten mode.
- **Find the teams:** identify one or all teams for a player-season selected from the menu's range. Eligible players must have at least **250 combined season minutes** and **15 MPG**, calculated as combined team minutes divided by combined team games. Every played stint needs known minutes and games. All played teams remain valid answers, including short stints below the season eligibility threshold. Selecting a specific menu team restricts the player pool without removing their other answers.

Find-the-teams uses a button grid, with one button per historical NBA team in the loaded CSV for that exact season. It shows season-correct names and includes defunct or renamed teams where present in the data. It does not use today's team list. Click a team to submit; correct choices are marked and disabled, wrong choices are marked and disabled, and five wrong selections end the game. There is no text box in this mode. Unknown teams cannot be invented if the CSV's season coverage is incomplete.

For roster guesses, click **Submit guess** or press Return. Matching ignores case and Latin diacritics while preserving original names on screen. Blank and duplicate guesses do not count. Quit/reveal and failure show unguessed answers in red; **Return to menu** retains the selected settings. Victory requires all roster players or the one/all-team completion goal selected in the menu.

Missing statistics display as a dash. Season-wide rates in Find-the-teams are approximate, weighted from rounded CSV team rates. Traded status is inferred from other positive-games team records in the same CSV and season.

### Packaging and sharing

After the scraper finishes and `data/rosters.csv` exists, run:

```sh
make
```

This validates the CSV, takes a build-only snapshot, and embeds it inside the application. The original CSV and running scraper are never changed. The packaged app automatically uses its bundled CSV, so the recipient needs no separate dataset or Python installation. Rebuild to ship updated roster data.

On macOS, the build creates `dist/NBA Trivia.app` and **`dist/NBA Trivia.zip`**. Send only the ZIP. The recipient extracts it and double-clicks the app. The app is a Finder package containing its dependencies and CSV. It is not Developer ID signed or notarized, so macOS may show a security warning. The current build targets Apple Silicon Macs.

On Windows, run `.venv\Scripts\python build_app.py` using a Windows virtual environment with the build dependencies installed. It produces **`dist/NBA Trivia.exe`** using PyInstaller one-file mode with the CSV inside. Windows and macOS need separate builds.

To bundle a CSV stored elsewhere:

```sh
.venv/bin/python build_app.py --data /path/to/rosters.csv
```

If the CSV is missing or invalid, the build stops before replacing any previous application. Existing app builds are not retroactively updated. Initial setup remains `python3 -m venv .venv` followed by `.venv/bin/python -m pip install -e '.[build]'`.

Source launches use the project's `data/rosters.csv`. A packaged app without bundled data falls back to the application-data directory. The CSV picker can override the default for the current session. Packaged releases with bundled data run offline.

## iPhone / Safari version (separate from desktop)

Hosted game: [Courtside · NBA Trivia](https://nba-trivia-courtside-skeens.milkybison514.chatgpt.site) (initially owner-private).

`mobile/` contains a separate responsive web app with the same three typed-answer game modes. Desktop app builds and terminal scraping remain independent.

Open the hosted mobile Site in Safari, then use **Share → Add to Home Screen**. After loading online, the app shell is cached for offline use. Imported CSV data stays in that browser's local storage; Safari may remove cached data, so keep a copy of the roster file. Physical iPhone installation and offline behavior require device testing.

Until the scraper finishes, the mobile page offers an explicitly fictional sample game and a CSV picker. Load the completed normalized roster CSV from the iPhone Files app to play with real NBA records; the selected CSV is parsed locally and never uploaded.

To include the completed roster directly in the mobile website:

```sh
make mobile-data
```

This writes only `mobile/dist/rosters.json`; it does not change the source CSV, running scraper, or desktop app. Republish the mobile Site afterward to make updated data available at its hosted URL. The site is initially private to its owner; sharing with others requires changing its audience in Sites.

For a local computer preview:

```sh
make mobile-serve
```

Open `http://localhost:8080` on that computer. This localhost address is not a remotely accessible iPhone link. Home Screen/offline functionality on a phone requires an HTTPS deployment. You can host the static contents of `mobile/dist/` on another HTTPS static host if desired.

Mobile logic tests: `node --test mobile/tests/engine.test.mjs`.

### Input and revealed answers

Mac controls use large themed buttons, inline year fields, and an always-visible searchable team list. There are no dropdowns or modal setting pickers.

Guesses ignore case and diacritics: `Jokic` matches `Jokić`, `Asik` matches `Aşık`, and `Porzingis` matches `Porziņģis`. Special Latin letters are normalized, including `ø → o`, `ł → l`, `æ → ae`, and `ß → ss`. Original spellings remain on screen.

Quit/reveal and failure show unguessed answer rows in red; previously guessed answers retain their normal color. The latest Mac redesign and eligibility rules have not been applied to the separate mobile version.

### Mac player-name autocomplete

In **Complete the roster**, start typing a first or last name to open a scrollable suggestion list. Suggestions ignore case and accents and search all player names in the loaded CSV, rather than revealing only the selected roster's answers. Click a suggestion to fill in its correctly spelled name, then click **Submit guess** (or press Return in the text box). Selecting a suggestion does not submit a guess.

Keyboard: Down opens/focuses suggestions; arrow keys navigate; Return selects a highlighted suggestion; Escape dismisses the list. Team-button mode is unchanged. The separate iPhone version has not received this Mac-only feature.

### Optional roster metadata: age, All-Star status, college

New scraper output appends `age`, `is_all_star`, and `college`. Old CSVs remain readable: their missing fields default to unknown. The Mac roster source code adds these as randomized hint categories only when the chosen roster has data for them, and displays the fields on correctly guessed or revealed rows. A horizontal table scrollbar accommodates the extra columns. The existing packaged app must be rebuilt separately to include these source changes.

- `age`: the source's season-age value from the regular-season statistics tables. Basketball Reference defines it as age on January 31 of that season; it is not current age.
- `is_all_star`: `1` when the Awards column contains the exact `AS` marker, `0` when Awards is available without that marker, and blank when unavailable. It means selected for that season's All-Star roster, not necessarily that the player appeared in the game. Selection is reconciled across a traded player's team rows. A season without an All-Star selection is not a positive result.
- `college`: the roster's listed college text, preserving multiple schools. Blank means no listed college/unknown; it is not automatically interpreted as proof the player never attended college.

Sources: [Basketball Reference glossary](https://www.basketball-reference.com/about/glossary.html), [Sports Reference All-Star help](https://faq.sports-reference.com/portal/en/kb/articles/all-sta), and the team-season roster/statistics pages linked in each row.

To generate a **separate** enriched file later, keeping the current dataset in place:

```sh
python3 -m nba_trivia scrape --start 1976 --end 2026 --data data/rosters_enriched.csv
```

Existing cached pages are reused. This command has not been run as part of the metadata update; `data/rosters.csv` has not been replaced, and the app has not been rebuilt. Preview the enriched file using the source app's CSV picker before choosing to bundle it in a future release.
