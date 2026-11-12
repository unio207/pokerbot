"""Shared by the launch scripts: repo root, the runner (kit when present, else mini), the Rules Card."""

import json
import os
import shutil
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
ROOT = SKILL.parent.parent  # <repo>/skills/sequoia-launch -> <repo>
CARD = ROOT / "rules_card.json"
sys.path.insert(0, str(ROOT))
import practice  # noqa: E402  (find_kit, lineups, run: the repo's own runner logic)


def runner(force_mini: bool = False) -> tuple[list[str], str]:
    """(command, "kit" | "mini"). The kit is used whenever its `poker-agent` exists."""
    kit = practice.find_kit()
    if not force_mini and (shutil.which(kit) or Path(kit).is_file()):
        return [kit], "kit"
    return [sys.executable, str(ROOT / "devtest" / "mini_sim.py")], "mini"


def use_sdk(force_shim: bool = False) -> str:
    """Make `import poker_agent_sdk` work in this process. Returns "kit" or "shim".

    Outside the kit's environment, restart under the kit's Python when the kit is installed,
    so bots are exercised against the real SDK classes. Without a kit: the repo's stand-in.
    """
    if not force_shim:
        try:
            import poker_agent_sdk  # noqa: F401

            return "kit"
        except ImportError:
            kit_python = Path(practice.find_kit()).parent / "python"
            if kit_python.is_file() and not os.environ.get("NL26_REEXEC"):
                os.environ["NL26_REEXEC"] = "1"
                os.execv(str(kit_python), [str(kit_python), *sys.argv])
    sys.modules.pop("poker_agent_sdk", None)
    sys.path.insert(0, str(ROOT / "devtest" / "shim"))
    return "shim"


def card() -> dict:
    """The Rules Card: <repo>/rules_card.json over the template's documented defaults."""
    merged = json.loads((SKILL / "templates" / "rules_card.json").read_text())
    merged["_filled"] = CARD.is_file()
    if CARD.is_file():
        for section, values in json.loads(CARD.read_text()).items():
            if isinstance(values, dict) and isinstance(merged.get(section), dict):
                merged[section].update(values)
            else:
                merged[section] = values
    return merged


def mini_args(card: dict, engine: str) -> list[str]:
    """`play` options only the mini simulator needs; the kit takes them from its own config.
    variant.mini_name is a ruleset name devtest/sim_variants.py plays (zoo/variants/)."""
    name = card["variant"].get("mini_name")
    return ["--variant", name] if engine == "mini" and name else []


def summary(result) -> dict:
    """The `bots` part of a runner `play` summary, or stop with the raw output.

    Assumed shape (confirmed on the mini simulator only): {"bots": {"<folder>#<index>":
    {"average_points", "places", "failed_decisions"}}}. If the kit prints something else,
    this function is the one place to adapt."""
    try:
        return json.loads(result.stdout)["bots"]
    except (ValueError, KeyError, TypeError):
        sys.exit("the runner's `play` output is not the summary these scripts expect; adapt common.summary().\n"
                 f"exit code {result.returncode}\nstdout: {result.stdout[:1500]}\nstderr: {result.stderr[:1500]}")  # fmt: skip


def bot_dir(argument: str) -> Path:
    path = Path(argument).resolve()
    path = path.parent if path.name == "agent.py" else path
    if not (path / "agent.py").is_file():
        sys.exit(f"{path} has no agent.py")
    return path
