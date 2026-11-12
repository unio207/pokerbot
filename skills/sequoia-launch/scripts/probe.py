"""Stage 2: see what the kit actually sends a bot, and start the Rules Card from it.

    python probe.py            # kit when installed, else the mini simulator
    python probe.py --mini

Plays a few tables with scripts/probe_bot, prints what it observed and writes
<repo>/rules_card.json with the observed `config` and phases filled in. RULES.md still has to
be read by hand: this shows the fields, not the meaning. If the kit's sandbox hides the temp
file, nothing is observed and the script says so: fill the card from RULES.md and
`sdk/agent-sdk` instead.
"""

import json
import os
import sys
import tempfile
from pathlib import Path

from common import CARD, ROOT, SKILL, practice, runner


def main() -> None:
    command, engine = runner("--mini" in sys.argv)
    out = Path(tempfile.gettempdir()) / "nl26_probe.jsonl"
    out.unlink(missing_ok=True)
    sparring = ROOT / "sparring"
    # Eight seats, as in the tournament, so config.players and the phases look like a real table.
    bots = [SKILL / "scripts" / "probe_bot", sparring / "min_raiser", sparring / "calling_station",
            sparring / "calling_station", sparring / "nit", sparring / "shover", sparring / "min_raiser",
            sparring / "check_or_fold"]  # fmt: skip
    # `--variant NAME`: on the mini simulator, play that ruleset from zoo/variants/.
    mini_name = sys.argv[sys.argv.index("--variant") + 1] if "--variant" in sys.argv and engine == "mini" else ""
    result = practice.run(command, ["play", *map(str, bots), "--tables", "6", "--seed", "probe", "--no-history",
                                    *(["--variant", mini_name] if mini_name else [])])  # fmt: skip
    if result.returncode != 0:
        sys.exit(f"runner ({engine}) failed:\n{result.stdout[-2000:]}{result.stderr[-2000:]}")
    if not out.is_file():
        sys.exit(f"runner ({engine}) played, but the probe file {out} was not written (sandboxed temp dir?).\n"
                 "Fill rules_card.json by hand from the kit's RULES.md and sdk/agent-sdk.")  # fmt: skip
    seen: dict[str, list] = {}
    for line in out.read_text().splitlines():
        kind, value = json.loads(line)
        seen.setdefault(kind, []).append(value)
    print(f"engine: {engine}\n")
    for kind in ("config", "variant", "state_fields", "seat_fields", "phase", "event", "probe_error"):
        for value in seen.get(kind, []):
            print(f"{kind}: {json.dumps(value)}")
        print()

    filled = json.loads((SKILL / "templates" / "rules_card.json").read_text())
    if CARD.is_file():
        os.replace(CARD, CARD.with_suffix(".json.bak"))
    filled["source"] = f"probe.py on the {engine}" + ("" if engine == "kit" else " (UNOFFICIAL)") + "; RULES.md not yet read"
    config = seen["config"][0] if isinstance(seen.get("config", [None])[0], dict) else {}
    filled["config_observed"] = seen.get("config", [])
    for key in filled["config"]:
        if key in config:
            value = config[key]
            if key == "blinds":
                value = [[level.get("small_blind"), level.get("big_blind"), level.get("ante", 0)] for level in value]
            filled["config"][key] = value
    if "variant" in config:
        filled["variant"]["name"] = config["variant"]
    filled["variant"]["mini_name"] = mini_name
    phases = seen.get("phase", [])
    filled["variant"]["phases"] = sorted({phase[0] for phase in phases})
    filled["variant"]["hole_cards"] = max((phase[1] for phase in phases), default=2)
    shapes = {(name, cards, board, tuple(sorted(kind for kind, _, _ in actions))) for name, cards, board, actions in phases}
    filled["variant"]["phase_shapes"] = [  # gate.py builds its clean fuzz states from these
        {"phase": name, "cards": cards, "board": board, "kinds": list(kinds)} for name, cards, board, kinds in sorted(shapes)
    ]
    filled["variant"]["state_variant_field"] = seen.get("variant", [])
    CARD.write_text(json.dumps(filled, indent=2) + "\n")
    more = len(seen.get("config", [])) > 1
    print(f"wrote {CARD}" + ("   NOTE: config differs between tables (drawn per table?): see config_observed" if more else ""))
    print("Next: read RULES.md, correct `variant`, `limits`, list `invalidates` and `open_questions`.")


if __name__ == "__main__":
    main()
