"""A 34-test battery for every bot, on the unofficial mini simulator (no-limit hold'em).

    python3.12 tools/bot_tests.py run --out eval-results/bot-tests/raw.json.gz [--extra ../../zoo/claude_exploiter_1]
    python3.12 tools/bot_tests.py report eval-results/bot-tests/raw.json.gz > eval-results/bot-tests/README.md

How the tests work (details per test in the report):

* Probe tests put a bot into hand-built spots. Each spot is played on the simulator's real
  `Table`, with a rigged deck and scripted opponents ("puppets"), so the bot sees exactly the
  GameState it would see in play. Earlier actions of the bot in that hand can be forced (it
  is still asked, so its memory updates, but the scripted action is played). The decision
  at the probe point is the bot's own and is scored against exact equity, pot odds, MDF,
  ICM, or a solver.
* The "solver" is the exact heads-up push/fold equilibrium (fictitious play on a 169x169
  preflop equity matrix), the only no-limit subgame we can solve here. Exploitability,
  GTO deviation and regret are measured in that subgame; nothing here solves 8-max play.
* Simulator tests play whole tables: fixed fields, memory ablation (the bot's memory wiped
  every decision), self-play, heads-up matches and an out-of-sample league with varied rules.
* Code tests: tools/fuzz.py and a static scan for code that could read hidden information.

All spots are hold'em, 8 seats, blinds 10/20, so 1 big blind = 20 chips.
"""

import argparse
import gzip
import itertools
import json
import math
import os
import random
import re
import subprocess
import sys
import time
import types
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "devtest"))
import mini_sim  # noqa: E402
from mini_sim import DECK, hand_rank  # noqa: E402
from poker_agent_sdk import Action, icm  # noqa: E402

BB = 20
RANKS = "23456789TJQKA"
SUITS = "cdhs"
POS = ["BTN", "SB", "BB", "UTG", "UTG1", "MP", "HJ", "CO"]  # offset from the button
CACHE = ROOT / "eval-results" / "bot-tests" / "cache"


# ====================================================================== hand classes
def make_classes():
    names, combos = [], []
    for hi in range(12, -1, -1):
        for lo in range(hi, -1, -1):
            r1, r2 = RANKS[hi], RANKS[lo]
            if hi == lo:
                names.append(r1 + r2)
                combos.append([(r1 + a, r2 + b) for a, b in itertools.combinations(SUITS, 2)])
            else:
                names.append(r1 + r2 + "s")
                combos.append([(r1 + s, r2 + s) for s in SUITS])
                names.append(r1 + r2 + "o")
                combos.append([(r1 + a, r2 + b) for a in SUITS for b in SUITS if a != b])
    return names, combos


NAMES, COMBOS = make_classes()
W = [len(c) for c in COMBOS]  # 6 / 4 / 12
WT = sum(W)  # 1326


def _eq_row(args):
    i, samples, seed = args
    rng = random.Random(f"{seed}:{i}")
    row = []
    for j in range(len(NAMES)):
        if j < i:
            row.append(None)
            continue
        score = 0.0
        for _ in range(samples):
            while True:
                a, b = rng.choice(COMBOS[i]), rng.choice(COMBOS[j])
                if not set(a) & set(b):
                    break
            rest = [c for c in DECK if c not in a and c not in b]
            board = tuple(rng.sample(rest, 5))
            ra, rb = hand_rank(a + board), hand_rank(b + board)
            score += 1.0 if ra > rb else 0.5 if ra == rb else 0.0
        row.append(score / samples)
    return i, row


def preflop_matrix(workers, samples=1500):
    """eq[i][j]: equity of class i against class j (Monte Carlo, cached on disk)."""
    path = CACHE / f"preflop_eq_{samples}.json.gz"
    if path.exists():
        return json.loads(gzip.decompress(path.read_bytes()))
    n = len(NAMES)
    eq = [[0.5] * n for _ in range(n)]
    with ProcessPoolExecutor(workers) as pool:
        for i, row in pool.map(_eq_row, [(i, samples, "pf") for i in range(n)]):
            for j in range(i, n):
                eq[i][j] = row[j]
                eq[j][i] = 1 - row[j]
    for i in range(n):
        eq[i][i] = 0.5
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(json.dumps(eq).encode(), mtime=0))
    return eq


def rankings(eq):
    """Class order for reference ranges: equity against a top-25% range (itself ranked by
    equity against a random hand). Puts pairs and suited broadways ahead of offsuit junk."""
    n = len(NAMES)
    vs_rand = [sum(W[j] * eq[i][j] for j in range(n)) / WT for i in range(n)]
    order0 = sorted(range(n), key=lambda i: -vs_rand[i])
    top = top_classes(order0, 0.25)
    tw = sum(W[j] for j in top)
    vs_top = [sum(W[j] * eq[i][j] for j in top) / tw for i in range(n)]
    return sorted(range(n), key=lambda i: -vs_top[i])


def top_classes(order, frac):
    out, acc = [], 0
    for i in order:
        if acc >= frac * WT:
            break
        out.append(i)
        acc += W[i]
    return out


def range_combos(order, frac):
    return [c for i in top_classes(order, frac) for c in COMBOS[i]]


# ====================================================================== push/fold solver
def pf_value(p, c, eq, S):
    """SB's expected result in bb for push frequencies p[i] and call frequencies c[j]."""
    n = len(p)
    cw = sum(W[j] * c[j] for j in range(n))
    v = 0.0
    for i in range(n):
        if p[i] == 0:
            v -= W[i] * 0.5
            continue
        called = sum(W[j] * c[j] * S * (2 * eq[i][j] - 1) for j in range(n) if c[j])
        push = ((WT - cw) * 1.0 + called) / WT
        v += W[i] * ((1 - p[i]) * -0.5 + p[i] * push)
    return v / WT


