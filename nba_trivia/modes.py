"""Typed-answer game sessions, independent of the desktop interface."""
import random
import unicodedata

MODE_NAMES = {"Complete the roster": "one-player",
              "Name a player's teams": "player-teams"}
HINTS = ("height_inches", "jersey_number", "ppg")


def normalized(text):
    text = unicodedata.normalize("NFKD", text.casefold())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.translate(str.maketrans({
        "ø": "o", "ł": "l", "đ": "d", "ð": "d", "þ": "th",
        "æ": "ae", "œ": "oe", "ı": "i", "ħ": "h", "ŋ": "n", "ŧ": "t",
        "’": "'", "‘": "'", "ʼ": "'", "‐": "-", "‑": "-", "–": "-",
    })).strip()


def make_session(rows, mode, team=None, goal="all", rng=None):
    rng = rng or random.Random()
    groups = {}
    for row in rows:
        groups.setdefault((row.team_id, row.season_end), []).append(row)
    if mode == "one-player":
        candidates = {}
        for key, roster in groups.items():
            if team is not None and key[0] != team:
                continue
            eligible = sorted(
                [r for r in roster if r.minutes_total is not None and r.minutes_total >= 250],
                key=lambda r: (r.ppg is None, -(r.ppg or 0), r.player_id))
            if eligible:
                candidates[key] = eligible
        if not candidates:
            raise ValueError("No roster players with at least 250 team minutes in this selection.")
        answers = candidates[rng.choice(sorted(candidates))]
    elif mode == "player-teams":
        players = {}
        for row in rows:
            players.setdefault((row.player_id, row.season_end), []).append(row)
        # A specific team limits which player-seasons are selected, not their answers.
        candidates = []
        for rs in players.values():
            played = [r for r in rs if r.games is not None and r.games > 0]
            if not played or any(r.games is None for r in rs):
                continue
            if any(r.minutes_total is None for r in played):
                continue
            games = sum(r.games for r in played)
            minutes = sum(r.minutes_total for r in played)
            if minutes >= 250 and minutes / games >= 15 and any(
                    team is None or r.team_id == team for r in played):
                candidates.append(played)
        if not candidates:
            raise ValueError("No player-season meets 250 total minutes and 15 minutes per game with known games/minutes for every stint.")
        answers = rng.choice(candidates)
    else:
        raise ValueError("Unknown game mode")
    return Session(rows, answers, mode, goal, rng)


class Session:
    def __init__(self, rows, answers, mode, goal, rng):
        self.rows, self.answers, self.mode, self.goal = rows, answers, mode, goal
        self.found = set()
        self.wrong = 0
        self.outcome = None
        self.hints = list(HINTS)
        rng.shuffle(self.hints)
        self.revealed_hints = []
        self.traded = {}
        for r in rows:
            if r.games is not None and r.games > 0:
                self.traded.setdefault((r.player_id, r.season_end), set()).add(r.team_id)

    @property
    def anchor(self):
        return self.answers[0]

    @property
    def prompt(self):
        a = self.anchor
        if self.mode == "player-teams":
            return f"Name {'one team' if self.goal == 'one' else 'all teams'} {a.player_name} played for in {a.season} ({a.season_end})."
        if self.mode == "one-player":
            return f"Name every player on {a.team_name} in {a.season} ({a.season_end}) who played at least 250 minutes for that team. Rows are ordered by PPG."
        raise ValueError("Unknown game mode")

    @property
    def team_options(self):
        """Historical teams present in the CSV for this exact NBA season."""
        options = {r.team_id: r.team_name for r in self.rows
                   if r.league == "NBA" and r.season_end == self.anchor.season_end}
        return sorted(options.items(), key=lambda item: (item[1], item[0]))

    def identity(self, row):
        return row.team_id if self.mode == "player-teams" else row.player_id

    def label(self, row):
        return row.team_name if self.mode == "player-teams" else row.player_name

    def guess(self, text):
        if self.outcome:
            return "This game has ended."
        value = normalized(text)
        if not value:
            return "Enter a name before submitting."
        matches = [r for r in self.answers if value in (
            {normalized(r.team_name), normalized(r.team_id)} if self.mode == "player-teams"
            else {normalized(r.player_name)})]
        if matches:
            new = [r for r in matches if self.identity(r) not in self.found]
            if not new:
                return "You already found that answer."
            self.found.update(self.identity(r) for r in new)
            needed = 1 if self.mode == "player-teams" and self.goal == "one" else len(self.answers)
            if len(self.found) >= needed:
                self.outcome = "victory"
            return "Correct!"
        if self.mode == "player-teams":
            self.wrong += 1
            if self.wrong >= 5:
                self.outcome = "failure"
            return f"{self.anchor.player_name} did not play for {text.strip()} in {self.anchor.season_end}. Incorrect guesses: {self.wrong}/5."
        # Distinguish a real roster member who does not meet this mode's eligibility.
        roster_member = any(normalized(r.player_name) == value and r.team_id == self.anchor.team_id
                            and r.season_end == self.anchor.season_end for r in self.rows)
        if roster_member:
            return (f"{text.strip()} was on {self.anchor.team_name} in {self.anchor.season_end}, but "
                    + "did not meet the 250-minute requirement.")
        return f"{text.strip()} was not on {self.anchor.team_name} in {self.anchor.season_end}."

    def hint(self):
        if self.outcome or self.mode != "one-player" or not self.hints:
            return None
        field = self.hints.pop()
        self.revealed_hints.append(field)
        return field

    def quit(self):
        if not self.outcome:
            self.outcome = "quit"

    def season_stats(self):
        """Weight rounded team rates by games; label them as approximations in UI."""
        games = sum(r.games for r in self.answers)
        stats = {}
        for field in ("ppg", "rpg", "apg", "spg", "bpg"):
            stats[field] = (round(sum(getattr(r, field) * r.games for r in self.answers) / games, 1)
                            if games and all(getattr(r, field) is not None for r in self.answers) else None)
        stats["games"] = games
        stats["minutes_total"] = (sum(r.minutes_total for r in self.answers)
                                  if all(r.minutes_total is not None for r in self.answers) else None)
        return stats
