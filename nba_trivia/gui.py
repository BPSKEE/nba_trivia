"""Native desktop menu and trivia interface. Network work stays off the UI thread."""
import os
import queue
import sys
import threading
from datetime import date
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, ttk

from .autocomplete import NameIndex
from .data import read_csv
from .modes import MODE_NAMES, make_session

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
    return default_data_dir() / "rosters.csv"


def select_range(rows, start, end):
    if not MIN_YEAR <= start <= end <= latest_season():
        raise ValueError(f"Choose ending years from {MIN_YEAR} to {latest_season()}, with start ≤ finish.")
    selected = [r for r in rows if start <= r.season_end <= end and r.league == "NBA"]
    missing = sorted(set(range(start, end + 1)) - {r.season_end for r in selected})
    if missing:
        raise ValueError("CSV has no NBA records for: " + ", ".join(map(str, missing)) + ". Choose a covered range or load another CSV.")
    return selected


BG = "#f5f2e9"
PAPER = "#fffdf7"
INK = "#18312b"
GREEN = "#173e32"
RUST = "#9b4c2e"
RED = "#b42318"


class CourtButton(ttk.Button):
    """Clam-themed buttons keep their full hit area and colors on macOS."""
    def __init__(self, parent, text, command, primary=False, **kwargs):
        self.theme = ttk.Style(parent)
        self.theme_name = f"Court{id(self)}.TButton"
        self.colors = {"background": GREEN if primary else "#e3e8db",
                       "foreground": PAPER if primary else INK,
                       "disabledforeground": "#6b776b"}
        self.padding = [16, 13]
        self.theme.configure(self.theme_name, font=("Helvetica", 13, "bold"),
                             borderwidth=0, relief="flat", anchor="center", padding=tuple(self.padding))
        super().__init__(parent, text=text, command=command, style=self.theme_name, cursor="hand2")
        self.configure(**kwargs)

    def configure(self, cnf=None, **kwargs):
        if cnf is not None:
            return super().configure(cnf, **kwargs)
        for name in self.colors:
            if name in kwargs:
                self.colors[name] = kwargs.pop(name)
        style_options = {key: kwargs.pop(key) for key in ("font", "wraplength") if key in kwargs}
        if "padx" in kwargs:
            self.padding[0] = kwargs.pop("padx")
        if "pady" in kwargs:
            self.padding[1] = kwargs.pop("pady")
        self.theme.configure(self.theme_name, background=self.colors["background"],
                             foreground=self.colors["foreground"], padding=tuple(self.padding), **style_options)
        self.theme.map(self.theme_name,
                       background=[("pressed", "#b7c8ac"), ("active", "#c9d5bc")],
                       foreground=[("disabled", self.colors["disabledforeground"]),
                                   ("pressed", INK), ("active", INK)])
        return super().configure(**kwargs)

    config = configure