def br_call(p, eq, S):
    n = len(p)
    out = []
    pw = sum(W[i] * p[i] for i in range(n))
    for j in range(n):
        if pw == 0:
            out.append(0.0)
            continue
        ev = sum(W[i] * p[i] * S * (2 * eq[j][i] - 1) for i in range(n) if p[i]) / pw
        out.append(1.0 if ev > -1 else 0.0)
    return out


def br_push(c, eq, S):
    n = len(c)
    cw = sum(W[j] * c[j] for j in range(n))
    out = []
    for i in range(n):
        called = sum(W[j] * c[j] * S * (2 * eq[i][j] - 1) for j in range(n) if c[j])
        out.append(1.0 if ((WT - cw) + called) / WT > -0.5 else 0.0)
    return out


def solve_pushfold(eq, S, iters=600):
    n = len(eq)
    p, c = [1.0] * n, [0.5] * n
    for t in range(1, iters + 1):
        bc, bp = br_call(p, eq, S), br_push(c, eq, S)
        p = [p[i] + (bp[i] - p[i]) / (t + 1) for i in range(n)]
        c = [c[j] + (bc[j] - c[j]) / (t + 1) for j in range(n)]
    return p, c, pf_value(p, c, eq, S)


def nash_tables(eq, depths, workers):
    path = CACHE / "pushfold_nash.json"
    if path.exists():
        data = json.loads(path.read_text())
        if all(str(d) in data for d in depths):
            return {int(k): v for k, v in data.items()}
    with ProcessPoolExecutor(workers) as pool:
        res = list(pool.map(_solve, [(eq, d) for d in depths]))
    data = {d: dict(push=p, call=c, value=v) for d, (p, c, v) in zip(depths, res)}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))
    return data


def _solve(args):
    return solve_pushfold(*args)


# ====================================================================== equity helpers
def eq_river(hole, board, vcombos):
    dead = set(hole) | set(board)
    hr = hand_rank(tuple(hole) + tuple(board))
    s = n = 0
    for c in vcombos:
        if c[0] in dead or c[1] in dead:
            continue
        vr = hand_rank(tuple(c) + tuple(board))
        s += 1.0 if hr > vr else 0.5 if hr == vr else 0.0
        n += 1
    return s / n


def eq_mc(hole, board, vcombos, samples, rng):
    dead = set(hole) | set(board)
    valid = [c for c in vcombos if c[0] not in dead and c[1] not in dead]
    rest = [c for c in DECK if c not in dead]
    need = 5 - len(board)
    s = 0.0
    for _ in range(samples):
        v = rng.choice(valid)
        pool = [c for c in rest if c not in v]
        run = tuple(board) + tuple(rng.sample(pool, need))
        hr, vr = hand_rank(tuple(hole) + run), hand_rank(tuple(v) + run)
        s += 1.0 if hr > vr else 0.5 if hr == vr else 0.0
    return s / samples


def _eq_job(args):
    kind, hole, board, vcombos, samples, seed = args
    if kind == "river":
        return eq_river(hole, board, vcombos)
    return eq_mc(hole, board, vcombos, samples, random.Random(seed))


# ====================================================================== probe engine
class Rig(random.Random):
    """Shuffles the deck so the simulator deals `plan` in order (it pops from the end)."""
    plan = None

    def shuffle(self, x):
        if self.plan is None or len(x) < 36:
            return super().shuffle(x)
        planned = set(self.plan)
        rest = [c for c in x if c not in planned]
        super().shuffle(rest)
        x[:] = rest + list(reversed(self.plan))


def street_of(state):
    return {0: 0, 3: 1, 4: 2, 5: 3}.get(len(state.board), 0)


def spec_action(spec, state):
    can = state.can
    if isinstance(spec, (list, tuple)):
        kind, value = spec
    else:
        kind, value = spec, None
    if kind in ("fold", "checkfold"):
        return Action.check() if can("check") else Action.fold()
    if kind in ("check", "checkcall") and can("check"):
        return Action.check()
    if kind in ("call", "checkcall", "check"):
        if kind == "check":
            return Action.fold()
        return Action.call() if can("call") else Action.check()
    r = can("raise")
    if r is None:
        return Action.call() if can("call") else Action.check()
    me = state.seats[state.seat].bet
    if kind == "allin":
        amount = r.max_amount
    elif kind == "to":
        amount = value
    elif kind == "bet":  # value * pot, on top of a call
        amount = me + state.to_call + value * (state.pot + state.to_call)
    else:
        raise ValueError(kind)
    return Action.raise_to(int(max(r.min_amount, min(r.max_amount, amount))))


class Puppet:
    def __init__(self, script=None, default="checkfold", fn=None):
        self.script = {int(k): list(v) for k, v in (script or {}).items()}
        self.default, self.fn = default, fn

    def act(self, state, memory):
        if self.fn:
            return self.fn(state), memory
        q = self.script.get(street_of(state))
        return spec_action(q.pop(0) if q else self.default, state), memory


class Hero:
    """The bot under test. Forced actions are played in order (the bot is still asked, so its
    memory sees the hand); the first unforced decision on `probe` street is recorded."""

    def __init__(self, bot, forced=None, probe=None):
        self.bot = bot
        self.forced = {int(k): list(v) for k, v in (forced or {}).items()}
        self.probe = probe
        self.result = None
        self.decisions = []

    def act(self, state, memory):
        action, memory = self.bot.act(state, memory)
        st = street_of(state)
        q = self.forced.get(st)
        if q:
            return spec_action(q.pop(0), state), memory
        if self.probe is not None and self.result is None and st == self.probe:
            self.result = (state, action)
        if self.probe is None:
            self.decisions.append((state, action))
        return action, memory


