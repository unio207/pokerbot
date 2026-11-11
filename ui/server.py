"""Local web UI for practising bots: build line-ups, run matches, read results, replay hands.

    python ui/server.py                # http://127.0.0.1:8765
    python ui/server.py --port 9000
    python ui/server.py --kit /path/to/kit/.venv/bin/poker-agent

Two engines:
- "kit": every table is played by the organizers' starter kit (`poker-agent play`), so the
  variant, rules and the 1 ms limit are the real ones. Used by default when `poker-agent`
  is found (start this server from the kit's activated environment, or pass --kit).
- "mini": the UNOFFICIAL simulator in devtest/mini_sim.py: hold'em and the variants in
  devtest/sim_variants.py, chosen per run. Tables are played by a pool of worker
  processes (--workers), so a run takes a few seconds.

Standard library only. Bots are re-read from disk on every run, so edit an agent.py and
click Run again; no restart needed.
"""

import argparse
import atexit
import json
import math
import os
import platform
import random
import re
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import traceback
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, wait
from concurrent.futures.process import BrokenProcessPool
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from multiprocessing import get_context
from pathlib import Path
from urllib.parse import parse_qs, urlparse

UI = Path(__file__).resolve().parent
ROOT = UI.parent
SKIP_DIRS = {"ui", "devtest", "tools", "__pycache__", "node_modules", "venv", ".venv"}
STATIC = {"/": ("index.html", "text/html"), "/index.html": ("index.html", "text/html"),
          "/app.js": ("app.js", "text/javascript"), "/style.css": ("style.css", "text/css")}  # fmt: skip
REPLAY_TABLES = 20  # tables per run that keep a full hand-by-hand replay
MAX_TABLES = 5000
KEEP_RUNS = 300  # runs kept (and reloaded from RUNS_DIR at start); replays only for the newest few
RUNS_DIR = ROOT / "practice-runs"  # one JSON file per finished run, so history survives a restart
KEEP_REPLAYS = 8
FAILURE_NOTES = 5  # first N failure details kept per entry

sys.path.insert(0, str(ROOT / "devtest"))
import mini_sim  # noqa: E402  (imported by name so worker processes can import it too)

# ---------------------------------------------------------------------------- organizers' kit
KIT: Path | None = None  # the kit's `poker-agent` executable, when found
HISTORY_DIR = ROOT / "hand-history"
VIEWER_PORT = 8766  # where the kit's replay viewer is started
KIT_CHUNKS = 9  # a kit run is split into this many `poker-agent play` calls for progress and error bars


def find_kit(explicit=None) -> Path | None:
    """The kit's `poker-agent`: --kit, $POKER_AGENT, next to this Python, on PATH, or in a
    `starter-kit` folder inside or beside this project (where the setup skill unpacks it)."""
    candidates = [explicit, os.environ.get("POKER_AGENT"),
                  Path(sys.executable).parent / "poker-agent", shutil.which("poker-agent")]  # fmt: skip
    for kit in (ROOT / "starter-kit", ROOT.parent / "starter-kit", Path.home() / "work" / "starter-kit"):
        candidates += [kit / ".venv" / "bin" / "poker-agent", kit / ".venv" / "Scripts" / "poker-agent.exe"]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate).absolute()
    return None


def find_replay() -> Path | None:
    """The kit's hand viewer command, installed beside `poker-agent`."""
    for candidate in (KIT and KIT.parent / "replay", KIT and KIT.parent / "replay.exe", shutil.which("replay")):
        if candidate and Path(candidate).is_file():
            return Path(candidate).absolute()
    return None


