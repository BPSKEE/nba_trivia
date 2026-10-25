"""Polite, cached Basketball Reference collection; no block bypasses."""
import hashlib
import re
import os
import ssl
import time
from dataclasses import replace
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

from .data import PlayerSeason, write_csv

BASE = "https://www.basketball-reference.com"
USER_AGENT = "NBATriviaData/0.1"


class SourceError(RuntimeError):
    pass


class Tables(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = {}
        self.table = None
        self.row = None
        self.cell = None

    def handle_comment(self, data):
        if "<table" in data:
            nested = Tables()
            nested.feed(data)
            self.tables.update(nested.tables)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "table":
            self.table = attrs.get("id", "")
            self.tables.setdefault(self.table, [])
        elif tag == "tr" and self.table is not None:
            self.row = {}
        elif tag in ("td", "th") and self.row is not None:
            self.cell = {"text": "", "href": "", **attrs}
        elif tag == "a" and self.cell is not None:
            self.cell["href"] = attrs.get("href", "")

    def handle_data(self, data):
        if self.cell is not None:
            self.cell["text"] += data

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None:
            self.cell["text"] = self.cell["text"].strip()
            self.row[self.cell.get("data-stat", "")] = self.cell
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.tables[self.table].append(self.row)
            self.row = None
        elif tag == "table":
            self.table = None


def tables(html):
    parser = Tables()
    parser.feed(html)
    return parser.tables


def cell(row, *names):
    for name in names:
        if name in row:
            return row[name].get("text", "")
    return ""


def number(value, kind=float):
    return kind(value.replace(",", "")) if value and value != "—" else None


def player_id(row):
    for name in ("player", "name_display"):
        value = row.get(name, {})
        match = re.search(r"/players/[a-z]/([a-z0-9]+)\.html", value.get("href", ""))
        if match:
            return match.group(1)
    return None


def parse_team(html, year, team, name, league="NBA"):
    parsed = tables(html)
    totals_rows = parsed.get("totals") or parsed.get("totals_stats")
    if not parsed.get("roster") or not totals_rows:
        raise SourceError(f"Missing roster/totals tables for {team} {year}; source format may have changed")
    totals = {player_id(r): r for r in totals_rows if player_id(r)}
    details = {}
    for table_name in ("totals", "totals_stats", "per_game", "per_game_stats"):
        for record in parsed.get(table_name, []):
            pid = player_id(record)
            if pid:
                details.setdefault(pid, []).append(record)
    result = []
    for roster in parsed["roster"]:
        pid = player_id(roster)
        if not pid:
            continue
        stats = totals.get(pid, {})
        records = details.get(pid, [])
        age = next((number(cell(record, "age"), int) for record in records
                    if cell(record, "age")), None)
        awards = [cell(record, "awards") for record in records if "awards" in record]
        is_all_star = int(any("AS" in re.split(r"[\s,]+", value) for value in awards)) if awards else None
        games = number(cell(stats, "g", "games"), int)
        height = cell(roster, "height")
        match = re.fullmatch(r"(\d+)-(\d+)", height)
        rates = {}
        for dest, source in (("ppg", "pts"), ("rpg", "trb"), ("apg", "ast"), ("spg", "stl"), ("bpg", "blk")):
            total = number(cell(stats, source))
            rates[dest] = round(total / games, 1) if total is not None and games else None
        result.append(PlayerSeason(
            year, f"{year - 1}-{str(year)[-2:]}", league, team, name, pid,
            cell(roster, "player", "name_display"), cell(roster, "pos"),
            cell(roster, "number"), int(match[1]) * 12 + int(match[2]) if match else None,
            number(cell(roster, "weight"), int), games, number(cell(stats, "mp")),
            source_url=f"{BASE}/teams/{team}/{year}.html", age=age,
            is_all_star=is_all_star, college=cell(roster, "college"), **rates))
    if not result:
        raise SourceError(f"No roster players parsed for {team} {year}")
    return result


def parse_teams(html, year):
    found = {}
    for rows in tables(html).values():
        for row in rows:
            for item in row.values():
                match = re.fullmatch(rf"/teams/([A-Z0-9]{{3}})/{year}\.html", item.get("href", ""))
                if match:
                    found[match[1]] = item["text"].rstrip("*")
    if not found:
        raise SourceError(f"No teams found for {year}; source format may have changed")
    return sorted(found.items())


def tls_context():
    """Use platform roots plus certifi when no explicit CA override is set."""
    context = ssl.create_default_context()
    if not (os.environ.get("SSL_CERT_FILE") or os.environ.get("SSL_CERT_DIR")):
        try:
            import certifi
        except ImportError:
            pass
        else:
            context.load_verify_locations(cafile=certifi.where())
    return context


class Client:
    def __init__(self, cache, delay=4.0):
        self.cache = Path(cache)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.delay = max(4.0, delay)
        self.last_request = 0.0
        self.robots = None
        self.ssl_context = tls_context()

    def _request(self, url):
        time.sleep(max(0, self.delay - (time.monotonic() - self.last_request)))
        self.last_request = time.monotonic()
        try:
            with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=45, context=self.ssl_context) as response:
                if urlparse(response.url).netloc != urlparse(BASE).netloc:
                    raise SourceError("Unexpected redirect from source")
                return response.read().decode("utf-8")
        except (HTTPError, URLError, TimeoutError) as error:
            raise SourceError(f"Source unavailable at {url}: {error}. Collection stopped; cached pages retained.") from error

    def get(self, path):
        url = urljoin(BASE, path)
        if urlparse(url).netloc != urlparse(BASE).netloc:
            raise SourceError("Only Basketball Reference URLs are supported")
        cached = self.cache / (hashlib.sha256(url.encode()).hexdigest() + ".html")
        if cached.exists():
            return cached.read_text(encoding="utf-8")
        if self.robots is None:
            self.robots = RobotFileParser()
            self.robots.parse(self._request(BASE + "/robots.txt").splitlines())
        crawl_delay = self.robots.crawl_delay(USER_AGENT)
        if crawl_delay is not None:
            self.delay = max(self.delay, crawl_delay)
        if not self.robots.can_fetch(USER_AGENT, url):
            raise SourceError(f"robots.txt disallows {url}; collection stopped")
        html = self._request(url)
        if "<table" not in html.lower() or any(s in html.lower() for s in ("just a moment...", "verify you are human", "access denied")):
            raise SourceError(f"Unexpected or blocked response at {url}; not cached")
        temporary = cached.with_suffix(".tmp")
        temporary.write_text(html, encoding="utf-8")
        temporary.replace(cached)
        return html


def collect(client, start, end, output, progress=print):
    if not 1947 <= start <= end:
        raise ValueError("Use end-of-season years with 1947 <= start <= end")
    rows = []
    for year in range(start, end + 1):
        league = "BAA" if year <= 1949 else "NBA"
        teams = parse_teams(client.get(f"/leagues/{league}_{year}.html"), year)
        for team, name in teams:
            progress(f"Collecting {year} {team} ({name})", flush=True)
            rows.extend(parse_team(client.get(f"/teams/{team}/{year}.html"), year, team, name, league))
    # All-Star selection belongs to the player-season, even across a trade.
    all_stars = {(r.player_id, r.season_end, r.league) for r in rows if r.is_all_star == 1}
    rows = [replace(r, is_all_star=1) if (r.player_id, r.season_end, r.league) in all_stars else r
            for r in rows]
    write_csv(output, rows)
    return rows