def classify(state, action):
    if not isinstance(action, Action):
        return {"k": "illegal"}
    legal = state.can(action.kind)
    if legal is None:
        return {"k": "illegal"}
    out = {"k": action.kind}
    if action.kind == "raise":
        try:
            amount = math.floor(action.amount)
        except Exception:
            return {"k": "illegal"}
        if not legal.min_amount <= amount <= legal.max_amount:
            return {"k": "illegal"}
        me = state.seats[state.seat].bet
        out["a"] = amount
        out["f"] = round((amount - me - state.to_call) / max(1, state.pot + state.to_call), 3)
        out["allin"] = amount >= legal.max_amount
    return out


def rules_ns(payouts=(50, 30, 20)):
    return types.SimpleNamespace(stack=2000, decision_ms=1, bank_ms=100, hand_cap=10**6,
                                 hands_per_level=10**6, payouts=tuple(payouts), variant="holdem",
                                 random_payouts=False)


def deal_plan(alive, holes, board):
    return [c for s in sorted(alive) for c in holes[s]] + list(board)


def run_spot(bot, sc, memory=None):
    """Play one scripted hand; return (classified decision or None, hero memory after)."""
    n = 8
    hero_seat = sc["hero"]
    hero = Hero(bot, sc.get("forced"), sc["probe"])
    agents = []
    for s in range(n):
        if s == hero_seat:
            agents.append(hero)
        else:
            p = sc.get("puppets", {}).get(str(s)) or sc.get("puppets", {}).get(s) or {}
            agents.append(Puppet(p.get("script"), p.get("default", "checkfold")))
    rng = Rig(sc["id"])
    table = mini_sim.Table(agents, rng, rules_ns(sc.get("payouts", (50, 30, 20))), sc.get("tid", "probe"))
    table.button = sc["button"]
    table.stacks = list(sc["stacks"])
    table.bust_order = list(sc.get("bust", []))
    table.bank = [1e12] * n
    if memory is not None:
        table.memory[hero_seat] = memory
    alive = [s for s in range(n) if table.stacks[s] > 0]
    holes = {int(k): tuple(v) for k, v in sc["holes"].items()}
    rng.plan = deal_plan(alive, holes, sc["board"])
    # Bots that draw from the global `random` get the same draws in a spot and in its
    # transformed copies (consistency, leakage), which carry the base spot's `rseed`.
    random.seed(sc.get("rseed", sc["id"]))
    if hasattr(bot, "reseed"):
        bot.reseed(sc.get("rseed", sc["id"]))
    table.play_hand(sc.get("hand", 1))
    if hero.result is None:
        return None, table.memory[hero_seat]
    return classify(*hero.result), table.memory[hero_seat]


# ====================================================================== scenario building
def fill_holes(rng, alive, given, board_given, ranges):
    """Cards for every alive seat: given ones, else drawn from that seat's range (or random)."""
    used = set(c for v in given.values() for c in v) | set(board_given)
    holes = {s: tuple(v) for s, v in given.items()}
    for s in alive:
        if s in holes:
            continue
        rngs = ranges.get(s)
        while True:
            if rngs:
                h = rng.choice(rngs)
            else:
                h = tuple(rng.sample(DECK, 2))
            if not set(h) & used:
                break
        holes[s] = tuple(h)
        used |= set(h)
    return holes, used


def complete_board(rng, used, board):
    rest = [c for c in DECK if c not in used]
    return list(board) + rng.sample(rest, 5 - len(board))


def spot(sid, hero, button, stacks, holes, board, puppets, forced, probe, **kw):
    return dict(id=sid, hero=hero, button=button, stacks=stacks,
                holes={str(k): list(v) for k, v in holes.items()}, board=list(board),
                puppets={str(k): v for k, v in puppets.items()}, forced=forced, probe=probe, **kw)


def seat_at(button, pos):
    return (button + POS.index(pos)) % 8


def texture(board):
    ranks = sorted((RANKS.index(c[0]) for c in board), reverse=True)
    suits = len({c[1] for c in board})
    if len(set(ranks)) < 3:
        return "paired"
    if suits == 1:
        return "monotone"
    gaps = [ranks[0] - ranks[1], ranks[1] - ranks[2]]
    connected = sum(g <= 2 for g in gaps) >= 1 and ranks[0] - ranks[2] <= 4
    if suits == 2 and connected:
        return "wet"
    if suits == 3 and not connected and ranks[0] - ranks[2] >= 5:
        return "dry"
    return "other"


