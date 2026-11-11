"""Source: Codex, this session. Profile: D. Shove-aware counterstrategy.
Notes: Range-bucket all-in calls, closing-action ICM, bounded shover tracking.

Standard hold'em only. Positional/shove policies are the user's estimates, not
solver solutions. Range-equity and tie tables use 5,000 seeded samples per cell
(tools/gen_zoo_equity.py); opponent ranges follow the starter's random-equity
ordering, not a solved shove ordering. Postflop equity remains heuristic.
Exact modeled ICM comparison only for a closing, single-opponent all-in with
reconstructable contributions and <=3 paid places; other cases use premiums.
Extra phases use the first legal minimum; variant semantics need adaptation.
Hand evaluator and class ordering copied from starter/agent.py at generation.
No runtime rollouts, external assets, mutable cross-call state, or dependencies.
"""

import json
import poker_agent_sdk
from poker_agent_sdk import Action, GameState

ADAPTIVE = False
WIDTHS = (.05, .10, .20, .35, .50, .75, 1.0)
OPEN = (.08, .55, .45, .30, .22, .18, .15, .13)
PUSH = (
    (2, (.90,.75,.55,.45,.38,.30)), (3, (.78,.60,.45,.35,.29,.23)),
    (4, (.74,.52,.38,.30,.25,.20)), (5, (.72,.46,.33,.26,.21,.17)),
    (6, (.68,.42,.29,.23,.19,.15)), (8, (.62,.36,.25,.19,.15,.12)),
    (10,(.58,.32,.22,.16,.13,.10)), (12,(.53,.28,.19,.14,.11,.09)),
    (15,(.46,.23,.16,.11,.09,.07)))


class Agent(poker_agent_sdk.Agent):
    def act(self, state: GameState, memory: bytes) -> tuple[Action, bytes]:
        if state.phase != 'betting':
            first = state.legal_actions[0]
            return Action(first.kind, first.min_amount), (memory if len(memory)<=min(2048,state.config.memory_bytes) else b'')
        notes = observe(state, memory)
        action = preflop(state, notes) if not state.board else postflop(state, notes)
        encoded = json.dumps(notes, separators=(',', ':')).encode()
        if len(encoded) > min(2048, state.config.memory_bytes):
            encoded = b''
        return legal(state, action), encoded


def passive(s):
    if s.can('check'): return Action.check()
    if s.can('fold'): return Action.fold()
    a = s.legal_actions[0]
    return Action(a.kind, a.min_amount)


def legal(s, a):
    option = s.can(a.kind)
    if option and a.kind == 'raise':
        return Action.raise_to(int(max(option.min_amount, min(option.max_amount, a.amount))))
    return a if option else passive(s)


def raise_to(s, amount):
    if s.can('raise'): return legal(s, Action.raise_to(int(amount)))
    return Action.call() if s.can('call') else passive(s)


