"""Native desktop menu and trivia interface. Network work stays off the UI thread."""
import os
import queue
import sys
import threading
from datetime import date
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, ttk

from .data import read_csv
from .game import question
from .scraper import Client, collect

MIN_YEAR = 1976
MODE_NAMES = {"Guess the player": "guess-player", "Guess the team": "guess-team",
              "Who scored more?": "higher-stat"}


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


def select_range(rows, start, end):
    if not MIN_YEAR <= start <= end <= latest_season():
        raise ValueError(f"Choose ending years from {MIN_YEAR} to {latest_season()}, with start ≤ finish.")
    selected = [r for r in rows if start <= r.season_end <= end and r.league == "NBA"]
    missing = sorted(set(range(start, end + 1)) - {r.season_end for r in selected})
    if missing:
        raise ValueError("CSV has no NBA records for: " + ", ".join(map(str, missing)) + ". Choose a covered range or load another CSV.")
    return selected


class TriviaApp:
    def __init__(self, root):
        self.root = root
        root.title("NBA Trivia")
        root.geometry("780x620")
        root.minsize(640, 540)
        self.events = queue.Queue()
        self.busy = False
        self.closed = False
        self.data_dir = default_data_dir()
        self.data_path = self.data_dir / "rosters.csv"
        self.mode = tk.StringVar(value=next(iter(MODE_NAMES)))
        self.start = tk.StringVar(value=str(MIN_YEAR))
        self.end = tk.StringVar(value=str(latest_season()))
        self.rounds = tk.StringVar(value="10")
        self.status = tk.StringVar(value="Choose your game settings.")
        self.frame = ttk.Frame(root, padding=30)
        self.frame.pack(fill="both", expand=True)
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.menu()
        root.after(100, self.poll)

    def clear(self):
        for child in self.frame.winfo_children():
            child.destroy()

    def menu(self):
        self.clear()
        ttk.Label(self.frame, text="NBA Trivia", font=("Helvetica", 28, "bold")).pack(anchor="w")
        ttk.Label(self.frame, text="Pick an era. Test your basketball knowledge.").pack(anchor="w", pady=(5, 20))
        for title, variable, values in (
            ("Game mode", self.mode, list(MODE_NAMES)),
            ("First season ending year", self.start, list(range(MIN_YEAR, latest_season() + 1))),
            ("Last season ending year", self.end, list(range(MIN_YEAR, latest_season() + 1))),
            ("Questions", self.rounds, [5, 10, 20])):
            ttk.Label(self.frame, text=title).pack(anchor="w", pady=(6, 3))
            ttk.Combobox(self.frame, textvariable=variable, values=values, state="readonly").pack(fill="x")
        ttk.Label(self.frame, text="Years refer to when the season ends: 1976 = 1975–76.").pack(anchor="w", pady=10)
        self.submit = ttk.Button(self.frame, text="Start game", command=self.start_game)
        self.submit.pack(fill="x", pady=8)
        self.file_button = ttk.Button(self.frame, text="Choose roster CSV…", command=self.choose_file)
        self.file_button.pack(anchor="w")
        ttk.Label(self.frame, textvariable=self.status, wraplength=660).pack(anchor="w", pady=12)

    def choose_file(self):
        path = filedialog.askopenfilename(title="Choose normalized roster CSV", filetypes=[("CSV files", "*.csv")])
        if path:
            self.data_path = Path(path)
            self.status.set(f"Selected {self.data_path.name}")

    def start_game(self):
        if self.busy:
            return
        try:
            start, end, rounds = int(self.start.get()), int(self.end.get()), int(self.rounds.get())
            if not MIN_YEAR <= start <= end <= latest_season() or rounds < 1:
                raise ValueError("Choose a valid season range and question count.")
        except ValueError as error:
            self.status.set(str(error))
            return
        mode = MODE_NAMES[self.mode.get()]
        self.busy = True
        self.submit.config(state="disabled")
        self.file_button.config(state="disabled")
        self.status.set("Loading roster data… First-time collection can take hours; progress will appear here.")
        path = self.data_path

        def work():
            try:
                if not path.exists():
                    def progress(message, **kwargs):
                        self.events.put(("progress", message))
                    collect(Client(self.data_dir / "cache"), MIN_YEAR, latest_season(), path, progress)
                rows = select_range(read_csv(path), start, end)
                first = question(rows, mode)
                self.events.put(("ready", (rows, mode, rounds, first)))
            except Exception as error:
                self.events.put(("error", str(error)))
        threading.Thread(target=work, daemon=True).start()

    def poll(self):
        if self.closed:
            return
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "progress":
                    self.status.set(payload)
                elif kind == "error":
                    self.busy = False
                    self.submit.config(state="normal")
                    self.file_button.config(state="normal")
                    self.status.set(payload)
                elif kind == "ready":
                    self.busy = False
                    self.rows, self.game_mode, self.total, first = payload
                    self.score = 0
                    self.number = 0
                    self.show_question(first)
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def show_question(self, current=None):
        try:
            current = current or question(self.rows, self.game_mode)
        except ValueError as error:
            self.status.set(str(error))
            self.menu()
            return
        self.current = current
        self.number += 1
        self.clear()
        ttk.Label(self.frame, text=f"Question {self.number} / {self.total}  •  Score {self.score}", font=("Helvetica", 16)).pack(anchor="w")
        ttk.Label(self.frame, text=current.prompt, wraplength=660, font=("Helvetica", 19)).pack(fill="x", pady=30)
        self.answers = []
        for choice in current.choices:
            button = ttk.Button(self.frame, text=choice, command=lambda value=choice: self.answer(value))
            button.pack(fill="x", pady=6, ipady=8)
            self.answers.append(button)
        self.feedback = ttk.Label(self.frame, text="", wraplength=660)
        self.feedback.pack(anchor="w", pady=15)
        self.next_button = ttk.Button(self.frame, text="Next question" if self.number < self.total else "See results", command=self.advance, state="disabled")
        self.next_button.pack(fill="x")
        ttk.Button(self.frame, text="Back to menu", command=self.menu).pack(anchor="w", pady=15)

    def answer(self, choice):
        for button in self.answers:
            button.config(state="disabled")
        correct = choice == self.current.answer
        self.score += int(correct)
        self.feedback.config(text="Correct!" if correct else f"Correct answer: {self.current.answer}")
        self.next_button.config(state="normal")

    def advance(self):
        if self.number < self.total:
            self.show_question()
            return
        self.clear()
        ttk.Label(self.frame, text="Game complete", font=("Helvetica", 28, "bold")).pack(pady=35)
        ttk.Label(self.frame, text=f"You scored {self.score} out of {self.total}", font=("Helvetica", 20)).pack(pady=20)
        ttk.Button(self.frame, text="Back to menu", command=self.menu).pack(fill="x", pady=20)

    def close(self):
        self.closed = True
        self.root.destroy()


def main():
    root = tk.Tk()
    TriviaApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