def build_scenarios(order, seed="bt1"):
    rng = random.Random(seed)
    btn_range = range_combos(order, 0.45)
    bb_range = range_combos(order, 0.50)
    co_range = range_combos(order, 0.30)
    sc = {}

    # --- RFI by position (100 bb): everyone before the hero folds.
    hero = 3
    rfi = []
    for pos in ["UTG", "UTG1", "MP", "HJ", "CO", "BTN", "SB"]:
        button = (hero - POS.index(pos)) % 8
        for i in range(len(NAMES)):
            h = rng.choice(COMBOS[i])
            holes, used = fill_holes(rng, range(8), {hero: h}, [], {})
            rfi.append(spot(f"rfi:{pos}:{i}", hero, button, [2000] * 8, holes, complete_board(rng, used, []),
                            {}, {}, 0, meta=dict(pos=pos, cls=i)))
    sc["rfi"] = rfi

    # --- BTN open by stack depth.
    depth = []
    for d in [40, 20, 12, 8]:
        for i in range(len(NAMES)):
            h = rng.choice(COMBOS[i])
            holes, used = fill_holes(rng, range(8), {hero: h}, [], {})
            depth.append(spot(f"depth:{d}:{i}", hero, hero, [d * BB] * 8, holes,
                              complete_board(rng, used, []), {}, {}, 0, meta=dict(depth=d, cls=i)))
    sc["depth"] = depth

    # --- BTN facing a CO open to 2.5 bb.
    tb = []
    button = hero
    co = seat_at(button, "CO")
    for i in range(len(NAMES)):
        h = rng.choice(COMBOS[i])
        holes, used = fill_holes(rng, range(8), {hero: h}, [], {co: co_range})
        tb.append(spot(f"3bet:{i}", hero, button, [2000] * 8, holes, complete_board(rng, used, []),
                       {co: {"script": {0: [["to", 50], "call"]}, "default": "checkcall"}}, {}, 0,
                       meta=dict(cls=i)))
    sc["threebet"] = tb

    # --- Heads-up push/fold (6 seats busted), SB first to act or BB facing a shove.
    hu = []
    villain = 5
    bust = [0, 1, 2, 4, 6, 7]
    for d in [5, 8, 10, 15, 20]:
        stacks = [0] * 8
        stacks[hero] = stacks[villain] = d * BB
        for i in range(len(NAMES)):
            h = rng.choice(COMBOS[i])
            holes, used = fill_holes(rng, [hero, villain], {hero: h}, [], {})
            board = complete_board(rng, used, [])
            hu.append(spot(f"husb:{d}:{i}", hero, hero, stacks, holes, board,
                           {villain: {"script": {}, "default": "checkfold"}}, {}, 0, bust=bust,
                           meta=dict(role="SB", depth=d, cls=i)))
            hu.append(spot(f"hubb:{d}:{i}", hero, villain, stacks, holes, board,
                           {villain: {"script": {0: ["allin"]}, "default": "checkcall"}}, {}, 0, bust=bust,
                           meta=dict(role="BB", depth=d, cls=i)))
    sc["hu"] = hu

    # --- ICM: 4 left, 3 paid. UTG folds, chip-leader BTN shoves 40 bb, SB (5 bb) folds,
    #     hero BB with 20 bb decides. Same spot with winner-takes-all payouts.
    icm_spots = []
    alive = [0, 1, 2, 3]
    stacks = [25 * BB, 40 * BB, 5 * BB, 20 * BB, 0, 0, 0, 0]
    shove_range = range_combos(order, 0.30)
    for payouts in [(50, 30, 20), (100,)]:
        for i in range(len(NAMES)):
            h = rng.choice(COMBOS[i])
            holes, used = fill_holes(rng, alive, {3: h}, [], {1: shove_range})
            icm_spots.append(spot(f"icm:{len(payouts)}:{i}", 3, 1, stacks, holes, complete_board(rng, used, []),
                                  {0: {"default": "checkfold"}, 1: {"script": {0: ["allin"]}, "default": "checkcall"},
                                   2: {"default": "checkfold"}}, {}, 0, bust=[4, 5, 6, 7], payouts=list(payouts),
                                  meta=dict(payouts=list(payouts), cls=i)))
    sc["icm"] = icm_spots

    # --- Postflop. Hero BTN raises to 2.5 bb, BB calls; flop checked to the hero.
    def flop_with(tex):
        while True:
            b = rng.sample(DECK, 3)
            if texture(b) == tex:
                return b

    cb = []
    bbs = seat_at(hero, "BB")
    for tex in ["dry", "wet", "paired", "monotone"]:
        for k in range(75):
            flop = flop_with(tex)
            while True:
                h = rng.choice(btn_range)
                if not set(h) & set(flop):
                    break
            holes, used = fill_holes(rng, range(8), {hero: h}, flop, {bbs: bb_range})
            board = complete_board(rng, used, flop)
            cb.append(spot(f"cbet:{tex}:{k}", hero, hero, [2000] * 8, holes, board,
                           {bbs: {"script": {0: ["call"], 1: ["check", "call"], 2: ["check", "call"],
                                             3: ["check", "call"]}, "default": "checkcall"}},
                           {0: [["to", 50]]}, 1, meta=dict(texture=tex, eqkind="mc", vr="bb")))
    sc["cbet"] = cb

    # --- Multiway twin of the first 150 c-bet spots: CO limps, hero raises to 4 bb, SB, BB, CO call.
    mw = []
    cos, sbs = seat_at(hero, "CO"), seat_at(hero, "SB")
    for base in cb[::2]:
        h = tuple(base["holes"][str(hero)])
        flop = base["board"][:3]
        holes, used = fill_holes(rng, range(8), {hero: h}, flop, {bbs: bb_range, sbs: bb_range, cos: bb_range})
        board = complete_board(rng, used, flop)
        pup = {"script": {0: ["call", "call"], 1: ["check", "call"]}, "default": "checkcall"}
        mw.append(spot(base["id"].replace("cbet", "mw"), hero, hero, [2000] * 8, holes, board,
                       {cos: pup, sbs: {"script": {0: ["call"], 1: ["check", "call"]}, "default": "checkcall"},
                        bbs: {"script": {0: ["call"], 1: ["check", "call"]}, "default": "checkcall"}},
                       {0: [["to", 80]]}, 1, meta=dict(texture=base["meta"]["texture"], twin=base["id"])))
    sc["multiway"] = mw

    # --- River as the aggressor: hero bets half pot on flop and turn, BB calls, river checked to hero.
    riv = []
    for k in range(300):
        while True:
            h = rng.choice(btn_range)
            holes, used = fill_holes(rng, range(8), {hero: h}, [], {bbs: bb_range})
            board = complete_board(rng, used, [])
            break
        riv.append(spot(f"river:{k}", hero, hero, [2000] * 8, holes, board,
                        {bbs: {"script": {0: ["call"], 1: ["check", "call"], 2: ["check", "call"],
                                          3: ["check", "call"]}, "default": "checkcall"}},
                        {0: [["to", 50]], 1: [["bet", 0.5]], 2: [["bet", 0.5]]}, 3,
                        meta=dict(eqkind="river", vr="bb")))
    sc["river"] = riv

    # --- Hero BB defends vs a BTN open, checks the flop, faces a bet of each size.
    fd = []
    button = btn = (hero - 2) % 8  # hero is BB, so the button is 2 seats before the hero
    for s in [0.33, 0.5, 0.75, 1.0, 1.5]:
        for k in range(80):
            h = rng.choice(bb_range)
            holes, used = fill_holes(rng, range(8), {hero: h}, [], {btn: btn_range})
            board = complete_board(rng, used, [])
            fd.append(spot(f"flopdef:{s}:{k}", hero, button, [2000] * 8, holes, board,
                           {btn: {"script": {0: [["to", 50], "call"], 1: [["bet", s], "fold"]}, "default": "checkfold"}},
                           {0: ["call"], 1: ["check"]}, 1, meta=dict(size=s, eqkind="mc", vr="btn")))
    sc["flopdef"] = fd

    # --- River defence: BTN bets half pot on the flop (hero calls), checks the turn, bets the river.
    rd = []
    for s in [0.33, 0.5, 1.0, 2.0]:
        for k in range(120):
            h = rng.choice(bb_range)
            holes, used = fill_holes(rng, range(8), {hero: h}, [], {btn: btn_range})
            board = complete_board(rng, used, [])
            rd.append(spot(f"riverdef:{s}:{k}", hero, button, [2000] * 8, holes, board,
                           {btn: {"script": {0: [["to", 50], "call"], 1: [["bet", 0.5], "call"], 2: ["check", "call"],
                                             3: [["bet", s], "fold"]}, "default": "checkfold"}},
                           {0: ["call"], 1: ["check", "call"], 2: ["check"], 3: ["check"]}, 3,
                           meta=dict(size=s, eqkind="river", vr="btn")))
    sc["riverdef"] = rd

    # --- Repeats (mixed strategies), transforms (consistency) and hidden-card swaps (leakage).
    rep = []
    for base in riv[:60] + [x for x in rfi if x["meta"]["pos"] == "BTN"]:
        for r in range(6):
            rep.append(dict(base, id=f"{base['id']}:rep{r}", tid=f"rep-{r}", hand=1 + 37 * r,
                            meta=dict(base["meta"], base=base["id"])))
    sc["repeat"] = rep

    perm = dict(zip(SUITS, "dhsc"))

    def suitswap(card):
        return card[0] + perm[card[1]]

    def rot(seat, k):
        return (seat + k) % 8

    cons = []
    for base in riv[:100] + [x for x in rfi if x["meta"]["pos"] in ("BTN", "CO")]:
        cons.append(dict(base, id=base["id"] + ":suit", rseed=base["id"],
                         holes={k: [suitswap(c) for c in v] for k, v in base["holes"].items()},
                         board=[suitswap(c) for c in base["board"]], meta=dict(base["meta"], base=base["id"], t="suit")))
        k = 3
        cons.append(dict(base, id=base["id"] + ":seat", rseed=base["id"], hero=rot(base["hero"], k), button=rot(base["button"], k),
                         stacks=[base["stacks"][(s - k) % 8] for s in range(8)],
                         holes={str(rot(int(s), k)): v for s, v in base["holes"].items()},
                         puppets={str(rot(int(s), k)): v for s, v in base["puppets"].items()},
                         meta=dict(base["meta"], base=base["id"], t="seat")))
    sc["consistency"] = cons

    leak = []
    for base in riv[:100] + fd[::2]:
        hero_s = str(base["hero"])
        visible = {"river": 5, "flopdef": 3}[base["id"].split(":")[0]]
        given = {hero: tuple(base["holes"][hero_s])}
        holes, used = fill_holes(random.Random(base["id"] + "leak"), range(8), given, base["board"][:visible], {})
        board = complete_board(random.Random(base["id"] + "leak2"), used, base["board"][:visible])
        leak.append(dict(base, id=base["id"] + ":leak", rseed=base["id"], holes={str(k): list(v) for k, v in holes.items()},
                         board=board, meta=dict(base["meta"], base=base["id"])))
    sc["leakage"] = leak
    return sc


