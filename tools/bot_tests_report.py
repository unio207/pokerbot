"""Scores the raw output of tools/bot_tests.py: one metric and one 0-100 score per test per bot.

Every score is a transparent formula over the measured metric (see TESTS below and the
report's method section). 100 is the target behaviour; the weighting is our own choice and
the raw metrics are printed beside each score so they can be judged directly.
"""

import gzip
import json
import math
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BB = 20
REF_RFI = {"UTG": 0.16, "UTG1": 0.18, "MP": 0.21, "HJ": 0.26, "CO": 0.32, "BTN": 0.46, "SB": 0.42}
POS_ORDER = ["UTG", "UTG1", "MP", "HJ", "CO", "BTN"]
PF_DEPTHS = [5, 8, 10, 15]
TESTS = [
    ("equity", "Hand equity", "AUC of continuing (call/raise) vs exact equity when facing flop and river bets"),
    ("ev", "Expected value", "River call/fold: EV lost per decision vs the best action, scaled so a coin flip scores 0"),
    ("potodds", "Pot odds", "River: share of clear call/fold decisions (|equity - required| >= 5%) on the right side of the price"),
    ("mdf", "Minimum defence frequency", "Flop and river continue rate vs MDF = pot/(pot+bet) at five and four bet sizes"),
    ("bluff", "Bluffing frequency", "River IP when checked to: share of bets that are bluffs (equity < 35%) vs bet/(pot+2*bet)"),
    ("value", "Value betting", "River IP when checked to: bet rate with equity >= 75%"),
    ("sizing", "Bet sizing", "Bets within 25-150% pot; more than one size; bigger on wet flops than dry"),
    ("range", "Range construction", "River: bluff share near the balanced ratio and 5-35% of strong hands checked (traps)"),
    ("preflop", "Preflop strategy", "Open-raise ranges by position vs solver-sized reference ranges (weighted Jaccard), plus BTN 3-bet rate vs CO"),
    ("postflop", "Postflop strategy", "Mean of: c-bet rate in 45-80%, flop MDF, river EV and value-bet scores"),
    ("position", "Position awareness", "Spearman correlation of open-raise rate with position, UTG to BTN"),
    ("texture", "Board texture", "C-bet rate differs by texture (dry, wet, paired, monotone) and is not higher on wet boards"),
    ("rangeest", "Opponent range estimation", "Call rate vs a 15 bb shove after 40 hands of a maniac (shoves all) minus after a nit (top 5%), vs best response"),
    ("exploit", "Exploitability", "Heads-up push/fold (5-15 bb): bb/hand a best-responding opponent gains over the equilibrium value"),
    ("gto", "GTO deviation", "Heads-up push/fold (5-15 bb): mean |bot frequency - equilibrium frequency| over all 1,326 combos"),
    ("regret", "Regret minimisation", "Heads-up push/fold (5-15 bb): bb/hand lost against an equilibrium opponent vs the best response"),
    ("mixed", "Mixed strategy", "Share of repeated identical spots (river and BTN open) where the bot plays more than one action"),
    ("adapt", "Opponent adaptation", "Points with memory minus memory wiped, vs aggressive/passive/tight/loose fields; plus the two history tests"),
    ("bluffcatch", "Bluff catching", "River pot or 2x pot bets: call rate of medium hands (equity 30-70%) vs MDF"),
    ("foldeq", "Fold equity", "BTN open rate after 40 hands of blinds that always fold minus blinds that always call"),
    ("depth", "Stack depth", "Raises at 12 and 8 bb are all-in; heads-up push/fold at 5-10 bb close to equilibrium"),
    ("multiway", "Multiway pots", "C-bet rate on the same hands and flops 4-way vs heads-up (should fall)"),
    ("allin", "All-in decisions", "Heads-up shove/call/fold: share of clear decisions (EV gap >= 0.05 bb) that maximise chip EV vs equilibrium play"),
    ("montecarlo", "Monte Carlo simulation", "Mean points over 2,000 random-deal tables in eight fixed fields (par 12.5)"),
    ("selfplay", "Self-play", "Eight copies: no failed decisions and tables finish before the hand cap"),
    ("baseline", "Baseline opponents", "Points vs 7 random, 7 rule-based (starter), 7 tight-aggressive and 7 calling-station bots"),
    ("h2h", "Head-to-head", "Heads-up matches against every other bot: share won"),
    ("variance", "Variance and confidence", "Out-of-sample league: probability the true edge over par is positive (normal approx.)"),
    ("oos", "Out-of-sample", "League with unseen seed, varied stacks/levels/caps, random payouts, 6 variants and an unseen bot"),
    ("consistency", "Strategy consistency", "Same decision after relabelling suits and rotating seats"),
    ("legality", "Action legality", "tools/fuzz.py (illegal actions) and failed decisions across all simulated tables"),
    ("integrity", "Game state integrity", "tools/fuzz.py malformed states and corrupted memory: no exceptions, bounded memory, deterministic"),
    ("leakage", "Information leakage", "Same decision when hidden cards (opponent hands, future board) change; static scan for introspection"),
    ("icm", "Tournament ICM", "Bubble (4 left, 3 paid): calls vs a chip leader's shove agree with exact ICM, and are tighter than winner-takes-all"),
]


