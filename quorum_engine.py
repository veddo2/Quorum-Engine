"""
THE QUORUM ENGINE
Tabs:
  Town vote    - deal a town meeting
  Council vote - deal a council session (individuals, one vote each)
  Factions     - configure the town's blocs
  Council      - configure the council's individuals and their personalities
  History      - every vote you have run
"""

import copy
import datetime
import json
import math
import os
import random
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any

# --------------------------------------------------------------------------
# constants
# --------------------------------------------------------------------------

SUITS = ("h", "d", "c", "s")
SYM = {"h": "\u2665", "d": "\u2666", "c": "\u2663", "s": "\u2660"}
DOMAIN = {"h": "Care", "d": "Means", "c": "Safety", "s": "Say"}
DOMAIN_NOTE = {
    "h": "food, medicine, mercy, morale",
    "d": "fuel, tools, trade, property",
    "c": "walls, weapons, patrols, work",
    "s": "law, tradition, status, faith",
}
RANKS = ("A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K")
VALUE = {"A": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6,
         "7": 7, "8": 8, "9": 9, "10": 10, "J": 11, "Q": 12, "K": 13}
# every face card is the same: a bloc takes the floor and swings its suit by 2
SPEECH = {"J": 2, "Q": 2, "K": 2}
WORD = {"J": "jack", "Q": "queen", "K": "king"}
SWAY_CAP = 4            # the room's ceiling on floor sway, before explosions

WT_MIN, WT_MAX = 1, 99
REL_MIN, REL_MAX = -4, 4
RAT_MIN, RAT_MAX = 1, 4
DIFF_MIN, DIFF_MAX = 4, 12
# on a 1-13 deck the middle card is 7, so 7 is the coin flip. below it the room
# tends to pass, above it the room tends to refuse.
DIFF_DEFAULT = 7

ZEA_CAP = 0.75          # a zealous bloc never votes against, but tops out here
APA_CAP = 0.25          # an apathetic bloc never votes for, and barely turns out

# Does the turnout cut bite always, or only when the flag has to change the side
# the bloc would otherwise vote? False = always, the moment the flag is ticked.
# Zeal is a loyalty state, so it only costs them when they have to be dragged in.
# Apathy is a turnout state, so it bites every time.
APA_ONLY_WHEN_TURNED = False
ZEA_ONLY_WHEN_HELD = True

DISPOSITION_ORDER = ("Zealous", "Apathetic", "for it, hard", "leans for",
                     "of two minds", "leans against", "against it, hard")

BOX_ON = "\u2611"
BOX_OFF = "\u2610"

# one shared column spec for the editor header and every editor row, so the
# labels can never drift off their widgets. (field, pixel width, stretch?)
EDITOR_COLS = (
    ("name",  200, True),
    ("hook",  220, True),
    ("h",      44, False),
    ("d",      44, False),
    ("c",      44, False),
    ("s",      44, False),
    ("rel",    54, False),
    ("wt",     54, False),
)
EDITOR_HEAD = {"name": "name", "hook": "notes", "rel": "rel", "wt": "wt"}

# combobox shows a label; the engine wants a suit key. keep both directions.
SUIT_LABELS = {k: f"{SYM[k]}  {DOMAIN[k]}" for k in SUITS}
LABEL_SUIT = {v: k for k, v in SUIT_LABELS.items()}
SYM_SUIT = {v: k for k, v in SYM.items()}

PERMS = [
    [4, 3, 2, 1], [4, 3, 1, 2], [4, 2, 3, 1], [4, 2, 1, 3], [4, 1, 3, 2], [4, 1, 2, 3],
    [3, 4, 2, 1], [3, 4, 1, 2], [3, 2, 4, 1], [3, 2, 1, 4], [3, 1, 4, 2], [3, 1, 2, 4],
    [2, 4, 3, 1], [2, 4, 1, 3], [2, 3, 4, 1], [2, 3, 1, 4], [2, 1, 4, 3], [2, 1, 3, 4],
    [1, 4, 3, 2], [1, 4, 2, 3], [1, 3, 4, 2], [1, 3, 2, 4], [1, 2, 4, 3], [1, 2, 3, 4],
]

DEFAULT_FACTIONS = [
    ("The Grange (farm families)", {"h": 4, "d": 3, "c": 2, "s": 1},  1, 5, "seed, labour, food"),
    ("Mill hands",                 {"h": 2, "d": 4, "c": 3, "s": 1},  0, 4, "fuel, muscle, machines"),
    ("The congregation",           {"h": 3, "d": 2, "c": 1, "s": 4},  2, 4, "legitimacy, the pulpit"),
    ("Clinic staff",               {"h": 4, "d": 1, "c": 2, "s": 3},  3, 2, "medicine, expertise"),
    ("Prepper compound",           {"h": 1, "d": 3, "c": 4, "s": 2}, -2, 3, "guns, generators"),
    ("Refugee families",           {"h": 4, "d": 2, "c": 3, "s": 1},  1, 3, "gratitude, willing hands"),
    ("The old-timers",             {"h": 1, "d": 2, "c": 3, "s": 4},  0, 2, "memory, precedent"),
    ("The teens",                  {"h": 2, "d": 4, "c": 3, "s": 1},  0, 3, "legs, nerve, gossip"),
]

DEFAULT_COUNCIL = [
    ("Mayor Ruth Alvarez", {"h": 3, "d": 2, "c": 1, "s": 4},  1, 1,
     "tired, wants consensus, hates a scene"),
    ("Deacon Pike",        {"h": 4, "d": 2, "c": 1, "s": 3},  2, 1,
     "moral authority, keeps score of favours"),
    ("Harlan Voss",        {"h": 2, "d": 4, "c": 3, "s": 1},  0, 1,
     "mill owner, counts every barrel twice"),
    ("Sgt. Mears",         {"h": 1, "d": 3, "c": 4, "s": 2}, -1, 1,
     "ex-army, thinks only about the perimeter"),
    ("Dr. Chen",           {"h": 4, "d": 1, "c": 2, "s": 3},  3, 1,
     "clinic, exhausted, will not be talked over"),
]


def _data_dir() -> str:
    """Where the save lives.

    Running from source, that is the folder the script sits in. Frozen into an
    exe, __file__ points inside a temp folder that is wiped on exit, so use the
    folder the exe sits in instead - and if that folder is not writable (an
    install under Program Files), fall back to %APPDATA%.
    """
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    try:
        probe = os.path.join(base, ".write_test")
        with open(probe, "w", encoding="utf-8") as fh:
            fh.write("")
        os.remove(probe)
        return base
    except OSError:
        fallback = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"),
                                "QuorumEngine")
        os.makedirs(fallback, exist_ok=True)
        return fallback


DEFAULT_SAVE = os.path.join(_data_dir(), "quorum_save.json")


def new_entity(name: str) -> dict[str, Any]:
    return {"name": name, "ratings": {"h": 4, "d": 3, "c": 2, "s": 1},
            "rel": 0, "wt": 1, "hook": "", "apa": False, "zea": False}


def blank_state() -> dict[str, Any]:
    return {
        "factions": [
            {"name": n, "ratings": dict(r), "rel": rel, "wt": wt, "hook": hook,
             "apa": False, "zea": False}
            for (n, r, rel, wt, hook) in DEFAULT_FACTIONS],
        "council": [
            {"name": n, "ratings": dict(r), "rel": rel, "wt": wt, "hook": hook,
             "apa": False, "zea": False}
            for (n, r, rel, wt, hook) in DEFAULT_COUNCIL],
        "history": [],
        "settings": {
            "keep_ladders": True,
            "town":    {"difficulty": DIFF_DEFAULT,
                        "bill_title": "Seal the north road and turn back outsiders",
                        "bill_frame": "c", "bill_cost": "d"},
            "council": {"difficulty": DIFF_DEFAULT,
                        "bill_title": "Grant the clinic the last of the diesel",
                        "bill_frame": "h", "bill_cost": "d"},
        },
    }


def suit_key(text: Any) -> str:
    """Normalise a suit from a combobox label ('\u2663  Safety'), a bare symbol
    ('\u2663'), or a bare key ('c'). Falls back to 'h'."""
    if text in LABEL_SUIT:
        return LABEL_SUIT[text]
    if text in SYM_SUIT:
        return SYM_SUIT[text]
    if text in SYM:
        return text
    return "h"


def clamp_int(value: Any, default: int, lo: int, hi: int) -> int:
    try:
        val = int(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, val))


def var_int(var: Any, default: int | None = None) -> int | None:
    """Read an IntVar without blowing up on a half-typed string like '-' or ''."""
    try:
        return int(var.get())
    except (tk.TclError, ValueError):
        return default


def safe_int(var: Any, default: int, lo: int | None = None,
             hi: int | None = None) -> int:
    val = var_int(var, default)
    if val is None:
        val = default
    if lo is not None:
        val = max(lo, val)
    if hi is not None:
        val = min(hi, val)
    return val


def fmt_num(x: float) -> str:
    """Whole numbers print bare; fractions print trimmed. Keeps tallies readable."""
    if abs(x - round(x)) < 1e-9:
        return str(int(round(x)))
    return f"{x:.2f}".rstrip("0").rstrip(".")


