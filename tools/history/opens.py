"""What happens after a first-in open raise (deep, not in the blinds, 4+ alive): us against named teams. Reads only."""
import gzip, json, sys, collections
path = sys.argv[1]; TOP = set(sys.argv[2:])
def lines(path):
    try:
        with gzip.open(path, "rt") as f:
            for line in f: yield line
    except EOFError: print("(file is cut short: read up to the cut)")
S = {"us": collections.defaultdict(lambda: [0, 0.0]), "top": collections.defaultdict(lambda: [0, 0.0])}
N = collections.Counter(); size = {"us": [0, 0.0], "top": [0, 0.0]}; names = {}; me = None; table = None
for line in lines(path):
    try: rec = json.loads(line)
    except ValueError: break
    if "entries" in rec: me = rec["you"]; names = {e["entry_id"]: e["team_name"] for e in rec["entries"]}; continue
    if "hands" in rec: table = rec; continue
    if not rec.get("you") or table is None: continue
    fill = set(table.get("fillers") or [])
    group = {i: ("us" if e == me else "top" if names.get(e) in TOP else None) for i, e in enumerate(table["seats"]) if i not in fill}
    for h in table["hands"]:
        sb = h["stacks_before"]
        if sum(1 for s in sb if s > 0) < 4: continue
        bb = h["blinds"][1]; ev = h["events"]; blinds = {e["seat"] for e in ev if e["kind"] == "blind"}
        opener = None; k_open = None
        for k, e in enumerate(ev):
            if e["kind"] == "board": break
            if e["kind"] == "raise": opener, k_open = e["seat"], k; break
            if e["kind"] == "call": break  # a limp: not a first-in open
        if opener is None or opener in blinds or group.get(opener) is None or sb[opener] / bb <= 15: continue
        g = group[opener]; N[g] += 1; size[g][0] += 1; size[g][1] += ev[k_open]["amount"] / bb
        rest = ev[k_open + 1:]; pre = []; post = []; seen_board = False
        for e in rest:
            if e["kind"] == "board": seen_board = True; continue
            (post if seen_board else pre).append(e)
        reraised = any(e["kind"] == "raise" and e.get("seat") != opener for e in pre)
        called = any(e["kind"] == "call" and e.get("seat") != opener for e in pre)
        mine_pre = [e["kind"] for e in pre if e.get("seat") == opener]
        if reraised:
            cat = "1 re-raised: we fold" if "fold" in mine_pre else "2 re-raised: we continue"
        elif not called: cat = "0 everyone folds"
        else:
            first = next((e["kind"] for e in post if e.get("seat") == opener and e["kind"] in ("check", "raise", "call", "fold")), None)
            bet_before = False
            for e in post:
                if e.get("seat") == opener: break
                if e["kind"] == "raise": bet_before = True
            if first is None: cat = "3 called: all-in or no flop decision"
            elif first == "raise": cat = "4 called: we bet or raise the flop"
            elif first == "check": cat = "5 called: we check the flop"
            elif first == "fold": cat = "6 called: we fold the flop to a bet"
            else: cat = "7 called: we call a flop bet"
        c = S[g][cat]; c[0] += 1; c[1] += (h["stacks_after"][opener] - sb[opener]) / bb
print(f"first-in opens: us {N['us']} (mean size {size['us'][1] / max(1, size['us'][0]):.2f} bb), named teams {N['top']} (mean size {size['top'][1] / max(1, size['top'][0]):.2f} bb)")
print(f"{'after the open':40s} {'us: share':>9s} {'bb each':>8s} {'adds':>6s} | {'top: share':>10s} {'bb each':>8s} {'adds':>6s}")
tot = {"us": 0.0, "top": 0.0}
for cat in sorted(set(S["us"]) | set(S["top"])):
    out = f"{cat[2:]:40s}"
    for g in ("us", "top"):
        n, d = S[g][cat]; tot[g] += d / max(1, N[g])
        out += f" {100 * n / max(1, N[g]):8.1f}% {d / n if n else 0:8.2f} {d / max(1, N[g]):6.2f}" + (" |" if g == "us" else "")
    print(out)
print(f"{'bb per open':40s} {'':9s} {'':8s} {tot['us']:6.2f} | {'':10s} {'':8s} {tot['top']:6.2f}")
