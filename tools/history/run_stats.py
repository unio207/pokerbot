"""Stream one team hand-history download: our points per table, places, heads-up button play. Reads only."""
import gzip, json, sys, math, collections
path = sys.argv[1]
points, places, first_line = [], collections.Counter(), None
hu = collections.Counter(); kinds = collections.Counter(); tables = hands = 0; table = None
with gzip.open(path, "rt") as f:
    for line in f:
        rec = json.loads(line)
        if first_line is None:
            first_line = rec
            me = rec.get("you"); names = {e["entry_id"]: e["team_name"] for e in rec.get("entries", [])}
            print("header keys", sorted(rec), "entries", len(names), "we are", names.get(me))
            continue
        if "hands" in rec:
            table = rec; continue
        you = rec.get("you")
        if not you or table is None:
            continue
        seat = you["seat"]; hs = table["hands"]; tables += 1; hands += len(hs)
        if tables == 1:
            print("table keys", sorted(table), "| hand keys", sorted(hs[0]), "| you keys", sorted(you))
        last = hs[-1]; pts = last["equity_after"][seat]; points.append(pts)
        pay = table.get("payouts") or [50, 30, 20]
        alive = sum(1 for s in last["stacks_after"] if s > 0)
        if last["stacks_after"][seat] > 0 and alive == 1: places[1] += 1
        elif abs(pts - pay[0]) < 1e-6: places[1] += 1
        elif len(pay) > 1 and abs(pts - pay[1]) < 1e-6: places[2] += 1
        elif len(pay) > 2 and abs(pts - pay[2]) < 1e-6: places[3] += 1
        elif pts == 0: places["out of the points"] += 1
        else: places["hand cap or other split"] += 1
        for h in hs:
            live = [i for i, s in enumerate(h["stacks_before"]) if s > 0]
            if len(live) != 2 or h["stacks_before"][seat] <= 0:
                continue
            blinds = [e for e in h["events"] if e["kind"] == "blind"]
            if len(blinds) != 2: continue
            mine = [e for e in blinds if e.get("seat") == seat]
            if not mine: continue
            small = min(blinds, key=lambda e: e["amount"])
            role = "button" if small.get("seat") == seat and blinds[0]["amount"] != blinds[1]["amount"] else "big blind"
            act = next((e for e in h["events"] if e.get("seat") == seat and e["kind"] in ("fold", "call", "check", "raise")), None)
            hu[(role, act["kind"] if act else "no action")] += 1
        table = None
n = len(points); mean = sum(points) / n; se = math.sqrt(sum((p - mean) ** 2 for p in points) / (n - 1) / n)
print(f"tables {tables} hands {hands}  points/table {mean:.2f} ± {se:.2f}")
print("places:", {k: f"{v} ({100 * v / n:.1f}%)" for k, v in sorted(places.items(), key=lambda kv: str(kv[0]))})
for role in ("button", "big blind"):
    tot = sum(v for (r, _), v in hu.items() if r == role)
    print(f"heads-up {role}: n {tot}", {k: f"{100 * v / max(1, tot):.1f}%" for (r, k), v in sorted(hu.items()) if r == role})
