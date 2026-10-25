"""Shared desktop file locations and season validation."""
import os
import sys
from datetime import date
from pathlib import Path

MIN_YEAR = 1976


def latest_season():
    today = date.today()
    return today.year if today.month >= 7 else today.year - 1


def default_data_dir():
    if not getattr(sys, "frozen", False):
        return Path(__file__).resolve().parent.parent / "data"
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/NBA Trivia"
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "NBA Trivia"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "nba-trivia"


def default_roster_path():
    # A packaged release always prefers the dataset shipped with that release.
    if getattr(sys, "frozen", False):
        bundled = Path(sys._MEIPASS) / "data" / "rosters.csv"
        if bundled.is_file():
            return bundled
    directory = default_data_dir()
    enriched = directory / "rosters_enriched.csv"
    return enriched if enriched.is_file() else directory / "rosters.csv"


def allstars_path():
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "data" / "allstars.csv"
    return Path(__file__).resolve().parent.parent / "data" / "allstars.csv"


def select_range(rows, start, end):
    if not MIN_YEAR <= start <= end <= latest_season():
        raise ValueError(f"Choose ending years from {MIN_YEAR} to {latest_season()}, with start ≤ finish.")
    selected = [r for r in rows if start <= r.season_end <= end and r.league == "NBA"]
    missing = sorted(set(range(start, end + 1)) - {r.season_end for r in selected})
    if missing:
        raise ValueError("CSV has no NBA records for: " + ", ".join(map(str, missing)) + ". Choose a covered range or load another CSV.")
    return selected