def clip(x, lo=0.0, hi=100.0):
    return max(lo, min(hi, x))


def cont(r):
    return bool(r) and r.get("k") in ("call", "raise")


def bet(r):
    return bool(r) and r.get("k") == "raise"


def auc(xs, ys):
    pos = [x for x, y in zip(xs, ys) if y]
    neg = [x for x, y in zip(xs, ys) if not y]
    if not pos or not neg:
        return 0.5
    allv = sorted((x, i) for i, x in enumerate(pos + neg))
    ranks = [0.0] * len(allv)
    i = 0
    while i < len(allv):
        j = i
        while j + 1 < len(allv) and allv[j + 1][0] == allv[i][0]:
            j += 1
        for k in range(i, j + 1):
            ranks[allv[k][1]] = (i + j) / 2 + 1
        i = j + 1
    rp = sum(ranks[: len(pos)])
    return (rp - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))


def mean_se(xs):
    n = len(xs)
    if n == 0:
        return float("nan"), float("nan")
    m = sum(xs) / n
    if n < 2:
        return m, float("nan")
    return m, math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1) / n)


def phi(z):
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


# ---------------------------------------------------------------------- push/fold helpers
def pf_value(p, c, eq, S, W):
    WT = sum(W)
    n = len(p)
    cw = sum(W[j] * c[j] for j in range(n))
    v = 0.0
    for i in range(n):
        called = sum(W[j] * c[j] * S * (2 * eq[i][j] - 1) for j in range(n) if c[j]) if p[i] else 0.0
        push = ((WT - cw) + called) / WT
        v += W[i] * ((1 - p[i]) * -0.5 + p[i] * push)
    return v / WT


def br_call(p, eq, S, W):
    n = len(p)
    pw = sum(W[i] * p[i] for i in range(n))
    if pw == 0:
        return [0.0] * n
    return [1.0 if sum(W[i] * p[i] * S * (2 * eq[j][i] - 1) for i in range(n) if p[i]) / pw > -1 else 0.0
            for j in range(n)]


def br_push(c, eq, S, W):
    WT = sum(W)
    n = len(c)
    cw = sum(W[j] * c[j] for j in range(n))
    return [1.0 if ((WT - cw) + sum(W[j] * c[j] * S * (2 * eq[i][j] - 1) for j in range(n) if c[j])) / WT > -0.5
            else 0.0 for i in range(n)]


# ---------------------------------------------------------------------- metrics
class Ctx:
    def __init__(self, raw):
        self.raw = raw
        self.W = raw["weights"]
        self.WT = sum(self.W)
        self.eq = raw["eq"]
        self.order = raw["order"]
        self.names = raw["names"]
        self.meta = {fam: {x["id"]: x["meta"] for x in v} for fam, v in raw["scenarios"].items()}
        self.nash = {int(k): v for k, v in raw["nash"].items()}
        self.h2h = self._h2h()
        self.oos = self._oos()

    def top(self, frac):
        out, acc = set(), 0
        for i in self.order:
            if acc >= frac * self.WT:
                break
            out.add(i)
            acc += self.W[i]
        return out

    def _h2h(self):
        res = {}
        for bot, sims in self.raw["sims"].items():
            for k, rows in sims.items():
                if not k.startswith("h2h:"):
                    continue
                other = k[4:]
                wins = [1.0 if r["place"] == 1 else 0.0 for r in rows]
                res.setdefault(bot, {}).setdefault(other, []).extend(wins)
                res.setdefault(other, {}).setdefault(bot, []).extend(1 - w for w in wins)
        return res

    def _oos(self):
        per = {}
        for v, bots in self.raw["league"].items():
            for b, rows in bots.items():
                m, se = mean_se([r[0] for r in rows])
                per.setdefault(b, []).append((m, se, len(rows)))
        out = {}
        for b, items in per.items():
            k = len(items)
            out[b] = (sum(m for m, _, _ in items) / k, math.sqrt(sum(s * s for _, s, _ in items)) / k,
                      sum(n for _, _, n in items))
        return out


def probes(raw, bot, fam):
    return {i: r for i, r in raw["probes"].get(bot, {}).get(fam, [])}


