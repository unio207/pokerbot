"""Side-prize counters per team from a team history: scoops and rivers seen per table. Reads only."""
import gzip, json, sys, collections
path = sys.argv[1]
def lines(path):
    try:
        with gzip.open(path, "rt") as f:
            for line in f: yield line
    except EOFError: pass
T = collections.defaultdict(collections.Counter); names = {}; me = None; table = None
for line in lines(path):
    try: rec = json.loads(line)
    except ValueError: break
    if "entries" in rec: me = rec["you"]; names = {e["entry_id"]: e["team_name"] for e in rec["entries"]}; continue
    if "hands" in rec: table = rec; continue
    if not rec.get("you") or table is None: continue
    fill = set(table.get("fillers") or []); team = {i: names.get(e, "?") for i, e in enumerate(table["seats"]) if i not in fill}
    for t in team.values(): T[t]["tables"] += 1
    for h in table["hands"]:
        for e in h["events"]:
            k = e["kind"]
            if k == "prize_scoops" and e.get("seat") in team: T[team[e["seat"]]]["scoops"] += 1
            elif k == "prize_rivers_seen" and e.get("seat") in team: T[team[e["seat"]]]["rivers"] += 1
    table = None
ours = names[me]; teams = [t for t in T if T[t]["tables"] >= 200]
for key, label in (("scoops", "SCOOPS per table"), ("rivers", "RIVERS SEEN per table")):
    order = sorted(teams, key=lambda t: -T[t][key] / T[t]["tables"])
    top = "  ".join(f"{t[:16]} {T[t][key] / T[t]['tables']:.2f}" for t in order[:5])
    print(f"{label}: us {T[ours][key] / T[ours]['tables']:.2f}, rank {order.index(ours) + 1} of {len(order)} | median {T[order[len(order) // 2]][key] / T[order[len(order) // 2]]['tables']:.2f} | top five: {top}")
