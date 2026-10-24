import argparse
import sys
from datetime import date
from pathlib import Path

from .data import Catalog, read_csv
from .game import MODES, question
from .scraper import Client, SourceError, collect


def main():
    parser = argparse.ArgumentParser(description="NBA trivia and historical roster collection")
    parser.add_argument("command", nargs="?", choices=("play", "scrape", "query"), default="play")
    parser.add_argument("--data", type=Path, default=Path("data/rosters.csv"))
    parser.add_argument("--cache", type=Path, default=Path("data/cache"))
    parser.add_argument("--start", type=int, default=1976)
    today = date.today()
    parser.add_argument("--end", type=int, default=today.year if today.month >= 7 else today.year - 1)
    parser.add_argument("--refresh", action="store_true", help="Rebuild CSV using cached pages; remove specific cache files to refetch")
    parser.add_argument("--offline", action="store_true", help="Never collect data at startup")
    parser.add_argument("--season", type=int)
    parser.add_argument("--team", type=str.upper)
    parser.add_argument("--position")
    parser.add_argument("--min-minutes", type=float)
    parser.add_argument("--sort", default="player_name")
    parser.add_argument("--descending", action="store_true")
    parser.add_argument("--mode", choices=MODES, default="guess-player")
    parser.add_argument("--rounds", type=int, default=5)
    args = parser.parse_args()
    try:
        if args.rounds < 1:
            raise ValueError("Rounds must be positive")
        needs_collection = args.command == "scrape" or args.refresh or not args.data.exists()
        if needs_collection:
            if args.offline:
                raise ValueError("Offline mode requires an existing CSV and cannot refresh/scrape")
            print(f"Building seasons {args.start}–{args.end}; full history may take hours. Cached pages resume interrupted runs.")
            try:
                collect(Client(args.cache), args.start, args.end, args.data)
            except SourceError as error:
                if args.command == "scrape" or not args.data.exists():
                    raise
                print(f"Refresh failed: {error}\nUsing existing CSV.", file=sys.stderr)
        rows = read_csv(args.data)
        if args.command == "scrape":
            print(f"Saved {len(rows):,} rows to {args.data}")
            return
        rows = Catalog(rows).select(season=args.season, team=args.team, position=args.position,
                                    min_minutes=args.min_minutes, sort_by=args.sort, descending=args.descending)
        if args.command == "query":
            import csv
            from dataclasses import asdict
            from .data import COLUMNS
            writer = csv.DictWriter(sys.stdout, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(asdict(r) for r in rows)
            return
        score = 0
        for _ in range(args.rounds):
            q = question(rows, args.mode)
            print("\n" + q.prompt)
            for index, choice in enumerate(q.choices, 1):
                print(f"{index}. {choice}")
            while True:
                reply = input("Answer (number, or q to quit): ").strip()
                if reply.lower() == "q":
                    return
                if reply.isdigit() and 1 <= int(reply) <= len(q.choices):
                    break
                print("Choose one of the displayed numbers.")
            correct = q.choices[int(reply) - 1] == q.answer
            score += correct
            print("Correct!" if correct else f"Answer: {q.answer}")
        print(f"\nScore: {score}/{args.rounds}")
    except (SourceError, ValueError, OSError) as error:
        parser.exit(1, f"Error: {error}\n")
    except (EOFError, KeyboardInterrupt):
        print("\nStopped. Existing CSV and cached pages retained.")
