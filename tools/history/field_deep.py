"""One streaming pass over a team hand-history download: per-team style and results, and how we bust. Reads only."""
import gzip, json, sys, math, collections
path = sys.argv[1]
def lines(path):
    """Lines of a gzip download; a file cut short is read up to the cut."""
    try:
        with gzip.open(path, "rt") as f:
            for line in f:
                yield line
    except EOFError:
        print("(file is cut short: read up to the cut)")
T = collections.defaultdict(collections.Counter)   # team -> counters
pts = collections.defaultdict(list)
us = collections.Counter(); bust_hand = []; place = collections.Counter(); stack_bb = collections.defaultdict(list); field_bb = collections.defaultdict(list)
by_alive = collections.defaultdict(collections.Counter)
names = {}; me = None; table = None
for line in lines(path):
    if True:
        try:
            rec = json.loads(line)
        except ValueError:
            break
        if "entries" in rec:
            me = rec["you"]; names = {e["entry_id"]: e["team_name"] for e in rec["entries"]}; continue
        if "hands" in rec:
            table = rec; continue
        you = rec.get("you")
        if not you or table is None: continue
        seat = you["seat"]; hs = table["hands"]; fill = set(table.get("fillers") or [])
        team = [None if i in fill else names.get(e, "?") for i, e in enumerate(table["seats"])]
        last = hs[-1]
        for i, t in enumerate(team):
            if t: pts[t].append(last["equity_after"][i]); T[t]["tables"] += 1; T[t]["first"] += last["equity_after"][i] >= (table["payouts"] or [50])[0] - 1e-6
        busted = False
        for k, h in enumerate(hs):
            sb = h["stacks_before"]; alive = [i for i, s in enumerate(sb) if s > 0]; bb = h["blinds"][1]
            if k in (20, 40, 60, 80) and sb[seat] > 0:
                stack_bb[k].append(sb[seat] / bb); field_bb[k].append(sum(sb[i] for i in alive) / len(alive) / bb)
            raised = False; acted = set(); street = 0; bet_open = False; shows = set(); wins = set(); allin_pre = {}
            for e in h["events"]:
                kind = e["kind"]; s = e.get("seat")
                if kind == "board":
                    if e.get("amount") == 1: street += 1; bet_open = False
                    continue
                if kind == "show": shows.add(s); continue
                if kind == "win": wins.add(s); continue
                if kind not in ("fold", "call", "check", "raise") or s is None or team[s] is None: continue
                c = T[team[s]]
                if street == 0:
                    if s not in acted:
                        acted.add(s); c["hands"] += 1
                        if kind in ("call", "raise"): c["vpip"] += 1
                        if kind == "raise": c["pfr"] += 1
                        if raised: c["face_raise"] += 1; c["fold_raise"] += kind == "fold"; c["reraise"] += kind == "raise"
                        if s == seat: 
                            a = by_alive[min(len(alive), 4) if len(alive) > 2 else 2]; a["hands"] += 1; a["vpip"] += kind in ("call", "raise"); a["pfr"] += kind == "raise"
                            if raised: a["face"] += 1; a["foldr"] += kind == "fold"
                    if kind == "raise":
                        raised = True
                        if e["amount"] >= sb[s]: c["shove"] += 1; allin_pre[s] = "shove"
                    elif kind == "call" and h["stacks_after"][s] == 0 or (kind == "call" and e.get("amount", 0) >= sb[s]): allin_pre.setdefault(s, "call")
                else:
                    if kind == "raise":
                        if not bet_open: c["bet"] += 1
                        else: c["raise_post"] += 1
                        bet_open = True
                    elif kind == "check": c["check"] += 1
                    elif bet_open: c["face_bet"] += 1; c["fold_bet"] += kind == "fold"
            for s in shows:
                if team[s]: T[team[s]]["showdown"] += 1; T[team[s]]["sd_win"] += s in wins
            if not busted and sb[seat] > 0 and h["stacks_after"][seat] == 0:
                busted = True; bust_hand.append(k); left = sum(1 for x in h["stacks_after"] if x > 0); place[left + 1] += 1
                us["bust_" + ("preflop " + allin_pre[seat] if seat in allin_pre else "postflop or blinds")] += 1
                us["bust_bb_" + ("<=10" if sb[seat] / bb <= 10 else "10-25" if sb[seat] / bb <= 25 else ">25")] += 1
        if not busted: place["survived"] += 1
        table = None
def row(t):
    c = T[t]; p = pts[t]; n = len(p); m = sum(p) / n
    pc = lambda a, b: f"{100 * c[a] / max(1, c[b]):4.0f}"
    return f"{t[:22]:22s} n {n:5d} pts {m:5.2f} 1st {100 * c['first'] / n:4.1f}% | VPIP {pc('vpip','hands')} PFR {pc('pfr','hands')} shove {pc('shove','hands')} f/raise {pc('fold_raise','face_raise')} reraise {pc('reraise','face_raise')} | bet {100 * c['bet'] / max(1, c['bet'] + c['check']):4.0f} f/bet {pc('fold_bet','face_bet')} | SD/hand {100 * c['showdown'] / max(1, c['hands']):4.1f} SDwin {pc('sd_win','showdown')}"
rank = sorted((t for t in pts if len(pts[t]) >= 300), key=lambda t: -sum(pts[t]) / len(pts[t]))
our = names[me]; print("teams with 300+ tables in our file:", len(rank), "| our rank among them:", rank.index(our) + 1)
for t in rank[:10]: print(row(t))
print("..."); print(row(our))
mid = rank[len(rank) // 2 - 2: len(rank) // 2 + 2]; print("median teams:"); [print(row(t)) for t in mid]
n = sum(place.values()); print("our finish:", {k: f"{100 * v / n:.1f}%" for k, v in sorted(place.items(), key=lambda kv: str(kv[0]))})
bust_hand.sort(); print("bust hand number: median", bust_hand[len(bust_hand) // 2], "quartiles", bust_hand[len(bust_hand) // 4], bust_hand[3 * len(bust_hand) // 4])
print("how we bust:", {k: f"{100 * v / max(1, len(bust_hand)):.1f}%" for k, v in sorted(us.items())})
for k in (20, 40, 60, 80): print(f"hand {k}: we are alive in {len(stack_bb[k])} tables, our stack {sum(stack_bb[k]) / len(stack_bb[k]):.1f} bb, mean live stack {sum(field_bb[k]) / len(field_bb[k]):.1f} bb")
for a in sorted(by_alive, reverse=True):
    c = by_alive[a]; print(f"players alive {'5+' if a == 4 and False else a}{'+' if a == 4 else ''}: hands {c['hands']} VPIP {100 * c['vpip'] / c['hands']:.0f}% PFR {100 * c['pfr'] / c['hands']:.0f}% fold to raise {100 * c['foldr'] / max(1, c['face']):.0f}% (n {c['face']})")