def attach_equities(sc, order, workers):
    ranges = {"bb": range_combos(order, 0.50), "btn": range_combos(order, 0.45)}
    jobs, where = [], []
    for fam in ("cbet", "river", "flopdef", "riverdef", "multiway"):
        for x in sc[fam]:
            hero = str(x["hero"])
            vr = x["meta"].get("vr", "bb")
            if fam == "multiway":
                continue
            visible = 3 if x["probe"] == 1 else 5
            kind = "river" if visible == 5 else "mc"
            jobs.append((kind, tuple(x["holes"][hero]), tuple(x["board"][:visible]), ranges[vr], 400, x["id"]))
            where.append(x)
    with ProcessPoolExecutor(workers) as pool:
        for x, e in zip(where, pool.map(_eq_job, jobs, chunksize=8)):
            x["meta"]["eq"] = round(e, 4)


# ====================================================================== workers
_BOTS = {}


def get_bot(path):
    if path not in _BOTS:
        _BOTS[path] = mini_sim.load_agent(Path(path))
    return _BOTS[path]


def probe_job(args):
    path, fam, spots = args
    bot = get_bot(path)
    out = []
    for x in spots:
        try:
            r, _ = run_spot(bot, x)
        except Exception as e:  # a harness problem, not a bot decision
            r = {"k": "error", "e": repr(e)[:200]}
        out.append((x["id"], r))
    return path, fam, out


