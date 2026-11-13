"""Check the three-card preflop ranking of bots/final against dealt hands (Pittsburgh).

    python3.12 tools/preflop_check.py            # 12,000 deals per hand, about 15 s
    python3.12 tools/preflop_check.py 2000       # fewer deals

For eight chosen hands it deals a random three-card opponent and two boards, lets both sides
keep the pair the bot would keep after the turn, and measures the share of the pot won. Beside
it: the best two cards' hold'em equity (the ranking used up to v96) and `_three_card_equity`
(the fit used from v971). Exits 1 if the fit is more than 0.02 from the measured share.
"""

import importlib.util
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "devtest" / "shim"))

HANDS = (("9h", "9d", "2c"), ("5h", "5d", "Kc"), ("Ah", "Kd", "Qs"), ("Jh", "Ts", "9d"),
         ("Ah", "7c", "2d"), ("Kh", "Qh", "Jh"), ("Ah", "Ad", "7c"), ("8h", "7d", "3c"))  # fmt: skip
DECK = [rank + suit for rank in "23456789TJQKA" for suit in "cdhs"]


def load_bot():
    spec = importlib.util.spec_from_file_location("final_agent", ROOT / "bots" / "final" / "agent.py")
    bot = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bot)
    return bot


def share(bot, hero, deals, rng) -> float:
    rest = [card for card in DECK if card not in hero]
    total = 0.0
    for _ in range(deals):
        dealt = rng.sample(rest, 13)
        villain, boards = tuple(dealt[:3]), (tuple(dealt[3:8]), tuple(dealt[8:13]))
        turn = [board[:4] for board in boards]
        kept = []
        for hand in (hero, villain):
            i, j = bot.double_board_keep(hand, turn)[2]
            kept.append((hand[i], hand[j]))
        for board in boards:
            ours, theirs = bot.hand_rank(kept[0] + board), bot.hand_rank(kept[1] + board)
            total += 0.5 if ours > theirs else 0.25 if ours == theirs else 0.0
    return total / deals


def main() -> None:
    deals = int(sys.argv[1]) if len(sys.argv) > 1 else 12000
    bot, rng, worst = load_bot(), random.Random(3), 0.0
    print(f"{'hand':10s} {'measured':>9s} {'best two':>9s} {'fit':>7s} {'fit - measured':>15s}   n = {deals:,} deals per hand")
    for hero in HANDS:
        pairs = [bot._EQUITY[bot._class_key(a, b)] for i, a in enumerate(hero) for b in hero[i + 1 :]]
        measured, fit = share(bot, hero, deals, rng), bot._three_card_equity(hero)
        worst = max(worst, abs(fit - measured))
        print(f"{' '.join(hero):10s} {measured:9.3f} {max(pairs):9.3f} {fit:7.3f} {fit - measured:+15.3f}")
    print(f"largest gap between the fit and the measured share: {worst:.3f}")
    if worst > 0.02:
        sys.exit(1)


if __name__ == "__main__":
    main()
