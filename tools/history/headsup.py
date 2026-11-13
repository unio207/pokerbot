"""Heads-up play from a team history: who wins, from what chip share, and what each side does by stack depth. Reads only."""
import gzip, json, sys, collections
path = sys.argv[1]; TOP = set(sys.argv[2:])
def lines(path):
    try:
        with gzip.open(path, "rt") as f:
            for line in f: yield line
    except EOFError: print("(file is cut short)")
match = {g: collections.Counter() for g in ("us", "top", "rest")}
share_bins = {g: collections.defaultdict(lambda: [0, 0]) for g in ("us", "top", "rest")}
btn = {g: collections.defaultdict(collections.Counter) for g in ("us", "top", "rest")}
bbv = {g: collections.defaultdict(collections.Counter) for g in ("us", "top", "rest")}
reach = collections.Counter(); tables = collections.Counter(); names = {}; me = None; table = None
def depth(x): return "<=6" if x <= 6 else "6-10" if x <= 10 else "10-15" if x <= 15 else "15-25" if x <= 25 else ">25"
for line in lines(path):
    try: rec = json.loads(line)
    except ValueError: break
    if "entries" in rec: me = rec["you"]; names = {e["entry_id"]: e["team_name"] for e in rec["entries"]}; continue
    if "hands" in rec: table = rec; continue
    if not rec.get("you") or table is None: continue
    fill = set(table.get("fillers") or [])
    grp = {i: ("us" if e == me else "top" if names.get(e) in TOP else "rest") for i, e in enumerate(table["seats"]) if i not in fill}
    for g in set(grp.values()): tables[g] += sum(1 for v in grp.values() if v == g)
    started = False
    for h in table["hands"]:
        sb = h["stacks_before"]; live = [i for i, s in enumerate(sb) if s > 0]
        if len(live) != 2: continue
        bb = h["blinds"][1]; total = sb[live[0]] + sb[live[1]]
        if not started:
            started = True; last = table["hands"][-1]["stacks_after"]
            for i in live:
                if i in grp:
                    g = grp[i]; won = last[i] > 0 and last[live[0] if i == live[1] else live[1]] == 0
                    match[g]["played"] += 1; match[g]["won"] += won; reach[g] += 1
                    sh = sb[i] / total; b = "under 35% of the chips" if sh < 0.35 else "35 to 65%" if sh <= 0.65 else "over 65%"
                    share_bins[g][b][0] += 1; share_bins[g][b][1] += won
        blinds = [e for e in h["events"] if e["kind"] == "blind"]
        if len(blinds) != 2 or blinds[0]["amount"] == blinds[1]["amount"]: continue
        button = min(blinds, key=lambda e: e["amount"])["seat"]; big = max(blinds, key=lambda e: e["amount"])["seat"]
        eff = depth(min(sb[button], sb[big]) / bb)
        acts = [e for e in h["events"] if e["kind"] in ("fold", "call", "check", "raise", "board")]
        first = next((e for e in acts if e.get("seat") == button), None)
        if first is None or first["kind"] == "board": continue
        kind = first["kind"]
        if kind == "raise": kind = "shove" if first["amount"] >= sb[button] or first["amount"] >= sb[big] else "raise"
        if button in grp: btn[grp[button]][eff][kind] += 1
        if kind in ("raise", "shove") and big in grp:
            resp = next((e for e in acts[acts.index(first) + 1:] if e.get("seat") == big), None)
            if resp and resp["kind"] != "board": bbv[grp[big]][eff]["vs " + kind + ": " + resp["kind"]] += 1
for g in ("us", "top", "rest"):
    m = match[g]; print(f"{g:4s}: seats {tables[g]:6d}, reached heads-up {100 * reach[g] / max(1, tables[g]):5.1f}%, won it {100 * m['won'] / max(1, m['played']):5.1f}% (n {m['played']})  by starting chip share: " + "; ".join(f"{b} {100 * w / n:.0f}% (n {n})" for b, (n, w) in sorted(share_bins[g].items())))
for g in ("us", "top"):
    print(f"--- {g}: on the button, first action by effective stack (bb)")
    for d in ("<=6", "6-10", "10-15", "15-25", ">25"):
        c = btn[g][d]; n = sum(c.values()) or 1
        print(f"   {d:6s} n {n:6d}  " + "  ".join(f"{k} {100 * c[k] / n:4.0f}%" for k in ("fold", "call", "raise", "shove")))
    print(f"--- {g}: in the big blind against a raise or a shove")
    for d in ("<=6", "6-10", "10-15", "15-25", ">25"):
        c = bbv[g][d]
        for kind in ("raise", "shove"):
            n = sum(v for k, v in c.items() if k.startswith("vs " + kind)) or 1
            print(f"   {d:6s} vs {kind:5s} n {n:6d}  " + "  ".join(f"{k} {100 * c['vs ' + kind + ': ' + k] / n:4.0f}%" for k in ("fold", "call", "raise")))