def card_str(card: tuple[str, str]) -> str:
    return f"{card[1]}{SYM[card[0]]}"


def listen_mult(rel: int) -> float:
    """How closely someone follows YOUR arguments, by relationship."""
    if rel >= 3:
        return 2.0
    if rel >= 0:
        return 1.0
    if rel >= -3:
        return 0.5
    return 0.0


def apply_mult(val: int, mult: float) -> int:
    if val == 0:
        return 0
    out = int(round(abs(val) * mult))
    if mult > 0:
        out = max(1, out)
    return out if val > 0 else -out


def flag_nudge(ent: dict[str, Any]) -> int:
    """Zealous leans them in, apathetic lets them drift out."""
    return -1 if ent["apa"] else (1 if ent["zea"] else 0)


def rec_difficulty(rec: dict[str, Any]) -> int:
    """Pass difficulty of a history record. Older records stored it as 'anchor'."""
    return clamp_int(rec.get("difficulty", rec.get("anchor", DIFF_DEFAULT)),
                     DIFF_DEFAULT, DIFF_MIN, DIFF_MAX)


# --------------------------------------------------------------------------
# the vote panel (used by both Town and Council)
# --------------------------------------------------------------------------

class VotePanel(ttk.Frame):

    def __init__(self, parent: tk.Misc, app: "QuorumApp", key: str,
                 show_weight: bool):
        super().__init__(parent)
        self.app = app
        self.key = key                      # "factions" or "council"
        self.show_weight = show_weight
        self.settings: dict[str, Any] = app.state["settings"][
            "town" if key == "factions" else "council"]

        self.results: list[dict[str, Any]] = []
        self.pool: list[dict[str, Any]] = []
        self.address: tuple[str, str] | None = None
        self.leverage = 3
        self.leverage_used = 0
        self.floors_used: set[str] = set()
        self.current_record: dict[str, Any] | None = None
        self._save_job: str | None = None
        self._ctx_menu: tk.Menu | None = None

        self.build()
        self.render()

    # -------- ui --------

    def build(self) -> None:
        s = self.settings

        bill = ttk.LabelFrame(self, text="The bill on the table", padding=10)
        bill.pack(fill="x", padx=6, pady=6)
        # the title row takes all the slack, so the panel tracks the window
        bill.columnconfigure(1, weight=1)

        ttk.Label(bill, text="Title").grid(row=0, column=0, sticky="w")
        self.var_title = tk.StringVar(value=s["bill_title"])
        ttk.Entry(bill, textvariable=self.var_title, width=36).grid(
            row=0, column=1, sticky="we", padx=6)
        self.var_title.trace_add("write", lambda _n, _i, _m: self.on_bill_change())

        # the option row sits in its own frame so it never shares a column with
        # the title - that is what lets the title stretch past it
        opts = ttk.Frame(bill)
        opts.grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))

        ttk.Label(opts, text="Serves").pack(side="left")
        self.var_frame = tk.StringVar(value=SUIT_LABELS[suit_key(s["bill_frame"])])
        ttk.Combobox(opts, textvariable=self.var_frame, width=16, state="readonly",
                     values=[SUIT_LABELS[k] for k in SUITS]).pack(side="left", padx=6)
        self.var_frame.trace_add("write", lambda _n, _i, _m: self.on_bill_change())

        ttk.Label(opts, text="Spends").pack(side="left", padx=(12, 0))
        self.var_cost = tk.StringVar(value=SUIT_LABELS[suit_key(s["bill_cost"])])
        ttk.Combobox(opts, textvariable=self.var_cost, width=16, state="readonly",
                     values=[SUIT_LABELS[k] for k in SUITS]).pack(side="left", padx=6)
        self.var_cost.trace_add("write", lambda _n, _i, _m: self.on_bill_change())

        ttk.Label(opts, text="Pass Difficulty").pack(side="left", padx=(12, 0))
        self.var_difficulty = tk.IntVar(value=s["difficulty"])
        diff_box = ttk.Spinbox(opts, from_=DIFF_MIN, to=DIFF_MAX, width=5,
                               textvariable=self.var_difficulty,
                               command=self.on_difficulty_change)
        diff_box.pack(side="left", padx=6)
        self.var_difficulty.trace_add(
            "write", lambda _n, _i, _m: self.on_difficulty_change())

        self.lbl_bands = ttk.Label(bill, text="", justify="left", anchor="w")
        self.lbl_bands.grid(row=2, column=0, columnspan=2, sticky="we", pady=(8, 0))
        # wrap the legend to the frame instead of letting it set the frame's width
        bill.bind("<Configure>",
                  lambda e: self.lbl_bands.configure(wraplength=max(240, e.width - 26)))

        ctl = ttk.Frame(self)
        ctl.pack(fill="x", padx=6)
        ttk.Button(ctl, text="Open the meeting", command=self.deal).pack(side="left")
        ttk.Button(ctl, text="Clear", command=self.clear_vote).pack(side="left", padx=6)
        ttk.Button(ctl, text="Clear flags", command=self.clear_flags).pack(side="left")
        ttk.Button(ctl, text="Make argument", command=self.make_argument).pack(
            side="left", padx=(18, 0))
        ttk.Button(ctl, text="Record to history", command=self.record_vote).pack(
            side="left", padx=(18, 0))
        self.lbl_leverage = ttk.Label(ctl, text="")
        self.lbl_leverage.pack(side="left", padx=12)

        pool_frame = ttk.LabelFrame(self, text="The pool - speeches in the room", padding=8)
        pool_frame.pack(fill="x", padx=6, pady=6)
        self.pool_inner = ttk.Frame(pool_frame)
        self.pool_inner.pack(fill="x", anchor="w")

        self.hint = ttk.Label(self, text="", foreground="#555")
        self.hint.pack(fill="x", padx=8)

        cols = ("name", "disposition", "apa", "zea", "card", "outcome", "weight", "notes")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=11)
        for c, w in zip(cols, (190, 120, 44, 44, 56, 150, 56, 300)):
            self.tree.heading(c, text="faction" if c == "name" else c.capitalize())
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=6, pady=(4, 6))
        for tag, colr in (("yes", "#15803d"), ("halfy", "#4d7c0f"), ("neutral", "#6b7280"),
                          ("halfn", "#b45309"), ("no", "#b91c1c")):
            self.tree.tag_configure(tag, foreground=colr)
        self.tree.bind("<Button-1>", self.on_tree_click)
        self.tree.bind("<Button-3>", self.on_tree_rightclick)

        self.apa_col = f"#{cols.index('apa') + 1}"
        self.zea_col = f"#{cols.index('zea') + 1}"

        self.summary = tk.Text(self, height=10, wrap="word")
        self.summary.pack(fill="both", padx=6, pady=(0, 8))
        self.summary.configure(state="disabled")

    def roster(self) -> list[dict[str, Any]]:
        return self.app.state[self.key]

    def frame_suit(self) -> str:
        return suit_key(self.var_frame.get())

    def cost_suit(self) -> str:
        return suit_key(self.var_cost.get())

    def difficulty_T(self) -> int:
        return safe_int(self.var_difficulty, DIFF_DEFAULT, lo=DIFF_MIN, hi=DIFF_MAX)

    def band_for(self, score: int, T: int) -> tuple[str, float]:
        """The band a score lands in, and the turnout multiplier that goes with
        it. The difficulty is the pivot: reaching it puts a bloc on the for side."""
        if score >= T + 2:
            return ("yes", 1.0)
        if score >= T:
            return ("halfy", 0.5)
        if score >= T - 2:
            return ("halfn", 0.5)
        return ("no", 1.0)

    def sway_cap(self) -> int:
        """The room's ceiling on floor sway. An exploded speech pushes it up, so
        a chained speech is never silently swallowed by the flat cap."""
        loudest = max((p.get("magnitude", SPEECH["K"]) for p in self.pool),
                      default=SPEECH["K"])
        return SWAY_CAP + max(0, loudest - SPEECH["K"])

    def on_bill_change(self) -> None:
        self.settings["bill_title"] = self.var_title.get()
        self.settings["bill_frame"] = self.frame_suit()
        self.settings["bill_cost"] = self.cost_suit()
        if self.results:
            self.recompute()
        self.render()
        self.debounced_save()

    def debounced_save(self) -> None:
        if self._save_job:
            self.after_cancel(self._save_job)
        self._save_job = self.after(500, self._flush_save)

    def _flush_save(self) -> None:
        self._save_job = None
        self.app.save_file()

    def on_difficulty_change(self) -> None:
        T = self.difficulty_T()
        if var_int(self.var_difficulty, T) != T:
            self.var_difficulty.set(T)
        self.settings["difficulty"] = T
        self.app.save_file()
        self.render_bands()
        if self.results:
            self.recompute()
            self.render()

    def render_bands(self) -> None:
        T = self.difficulty_T()
        f, c = self.frame_suit(), self.cost_suit()
        self.lbl_bands.config(text=(
            f"Pass difficulty {T} - the score a bloc must reach to be on the for side. "
            f"Higher is harder. On a 1-13 deck the middle card is 7, so 7 is the coin flip.\n"
            f"Bands on score:  <= {T-3}  against, as a bloc   |   {T-2}-{T-1}  splits, half against"
            f"   |   {T}-{T+1}  splits, half for   |   {T+2}+  for it, as a bloc\n"
            f"Score: the card's face value, plus their lean, plus one if the previous bloc drew "
            f"the same suit. That is the whole of it - a speech never changes it.\n"
            f"Lean: their rating in the served domain ({SYM[f]} {DOMAIN[f]}), or minus their "
            f"rating in the spent domain ({SYM[c]} {DOMAIN[c]}) - whichever is bigger.\n"
            f"A face card (J, Q, K) means that bloc takes the floor: they draw again for their "
            f"real vote, and every extra face card in a row makes that speech one louder.\n"
            f"Speeches decide turnout, not minds. Once a bloc has made its mind up, a speech only "
            f"rallies the blocs of its own suit who already agree with it, and dampens the ones "
            f"who do not. Nobody is ever talked across.\n"
            f"Relationship does not affect the score. It only decides how hard your arguments land: "
            f"rel +3 or more x2, rel 0 to +2 x1, rel -1 to -3 x0.5, rel -4 or worse x0.\n"
            f"Flags override the outcome: a zealous bloc will not vote against and comes in for "
            f"the bill; an apathetic bloc will not vote for and lands against it. Zeal only costs "
            f"turnout when it has to drag them in - three-quarter if the read had it against, "
            f"full if the read already agreed. Apathy turns out at a quarter every time, "
            f"whichever way the read went."
        ))

    # -------- mechanics --------

    def build_deck(self) -> list[tuple[str, str]]:
        deck = [(s, r) for s in SUITS for r in RANKS]
        random.shuffle(deck)
        return deck

    def deal(self) -> None:
        facs = self.roster()
        if not facs:
            messagebox.showinfo("Nothing to deal",
                                f"Add some {'factions' if self.key == 'factions' else 'councillors'} "
                                f"on the {self.key.capitalize()} tab first.")
            return

        deck = self.build_deck()

        def draw() -> tuple[str, str]:
            if not deck:
                deck.extend(self.build_deck())
            return deck.pop()

        self.address = draw()
        a_rank = self.address[1]
        self.leverage = 3 if a_rank in SPEECH else min(4, max(1, VALUE[a_rank]))
        self.leverage_used = 0
        self.floors_used = set()
        self.pool = []

        self.results = []
        prev = None
        for f in facs:
            card = draw()
            # a face card takes the floor: they draw again for their real vote,
            # and if that is a face card too, it explodes - keep drawing. every
            # face card in the run makes the one speech louder by 1.
            floor: list[tuple[str, str]] = []
            while card[1] in SPEECH:
                floor.append(card)
                card = draw()
            suit, rank = card
            momentum = 1 if prev == suit else 0
            prev = suit
            self.results.append({
                "name": f["name"], "suit": suit, "rank": rank,
                "lean": 0, "momentum": momentum,
                "base": 0, "score": 0, "speaker": False,
                "rally": 0, "turnout_shift": 0, "flag_nudge": 0,
                "floor_card": card_str(floor[-1]) if floor else "",
                "floor_n": len(floor),
                "held_by_zeal": False, "turned_by_apathy": False,
            })
            if floor:
                self.pool.append({
                    "suit": floor[0][0], "rank": floor[0][1], "who": f["name"],
                    "speaker": len(self.results) - 1, "sign": 0,
                    "magnitude": SPEECH[floor[0][1]] + len(floor) - 1,
                    "chain": len(floor),
                })
        for p in self.pool:
            self.results[p["speaker"]]["speaker"] = True

        self.recompute()
        self.render()
        self.app.status(f"{'Town meeting' if self.key == 'factions' else 'Council session'} opened.")

    def clear_vote(self) -> None:
        self.results = []
        self.pool = []
        self.address = None
        self.current_record = None
        self.leverage_used = 0
        self.floors_used = set()
        self.clear_flags()
        self.render()

    def clear_flags(self) -> None:
        for f in self.roster():
            f["apa"] = f["zea"] = False
        self.app.save_file()

    def recompute(self) -> None:
        results = self.results
        if not results:
            return
        T = self.difficulty_T()
        roster = self.roster()

        # 1. THE MIND. their own card, the bill's lean, momentum - and nothing
        #    else. a speech never touches this number.
        for i, r in enumerate(results):
            f = roster[i]
            r["lean"] = self.lean(f)
            r["score"] = VALUE[r["rank"]] + r["lean"] + r["momentum"]
            r["base"] = r["score"]

        # 2. THE MIND, SET. the band comes off their own card alone. flags are a
        #    commitment rather than an argument, so those do set the mind - and
        #    they set it before anyone speaks.
        for i, r in enumerate(results):
            f = roster[i]
            r["flag_nudge"] = flag_nudge(f)
            r["band"], r["w"] = self.band_for(r["score"], T)
            r["held_by_zeal"] = False
            r["turned_by_apathy"] = False
            if f["apa"]:
                # checked out: if the read had them with you, they stay home and
                # land against you anyway, at quarter strength.
                if r["band"] in ("yes", "halfy"):
                    r["band"], r["w"] = "no", APA_CAP
                    r["turned_by_apathy"] = True
                elif not APA_ONLY_WHEN_TURNED:
                    r["w"] = APA_CAP
            elif f["zea"]:
                # committed: if the read had them against you, they come in
                # anyway, capped at three-quarter strength.
                if r["band"] in ("halfn", "no"):
                    r["band"], r["w"] = "yes", ZEA_CAP
                    r["held_by_zeal"] = True
                elif not ZEA_ONLY_WHEN_HELD:
                    r["w"] = ZEA_CAP

        # 3. THE FLOOR. every mind is already made, so a speech cannot flip
        #    anyone. it rallies the blocs of its own suit who are on its side,
        #    and dampens the ones who are not. the sign is read off the
        #    speaker's settled vote, so nothing loops back into the mind. this
        #    lands on its own - nobody clicks a speech onto a target.
        for p in self.pool:
            if p.get("fixed"):
                continue
            band = results[p["speaker"]]["band"]
            p["sign"] = 1 if band in ("yes", "halfy") else -1

        cap = self.sway_cap()
        for i, r in enumerate(results):
            s = 0
            for p in self.pool:
                if p["suit"] != r["suit"] or p["speaker"] == i:
                    continue
                val = p["magnitude"]
                if p["who"] == "You":
                    val = apply_mult(val, listen_mult(roster[i]["rel"]))
                s += p["sign"] * val
            r["rally"] = max(-cap, min(cap, s))
            # matched to their own side: a rally helps the people who already
            # agree, and the other side's noise turns their own out less
            on_side = 1 if r["band"] in ("yes", "halfy") else -1
            r["turnout_shift"] = max(-cap, min(cap, r["rally"] * on_side))

        # 4. TURNOUT. the flag cuts it, the floor moves it, and nobody vanishes.
        for i, r in enumerate(results):
            f = roster[i]
            base_w = clamp_int(f["wt"], WT_MIN, WT_MIN, WT_MAX)
            r["weight"] = max(WT_MIN, math.ceil(base_w * r["w"]) + r["turnout_shift"])
            r["rider"] = ("will do more than asked" if (r["band"] == "yes" and r["score"] >= T + 4)
                          else "will work against you" if (r["band"] == "no" and r["score"] <= T - 4)
                          else "")

    # -------- arguments --------

    def make_argument(self) -> None:
        if not self.results:
            self.app.status("Open the meeting first.")
            return
        if self.leverage_used >= self.leverage:
            self.app.status("You are out of leverage - no more arguments.")
            return

        dlg = tk.Toplevel(self)
        dlg.title("Make an argument")
        dlg.transient(self.app)
        dlg.resizable(False, False)

        ttk.Label(dlg, text="What is your argument about?",
                  padding=(14, 12, 14, 4)).pack(anchor="w")
        suit_var = tk.StringVar(value="h")
        sframe = ttk.Frame(dlg, padding=(14, 0))
        sframe.pack(fill="x")
        for k in SUITS:
            ttk.Radiobutton(sframe, text=f"{SYM[k]}   {DOMAIN[k]}   ({DOMAIN_NOTE[k]})",
                            value=k, variable=suit_var).pack(anchor="w")

        ttk.Label(dlg, text="Which way are you arguing?",
                  padding=(14, 12, 14, 4)).pack(anchor="w")
        dir_var = tk.StringVar(value="for")
        dframe = ttk.Frame(dlg, padding=(14, 0))
        dframe.pack(fill="x")
        ttk.Radiobutton(dframe, text="For the bill", value="for",
                        variable=dir_var).pack(anchor="w")
        ttk.Radiobutton(dframe, text="Against the bill", value="against",
                        variable=dir_var).pack(anchor="w")

        err = ttk.Label(dlg, text="", foreground="#b91c1c", padding=(14, 8, 14, 0))
        err.pack(anchor="w")

        def confirm() -> None:
            suit = suit_var.get()
            if suit in self.floors_used:
                err.config(text=f"You have already argued {DOMAIN[suit]} here tonight.")
                return
            sign = 1 if dir_var.get() == "for" else -1
            self.pool.append({"suit": suit, "rank": "K", "who": "You",
                              "speaker": -1, "sign": sign, "fixed": True,
                              "magnitude": SPEECH["K"], "chain": 1})
            self.leverage_used += 1
            self.floors_used.add(suit)
            self.recompute()
            self.render()
            self.app.status(f"You argue {'for' if sign > 0 else 'against'} {DOMAIN[suit]}.")
            dlg.destroy()

        btns = ttk.Frame(dlg, padding=14)
        btns.pack(fill="x")
        ttk.Button(btns, text="Make the argument", command=confirm).pack(side="right")
        ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(side="right", padx=6)
        dlg.bind("<Return>", lambda _e: confirm())
        dlg.bind("<Escape>", lambda _e: dlg.destroy())

        dlg.update_idletasks()
        dlg.geometry(f"+{self.app.winfo_rootx() + 200}+{self.app.winfo_rooty() + 160}")
        dlg.grab_set()

    # -------- reading the room --------

    def lean(self, f: dict[str, Any]) -> int:
        """The bill's pull on this bloc: their rating in the served domain, or
        minus their rating in the spent domain, whichever is bigger."""
        served = clamp_int(f["ratings"].get(self.frame_suit(), 1), 1, RAT_MIN, RAT_MAX)
        spent = clamp_int(f["ratings"].get(self.cost_suit(), 1), 1, RAT_MIN, RAT_MAX)
        if served > spent:
            return served
        if spent > served:
            return -spent
        return 0

    def disposition(self, f: dict[str, Any]) -> int:
        """Their standing read on the bill, before any card is dealt."""
        return self.lean(f) + flag_nudge(f)

    def disposition_band(self, score: int) -> tuple[str, str]:
        if score >= 3:
            return ("for it, hard", "yes")
        if score >= 1:
            return ("leans for", "halfy")
        if score <= -3:
            return ("against it, hard", "no")
        if score <= -1:
            return ("leans against", "halfn")
        return ("of two minds", "neutral")

    def disposition_text(self, f: dict[str, Any]) -> tuple[str, str]:
        """A flag overrides the reading entirely."""
        if f["apa"]:
            return ("Apathetic", "neutral")
        if f["zea"]:
            return ("Zealous", "yes")
        return self.disposition_band(self.disposition(f))

    def disposition_label(self, f: dict[str, Any]) -> str:
        return self.disposition_text(f)[0]

    def outcome_text(self, f: dict[str, Any], r: dict[str, Any]) -> str:
        """A flag overrides the outcome too - and the tally follows it."""
        if f["apa"]:
            return "Apathetic - against"
        if f["zea"]:
            return "Zealous - for it"
        return {"yes": "for it, as a bloc" if self.show_weight else "for it",
                "halfy": "splits, half for" if self.show_weight else "leaning for",
                "halfn": "splits, half against" if self.show_weight else "leaning against",
                "no": "against, as a bloc" if self.show_weight else "against"}[r["band"]]

    def box(self, on: bool) -> str:
        return BOX_ON if on else BOX_OFF

    def standing_weight(self, f: dict[str, Any]) -> int:
        """What this bloc brings if the room reads true. Preview only.

        Apathy is a turnout state, so it shows the quarter straight away.
        Zeal only costs them when the read has them against, so the preview
        reads the room the same way the live vote will.
        """
        wt = clamp_int(f.get("wt"), WT_MIN, WT_MIN, WT_MAX)
        if f["apa"]:
            return max(WT_MIN, math.ceil(wt * APA_CAP))
        if f["zea"]:
            if not ZEA_ONLY_WHEN_HELD:
                return max(WT_MIN, math.ceil(wt * ZEA_CAP))
            band = self.disposition_band(self.disposition(f))[1]
            if band in ("halfn", "no"):
                return max(WT_MIN, math.ceil(wt * ZEA_CAP))
        return wt

    def render_preview(self) -> None:
        frame, cost = self.frame_suit(), self.cost_suit()
        same = frame == cost
        for i, f in enumerate(self.roster()):
            label, tag = self.disposition_text(f)
            notes = [f"serves {DOMAIN[frame]} {f['ratings'].get(frame, 1)}",
                     f"costs {DOMAIN[cost]} {f['ratings'].get(cost, 1)}",
                     f"lean {self.lean(f):+d}"]
            if same:
                notes.append("serves and spends the same domain")
            if f["apa"]:
                notes.append("apathetic -1")
            if f["zea"]:
                notes.append("zealous +1")
            lm = listen_mult(f["rel"])
            notes.append("ignores you" if lm == 0 else f"listens x{lm:g}")
            if f["hook"]:
                notes.append(f["hook"])
            self.tree.insert("", "end", iid=str(i),
                             values=(f["name"], label, self.box(f["apa"]), self.box(f["zea"]),
                                     "-", "-", fmt_num(self.standing_weight(f))
                                     if self.show_weight else 1,
                                     " | ".join(notes)),
                             tags=(tag,))

    def preview_summary(self) -> str:
        counts: dict[str, int] = {}
        for f in self.roster():
            label = self.disposition_label(f)
            counts[label] = counts.get(label, 0) + 1
        frame, cost = self.frame_suit(), self.cost_suit()
        flagged = [f["name"] for f in self.roster() if f["apa"] or f["zea"]]
        lines = [f'The room as it stands on "{self.var_title.get()}"  '
                 f'(pass difficulty {self.difficulty_T()}):', ""]
        for label in DISPOSITION_ORDER:
            if counts.get(label):
                lines.append(f"  {label}: {counts[label]}")
        if flagged:
            lines += ["", "Flagged: " + ", ".join(flagged)]
        lines += ["",
                  f"This bill serves {SYM[frame]} {DOMAIN[frame]} and spends "
                  f"{SYM[cost]} {DOMAIN[cost]}.",
                  "Lean is their rating in the served domain, or minus their rating in the "
                  "spent domain, whichever is bigger - the bill is judged on their single "
                  "strongest feeling about it, not on the difference. A flag shifts it by one "
                  "and overrides the reading outright.",
                  "Once the cards are dealt, a bloc's own card decides its mind and nothing "
                  "else does. A face card means that bloc takes the floor: they draw again for "
                  "their real vote, and every face card in a row makes the speech louder.",
                  "Speeches never change a mind. They only decide who turns out: a speech rallies "
                  "the blocs of its own suit who already agree with it, and dampens the ones who "
                  "do not. It lands on its own - no clicking. Nobody gets talked across, so the "
                  "room's direction is the cards' business and the margin is the floor's.",
                  "A zealous bloc will not vote against and an apathetic bloc will not vote for "
                  "- the flag sets the outcome. Zeal only costs turnout when it has to drag them "
                  "in; apathy turns out at a quarter every time. The weight column already shows "
                  "the quarter.",
                  "Press 'Open the meeting' to deal the cards."]
        return "\n".join(lines)

    # -------- rendering --------

    def render(self) -> None:
        self.render_bands()
        self.lbl_leverage.config(
            text=f"Arguments left: {self.leverage - self.leverage_used} of {self.leverage}"
                 + (f"   (address: {card_str(self.address)})" if self.address else ""))

        for w in self.pool_inner.winfo_children():
            w.destroy()
        if self.results:
            if self.pool:
                for p in self.pool:
                    who = "You" if p["who"] == "You" else p["who"]
                    txt = (f"{p['rank']}{SYM[p['suit']]}  {who} - "
                           f"{'for' if p['sign'] > 0 else 'against'} "
                           f"(rallies {DOMAIN[p['suit']]} "
                           f"{'for' if p['sign'] > 0 else 'against'} by {p['magnitude']})"
                           + (f"   floor x{p['chain']}" if p.get("chain", 1) > 1 else ""))
                    ttk.Label(self.pool_inner, text=txt, padding=(8, 3),
                              relief="solid", borderwidth=1).pack(side="left", padx=4, pady=2)
            else:
                ttk.Label(self.pool_inner,
                          text="Nobody has taken the floor. The room is quiet.").pack(anchor="w")
        else:
            ttk.Label(self.pool_inner,
                      text="No meeting yet - the cards are still in the deck.").pack(anchor="w")

        for item in self.tree.get_children():
            self.tree.delete(item)

        roster = self.roster()

        if self.results:
            for i, r in enumerate(self.results):
                f = roster[i]
                notes = []
                if r["floor_n"]:
                    notes.append("took the floor with " + r["floor_card"]
                                 + (f" x{r['floor_n']}" if r["floor_n"] > 1 else ""))
                if r["lean"]:
                    notes.append(f"lean {r['lean']:+d}")
                if r["momentum"]:
                    notes.append("same suit as the last draw, +1")
                if r["turnout_shift"] > 0:
                    notes.append(f"rallied +{r['turnout_shift']}")
                elif r["turnout_shift"] < 0:
                    notes.append(f"shouted down {r['turnout_shift']}")
                if f["apa"]:
                    notes.append("apathetic")
                if f["zea"]:
                    notes.append("zealous")
                if r["held_by_zeal"]:
                    notes.append("held by zeal")
                if r["turned_by_apathy"]:
                    notes.append("turned by apathy")
                notes.append(f"score {r['score']}")
                lm = listen_mult(f["rel"])
                notes.append("ignores you" if lm == 0 else f"listens x{lm:g}")
                if r["rider"]:
                    notes.append(r["rider"])
                self.tree.insert("", "end", iid=str(i),
                                 values=(f["name"], self.disposition_label(f),
                                         self.box(f["apa"]), self.box(f["zea"]),
                                         f"{r['rank']}{SYM[r['suit']]}",
                                         self.outcome_text(f, r),
                                         fmt_num(r["weight"]), " | ".join(notes)),
                                 tags=(r["band"],))
        else:
            self.render_preview()

        if not self.results:
            self.set_summary(self.preview_summary())
            self.hint.config(text="Click an apa or zea box to flag someone - the room re-reads "
                                  "at once. Press 'Open the meeting' to deal the cards.")
            return

        yes = no = 0
        for r in self.results:
            if r["band"] in ("yes", "halfy"):
                yes += r["weight"]
            else:
                no += r["weight"]

        total = yes + no
        margin = (yes - no) / total if total else 0

        if yes == no:
            verdict, note = ("Deadlocked",
                             "Cut a fresh card - high card carries the room.")
        elif yes > no:
            if margin > 0.5:
                verdict, note = ("Decisive mandate",
                                 "It passes clean. The routed side will remember it.")
            elif margin > 0.15:
                verdict, note = ("Carried",
                                 "It passes. Whoever hardened against it will make trouble later.")
            else:
                verdict, note = ("Passed by a hair",
                                 "One defection flips this next time.")
        else:
            if margin < -0.5:
                verdict, note = ("Routed",
                                 "It fails badly. The room was never with you.")
            elif margin < -0.15:
                verdict, note = ("Defeated",
                                 "The bill fails. Those who wanted it will expect something anyway.")
            else:
                verdict, note = ("Lost by a hair",
                                 "Narrow loss. Bring it back after one scene of work.")

        lines = [f"{verdict}   ({fmt_num(yes)} for, {fmt_num(no)} against)"
                 f"   [pass difficulty {self.difficulty_T()}]"]
        if self.address:
            a_suit, a_rank = self.address
            lines.append(f"Your address: {card_str(self.address)} - " + (
                "it carried, and it is a speech in the room." if a_rank in SPEECH
                else f"no speech, but you banked {self.leverage} leverage from it."))
        lines += ["", note]

        speakers = []
        for p in self.pool:
            who = "Your" if p["who"] == "You" else f"{p['who']}'s"
            speakers.append(
                f"  {who} {WORD[p['rank']]} of {SYM[p['suit']]} - "
                f"{'for' if p['sign'] > 0 else 'against'}, rallying every "
                f"{DOMAIN[p['suit']]} {'faction' if self.key == 'factions' else 'member'} "
                f"on its own side by {p['magnitude']}"
                + (f"   (floor x{p['chain']})" if p.get("chain", 1) > 1 else ""))
        if speakers:
            lines += ["", "Speeches made:"] + speakers

        for title, key in (("For it", "yes"), ("Split, half for", "halfy"),
                           ("Split, half against", "halfn"), ("Against it", "no")):
            names = [r["name"] for r in self.results if r["band"] == key]
            if names:
                lines += ["", f"{title}: " + ", ".join(names)]

        held = [r["name"] for r in self.results if r["held_by_zeal"]]
        if held:
            lines += ["", "Held by zeal: " + ", ".join(held)]

        turned = [r["name"] for r in self.results if r["turned_by_apathy"]]
        if turned:
            lines += ["", "Turned by apathy: " + ", ".join(turned)]

        hard = [r["name"] for r in self.results if r["rider"] == "will work against you"]
        if hard:
            lines += ["", "Hardened by this: " + ", ".join(hard)]

        deaf = [r["name"] for i, r in enumerate(self.results)
                if i < len(roster) and listen_mult(roster[i]["rel"]) == 0]
        if deaf:
            lines += ["", "Will not hear you at all: " + ", ".join(deaf)]

        self.set_summary("\n".join(lines))

        self.current_record = {
            "when": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "mode": "Town" if self.key == "factions" else "Council",
            "title": self.var_title.get(),
            "frame": self.frame_suit(), "cost": self.cost_suit(),
            "difficulty": self.difficulty_T(),
            "verdict": verdict, "yes": yes, "no": no, "note": note,
            "address": card_str(self.address) if self.address else "",
            "arguments": [f"You argued {'for' if p['sign'] > 0 else 'against'} {DOMAIN[p['suit']]}"
                          for p in self.pool if p["who"] == "You"],
            "rows": [{"faction": r["name"], "card": f"{r['rank']}{SYM[r['suit']]}",
                      "outcome": self.outcome_text(roster[i], r), "weight": r["weight"],
                      "notes": " | ".join(x for x in [
                          ("took the floor with " + r["floor_card"]
                           + (f" x{r['floor_n']}" if r["floor_n"] > 1 else "")) if r["floor_n"] else "",
                          f"lean {r['lean']:+d}",
                          f"score {r['score']}",
                          f"turnout {r['turnout_shift']:+d}" if r["turnout_shift"] else "",
                          r["rider"]] if x)}
                     for i, r in enumerate(self.results)],
        }

        self.hint.config(text="Speeches land on their own - every bloc whose card matches a "
                              "speech's suit is rallied if it agrees and dampened if it does not. "
                              "Tick an apa / zea box to flag someone.")

    def set_summary(self, text: str) -> None:
        self.summary.configure(state="normal")
        self.summary.delete("1.0", "end")
        self.summary.insert("1.0", text)
        self.summary.configure(state="disabled")

    def on_tree_click(self, event: tk.Event) -> None:
        if self.tree.identify_region(event.x, event.y) != "cell":
            return
        row = self.tree.identify_row(event.y)
        if not row:
            return
        i = int(row)
        col = self.tree.identify_column(event.x)
        if col == self.apa_col:
            self.toggle_flag(i, "apa")
            return
        if col == self.zea_col:
            self.toggle_flag(i, "zea")

    def on_tree_rightclick(self, event: tk.Event) -> None:
        row = self.tree.identify_row(event.y)
        if not row:
            return
        i = int(row)
        if self._ctx_menu is not None:
            self._ctx_menu.destroy()
        m = tk.Menu(self, tearoff=0)
        self._ctx_menu = m
        m.add_command(label="Toggle apathetic (quarter turnout, -1)",
                      command=lambda: self.toggle_flag(i, "apa"))
        m.add_command(label="Toggle zealous (three-quarter turnout, +1)",
                      command=lambda: self.toggle_flag(i, "zea"))
        try:
            m.tk_popup(event.x_root, event.y_root)
        finally:
            m.grab_release()

    def toggle_flag(self, i: int, which: str) -> None:
        """Apathy and zeal are exclusive - ticking one clears the other."""
        roster = self.roster()
        if i >= len(roster):
            return
        f = roster[i]
        f[which] = not f[which]
        if f[which]:
            f["zea" if which == "apa" else "apa"] = False
        self.app.save_file()
        self.recompute()
        self.render()
        self.app.status(f"{f['name']} is now "
                        f"{'apathetic' if f['apa'] else 'zealous' if f['zea'] else 'unflagged'}.")

    def record_vote(self) -> None:
        if not self.current_record:
            self.app.status("Nothing to record - open a meeting first.")
            return
        self.app.state["history"].insert(0, copy.deepcopy(self.current_record))
        self.app.refresh_history_tab()
        self.app.save_file()
        self.app.status("Vote recorded to history.")


