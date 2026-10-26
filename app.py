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
import os
import random
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

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
SPEECH = {"J": 1, "Q": 1, "K": 2}
WORD = {"J": "jack", "Q": "queen", "K": "king"}
SWAY_CAP = 4

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

DEFAULT_SAVE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "quorum_save.json")


def new_entity(name):
    return {"name": name, "ratings": {"h": 4, "d": 3, "c": 2, "s": 1},
            "rel": 0, "wt": 1, "hook": "", "apa": False, "zea": False}


def blank_state():
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
            "town":    {"anchor": 8,
                        "bill_title": "Seal the north road and turn back outsiders",
                        "bill_frame": "c", "bill_cost": "d"},
            "council": {"anchor": 8,
                        "bill_title": "Grant the clinic the last of the diesel",
                        "bill_frame": "h", "bill_cost": "d"},
        },
    }


def card_str(card):
    return f"{card[1]}{SYM[card[0]]}"


def listen_mult(rel):
    """How closely someone follows YOUR arguments, by relationship."""
    if rel >= 3:
        return 2.0
    if rel >= 0:
        return 1.0
    if rel >= -3:
        return 0.5
    return 0.0


def apply_mult(val, mult):
    if val == 0:
        return 0
    out = int(round(abs(val) * mult))
    if mult > 0:
        out = max(1, out)
    return out if val > 0 else -out


# --------------------------------------------------------------------------
# the vote panel (used by both Town and Council)
# --------------------------------------------------------------------------