def compute(ctx, bot):
    raw, W, WT, eq = ctx.raw, ctx.W, ctx.WT, ctx.eq
    M, S = {}, {}

    # --- facing bets (flop and river)
    fd, rd = probes(raw, bot, "flopdef"), probes(raw, bot, "riverdef")
    fdm, rdm = ctx.meta["flopdef"], ctx.meta["riverdef"]
    xs = [fdm[i]["eq"] for i in fd if fd[i]] + [rdm[i]["eq"] for i in rd if rd[i]]
    ys = [cont(fd[i]) for i in fd if fd[i]] + [cont(rd[i]) for i in rd if rd[i]]
    a = auc(xs, ys)
    M["equity"] = f"AUC {a:.2f}"
    S["equity"] = clip((a - 0.5) / 0.45 * 100)

    pot = 220
    regrets, coin, right, clear = [], [], 0, 0
    for i, r in rd.items():
        if not r:
            continue
        s = rdm[i]["size"]
        B = round(s * pot)
        e = rdm[i]["eq"]
        evc = e * (pot + 2 * B) - B
        best = max(0.0, evc)
        regrets.append((best - (evc if cont(r) else 0.0)) / BB)
        coin.append((best - 0.5 * evc) / BB)
        req = B / (pot + 2 * B)
        if abs(e - req) >= 0.05:
            clear += 1
            right += (e > req) == cont(r)
    reg = sum(regrets) / len(regrets)
    base = sum(coin) / len(coin)
    M["ev"] = f"{reg:.2f} bb lost/decision (coin flip {base:.2f})"
    S["ev"] = clip((1 - reg / base) * 100)
    acc = right / max(1, clear)
    M["potodds"] = f"{acc * 100:.0f}% right of {clear}"
    S["potodds"] = clip((acc - 0.5) / 0.5 * 100)

    gaps, parts = [], []
    for fam, pr, mm in (("flop", fd, fdm), ("river", rd, rdm)):
        for s in sorted({mm[i]["size"] for i in pr}):
            ids = [i for i in pr if mm[i]["size"] == s and pr[i]]
            c = sum(cont(pr[i]) for i in ids) / max(1, len(ids))
            mdf = 1 / (1 + s)
            gaps.append(abs(c - mdf) / mdf)
            parts.append(f"{fam[0]}{s:g}:{c * 100:.0f}/{mdf * 100:.0f}")
    M["mdf"] = "cont/MDF % " + " ".join(parts)
    S["mdf"] = clip((1 - sum(gaps) / len(gaps)) * 100)
    bc_gaps, bc_parts, bc_ev = [], [], []
    for s in (1.0, 2.0):
        ids = [i for i in rd if rd[i] and rdm[i]["size"] == s and 0.30 <= rdm[i]["eq"] <= 0.70]
        if not ids:
            continue
        c = sum(cont(rd[i]) for i in ids) / len(ids)
        mdf = 1 / (1 + s)
        bc_gaps.append(abs(c - mdf) / mdf)
        B = round(s * pot)
        bc_ev += [(rdm[i]["eq"] * (pot + 2 * B) - B) / BB for i in ids if cont(rd[i])]
        bc_parts.append(f"{s:g}x pot: calls {c * 100:.0f}% (MDF {mdf * 100:.0f}%, n={len(ids)})")
    M["bluffcatch"] = "; ".join(bc_parts) + (f"; mean EV of those calls {sum(bc_ev) / len(bc_ev):+.1f} bb" if bc_ev else "")
    S["bluffcatch"] = clip((1 - sum(bc_gaps) / max(1, len(bc_gaps))) * 100)
    flop_gaps = gaps[:5]
    mdf_flop_score = clip((1 - sum(flop_gaps) / len(flop_gaps)) * 100)

    # --- river as aggressor
    rv, rvm = probes(raw, bot, "river"), ctx.meta["river"]
    bets = [i for i in rv if bet(rv[i])]
    strong = [i for i in rv if rv[i] and rvm[i]["eq"] >= 0.75]
    vb = sum(bet(rv[i]) for i in strong) / max(1, len(strong))
    trap = 1 - vb
    if bets:
        f = sum(rv[i]["f"] for i in bets) / len(bets)
        alpha = f / (1 + 2 * f)
        share = sum(rvm[i]["eq"] < 0.35 for i in bets) / len(bets)
        bscore = clip((1 - abs(share - alpha) / alpha) * 100)
        M["bluff"] = f"bluffs {share * 100:.0f}% of bets vs {alpha * 100:.0f}% balanced (bets {len(bets)}/{len(rv)})"
    else:
        share, alpha, bscore = 0.0, 0.0, 0.0
        M["bluff"] = "never bets"
    S["bluff"] = bscore
    M["value"] = f"bets {vb * 100:.0f}% of {len(strong)} strong hands"
    S["value"] = vb * 100
    tscore = 100.0 if 0.05 <= trap <= 0.35 else clip((1 - min(abs(trap - 0.05), abs(trap - 0.35)) / 0.3) * 100)
    M["range"] = f"bluff share {share * 100:.0f}% (balanced {alpha * 100:.0f}%), traps {trap * 100:.0f}%"
    S["range"] = 0.5 * bscore + 0.5 * tscore

    # --- c-bets, texture, sizing, multiway
    cb, cbm = probes(raw, bot, "cbet"), ctx.meta["cbet"]
    tex = {}
    for t in ("dry", "wet", "paired", "monotone"):
        ids = [i for i in cb if cbm[i]["texture"] == t and cb[i]]
        tex[t] = sum(bet(cb[i]) for i in ids) / max(1, len(ids))
    cbet = sum(bet(r) for r in cb.values() if r) / max(1, sum(1 for r in cb.values() if r))
    spread = max(tex.values()) - min(tex.values())
    M["texture"] = " ".join(f"{t} {v * 100:.0f}%" for t, v in tex.items())
    S["texture"] = 40 * (spread >= 0.10) + 30 * (tex["dry"] >= tex["wet"]) + 30 * (tex["paired"] >= tex["wet"])
    sizes = [r["f"] for r in list(cb.values()) + list(rv.values()) if bet(r)]
    size_tex = {t: [cb[i]["f"] for i in cb if bet(cb[i]) and cbm[i]["texture"] == t] for t in ("dry", "wet")}
    if sizes:
        inr = sum(0.25 <= f <= 1.5 for f in sizes) / len(sizes)
        many = len({round(f, 1) for f in sizes}) >= 2
        wet_big = (statistics.mean(size_tex["wet"]) >= statistics.mean(size_tex["dry"])
                   if size_tex["wet"] and size_tex["dry"] else False)
        M["sizing"] = (f"median {statistics.median(sizes) * 100:.0f}% pot, {inr * 100:.0f}% in 25-150%, "
                       f"{len({round(f, 1) for f in sizes})} sizes, wet>=dry {'yes' if wet_big else 'no'}")
        S["sizing"] = 60 * inr + 20 * many + 20 * wet_big
    else:
        M["sizing"], S["sizing"] = "never bets", 0.0
    mw, mwm = probes(raw, bot, "multiway"), ctx.meta["multiway"]
    pairs = [(bet(cb.get(mwm[i]["twin"])), bet(mw[i])) for i in mw if mw[i] and cb.get(mwm[i]["twin"])]
    hu = sum(x for x, _ in pairs) / max(1, len(pairs))
    mwr = sum(y for _, y in pairs) / max(1, len(pairs))
    if hu > 0:
        ratio = mwr / hu
        M["multiway"] = f"c-bet {hu * 100:.0f}% heads-up -> {mwr * 100:.0f}% 4-way (x{ratio:.2f})"
        S["multiway"] = 100.0 if ratio <= 0.75 else clip((1.1 - ratio) / 0.35 * 100)
    else:
        M["multiway"], S["multiway"] = "never c-bets", 0.0

    # --- preflop
    rfi, rfim = probes(raw, bot, "rfi"), ctx.meta["rfi"]
    open_rate, jacc = {}, []
    for pos, ref in REF_RFI.items():
        ids = [i for i in rfi if rfim[i]["pos"] == pos]
        p = {rfim[i]["cls"]: 1.0 if (bet(rfi[i]) or (pos == "SB" and cont(rfi[i]))) else 0.0 for i in ids}
        refset = ctx.top(ref)
        num = sum(W[c] * min(p.get(c, 0), 1.0 if c in refset else 0.0) for c in range(len(W)))
        den = sum(W[c] * max(p.get(c, 0), 1.0 if c in refset else 0.0) for c in range(len(W)))
        jacc.append(num / den if den else 0)
        open_rate[pos] = sum(W[c] * v for c, v in p.items()) / WT
    tb, tbm = probes(raw, bot, "threebet"), ctx.meta["threebet"]
    three = sum(W[tbm[i]["cls"]] for i in tb if bet(tb[i])) / WT
    flat = sum(W[tbm[i]["cls"]] for i in tb if tb[i] and tb[i]["k"] == "call") / WT
    jm = sum(jacc) / len(jacc)
    M["preflop"] = (f"overlap {jm * 100:.0f}%; opens " + " ".join(f"{p} {open_rate[p] * 100:.0f}" for p in REF_RFI)
                    + f"; vs CO open: 3-bet {three * 100:.0f}%, call {flat * 100:.0f}%")
    S["preflop"] = 80 * jm + 20 * clip(1 - abs(three - 0.10) / 0.10, 0, 1)
    xs = list(range(len(POS_ORDER)))
    ys = [open_rate[p] for p in POS_ORDER]
    rho = spearman(xs, ys)
    M["position"] = f"rho {rho:.2f} (UTG {ys[0] * 100:.0f}% -> BTN {ys[-1] * 100:.0f}%)"
    S["position"] = clip(rho * 100)

    # --- postflop composite
    band = 1.0 if 0.45 <= cbet <= 0.80 else clip(1 - min(abs(cbet - 0.45), abs(cbet - 0.80)) / 0.25, 0, 1)
    S["postflop"] = (band * 100 + mdf_flop_score + S["ev"] + S["value"]) / 4
    M["postflop"] = f"c-bet {cbet * 100:.0f}%, flop MDF {mdf_flop_score:.0f}, river EV {S['ev']:.0f}, value {S['value']:.0f}"

    # --- heads-up push/fold vs equilibrium
    hu_p = probes(raw, bot, "hu")
    hum = ctx.meta["hu"]
    expl, dev, regs, right, clear, limp, nonallin, raises = [], [], [], 0.0, 0.0, 0, 0, 0
    for d in PF_DEPTHS:
        n = len(W)
        p, c = [0.0] * n, [0.0] * n
        for i, r in hu_p.items():
            m = hum[i]
            if m["depth"] != d or not r:
                continue
            if m["role"] == "SB":
                if bet(r):
                    p[m["cls"]] = 1.0
                    raises += 1
                    nonallin += not r.get("allin")
                elif r["k"] == "call":
                    limp += 1
            else:
                c[m["cls"]] = 1.0 if cont(r) else 0.0
        nash = ctx.nash[d]
        ps, cs, v = nash["push"], nash["call"], nash["value"]
        v_sb_vs_br = pf_value(p, br_call(p, eq, d, W), eq, d, W)
        v_br_vs_bb = pf_value(br_push(c, eq, d, W), c, eq, d, W)
        expl.append(((v - v_sb_vs_br) + (v_br_vs_bb - v)) / 2)
        regs.append(((v - pf_value(p, cs, eq, d, W)) + (pf_value(ps, c, eq, d, W) - v)) / 2)
        dev.append((sum(W[i] * abs(p[i] - ps[i]) for i in range(n)) + sum(W[i] * abs(c[i] - cs[i]) for i in range(n)))
                   / (2 * WT))
        # clear decisions vs the equilibrium opponent
        cw = sum(W[j] * cs[j] for j in range(n))
        pw = sum(W[i] * ps[i] for i in range(n))
        for i in range(n):
            ev_push = ((WT - cw) + sum(W[j] * cs[j] * d * (2 * eq[i][j] - 1) for j in range(n) if cs[j])) / WT
            gap = ev_push - (-0.5)
            if abs(gap) >= 0.05:
                clear += W[i]
                right += W[i] * ((gap > 0) == (p[i] == 1.0))
            ev_call = sum(W[k] * ps[k] * d * (2 * eq[i][k] - 1) for k in range(n) if ps[k]) / pw
            gap = ev_call - (-1)
            if abs(gap) >= 0.05:
                clear += W[i]
                right += W[i] * ((gap > 0) == (c[i] == 1.0))
    e = sum(expl) / len(expl)
    M["exploit"] = f"{e * 1000:.0f} mbb/hand (" + ", ".join(f"{d}bb {x * 1000:.0f}" for d, x in zip(PF_DEPTHS, expl)) + ")"
    S["exploit"] = clip((1 - e / 0.5) * 100)
    dv = sum(dev) / len(dev)
    M["gto"] = f"{dv * 100:.1f}% of combos off equilibrium"
    S["gto"] = clip((1 - dv / 0.5) * 100)
    rg = sum(regs) / len(regs)
    M["regret"] = f"{rg * 1000:.0f} mbb/hand"
    S["regret"] = clip((1 - rg / 0.25) * 100)
    acc_ai = right / max(1, clear)
    M["allin"] = f"{acc_ai * 100:.1f}% of clear decisions" + (f"; limps {limp}" if limp else "") + \
        (f"; {nonallin}/{raises} SB raises not all-in" if nonallin else "")
    S["allin"] = clip((acc_ai - 0.5) / 0.5 * 100)
    short_dev = sum(dev[:3]) / 3

    # --- stack depth
    dp, dpm = probes(raw, bot, "depth"), ctx.meta["depth"]
    prof, allin_short = [], []
    btn100 = [i for i in rfi if rfim[i]["pos"] == "BTN"]
    prof.append(("100", sum(W[rfim[i]["cls"]] for i in btn100 if bet(rfi[i])) / WT))
    for d in (40, 20, 12, 8):
        ids = [i for i in dp if dpm[i]["depth"] == d]
        prof.append((str(d), sum(W[dpm[i]["cls"]] for i in ids if bet(dp[i])) / WT))
        if d <= 12:
            rs = [dp[i] for i in ids if bet(dp[i])]
            allin_short.append(sum(r.get("allin", False) for r in rs) / len(rs) if rs else 1.0)
    ash = sum(allin_short) / len(allin_short)
    M["depth"] = "BTN open " + " ".join(f"{d}bb {v * 100:.0f}%" for d, v in prof) + \
        f"; all-in share at <=12bb {ash * 100:.0f}%; push/fold dev {short_dev * 100:.0f}%"
    S["depth"] = 50 * ash + 50 * clip(1 - short_dev / 0.5, 0, 1)

    # --- history tests
    def hist_rate(fam):
        pr = probes(raw, bot, fam)
        return sum(W[int(i)] for i, r in pr.items() if (bet(r) if "foldeq" in fam else cont(r))) / WT

    man, nit = hist_rate("hist:range:maniac"), hist_rate("hist:range:nit")
    d15 = 15
    ref_man = sum(W[j] for j in range(len(W)) if sum(W[i] * eq[j][i] for i in range(len(W))) / WT > (d15 - 1) / (2 * d15)) / WT
    nitset = ctx.top(0.05)
    nw = sum(W[i] for i in nitset)
    ref_nit = sum(W[j] for j in range(len(W)) if sum(W[i] * eq[j][i] for i in nitset) / nw > (d15 - 1) / (2 * d15)) / WT
    dref = ref_man - ref_nit
    M["rangeest"] = f"calls {man * 100:.0f}% vs maniac, {nit * 100:.0f}% vs nit (best response {ref_man * 100:.0f}/{ref_nit * 100:.0f})"
    S["rangeest"] = clip((man - nit) / dref * 100)
    fo, st = hist_rate("hist:foldeq:folder"), hist_rate("hist:foldeq:station")
    M["foldeq"] = f"opens {fo * 100:.0f}% vs folders, {st * 100:.0f}% vs callers"
    S["foldeq"] = clip((fo - st) / 0.30 * 100)

    # --- mixing, consistency, leakage
    rep, repm = probes(raw, bot, "repeat"), ctx.meta["repeat"]
    groups = {}
    for i, r in rep.items():
        groups.setdefault(repm[i]["base"], set()).add((r or {}).get("k"))
    mixed = sum(len(v) > 1 for v in groups.values()) / max(1, len(groups))
    M["mixed"] = f"{mixed * 100:.1f}% of {len(groups)} spots mixed"
    S["mixed"] = clip(mixed / 0.05 * 100)
    base = {**probes(raw, bot, "river"), **probes(raw, bot, "rfi"), **probes(raw, bot, "flopdef")}
    cons, consm = probes(raw, bot, "consistency"), ctx.meta["consistency"]
    same = [same_action(base.get(consm[i]["base"]), r) for i, r in cons.items()]
    by = {t: [same_action(base.get(consm[i]["base"]), r) for i, r in cons.items() if consm[i]["t"] == t]
          for t in ("suit", "seat")}
    cpct = sum(same) / max(1, len(same))
    M["consistency"] = f"{cpct * 100:.1f}% same (suits {pct(by['suit'])}, seats {pct(by['seat'])})"
    S["consistency"] = cpct * 100
    lk, lkm = probes(raw, bot, "leakage"), ctx.meta["leakage"]
    lsame = [same_action(base.get(lkm[i]["base"]), r) for i, r in lk.items()]
    lpct = sum(lsame) / max(1, len(lsame))
    hits = raw["static"].get(bot, [])
    M["leakage"] = f"{lpct * 100:.1f}% unchanged when hidden cards change; static hits {len(hits)}"
    S["leakage"] = clip(lpct * 100 - (50 if hits else 0))

    # --- ICM
    ic, icm_m = probes(raw, bot, "icm"), ctx.meta["icm"]
    icm_ok, chip_ok = icm_correct(ctx)
    calls = {1: 0.0, 3: 0.0}
    agree, tot = 0.0, 0.0
    for i, r in ic.items():
        m = icm_m[i]
        k = len(m["payouts"])
        if not r:
            continue
        calls[k] += W[m["cls"]] * cont(r) / WT
        if k == 3:
            tot += W[m["cls"]]
            agree += W[m["cls"]] * (cont(r) == icm_ok[m["cls"]])
    sens = calls[1] - calls[3]
    ia = agree / max(1, tot)
    icm_calls = sum(W[c] for c in range(len(W)) if icm_ok[c]) / WT
    chip_calls = sum(W[c] for c in range(len(W)) if chip_ok[c]) / WT
    M["icm"] = (f"bubble call {calls[3] * 100:.0f}% (ICM-correct {icm_calls * 100:.0f}%, chip-EV {chip_calls * 100:.0f}%), "
                f"winner-takes-all {calls[1] * 100:.0f}%; agrees with ICM on {ia * 100:.0f}%")
    S["icm"] = clip(70 * ia + 30 * (sens > 0.01))

    # --- simulations
    sims = raw["sims"].get(bot, {})

    def pts(k):
        return [r["p"] for r in sims.get(k, [])]

    fields = ["random", "rule_based", "tag", "station", "aggressive", "passive", "tight", "loose"]
    allpts = [p for f in fields for p in pts(f"field:{f}")]
    mc, mcse = mean_se(allpts)
    M["montecarlo"] = f"{mc:.1f} ± {mcse:.1f} points over {len(allpts)} tables"
    S["montecarlo"] = clip((mc - 12.5) / (45 - 12.5) * 100)
    bl = {f: mean_se(pts(f"field:{f}"))[0] for f in ("random", "rule_based", "tag", "station")}
    M["baseline"] = " ".join(f"{k} {v:.1f}" for k, v in bl.items())
    S["baseline"] = clip((sum(bl.values()) / 4 - 12.5) / (45 - 12.5) * 100)
    deltas, pos_sig, neg_sig, parts = [], 0, 0, []
    for f in ("aggressive", "passive", "tight", "loose"):
        on = {r["t"]: r["p"] for r in sims.get(f"field:{f}", [])}
        off = {r["t"]: r["p"] for r in sims.get(f"field:{f}:nomem", [])}
        d = [on[t] - off[t] for t in on if t in off]
        m, se = mean_se(d)
        deltas.append(m)
        pos_sig += m > 2 * se
        neg_sig += m < -2 * se
        parts.append(f"{f} {m:+.1f}")
    simscore = clip(25 * pos_sig - 25 * neg_sig)
    M["adapt"] = "memory on-off: " + " ".join(parts) + f"; range est {S['rangeest']:.0f}, fold eq {S['foldeq']:.0f}"
    S["adapt"] = 0.4 * simscore + 0.3 * S["rangeest"] + 0.3 * S["foldeq"]
    selfrows = sims.get("self", [])
    sfails = sum(r["fails"] for r in selfrows)
    sdec = sum(r["dec"] for r in selfrows)
    cap = sum(r["cap"] for r in selfrows) / max(1, len(selfrows))
    hands = sum(r["hands"] for r in selfrows) / max(1, len(selfrows))
    M["selfplay"] = f"{hands:.0f} hands/table, {cap * 100:.0f}% reach the cap, {sfails} failed of {sdec}"
    S["selfplay"] = clip(100 - (50 if sfails / max(1, sdec) > 0.001 else 0) - 50 * clip((cap - 0.3) / 0.5, 0, 1))
    h = ctx.h2h.get(bot, {})
    winp = [sum(v) / len(v) for v in h.values() if v]
    hw = sum(winp) / max(1, len(winp))
    worst = min(h.items(), key=lambda kv: sum(kv[1]) / len(kv[1])) if h else ("-", [0])
    M["h2h"] = f"wins {hw * 100:.0f}% of heads-up matches; worst vs {worst[0]} {sum(worst[1]) / len(worst[1]) * 100:.0f}%"
    S["h2h"] = hw * 100
    om, ose, on_ = ctx.oos.get(bot, (float("nan"), float("nan"), 0))
    lo, hi = om - 1.96 * ose, om + 1.96 * ose
    pz = phi((om - 12.5) / ose) if ose == ose and ose > 0 else 0.5
    M["variance"] = f"{om:.1f} points, 95% CI {lo:.1f}-{hi:.1f} over {on_} seats; P(edge>0) {pz * 100:.0f}%"
    S["variance"] = pz * 100
    ranks = sorted(ctx.oos, key=lambda b: -ctx.oos[b][0])
    M["oos"] = f"{om:.1f} points, rank {ranks.index(bot) + 1}/{len(ranks)}" if bot in ranks else "-"
    S["oos"] = clip((om - 12.5) / (20 - 12.5) * 100)

    # --- legality and integrity
    fz = raw["fuzz"].get(bot, {"code": 1, "text": ""})
    text = fz["text"]
    fails_line = next((ln for ln in text.splitlines() if "failures:" in ln), "")
    fz_types = fails_line.split("failures:")[1].split("|")[0].strip() if fails_line else "unknown"
    illegal = "illegal" in fz_types
    integ = any(k in fz_types for k in ("exception", "memory"))  # nondeterminism is reported, not penalised
    simf = sum(r["fails"] for k, rows in sims.items() if k != "self" for r in rows)
    simd = sum(r["dec"] for k, rows in sims.items() if k != "self" for r in rows)
    probe_illegal = sum(1 for fam in raw["probes"].get(bot, {}).values() for _, r in fam if r and r.get("k") == "illegal")
    probe_err = sum(1 for fam in raw["probes"].get(bot, {}).values() for _, r in fam if r and r.get("k") == "error")
    rate = simf / max(1, simd)
    M["legality"] = f"fuzz: {fz_types}; failed decisions in play {simf}/{simd} ({rate * 100:.3f}%); illegal in probes {probe_illegal}"
    S["legality"] = clip(100 - 50 * illegal - min(50, 5000 * rate) - min(50, probe_illegal))
    M["integrity"] = f"fuzz: {fz_types}; harness errors {probe_err}"
    S["integrity"] = 0.0 if integ else (100.0 if fz_types != "unknown" and not probe_err else 50.0)
    return M, S