def kit_chunks(tables: int, replay_tables: int) -> list[tuple[int, bool]]:
    """(tables, save a hand history) per `poker-agent play` call. Only the first, small call
    saves a history, so the file stays small; the rest is split evenly."""
    chunks = []
    first = min(replay_tables, tables)
    if first:
        chunks.append((first, True))
    rest = tables - first
    if rest:
        parts = min(KIT_CHUNKS, max(1, rest // 20))
        chunks += [(rest // parts + (1 if i < rest % parts else 0), False) for i in range(parts)]
    return chunks


_viewer = {"process": None, "url": None, "file": None}


def stop_viewer() -> None:
    process = _viewer["process"]
    if process and process.poll() is None:
        process.kill()
    _viewer.update(process=None, url=None, file=None)


atexit.register(stop_viewer)


def open_viewer(history: Path) -> str:
    """Start the kit's own replay viewer on a hand-history file and return its address."""
    if _viewer["file"] == history and _viewer["process"] and _viewer["process"].poll() is None:
        return _viewer["url"]
    replay = find_replay()
    if replay is None:
        raise ValueError(f"The kit's `replay` command was not found. Run it yourself: replay {history}")
    stop_viewer()
    # A fixed port, so it can be forwarded over SSH when this runs on the build machine.
    port = VIEWER_PORT
    with socket.socket() as probe:
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            raise ValueError(f"Port {port} is in use; restart this server with another --viewer-port.") from None
    process = subprocess.Popen([str(replay), str(history), "--no-open", "--port", str(port)], cwd=ROOT,
                               stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)  # fmt: skip
    deadline = time.time() + 8
    while time.time() < deadline:
        if process.poll() is not None:
            raise ValueError("The kit's viewer stopped: " + (process.stderr.read() or "no message")[-600:])
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
            break
        except OSError:
            time.sleep(0.1)
    else:
        process.kill()
        raise ValueError("The kit's viewer did not start within 8 seconds.")
    _viewer.update(process=process, url=f"http://127.0.0.1:{port}/", file=history)
    return _viewer["url"]


# ---------------------------------------------------------------------------- bots on disk
def bot_folders() -> list[Path]:
    """Every folder at depth 1 or 2 under ROOT that holds an agent.py.

    Skips underscore-prefixed scaffolding such as zoo/_template so it never appears in
    the seat picker or random-fill pools.
    """
    found = []
    for first in sorted(ROOT.iterdir()):
        if not first.is_dir() or first.name.startswith(".") or first.name in SKIP_DIRS:
            continue
        candidates = [first] + sorted(p for p in first.iterdir() if p.is_dir()
                                      and not p.name.startswith(".") and p.name not in SKIP_DIRS)  # fmt: skip
        found += [f for f in candidates if (f / "agent.py").is_file() and f.resolve().is_relative_to(ROOT)
                  and not f.name.startswith("_")]
    return found


HEADER_RE = re.compile(r"^(Source|Profile|Variants|Notes):[ \t]*(.*)$", re.MULTILINE)


def discover_bots() -> list[dict]:
    """Every bot folder, with its group (top folder) and the header fields zoo bots carry."""
    bots = []
    for folder in bot_folders():
        agent = folder / "agent.py"
        try:
            problems = mini_sim.check(agent)
        except Exception as error:  # noqa: BLE001
            problems = [f"check failed: {error}"]
        rel = folder.relative_to(ROOT).as_posix()
        try:
            head = agent.read_text(encoding="utf-8", errors="replace")[:3000]
        except OSError:
            head = ""
        header = {key.lower(): value.strip() for key, value in HEADER_RE.findall(head)
                  if value.strip() and not value.strip().startswith("<")}  # fmt: skip
        # One line saying what the bot is: its Notes or Profile header, else the first
        # sentence of the file's docstring.
        opening = re.match(r"\s*(?:#[^\n]*\n\s*)*[rR]?(\"\"\"|\'\'\')\s*(.+?)(?:\.\s|\n\s*\n|\1)", head, re.DOTALL)
        summary = header.get("notes") or header.get("profile") or (
            " ".join(opening.group(2).split())[:200] if opening else "")
        bots.append({"path": rel, "name": folder.name, "group": rel.split("/")[0] if "/" in rel else "",
                     "modified": agent.stat().st_mtime, "problems": problems, "header": header,
                     "summary": summary})  # fmt: skip
    return bots


def resolve_bot(rel) -> Path:
    """A bot path from the browser, accepted only if it is a discovered bot inside ROOT."""
    if not isinstance(rel, str) or not rel or "\x00" in rel:
        raise ValueError("bad bot path")
    folder = (ROOT / rel).resolve()
    if not folder.is_relative_to(ROOT) or folder == ROOT:
        raise ValueError(f"{rel!r} is outside the project folder")
    if rel not in {folder.relative_to(ROOT).as_posix() for folder in bot_folders()}:
        raise ValueError(f"{rel!r} is not a bot folder (needs agent.py, at most two levels deep)")
    return folder


# ---------------------------------------------------------------------------- runs
def _int(value, low, high, name):
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a whole number") from None
    if not low <= number <= high:
        raise ValueError(f"{name} must be between {low} and {high}")
    return number


def parse_settings(body) -> dict:
    lineup = body.get("lineup")
    if not isinstance(lineup, list) or not 2 <= len(lineup) <= 10:
        raise ValueError("Pick 2 to 10 seats.")
    for rel in lineup:
        resolve_bot(rel)
    payouts = body.get("payouts", [50, 30, 20])
    if isinstance(payouts, str):
        payouts = [p for p in re.split(r"[\s,/]+", payouts.strip()) if p]
    if not isinstance(payouts, list) or not 1 <= len(payouts) <= len(lineup):
        raise ValueError("Payouts: 1 to (number of seats) values, e.g. 50 30 20.")
    payouts = [_int(p, 0, 10000, "each payout") for p in payouts]
    seed = str(body.get("seed") or "").strip() or f"{random.randrange(16**8):08x}"
    if len(seed) > 64 or not re.fullmatch(r"[A-Za-z0-9_.:-]+", seed):
        raise ValueError("Seed: up to 64 letters, digits, and _ . : - only.")
    engine = body.get("engine") or ("kit" if KIT else "mini")
    if engine not in ("kit", "mini"):
        raise ValueError("Engine must be kit or mini.")
    if engine == "kit" and KIT is None:
        raise ValueError("The organizers' kit was not found. Start this server from the kit's activated "
                         "environment (so `poker-agent` is on PATH) or pass --kit, or switch the engine "
                         "to the mini simulator.")  # fmt: skip
    variant = str(body.get("variant") or "holdem")
    if variant not in mini_sim.VARIANTS:
        raise ValueError(f"Variant must be one of: {', '.join(sorted(mini_sim.VARIANTS))}.")
    settings = {
        "engine": engine,
        # The kit plays its own variant; the choice applies to the mini simulator only.
        "variant": variant if engine == "mini" else "kit",
        "lineup": lineup,
        "tables": _int(body.get("tables", 50), 1, MAX_TABLES, "Tables"),
        "seed": seed,
        "hand_cap": _int(body.get("hand_cap", 250), 1, 2000, "Hand cap"),
        "hands_per_level": _int(body.get("hands_per_level", 20), 1, 1000, "Hands per level"),
        "stack": _int(body.get("stack", 2000), 20, 10**7, "Starting stack"),
        "payouts": payouts,
        "random_payouts": False,
        # Vary: the seed also picks the hand cap, hands per level and stack, and every table
        # draws its own payouts, so each seed is a slightly different tournament. Mini only.
        "vary": bool(body.get("vary")) and engine == "mini",
        "replay_tables": _int(body.get("replay_tables", REPLAY_TABLES), 0, 50, "Replay tables"),
    }
    if settings["vary"]:
        settings.update(mini_sim.vary_rules(seed))
    return settings


def summarize(values, weights=None):
    """(mean, standard error). `weights` are tables per value when values are chunk averages."""
    count = len(values)
    weights = weights or [1] * count
    total = sum(weights)
    mean = sum(w * v for w, v in zip(weights, values)) / total
    if count < 2:
        return mean, 0.0
    spread = sum((w * (v - mean)) ** 2 for w, v in zip(weights, values))
    return mean, math.sqrt(spread * count / (count - 1)) / total


def percentile_us(times, q):
    if not times:
        return 0.0
    return round(times[min(len(times) - 1, int(len(times) * q))] / 1000, 1)


class Run:
    def __init__(self, run_id, settings):
        self.id = run_id
        self.settings = settings
        self.status = "queued"
        self.error = None
        self.done = 0
        self.created = time.time()
        self.started = self.finished = None
        self.cancel = False
        self.results = None
        self.points = None  # per entry: points per table (mini) or per chunk (kit), for comparisons
        self.weights = None  # kit runs: tables in each chunk
        self.history_file = None  # kit runs: hand history saved by the kit, for its viewer
        self.kit_stderr = ""
        self.replays = []  # per recorded table: {table, labels, places, points, hands}
        self.bot_mtimes = {}
        self.bot_info = {}  # per bot path: summary, variants and upload-check problems when the run started
        self.file = None  # where the run is saved under RUNS_DIR

    def public(self, full=True):
        out = {"id": self.id, "status": self.status, "error": self.error, "done": self.done,
               "settings": self.settings, "created": self.created, "started": self.started,
               "finished": self.finished, "bot_mtimes": self.bot_mtimes,
               "replay_tables": len(self.replays), "kit_stderr": self.kit_stderr,
               "history_file": self.history_file and self.history_file.relative_to(ROOT).as_posix()}  # fmt: skip
        if full or self.status != "done":
            out["results"] = self.results
        else:
            out["results"] = self.results and {"entries": [
                {k: e.get(k) for k in ("label", "bot", "average_points", "se", "failed_decisions",
                                       "win_rate", "top3_rate")}
                for e in self.results["entries"]], "par": self.results["par"]}  # fmt: skip
        return out

    # The match loop mirrors mini_sim.play exactly (same per-table RNG and seat shuffle),
    # so a seed gives the same deals as `mini_sim.py play --seed`.
    def execute(self):
        s = self.settings
        self.status, self.started = "running", time.time()
        bots = [resolve_bot(rel) for rel in s["lineup"]]
        labels = [f"{bot.name}#{index}" for index, bot in enumerate(bots)]
        known = {bot["path"]: bot for bot in discover_bots()}
        for rel in dict.fromkeys(s["lineup"]):
            bot = known.get(rel, {})
            self.bot_info[rel] = {"summary": bot.get("summary", ""), "problems": bot.get("problems", []),
                                  "variants": bot.get("header", {}).get("variants", "")}  # fmt: skip
        if s["engine"] == "kit":
            return self.execute_kit(s, bots, labels)
        for bot, rel in zip(bots, s["lineup"]):
            self.bot_mtimes[rel] = (bot / "agent.py").stat().st_mtime
        n = len(bots)
        points = [[] for _ in labels]
        places = [Counter() for _ in labels]
        failures = [0] * n
        notes = [[] for _ in labels]
        latency = [[] for _ in labels]
        activity = [[0, 0, 0] for _ in labels]  # hands dealt, entered by choice, raised before the flop
        try:
            self.play_tables(s, bots, labels, points, places, failures, notes, latency, activity)
        except BrokenProcessPool:
            reset_pool()
            self.status, self.finished = "error", time.time()
            self.error = ("A worker process died while playing a table. A bot probably ended the "
                          "process (sys.exit, a crash in a C library) or ran out of memory.")  # fmt: skip
            return
        except Exception:  # noqa: BLE001
            self.status, self.finished = "error", time.time()
            self.error = "A table could not be played:\n" + traceback.format_exc(limit=-6)
            return
        self.finish(s, labels, points, places, failures, notes, latency, activity=activity)

    def execute_kit(self, s, bots, labels):
        """Play the match with the organizers' `poker-agent play`, in a few calls so there is
        progress, and so chunk averages give error bars and paired comparisons."""
        for bot, rel in zip(bots, s["lineup"]):
            self.bot_mtimes[rel] = (bot / "agent.py").stat().st_mtime
        n = len(bots)
        points = [[] for _ in labels]
        places = [Counter() for _ in labels]
        failures = [0] * n
        weights = []
        for index, (count, keep) in enumerate(kit_chunks(s["tables"], s["replay_tables"])):
            if self.cancel:
                break
            command = [str(KIT), "play", *map(str, bots), "--tables", str(count),
                       "--seed", f"{s['seed']}-c{index}", "--hand-cap", str(s["hand_cap"])]  # fmt: skip
            history = None
            if keep:
                HISTORY_DIR.mkdir(exist_ok=True)
                stamp = time.strftime("%Y%m%d-%H%M%S")
                history = HISTORY_DIR / f"ui-run{self.id}-{stamp}-{random.randrange(16**4):04x}.jsonl.gz"
                command += ["--history", str(history)]
            else:
                command.append("--no-history")
            process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            while True:
                try:
                    out, err = process.communicate(timeout=0.25)
                    break
                except subprocess.TimeoutExpired:
                    if self.cancel:
                        process.kill()
            if self.cancel:
                break
            # Keep what the bots printed; drop the kit's two lines about the saved history.
            kept = [line for line in err.splitlines() if not line.startswith(("Hand history saved", "Watch with"))]
            self.kit_stderr = ("\n".join(kept))[-4000:] or self.kit_stderr
            try:
                if process.returncode != 0:
                    raise ValueError(f"exit code {process.returncode}")
                summary = json.loads(out)["bots"]
                rows = [summary[label] for label in labels]
            except (ValueError, KeyError, TypeError) as error:
                self.status, self.finished = "error", time.time()
                self.error = f"`poker-agent play` failed ({error}).\n{(err or out)[-3000:]}"
                return
            for i, row in enumerate(rows):
                points[i].append(row["average_points"])
                failures[i] += row["failed_decisions"]
                for place, times in row["places"].items():
                    places[i][int(place)] += times
            weights.append(count)
            self.done += count
            if history and history.is_file():
                self.history_file = history
        if self.cancel:
            self.status = "cancelled"
        self.finish(s, labels, points, places, failures, [[] for _ in labels], None, weights)

    def play_tables(self, s, bots, labels, points, places, failures, notes, latency, activity):
        """Tables are played by a pool of worker processes. Each table's cards and seats come
        from (seed, table number) alone, so the result is the same as playing them in order."""
        spec = {
            "bots": [str(bot) for bot in bots], "seed": s["seed"], "token": f"run-{self.id}-{self.created}",
            "fresh": True, "notes": FAILURE_NOTES, "replay_tables": s["replay_tables"],
            "rules": {"stack": s["stack"], "decision_ms": 1, "bank_ms": 100, "hand_cap": s["hand_cap"],
                      "hands_per_level": s["hands_per_level"], "payouts": tuple(s["payouts"]),
                      "variant": s["variant"], "random_payouts": s["random_payouts"]},
        }  # fmt: skip
        pool = get_pool()
        waiting = list(range(s["tables"]))
        running = {}
        played = {}
        while waiting or running:
            if self.cancel:
                for future in running:
                    future.cancel()
                self.status = "cancelled"
                break
            while waiting and len(running) < 2 * WORKERS:
                number = waiting.pop(0)
                running[pool.submit(mini_sim.play_table, spec, number)] = number
            finished, _ = wait(running, timeout=0.2, return_when="FIRST_COMPLETED")
            for future in finished:
                played[running.pop(future)] = future.result()
                self.done = len(played)
        if self.cancel:  # keep only the unbroken run of tables from the start
            count = next((k for k in range(s["tables"]) if k not in played), s["tables"])
            played = {k: played[k] for k in range(count)}
            self.done = count
        for number in sorted(played):
            table = played[number]
            order = table["order"]
            for seat, index in enumerate(order):
                points[index].append(table["points"][seat])
                places[index][table["places"][seat]] += 1
                failures[index] += table["failures"][seat]
                latency[index].extend(table["latency"][seat])
                for k, name in enumerate(("dealt", "vpip", "pfr")):
                    activity[index][k] += table[name][seat]
            for note in table["notes"]:
                if len(notes[note["entry"]]) < FAILURE_NOTES:
                    notes[note["entry"]].append({k: note[k] for k in ("table", "hand", "reason", "detail")})
            if table["hands"] is not None:
                self.replays.append({
                    "table": number,
                    "seats": [{"label": labels[i], "bot": s["lineup"][i], "entry": i} for i in order],
                    "places": table["places"], "points": [round(p, 3) for p in table["points"]],
                    "payouts": table["payouts"], "failures": table["failures"], "hands": table["hands"],
                })  # fmt: skip

    def finish(self, s, labels, points, places, failures, notes, latency, weights=None, activity=None):
        n = len(labels)
        tables = self.done
        if tables == 0:
            self.status, self.finished = ("cancelled" if self.cancel else "error"), time.time()
            return
        kit = weights is not None
        # With too few chunks there is no spread to measure: fall back to a rule of thumb
        # (points per table swing between 0 and 50, so about 20 / sqrt(tables)).
        rough = kit and len(weights) < 4

        def stats(values):
            mean, se = summarize(values, weights)
            return mean, (20 / math.sqrt(tables) if rough else se)

        if kit:  # the kit sets the payouts; every table pays out the same total
            par = sum(summarize(points[i], weights)[0] for i in range(n)) / n
        else:
            par = (100 if s["random_payouts"] else sum(s["payouts"])) / n
        entries = []
        for i, label in enumerate(labels):
            mean, se = stats(points[i])
            times = sorted(latency[i]) if latency else []
            entries.append({
                "label": label, "bot": s["lineup"][i], "tables": tables,
                "average_points": round(mean, 3), "se": round(se, 3), "vs_par": round(mean - par, 3),
                "places": {str(k): v for k, v in sorted(places[i].items())},
                "finish_rates": {str(p): round(places[i][p] / tables, 4) for p in (1, 2, 3)},
                "win_rate": round(places[i][1] / tables, 4),
                "top3_rate": round(sum(places[i][p] for p in (1, 2, 3)) / tables, 4),
                # Share of hands entered by choice before the flop, and raised before the flop.
                "vpip": round(activity[i][1] / max(1, activity[i][0]), 4) if activity else None,
                "pfr": round(activity[i][2] / max(1, activity[i][0]), 4) if activity else None,
                # Dealt plenty of hands and never once chose to put chips in: not really playing.
                "inactive": bool(activity and activity[i][0] >= 50 and activity[i][1] == 0),
                "failed_decisions": failures[i], "failure_notes": notes[i],
                "decisions": len(times) if latency else None,
                "latency_us": {"p50": percentile_us(times, 0.5), "p99.9": percentile_us(times, 0.999),
                               "max": round(times[-1] / 1000, 1) if times else 0.0} if latency else None,
            })  # fmt: skip
        by_bot = []
        for rel in dict.fromkeys(s["lineup"]):
            idx = [i for i, b in enumerate(s["lineup"]) if b == rel]
            per_table = [sum(points[i][t] for i in idx) / len(idx) for t in range(len(points[0]))]
            mean, se = stats(per_table)
            mine = [entries[i] for i in idx]
            by_bot.append({"bot": rel, "seats": len(idx), "average_points": round(mean, 3),
                           "se": round(se, 3), "vs_par": round(mean - par, 3),
                           "win_rate": round(sum(e["win_rate"] for e in mine) / len(mine), 4),
                           "top3_rate": round(sum(e["top3_rate"] for e in mine) / len(mine), 4),
                           "vpip": round(sum(e["vpip"] for e in mine) / len(mine), 4) if activity else None,
                           "slowest_us": max(e["latency_us"]["p99.9"] for e in mine) if latency else None,
                           "inactive": any(e["inactive"] for e in mine),
                           "failed_decisions": sum(failures[i] for i in idx)})  # fmt: skip
        self.points, self.weights = points, weights
        warnings = []
        idle = sorted({entry["label"] for entry in entries if entry["inactive"]})
        if idle:
            where = "" if s["variant"] in ("holdem", "kit") else f" It probably does not support {s['variant']}."
            warnings.append(f"{', '.join(idle)} folded or checked every hand, so these results say little "
                            f"about a real field.{where}")  # fmt: skip
        if 0 < tables < 100:
            warnings.append(f"Only {tables} tables: differences under about {round(40 / math.sqrt(tables))} "
                            "points per table are noise.")  # fmt: skip
        self.results = {"par": round(par, 3), "tables": tables, "entries": entries, "by_bot": by_bot,
                        "warnings": warnings, "workers": None if kit else WORKERS,
                        "seconds": round(time.time() - self.started, 2), "engine": s["engine"],
                        "se_rough": rough, "chunks": len(weights) if kit else None}  # fmt: skip
        if self.status == "running":
            self.status = "done"
        self.finished = time.time()
        self.save()

    # ------------------------------------------------------------------ kept on disk
    def save(self) -> None:
        """Write the run (without replays) to RUNS_DIR. Failing to save never fails the run."""
        try:
            RUNS_DIR.mkdir(exist_ok=True)
            stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(self.created))
            self.file = RUNS_DIR / f"run-{stamp}-{self.id:04d}.json"
            self.file.write_text(json.dumps(self.public() | {"bot_info": self.bot_info}), encoding="utf-8")
        except OSError:
            self.file = None

    @classmethod
    def load(cls, path: Path) -> "Run":
        data = json.loads(path.read_text(encoding="utf-8"))
        run = cls(int(data["id"]), data["settings"])
        run.status, run.error, run.done = data["status"], data.get("error"), data.get("done", 0)
        run.created, run.started, run.finished = data.get("created"), data.get("started"), data.get("finished")
        run.results, run.bot_mtimes = data["results"], data.get("bot_mtimes", {})
        run.bot_info, run.kit_stderr, run.file = data.get("bot_info", {}), data.get("kit_stderr", ""), path
        if not (run.results and isinstance(run.results.get("entries"), list)):
            raise ValueError("no results")
        return run

    # ------------------------------------------------------------------ text log
    def log_text(self) -> str:
        """Everything about the run as plain text, to paste into a chat when something looks wrong."""
        s, r = self.settings, self.results
        when = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.created))
        variant = s["variant"]
        if variant in mini_sim.VARIANTS:
            variant = f"{variant} ({mini_sim.VARIANTS[variant].title})"
        payouts = "drawn per table (each a split of 100 over three places)" if s.get("random_payouts") \
            else "/".join(map(str, s["payouts"]))
        out = [
            "POKERBOT PRACTICE RUN LOG",
            f"run #{self.id}   status: {self.status}   started: {when}",
            f"engine: {'organizers kit' if s['engine'] == 'kit' else 'mini simulator (unofficial re-implementation)'}"
            f"   variant: {variant}",
            f"seed: {s['seed']}   tables: {self.done} played of {s['tables']} asked"
            + (f"   time: {r['seconds']} s   worker processes: {r.get('workers')}" if r else ""),
            f"rules: hand cap {s['hand_cap']}, {s['hands_per_level']} hands per blind level, starting stack "
            f"{s['stack']}, payouts {payouts}" + ("   (rules drawn from the seed)" if s.get("vary") else ""),
            f"python {platform.python_version()} on {platform.system()} {platform.machine()}",
            "",
            "LINE-UP (entry = bot folder # seat index in the line-up; seats are reshuffled every table)",
        ]  # fmt: skip
        labels = [f"{Path(rel).name}#{index}" for index, rel in enumerate(s["lineup"])]
        for label, rel in zip(labels, s["lineup"]):
            info = self.bot_info.get(rel, {})
            changed = self.bot_mtimes.get(rel)
            line = f"  {label:36s} {rel}"
            if changed:
                line += f"   agent.py saved {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(changed))}"
            out.append(line)
            if info.get("summary"):
                out.append(f"      about: {info['summary']}")
            if info.get("variants"):
                out.append(f"      says it supports: {info['variants']}")
            for problem in info.get("problems", []):
                out.append(f"      UPLOAD CHECK PROBLEM: {problem}")
        if self.error:
            out += ["", "ERROR", self.error.rstrip()]
        if r:
            out += ["", f"RESULTS (par = {r['par']} points per table: what an average seat scores)",
                    f"  {'entry':36s} {'pts/table':>9s} {'+-se':>6s} {'vs par':>7s} {'1st':>5s} {'top3':>5s} "
                    f"{'plays':>6s} {'raises':>6s} {'decisions':>9s} {'failed':>6s} {'p50us':>7s} {'p99.9us':>8s} "
                    f"{'maxus':>8s}  places 1st..last"]  # fmt: skip
            pct = lambda value: "-" if value is None else f"{100 * value:.0f}%"  # noqa: E731
            for e in sorted(r["entries"], key=lambda e: -e["average_points"]):
                lat = e.get("latency_us") or {}
                places = " ".join(str(e["places"].get(str(k), 0)) for k in range(1, len(labels) + 1))
                out.append(
                    f"  {e['label']:36s} {e['average_points']:9.2f} {e['se']:6.2f} {e['vs_par']:+7.2f} "
                    f"{pct(e.get('win_rate')):>5s} {pct(e.get('top3_rate')):>5s} {pct(e.get('vpip')):>6s} "
                    f"{pct(e.get('pfr')):>6s} {str(e.get('decisions') if e.get('decisions') is not None else '-'):>9s} "
                    f"{e['failed_decisions']:6d} {str(lat.get('p50', '-')):>7s} {str(lat.get('p99.9', '-')):>8s} "
                    f"{str(lat.get('max', '-')):>8s}  {places}" + ("   INACTIVE" if e.get("inactive") else ""))  # fmt: skip
            out += ["", "WARNINGS"] + ([f"  - {w}" for w in r.get("warnings", [])] or ["  none"])
            out += ["", "FAILED DECISIONS (first few per entry; each was played as check, else fold)"]
            noted = False
            for e in r["entries"]:
                if e["failed_decisions"]:
                    noted = True
                    out.append(f"  {e['label']}: {e['failed_decisions']} failed of {e.get('decisions') or '?'} decisions")
                    for note in e.get("failure_notes", []):
                        out.append(f"    table {note['table']} hand {note['hand']}: {note['reason']}")
                        out += [f"      {line}" for line in str(note["detail"]).rstrip().splitlines()]
            if not noted:
                out.append("  none")
        if self.kit_stderr:
            out += ["", "OUTPUT FROM THE KIT (stderr, last lines)", self.kit_stderr.rstrip()]
        out += [
            "",
            "HOW TO READ THIS",
            "  pts/table: average tournament points per table (default 50/30/20 for 1st/2nd/3rd, 0 below;",
            "    bots alive at the hand cap split the remaining points by ICM). +-se is its standard error:",
            "    differences smaller than about two of these are noise.",
            "  plays / raises: share of hands the bot put chips in by choice, and raised, before the flop",
            "    (VPIP / PFR). 0% means it folds or checks everything; INACTIVE marks that.",
            "  failed: decisions that raised an exception, timed out (1 ms limit, 100 ms per-table time bank)",
            "    or returned an illegal action. The real platform rejects an upload when over 10% fail in its",
            "    test match.",
            "  p50us / p99.9us / maxus: decision time in microseconds (1000 = the 1 ms limit). Times come from",
            "    this computer with several tables playing at once, so treat them as rough.",
            "  The mini simulator is our own re-implementation; variants other than holdem are our reading of",
            "    zoo/variants/*.md and include guesses.",
        ]  # fmt: skip
        return "\n".join(out) + "\n"


class Store:
    def __init__(self):
        self.lock = threading.Lock()
        self.runs: dict[int, Run] = {}
        self.queue: list[Run] = []
        self.wake = threading.Condition(self.lock)
        self.next_id = 1
        self.finished_runs = 0  # runs that produced results this session, and their tables
        self.finished_tables = 0
        for path in sorted(RUNS_DIR.glob("run-*.json"))[-KEEP_RUNS:] if RUNS_DIR.is_dir() else []:
            try:
                run = Run.load(path)
            except (OSError, ValueError, KeyError, TypeError):
                continue  # an unreadable or half-written file: leave it alone
            while run.id in self.runs:  # two sessions can both have a run #3
                run.id += 1000
            self.runs[run.id] = run
        self.next_id = max(self.runs, default=0) + 1
        threading.Thread(target=self.worker, daemon=True).start()

    def submit(self, settings) -> Run:
        with self.lock:
            run = Run(self.next_id, settings)
            self.next_id += 1
            self.runs[run.id] = run
            self.queue.append(run)
            ids = sorted(self.runs)
            for old in ids[:-KEEP_RUNS]:
                if self.runs[old].status in ("done", "error", "cancelled"):
                    del self.runs[old]
            for old in sorted(self.runs)[:-KEEP_REPLAYS]:
                self.runs[old].replays = []
            self.wake.notify()
        return run

    def worker(self):
        # One run at a time: runs share the process (and the global `random` module).
        while True:
            with self.lock:
                while not self.queue:
                    self.wake.wait()
                run = self.queue.pop(0)
            if run.cancel:
                run.status = "cancelled"
                continue
            try:
                run.execute()
            except Exception:  # noqa: BLE001
                run.status, run.error = "error", traceback.format_exc(limit=-6)
                run.finished = time.time()
            if run.results:
                self.finished_runs += 1
                self.finished_tables += run.results["tables"]

    def clear(self) -> int:
        """Forget every finished run and delete its saved file. Returns how many were removed."""
        with self.lock:
            gone = [run for run in self.runs.values() if run.status in ("done", "error", "cancelled")]
            for run in gone:
                del self.runs[run.id]
                if run.file:
                    try:
                        run.file.unlink()
                    except OSError:
                        pass
        return len(gone)

    def get(self, run_id) -> Run:
        run = self.runs.get(run_id)
        if run is None:
            raise LookupError("no such run")
        return run


def rankings(runs: list[Run]) -> dict:
    """Bots ranked across runs. Each run contributes each bot's points per table (averaged
    over its seats in that run), weighted by the run's tables. Bots are compared on points
    above par, because par depends on how many seats the table had. Runs in which a bot was
    inactive are counted in `inactive_runs` and left out of its scores."""
    bots: dict[str, dict] = {}

    def blank():
        return {"runs": 0, "tables": 0, "points": 0.0, "vs_par": 0.0, "var": 0.0, "win": 0.0, "top3": 0.0,
                "vpip": 0.0, "vpip_tables": 0, "failed": 0, "slowest": None, "inactive_runs": 0}  # fmt: skip

    def add(total, row, tables):
        if row.get("inactive"):
            # The bot folded or checked every hand in this run (it does not play the variant),
            # so the run says nothing about how good it is: count it, but leave its score out.
            total["inactive_runs"] += 1
            total["failed"] += row["failed_decisions"]
            return
        total["runs"] += 1
        total["tables"] += tables
        total["points"] += tables * row["average_points"]
        total["vs_par"] += tables * row["vs_par"]
        total["var"] += (tables * row["se"]) ** 2
        total["win"] += tables * (row.get("win_rate") or 0)
        total["top3"] += tables * (row.get("top3_rate") or 0)
        if row.get("vpip") is not None:
            total["vpip"] += tables * row["vpip"]
            total["vpip_tables"] += tables
        total["failed"] += row["failed_decisions"]
        if row.get("slowest_us") is not None:
            total["slowest"] = max(total["slowest"] or 0, row["slowest_us"])

    def done(total):
        tables = max(1, total["tables"])
        return {"runs": total["runs"], "tables": total["tables"],
                "average_points": round(total["points"] / tables, 3),
                "vs_par": round(total["vs_par"] / tables, 3), "se": round(math.sqrt(total["var"]) / tables, 3),
                "win_rate": round(total["win"] / tables, 4), "top3_rate": round(total["top3"] / tables, 4),
                "vpip": round(total["vpip"] / total["vpip_tables"], 4) if total["vpip_tables"] else None,
                "failed_decisions": total["failed"], "slowest_us": total["slowest"],
                "inactive_runs": total["inactive_runs"]}  # fmt: skip

    used = []
    for run in sorted(runs, key=lambda run: run.id):
        results = run.results
        if not results or not results.get("by_bot") or "win_rate" not in results["by_bot"][0]:
            continue
        tables, variant = results["tables"], run.settings["variant"]
        used.append({"id": run.id, "variant": variant, "tables": tables, "seed": run.settings["seed"],
                     "seats": len(run.settings["lineup"]), "par": results["par"], "created": run.created})  # fmt: skip
        for row in results["by_bot"]:
            bot = bots.setdefault(row["bot"], {"all": blank(), "variants": {}, "series": []})
            add(bot["all"], row, tables)
            add(bot["variants"].setdefault(variant, blank()), row, tables)
            bot["series"].append({"run": run.id, "variant": variant, "tables": tables, "seats": row["seats"],
                                  "average_points": row["average_points"], "vs_par": row["vs_par"],
                                  "se": row["se"], "win_rate": row.get("win_rate")})  # fmt: skip
    ranked = [{"bot": path, "name": Path(path).name, "group": path.split("/")[0] if "/" in path else ""}
              | done(bot["all"])
              | {"variants": {name: done(total) for name, total in bot["variants"].items()}, "series": bot["series"]}
              for path, bot in bots.items()]  # fmt: skip
    ranked.sort(key=lambda bot: (bot["tables"] == 0, -bot["vs_par"]))  # bots with no scored run go last
    for place, bot in enumerate(ranked, 1):
        bot["rank"] = place
    return {"bots": ranked, "runs": used, "variants": sorted({run["variant"] for run in used}),
            "tables": sum(run["tables"] for run in used)}  # fmt: skip


# ---------------------------------------------------------------------------- worker pool
WORKERS = mini_sim.default_workers(MAX_TABLES)
_pool = None


def get_pool() -> ProcessPoolExecutor:
    """Worker processes that play tables, started on the first run and kept for later ones.
    They are started fresh ("spawn"), not forked from this multi-threaded server."""
    global _pool
    if _pool is None:
        _pool = ProcessPoolExecutor(WORKERS, mp_context=get_context("spawn"))
    return _pool


def reset_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.shutdown(wait=False, cancel_futures=True)
    _pool = None


atexit.register(reset_pool)

# ---------------------------------------------------------------------------- HTTP
STORE: Store | None = None  # created in main(), so worker processes importing this file do not start one
ALLOWED_HOSTS = {"127.0.0.1", "localhost", "[::1]"}


class Handler(BaseHTTPRequestHandler):
    server_version = "pokerbot-ui"

    def log_message(self, fmt, *args):  # quieter console: only errors
        if args and str(args[1] if len(args) > 1 else "").startswith(("4", "5")):
            super().log_message(fmt, *args)

    def send_json(self, data, status=200):
        body = json.dumps(data, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def host_ok(self):
        if self.server.server_address[0] not in ("127.0.0.1", "::1", "localhost"):
            return True  # bound to a wider address on purpose with --host
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0]
        if host not in ALLOWED_HOSTS:
            self.send_json({"error": "bad Host header"}, 403)  # guards against DNS rebinding
            return False
        return True

    def do_GET(self):
        if not self.host_ok():
            return
        url = urlparse(self.path)
        parts = [p for p in url.path.split("/") if p]
        try:
            if url.path in STATIC:
                name, kind = STATIC[url.path]
                body = (UI / name).read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", kind + "; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif parts == ["api", "engine"]:
                self.send_json({"kit": str(KIT) if KIT else None, "replay": bool(find_replay()),
                                "default": "kit" if KIT else "mini",
                                "variants": [{"name": v.name, "title": v.title}
                                             for v in mini_sim.VARIANTS.values()]})  # fmt: skip
            elif parts == ["api", "bots"]:
                self.send_json({"bots": discover_bots()})
            elif parts == ["api", "runs"]:
                runs = sorted(STORE.runs.values(), key=lambda r: -r.id)
                self.send_json({"runs": [r.public(full=False) for r in runs],
                                # Totals for this server session, including runs no longer kept.
                                "session": {"runs": STORE.finished_runs, "tables": STORE.finished_tables}})  # fmt: skip
            elif parts == ["api", "rankings"]:
                # ?runs=3,5,8 limits it to those runs; ?variant=omaha to one variant. Default: every run.
                query = parse_qs(url.query)
                chosen = list(STORE.runs.values())
                if query.get("runs", [""])[0]:
                    ids = {int(value) for value in query["runs"][0].split(",") if value.strip()}
                    chosen = [run for run in chosen if run.id in ids]
                if query.get("variant", [""])[0]:
                    chosen = [run for run in chosen if run.settings["variant"] == query["variant"][0]]
                self.send_json(rankings(chosen))
            elif len(parts) == 3 and parts[:2] == ["api", "runs"]:
                self.send_json(STORE.get(int(parts[2])).public())
            elif len(parts) == 4 and parts[:2] == ["api", "runs"] and parts[3] == "log":
                body = STORE.get(int(parts[2])).log_text().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif len(parts) == 4 and parts[:2] == ["api", "runs"] and parts[3] == "replays":
                run = STORE.get(int(parts[2]))
                self.send_json({"tables": [{k: v for k, v in r.items() if k != "hands"} | {"hand_count": len(r["hands"])}
                                           for r in run.replays]})  # fmt: skip
            elif len(parts) == 5 and parts[:2] == ["api", "runs"] and parts[3] == "replays":
                run = STORE.get(int(parts[2]))
                table = int(parts[4])
                match = [r for r in run.replays if r["table"] == table]
                if not match:
                    raise LookupError("no replay for that table")
                self.send_json(match[0] | {"settings": run.settings})
            else:
                self.send_json({"error": "not found"}, 404)
        except LookupError as error:
            self.send_json({"error": str(error)}, 404)
        except (ValueError, KeyError) as error:
            self.send_json({"error": str(error)}, 400)

    def do_POST(self):
        if not self.host_ok():
            return
        # JSON only: a cross-site form cannot send this without a CORS preflight we never answer.
        if not (self.headers.get("Content-Type") or "").startswith("application/json"):
            return self.send_json({"error": "send application/json"}, 415)
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if length > 100_000:
                raise ValueError("request too large")
            body = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(body, dict):
                raise ValueError("expected a JSON object")
            parts = [p for p in urlparse(self.path).path.split("/") if p]
            if parts == ["api", "runs"]:
                run = STORE.submit(parse_settings(body))
                self.send_json({"id": run.id})
            elif parts == ["api", "runs", "clear"]:
                self.send_json({"removed": STORE.clear()})
            elif len(parts) == 4 and parts[:2] == ["api", "runs"] and parts[3] == "cancel":
                STORE.get(int(parts[2])).cancel = True
                self.send_json({"ok": True})
            elif len(parts) == 4 and parts[:2] == ["api", "runs"] and parts[3] == "viewer":
                run = STORE.get(int(parts[2]))
                if not run.history_file or not run.history_file.is_file():
                    raise ValueError("This run has no saved hand history.")
                self.send_json({"url": open_viewer(run.history_file)})
            else:
                self.send_json({"error": "not found"}, 404)
        except LookupError as error:
            self.send_json({"error": str(error)}, 404)
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, 400)


