"""Stable CSV contract: one regular-season player/team/season row."""
import csv
import os
import tempfile
from dataclasses import asdict, dataclass, fields
from pathlib import Path


@dataclass(frozen=True)
class PlayerSeason:
    season_end: int
    season: str
    league: str
    team_id: str
    team_name: str
    player_id: str
    player_name: str
    position: str = ""
    jersey_number: str = ""
    height_inches: int | None = None
    weight_lbs: int | None = None
    games: int | None = None
    minutes_total: float | None = None
    ppg: float | None = None
    rpg: float | None = None
    apg: float | None = None
    spg: float | None = None
    bpg: float | None = None
    source_url: str = ""

    @property
    def key(self):
        return self.season_end, self.league, self.team_id, self.player_id


COLUMNS = [f.name for f in fields(PlayerSeason)]
INTS = {"season_end", "height_inches", "weight_lbs", "games"}
FLOATS = {"minutes_total", "ppg", "rpg", "apg", "spg", "bpg"}


def write_csv(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    records = {}
    for row in rows:
        if row.key in records:
            raise ValueError(f"Duplicate player/team/season: {row.key}")
        records[row.key] = row
    if not records:
        raise ValueError("Refusing to replace data with an empty dataset")
    fd, temporary = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=COLUMNS)
            writer.writeheader()
            for key in sorted(records):
                writer.writerow(asdict(records[key]))
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != COLUMNS:
            raise ValueError("Unsupported CSV schema; rebuild the data file")
        rows = []
        seen = set()
        for record in reader:
            for name in INTS | FLOATS:
                record[name] = (int if name in INTS else float)(record[name]) if record[name] else None
            row = PlayerSeason(**record)
            if row.key in seen:
                raise ValueError(f"Duplicate row: {row.key}")
            seen.add(row.key)
            rows.append(row)
        if not rows:
            raise ValueError("CSV contains no players")
        return rows


class Catalog:
    def __init__(self, rows):
        self.rows = list(rows)
        self.by_team_season = {}
        self.by_player = {}
        for row in self.rows:
            self.by_team_season.setdefault((row.team_id, row.season_end), []).append(row)
            self.by_player.setdefault(row.player_id, []).append(row)

    def select(self, *, season=None, team=None, position=None, min_minutes=None,
               sort_by="player_name", descending=False):
        if sort_by not in COLUMNS:
            raise ValueError(f"Unknown sort field: {sort_by}")
        rows = [r for r in self.rows if
                (season is None or r.season_end == season) and
                (team is None or r.team_id == team) and
                (position is None or position in r.position.split("-")) and
                (min_minutes is None or (r.minutes_total is not None and r.minutes_total >= min_minutes))]
        present = [r for r in rows if getattr(r, sort_by) is not None]
        missing = [r for r in rows if getattr(r, sort_by) is None]
        return sorted(present, key=lambda r: getattr(r, sort_by), reverse=descending) + missing