def observe(s, memory):
    n = len(s.seats)
    try:
        d = json.loads(memory) if memory and len(memory) <= 2048 else None
        if (not isinstance(d, dict) or d.get('v') != 1 or len(d['r']) != n
            or any(not isinstance(row,list) or len(row)!=18 or any(type(x)!=int or x<0 for x in row) for row in d['r'])
            or any(len(d[k])!=n or any(type(x)!=int or x<0 for x in d[k]) for k in ('stack','start','bet'))
            or any(type(d[k])!=int or d[k]<0 for k in ('seen','sh','pf','high','step'))):
            d = None
    except (ValueError, TypeError, KeyError, IndexError):
        d = None
    if d is None:
        d = dict(v=1, r=[[0]*18 for _ in range(n)], stack=[s.config.starting_stack]*n,
                 bet=[0]*n, start=[s.config.starting_stack]*n, seen=0, sh=0, pf=0,
                 high=0, step=max(1,s.blinds.big_blind))
    # SDK events are incremental; never rescan past table history.
    events = s.events
    if len(events) > 64:
        # Drop uncertain evidence rather than infer actions across a missing prefix.
        d['pf'] = 0
        events = events[-64:]
    for e in events:
        if e.kind == 'hand':
            d.update(bet=[0]*n, start=d['stack'][:], seen=0, sh=0, pf=1,
                     high=0, step=max(1,s.blinds.big_blind))
        elif e.kind == 'board':
            d.update(pf=0, bet=[0]*n, high=0, step=max(1,s.blinds.big_blind))
        elif e.seat is not None and 0 <= e.seat < n:
            i = e.seat
            if e.kind == 'stack':
                d['stack'][i] = max(0,e.amount)
            elif e.kind == 'blind':
                d['bet'][i] += e.amount
                d['high'] = max(d['high'],d['bet'][i])
            elif e.kind in ('fold','check','call','raise'):
                old = d['bet'][i]
                facing = d['high'] > old
                depth = int(d['start'][i] > 12 * max(1,s.blinds.big_blind))
                r, off = d['r'][i], 9*depth
                if d['pf'] and i != s.seat:
                    if not d['seen'] & (1 << i):
                        r[off] += 1
                        r[off+1] += int(e.kind in ('call','raise'))
                        d['seen'] |= 1 << i
                    if facing:
                        r[off+4] += 1
                        r[off+5] += int(e.kind == 'fold')
                        r[off+6] += int(e.kind == 'call')
                    if e.kind == 'raise':
                        r[off+2] += 1
                        r[off+7] += int(e.amount == d['high']+d['step'])
                        if e.amount >= d['start'][i] and not d['sh'] & (1 << i):
                            r[off+3] += 1
                            d['sh'] |= 1 << i
                    if max(r) >= 240:
                        d['r'][i] = [x//2 for x in r]
                if e.kind == 'call': d['bet'][i] += e.amount
                elif e.kind == 'raise':
                    d['step'] = max(d['step'],e.amount-d['high'])
                    d['bet'][i] = e.amount
                    d['high'] = max(d['high'], e.amount)
    return d


def read(s, d, seat):
    p = next(p for p in s.seats if p.seat == seat)
    off = 9*int((p.stack+p.bet) > 12*max(1,s.blinds.big_blind))
    # An all-in seat's stack is now zero; classify by its remembered starting stack.
    if p.status == 'all_in':
        off = 9*int(d['start'][seat] > 12*max(1,s.blinds.big_blind))
    return d['r'][seat][off:off+9]


def range_bucket(s, d, seat):
    r = read(s,d,seat)
    if r[0] >= 16 and r[3] >= 15: return 6
    if r[0] >= 10 and r[3] >= 8: return 5
    if r[0] >= 20 and r[1] <= 2: return 0
    if r[0] < 8: return 2
    frequency = (r[3]+1)/(r[0]+5)
    return min(range(7),key=lambda i:abs(WIDTHS[i]-frequency))


def behind(s):
    alive = [p.seat for p in s.seats if p.status != 'busted']
    n = len(s.seats)
    order = sorted(alive,key=lambda i:(i-s.button-1)%n)
    if len(order) == 2: order = order[::-1]
    bb = order[1]
    cycle = sorted(alive,key=lambda i:(i-bb-1)%n)
    return sum(next(p for p in s.seats if p.seat == i).status == 'active'
               for i in cycle[cycle.index(s.seat)+1:])


def premium(s, me):
    if s.players_remaining <= 2: return 0.0
    paid = sum(p > 0 for p in s.config.payouts)
    if paid == 1: return 0.0
    if s.players_remaining == paid+1:
        others = [p.stack for p in s.seats if p.seat != s.seat and p.status != 'busted']
        return .21 if others and min(others) < .25*me.stack else .15
    return .06 if s.players_remaining <= paid else .05


def utility(stacks, hero, payouts):
    alive = [i for i,x in enumerate(stacks) if x > 0]
    pay = tuple(payouts)+(0,)*len(stacks)
    if stacks[hero] <= 0: return pay[len(alive)]
    total, h = sum(stacks), stacks[hero]
    value = pay[0]*h/total
    for i in alive:
        if i == hero: continue
        a = stacks[i]
        value += pay[1]*(a/total)*(h/(total-a))
        if pay[2]:
            for j in alive:
                if j in (hero,i): continue
                b = stacks[j]
                value += pay[2]*(a/total)*(b/(total-a))*(h/(total-a-b))
    return value


def contributions(s):
    if len(s.history)>128: return None
    n = len(s.seats)
    contributions, street = [0]*n, [0]*n
    for e in s.history:
        if e.kind == 'board':
            # The simulator returns uncalled excess without a public refund event.
            ordered = sorted(street,reverse=True)
            if len(ordered)>1 and ordered[0]>ordered[1]:
                contributions[street.index(ordered[0])] -= ordered[0]-ordered[1]
            street = [0]*n
        elif e.seat is not None and e.kind in ('blind','call','raise'):
            amount = e.amount-street[e.seat] if e.kind == 'raise' else e.amount
            contributions[e.seat] += amount
            street[e.seat] += amount
    if sum(contributions) != s.pot: return None
    return contributions


def eligible_pot(s):
    me = next(p for p in s.seats if p.seat==s.seat)
    c = min(s.to_call,me.stack)
    amounts = contributions(s)
    if amounts is not None:
        amounts[s.seat] += c
        return sum(min(x,amounts[s.seat]) for x in amounts)
    # Unknown contribution history: count only eligible current-street money.
    # Excluding earlier streets makes this fallback deliberately conservative.
    return c+sum(min(p.bet,me.bet+c) for p in s.seats)


def outcomes(s, foe):
    """Conserved closing-action stack vectors, or None for unsupported pots."""
    if any(x>0 for x in s.config.payouts[3:]): return None
    if any(p.seat not in (s.seat,foe.seat) and p.status in ('active','all_in') for p in s.seats):
        return None
    if foe.status != 'all_in': return None
    amounts = contributions(s)
    if amounts is None: return None
    c = min(s.to_call,next(p.stack for p in s.seats if p.seat==s.seat))
    amounts[s.seat] += c
    eligible = sum(min(x,amounts[s.seat]) for x in amounts)
    total = s.pot+c
    base = [p.stack for p in s.seats]
    fold = base[:]
    fold[foe.seat] += s.pot
    base[s.seat] -= c
    win, lose, tie = base[:], base[:], base[:]
    win[s.seat] += eligible
    win[foe.seat] += total-eligible
    lose[foe.seat] += total
    tie[s.seat] += eligible/2
    tie[foe.seat] += total-eligible/2
    return fold,win,lose,tie,eligible


def call_allin(s,d,key,foes):
    me = next(p for p in s.seats if p.seat==s.seat)
    equities = [_RANGE_EQUITY[key][range_bucket(s,d,p.seat)] for p in foes]
    if len(foes) == 1:
        idx = range_bucket(s,d,foes[0].seat)
        eq, ties = equities[0], _TIE_RATE[key][idx]
        modeled = outcomes(s,foes[0])
        if modeled:
            f,w,l,t,_ = modeled
            vf,vw,vl,vt = (utility(x,s.seat,s.config.payouts) for x in (f,w,l,t))
            expected = (eq-.5*ties)*vw + ties*vt + (1-eq-.5*ties)*vl
            return expected >= vf+.03*max(0,vw-vl)
    # Conservative multiway proxy; no invented exact multiway ICM or squared equity.
    eq = max(0,sum(equities)-(len(equities)-1))
    need = s.to_call/max(1,eligible_pot(s))
    return eq >= need+premium(s,me)+.03


def preflop(s,d):
    me = next(p for p in s.seats if p.seat==s.seat)
    if len(s.cards) != 2: return passive(s)
    key = _class_key(*s.cards)
    pct = _PERCENTILE[key]
    bb = max(1,s.blinds.big_blind)
    depth = (me.stack+me.bet)/bb
    rivals = [p for p in s.seats if p.seat != s.seat and p.status in ('active','all_in')]
    raises = [e for e in s.history if e.kind=='raise']
    if s.to_call and (any(p.status=='all_in' for p in rivals) or s.to_call>=.4*me.stack):
        contenders = [p for p in rivals if p.status=='all_in' or p.bet>me.bet]
        if contenders and call_allin(s,d,key,contenders): return Action.call()
        return passive(s)
    left = behind(s)
    opened = not raises
    if opened:
        limit = OPEN[min(left,7)]
        if s.players_remaining==2: limit = .80
        if ADAPTIVE and left in (1,2,3):
            # Demand evidence for every remaining opponent; conservative if a seat folded.
            fold_chance = 1.0
            for p in rivals:
                r = read(s,d,p.seat)
                fold_chance *= (r[5]+1)/(r[4]+2) if r[4]>=6 else .5
            if fold_chance>.65: limit = .95
            elif all(read(s,d,p.seat)[0]>=20 and read(s,d,p.seat)[1]<=2 for p in rivals):
                limit = min(.85,limit+.15)
        if any(range_bucket(s,d,p.seat)>=5 for p in rivals): limit *= .75
        if depth <= 12:
            col = min(5,max(0,left-1))
            row = next((row for cap,row in PUSH if depth<=cap),PUSH[-1][1])
            limit = row[col] if left else .5*row[0]
            if s.players_remaining>2 and premium(s,me)>=.15: limit *= .7
            if pct<limit: return raise_to(s,me.bet+me.stack)
        elif pct<limit:
            limpers = sum(e.kind=='call' for e in s.history)
            return raise_to(s,bb*((2 if depth<=30 or ADAPTIVE else 2.2)+limpers))
        return passive(s)
    # Ordinary raised pot: value 3-bets and cheap, in-position calls only.
    minraiser = ADAPTIVE and any((lambda r:r[2]>=8 and r[7]>=.75*r[2])(read(s,d,p.seat)) for p in rivals)
    if pct<(.05 if minraiser else .035): return raise_to(s,min(me.stack+me.bet,3*(me.bet+s.to_call)))
    if pct<(.10 if left else .20) and s.to_call<=.12*me.stack:
        return Action.call()
    return passive(s)


def postflop(s,d):
    if len(s.cards)!=2: return passive(s)
    me = next(p for p in s.seats if p.seat==s.seat)
    rivals = [p for p in s.seats if p.seat!=s.seat and p.status in ('active','all_in')]
    mine, table = hand_rank(tuple(s.cards)+tuple(s.board)), hand_rank(s.board)
    hole = [_RANK[c[0]] for c in s.cards]
    board = [_RANK[c[0]] for c in s.board]
    cat = mine[0]
    if mine==table:
        eq = .5 if len(s.board)==5 and mine[:2]==(8,14) else .23
    elif cat>=4: eq = (.90,.90,.94,.97,.99)[cat-4]
    elif cat==3: eq = .88 if table[0]<3 else .42
    elif cat==2: eq = .78 if table[0]==0 else .52
    elif cat==1:
        eq = .70 if mine[1]>max(board) else (.64 if mine[1]==max(board) else .36)
        if table[0]==1: eq=.28
    else: eq = .23 if max(hole)==14 else .12
    suits = max(sum(c[1]==x for c in s.board) for x in 'cdhs')
    if suits>=4 and cat<5: eq -= .18
    flush,straight = _draws(s.cards,s.board) if len(s.board)<5 else (False,0)
    if cat<4 and len(s.board)<5:
        outs = min(15,(9 if flush else 0)+(8 if straight==2 else 4 if straight else 0))
        p = outs/(52-len(s.cards)-len(s.board))
        if s.to_call>=me.stack or all(p.status=='all_in' for p in rivals):
            p = 1-(1-p)*(1-outs/max(1,51-len(s.cards)-len(s.board))) if len(s.board)==3 else p
        eq = max(eq,.85*p)
    eq = max(0,eq-.10*max(0,len(rivals)-1))
    station = ADAPTIVE and any((lambda r:r[4]>=10 and r[6]/max(1,r[4])>=.8)(read(s,d,p.seat)) for p in rivals)
    if not s.to_call:
        if eq>=.76 or (station and eq>=.60):
            return raise_to(s,me.bet+(.75 if station else .66)*s.pot)
        if eq>=.61 and len(rivals)==1: return raise_to(s,me.bet+.5*s.pot)
        if ADAPTIVE and len(rivals)==1 and not station and len(s.board)==3:
            dry = suits<=2 and len(set(board))>=2 and max(board)-min(board)>=6
            opener = next((e.seat for e in reversed(s.history) if e.kind=='raise'),None)
            mix = (s.hand_number*17+s.seat+sum(hole))%2==0
            if dry and opener==s.seat and (flush or straight==2 or mix):
                return raise_to(s,me.bet+s.pot/3)
        return passive(s)
    need = s.to_call/max(1,eligible_pot(s))
    margin = .10 if len(rivals)>1 else .05
    if s.to_call>=.4*me.stack: margin += premium(s,me)
    if eq>=.90 and s.can('raise'):
        return raise_to(s,me.bet+s.to_call+.66*(s.pot+s.to_call))
    return Action.call() if eq>=need+margin else passive(s)


_RANK = {rank: value for value, rank in enumerate("23456789TJQKA", 2)}


def _straight_high(ranks) -> int:
    mask = 0
    for rank in ranks:
        mask |= 1 << rank
    if mask & (1 << 14):
        mask |= 2  # the ace also plays low
    for high in range(14, 4, -1):
        if (mask >> (high - 4)) & 31 == 31:
            return high
    return 0


def hand_rank(cards) -> tuple:
    """Best five of the given cards as a tuple that compares correctly (bigger wins)."""
    ranks = sorted((_RANK[card[0]] for card in cards), reverse=True)
    by_suit: dict[str, list[int]] = {}
    for card in cards:
        by_suit.setdefault(card[1], []).append(_RANK[card[0]])
    flush = next((sorted(v, reverse=True) for v in by_suit.values() if len(v) >= 5), None)
    if flush:
        high = _straight_high(flush)
        if high:
            return (8, high)
    counts: dict[int, int] = {}
    for rank in ranks:
        counts[rank] = counts.get(rank, 0) + 1
    groups = sorted(counts.items(), key=lambda item: (item[1], item[0]), reverse=True)
    top, top_count = groups[0]
    second, second_count = groups[1] if len(groups) > 1 else (0, 0)
    if top_count == 4:
        return (7, top, max((rank for rank in ranks if rank != top), default=0))
    if top_count == 3 and second_count >= 2:
        return (6, top, second)
    if flush:
        return (5, *flush[:5])
    high = _straight_high(ranks)
    if high:
        return (4, high)
    if top_count == 3:
        return (3, top, *[rank for rank in ranks if rank != top][:2])
    if top_count == 2 and second_count == 2:
        kicker = max((rank for rank in ranks if rank != top and rank != second), default=0)
        return (2, top, second, kicker)
    if top_count == 2:
        return (1, top, *[rank for rank in ranks if rank != top][:3])
    return (0, *ranks[:5])


def _made_strength(hole, board) -> float:
    """Rough equity vs one random hand from hand category and how the hole cards contribute."""
    mine = hand_rank(tuple(hole) + tuple(board))
    table = hand_rank(board)
    hole_ranks = sorted((_RANK[card[0]] for card in hole), reverse=True)
    board_ranks = sorted((_RANK[card[0]] for card in board), reverse=True)
    top_board = board_ranks[0]
    overcards = sum(1 for rank in hole_ranks if rank > top_board)
    nothing = 0.22 + 0.05 * overcards
    category = mine[0]
    if mine == table:
        strength = 0.30  # playing the board: at best a split
    elif category >= 6:
        strength = 0.97 if table[0] < 6 else 0.85
    elif category == 5:
        suit = next(s for s in "cdhs" if sum(card[1] == s for card in tuple(hole) + tuple(board)) >= 5)
        ours = max((_RANK[card[0]] for card in hole if card[1] == suit), default=2)
        on_board = sum(card[1] == suit for card in board)
        strength = 0.93 if on_board <= 3 else 0.55 + 0.35 * (ours - 2) / 12
    elif category == 4:
        strength = 0.86
    elif category == 3:
        if table[0] == 3:
            strength = 0.45  # trips are on the board; only kickers differ
        else:
            strength = 0.90 if hole_ranks[0] == hole_ranks[-1] else 0.84
    elif category == 2:
        if table[0] == 2:
            strength = 0.40
        elif table[0] == 1:  # the board is paired and we hold one more pair
            ours = mine[1] if mine[1] != table[1] else mine[2]
            strength = 0.64 if ours >= top_board else 0.50
        else:
            strength = 0.80
    elif category == 1:
        if table[0] == 1:
            strength = nothing + 0.05  # the pair is on the board
        elif mine[1] > top_board:
            strength = 0.72 + 0.06 * (mine[1] - 2) / 12  # overpair
        elif mine[1] == top_board:
            kicker = max((rank for rank in hole_ranks if rank != top_board), default=top_board)
            strength = 0.64 + 0.08 * (kicker - 2) / 12  # top pair
        elif len(board_ranks) > 1 and mine[1] >= sorted(set(board_ranks), reverse=True)[1]:
            strength = 0.52
        else:
            strength = 0.42
    else:
        strength = nothing
    if len(board) < 5 and category < 4:
        left = 5 - len(board)
        flush_draw, straight_draw = _draws(hole, board)
        strength += (0.07 * left if flush_draw else 0.0) + 0.025 * left * straight_draw
    return min(strength, 0.97)


def _draws(hole, board) -> tuple[bool, int]:
    """(four to a flush using a hole card, straight draw: 2 open-ended, 1 gutshot, 0 none)."""
    cards = tuple(hole) + tuple(board)
    flush_draw = any(
        sum(card[1] == suit for card in cards) == 4 and any(card[1] == suit for card in hole)
        for suit in "cdhs"
    )
    mask = 0
    for card in cards:
        mask |= 1 << _RANK[card[0]]
    if mask & (1 << 14):
        mask |= 2
    completing = sum(1 for rank in range(2, 15) if _straight_high_mask(mask | 1 << rank))
    return flush_draw, 2 if completing >= 2 else completing


def _straight_high_mask(mask: int) -> bool:
    if mask & (1 << 14):
        mask |= 2
    return any((mask >> low) & 31 == 31 for low in range(1, 11))


def _has_draw(hole, board) -> bool:
    if len(board) >= 5:
        return False
    flush_draw, straight_draw = _draws(hole, board)
    return flush_draw or straight_draw == 2


# ----------------------------------------------------------------------------- preflop table
def _class_key(a: str, b: str) -> str:
    """'AKs', 'T9o', 'QQ': the 169 starting-hand classes."""
    if _RANK[a[0]] < _RANK[b[0]]:
        a, b = b, a
    if a[0] == b[0]:
        return a[0] + b[0]
    return a[0] + b[0] + ("s" if a[1] == b[1] else "o")


def _preflop_equity(cards) -> float:
    return _EQUITY[_class_key(cards[0], cards[1])]


# Equity of each class against one random hand (Monte Carlo, tools/gen_preflop.py).
_EQUITY_TABLE = "AA:846 AKs:662 AKo:649 AQs:650 AQo:649 AJs:646 AJo:641 ATs:654 ATo:630 A9s:629 A9o:614 A8s:624 A8o:593 A7s:606 A7o:590 A6s:607 A6o:578 A5s:596 A5o:579 A4s:584 A4o:564 A3s:590 A3o:546 A2s:571 A2o:540 KK:834 KQs:632 KQo:622 KJs:629 KJo:603 KTs:613 KTo:592 K9s:602 K9o:584 K8s:592 K8o:559 K7s:580 K7o:549 K6s:565 K6o:549 K5s:548 K5o:533 K4s:557 K4o:513 K3s:531 K3o:515 K2s:535 K2o:500 QQ:811 QJs:593 QJo:582 QTs:595 QTo:578 Q9s:581 Q9o:546 Q8s:557 Q8o:544 Q7s:549 Q7o:500 Q6s:540 Q6o:505 Q5s:539 Q5o:502 Q4s:526 Q4o:498 Q3s:524 Q3o:481 Q2s:504 Q2o:466 JJ:775 JTs:578 JTo:565 J9s:549 J9o:525 J8s:532 J8o:520 J7s:533 J7o:489 J6s:502 J6o:478 J5s:495 J5o:460 J4s:484 J4o:462 J3s:485 J3o:452 J2s:473 J2o:455 TT:747 T9s:551 T9o:519 T8s:519 T8o:492 T7s:507 T7o:488 T6s:491 T6o:465 T5s:472 T5o:431 T4s:457 T4o:438 T3s:457 T3o:428 T2s:456 T2o:415 99:725 98s:501 98o:486 97s:482 97o:469 96s:464 96o:442 95s:464 95o:424 94s:442 94o:402 93s:430 93o:399 92s:415 92o:399 88:684 87s:479 87o:447 86s:462 86o:441 85s:435 85o:413 84s:434 84o:389 83s:407 83o:387 82s:400 82o:374 77:669 76s:459 76o:414 75s:439 75o:406 74s:422 74o:383 73s:408 73o:367 72s:385 72o:355 66:639 65s:434 65o:396 64s:420 64o:392 63s:381 63o:349 62s:370 62o:334 55:601 54s:406 54o:381 53s:399 53o:362 52s:384 52o:343 44:561 43s:386 43o:358 42s:373 42o:324 33:545 32s:356 32o:327 22:504"

_EQUITY = {key: int(value) / 1000 for key, value in (item.split(":") for item in _EQUITY_TABLE.split())}


def _percentiles() -> dict[str, float]:
    """Fraction of all starting hands that are strictly better, weighted by combinations."""
    combos = {key: 6 if len(key) == 2 else 4 if key[2] == "s" else 12 for key in _EQUITY}
    result, better = {}, 0
    for key in sorted(_EQUITY, key=_EQUITY.__getitem__, reverse=True):
        result[key] = better / 1326
        better += combos[key]
    return result


_PERCENTILE = _percentiles()


_RANGE_EQUITY = {'AA': (0.8268, 0.8469, 0.8468, 0.8587, 0.863, 0.8506, 0.8445), 'KK': (0.7113, 0.7253, 0.7541, 0.7804, 0.8026, 0.8194, 0.8237), 'QQ': (0.6292, 0.6648, 0.6984, 0.7141, 0.7483, 0.7887, 0.7954), 'JJ': (0.5566, 0.6083, 0.6434, 0.6803, 0.7065, 0.7438, 0.766), 'TT': (0.4891, 0.5548, 0.6207, 0.6513, 0.6784, 0.7155, 0.7481), '99': (0.4454, 0.5215, 0.5772, 0.6293, 0.6446, 0.6819, 0.7314), '88': (0.3834, 0.4664, 0.5206, 0.5861, 0.6154, 0.6441, 0.692), '77': (0.3273, 0.4377, 0.5038, 0.5456, 0.5918, 0.6211, 0.6706), 'AKs': (0.4785, 0.5943, 0.6484, 0.6774, 0.668, 0.664, 0.6687), 'ATs': (0.3602, 0.4022, 0.5278, 0.6063, 0.6108, 0.6415, 0.632), 'AQs': (0.4049, 0.5216, 0.6071, 0.6331, 0.6517, 0.648, 0.6579), 'AKo': (0.4385, 0.5594, 0.6332, 0.6496, 0.6529, 0.6506, 0.6626), 'AQo': (0.379, 0.5004, 0.5858, 0.6167, 0.6438, 0.6404, 0.6372), 'AJs': (0.3941, 0.4598, 0.5678, 0.6071, 0.6327, 0.6496, 0.6594), 'AJo': (0.3623, 0.427, 0.5531, 0.593, 0.6112, 0.6409, 0.6329), '66': (0.2946, 0.3947, 0.4903, 0.5405, 0.5596, 0.5981, 0.6369), 'KQs': (0.3678, 0.4047, 0.4873, 0.5356, 0.5962, 0.6193, 0.635), 'ATo': (0.3161, 0.3646, 0.5108, 0.5722, 0.5941, 0.6201, 0.6282), 'A9s': (0.32, 0.3735, 0.5101, 0.5617, 0.5933, 0.6129, 0.6259), 'KJs': (0.3668, 0.399, 0.4554, 0.5255, 0.5686, 0.6195, 0.6226), 'A8s': (0.3359, 0.3421, 0.477, 0.5278, 0.5679, 0.5891, 0.6222), 'KQo': (0.3371, 0.3705, 0.4569, 0.5093, 0.5649, 0.5997, 0.6134), 'A9o': (0.2858, 0.3231, 0.4762, 0.5379, 0.5656, 0.5911, 0.6095), 'KTs': (0.3503, 0.3655, 0.4377, 0.5064, 0.5332, 0.5916, 0.6199), 'A6s': (0.3011, 0.3341, 0.4432, 0.5, 0.5402, 0.5779, 0.6011), 'A7s': (0.2967, 0.3348, 0.4443, 0.5295, 0.5544, 0.592, 0.6053), 'KJo': (0.3372, 0.3552, 0.4274, 0.4914, 0.5539, 0.5894, 0.6138), 'K9s': (0.3179, 0.3521, 0.3926, 0.47, 0.5249, 0.5863, 0.5924), '55': (0.3097, 0.3924, 0.4625, 0.5128, 0.5443, 0.5714, 0.5986), 'A5s': (0.3265, 0.3465, 0.4473, 0.5024, 0.5465, 0.584, 0.5914), 'QTs': (0.3563, 0.3708, 0.3963, 0.465, 0.5033, 0.5691, 0.5899), 'A8o': (0.2759, 0.3029, 0.4531, 0.5076, 0.5473, 0.5792, 0.6013), 'QJs': (0.3698, 0.3782, 0.4162, 0.4633, 0.5121, 0.5767, 0.6051), 'K8s': (0.2946, 0.3409, 0.377, 0.4517, 0.4954, 0.5553, 0.5927), 'KTo': (0.3103, 0.3376, 0.3937, 0.473, 0.531, 0.5695, 0.5982), 'A3s': (0.3125, 0.3368, 0.4319, 0.4824, 0.5254, 0.5568, 0.5949), 'A7o': (0.2587, 0.3061, 0.4188, 0.4984, 0.5339, 0.5546, 0.5828), 'A4s': (0.3163, 0.3411, 0.4416, 0.4949, 0.5282, 0.5548, 0.5952), 'K9o': (0.2861, 0.3141, 0.3587, 0.4442, 0.4993, 0.5351, 0.5739), 'QJo': (0.3377, 0.3391, 0.3773, 0.4255, 0.5005, 0.556, 0.5726), 'Q9s': (0.3276, 0.359, 0.3559, 0.4276, 0.4728, 0.5458, 0.5619), 'K7s': (0.3002, 0.3351, 0.3731, 0.4312, 0.4796, 0.545, 0.5826), 'A5o': (0.2839, 0.3032, 0.4162, 0.4789, 0.5144, 0.5512, 0.572), 'A6o': (0.2582, 0.3036, 0.4007, 0.4751, 0.5064, 0.5487, 0.5736), 'JTs': (0.3591, 0.3632, 0.4084, 0.4436, 0.4538, 0.5398, 0.5808), 'QTo': (0.3031, 0.327, 0.3621, 0.437, 0.465, 0.543, 0.5861), 'A2s': (0.3159, 0.3265, 0.4391, 0.4755, 0.5274, 0.5557, 0.5738), 'JTo': (0.3123, 0.3295, 0.353, 0.4096, 0.4383, 0.5085, 0.557), 'K6s': (0.3034, 0.336, 0.3575, 0.4265, 0.4766, 0.5318, 0.5651), 'A4o': (0.2821, 0.3006, 0.4035, 0.4694, 0.5078, 0.5515, 0.565), '44': (0.3071, 0.3871, 0.4554, 0.5084, 0.5285, 0.5459, 0.5576), 'K8o': (0.2632, 0.31, 0.3282, 0.4091, 0.4761, 0.527, 0.5569), 'K4s': (0.2915, 0.3381, 0.3634, 0.4041, 0.4483, 0.5248, 0.5451), 'Q8s': (0.3214, 0.347, 0.3661, 0.4009, 0.4498, 0.5265, 0.5659), 'T9s': (0.3272, 0.3534, 0.3804, 0.4097, 0.4219, 0.4929, 0.5404), 'J9s': (0.3278, 0.3583, 0.3817, 0.408, 0.4305, 0.5136, 0.5695), 'K6o': (0.262, 0.3055, 0.3332, 0.3892, 0.4445, 0.5139, 0.5441), 'K7o': (0.2599, 0.301, 0.3365, 0.4015, 0.4552, 0.5124, 0.5442), 'Q7s': (0.2873, 0.3433, 0.351, 0.3746, 0.4228, 0.4964, 0.5507), 'K5s': (0.2933, 0.3336, 0.3686, 0.4147, 0.4561, 0.5082, 0.5554), 'A3o': (0.2786, 0.3008, 0.3886, 0.458, 0.4919, 0.5441, 0.5583), 'Q9o': (0.2955, 0.3228, 0.3299, 0.4004, 0.436, 0.5193, 0.5583), '33': (0.2969, 0.3774, 0.4596, 0.4897, 0.5026, 0.5132, 0.5294), 'Q8o': (0.277, 0.3072, 0.311, 0.3623, 0.4219, 0.5078, 0.5404), 'A2o': (0.2727, 0.3002, 0.392, 0.4393, 0.4987, 0.5391, 0.5532), 'Q6s': (0.3069, 0.3265, 0.3575, 0.3721, 0.4203, 0.5011, 0.5312), 'Q5s': (0.2972, 0.3129, 0.3554, 0.3792, 0.4017, 0.4789, 0.5262), 'K2s': (0.2831, 0.3098, 0.3448, 0.4024, 0.4385, 0.4866, 0.5304), 'J7s': (0.2928, 0.3297, 0.355, 0.3802, 0.3871, 0.4558, 0.518), 'K5o': (0.2613, 0.2968, 0.3316, 0.3839, 0.4359, 0.4934, 0.5322), 'J8s': (0.3141, 0.3367, 0.3561, 0.3858, 0.4161, 0.5025, 0.5291), 'K3s': (0.2816, 0.3312, 0.3521, 0.4009, 0.4526, 0.5014, 0.5446), 'Q4s': (0.2963, 0.3223, 0.3319, 0.3755, 0.4079, 0.4794, 0.52), 'J9o': (0.2979, 0.3213, 0.3359, 0.3853, 0.4035, 0.4817, 0.5324), 'Q3s': (0.2892, 0.3297, 0.3348, 0.3743, 0.3906, 0.4666, 0.5118), 'J8o': (0.2724, 0.3056, 0.3244, 0.3631, 0.3855, 0.4692, 0.5193), 'T8s': (0.3186, 0.3439, 0.3704, 0.3992, 0.4118, 0.4707, 0.5275), 'T9o': (0.2944, 0.3201, 0.3483, 0.37, 0.3968, 0.4542, 0.5173), 'K3o': (0.2444, 0.2861, 0.3183, 0.3781, 0.4277, 0.4781, 0.5211), 'K4o': (0.2518, 0.2911, 0.3269, 0.3715, 0.4336, 0.5052, 0.539), 'T7s': (0.2907, 0.3304, 0.3655, 0.389, 0.3916, 0.4552, 0.5089), 'Q6o': (0.264, 0.2862, 0.3183, 0.3491, 0.4009, 0.4651, 0.5196), '22': (0.2952, 0.3764, 0.438, 0.4566, 0.4819, 0.4881, 0.5131), 'Q2s': (0.2752, 0.3138, 0.3349, 0.3577, 0.3922, 0.4427, 0.5086), 'J6s': (0.2947, 0.3159, 0.3402, 0.3609, 0.3871, 0.4534, 0.5087), 'Q5o': (0.2576, 0.2833, 0.3084, 0.3376, 0.3733, 0.439, 0.498), '98s': (0.3094, 0.3472, 0.3771, 0.4042, 0.4069, 0.4566, 0.5046), 'K2o': (0.2336, 0.2857, 0.3317, 0.357, 0.4095, 0.4615, 0.5107), 'Q7o': (0.2497, 0.2911, 0.3109, 0.3377, 0.3932, 0.4861, 0.5251), 'Q4o': (0.2555, 0.2916, 0.295, 0.328, 0.3702, 0.4397, 0.4918), 'J5s': (0.2922, 0.3072, 0.3423, 0.3677, 0.3846, 0.432, 0.4996), 'T8o': (0.2743, 0.3026, 0.335, 0.3618, 0.3815, 0.443, 0.4995), 'T6s': (0.2733, 0.313, 0.3403, 0.3687, 0.3732, 0.434, 0.488), 'J7o': (0.2506, 0.2904, 0.3223, 0.3436, 0.3809, 0.4464, 0.4903), 'T7o': (0.2457, 0.2976, 0.3223, 0.3544, 0.3519, 0.4288, 0.4797), '98o': (0.2601, 0.3104, 0.3534, 0.3665, 0.3933, 0.4221, 0.4853), 'J3s': (0.2779, 0.305, 0.3342, 0.3596, 0.3692, 0.4358, 0.4691), 'J4s': (0.2868, 0.3058, 0.3469, 0.3617, 0.3782, 0.4368, 0.5058), '97s': (0.281, 0.3439, 0.36, 0.3891, 0.3948, 0.4348, 0.4853), 'Q3o': (0.2564, 0.2771, 0.3108, 0.3231, 0.3625, 0.4259, 0.4719), '87s': (0.2852, 0.3408, 0.3812, 0.3861, 0.4011, 0.4209, 0.4837), 'J6o': (0.255, 0.2797, 0.2815, 0.3247, 0.3509, 0.4213, 0.484), 'J2s': (0.2766, 0.3014, 0.3362, 0.3499, 0.3417, 0.434, 0.481), 'T5s': (0.2707, 0.3004, 0.3373, 0.3555, 0.3694, 0.4058, 0.4693), '97o': (0.2577, 0.2999, 0.3392, 0.3421, 0.3724, 0.4025, 0.4618), 'Q2o': (0.2472, 0.2772, 0.2949, 0.3143, 0.3441, 0.4379, 0.4734), 'T6o': (0.2426, 0.2888, 0.3113, 0.3344, 0.3522, 0.4006, 0.4723), '95s': (0.2714, 0.3164, 0.3388, 0.35, 0.3744, 0.4035, 0.4685), '96s': (0.2876, 0.3233, 0.3562, 0.3774, 0.3961, 0.4065, 0.4624), '86s': (0.2877, 0.3375, 0.3601, 0.3799, 0.3963, 0.4155, 0.4526), 'J4o': (0.2334, 0.2642, 0.2973, 0.321, 0.3419, 0.4097, 0.4583), 'J5o': (0.2356, 0.279, 0.3202, 0.3268, 0.3394, 0.4104, 0.4702), '76s': (0.2735, 0.324, 0.3605, 0.392, 0.4007, 0.3927, 0.4442), 'T3s': (0.2689, 0.2976, 0.323, 0.3383, 0.3581, 0.3968, 0.4623), 'T4s': (0.2721, 0.3028, 0.3319, 0.3538, 0.3642, 0.4027, 0.4597), 'T2s': (0.2573, 0.2897, 0.327, 0.3368, 0.373, 0.391, 0.4504), 'J2o': (0.239, 0.2663, 0.2994, 0.3147, 0.3245, 0.3846, 0.4408), 'J3o': (0.247, 0.2732, 0.3039, 0.3214, 0.338, 0.3866, 0.4548), '87o': (0.2482, 0.304, 0.3377, 0.3466, 0.3801, 0.3983, 0.4494), '94s': (0.2635, 0.2971, 0.3249, 0.349, 0.3481, 0.3813, 0.4275), '96o': (0.2448, 0.2891, 0.3071, 0.3496, 0.3422, 0.3813, 0.4328), '86o': (0.2368, 0.286, 0.3322, 0.3466, 0.3583, 0.3618, 0.4347), '75s': (0.2803, 0.3202, 0.3443, 0.3888, 0.3938, 0.3952, 0.4359), 'T4o': (0.2267, 0.255, 0.2974, 0.3095, 0.333, 0.3915, 0.4347), '85s': (0.2631, 0.3251, 0.3507, 0.3672, 0.3786, 0.3887, 0.4364), '65s': (0.2825, 0.3305, 0.3702, 0.3777, 0.3813, 0.3861, 0.4216), '84s': (0.2619, 0.3021, 0.3355, 0.3562, 0.3559, 0.3734, 0.4338), 'T5o': (0.2265, 0.261, 0.3028, 0.3192, 0.3202, 0.379, 0.4407), '93s': (0.2547, 0.3033, 0.3204, 0.338, 0.3552, 0.3702, 0.4273), 'T3o': (0.2267, 0.2571, 0.3079, 0.305, 0.3271, 0.3642, 0.4271), '95o': (0.2315, 0.2825, 0.2888, 0.3306, 0.34, 0.3726, 0.4253), '74s': (0.2498, 0.3028, 0.3353, 0.3657, 0.3766, 0.3694, 0.4149), '64s': (0.2688, 0.3174, 0.3494, 0.3805, 0.378, 0.3903, 0.4139), '92s': (0.2508, 0.2996, 0.3278, 0.3279, 0.3573, 0.3793, 0.4293), 'T2o': (0.2272, 0.2592, 0.2942, 0.3066, 0.314, 0.3501, 0.4172), '76o': (0.2374, 0.3036, 0.3402, 0.3439, 0.3765, 0.3661, 0.4374), '85o': (0.232, 0.2859, 0.3022, 0.3377, 0.3402, 0.3496, 0.4099), '73s': (0.2429, 0.2984, 0.3295, 0.3432, 0.352, 0.3614, 0.3993), '83s': (0.2352, 0.2788, 0.3114, 0.3409, 0.3512, 0.3603, 0.4048), '54s': (0.2836, 0.3236, 0.3672, 0.387, 0.3915, 0.3938, 0.42), '75o': (0.2168, 0.2915, 0.3177, 0.3418, 0.3464, 0.3579, 0.3987), '94o': (0.2116, 0.2693, 0.2746, 0.3128, 0.32, 0.3488, 0.4057), '82s': (0.2402, 0.2911, 0.3195, 0.3507, 0.3497, 0.3471, 0.3925), '53s': (0.2669, 0.3165, 0.3435, 0.3659, 0.3665, 0.3849, 0.404), '92o': (0.2091, 0.2644, 0.2709, 0.2982, 0.316, 0.3338, 0.3933), '93o': (0.2228, 0.2718, 0.2895, 0.3087, 0.303, 0.3462, 0.3996), '65o': (0.2432, 0.2827, 0.3317, 0.3406, 0.3526, 0.3733, 0.3922), '64o': (0.2251, 0.2802, 0.3145, 0.3312, 0.3312, 0.351, 0.3868), '84o': (0.2153, 0.2658, 0.2952, 0.3136, 0.3241, 0.3412, 0.3864), '83o': (0.1901, 0.2543, 0.2958, 0.3077, 0.3109, 0.3372, 0.3819), '43s': (0.2629, 0.319, 0.345, 0.363, 0.3606, 0.3754, 0.3866), '72s': (0.2206, 0.2987, 0.306, 0.3305, 0.3313, 0.3535, 0.3756), '52s': (0.2474, 0.305, 0.3356, 0.3542, 0.3478, 0.3649, 0.389), '74o': (0.2142, 0.2661, 0.3141, 0.33, 0.3219, 0.3429, 0.3883), '54o': (0.2294, 0.2844, 0.3127, 0.3387, 0.359, 0.3666, 0.3791), '63s': (0.2455, 0.3085, 0.3471, 0.3554, 0.3691, 0.3641, 0.3944), '82o': (0.1954, 0.2636, 0.2859, 0.2997, 0.3133, 0.328, 0.3828), '42s': (0.2477, 0.2936, 0.324, 0.3498, 0.3403, 0.3584, 0.3695), '62s': (0.2335, 0.2941, 0.3293, 0.3385, 0.3451, 0.3485, 0.3751), '73o': (0.2036, 0.2581, 0.3037, 0.2997, 0.3183, 0.3326, 0.3749), '53o': (0.2302, 0.285, 0.3043, 0.3237, 0.3236, 0.3384, 0.36), '43o': (0.2188, 0.2753, 0.3039, 0.3217, 0.3291, 0.3233, 0.3672), '32s': (0.2557, 0.2933, 0.3253, 0.3375, 0.3471, 0.3458, 0.3705), '72o': (0.1794, 0.2444, 0.2765, 0.2907, 0.3016, 0.3134, 0.3424), '63o': (0.205, 0.2645, 0.2958, 0.3107, 0.3226, 0.3402, 0.3721), '52o': (0.22, 0.264, 0.2981, 0.3041, 0.3205, 0.325, 0.3534), '62o': (0.1874, 0.2454, 0.2875, 0.3024, 0.3081, 0.3331, 0.3383), '32o': (0.2039, 0.2577, 0.2883, 0.2985, 0.3073, 0.3158, 0.3164), '42o': (0.2079, 0.2689, 0.2909, 0.3024, 0.2996, 0.3205, 0.326)}
_TIE_RATE = {'AA': (0.0224, 0.0174, 0.0116, 0.0078, 0.008, 0.006, 0.0042), 'KK': (0.0234, 0.0098, 0.0098, 0.0064, 0.0072, 0.0048, 0.0062), 'QQ': (0.0156, 0.0148, 0.0084, 0.0074, 0.007, 0.0058, 0.0044), 'JJ': (0.0204, 0.0118, 0.0104, 0.0074, 0.0074, 0.0084, 0.006), 'TT': (0.0198, 0.014, 0.007, 0.0074, 0.008, 0.007, 0.0082), '99': (0.024, 0.0106, 0.0104, 0.007, 0.008, 0.0082, 0.0072), '88': (0.0176, 0.0116, 0.0088, 0.0082, 0.004, 0.0086, 0.0096), '77': (0.0214, 0.0126, 0.0088, 0.0072, 0.0084, 0.009, 0.0112), 'AKs': (0.1446, 0.0978, 0.0604, 0.0408, 0.0312, 0.0192, 0.0134), 'ATs': (0.0572, 0.1052, 0.0708, 0.059, 0.04, 0.0278, 0.0176), 'AQs': (0.0538, 0.1008, 0.0618, 0.043, 0.0334, 0.0252, 0.019), 'AKo': (0.159, 0.0968, 0.0656, 0.0484, 0.0306, 0.0228, 0.014), 'AQo': (0.0464, 0.11, 0.066, 0.045, 0.0344, 0.0256, 0.0144), 'AJs': (0.0198, 0.104, 0.0656, 0.0458, 0.0366, 0.0256, 0.0196), 'AJo': (0.0198, 0.1112, 0.0678, 0.0452, 0.0344, 0.0262, 0.023), '66': (0.0064, 0.0118, 0.0098, 0.0082, 0.01, 0.0102, 0.0106), 'KQs': (0.0076, 0.0346, 0.0518, 0.0352, 0.0312, 0.0262, 0.0224), 'ATo': (0.0458, 0.1104, 0.0708, 0.0516, 0.0402, 0.0266, 0.0192), 'A9s': (0.0208, 0.0606, 0.0774, 0.0658, 0.0414, 0.0346, 0.0262), 'KJs': (0.0084, 0.0292, 0.05, 0.0398, 0.0328, 0.025, 0.0216), 'A8s': (0.0202, 0.0554, 0.0808, 0.0736, 0.0514, 0.0362, 0.03), 'KQo': (0.0054, 0.0258, 0.0498, 0.041, 0.0338, 0.0246, 0.0196), 'A9o': (0.0224, 0.0518, 0.0812, 0.067, 0.0448, 0.0306, 0.0262), 'KTs': (0.0078, 0.0126, 0.051, 0.0388, 0.0408, 0.0292, 0.0266), 'A6s': (0.0202, 0.0414, 0.0692, 0.088, 0.0644, 0.0366, 0.0338), 'A7s': (0.021, 0.0356, 0.0782, 0.077, 0.0584, 0.0372, 0.0362), 'KJo': (0.0064, 0.0252, 0.054, 0.0404, 0.0374, 0.0288, 0.0216), 'K9s': (0.0086, 0.007, 0.0528, 0.0392, 0.0406, 0.0298, 0.0256), '55': (0.007, 0.0052, 0.0086, 0.01, 0.0078, 0.0088, 0.016), 'A5s': (0.0182, 0.0382, 0.0742, 0.0952, 0.0674, 0.0492, 0.0408), 'QTs': (0.0042, 0.0088, 0.0182, 0.0352, 0.0334, 0.0294, 0.0258), 'A8o': (0.023, 0.057, 0.0842, 0.0744, 0.0502, 0.0336, 0.031), 'QJs': (0.006, 0.008, 0.0384, 0.0362, 0.0366, 0.0298, 0.0226), 'K8s': (0.0064, 0.0102, 0.036, 0.0494, 0.054, 0.0358, 0.0362), 'KTo': (0.0102, 0.0096, 0.0534, 0.0376, 0.0396, 0.0262, 0.0248), 'A3s': (0.0194, 0.0412, 0.0738, 0.0988, 0.072, 0.048, 0.0378), 'A7o': (0.0202, 0.0466, 0.0808, 0.0728, 0.0634, 0.0456, 0.034), 'A4s': (0.021, 0.0358, 0.0684, 0.0962, 0.0776, 0.0436, 0.0412), 'K9o': (0.007, 0.009, 0.0518, 0.0532, 0.0426, 0.039, 0.0302), 'QJo': (0.0042, 0.0078, 0.0446, 0.0366, 0.035, 0.03, 0.026), 'Q9s': (0.0052, 0.006, 0.0138, 0.0416, 0.0468, 0.0292, 0.027), 'K7s': (0.0084, 0.0106, 0.0246, 0.0428, 0.056, 0.042, 0.0376), 'A5o': (0.0182, 0.0416, 0.0704, 0.1006, 0.0628, 0.0532, 0.0444), 'A6o': (0.0176, 0.0388, 0.067, 0.0954, 0.066, 0.055, 0.034), 'JTs': (0.0062, 0.0064, 0.0112, 0.0288, 0.0312, 0.032, 0.0232), 'QTo': (0.007, 0.008, 0.0182, 0.0368, 0.0348, 0.03, 0.027), 'A2s': (0.0174, 0.0422, 0.0658, 0.0998, 0.0736, 0.043, 0.0368), 'JTo': (0.0058, 0.007, 0.0112, 0.0264, 0.0262, 0.033, 0.0264), 'K6s': (0.0068, 0.0088, 0.0278, 0.0538, 0.06, 0.0444, 0.033), 'A4o': (0.0238, 0.0416, 0.0746, 0.112, 0.0728, 0.0478, 0.0392), '44': (0.0074, 0.005, 0.0068, 0.0084, 0.0106, 0.0082, 0.0164), 'K8o': (0.0068, 0.0064, 0.0344, 0.0534, 0.055, 0.0388, 0.037), 'K4s': (0.0074, 0.0074, 0.0268, 0.0394, 0.0666, 0.0444, 0.0414), 'Q8s': (0.0044, 0.0092, 0.0126, 0.0402, 0.0424, 0.045, 0.0286), 'T9s': (0.0068, 0.008, 0.0104, 0.0182, 0.0258, 0.039, 0.0292), 'J9s': (0.0072, 0.007, 0.0118, 0.0196, 0.031, 0.036, 0.0354), 'K6o': (0.0052, 0.0086, 0.0216, 0.0516, 0.0714, 0.0474, 0.0402), 'K7o': (0.007, 0.0096, 0.0266, 0.0566, 0.058, 0.0396, 0.0364), 'Q7s': (0.0086, 0.0082, 0.0116, 0.03, 0.0504, 0.0432, 0.0326), 'K5s': (0.0062, 0.0092, 0.0284, 0.0482, 0.0694, 0.0476, 0.0336), 'A3o': (0.022, 0.0416, 0.0764, 0.1044, 0.0714, 0.0462, 0.041), 'Q9o': (0.0058, 0.0068, 0.0134, 0.0412, 0.0392, 0.0334, 0.0322), '33': (0.0062, 0.0068, 0.008, 0.0098, 0.01, 0.0164, 0.0188), 'Q8o': (0.0048, 0.0076, 0.0108, 0.0382, 0.0514, 0.04, 0.034), 'A2o': (0.0194, 0.042, 0.0748, 0.1014, 0.0778, 0.0462, 0.0384), 'Q6s': (0.0026, 0.0058, 0.0122, 0.025, 0.0522, 0.0406, 0.0388), 'Q5s': (0.0048, 0.0054, 0.0124, 0.024, 0.0542, 0.0514, 0.0396), 'K2s': (0.0082, 0.0096, 0.026, 0.042, 0.071, 0.048, 0.0392), 'J7s': (0.0068, 0.0078, 0.012, 0.0128, 0.0282, 0.0432, 0.0368), 'K5o': (0.0054, 0.01, 0.0308, 0.0486, 0.0738, 0.048, 0.0452), 'J8s': (0.0062, 0.0078, 0.011, 0.0112, 0.0242, 0.039, 0.029), 'K3s': (0.0084, 0.0088, 0.0286, 0.0426, 0.0684, 0.0496, 0.0416), 'Q4s': (0.0066, 0.0066, 0.0154, 0.0258, 0.0518, 0.0452, 0.0428), 'J9o': (0.0062, 0.0058, 0.0114, 0.0178, 0.0286, 0.0374, 0.0328), 'Q3s': (0.0076, 0.0062, 0.012, 0.0242, 0.0552, 0.0488, 0.044), 'J8o': (0.0056, 0.0072, 0.0088, 0.0134, 0.0306, 0.0428, 0.0422), 'T8s': (0.0076, 0.007, 0.0104, 0.0144, 0.0208, 0.0366, 0.0386), 'T9o': (0.0056, 0.0074, 0.0102, 0.0132, 0.03, 0.0348, 0.0358), 'K3o': (0.0076, 0.0074, 0.0258, 0.0458, 0.0722, 0.051, 0.0402), 'K4o': (0.0072, 0.0098, 0.0226, 0.0478, 0.072, 0.0536, 0.0452), 'T7s': (0.0074, 0.0068, 0.0086, 0.0136, 0.0208, 0.0404, 0.0394), 'Q6o': (0.0044, 0.0056, 0.0106, 0.0282, 0.059, 0.0518, 0.042), '22': (0.0064, 0.0064, 0.008, 0.0088, 0.011, 0.015, 0.0174), 'Q2s': (0.006, 0.0088, 0.0106, 0.0214, 0.0548, 0.047, 0.0432), 'J6s': (0.005, 0.0086, 0.0108, 0.0134, 0.0238, 0.0412, 0.0406), 'Q5o': (0.0056, 0.005, 0.0116, 0.0264, 0.0594, 0.05, 0.04), '98s': (0.0048, 0.0088, 0.0086, 0.0124, 0.0158, 0.034, 0.0328), 'K2o': (0.0068, 0.0078, 0.0274, 0.0452, 0.0778, 0.045, 0.0422), 'Q7o': (0.007, 0.0074, 0.0114, 0.0266, 0.0568, 0.0438, 0.0338), 'Q4o': (0.0066, 0.0052, 0.0104, 0.022, 0.0552, 0.0478, 0.0416), 'J5s': (0.0056, 0.0068, 0.0086, 0.0122, 0.02, 0.0476, 0.0452), 'T8o': (0.0078, 0.0052, 0.0084, 0.0152, 0.0154, 0.0384, 0.0418), 'T6s': (0.0066, 0.0084, 0.0074, 0.0122, 0.0148, 0.0496, 0.0404), 'J7o': (0.0072, 0.0068, 0.0106, 0.0132, 0.0246, 0.048, 0.0386), 'T7o': (0.0058, 0.0068, 0.0098, 0.012, 0.0198, 0.0444, 0.039), '98o': (0.0082, 0.0064, 0.01, 0.0114, 0.0178, 0.0334, 0.0422), 'J3s': (0.0054, 0.0072, 0.01, 0.0132, 0.0208, 0.046, 0.047), 'J4s': (0.0052, 0.008, 0.0094, 0.0126, 0.0216, 0.0504, 0.0476), '97s': (0.008, 0.0074, 0.0108, 0.0102, 0.0132, 0.04, 0.039), 'Q3o': (0.006, 0.0046, 0.0124, 0.0234, 0.0562, 0.0526, 0.0438), '87s': (0.006, 0.0072, 0.0088, 0.0098, 0.0122, 0.033, 0.0438), 'J6o': (0.0064, 0.0058, 0.0078, 0.0118, 0.0178, 0.0446, 0.0452), 'J2s': (0.0068, 0.0056, 0.0084, 0.0134, 0.0182, 0.0468, 0.0452), 'T5s': (0.0066, 0.0092, 0.0098, 0.0106, 0.0192, 0.0484, 0.0414), '97o': (0.0086, 0.0066, 0.0064, 0.0086, 0.0148, 0.043, 0.046), 'Q2o': (0.0052, 0.0096, 0.0106, 0.023, 0.0566, 0.0518, 0.0364), 'T6o': (0.0072, 0.0096, 0.0074, 0.0128, 0.0168, 0.046, 0.0442), '95s': (0.0088, 0.006, 0.0092, 0.0132, 0.0132, 0.0362, 0.0454), '96s': (0.0064, 0.0062, 0.0072, 0.0108, 0.0122, 0.0338, 0.0488), '86s': (0.0074, 0.0046, 0.009, 0.009, 0.0102, 0.0342, 0.0448), 'J4o': (0.006, 0.0092, 0.0098, 0.0132, 0.021, 0.0518, 0.0442), 'J5o': (0.0056, 0.01, 0.0108, 0.0108, 0.0248, 0.054, 0.0448), '76s': (0.0066, 0.0072, 0.0058, 0.01, 0.0142, 0.0274, 0.0492), 'T3s': (0.0054, 0.0064, 0.0096, 0.0114, 0.0182, 0.0448, 0.0442), 'T4s': (0.0074, 0.0088, 0.009, 0.0124, 0.0172, 0.0494, 0.0434), 'T2s': (0.0082, 0.0078, 0.0088, 0.0124, 0.0172, 0.05, 0.0496), 'J2o': (0.0064, 0.0078, 0.0112, 0.0142, 0.0214, 0.0524, 0.0476), 'J3o': (0.0064, 0.008, 0.007, 0.0144, 0.0248, 0.0544, 0.0472), '87o': (0.0068, 0.004, 0.007, 0.0092, 0.0122, 0.0346, 0.0452), '94s': (0.0074, 0.005, 0.0086, 0.0096, 0.0142, 0.0334, 0.0502), '96o': (0.0072, 0.0054, 0.0098, 0.0092, 0.0128, 0.0414, 0.05), '86o': (0.0048, 0.006, 0.008, 0.0084, 0.0134, 0.0364, 0.0506), '75s': (0.007, 0.006, 0.0038, 0.0136, 0.0096, 0.0224, 0.0538), 'T4o': (0.007, 0.0072, 0.0092, 0.0114, 0.0156, 0.0538, 0.0542), '85s': (0.0046, 0.007, 0.0086, 0.0128, 0.0152, 0.0346, 0.052), '65s': (0.0066, 0.0058, 0.006, 0.009, 0.0138, 0.0258, 0.0516), '84s': (0.0078, 0.0078, 0.0082, 0.0112, 0.0118, 0.03, 0.0544), 'T5o': (0.0058, 0.012, 0.0092, 0.0128, 0.0164, 0.05, 0.0442), '93s': (0.0066, 0.005, 0.0092, 0.0104, 0.0176, 0.0392, 0.0478), 'T3o': (0.0078, 0.0066, 0.0078, 0.0136, 0.0154, 0.0512, 0.0494), '95o': (0.0058, 0.005, 0.0088, 0.0104, 0.0128, 0.0388, 0.0502), '74s': (0.0068, 0.008, 0.007, 0.0098, 0.0144, 0.0268, 0.0558), '64s': (0.0064, 0.0076, 0.0088, 0.0102, 0.0096, 0.0266, 0.0498), '92s': (0.0064, 0.0056, 0.008, 0.0098, 0.0142, 0.0322, 0.0418), 'T2o': (0.008, 0.0096, 0.0084, 0.0112, 0.0156, 0.0426, 0.0464), '76o': (0.0052, 0.0052, 0.0096, 0.0102, 0.0142, 0.0222, 0.0516), '85o': (0.0068, 0.0046, 0.0072, 0.0106, 0.0124, 0.0284, 0.0526), '73s': (0.0078, 0.0072, 0.0062, 0.008, 0.012, 0.026, 0.0526), '83s': (0.0064, 0.0076, 0.0088, 0.0102, 0.012, 0.0314, 0.0552), '54s': (0.0076, 0.0076, 0.0088, 0.0088, 0.0118, 0.0232, 0.0548), '75o': (0.0088, 0.0054, 0.0082, 0.0088, 0.0144, 0.0266, 0.0574), '94o': (0.0096, 0.0066, 0.0096, 0.0124, 0.01, 0.036, 0.0562), '82s': (0.0068, 0.007, 0.007, 0.0118, 0.009, 0.0254, 0.0506), '53s': (0.007, 0.0058, 0.0066, 0.0086, 0.013, 0.0186, 0.0596), '92o': (0.007, 0.008, 0.0086, 0.0108, 0.014, 0.0304, 0.0534), '93o': (0.0072, 0.0072, 0.0102, 0.0118, 0.0156, 0.0336, 0.0496), '65o': (0.0052, 0.0066, 0.0074, 0.0092, 0.0108, 0.0238, 0.058), '64o': (0.0054, 0.0052, 0.0074, 0.0084, 0.0116, 0.024, 0.0576), '84o': (0.0058, 0.0068, 0.0092, 0.0116, 0.0134, 0.0284, 0.0584), '83o': (0.0058, 0.009, 0.0068, 0.0106, 0.015, 0.0288, 0.0566), '43s': (0.0062, 0.0084, 0.006, 0.0116, 0.012, 0.0172, 0.0576), '72s': (0.0064, 0.0066, 0.0084, 0.0134, 0.0102, 0.0214, 0.0516), '52s': (0.0076, 0.0068, 0.0068, 0.0064, 0.0132, 0.0218, 0.062), '74o': (0.0084, 0.007, 0.0078, 0.0096, 0.0122, 0.0278, 0.0574), '54o': (0.006, 0.008, 0.0062, 0.0078, 0.0112, 0.0224, 0.061), '63s': (0.0066, 0.007, 0.0086, 0.008, 0.011, 0.0194, 0.0528), '82o': (0.0076, 0.0088, 0.007, 0.009, 0.0126, 0.03, 0.0588), '42s': (0.0062, 0.0068, 0.0084, 0.0076, 0.0106, 0.0184, 0.0586), '62s': (0.0058, 0.0066, 0.009, 0.0078, 0.0126, 0.0226, 0.0606), '73o': (0.0064, 0.0066, 0.0082, 0.0066, 0.0146, 0.026, 0.0562), '53o': (0.0064, 0.0072, 0.0086, 0.0122, 0.0124, 0.0216, 0.0628), '43o': (0.0048, 0.007, 0.0086, 0.0086, 0.011, 0.0206, 0.0536), '32s': (0.007, 0.0066, 0.0078, 0.0106, 0.0122, 0.0156, 0.0614), '72o': (0.0088, 0.0076, 0.0094, 0.009, 0.0116, 0.0288, 0.0576), '63o': (0.0052, 0.0042, 0.0088, 0.0078, 0.014, 0.0204, 0.0558), '52o': (0.0064, 0.0048, 0.0078, 0.0118, 0.0102, 0.022, 0.0636), '62o': (0.0076, 0.0068, 0.0046, 0.0116, 0.0122, 0.023, 0.0638), '32o': (0.0074, 0.005, 0.0074, 0.0082, 0.0106, 0.02, 0.0572), '42o': (0.007, 0.0066, 0.0066, 0.0116, 0.008, 0.0214, 0.0592)}
