"""Preflop frequencies of named teams (and us) by players alive, seats still to act and effective stack. Reads only.
Prints Python literals for the top teams: first-in play, call of a shove, response to a raise."""
import gzip, json, sys, collections
path = sys.argv[1]; TOP = set(sys.argv[2:])
def lines(path):
    try:
        with gzip.open(path, "rt") as f:
            for line in f: yield line
    except EOFError: pass
DEPTH = (6, 10, 15, 25)
def drow(x): return sum(x > d for d in DEPTH)
def arow(n): return 0 if n == 2 else 1 if n == 3 else 2 if n <= 5 else 3   # 2, 3, 4-5, 6+
first = {g: collections.defaultdict(collections.Counter) for g in ("us", "top")}   # (alive row, behind, depth) -> fold/raise/shove/call
vs_shove = {g: collections.defaultdict(collections.Counter) for g in ("us", "top")}  # (alive row, is_bb, depth) -> fold/call
vs_raise = {g: collections.defaultdict(collections.Counter) for g in ("us", "top")}  # (alive row, pos, depth) -> fold/call/raise
names = {}; me = None; table = None
for line in lines(path):
    try: rec = json.loads(line)
    except ValueError: break
    if "entries" in rec: me = rec["you"]; names = {e["entry_id"]: e["team_name"] for e in rec["entries"]}; continue
    if "hands" in rec: table = rec; continue
    if not rec.get("you") or table is None: continue
    fill = set(table.get("fillers") or [])
    grp = {i: ("us" if e == me else "top" if names.get(e) in TOP else None) for i, e in enumerate(table["seats"]) if i not in fill}
    for h in table["hands"]:
        sb = h["stacks_before"]; live = [i for i, s in enumerate(sb) if s > 0]; n = len(live)
        if n < 2: continue
        bb = h["blinds"][1]; ev = h["events"]; blinds = [e for e in ev if e["kind"] == "blind"]
        if len(blinds) != 2: continue
        big = max(blinds, key=lambda e: e["amount"])["seat"]; small = min(blinds, key=lambda e: e["amount"])["seat"]
        if blinds[0]["amount"] == blinds[1]["amount"]: continue
        acted = []; raises = []; limp = False; a = arow(n)
        for e in ev:
            if e["kind"] == "board": break
            s = e.get("seat"); k = e["kind"]
            if k not in ("fold", "call", "check", "raise") or s is None: continue
            g = grp.get(s)
            if s not in acted:
                eff = min(sb[s], max(sb[i] for i in live if i != s)) / bb; d = drow(eff)
                if not raises and not limp and g:
                    behind = n - 1 - len(acted) if s != big else 0
                    if s != big:
                        kind = k if k != "raise" else ("shove" if e["amount"] >= sb[s] or e["amount"] >= max(sb[i] for i in live if i != s) else "raise")
                        first[g][(a, min(behind, 4), d)][kind] += 1
                elif len(raises) == 1 and g:
                    r = raises[0]; shove = r["amount"] >= sb[r["seat"]] or r["amount"] >= sb[s]
                    pos = "bb" if s == big else "sb" if s == small else "other"
                    if shove: vs_shove[g][(a, pos == "bb", drow(min(r["amount"], sb[s]) / bb))][k if k != "raise" else "call"] += 1
                    else: vs_raise[g][(a, pos, d)][k] += 1
                acted.append(s)
            if k == "raise": raises.append(e)
            elif k == "call" and not raises: limp = True
def share(c, keys): 
    n = sum(c.values()); return round(sum(c[k] for k in keys) / n, 2) if n >= 40 else None
AL = ("2", "3", "4-5", "6+")
for g in ("top", "us"):
    print(f"=== {g}: FIRST IN, share of hands played (raise or shove) | shove share of those; rows = seats behind 1..4+, columns = depth <=6, 6-10, 10-15, 15-25, >25")
    for a in range(4):
        for b in range(1, 5):
            cells = [first[g][(a, b, d)] for d in range(5)]
            if sum(sum(c.values()) for c in cells) < 200: continue
            print(f"  alive {AL[a]:3s} behind {b}: play " + " ".join(f"{share(c, ('raise', 'shove')) if share(c, ('raise', 'shove')) is not None else '--':>5}" for c in cells) + "  | shove " + " ".join(f"{share(c, ('shove',)) if share(c, ('shove',)) is not None else '--':>5}" for c in cells) + f"   n {[sum(c.values()) for c in cells]}")
    print(f"=== {g}: CALL A SHOVE (first raise is all-in), share called; columns = depth")
    for a in range(4):
        for isbb in (True, False):
            cells = [vs_shove[g][(a, isbb, d)] for d in range(5)]
            if sum(sum(c.values()) for c in cells) < 200: continue
            print(f"  alive {AL[a]:3s} {'big blind' if isbb else 'other    '}: " + " ".join(f"{share(c, ('call',)) if share(c, ('call',)) is not None else '--':>5}" for c in cells) + f"   n {[sum(c.values()) for c in cells]}")
    print(f"=== {g}: FACING ONE RAISE (not all-in): re-raise share | call share; columns = depth")
    for a in range(4):
        for pos in ("bb", "sb", "other"):
            cells = [vs_raise[g][(a, pos, d)] for d in range(5)]
            if sum(sum(c.values()) for c in cells) < 200: continue
            print(f"  alive {AL[a]:3s} {pos:5s}: re-raise " + " ".join(f"{share(c, ('raise',)) if share(c, ('raise',)) is not None else '--':>5}" for c in cells) + "  | call " + " ".join(f"{share(c, ('call',)) if share(c, ('call',)) is not None else '--':>5}" for c in cells) + f"   n {[sum(c.values()) for c in cells]}")