class AutocompleteEntry(ttk.Frame):
    """Inline dropdown keeps focus and clicks inside the game window."""
    def __init__(self, parent, variable, names):
        super().__init__(parent)
        self.variable, self.names = variable, names
        self.accepting = False
        self.entry = ttk.Entry(self, textvariable=variable, font=("Helvetica", 16))
        self.entry.pack(fill="x")
        self.dropdown = ttk.Frame(self)
        self.listbox = tk.Listbox(self.dropdown, height=6, font=("Helvetica", 14),
                                 background=PAPER, foreground=INK, selectbackground=GREEN,
                                 selectforeground=PAPER, activestyle="none", exportselection=False,
                                 borderwidth=0, highlightthickness=1, highlightbackground="#b8c5af")
        scroll = ttk.Scrollbar(self.dropdown, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.listbox.pack(side="left", fill="both", expand=True)
        self.trace = variable.trace_add("write", self.changed)
        self.entry.bind("<Down>", self.navigate)
        self.entry.bind("<Escape>", self.dismiss)
        self.entry.bind("<Return>", self.entry_return)
        self.entry.bind("<FocusIn>", self.changed)
        self.entry.bind("<FocusOut>", self.focus_out)
        self.listbox.bind("<FocusOut>", self.focus_out)
        self.listbox.bind("<Return>", self.accept)
        self.listbox.bind("<Escape>", self.dismiss)
        self.listbox.bind("<ButtonRelease-1>", self.clicked)

    def changed(self, *args):
        if self.accepting or str(self.entry.cget("state")) == "disabled":
            return
        matches = self.names.matches(self.variable.get())
        self.listbox.delete(0, "end")
        for name in matches:
            self.listbox.insert("end", name)
        if matches:
            self.listbox.configure(height=min(6, len(matches)))
            self.dropdown.pack(fill="x", pady=(2, 0))
        else:
            self.hide()

    def hide(self):
        self.dropdown.pack_forget()
        self.listbox.selection_clear(0, "end")

    def focus_out(self, event):
        self.after_idle(self.hide_if_unfocused)

    def hide_if_unfocused(self):
        if self.winfo_exists() and self.focus_get() not in (self.entry, self.listbox):
            self.hide()

    def navigate(self, event=None):
        self.changed()
        if self.listbox.size():
            self.listbox.focus_set()
            self.listbox.selection_set(0)
            self.listbox.activate(0)
        return "break"

    def entry_return(self, event=None):
        # Return still submits a typed guess; choosing from the list only fills it.
        self.hide()

    def clicked(self, event):
        index = self.listbox.nearest(event.y)
        bounds = self.listbox.bbox(index) if self.listbox.size() else None
        if bounds and bounds[1] <= event.y < bounds[1] + bounds[3]:
            self.listbox.selection_clear(0, "end")
            self.listbox.selection_set(index)
            self.accept()

    def accept(self, event=None):
        selected = self.listbox.curselection()
        if selected:
            name = self.listbox.get(selected[0])
            self.accepting = True
            self.entry.focus_set()
            self.variable.set(name)
            self.entry.icursor("end")
            self.hide()
            # FocusIn can arrive after focus_set; prevent it reopening the list.
            self.after_idle(self.allow_updates)
        return "break"

    def allow_updates(self):
        self.accepting = False

    def dismiss(self, event=None):
        self.accepting = True
        self.entry.focus_set()
        self.hide()
        self.after_idle(self.allow_updates)
        return "break"

    def destroy(self):
        self.variable.trace_remove("write", self.trace)
        super().destroy()


class TriviaApp:
    def __init__(self, root):
        self.root = root
        root.title("Courtside · NBA Trivia")
        root.geometry("1100x940")
        root.minsize(980, 880)
        root.configure(background=BG)
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=INK, font=("Helvetica", 12))
        style.configure("Muted.TLabel", foreground="#64715f", font=("Helvetica", 11))
        style.configure("Eyebrow.TLabel", foreground=RUST, font=("Helvetica", 10, "bold"))
        style.configure("TEntry", padding=10, fieldbackground=PAPER, foreground=INK)
        style.configure("TSpinbox", padding=10, arrowsize=26, fieldbackground=PAPER)
        style.configure("Treeview", rowheight=30, font=("Helvetica", 12), background=PAPER,
                        fieldbackground=PAPER, foreground=INK, borderwidth=0)
        style.configure("Treeview.Heading", font=("Helvetica", 10, "bold"),
                        background="#e4e7da", foreground=INK, padding=8)
        self.events = queue.Queue()
        self.busy = False
        self.closed = False
        self.data_dir = default_data_dir()
        self.data_path = default_roster_path()
        self.mode = tk.StringVar(value=next(iter(MODE_NAMES)))
        self.start = tk.StringVar(value=str(MIN_YEAR))
        self.end = tk.StringVar(value=str(latest_season()))
        self.team = tk.StringVar(value="All teams")
        self.goal = tk.StringVar(value="All teams")
        self.status = tk.StringVar(value="Loading your roster data…")
        self.team_ids = {"All teams": None}
        self.player_names = NameIndex([])
        self.canvas = tk.Canvas(root, background=BG, highlightthickness=0)
        page_scroll = ttk.Scrollbar(root, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=page_scroll.set)
        page_scroll.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.frame = ttk.Frame(self.canvas, padding=(30, 20))
        page = self.canvas.create_window((0, 0), window=self.frame, anchor="nw")
        self.canvas.bind("<Configure>", lambda event: self.canvas.itemconfigure(page, width=event.width))
        self.frame.bind("<Configure>", lambda event: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        root.bind("<MouseWheel>", self.scroll_page)
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.menu()
        root.after(100, self.poll)
        if self.data_path.exists():
            self.load(False)
        else:
            self.status.set("Choose a completed roster CSV to begin.")

    def button(self, parent, text, command, primary=False, **kwargs):
        return CourtButton(parent, text, command, primary, **kwargs)

    def scroll_page(self, event):
        if event.widget.winfo_class() not in ("Listbox", "Treeview", "TSpinbox"):
            steps = -int(event.delta / 120) if abs(event.delta) >= 120 else -event.delta
            self.canvas.yview_scroll(steps, "units")

    def clear(self):
        self.canvas.yview_moveto(0)
        self.root.unbind("<Return>")
        for child in self.frame.winfo_children():
            child.destroy()

    def header(self):
        ttk.Label(self.frame, text="◉  COURTSIDE", font=("Helvetica", 21, "bold")).pack(anchor="w")
        ttk.Label(self.frame, text="NBA TRIVIA CLUB  /  THE ROSTER ROOM", style="Eyebrow.TLabel").pack(anchor="w", pady=(4, 14))
        ttk.Separator(self.frame).pack(fill="x", pady=(0, 18))

    def set_mode(self, name):
        self.mode.set(name)
        self.menu()

    def menu(self):
        self.clear()
        self.header()
        ttk.Label(self.frame, text="You know the stars. Know the roster?", font=("Georgia", 29)).pack(anchor="w")
        ttk.Label(self.frame, text="Pick your era. Call your shot. Every bench counts.", style="Muted.TLabel").pack(anchor="w", pady=(6, 16))
        modes = ttk.Frame(self.frame)
        modes.pack(fill="x")
        descriptions = ["COMPLETE THE ROSTER\nName every player with 250+ team minutes", "FIND THE TEAMS\nPick a player's teams from that season"]
        for col, (name, description) in enumerate(zip(MODE_NAMES, descriptions)):
            modes.columnconfigure(col, weight=1, uniform="mode")
            self.button(modes, description, lambda n=name: self.set_mode(n), self.mode.get() == name).grid(row=0, column=col, sticky="ew", padx=(0, 10) if col == 0 else (0, 0))
        settings = ttk.Frame(self.frame)
        settings.pack(fill="x", pady=(18, 10))
        for col, (title, variable) in enumerate((("FIRST SEASON ENDING YEAR", self.start), ("LAST SEASON ENDING YEAR", self.end))):
            settings.columnconfigure(col, weight=1, uniform="years")
            ttk.Label(settings, text=title, style="Eyebrow.TLabel").grid(row=0, column=col, sticky="w")
            ttk.Spinbox(settings, from_=MIN_YEAR, to=latest_season(), textvariable=variable,
                        font=("Helvetica", 17), width=12, wrap=False).grid(row=1, column=col, sticky="ew", padx=(0, 12) if col == 0 else 0, pady=7)
        ttk.Label(self.frame, text="Type a year directly or use the arrows. 1976 means the 1975–76 season.", style="Muted.TLabel").pack(anchor="w")
        ttk.Label(self.frame, text="TEAM  /  CLICK A ROW TO SELECT", style="Eyebrow.TLabel").pack(anchor="w", pady=(17, 5))
        self.team_search = tk.StringVar()
        search = ttk.Entry(self.frame, textvariable=self.team_search, font=("Helvetica", 13))
        search.pack(fill="x")
        ttk.Label(self.frame, text="Filter teams by typing above. Leave All teams selected to include every team.", style="Muted.TLabel").pack(anchor="w", pady=4)
        body = ttk.Frame(self.frame)
        body.pack(fill="x")
        self.team_list = tk.Listbox(body, height=5, font=("Helvetica", 14), background=PAPER,
                                   foreground=INK, selectbackground=GREEN, selectforeground=PAPER,
                                   activestyle="none", exportselection=False, borderwidth=0, highlightthickness=1,
                                   highlightbackground="#b8c5af")
        scroll = ttk.Scrollbar(body, orient="vertical", command=self.team_list.yview)
        self.team_list.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.team_list.pack(side="left", fill="x", expand=True)
        self.team_list.bind("<<ListboxSelect>>", self.select_team)
        self.team_search.trace_add("write", self.update_team_list)
        self.update_team_list()
        ttk.Label(self.frame, textvariable=self.team, style="Muted.TLabel").pack(anchor="w", pady=5)
        if MODE_NAMES[self.mode.get()] == "player-teams":
            goal = ttk.Frame(self.frame)
            goal.pack(fill="x", pady=6)
            ttk.Label(goal, text="FIND").pack(side="left", padx=(0, 12))
            for title in ("One team", "All teams"):
                self.button(goal, title, lambda v=title: self.set_goal(v), self.goal.get() == title).pack(side="left", padx=5)
        else:
            ttk.Label(self.frame, text="250+ minutes • All eligible players • Randomized hints • Unlimited guesses", style="Muted.TLabel").pack(anchor="w", pady=8)
        self.submit = self.button(self.frame, "STEP ONTO THE COURT  ↗", lambda: self.load(True), True)
        self.submit.pack(fill="x", pady=(12, 8))
        files = ttk.Frame(self.frame)
        files.pack(fill="x")
        self.file_button = self.button(files, "Choose CSV…", self.choose_file)
        self.file_button.pack(side="left", padx=(0, 8))
        self.reload_button = self.button(files, "Reload data", lambda: self.load(False))
        self.reload_button.pack(side="left")
        ttk.Label(self.frame, textvariable=self.status, wraplength=1000, style="Muted.TLabel").pack(anchor="w", pady=10)
        if self.busy:
            self.set_busy(True)

    def set_goal(self, value):
        self.goal.set(value)
        self.menu()

    def update_team_list(self, *args):
        from .modes import normalized
        selected = self.team.get()
        visible = [name for name in self.team_ids if normalized(self.team_search.get()) in normalized(name)]
        self.team_list.delete(0, "end")
        for name in visible:
            self.team_list.insert("end", name)
        if selected in visible:
            index = visible.index(selected)
            self.team_list.selection_set(index)
            self.team_list.see(index)

    def select_team(self, event=None):
        selected = self.team_list.curselection()
        if selected:
            self.team.set(self.team_list.get(selected[0]))

    def choose_file(self):
        path = filedialog.askopenfilename(title="Choose normalized roster CSV", filetypes=[("CSV files", "*.csv")])
        if path:
            self.data_path = Path(path)
            self.load(False)

    def set_busy(self, value):
        self.busy = value
        for widget in (self.submit, self.file_button, self.reload_button):
            widget.config(state="disabled" if value else "normal")

    def load(self, play):
        if self.busy:
            return
        try:
            start, end = int(self.start.get()), int(self.end.get())
            if not MIN_YEAR <= start <= end <= latest_season():
                raise ValueError("Choose a valid year range with start ≤ finish.")
        except ValueError:
            self.status.set(f"Enter whole years between {MIN_YEAR} and {latest_season()}, with start ≤ finish.")
            return
        self.set_busy(True)
        self.status.set("Reading roster CSV…")
        path = self.data_path
        mode, team, goal = MODE_NAMES[self.mode.get()], self.team_ids[self.team.get()], self.goal.get()

        def work():
            try:
                if not path.exists():
                    raise ValueError("Roster CSV is not ready. Let the scraper finish, then choose its output CSV.")
                rows = read_csv(path)
                session = make_session(select_range(rows, start, end), mode, team,
                                       "one" if goal == "One team" else "all") if play else None
                self.events.put(("ready", (rows, session)))
            except Exception as error:
                self.events.put(("error", str(error)))
        threading.Thread(target=work, daemon=True).start()

    def poll(self):
        if self.closed:
            return
        try:
            while True:
                kind, payload = self.events.get_nowait()
                self.set_busy(False)
                if kind == "error":
                    self.status.set(payload)
                else:
                    rows, session = payload
                    self.player_names = NameIndex(r.player_name for r in rows)
                    names = {}
                    for row in rows:
                        if row.league == "NBA" and row.season_end >= MIN_YEAR:
                            names.setdefault(row.team_id, set()).add(row.team_name)
                    self.team_ids = {"All teams": None, **{
                        f"{' / '.join(sorted(labels))} ({tid})": tid for tid, labels in
                        sorted(names.items(), key=lambda item: sorted(item[1])[0])}}
                    if self.team.get() not in self.team_ids:
                        self.team.set("All teams")
                    self.update_team_list()
                    self.status.set(f"{len(rows):,} roster records ready · {self.data_path.name}")
                    if session:
                        self.session = session
                        self.show_game()
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    @staticmethod
    def display(value):
        return "—" if value is None or value == "" else str(value)

    def show_game(self):
        self.clear()
        self.header()
        s = self.session
        ttk.Label(self.frame, text=s.prompt, wraplength=1010, font=("Georgia", 22)).pack(fill="x", pady=(0, 12))
        if s.mode == "player-teams":
            stats = s.season_stats()
            games, minutes = stats['games'], stats['minutes_total']
            text = " · ".join(f"{field.upper()} {self.display(stats[field])}" for field in ("ppg", "rpg", "apg", "spg", "bpg"))
            ttk.Label(self.frame, text=f"{games} games · {minutes:g} minutes · {minutes/games:.1f} MPG\nApproximate season averages: {text}", style="Muted.TLabel").pack(anchor="w", pady=(0, 8))
        columns = ("name", "games") if s.mode == "player-teams" else ("name", "position", "games", "traded") + s.hint_fields
        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=s.mode == "one-player", pady=5)
        self.table = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="none",
                                 height=min(8 if s.mode == "one-player" else 3, len(s.answers)))
        self.table.tag_configure("revealed", foreground=RED)
        titles = {"name": "TEAM" if s.mode == "player-teams" else "PLAYER", "position": "POS", "games": "GAMES", "traded": "TRADED*", "height_inches": "HEIGHT", "jersey_number": "JERSEY", "ppg": "PPG", "age": "AGE", "is_all_star": "ALL-STAR", "college": "COLLEGE"}
        for column in columns:
            self.table.heading(column, text=titles[column])
            self.table.column(column, width=230 if column in ("name", "college") else 85, minwidth=65, stretch=column in ("name", "college"))
        horizontal = ttk.Scrollbar(table_frame, orient="horizontal", command=self.table.xview)
        self.table.configure(xscrollcommand=horizontal.set)
        horizontal.pack(side="bottom", fill="x")
        scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.table.pack(side="left", fill="both", expand=True)
        self.progress = ttk.Label(self.frame, style="Eyebrow.TLabel")
        self.progress.pack(anchor="w", pady=8)
        self.entry = self.guess_button = self.hint_button = None
        self.autocomplete = None
        self.team_buttons = {}
        if s.mode == "player-teams":
            ttk.Label(self.frame, text="CHOOSE A TEAM · FIVE INCORRECT GUESSES MAXIMUM", style="Eyebrow.TLabel").pack(anchor="w", pady=(0, 5))
            teams = ttk.Frame(self.frame)
            teams.pack(fill="x")
            for i, (tid, name) in enumerate(s.team_options):
                teams.columnconfigure(i % 5, weight=1, uniform="teams")
                button = self.button(teams, name, lambda t=tid: self.submit_guess(t), wraplength=175)
                button.configure(font=("Helvetica", 11, "bold"), pady=9, padx=5)
                button.grid(row=i // 5, column=i % 5, sticky="nsew", padx=3, pady=3)
                self.team_buttons[tid] = button
        else:
            ttk.Label(self.frame, text="*Traded: another team record in the CSV that season. Rows ordered by PPG.", style="Muted.TLabel").pack(anchor="w", pady=4)
            self.guess_text = tk.StringVar()
            row = ttk.Frame(self.frame)
            row.pack(fill="x", pady=8)
            self.autocomplete = AutocompleteEntry(row, self.guess_text, self.player_names)
            self.autocomplete.pack(side="left", fill="x", expand=True, padx=(0, 10), anchor="n")
            self.entry = self.autocomplete.entry
            self.guess_button = self.button(row, "Submit guess", self.submit_guess, True)
            self.guess_button.pack(side="right", anchor="n")
            self.entry.focus_set()
            self.root.bind("<Return>", lambda event: self.submit_guess())
        self.feedback = ttk.Label(self.frame, text="", wraplength=1010)
        self.feedback.pack(anchor="w", pady=8)
        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", pady=5)
        if s.mode == "one-player":
            self.hint_button = self.button(actions, f"Reveal hint · {len(s.hints)} left", self.reveal_hint)
            self.hint_button.pack(side="left", padx=(0, 10))
        self.quit_button = self.button(actions, "Quit & reveal answers", self.quit_game)
        self.quit_button.pack(side="left")
        self.return_button = self.button(actions, "Return to menu", self.menu, True)
        self.refresh_table()

    def refresh_table(self, reveal=False):
        s = self.session
        self.progress.config(text=f"FOUND {len(s.found)} / {len(s.answers)}" + (f"  ·  INCORRECT {s.wrong}/5" if s.mode == "player-teams" else ""))
        self.table.delete(*self.table.get_children())
        for row in s.answers:
            visible = reveal or s.identity(row) in s.found
            name = s.label(row) if visible else "________________"
            if s.mode == "player-teams":
                values = (name, self.display(row.games))
            else:
                extras = []
                for field in s.hint_fields:
                    value = getattr(row, field)
                    if field == "is_all_star" and value is not None:
                        value = "Yes" if value else "No"
                    if field == "height_inches" and value is not None:
                        value = f"{value // 12}′ {value % 12}″"
                    extras.append(self.display(value) if visible or field in s.revealed_hints else "Hidden")
                traded = len(s.traded.get((row.player_id, row.season_end), set())) > 1
                values = (name, self.display(row.position), self.display(row.games), "Yes" if traded else "No", *extras)
            self.table.insert("", "end", values=values,
                              tags=("revealed",) if reveal and s.identity(row) not in s.found else ())

    def submit_guess(self, team_id=None):
        if self.session.outcome:
            return
        if self.autocomplete:
            self.autocomplete.hide()
        value = team_id if team_id is not None else self.guess_text.get()
        message = self.session.guess(value)
        self.feedback.config(text=message)
        if team_id is not None:
            correct = team_id in self.session.found
            self.team_buttons[team_id].config(state="disabled", background=GREEN if correct else "#f6dfd7",
                                               foreground=PAPER if correct else RED, disabledforeground=PAPER if correct else RED)
        elif message == "Correct!":
            self.guess_text.set("")
        self.refresh_table()
        if self.session.outcome:
            self.finish()

    def reveal_hint(self):
        self.session.hint()
        self.refresh_table()
        left = len(self.session.hints)
        self.hint_button.config(text=f"Reveal hint · {left} left", state="normal" if left else "disabled")

    def quit_game(self):
        self.session.quit()
        self.finish()

    def finish(self):
        s = self.session
        self.root.unbind("<Return>")
        if self.autocomplete:
            self.autocomplete.hide()
        self.refresh_table(reveal=True)
        for control in (self.entry, self.guess_button, self.hint_button):
            if control:
                control.config(state="disabled")
        for tid, button in self.team_buttons.items():
            button.config(state="disabled")
            if any(r.team_id == tid for r in s.answers) and tid not in s.found:
                button.config(background="#f6dfd7", disabledforeground=RED)
        self.quit_button.pack_forget()
        self.feedback.config(text={"victory": "Victory! You know your roster.", "failure": "Game over — five incorrect guesses.", "quit": "Answers revealed in red."}[s.outcome], font=("Georgia", 18))
        self.return_button.pack(side="right")

    def close(self):
        self.closed = True
        self.root.destroy()


def main():
    root = tk.Tk()
    TriviaApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
