**Priority: high, affects every version (v0, v1, v3a/live).** Research finding from the practice 2 histories (`13b7f112`, 5,000 tables). Not fixed in code: this is for whoever does development.

## The bug
`_big_blind_seat()` in `tools/core_agent.py` (line ~1124 on `pittsburgh-v2`, same function on `main`) takes the **last** `blind` event as the big blind:
```python
def _big_blind_seat(state):
    blinds = [event.seat for event in state.history if event.kind == "blind"]
    return blinds[-1] if blinds else None
```
On the platform, heads-up hands post the **big blind first and the small blind last**:

| Players left | BB posted last (code assumes) | SB posted last (BB misread) |
|---|---|---|
| Heads-up | 603 | **37,779 (98%)** |
| 3 | 27,464 | 376 |
| 4+ | 163,508 | 904 |

(Counted from our tables in practice 2.) Direct check with the kit's types: a heads-up state where we are seat 1 on the button and seat 6 is the big blind (events `blind 6 600`, `blind 1 300`) gives `_big_blind_seat = 1` and `_seats_behind = []`, both on a 2-seat table and on an 8-seat table with 6 busted.

## What it does to our play heads-up
- **On the button** the bot believes it is the big blind (`behind == 0`), so `hu_open` never applies. It uses the "big blind over limpers" path: `P["open"][0]` (8%) deep, or half a push range short, and folds the rest because a 300-into-900 call is above the 0.2 completion threshold.
- **In the big blind** it believes a seat is still behind it, so it defends less (`closing = behind == 0` is false).

Measured heads-up behaviour in practice 2 (49,885 hands):

| | us | opponents |
|---|---|---|
| Button: fold / raise / call | **75% / 22% / 4%** | 33% / 55% / 12% |
| Facing a button raise: fold / call / raise | **84% / 9% / 7%** | 64% / 35% / 1% |

By stack depth on the button: ≤10bb fold 68%, 10–15bb fold 82%, **15–30bb fold 89%, >30bb fold 88%** (where `hu_open = 0.65` should open about 65–75%).

## Cost
- We reach heads-up at **30.6%** of tables but win only **25%** of them (practice 2). Entering as chip leader we win **48.8%**; entering behind, **10.3%**.
- Our 1st-place rate: 11.4% (practice 1), **7.5%** (practice 2), against ~30% for the top 8. 2nd place pays 30, 1st pays 50.
- Rough size: at equal heads-up skill we'd win about our chip share (mean 0.43) instead of 0.25 heads-up: about +0.18 × 0.306 × 20 ≈ **+1.1 points/table** from heads-up alone. Probably more, since the same misread feeds the push/fold column and the blind-defence logic.

## Suggested fix (not applied)
Identify the big blind by amount rather than order, with a fallback for a short big blind posting all-in:
```python
def _big_blind_seat(state):
    blinds = [event for event in state.history if event.kind == "blind"]
    if not blinds:
        return None
    full = [event.seat for event in blinds if event.amount == state.blinds.big_blind]
    return full[-1] if full else max(blinds, key=lambda event: event.amount).seat
```
Edge cases to check: a big blind all-in for less than the small blind (then `max` picks the wrong seat; rare), and antes if a ruleset adds them as `blind` events.

**Check after fixing:** the same heads-up state should give `_big_blind_seat = 6` and `_seats_behind = [6]`. Then compare the button open rate in a kit run (count by the bot's actual seat: `poker-agent play` shuffles seats, so don't assume seat 0).

## Other practice 2 numbers
- Live upload was **v3a** (75,994 bytes). **43rd of 100**: 14.47 ± 0.45 (median 13.69). 0 missed in 803,861 decisions. No table reached the hand cap; payouts 50/30/20 on every table.
- Field profile still holds: top 8 play 19–32% of hands and fold to raises 67–81%. We play 15% and fold 89%.
- Kit A/Bs (zoo line-ups): v3a vs v1 on fresh seeds **+0.34 ± 0.31, not confirmed** (first seed set was +0.62 ± 0.27). v3b (aggressive settings) vs v3a −1.03 ± 0.63, not detectable. **Neither A/B exercises this bug much**: the gauntlet's tables rarely reach the misread state the way real 8-player tables do, which may be why setting changes look flat there. The real-field histories are the better evidence.

Related: #12.
