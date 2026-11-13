"""The event clock. Run it at every stage boundary and before every upload.

    python clock.py start            # the variant was announced now
    python clock.py start 18:02      # ...or at this local time today
    python clock.py                  # T+mm:ss, stage, next snapshot, upload cutoff
"""

import sys
import time

from common import SKILL, card

T0 = SKILL / ".t0"
# (starts at minute, stage). Mirrors the table in SKILL.md.
STAGES = ((0, "1 kit + active bot"), (10, "2 Rules Card"), (18, "3 convert to the variant"),
          (38, "4 safety gate, upload v1"), (44, "5 format corrections (gauntlet beside)"),
          (48, "7 last practice-covered upload"), (52, "9 hand-off (STATE.md); no new code"))  # fmt: skip
WEIGHTS = (1, 2, 3, 5, 8, 13)  # fibonacci: how Pittsburgh scored its six rounds


def main() -> None:
    if sys.argv[1:2] == ["start"]:
        start = time.time()
        if len(sys.argv) > 2:
            hour, minute = map(int, sys.argv[2].split(":"))
            now = time.localtime()
            start = time.mktime(now[:3] + (hour, minute, 0) + now[6:])
        T0.write_text(str(start))
    if not T0.is_file():
        sys.exit("clock not started: python clock.py start [HH:MM]")
    schedule = card()["schedule"]
    minutes = (time.time() - float(T0.read_text())) / 60
    build, gap, cutoff = schedule["build_minutes"], schedule["round_gap_minutes"], schedule["upload_cutoff_minutes"]
    print(f"T+{int(minutes):d}:{int(minutes % 1 * 60):02d}")
    if minutes < build:
        print("stage", next(name for start, name in reversed(STAGES) if minutes >= start))
    for number in range(1, schedule["rounds"] + 1):
        snapshot = build + gap * (number - 1)
        if minutes < snapshot:
            left = snapshot - minutes
            state = "OPEN" if left > cutoff else "CLOSED except to replace a failing active bot"
            weight = WEIGHTS[number - 1] if number <= len(WEIGHTS) else "?"
            print(f"round {number} (weight {weight}x) snapshot in {left:.1f} min, at T+{snapshot}")
            print(f"uploads {state} (cutoff {cutoff} min before the snapshot)")
            return
    print("all snapshots taken: nothing uploaded now counts")


if __name__ == "__main__":
    main()
