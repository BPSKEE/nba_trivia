# NBA trivia framework

## Play in a browser or on iPhone

[**Open NBA Trivia**](https://bpskee.github.io/nba_trivia/)

This is the GitHub Pages address for this repository. **The link becomes live after you push `docs/` and enable Pages using the steps below.** The website runs independently of ChatGPT, with the roster and All-Star data included. Visitors need only the link.

### Enable the website once

1. Push this project, including the **`docs/` folder**, to your `BPSKEE/nba_trivia` GitHub repository. The generated website is already in that folder; GitHub does not need to run Python or build the app.
2. On GitHub, open the repository → **Settings → Pages**.
3. Under **Build and deployment**, select **Deploy from a branch**.
4. Select **main**, select **/docs**, and click **Save**. If your default branch has another name, select that branch instead.
5. Wait for GitHub to finish publishing, then click the address shown on the Pages settings screen. Share that address with anyone.

If the repository name or owner changes, use the address GitHub shows and update the link above. See [GitHub's Pages setup instructions](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site).

### Custom domain: courtside.io

The repository includes `docs/CNAME` with `courtside.io`, and `make website` preserves this setting. Push that file, then keep **Settings → Pages → Custom domain** set to `courtside.io`.

At Namecheap, open **Domain List → Manage → Advanced DNS → Host Records**. Configure:

| Type | Host | Value |
| --- | --- | --- |
| A Record | @ | 185.199.108.153 |
| A Record | @ | 185.199.109.153 |
| A Record | @ | 185.199.110.153 |
| A Record | @ | 185.199.111.153 |
| CNAME Record | www | bpskee.github.io |

Use Automatic TTL. Replace the existing `www` parking CNAME and any root (`@`) parking/URL redirect or conflicting A/AAAA records. Keep email (MX/TXT) records. The CNAME target has no `https://` and no repository path.

DNS may take up to 24 hours to propagate. Once GitHub's DNS check succeeds and the certificate is ready, enable **Enforce HTTPS**. The final game address is https://courtside.io/. Adding the repository file does not change DNS at Namecheap; you must save those records there.

[GitHub custom-domain instructions](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/managing-a-custom-domain-for-your-github-pages-site).

### Update or preview the website

After changing website code or the enriched data, run:

```sh
make website
```

Then commit and push the updated `docs/` folder. Pages republishes automatically. The build reads `data/rosters_enriched.csv` and `data/allstars.csv`; it does not replace either CSV or rebuild the Mac app. It also creates `dist/NBA Trivia Website.zip`, containing a `docs/` folder you can upload through GitHub's website if you prefer.

For a preview on your own computer:

```sh
make website-serve
```

Then [open the local preview](http://localhost:8080). Keep that terminal running while playing locally. `localhost` means the device opening the link; it is not a public hosting address. Use the GitHub Pages link to play on iPhone or share with others without leaving your computer running.

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

- **Complete the roster:** identify every player with at least 250 minutes for the selected team-season. Blank names are ordered by PPG descending (unknown PPG last). Position, games, and inferred traded status are shown initially. One **Reveal all hints** button reveals every player’s jersey number, height, PPG, college, and age together; it then disables. Names remain hidden until guessed. Correct guesses reveal that player's data. Unlimited guesses; incorrect input stays entered. This replaces the separate top-ten mode.
- **Find the teams:** identify one or all teams for a player-season selected from the menu's range. Eligible players must have at least **250 combined season minutes** and **15 MPG**, calculated as combined team minutes divided by combined team games. Every played stint needs known minutes and games. All played teams remain valid answers, including short stints below the season eligibility threshold. Selecting a specific menu team restricts the player pool without removing their other answers.

Find-the-teams uses a button grid, with one button per historical NBA team in the loaded CSV for that exact season. It shows season-correct names and includes defunct or renamed teams where present in the data. It does not use today's team list. Click a team to submit; correct choices are marked and disabled, wrong choices are marked and disabled, and five wrong selections end the game. There is no text box in this mode. Unknown teams cannot be invented if the CSV's season coverage is incomplete.

For roster guesses, click **Submit guess** or press Return. Matching ignores case and Latin diacritics while preserving original names on screen. Blank and duplicate guesses do not count. Quit/reveal and failure show unguessed answers in red; **Return to menu** retains the selected settings. Victory requires all roster players or the one/all-team completion goal selected in the menu.

Missing statistics display as a dash. Season-wide rates in Find-the-teams are approximate, weighted from rounded CSV team rates. Traded status is inferred from other positive-games team records in the same CSV and season.

### Packaging and sharing

After the scraper finishes and `data/rosters.csv` exists, run:

```sh
make
```

This validates the CSV, takes a build-only snapshot, and embeds it inside the application. Builds prefer `data/rosters_enriched.csv` when present, otherwise `data/rosters.csv`. The original CSV and running scraper are never changed. The packaged app automatically uses its bundled CSV, so the recipient needs no separate dataset or Python installation. Rebuild to ship updated roster data.

On macOS, the build creates `dist/NBA Trivia.app` and **`dist/NBA Trivia.zip`**. Send only the ZIP. The recipient extracts it and double-clicks the app. The app is a Finder package containing its dependencies and CSV. It is not Developer ID signed or notarized, so macOS may show a security warning. The current build targets Apple Silicon Macs.

On Windows, run `.venv\Scripts\python build_app.py` using a Windows virtual environment with the build dependencies installed. It produces **`dist/NBA Trivia.exe`** using PyInstaller one-file mode with the CSV inside. Windows and macOS need separate builds.

To bundle a CSV stored elsewhere:

```sh
.venv/bin/python build_app.py --data /path/to/rosters.csv
```

If the CSV is missing or invalid, the build stops before replacing any previous application. Existing app builds are not retroactively updated. Initial setup remains `python3 -m venv .venv` followed by `.venv/bin/python -m pip install -e '.[build]'`.

Source launches use the project's `data/rosters.csv`. A packaged app without bundled data falls back to the application-data directory. The CSV picker can override the default for the current session. Packaged releases with bundled data run offline.

## iPhone / Safari version (separate from desktop)

Use the **Open NBA Trivia** link at the top after enabling GitHub Pages. All four modes are included: complete the roster, name the player's teams, guess the college, and East/West All-Star rosters. Player and college autocomplete, hints, and red revealed answers are included.

On iPhone, open the link in Safari. You can use **Share → Add to Home Screen** to add an icon. The site caches its files and included data after a successful online load; Safari may remove cached files. Physical iPhone installation and offline behavior still require device testing.

The deployable website is entirely in `docs/`, including its data. There is no ChatGPT hosting, account requirement, backend server, or separate CSV for visitors. Source files are in `mobile/dist/`. Run `make website` to refresh `docs/` after source changes.

Web logic tests: `node --test mobile/tests/engine.test.mjs`.

### Input and revealed answers

Mac controls use large themed buttons, inline year fields, and an always-visible searchable team list. There are no dropdowns or modal setting pickers.

Guesses ignore case and diacritics: `Jokic` matches `Jokić`, `Asik` matches `Aşık`, and `Porzingis` matches `Porziņģis`. Special Latin letters are normalized, including `ø → o`, `ł → l`, `æ → ae`, and `ß → ss`. Original spellings remain on screen.

Quit/reveal and failure show unguessed answer rows in red; previously guessed answers retain their normal color.

### Mac player-name autocomplete

In **Complete the roster**, start typing a first or last name to open a scrollable suggestion list. Suggestions ignore case and accents and search all player names in the loaded CSV, rather than revealing only the selected roster's answers. Click a suggestion to fill in its correctly spelled name, then click **Submit guess** (or press Return in the text box). Selecting a suggestion does not submit a guess.

Keyboard: Down opens/focuses suggestions; arrow keys navigate; Return selects a highlighted suggestion; Escape dismisses the list. Team-button mode is unchanged. The website also supports player and college autocomplete.

### Roster metadata and All-Star markers

The enriched dataset adds `age`, `is_all_star`, and `college`. Mac roster mode has one **Reveal all hints** button: one click reveals jersey numbers, heights, PPG, colleges, and ages for all rows. Unknown values show a dash. Correct guesses still reveal the matching player's fields. Names stay hidden until guessed or the game ends.

A small gold star image at the left of a row and a light-gold row background indicate All-Star selection in that season. This marker is visible from the start; a legend below the game explains it. Quit/failure still show unguessed names in red, including on gold All-Star rows.

- `age`: Basketball Reference's season-age value (age on January 31), not current age.
- `is_all_star`: `1` for the exact `AS` Awards marker, `0` when the Awards field exists without `AS`, and blank when unknown. Selection is reconciled across traded players' team rows. This indicates selection, not necessarily game participation.
- `college`: source roster text, preserving multiple schools. Blank means no listed college/unknown.

Sources: [Basketball Reference glossary](https://www.basketball-reference.com/about/glossary.html) and [Sports Reference All-Star help](https://faq.sports-reference.com/portal/en/kb/articles/all-sta).

`data/rosters.csv` remains the original protected dataset. To reparse the existing cached pages into a **separate** enriched dataset without network requests:

```sh
.venv/bin/python enrich_rosters.py
```

This writes `data/rosters_enriched.csv` and refuses to overwrite the original `rosters.csv`. Missing cached pages cause it to stop instead of requesting the network. Both source launches and `make` prefer the enriched CSV when available. The app still bundles it under the internal name `rosters.csv` so recipients do not need a separate file. To explicitly build with another dataset, use `.venv/bin/python build_app.py --data /path/to/rosters.csv`.

When cached pages are missing, the existing network scraper can produce a separate enriched file with `python3 -m nba_trivia scrape --start 1976 --end 2026 --data data/rosters_enriched.csv`.

### Guess the college (Mac)

Select **Guess the college**, choose an inclusive range of season-ending years, and optionally select a team. The game picks a player who actually played in a selected season and has a listed college in the enriched CSV. Players without recorded colleges are excluded; this mode has fixed minimums of **25 career MPG and 2,000 career minutes**, with no menu toggle. Career MPG is total regular-season minutes divided by total regular-season games across all loaded seasons and team stints—not an average of season MPG, and not limited to the menu's year range or team. The chosen years only control which players were active. Careers with missing minutes/games are excluded. Players present in the dataset's first covered season are conservatively excluded because earlier career history cannot be verified; with the current dataset this affects players already present in 1975–76, including rookies from that season. Active players use career-to-date totals through the dataset's final season.

Type a college name to open autocomplete suggestions, click a school to fill it, then submit. Suggestions search all college names in the dataset, so they do not reveal only valid answers. Matching ignores case and accents. For players with multiple listed colleges, any one of their schools is accepted. Guesses are unlimited. A correct guess shows victory; **Quit & reveal answers** shows listed colleges in red. Both provide **Return to menu**. This mode is Mac-only for now.

### Mac click handling

Buttons explicitly handle mouse press/release and keyboard activation, firing once on release inside the button. Dragging outside cancels; disabled controls ignore clicks. Return on a focused button does not also trigger the game's root-level Submit binding.

Selecting a game mode or completion goal updates existing controls rather than destroying/rebuilding the menu. Autocomplete reserves a fixed-height suggestion area, so focus changes cannot collapse the list and move Hint, Quit, or Submit during a click. These behaviors have regression tests; physical Mac input still requires device verification.

### East / West All-Stars (Mac)

Select **East / West All-Stars**, choose an inclusive year range, and start. Set both year fields to the same year for a specific game. The mode picks a supported year in that range; regular-season team selection and the other modes' minutes requirements do not apply.

Two tables appear side-by-side, East on the left and West on the right. Type a player's name with the shared autocomplete, then submit. Correct guesses reveal that player's row in the correct conference. Both rosters must be completed to win. Guesses are unlimited; duplicate answers do not count. Quit reveals remaining names in red and provides Return to menu.

The separate `data/allstars.csv` uses actual conference rosters from [Basketball Reference's All-Star game pages](https://www.basketball-reference.com/allstar/). It includes game-roster players plus selected players identified in injury/withdrawal notes, so replacement players and the selections they replaced can both be answers. It does not infer conferences from end-of-season NBA rosters.

Supported East/West game years are **1976–2017 except 1999, plus 2024**. Years with other game formats or no game are excluded. A range containing no supported year produces a message instead of inventing East/West teams. The [All-Star history index](https://www.basketball-reference.com/allstar/) records the game formats.

To regenerate this dataset independently:

```sh
.venv/bin/python collect_allstars.py
make
```

Collection uses the same polite request interval and page cache as the main scraper, writes the All-Star file atomically after success, and leaves both regular-season CSVs untouched. `make` includes `allstars.csv` in the app when present. No network access is needed while playing.

## Current Mac frontend: Qt

The packaged app and `run_desktop.py` now launch the Qt frontend (`nba_trivia/qt_gui.py`). Standard Qt buttons, radio controls, searchable team selection, and popup autocomplete replace the Tk controls and custom mouse handlers. Menu widgets persist when selections change, and autocomplete does not resize the page. All four modes, career eligibility rules, one-click roster hints, All-Star gold markers, and red answer reveals are retained. The legacy Tk module is kept for compatibility tests but is not the packaged frontend.

East/West All-Star tables now show **Player / NBA team(s) / Age / College**. Metadata is joined by player ID and exact season from the enriched CSV, and is visible while names are hidden. Traded players list every recorded team for that season. Long text wraps, columns fit each table's width, and scrolling is vertical only. Unknown metadata is a dash.

Install the updated runtime/build dependencies before building: `.venv/bin/python -m pip install -e '.[build]'`, then `make`. Qt is bundled in the app; recipients do not install it. The current Qt wheel requires macOS 14 or newer; this build targets Apple Silicon.

UI tests exercise actual Qt widgets using Qt Test's offscreen mouse/keyboard events: `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -v`. This verifies event handling and layout without controlling the user's desktop; it does not replace physical-device testing.