# --------------------------------------------------------------------------
# app
# --------------------------------------------------------------------------

class QuorumApp(tk.Tk):

    def __init__(self) -> None:
        super().__init__()
        self.title("The Quorum Engine")
        self.geometry("1220x800")
        self.minsize(1000, 660)

        self.path = DEFAULT_SAVE
        self.state: dict[str, Any] = self.load_file(self.path)
        self.selected: dict[str, int | None] = {"factions": None, "council": None}
        self.row_frames: dict[str, list[tk.Frame]] = {"factions": [], "council": []}
        self.widgets_factions: list[dict[str, Any]] = []
        self.widgets_council: list[dict[str, Any]] = []
        self._clamp_job: str | None = None
        self.var_keep = tk.BooleanVar(value=bool(self.state["settings"]["keep_ladders"]))

        self.build_menu()
        self.build_ui()
        self.refresh_editors()
        self.refresh_history_tab()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # -------- persistence --------

    def sanitise(self) -> None:
        """Force every stored number back into range. Runs before every save."""
        for key in ("factions", "council"):
            for ent in self.state.get(key, []):
                ent["wt"] = clamp_int(ent.get("wt", 1), 1, WT_MIN, WT_MAX)
                ent["rel"] = clamp_int(ent.get("rel", 0), 0, REL_MIN, REL_MAX)
                ratings = ent.setdefault("ratings", {})
                for k in SUITS:
                    ratings[k] = clamp_int(ratings.get(k, 1), 1, RAT_MIN, RAT_MAX)

    def load_file(self, path: str) -> dict[str, Any]:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                if not isinstance(data, dict):
                    raise ValueError("save file is not an object")
                base = blank_state()
                base.update(data)
                base.setdefault("history", [])
                if not isinstance(base["history"], list):
                    base["history"] = []
                for key in ("factions", "council"):
                    if not isinstance(base.get(key), list):
                        base[key] = []
                    for ent in base[key]:
                        ent.setdefault("name", "Unnamed")
                        ent.setdefault("hook", "")
                        ent.setdefault("apa", False)
                        ent.setdefault("zea", False)
                        ent.setdefault("ratings", {})
                if not isinstance(base.get("settings"), dict):
                    base["settings"] = blank_state()["settings"]
                base["settings"].setdefault("keep_ladders", True)
                for k in ("town", "council"):
                    sec = base["settings"].setdefault(k, blank_state()["settings"][k])
                    # older saves called this "anchor"
                    if "difficulty" not in sec and "anchor" in sec:
                        sec["difficulty"] = sec.pop("anchor")
                    sec.setdefault("difficulty", DIFF_DEFAULT)
                    sec["difficulty"] = clamp_int(sec["difficulty"], DIFF_DEFAULT,
                                                  DIFF_MIN, DIFF_MAX)
                    sec.setdefault("bill_title", "")
                    sec.setdefault("bill_frame", "h")
                    sec.setdefault("bill_cost", "d")
                self.state = base
                self.sanitise()
                return base
            except Exception as exc:
                messagebox.showwarning("Load failed", f"Could not read save file:\n{exc}")
        return blank_state()

    def save_file(self, path: str | None = None) -> None:
        path = path or self.path
        self.sanitise()
        tmp = path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self.state, fh, indent=2, ensure_ascii=False)
            os.replace(tmp, path)
            self.path = path
            self.status(f"Saved to {os.path.basename(path)}")
        except Exception as exc:
            messagebox.showerror("Save failed", str(exc))

    def on_close(self) -> None:
        self.save_file()
        self.destroy()

    # -------- chrome --------

    def build_menu(self) -> None:
        bar = tk.Menu(self)
        filem = tk.Menu(bar, tearoff=0)
        filem.add_command(label="New town", command=self.new_town)
        filem.add_command(label="Open...", command=self.open_file)
        filem.add_command(label="Save", accelerator="Ctrl+S", command=lambda: self.save_file())
        filem.add_command(label="Save as...", command=self.save_as)
        filem.add_separator()
        filem.add_command(label="Export history as text...", command=self.export_history)
        filem.add_separator()
        filem.add_command(label="Quit", command=self.on_close)
        bar.add_cascade(label="File", menu=filem)
        self.config(menu=bar)
        self.bind("<Control-s>", lambda _e: self.save_file())

    def new_town(self) -> None:
        if messagebox.askyesno("New town", "Discard the current town, council and history?"):
            self.state = blank_state()
            self.selected = {"factions": None, "council": None}
            self.panels["town"].clear_vote()
            self.panels["council"].clear_vote()
            self.refresh_editors()
            self.refresh_history_tab()
            self.save_file()

    def open_file(self) -> None:
        path = filedialog.askopenfilename(
            filetypes=[("Quorum save", "*.json"), ("All files", "*.*")])
        if path:
            self.state = self.load_file(path)
            self.selected = {"factions": None, "council": None}
            self.panels["town"].clear_vote()
            self.panels["council"].clear_vote()
            self.refresh_editors()
            self.refresh_history_tab()

    def save_as(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".json",
                                            filetypes=[("Quorum save", "*.json")])
        if path:
            self.save_file(path)

    def export_history(self) -> None:
        if not self.state["history"]:
            messagebox.showinfo("Nothing to export", "No votes recorded yet.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".txt",
                                            filetypes=[("Text", "*.txt")])
        if not path:
            return
        lines = []
        for rec in self.state["history"]:
            lines.append("=" * 72)
            lines.append(f"{rec.get('when','')}  [{rec.get('mode','')}]  |  {rec.get('verdict','')}  "
                         f"({fmt_num(rec.get('yes',0))} for, {fmt_num(rec.get('no',0))} against)")
            lines.append(f"BILL: {rec.get('title','')}   "
                         f"[serves {DOMAIN[suit_key(rec.get('frame','h'))]}, "
                         f"spends {DOMAIN[suit_key(rec.get('cost','d'))]}, "
                         f"pass difficulty {rec_difficulty(rec)}]")
            lines.append("-" * 72)
            for row in rec.get("rows", []):
                lines.append(f"  {row['faction']:<34} {row['card']:<5} "
                             f"{row['outcome']:<26} w{fmt_num(row['weight'])}  {row['notes']}")
            if rec.get("arguments"):
                lines += ["", "Your arguments:"] + ["  " + a for a in rec["arguments"]]
            lines += ["", rec.get("note", ""), ""]
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("\n".join(lines))
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc))
            return
        self.status("History exported.")

    def status(self, text: str) -> None:
        if getattr(self, "statusbar", None) is not None:
            self.statusbar.config(text=text)

    def build_ui(self) -> None:
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=(8, 4))

        self.panels = {
            "town": VotePanel(nb, self, "factions", show_weight=True),
            "council": VotePanel(nb, self, "council", show_weight=False),
        }
        nb.add(self.panels["town"], text="  Town vote  ")
        nb.add(self.panels["council"], text="  Council vote  ")

        self.tab_fac = ttk.Frame(nb)
        self.tab_council = ttk.Frame(nb)
        self.tab_hist = ttk.Frame(nb)
        nb.add(self.tab_fac, text="  Factions  ")
        nb.add(self.tab_council, text="  Council  ")
        nb.add(self.tab_hist, text="  History  ")

        self.statusbar = ttk.Label(self, anchor="w", padding=(10, 3))
        self.statusbar.pack(fill="x", side="bottom")

        self.build_editor(self.tab_fac, "factions",
                          "Add faction", "Delete faction",
                          "\u2665 Care (food, medicine, mercy, morale)   "
                          "\u2666 Means (fuel, tools, trade, property)   "
                          "\u2663 Safety (walls, weapons, patrols, work)   "
                          "\u2660 Say (law, tradition, status, faith)\n"
                          "ratings are 1-4: how much this bloc cares about each concern.   "
                          "rel is how closely they follow YOU (-4 hostile to +4 devoted).   "
                          "wt is how many people they are - 1 to 99, never zero.   "
                          "Type any number: it is clamped the instant the variable changes.   "
                          "Click a row to select it, then Duplicate or Delete.\n"
                          "A bill's pull on a bloc is its rating in the domain the bill serves, "
                          "or minus its rating in the domain the bill spends - whichever is "
                          "bigger. It is judged on its single strongest feeling, not on the "
                          "difference.\n"
                          "A bloc's own card decides its mind. Speeches never change a mind - "
                          "they only decide who turns out, rallying their own side and dampening "
                          "the other. A speech lands automatically on every matching suit.\n"
                          "The apa / zea checkboxes live on the vote tab, next to each faction.   "
                          "Tick zealous if the bloc is committed - it will not vote against, and "
                          "comes in for the bill at three-quarter if the read had it against.   "
                          "Tick apathetic if it would shrug the whole thing off - it will not "
                          "vote for, and it turns out at a quarter, every time.   "
                          "A zealous bloc the read already had with you still votes full.")
        self.build_editor(self.tab_council, "council",
                          "Add councillor", "Delete councillor",
                          "Councillors are individuals - one vote each, weight is ignored.   "
                          "Use the notes field for personality: what they want, what they hate, "
                          "how they can be worked.   "
                          "ratings are 1-4: what this person actually cares about.   "
                          "Click a row to select it, then Duplicate or Delete.\n"
                          "The apa / zea checkboxes live on the vote tab, next to each member.   "
                          "Tick zealous if they are committed - they will not vote against.   "
                          "Tick apathetic if they would shrug the whole thing off - they will "
                          "not vote for.")
        self.build_history_tab()

    # -------- generic roster editor --------

    def build_editor(self, root: tk.Misc, key: str, add_label: str,
                     del_label: str, blurb: str) -> None:
        bar = ttk.Frame(root)
        bar.pack(fill="x", padx=6, pady=6)
        ttk.Button(bar, text=add_label,
                   command=lambda: self.add_entity(key)).pack(side="left")
        ttk.Button(bar, text="Duplicate",
                   command=lambda: self.dup_entity(key)).pack(side="left", padx=6)
        ttk.Button(bar, text=del_label,
                   command=lambda: self.del_entity(key)).pack(side="left")
        ttk.Button(bar, text="Shuffle priorities",
                   command=lambda: self.shuffle_priorities(key)).pack(side="left", padx=12)
        if key == "factions":
            ttk.Checkbutton(bar, text="keep ladders clean (one 4, 3, 2, 1)",
                            variable=self.var_keep,
                            command=self.on_keep_change).pack(side="left", padx=12)

        outer = ttk.Frame(root)
        outer.pack(fill="both", expand=True, padx=6, pady=6)
        canvas = tk.Canvas(outer, highlightthickness=0)
        sb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = ttk.Frame(canvas)
        win = canvas.create_window((0, 0), window=inner, anchor="nw")
        # let the inner grid fill the canvas width so weighted columns stretch
        canvas.bind("<Configure>", lambda e, c=canvas, w=win: c.itemconfigure(w, width=e.width))
        inner.bind("<Configure>", lambda e, c=canvas: c.configure(scrollregion=c.bbox("all")))
        canvas.bind_all("<MouseWheel>", lambda e, c=canvas: c.yview_scroll(
            int(-1 * (e.delta / 120)), "units"))

        setattr(self, f"inner_{key}", inner)
        setattr(self, f"canvas_{key}", canvas)

        blurb_lbl = ttk.Label(root, justify="left", foreground="#555",
                              text=blurb, anchor="w")
        blurb_lbl.pack(fill="x", padx=8, pady=(0, 8))
        root.bind("<Configure>",
                  lambda e, lbl=blurb_lbl: lbl.configure(
                      wraplength=max(240, e.width - 24)))

    def on_keep_change(self) -> None:
        self.state["settings"]["keep_ladders"] = bool(self.var_keep.get())
        self.save_file()

    def refresh_editors(self) -> None:
        self.refresh_editor("factions")
        self.refresh_editor("council")

    def _configure_columns(self, frame: tk.Misc) -> None:
        """Apply the one shared column spec. Used for the grid and every row."""
        for c, (field, width, stretch) in enumerate(EDITOR_COLS):
            frame.columnconfigure(c, minsize=width, weight=1 if stretch else 0)

    def refresh_editor(self, key: str) -> None:
        inner = getattr(self, f"inner_{key}")
        for w in inner.winfo_children():
            w.destroy()
        widgets: list[dict[str, Any]] = []
        frames: list[tk.Frame] = []

        self._configure_columns(inner)

        # header lives inside the same grid as the rows, so it can never drift
        for c, (field, _w, _s) in enumerate(EDITOR_COLS):
            text = EDITOR_HEAD.get(field, SYM.get(field, field))
            ttk.Label(inner, text=text, anchor="w").grid(
                row=0, column=c, sticky="we", padx=2, pady=(0, 4))

        for i, ent in enumerate(self.state[key]):
            ent["wt"] = clamp_int(ent.get("wt", 1), 1, WT_MIN, WT_MAX)
            ent["rel"] = clamp_int(ent.get("rel", 0), 0, REL_MIN, REL_MAX)

            # one strip per row, spanning every column of the same grid
            strip = tk.Frame(inner, bg=self.row_colour(key, i))
            strip.grid(row=i + 1, column=0, columnspan=len(EDITOR_COLS),
                       sticky="we", pady=1)
            self._configure_columns(strip)
            frames.append(strip)

            name = tk.StringVar(value=ent["name"])
            hook = tk.StringVar(value=ent["hook"])
            rel = tk.IntVar(value=ent["rel"])
            wt = tk.IntVar(value=ent["wt"])
            rat = {k: tk.IntVar(value=clamp_int(ent["ratings"].get(k, 1), 1, RAT_MIN, RAT_MAX))
                   for k in SUITS}

            ttk.Entry(strip, textvariable=name).grid(
                row=0, column=0, sticky="we", padx=2)
            ttk.Entry(strip, textvariable=hook).grid(
                row=0, column=1, sticky="we", padx=2)

            for ci, k in enumerate(SUITS, start=2):
                box = ttk.Spinbox(strip, from_=RAT_MIN, to=RAT_MAX, width=3, textvariable=rat[k],
                                  command=lambda i=i, k=k: self.on_rating(key, i, k))
                box.grid(row=0, column=ci, sticky="we", padx=2)
                box.bind("<KeyRelease>", lambda _e, i=i: self.on_rating_live(key, i))
                for seq in ("<FocusOut>", "<Return>", "<KP_Enter>"):
                    box.bind(seq, lambda _e, i=i, k=k: self.on_rating(key, i, k))

            rel_col = len(SUITS) + 2
            rel_box = ttk.Spinbox(strip, from_=REL_MIN, to=REL_MAX, width=3, textvariable=rel,
                                  command=lambda i=i: self.on_simple(key, i))
            rel_box.grid(row=0, column=rel_col, sticky="we", padx=2)
            rel_box.bind("<KeyRelease>", lambda _e, i=i: self.on_simple_live(key, i))
            for seq in ("<FocusOut>", "<Return>", "<KP_Enter>"):
                rel_box.bind(seq, lambda _e, i=i: self.on_simple(key, i))

            wt_box = ttk.Spinbox(strip, from_=WT_MIN, to=WT_MAX, width=3, textvariable=wt,
                                 command=lambda i=i: self.on_simple(key, i))
            wt_box.grid(row=0, column=rel_col + 1, sticky="we", padx=2)
            wt_box.bind("<KeyRelease>", lambda _e, i=i: self.on_simple_live(key, i))
            for seq in ("<FocusOut>", "<Return>", "<KP_Enter>"):
                wt_box.bind(seq, lambda _e, i=i: self.on_simple(key, i))

            widgets.append({"name": name, "hook": hook, "rel": rel, "wt": wt, "rat": rat})
            name.trace_add("write", lambda _n, _i, _m, k=key, i=i: self.on_text(k, i, "name"))
            hook.trace_add("write", lambda _n, _i, _m, k=key, i=i: self.on_text(k, i, "hook"))

            # the real safety net: a trace fires on any write to the variable,
            # whatever caused it - typing, arrows, paste, focus loss or not.
            rel.trace_add("write", lambda _n, _i, _m, k=key, i=i: self.on_simple_live(k, i))
            wt.trace_add("write", lambda _n, _i, _m, k=key, i=i: self.on_simple_live(k, i))
            for k in SUITS:
                rat[k].trace_add(
                    "write",
                    lambda _n, _i, _m, kk=key, i=i, s=k: self.on_rating_live(kk, i, s))

            strip.bind("<Button-1>", lambda _e, i=i, k=key: self.select_row(k, i))
            for child in strip.winfo_children():
                child.bind("<Button-1>",
                           lambda _e, i=i, k=key: self.select_row(k, i), add="+")

        setattr(self, f"widgets_{key}", widgets)
        self.row_frames[key] = frames
        self.schedule_clamp()

    def row_colour(self, key: str, i: int) -> str:
        return "#cfe3ff" if self.selected.get(key) == i else "#f2f2f2"

    def select_row(self, key: str, i: int) -> None:
        self.selected[key] = i
        for n, rf in enumerate(self.row_frames.get(key, [])):
            rf.configure(bg=self.row_colour(key, n))
        self.status(f"Selected row {i + 1} on the {key} tab.")

    def target_index(self, key: str) -> int | None:
        """Selected row, falling back to the last one."""
        if not self.state[key]:
            return None
        i = self.selected.get(key)
        if i is None or i >= len(self.state[key]):
            i = len(self.state[key]) - 1
        return i

    def _row_widgets(self, key: str, i: int) -> dict[str, Any] | None:
        if i >= len(self.state.get(key, [])):
            return None
        widgets = getattr(self, f"widgets_{key}", [])
        if i >= len(widgets):
            return None
        return widgets[i]

    # -------- the clamps --------

    def clamp_field(self, key: str, i: int, field: str) -> bool:
        """Clamp one numeric field. Returns True if anything changed."""
        w = self._row_widgets(key, i)
        if w is None:
            return False
        var = w[field]
        lo, hi = (REL_MIN, REL_MAX) if field == "rel" else (WT_MIN, WT_MAX)
        raw = var_int(var, None)
        if raw is None:
            return False                    # half-typed, e.g. '-' or '' - leave it
        clamped = max(lo, min(hi, raw))
        changed = False
        if clamped != raw:
            var.set(clamped)
            changed = True
            self.status(f"{field} clamped to {clamped} (was {raw}).")
        ent = self.state[key][i]
        if ent.get(field) != clamped:
            ent[field] = clamped
            changed = True
        return changed

    def clamp_rating(self, key: str, i: int, suit: str) -> bool:
        """Clamp one rating. Returns True if anything changed."""
        w = self._row_widgets(key, i)
        if w is None:
            return False
        var = w["rat"][suit]
        raw = var_int(var, None)
        if raw is None:
            return False
        clamped = max(RAT_MIN, min(RAT_MAX, raw))
        changed = False
        if clamped != raw:
            var.set(clamped)
            changed = True
            self.status(f"{DOMAIN[suit]} rating clamped to {clamped} (was {raw}).")
        ent = self.state[key][i]
        if ent["ratings"].get(suit) != clamped:
            ent["ratings"][suit] = clamped
            changed = True
        return changed

    def schedule_clamp(self) -> None:
        """Queue one idle sweep that force-fixes every box and every value."""
        if self._clamp_job is None:
            self._clamp_job = self.after_idle(self._run_clamp)

    def _run_clamp(self) -> None:
        self._clamp_job = None
        self.clamp_all()

    def clamp_all(self) -> None:
        changed = False
        for key in ("factions", "council"):
            for i in range(len(self.state.get(key, []))):
                for field in ("rel", "wt"):
                    changed |= self.clamp_field(key, i, field)
                for suit in SUITS:
                    changed |= self.clamp_rating(key, i, suit)
        if changed:
            self.save_file()
        self.refresh_panel("factions")
        self.refresh_panel("council")

    # -------- commit handlers --------

    def on_simple_live(self, key: str, i: int) -> None:
        changed = self.clamp_field(key, i, "rel")
        changed |= self.clamp_field(key, i, "wt")
        if changed:
            self.save_file()
            self.refresh_panel(key)
        self.schedule_clamp()

    def on_simple(self, key: str, i: int) -> None:
        """On commit: clamp, write the corrected value back, store it."""
        w = self._row_widgets(key, i)
        if w is None:
            return
        ent = self.state[key][i]
        rel = safe_int(w["rel"], ent.get("rel", 0), lo=REL_MIN, hi=REL_MAX)
        wt = safe_int(w["wt"], ent.get("wt", 1), lo=WT_MIN, hi=WT_MAX)
        if var_int(w["rel"], rel) != rel:
            w["rel"].set(rel)
        if var_int(w["wt"], wt) != wt:
            w["wt"].set(wt)
        ent["rel"] = rel
        ent["wt"] = wt
        self.save_file()
        self.refresh_panel(key)

    def on_rating_live(self, key: str, i: int, suit: str | None = None) -> None:
        changed = False
        for k in SUITS:
            if suit is None or k == suit:
                changed |= self.clamp_rating(key, i, k)
        if changed:
            self.save_file()
            self.refresh_panel(key)
        self.schedule_clamp()

    def on_rating(self, key: str, i: int, suit: str) -> None:
        """On commit: clamp, repair the ladder, refresh."""
        w = self._row_widgets(key, i)
        if w is None:
            return
        ent = self.state[key][i]
        before = dict(ent["ratings"])
        val = safe_int(w["rat"][suit], before.get(suit, 1), lo=RAT_MIN, hi=RAT_MAX)
        ent["ratings"][suit] = val
        if self.state["settings"]["keep_ladders"]:
            self.repair_ladder(ent)
        if var_int(w["rat"][suit], val) != val:
            w["rat"][suit].set(val)
        if ent["ratings"] != before:
            self.refresh_editor(key)
        self.save_file()
        self.refresh_panel(key)

    def on_text(self, key: str, i: int, field: str) -> None:
        if i < len(self.state.get(key, [])):
            widgets = getattr(self, f"widgets_{key}", [])
            if i < len(widgets):
                self.state[key][i][field] = widgets[i][field].get()
                self.save_file()
                self.refresh_panel(key)

    def refresh_panel(self, key: str) -> None:
        """Redraw the vote tab: recompute a live vote, otherwise re-read the room."""
        panel = getattr(self, "panels", {}).get("town" if key == "factions" else "council")
        if panel is None:
            return
        if panel.results:
            panel.recompute()
        panel.render()

    def invalidate_vote(self, key: str) -> None:
        panel = getattr(self, "panels", {}).get("town" if key == "factions" else "council")
        if panel is None:
            return
        if panel.results:
            panel.clear_vote()
            self.status("Roster changed - the open vote was cleared.")
        else:
            panel.render()

    def repair_ladder(self, ent: dict[str, Any]) -> None:
        """Force ratings to a permutation of 1-4, keeping what it can."""
        used: set[int] = set()
        out: dict[str, int | None] = {}
        for k in SUITS:
            v = ent["ratings"].get(k, 1)
            if v in used:
                v = None
            else:
                used.add(v)
            out[k] = v
        free = [x for x in (4, 3, 2, 1) if x not in used]
        for k in SUITS:
            if out[k] is None:
                out[k] = free.pop(0) if free else 1
        for k in SUITS:
            ent["ratings"][k] = out[k]

    def add_entity(self, key: str) -> None:
        label = "Faction" if key == "factions" else "Councillor"
        self.state[key].append(new_entity(f"{label} {len(self.state[key]) + 1}"))
        self.selected[key] = len(self.state[key]) - 1
        self.refresh_editor(key)
        self.invalidate_vote(key)
        self.save_file()

    def dup_entity(self, key: str) -> None:
        i = self.target_index(key)
        if i is None:
            return
        clone = copy.deepcopy(self.state[key][i])
        clone["name"] += " (copy)"
        self.state[key].insert(i + 1, clone)
        self.selected[key] = i + 1
        self.refresh_editor(key)
        self.invalidate_vote(key)
        self.save_file()

    def del_entity(self, key: str) -> None:
        i = self.target_index(key)
        if i is None:
            return
        self.state[key].pop(i)
        if not self.state[key]:
            self.selected[key] = None
        else:
            self.selected[key] = min(i, len(self.state[key]) - 1)
        self.refresh_editor(key)
        self.invalidate_vote(key)
        self.save_file()

    def shuffle_priorities(self, key: str) -> None:
        for ent in self.state[key]:
            for k, v in zip(SUITS, random.choice(PERMS)):
                ent["ratings"][k] = v
            ent["apa"] = ent["zea"] = False
        self.refresh_editor(key)
        self.invalidate_vote(key)
        self.save_file()

    # -------- history --------

    def build_history_tab(self) -> None:
        root = self.tab_hist
        bar = ttk.Frame(root)
        bar.pack(fill="x", padx=6, pady=6)
        ttk.Button(bar, text="Delete selected", command=self.delete_history).pack(side="left")
        ttk.Button(bar, text="Clear all", command=self.clear_history).pack(side="left", padx=6)
        ttk.Button(bar, text="Export as text", command=self.export_history).pack(side="left", padx=12)

        cols = ("when", "mode", "bill", "verdict", "tally")
        self.hist = ttk.Treeview(root, columns=cols, show="headings", height=12)
        for c, w in zip(cols, (130, 80, 380, 170, 130)):
            self.hist.heading(c, text=c.capitalize())
            self.hist.column(c, width=w, anchor="w")
        self.hist.pack(fill="both", expand=True, padx=6)
        self.hist.bind("<<TreeviewSelect>>", self.show_history_detail)

        ttk.Label(root, text="Detail").pack(anchor="w", padx=8, pady=(8, 0))
        self.hist_detail = tk.Text(root, height=14, wrap="word")
        self.hist_detail.pack(fill="both", expand=True, padx=6, pady=(0, 8))
        self.hist_detail.configure(state="disabled")

    def refresh_history_tab(self) -> None:
        for item in self.hist.get_children():
            self.hist.delete(item)
        for n, rec in enumerate(self.state["history"]):
            self.hist.insert("", "end", iid=str(n),
                             values=(rec.get("when", ""), rec.get("mode", ""), rec.get("title", ""),
                                     rec.get("verdict", ""),
                                     f"{fmt_num(rec.get('yes',0))} for / "
                                     f"{fmt_num(rec.get('no',0))} against"))

    def show_history_detail(self, _event: tk.Event | None = None) -> None:
        sel = self.hist.selection()
        if not sel:
            return
        rec = self.state["history"][int(sel[0])]
        lines = [f"{rec.get('when','')}  [{rec.get('mode','')}]  |  {rec.get('verdict','')}  "
                 f"({fmt_num(rec.get('yes',0))} for, {fmt_num(rec.get('no',0))} against)",
                 f"BILL: {rec.get('title','')}   "
                 f"[serves {DOMAIN[suit_key(rec.get('frame','h'))]}, "
                 f"spends {DOMAIN[suit_key(rec.get('cost','d'))]}, "
                 f"pass difficulty {rec_difficulty(rec)}]",
                 ""]
        if rec.get("address"):
            lines.append(f"Your address: {rec['address']}")
        for row in rec.get("rows", []):
            lines.append(f"  {row['faction']:<34} {row['card']:<5} "
                         f"{row['outcome']:<26} w{fmt_num(row['weight'])}  {row['notes']}")
        if rec.get("arguments"):
            lines += ["", "Your arguments:"] + ["  " + a for a in rec["arguments"]]
        lines += ["", rec.get("note", "")]
        self.hist_detail.configure(state="normal")
        self.hist_detail.delete("1.0", "end")
        self.hist_detail.insert("1.0", "\n".join(lines))
        self.hist_detail.configure(state="disabled")

    def delete_history(self) -> None:
        sel = self.hist.selection()
        if not sel:
            return
        for n in sorted((int(s) for s in sel), reverse=True):
            self.state["history"].pop(n)
        self.refresh_history_tab()
        self.save_file()

    def clear_history(self) -> None:
        if not self.state["history"]:
            return
        if messagebox.askyesno("Clear history", "Delete every recorded vote?"):
            self.state["history"] = []
            self.refresh_history_tab()
            self.save_file()


if __name__ == "__main__":
    QuorumApp().mainloop()