# ---- history tests: the bot plays 40 hands against puppets, then is probed with that memory.
def maniac_fn(state):
    return spec_action("allin", state)


def make_nit_fn(top):
    top = set(top)

    def fn(state):
        cards = tuple(state.cards)
        if cards in top or cards[::-1] in top:
            return spec_action("allin", state)
        return spec_action("checkfold", state)
    return fn


def folder_fn(state):
    return spec_action("checkfold", state)


def station_fn(state):
    return spec_action("checkcall", state)


def history_job(args):
    path, test, kind, order, seed = args
    bot = get_bot(path)
    rng = random.Random(f"{seed}:{test}:{kind}")
    hero = 3
    tid = f"hist-{test}-{kind}"
    if test == "range":  # heads-up, 15 bb, villain shoves everything or only the top 5%
        villain = 5
        stacks = [0] * 8
        stacks[hero] = stacks[villain] = 15 * BB
        bust = [0, 1, 2, 4, 6, 7]
        fn = maniac_fn if kind == "maniac" else make_nit_fn(range_combos(order, 0.05))
        others = {villain: fn}
    else:  # fold equity: 3-handed, blinds fold to any raise or call everything
        stacks = [0] * 8
        for s in (hero, 4, 5):
            stacks[s] = 100 * BB
        bust = [0, 1, 2, 6, 7]
        fn = folder_fn if kind == "folder" else station_fn
        others = {4: fn, 5: fn}
    agents = []
    h = Hero(bot)
    for s in range(8):
        agents.append(h if s == hero else Puppet(fn=others.get(s, folder_fn)))
    table = mini_sim.Table(agents, Rig(tid), rules_ns(), tid)
    table.bank = [1e12] * 8
    table.button = hero
    if hasattr(bot, "reseed"):
        bot.reseed(tid)
    for hand in range(1, 41):
        table.stacks = list(stacks)
        table.bust_order = list(bust)
        table.play_hand(hand)
    memory = table.memory[hero]
    out = []
    for i in range(len(NAMES)):
        hc = rng.choice(COMBOS[i])
        if test == "range":
            holes, used = fill_holes(rng, [hero, 5], {hero: hc}, [], {})
            x = spot(f"{tid}:{i}", hero, 5, stacks, holes, complete_board(rng, used, []),
                     {5: {"script": {0: ["allin"]}, "default": "checkcall"}}, {}, 0, bust=bust, tid=tid, hand=41 + i)
        else:
            holes, used = fill_holes(rng, [hero, 4, 5], {hero: hc}, [], {})
            x = spot(f"{tid}:{i}", hero, hero, stacks, holes, complete_board(rng, used, []),
                     {4: {"default": "checkfold"}, 5: {"default": "checkfold"}}, {}, 0, bust=bust, tid=tid,
                     hand=41 + i)
        r, _ = run_spot(bot, x, memory=memory)
        out.append((i, r))
    return path, f"hist:{test}:{kind}", out


# ---- whole-table simulations
class RandomBot:
    """Uniform over legal action kinds; raises to a random legal amount."""

    def __init__(self):
        self.rng = random.Random(0)

    def reseed(self, key):
        self.rng = random.Random(key)

    def act(self, state, memory):
        legal = state.legal_actions
        a = self.rng.choice(legal)
        if a.kind == "raise":
            return Action.raise_to(self.rng.randint(a.min_amount, a.max_amount)), memory
        return Action(a.kind), memory


class NoMemory:
    def __init__(self, pool):
        self.pool = pool

    def reseed(self, key):
        self.pool.reseed(key)

    def act(self, state, memory):
        action, _ = self.pool.act(state, b"")
        return action, b""


FIELDS = {
    "random": ["@random"] * 7,
    "rule_based": ["starter"] * 7,
    "tag": ["zoo/claude_grinder_1"] * 7,
    "station": ["sparring/calling_station"] * 7,
    "aggressive": ["sparring/shover"] * 4 + ["sparring/min_raiser"] * 3,
    "passive": ["sparring/check_or_fold"] * 4 + ["sparring/calling_station"] * 3,
    "tight": ["sparring/nit"] * 7,
    "loose": ["sparring/calling_station"] * 4 + ["sparring/shover"] * 3,
}
ABLATE = ["aggressive", "passive", "tight", "loose"]


def opp(name):
    if name == "@random":
        return RandomBot()
    return get_bot(str(ROOT / name))


