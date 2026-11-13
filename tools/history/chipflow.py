"""Chips won or lost per preflop situation, in big blinds per 100 hands dealt: us against the ten best teams. Reads only."""
import gzip, json, sys, collections
path = sys.argv[1]
def lines(path):
    """Lines of a gzip download; a file cut short is read up to the cut."""
    try:
        with gzip.open(path, "rt") as f:
            for line in f:
                yield line
    except EOFError:
        print("(file is cut short: read up to the cut)")
TOP = set(sys.argv[2:]) or {"Pluto", "Amateur Pros", "Cold Decks", "MY STREET", "SIGSEGV", "Claude Mythos 5.5", "Ferdabot II", "Hold Em Trophies", "Team 114", "Team bp"}
S = {"us": collections.defaultdict(lambda: [0, 0.0]), "top": collections.defaultdict(lambda: [0, 0.0])}
N = collections.Counter(); names = {}; me = None; table = None
for line in lines(path):
    if True:
        try:
            rec = json.loads(line)
        except ValueError:
            break
        if "entries" in rec:
            me = rec["you"]; names = {e["entry_id"]: e["team_name"] for e in rec["entries"]}; continue
        if "hands" in rec: table = rec; continue
        if not rec.get("you") or table is None: continue
        fill = set(table.get("fillers") or []); seats = table["seats"]
        group = {i: ("us" if e == me else "top" if names.get(e) in TOP else None) for i, e in enumerate(seats) if i not in fill}
        for h in table["hands"]:
            sb = h["stacks_before"]; alive = sum(1 for s in sb if s > 0)
            if alive < 4: continue
            bb = h["blinds"][1]; blinds = [e for e in h["events"] if e["kind"] == "blind"]
            if len(blinds) != 2: continue
            big = max(blinds, key=lambda e: e["amount"])["seat"]; small = min(blinds, key=lambda e: e["amount"])["seat"]
            raised = False; first = {}
            for e in h["events"]:
                if e["kind"] == "board": break
                s = e.get("seat")
                if e["kind"] in ("fold", "call", "check", "raise") and s is not None:
                    if s not in first: first[s] = (e["kind"], raised)
                    if e["kind"] == "raise": raised = True
            for s, g in group.items():
                if g is None or sb[s] <= 0: continue
                N[g] += 1
                kind, faced = first.get(s, ("none", False))
                pos = "BB" if s == big else "SB" if s == small else "other"
                depth = "deep" if sb[s] / bb > 15 else "short"
                if kind == "none": cat = f"{pos}: no decision (walk or all-in before us)"
                elif pos == "BB": cat = "BB: " + (("fold to raise" if kind == "fold" else "call a raise" if kind == "call" else "re-raise") if faced else ("check" if kind == "check" else "raise unraised pot"))
                elif kind == "fold": cat = f"{pos}: fold" + (" to raise" if faced else " first in")
                elif kind == "raise": cat = f"{pos}, {depth}: " + ("re-raise" if faced else "open raise")
                else: cat = f"{pos}: " + ("call a raise" if faced else "limp")
                c = S[g][cat]; c[0] += 1; c[1] += (h["stacks_after"][s] - sb[s]) / bb
print(f"hands dealt with 4+ players alive: us {N['us']}, top ten {N['top']}")
print(f"{'situation':44s} {'us: share':>9s} {'bb/hand':>8s} {'bb/100':>7s} | {'top: share':>10s} {'bb/hand':>8s} {'bb/100':>7s}")
tot = {"us": 0.0, "top": 0.0}
for cat in sorted(set(S["us"]) | set(S["top"])):
    out = f"{cat:44s}"
    for g in ("us", "top"):
        n, d = S[g][cat]; share = n / N[g]; per = d / n if n else 0.0; tot[g] += 100 * d / N[g]
        out += f" {100 * share:8.1f}% {per:8.2f} {100 * d / N[g]:7.1f}" + (" |" if g == "us" else "")
    print(out)
print(f"{'TOTAL bb per 100 hands':44s} {'':9s} {'':8s} {tot['us']:7.1f} | {'':10s} {'':8s} {tot['top']:7.1f}")