def main():
    global KIT, VIEWER_PORT, STORE, WORKERS
    # Stop the kit's viewer too when this server is terminated, not only on Ctrl+C.
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", default="127.0.0.1", help="Default 127.0.0.1 (this machine only).")
    parser.add_argument("--kit", help="Path to the kit's poker-agent executable (default: look on PATH "
                        "and in a starter-kit folder inside or beside this project).")  # fmt: skip
    parser.add_argument("--viewer-port", type=int, default=VIEWER_PORT,
                        help="Port for the kit's hand viewer (default 8766).")  # fmt: skip
    parser.add_argument("--workers", type=int, default=WORKERS,
                        help=f"Processes playing tables at once (default {WORKERS}: half the processors).")  # fmt: skip
    options = parser.parse_args()
    VIEWER_PORT = options.viewer_port
    WORKERS = max(1, options.workers)
    STORE = Store()
    KIT = find_kit(options.kit)
    if options.kit and KIT is None:
        parser.error(f"--kit {options.kit}: no such file")
    server = ThreadingHTTPServer((options.host, options.port), Handler)
    server.daemon_threads = True
    print(f"Pokerbot practice UI: http://{options.host}:{options.port}/")
    if KIT:
        print(f"Engine: organizers' kit ({KIT})")
    else:
        print("Engine: UNOFFICIAL mini simulator. The kit's `poker-agent` was not found; activate the "
              "kit's environment before starting this server, or pass --kit, to use the real engine.")  # fmt: skip
    print("Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