def sim_job(args):
    """kind: field:<name>[:nomem], self, h2h:<other>. Returns per-table rows for the hero."""
    path, kind, seed, start, end, n_seats = args
    hero_pool = get_bot(path)
    rows = []
    for number in range(start, end):
        rng = random.Random(f"{seed}:{kind.replace(':nomem', '')}:{number}")
        if kind.startswith("field:"):
            parts = kind.split(":")
            hero = NoMemory(hero_pool) if parts[-1] == "nomem" else hero_pool
            players = [hero] + [opp(o) for o in FIELDS[parts[1]]]
        elif kind == "self":
            players = [hero_pool] * 8
        else:
            other = get_bot(kind.split(":", 1)[1])
            players = [hero_pool, other]
        order = list(range(len(players)))
        rng.shuffle(order)
        random.seed(f"{seed}:{number}:bots")
        for p in players:
            if hasattr(p, "reseed"):
                p.reseed(f"{seed}:{number}:{id(p) % 7}")
        rules = types.SimpleNamespace(stack=2000, decision_ms=1, bank_ms=100, hand_cap=250, hands_per_level=20,
                                      payouts=(50, 30, 20), variant="holdem", random_payouts=False)
        table = mini_sim.Table([players[i] for i in order], rng, rules, f"bt-{number}")
        hands = 0
        orig = table.play_hand

        def counted(h, orig=orig):
            nonlocal hands
            hands = h
            orig(h)
        table.play_hand = counted
        points = table.play()
        seat = order.index(0)
        if kind == "self":
            rows.append(dict(hands=hands, fails=sum(table.failures), dec=sum(table.decisions),
                             cap=int(hands >= rules.hand_cap), alive=sum(s > 0 for s in table.stacks)))
        else:
            rows.append(dict(p=points[seat], place=table.places()[seat], fails=table.failures[seat],
                             dec=table.decisions[seat], hands=hands))
    return path, kind, start, rows


def league_job(args):
    """Out-of-sample league: candidates drawn 8 at a time, rules varied per block of 100 tables."""
    cands, variant, seed, number = args
    draw = random.Random(f"{seed}:{variant}:{number}:lineup")
    bots = draw.sample(cands, 8)
    rules = dict(stack=2000, decision_ms=1, bank_ms=100, hand_cap=250, hands_per_level=20,
                 payouts=[50, 30, 20], random_payouts=True, variant=variant)
    rules.update(mini_sim.vary_rules(f"{seed}:{number // 100}"))
    spec = {"bots": bots, "seed": f"{seed}:{variant}", "rules": rules, "token": "oos"}
    r = mini_sim.play_table(spec, number)
    return variant, [(bots[idx], r["points"][seat], r["failures"][seat], r["decisions"][seat])
                     for seat, idx in enumerate(r["order"])]


# ====================================================================== static checks
SUSPICIOUS = [r"\binspect\b", r"sys\._getframe", r"\bf_back\b", r"\bf_locals\b", r"gc\.get_objects",
              r"\bmini_sim\b", r"\bpoker_engine\b", r"__import__", r"\bgetattr\(\s*state\s*,\s*['\"]_",
              r"\bctypes\b", r"\bos\.environ\b", r"\bsubprocess\b", r"\bopen\("]


def static_scan(path):
    """Suspicious names in the code itself (strings and comments are blanked out first)."""
    import io
    import tokenize
    source = (Path(path) / "agent.py").read_text(encoding="utf-8", errors="replace")
    lines = source.splitlines()
    code = [list(" " * len(line)) for line in lines]
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type in (tokenize.STRING, tokenize.COMMENT) or tok.start[0] == 0:
                continue
            (r1, c1), (r2, c2) = tok.start, tok.end
            if r1 == r2 and r1 <= len(lines):
                code[r1 - 1][c1:c2] = lines[r1 - 1][c1:c2]
    except (tokenize.TokenError, IndentationError):
        code = [list(line) for line in lines]
    text = "\n".join("".join(c) for c in code)
    hits = []
    for pat in SUSPICIOUS:
        for m in re.finditer(pat, text):
            line = text.count("\n", 0, m.start()) + 1
            hits.append(f"{pat} @ line {line}: {text.splitlines()[line - 1].strip()[:100]}")
    return hits


def fuzz(path, states):
    p = subprocess.run([sys.executable, str(ROOT / "tools" / "fuzz.py"), path, "--states", str(states), "--seed", "7"],
                       capture_output=True, text=True, timeout=3600)
    text = p.stdout + p.stderr
    summary = [ln for ln in text.splitlines() if "failures:" in ln]
    return p.returncode, "\n".join(summary) + "\n" + text[-2500:]


def _fuzz_job(args):
    return args[0], fuzz(*args)


# ====================================================================== run
def candidates(extra):
    out = [str(ROOT / "bots" / p.parent.name) for p in sorted(ROOT.glob("bots/*/agent.py"))]
    out.append(str(ROOT / "starter"))
    out += [str(p.parent) for p in sorted(ROOT.glob("zoo/*/agent.py")) if p.parent.name != "_template"]
    out += [str(Path(e).resolve()) for e in extra]
    return out


def label(path):
    p = Path(path)
    return "starter" if p.name == "starter" else f"{p.parent.name}/{p.name}"