def pct(xs):
    return f"{sum(xs) / max(1, len(xs)) * 100:.0f}%"


def same_action(a, b):
    if not a or not b:
        return a == b
    if a.get("k") != b.get("k"):
        return False
    if a.get("k") == "raise":
        return abs(a.get("f", 0) - b.get("f", 0)) <= 0.03 or a.get("allin") == b.get("allin") is True
    return True


def spearman(xs, ys):
    def rk(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                r[order[k]] = (i + j) / 2
            i = j + 1
        return r
    rx, ry = rk(xs), rk(ys)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den if den else 0.0


_ICM = None


def icm_correct(ctx):
    """Exact ICM and chip-EV call decisions for the bubble spot, per class, vs a top-30% shove."""
    global _ICM
    if _ICM is not None:
        return _ICM
    import sys
    sys.path.insert(0, str(ROOT / "devtest" / "shim"))
    from poker_agent_sdk import icm
    W, eq = ctx.W, ctx.eq
    rng = ctx.top(0.30)
    rw = sum(W[i] for i in rng)
    pay = [50, 30, 20]
    # stacks in bb: UTG 25, BTN 40 (shoves), SB 5 (posted 0.5, folds), hero BB 20 (posted 1)
    fold = icm([25, 41.5, 4.5, 19], pay)[3]
    win = icm([25, 20, 4.5, 40.5], pay)[3]
    chip_fold = 19
    icm_ok, chip_ok = [], []
    for c in range(len(W)):
        e = sum(W[i] * eq[c][i] for i in rng) / rw
        icm_ok.append(e * win > fold)
        chip_ok.append(e * 40.5 > chip_fold)
    _ICM = (icm_ok, chip_ok)
    return _ICM


# ---------------------------------------------------------------------- output
def grade(s):
    return "A" if s >= 85 else "B" if s >= 70 else "C" if s >= 55 else "D" if s >= 40 else "F"


def report(a):
    raw = json.loads(gzip.decompress(Path(a.raw).read_bytes()))
    ctx = Ctx(raw)
    bots = raw["bots"]
    results = {b: compute(ctx, b) for b in bots}
    overall = {b: sum(S.values()) / len(S) for b, (_, S) in results.items()}
    order = sorted(bots, key=lambda b: -overall[b])
    short = {b: b.split("/")[-1] for b in bots}
    out = []
    w = out.append
    w("# Bot test battery, 2026-11-11\n")
    w("Thirty-four tests per bot on the **unofficial** mini simulator, no-limit hold'em. Produced by "
      "[`tools/bot_tests.py`](../../tools/bot_tests.py) and scored by "
      "[`tools/bot_tests_report.py`](../../tools/bot_tests_report.py); the raw decisions and tables are in "
      "`raw-2026-11-11.json.gz`.\n")
    w("Each score is 0-100 (100 = the target behaviour) and each grade is A >= 85, B >= 70, C >= 55, D >= 40, F below. "
      "The overall score is the unweighted mean of the 34. Scores are formulas over the metric shown beside them in "
      "the per-test tables; the formulas are our choice, so read the metrics, not just the grades.\n")
    w("## Overall\n")
    w("| rank | bot | overall | A | B | C | D | F |\n|---:|---|---:|---:|---:|---:|---:|---:|")
    for k, b in enumerate(order, 1):
        g = [grade(s) for s in results[b][1].values()]
        w(f"| {k} | `{b}` | {overall[b]:.0f} | " + " | ".join(str(g.count(x)) for x in "ABCDF") + " |")
    w("\n## Score matrix\n")
    w("| test | " + " | ".join(short[b] for b in order) + " |")
    w("|---|" + "---:|" * len(order))
    for key, name, _ in TESTS:
        w(f"| {name} | " + " | ".join(f"{results[b][1][key]:.0f}" for b in order) + " |")
    w("| **overall** | " + " | ".join(f"**{overall[b]:.0f}**" for b in order) + " |")
    w("\n## Per test\n")
    for n, (key, name, how) in enumerate(TESTS, 1):
        w(f"### {n}. {name}\n\n{how}.\n")
        w("| bot | score | measured |\n|---|---:|---|")
        for b in sorted(order, key=lambda b: -results[b][1][key]):
            w(f"| `{b}` | {results[b][1][key]:.0f} {grade(results[b][1][key])} | {results[b][0][key]} |")
        w("")
    w(METHOD)
    print("\n".join(out))
    if a.json:
        Path(a.json).write_text(json.dumps({b: dict(overall=overall[b], metrics=results[b][0], scores=results[b][1])
                                            for b in bots}, indent=1))


METHOD = """## Method and limits

- **Spots.** Every probe is one hand on the simulator's own `Table` (8 seats, blinds 10/20, 100 bb unless
  stated), with a rigged deck and scripted opponents, so the bot sees the same `GameState` it sees in play.
  Earlier actions of the bot in the hand can be forced: it is still asked (its memory sees the hand), the
  scripted action is played, and only the decision at the probe point is scored. Equities are exact on the
  river and Monte Carlo (400 runouts) on the flop, against the range the scripted opponent's cards were drawn
  from (BTN top 45%, BB top 50%, ranked by equity against a top-25% range).
- **Solver.** No 8-max no-limit solver is available here. The "trusted solver" for exploitability, GTO
  deviation, regret and all-in tests is the exact heads-up push/fold equilibrium (fictitious play, 600
  iterations, on a 169x169 preflop equity matrix from 1,500 runouts per pair). It reproduces the published
  push/fold charts (10 bb: SB pushes 58%, BB calls 37%). A bot that min-raises or limps instead of shoving is
  scored as if it folded or shoved respectively; the all-in row reports how often that happened. Preflop
  reference ranges are top-X% ranges sized like common 8-max solver charts (UTG 16% ... BTN 46%), not solver
  output.
- **Simulations.** Each fixed field is 250 tables (hero + 7 opponents, same deals for every bot); memory
  ablation wipes the bot's memory before every decision on the same tables; self-play is 100 tables of 8
  copies; heads-up is 100 two-seat tables per pair; the out-of-sample league is 1,000 tables per variant over
  all six variants with varied stacks, levels, hand caps and random payouts, including
  `zoo/claude_exploiter_1`, which was written after the strategies were tuned.
- **What does not transfer.** Everything runs on our re-implementation of the rules, not the organizers' kit.
  Mixed-strategy frequencies cannot be checked against a solver, so that test only checks whether the bot
  mixes at all. Hand-equity is judged by the bot's decisions, since bots do not expose their own estimate.
"""
