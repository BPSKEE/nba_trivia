"""Mode registry makes additional question generators easy to add."""
import random
from dataclasses import dataclass


@dataclass(frozen=True)
class Question:
    prompt: str
    choices: tuple[str, ...]
    answer: str


def question(rows, mode, rng=None):
    rng = rng or random.Random()
    if mode == "guess-player":
        eligible = [r for r in rows if r.games and r.ppg is not None]
        target = rng.choice(eligible) if eligible else None
        if target:
            prompt = (f"Who played for {target.team_name} in {target.season}, wore #{target.jersey_number or '?'}, "
                      f"and averaged {target.ppg} PPG / {target.rpg if target.rpg is not None else '?'} RPG / "
                      f"{target.apg if target.apg is not None else '?'} APG?")
            answer = target.player_name
            pool = {r.player_name for r in eligible}
    elif mode == "guess-team":
        target = rng.choice(rows) if rows else None
        if target:
            prompt = f"Which team roster included {target.player_name} in {target.season}?"
            answer = target.team_name
            # Exclude all valid teams for this player in this season from distractors.
            valid = {r.team_name for r in rows if r.player_id == target.player_id and r.season_end == target.season_end}
            pool = {r.team_name for r in rows} - valid | {answer}
    elif mode == "higher-stat":
        eligible = [r for r in rows if r.ppg is not None and r.games]
        if len({r.ppg for r in eligible}) < 2 or len({r.player_id for r in eligible}) < 2:
            raise ValueError("Higher-stat needs two distinct players with different PPG")
        a = rng.choice(eligible)
        candidates = [r for r in eligible if r.player_id != a.player_id and r.ppg != a.ppg]
        if not candidates:
            raise ValueError("No eligible comparison; broaden the filters")
        b = rng.choice(candidates)
        label = lambda r: f"{r.player_name} ({r.team_id}, {r.season})"
        options = [label(a), label(b)]
        rng.shuffle(options)
        return Question("Who averaged more points per game?", tuple(options), label(a if a.ppg > b.ppg else b))
    else:
        raise ValueError(f"Unknown mode: {mode}")
    if not target:
        raise ValueError("No eligible players for this mode and filter")
    alternatives = sorted(pool - {answer})
    if not alternatives:
        raise ValueError("Need more distinct players/teams for multiple choice")
    choices = rng.sample(alternatives, min(3, len(alternatives))) + [answer]
    rng.shuffle(choices)
    return Question(prompt, tuple(choices), answer)


MODES = ("guess-player", "guess-team", "higher-stat")