def run(a):
    t0 = time.time()
    workers = a.workers

    def log(msg):
        print(f"[{time.time() - t0:6.0f}s] {msg}", file=sys.stderr, flush=True)

    bots = candidates(a.extra)
    log(f"{len(bots)} bots")
    eq = preflop_matrix(workers)
    order = rankings(eq)
    log("preflop matrix ready")
    nash = nash_tables(eq, [5, 8, 10, 15, 20], workers)
    log("push/fold equilibria ready")
    sc = build_scenarios(order)
    attach_equities(sc, order, workers)
    log("scenarios: " + ", ".join(f"{k}={len(v)}" for k, v in sc.items()))

    raw = dict(bots=[label(b) for b in bots], order=order, names=NAMES, weights=W,
               nash={str(d): v for d, v in nash.items()}, eq=eq,
               scenarios={k: [dict(id=x["id"], meta=x["meta"]) for x in v] for k, v in sc.items()},
               probes={}, sims={}, league={}, fuzz={}, static={})

    jobs = []
    for b in bots:
        for fam, spots in sc.items():
            for k in range(0, len(spots), 60):
                jobs.append(("probe", (b, fam, spots[k:k + 60])))
        for test, kinds in (("range", ("maniac", "nit")), ("foldeq", ("folder", "station"))):
            for kind in kinds:
                jobs.append(("hist", (b, test, kind, order, a.seed)))
        for f in FIELDS:
            for k in range(0, a.field_tables, 25):
                jobs.append(("sim", (b, f"field:{f}", a.seed, k, min(k + 25, a.field_tables), 8)))
        for f in ABLATE:
            for k in range(0, a.field_tables, 25):
                jobs.append(("sim", (b, f"field:{f}:nomem", a.seed, k, min(k + 25, a.field_tables), 8)))
        for k in range(0, a.self_tables, 25):
            jobs.append(("sim", (b, "self", a.seed, k, min(k + 25, a.self_tables), 8)))
    for x, y in itertools.combinations(bots, 2):
        for k in range(0, a.h2h_tables, 20):
            jobs.append(("sim", (x, f"h2h:{y}", a.seed, k, min(k + 20, a.h2h_tables), 2)))
    variants = sorted(mini_sim.VARIANTS)
    for v in variants:
        for n in range(a.oos_tables):
            jobs.append(("league", (bots, v, a.seed + "-oos", n)))
    random.Random(1).shuffle(jobs)
    log(f"{len(jobs)} jobs")
    with ProcessPoolExecutor(workers) as pool:
        futs = [pool.submit(_dispatch, j) for j in jobs]
        fuzz_futs = [pool.submit(_fuzz_job, (b, a.fuzz_states)) for b in bots]
        for i, f in enumerate(futs):
            kind, res = f.result()
            if kind in ("probe", "hist"):
                path, fam, out = res
                raw["probes"].setdefault(label(path), {}).setdefault(fam, []).extend(out)
            elif kind == "sim":
                path, k, start, rows = res
                if k.startswith("h2h:"):
                    k = "h2h:" + label(k[4:])
                raw["sims"].setdefault(label(path), {}).setdefault(k, []).extend([dict(r, t=start + j)
                                                                                    for j, r in enumerate(rows)])
            else:
                v, rows = res
                for b, pts, fl, dec in rows:
                    raw["league"].setdefault(v, {}).setdefault(label(b), []).append([pts, fl, dec])
            if i % 500 == 0:
                log(f"{i}/{len(jobs)}")
        for f in fuzz_futs:
            b, (code, text) = f.result()
            raw["fuzz"][label(b)] = dict(code=code, text=text)
    for b in bots:
        raw["static"][label(b)] = static_scan(b)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(gzip.compress(json.dumps(raw, separators=(",", ":")).encode(), mtime=0))
    log(f"wrote {out}")


def reprobe(a):
    raw_path = Path(a.raw)
    raw = json.loads(gzip.decompress(raw_path.read_bytes()))
    bots = candidates(a.extra)
    eq = preflop_matrix(a.workers)
    order = rankings(eq)
    sc = build_scenarios(order)
    attach_equities(sc, order, a.workers)
    jobs = [("probe", (b, fam, spots[k:k + 60])) for b in bots for fam, spots in sc.items()
            for k in range(0, len(spots), 60)]
    jobs += [("hist", (b, test, kind, order, a.seed)) for b in bots
             for test, kinds in (("range", ("maniac", "nit")), ("foldeq", ("folder", "station"))) for kind in kinds]
    probes = {}
    with ProcessPoolExecutor(a.workers) as pool:
        for kind, (path, fam, out) in pool.map(_dispatch, jobs):
            probes.setdefault(label(path), {}).setdefault(fam, []).extend(out)
    with ProcessPoolExecutor(a.workers) as pool:
        for b, (code, text) in pool.map(_fuzz_job, [(b, a.fuzz_states) for b in bots]):
            raw["fuzz"][label(b)] = dict(code=code, text=text)
    raw["static"] = {label(b): static_scan(b) for b in bots}
    raw["probes"] = probes
    raw["scenarios"] = {k: [dict(id=x["id"], meta=x["meta"]) for x in v] for k, v in sc.items()}
    raw_path.write_bytes(gzip.compress(json.dumps(raw, separators=(",", ":")).encode(), mtime=0))
    print(f"re-probed {len(bots)} bots into {raw_path}", file=sys.stderr)


def _dispatch(job):
    funcs = dict(probe=probe_job, hist=history_job, sim=sim_job, league=league_job)
    return job[0], funcs[job[0]](job[1])


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--out", required=True)
    r.add_argument("--extra", nargs="*", default=[], help="more bot folders (outside the repo is fine)")
    r.add_argument("--seed", default="bt1")
    r.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    r.add_argument("--field-tables", type=int, default=250)
    r.add_argument("--self-tables", type=int, default=100)
    r.add_argument("--h2h-tables", type=int, default=100)
    r.add_argument("--oos-tables", type=int, default=1000, help="per variant")
    r.add_argument("--fuzz-states", type=int, default=20000)
    rp = sub.add_parser("reprobe", help="re-run only the probe tests into an existing raw file")
    rp.add_argument("raw")
    rp.add_argument("--extra", nargs="*", default=[])
    rp.add_argument("--seed", default="bt1")
    rp.add_argument("--fuzz-states", type=int, default=20000)
    rp.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    p = sub.add_parser("report")
    p.add_argument("raw")
    p.add_argument("--json", help="also write the per-bot metrics here")
    a = ap.parse_args()
    if a.cmd == "run":
        run(a)
    elif a.cmd == "reprobe":
        reprobe(a)
    else:
        from bot_tests_report import report
        report(a)


if __name__ == "__main__":
    main()