class VotePanel(ttk.Frame):

    def __init__(self, parent, app, key, show_weight):
        super().__init__(parent)
        self.app = app
        self.key = key                      # "factions" or "council"
        self.show_weight = show_weight
        self.settings = app.state["settings"][key]

        self.results = None
        self.pool = []
        self.address = None
        self.leverage = 3
        self.leverage_used = 0
        self.floors_used = set()
        self.pending_pull = None
        self.current_record = None

        self.build()
        self.render()

    # -------- ui --------

    def build(self):
        s = self.settings

        bill = ttk.LabelFrame(self, text="The bill on the table", padding=10)
        bill.pack(fill="x", padx=6, pady=6)

        ttk.Label(bill, text="Title").grid(row=0, column=0, sticky="w")
        self.var_title = tk.StringVar(value=s["bill_title"])
        ttk.Entry(bill, textvariable=self.var_title, width=58).grid(
            row=0, column=1, columnspan=5, sticky="we", padx=6)
        self.var_title.trace_add("write", lambda *_: self.on_bill_change())

        ttk.Label(bill, text="Serves").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.var_frame = tk.StringVar(value=s["bill_frame"])
        ttk.Combobox(bill, textvariable=self.var_frame, width=16, state="readonly",
                     values=[f"{SYM[k]}  {DOMAIN[k]}" for k in SUITS]).grid(
            row=1, column=1, sticky="w", padx=6, pady=(6, 0))
        self.var_frame.trace_add("write", lambda *_: self.on_bill_change())

        ttk.Label(bill, text="Spends").grid(row=1, column=2, sticky="w", pady=(6, 0))
        self.var_cost = tk.StringVar(value=s["bill_cost"])
        ttk.Combobox(bill, textvariable=self.var_cost, width=16, state="readonly",
                     values=[f"{SYM[k]}  {DOMAIN[k]}" for k in SUITS]).grid(
            row=1, column=3, sticky="w", padx=6, pady=(6, 0))
        self.var_cost.trace_add("write", lambda *_: self.on_bill_change())

        ttk.Label(bill, text="Band anchor").grid(row=1, column=4, sticky="e", pady=(6, 0))
        self.var_anchor = tk.IntVar(value=s["anchor"])
        ttk.Spinbox(bill, from_=5, to=18, width=5, textvariable=self.var_anchor,
                    command=self.on_anchor_change).grid(
            row=1, column=5, sticky="w", padx=6, pady=(6, 0))

        self.lbl_bands = ttk.Label(bill, text="", justify="left")
        self.lbl_bands.grid(row=2, column=0, columnspan=6, sticky="w", pady=(8, 0))

        ctl = ttk.Frame(self)
        ctl.pack(fill="x", padx=6)
        ttk.Button(ctl, text="Open the meeting", command=self.deal).pack(side="left")
        ttk.Button(ctl, text="Clear", command=self.clear_vote).pack(side="left", padx=6)
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

        cols = ("name", "card", "outcome", "weight", "notes")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=11)
        for c, w in zip(cols, (250, 70, 130, 70, 420)):
            self.tree.heading(c, text="faction" if c == "name" else c.capitalize())
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=6, pady=(4, 6))
        for tag, colr in (("yes", "#15803d"), ("halfy", "#4d7c0f"),
                          ("halfn", "#b45309"), ("no", "#b91c1c")):
            self.tree.tag_configure(tag, foreground=colr)
        self.tree.bind("<Button-1>", self.on_tree_click)
        self.tree.bind("<Button-3>", self.on_tree_rightclick)

        self.summary = tk.Text(self, height=10, wrap="word")
        self.summary.pack(fill="both", padx=6, pady=(0, 8))
        self.summary.configure(state="disabled")

    def roster(self):
        return self.app.state[self.key]

    def on_bill_change(self):
        self.settings["bill_title"] = self.var_title.get()
        self.settings["bill_frame"] = self.var_frame.get()[0]
        self.settings["bill_cost"] = self.var_cost.get()[0]
        self.app.save_file()
        if self.results:
            self.deal()

    def on_anchor_change(self):
        self.settings["anchor"] = int(self.var_anchor.get())
        self.app.save_file()
        self.render_bands()
        if self.results:
            self.recompute()
            self.render()

    def render_bands(self):
        T = int(self.var_anchor.get())
        f, c = self.var_frame.get()[0], self.var_cost.get()[0]
        self.lbl_bands.config(text=(
            f"Bands on score:  <= {T-5}  against, as a bloc   |   {T-4}-{T-3}  splits, half against"
            f"   |   {T-2}-{T-1}  splits, half for   |   {T}+  for it, as a bloc\n"
            f"Affinity: drawn suit served ({SYM[f]} {DOMAIN[f]}) -> +their rating and +2   |   "
            f"drawn suit spent ({SYM[c]} {DOMAIN[c]}) -> -their rating and -2   |   neither -> 0\n"
            f"Relationship does not affect the score. It only decides how hard your arguments land: "
            f"rel +3 or more x2, rel 0 to +2 x1, rel -1 to -3 x0.5, rel -4 or worse x0."
        ))

    # -------- mechanics --------

    def build_deck(self):
        deck = [(s, r) for s in SUITS for r in RANKS]
        random.shuffle(deck)
        return deck

    def deal(self):
        facs = self.roster()
        if not facs:
            messagebox.showinfo("Nothing to deal",
                                f"Add some {'factions' if self.key == 'factions' else 'councillors'} "
                                f"on the {self.key.capitalize()} tab first.")
            return

        deck = self.build_deck()
        self.address = deck.pop()
        a_rank = self.address[1]
        self.leverage = 3 if a_rank in SPEECH else min(4, max(1, VALUE[a_rank]))
        self.leverage_used = 0
        self.floors_used = set()
        self.pool = []
        self.pending_pull = None

        frame, cost = self.var_frame.get()[0], self.var_cost.get()[0]

        self.results = []
        prev = None
        for f in facs:
            card = deck.pop()
            if card[1] in SPEECH:
                self.pool.append({"suit": card[0], "rank": card[1], "who": f["name"],
                                  "speaker": len(self.results), "sign": 0})
                card = deck.pop()
            suit, rank = card
            rating = f["ratings"][suit]
            served, spent = suit == frame, suit == cost
            aff = rating if served else (-rating if spent else 0)
            res = 2 if served else (-2 if spent else 0)
            momentum = 1 if prev == suit else 0
            prev = suit
            self.results.append({
                "name": f["name"], "suit": suit, "rank": rank, "rating": rating,
                "aff": aff, "res": res, "momentum": momentum, "sway": 0,
                "base": VALUE[rank] + aff + res + momentum, "speaker": False,
            })
        for p in self.pool:
            self.results[p["speaker"]]["speaker"] = True

        self.recompute()
        self.render()
        self.app.status(f"{'Town meeting' if self.key == 'factions' else 'Council session'} opened.")

    def clear_vote(self):
        self.results = None
        self.pool = []
        self.pending_pull = None
        self.address = None
        self.current_record = None
        self.render()

    def recompute(self):
        T = int(self.var_anchor.get())
        roster = self.roster()

        for p in self.pool:
            if not p.get("fixed"):
                p["sign"] = 1 if self.results[p["speaker"]]["base"] >= T else -1

        for i, r in enumerate(self.results):
            s = 0
            for p in self.pool:
                if p["suit"] != r["suit"] or p["speaker"] == i:
                    continue
                val = SPEECH[p["rank"]]
                if p["who"] == "You":
                    val = apply_mult(val, listen_mult(roster[i]["rel"]))
                s += p["sign"] * val
            r["pool_sway"] = max(-SWAY_CAP, min(SWAY_CAP, s))

        for i, r in enumerate(self.results):
            f = roster[i]
            r["flag_nudge"] = -1 if f["apa"] else (1 if f["zea"] else 0)
            r["total_sway"] = r["pool_sway"] + r["flag_nudge"] + r.get("sway", 0)
            r["score"] = r["base"] + r["total_sway"]

            if r["score"] >= T:
                r["band"], r["w"] = "yes", 1.0
            elif r["score"] >= T - 2:
                r["band"], r["w"] = "halfy", 0.5
            elif r["score"] >= T - 4:
                r["band"], r["w"] = "halfn", 0.5
            else:
                r["band"], r["w"] = "no", 1.0

            base_w = f["wt"] if self.show_weight else 1
            mult = 0.25 if f["apa"] else (0.75 if f["zea"] else r["w"])
            r["weight"] = max(1, round(base_w * mult))
            r["rider"] = ("will do more than asked" if (r["band"] == "yes" and r["score"] >= T + 4)
                          else "will work against you" if (r["band"] == "no" and r["score"] <= T - 5)
                          else "")

    # -------- arguments --------

    def make_argument(self):
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

        def confirm():
            suit = suit_var.get()
            if suit in self.floors_used:
                err.config(text=f"You have already argued {DOMAIN[suit]} here tonight.")
                return
            sign = 1 if dir_var.get() == "for" else -1
            self.pool.append({"suit": suit, "rank": "K", "who": "You",
                              "speaker": -1, "sign": sign, "fixed": True})
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
        dlg.bind("<Return>", lambda e: confirm())
        dlg.bind("<Escape>", lambda e: dlg.destroy())

        dlg.update_idletasks()
        dlg.geometry(f"+{self.app.winfo_rootx() + 200}+{self.app.winfo_rooty() + 160}")
        dlg.grab_set()

    # -------- rendering --------

    def render(self):
        self.render_bands()
        self.lbl_leverage.config(
            text=f"Arguments left: {self.leverage - self.leverage_used} of {self.leverage}"
                 + (f"   (address: {card_str(self.address)})" if self.address else ""))

        for w in self.pool_inner.winfo_children():
            w.destroy()
        if self.results:
            if self.pool:
                for i, p in enumerate(self.pool):
                    who = "You" if p["who"] == "You" else p["who"]
                    txt = (f"{p['rank']}{SYM[p['suit']]}  {who} - "
                           f"{'for' if p['sign'] > 0 else 'against'} "
                           f"(sways all {DOMAIN[p['suit']]} by {p['sign'] * SPEECH[p['rank']]:+d})")
                    ttk.Button(self.pool_inner, text=txt,
                               command=lambda i=i: self.select_pool(i)).pack(side="left", padx=4, pady=2)
            else:
                ttk.Label(self.pool_inner,
                          text="Nobody has taken the floor. The room is quiet.").pack(anchor="w")

        for item in self.tree.get_children():
            self.tree.delete(item)

        if self.results:
            roster = self.roster()
            for i, r in enumerate(self.results):
                f = roster[i]
                label = {"yes": "for it, as a bloc" if self.show_weight else "for it",
                         "halfy": "splits, half for" if self.show_weight else "leaning for",
                         "halfn": "splits, half against" if self.show_weight else "leaning against",
                         "no": "against, as a bloc" if self.show_weight else "against"}[r["band"]]
                notes = []
                if r["aff"]:
                    notes.append(f"affinity {r['aff']:+d}")
                if r["res"]:
                    notes.append(f"resonance {r['res']:+d}")
                if r["total_sway"]:
                    notes.append(f"sway {r['total_sway']:+d}")
                if f["apa"]:
                    notes.append("flagged apathetic")
                if f["zea"]:
                    notes.append("flagged zealous")
                notes.append(f"score {r['score']}")
                lm = listen_mult(f["rel"])
                notes.append("ignores you" if lm == 0 else f"listens x{lm:g}")
                if r["rider"]:
                    notes.append(r["rider"])
                self.tree.insert("", "end", iid=str(i),
                                 values=(f["name"], f"{r['rank']}{SYM[r['suit']]}", label,
                                         r["weight"], " | ".join(notes)),
                                 tags=(r["band"],))

        if not self.results:
            self.set_summary("Write a bill, then press 'Open the meeting'.")
            self.hint.config(text="")
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

        lines = [f"{verdict}   ({yes} for, {no} against)"]
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
                f"{'for' if p['sign'] > 0 else 'against'}, swinging every "
                f"{DOMAIN[p['suit']]} {'faction' if self.key == 'factions' else 'member'} "
                f"by {p['sign'] * SPEECH[p['rank']]:+d}")
        if speakers:
            lines += ["", "Speeches made:"] + speakers

        for title, key in (("For it", "yes"), ("Split, half for", "halfy"),
                           ("Split, half against", "halfn"), ("Against it", "no")):
            names = [r["name"] for r in self.results if r["band"] == key]
            if names:
                lines += ["", f"{title}: " + ", ".join(names)]

        hard = [r["name"] for r in self.results if r["rider"] == "will work against you"]
        if hard:
            lines += ["", "Hardened by this: " + ", ".join(hard)]

        deaf = [r["name"] for r in self.results
                if listen_mult(self.roster()[self.results.index(r)]["rel"]) == 0]
        if deaf:
            lines += ["", "Will not hear you at all: " + ", ".join(deaf)]

        self.set_summary("\n".join(lines))

        self.current_record = {
            "when": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "mode": "Town" if self.key == "factions" else "Council",
            "title": self.var_title.get(),
            "frame": self.var_frame.get()[0], "cost": self.var_cost.get()[0],
            "anchor": int(self.var_anchor.get()),
            "verdict": verdict, "yes": yes, "no": no, "note": note,
            "address": card_str(self.address) if self.address else "",
            "arguments": [f"You argued {'for' if p['sign'] > 0 else 'against'} {DOMAIN[p['suit']]}"
                          for p in self.pool if p["who"] == "You"],
            "rows": [{"faction": r["name"], "card": f"{r['rank']}{SYM[r['suit']]}",
                      "outcome": r["band"], "weight": r["weight"],
                      "notes": " | ".join(x for x in [f"score {r['score']}", r["rider"]] if x)}
                     for r in self.results],
        }

        self.hint.config(text=("Pull the selected speech - click someone to land it there."
                               if self.pending_pull is not None
                               else "Click a speech above to pull it and aim it at one person."))

    def set_summary(self, text):
        self.summary.configure(state="normal")
        self.summary.delete("1.0", "end")
        self.summary.insert("1.0", text)
        self.summary.configure(state="disabled")

    def select_pool(self, i):
        self.pending_pull = None if self.pending_pull == i else i
        self.render()

    def on_tree_click(self, event):
        row = self.tree.identify_row(event.y)
        if row and self.pending_pull is not None:
            self.apply_pull(int(row))

    def on_tree_rightclick(self, event):
        row = self.tree.identify_row(event.y)
        if not row:
            return
        i = int(row)
        m = tk.Menu(self, tearoff=0)
        m.add_command(label="Toggle apathetic (quarter turnout, -1)",
                      command=lambda: self.toggle_flag(i, "apa"))
        m.add_command(label="Toggle zealous (three-quarter turnout, +1)",
                      command=lambda: self.toggle_flag(i, "zea"))
        m.tk_popup(event.x_root, event.y_root)

    def toggle_flag(self, i, which):
        f = self.roster()[i]
        f[which] = not f[which]
        if f[which]:
            f["zea" if which == "apa" else "apa"] = False
        self.app.save_file()
        self.recompute()
        self.render()

    def apply_pull(self, target):
        p = self.pool[self.pending_pull]
        r = self.results[target]
        val = SPEECH[p["rank"]]
        if p["who"] == "You":
            val = apply_mult(val, listen_mult(self.roster()[target]["rel"]))
        r["sway"] = max(-5, min(5, r.get("sway", 0) + p["sign"] * val))
        del self.pool[self.pending_pull]
        self.pending_pull = None
        self.recompute()
        self.render()

    def record_vote(self):
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

    def __init__(self):
        super().__init__()
        self.title("The Quorum Engine")
        self.geometry("1220x800")
        self.minsize(1000, 660)

        self.path = DEFAULT_SAVE
        self.state = self.load_file(self.path)

        self.build_menu()
        self.build_ui()
        self.refresh_editors()
        self.refresh_history_tab()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # -------- persistence --------

    def load_file(self, path):
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                base = blank_state()
                base.update(data)
                for k in ("town", "council"):
                    base["settings"].setdefault(k, blank_state()["settings"][k])
                return base
            except Exception as exc:
                messagebox.showwarning("Load failed", f"Could not read save file:\n{exc}")
        return blank_state()

    def save_file(self, path=None):
        path = path or self.path
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(self.state, fh, indent=2, ensure_ascii=False)
            self.path = path
            self.status(f"Saved to {os.path.basename(path)}")
        except Exception as exc:
            messagebox.showerror("Save failed", str(exc))

    def on_close(self):
        self.save_file()
        self.destroy()

    # -------- chrome --------

    def build_menu(self):
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
        self.bind("<Control-s>", lambda e: self.save_file())

    def new_town(self):
        if messagebox.askyesno("New town", "Discard the current town, council and history?"):
            self.state = blank_state()
            self.panels["town"].clear_vote()
            self.panels["council"].clear_vote()
            self.refresh_editors()
            self.refresh_history_tab()
            self.save_file()

    def open_file(self):
        path = filedialog.askopenfilename(
            filetypes=[("Quorum save", "*.json"), ("All files", "*.*")])
        if path:
            self.state = self.load_file(path)
            self.panels["town"].clear_vote()
            self.panels["council"].clear_vote()
            self.refresh_editors()
            self.refresh_history_tab()

    def save_as(self):
        path = filedialog.asksaveasfilename(defaultextension=".json",
                                            filetypes=[("Quorum save", "*.json")])
        if path:
            self.save_file(path)

    def export_history(self):
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
            lines.append(f"{rec['when']}  [{rec.get('mode','')}]  |  {rec['verdict']}  "
                         f"({rec['yes']} for, {rec['no']} against)")
            lines.append(f"BILL: {rec['title']}   [serves {DOMAIN[rec['frame']]}, "
                         f"spends {DOMAIN[rec['cost']]}, anchor {rec['anchor']}]")
            lines.append("-" * 72)
            for row in rec["rows"]:
                lines.append(f"  {row['faction']:<34} {row['card']:<5} "
                             f"{row['outcome']:<12} w{row['weight']}  {row['notes']}")
            if rec.get("arguments"):
                lines += ["", "Your arguments:"] + ["  " + a for a in rec["arguments"]]
            lines += ["", rec["note"], ""]
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))
        self.status("History exported.")

    def status(self, text):
        self.statusbar.config(text=text)

    def build_ui(self):
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
                          "wt is how many people they are.   "
                          "Right-click a row on the vote tab to flag apathetic or zealous.")
        self.build_editor(self.tab_council, "council",
                          "Add councillor", "Delete councillor",
                          "Councillors are individuals - one vote each, weight is ignored.   "
                          "Use the notes field for personality: what they want, what they hate, "
                          "how they can be worked.   "
                          "ratings are 1-4: what this person actually cares about.\n"
                          "Right-click a row on the vote tab to flag apathetic or zealous.")
        self.build_history_tab()

    # -------- generic roster editor --------

    def build_editor(self, root, key, add_label, del_label, blurb):
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
            self.var_keep = tk.BooleanVar(value=self.state["settings"]["keep_ladders"])
            ttk.Checkbutton(bar, text="keep ladders clean (one 4, 3, 2, 1)",
                            variable=self.var_keep,
                            command=self.on_keep_change).pack(side="left", padx=12)

        head = ttk.Frame(root)
        head.pack(fill="x", padx=6)
        cols = (("name", 30), ("notes", 34)) + tuple((SYM[k], 4) for k in SUITS) + \
               (("rel", 5), ("wt", 5))
        for text, w in cols:
            ttk.Label(head, text=text, width=w, anchor="w").pack(side="left", padx=2)

        outer = ttk.Frame(root)
        outer.pack(fill="both", expand=True, padx=6, pady=6)
        canvas = tk.Canvas(outer, highlightthickness=0)
        sb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        inner = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        setattr(self, f"inner_{key}", inner)
        setattr(self, f"canvas_{key}", canvas)

        ttk.Label(root, justify="left", foreground="#555",
                  text=blurb).pack(fill="x", padx=8, pady=(0, 8))

    def on_keep_change(self):
        self.state["settings"]["keep_ladders"] = bool(self.var_keep.get())
        self.save_file()

    def refresh_editors(self):
        self.refresh_editor("factions")
        self.refresh_editor("council")

    def refresh_editor(self, key):
        inner = getattr(self, f"inner_{key}")
        for w in inner.winfo_children():
            w.destroy()
        widgets = []

        for i, ent in enumerate(self.state[key]):
            row = ttk.Frame(inner)
            row.pack(fill="x", pady=1)

            name = tk.StringVar(value=ent["name"])
            hook = tk.StringVar(value=ent["hook"])
            rel = tk.IntVar(value=ent["rel"])
            wt = tk.IntVar(value=ent["wt"])
            rat = {k: tk.IntVar(value=ent["ratings"][k]) for k in SUITS}

            ttk.Entry(row, textvariable=name, width=30).pack(side="left", padx=2)
            ttk.Entry(row, textvariable=hook, width=34).pack(side="left", padx=2)
            for k in SUITS:
                ttk.Spinbox(row, from_=1, to=4, width=3, textvariable=rat[k],
                            command=lambda i=i, k=k: self.on_rating(key, i, k)).pack(side="left", padx=2)
            ttk.Spinbox(row, from_=-4, to=4, width=4, textvariable=rel,
                        command=lambda i=i: self.on_simple(key, i)).pack(side="left", padx=2)
            ttk.Spinbox(row, from_=1, to=9, width=4, textvariable=wt,
                        command=lambda i=i: self.on_simple(key, i)).pack(side="left", padx=2)

            widgets.append({"name": name, "hook": hook, "rel": rel, "wt": wt, "rat": rat})
            name.trace_add("write", lambda *_, i=i: self.on_text(key, i, "name"))
            hook.trace_add("write", lambda *_, i=i: self.on_text(key, i, "hook"))

        setattr(self, f"widgets_{key}", widgets)

    def on_text(self, key, i, field):
        self.state[key][i][field] = getattr(self, f"widgets_{key}")[i][field].get()
        self.save_file()

    def on_simple(self, key, i):
        w = getattr(self, f"widgets_{key}")[i]
        self.state[key][i]["rel"] = int(w["rel"].get())
        self.state[key][i]["wt"] = int(w["wt"].get())
        self.save_file()

    def on_rating(self, key, i, suit):
        val = max(1, min(4, int(getattr(self, f"widgets_{key}")[i]["rat"][suit].get())))
        ent = self.state[key][i]
        old = ent["ratings"][suit]
        if old == val:
            return
        if self.state["settings"]["keep_ladders"]:
            holder = next((k for k in SUITS if ent["ratings"][k] == val), None)
            ent["ratings"][suit] = val
            if holder and holder != suit:
                ent["ratings"][holder] = old
        else:
            ent["ratings"][suit] = val
        self.refresh_editor(key)
        self.save_file()

    def add_entity(self, key):
        label = "Faction" if key == "factions" else "Councillor"
        self.state[key].append(new_entity(f"{label} {len(self.state[key]) + 1}"))
        self.refresh_editor(key)
        self.save_file()

    def dup_entity(self, key):
        if self.state[key]:
            self.state[key].append(copy.deepcopy(self.state[key][-1]))
            self.state[key][-1]["name"] += " (copy)"
            self.refresh_editor(key)
            self.save_file()

    def del_entity(self, key):
        if self.state[key]:
            self.state[key].pop()
            self.refresh_editor(key)
            self.save_file()

    def shuffle_priorities(self, key):
        for ent in self.state[key]:
            for k, v in zip(SUITS, random.choice(PERMS)):
                ent["ratings"][k] = v
            ent["apa"] = ent["zea"] = False
        self.refresh_editor(key)
        self.save_file()

    # -------- history --------

    def build_history_tab(self):
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

    def refresh_history_tab(self):
        for item in self.hist.get_children():
            self.hist.delete(item)
        for n, rec in enumerate(self.state["history"]):
            self.hist.insert("", "end", iid=str(n),
                             values=(rec["when"], rec.get("mode", ""), rec["title"],
                                     rec["verdict"], f"{rec['yes']} for / {rec['no']} against"))

    def show_history_detail(self, _event=None):
        sel = self.hist.selection()
        if not sel:
            return
        rec = self.state["history"][int(sel[0])]
        lines = [rec["when"], f"[{rec.get('mode','')}]",
                 f"{rec['verdict']}  ({rec['yes']} for, {rec['no']} against)",
                 f"BILL: {rec['title']}",
                 f"serves {DOMAIN[rec['frame']]}, spends {DOMAIN[rec['cost']]}, anchor {rec['anchor']}",
                 f"your address: {rec.get('address', '-')}", "", "-" * 60]
        for row in rec["rows"]:
            lines.append(f"{row['faction']:<34} {row['card']:<5} {row['outcome']:<12} "
                         f"w{row['weight']}   {row['notes']}")
        if rec.get("arguments"):
            lines += ["", "Your arguments:"] + ["  " + a for a in rec["arguments"]]
        lines += ["", rec["note"]]
        self.hist_detail.configure(state="normal")
        self.hist_detail.delete("1.0", "end")
        self.hist_detail.insert("1.0", "\n".join(lines))
        self.hist_detail.configure(state="disabled")

    def delete_history(self):
        sel = self.hist.selection()
        if sel:
            for n in sorted((int(s) for s in sel), reverse=True):
                self.state["history"].pop(n)
            self.refresh_history_tab()
            self.save_file()

    def clear_history(self):
        if messagebox.askyesno("Clear history", "Delete every recorded vote?"):
            self.state["history"] = []
            self.refresh_history_tab()
            self.save_file()


if __name__ == "__main__":
    QuorumApp().mainloop()
