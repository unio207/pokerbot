"""Stamp one self-contained bot per profile out of the single core source.

    python3 tools/build.py            # write bots/<name>/agent.py for every profile
    python3 tools/build.py --check    # exit 1 if any bots/<name>/agent.py is missing or drifted
    options: --core PATH (default tools/core_agent.py)   --out DIR (default bots/)

Profile names are the string keys of the top-level `PROFILES = {...}` dict literal in the
core (read with `ast`; the core is never imported). Each bot is the core source with its
one top-level `ACTIVE = "..."` line replaced by `ACTIVE = "<name>"`.
"""

import argparse
import ast
import difflib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ACTIVE_LINE = re.compile(r'^ACTIVE = "[^"\n]*"[ \t]*$', re.M)


def profile_names(source: str) -> list[str]:
    for node in ast.parse(source).body:
        targets = node.targets if isinstance(node, ast.Assign) else [getattr(node, "target", None)]
        if any(isinstance(t, ast.Name) and t.id == "PROFILES" for t in targets):
            if not isinstance(node.value, ast.Dict):
                sys.exit("build: PROFILES is not a dict literal")
            keys = [k.value for k in node.value.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)]
            if len(keys) != len(node.value.keys) or not keys:
                sys.exit("build: PROFILES keys must all be string constants")
            return keys
    sys.exit("build: no top-level PROFILES dict in the core")


def stamp(source: str, name: str) -> str:
    if len(ACTIVE_LINE.findall(source)) != 1:
        sys.exit(f'build: core must contain exactly one top-level line like ACTIVE = "final" '
                 f"(found {len(ACTIVE_LINE.findall(source))})")
    return ACTIVE_LINE.sub(lambda _: f'ACTIVE = "{name}"', source)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--core", type=Path, default=ROOT / "tools" / "core_agent.py")
    parser.add_argument("--out", type=Path, default=ROOT / "bots")
    args = parser.parse_args()
    source = args.core.read_text()
    names = profile_names(source)
    bad = 0
    for name in names:
        want, path = stamp(source, name), args.out / name / "agent.py"
        if args.check:
            have = path.read_text() if path.exists() else None
            if have == want:
                continue
            bad += 1
            if have is None:
                print(f"missing: {path}")
                continue
            print(f"drifted: {path}")
            diff = difflib.unified_diff(have.splitlines(), want.splitlines(), "on disk", "expected", lineterm="")
            print("\n".join(list(diff)[:20]))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(want)
            print(f"wrote {path}")
    if args.check:
        print("ok" if not bad else f"{bad} of {len(names)} bots out of date")
        sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
