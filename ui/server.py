"""Local web UI for practising bots: build line-ups, run matches, compare, replay.

    python ui/server.py                # http://127.0.0.1:8765
    python ui/server.py --port 9000
    python ui/server.py --kit /path/to/kit/.venv/bin/poker-agent

Two engines:
- "kit": every table is played by the organizers' starter kit (`poker-agent play`), so the
  variant, rules and the 1 ms limit are the real ones. Used by default when `poker-agent`
  is found (start this server from the kit's activated environment, or pass --kit).
- "mini": the UNOFFICIAL in-process simulator in devtest/mini_sim.py (standard hold'em).

Standard library only. Bots are re-read from disk on every run, so edit an agent.py and
click Run again; no restart needed.
"""

import argparse
import atexit
import gc
import importlib.util
import json
import math
import os
import random
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import traceback
import types
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

UI = Path(__file__).resolve().parent
ROOT = UI.parent
SKIP_DIRS = {"ui", "devtest", "tools", "__pycache__", "node_modules", "venv", ".venv"}
STATIC = {"/": ("index.html", "text/html"), "/index.html": ("index.html", "text/html"),
          "/app.js": ("app.js", "text/javascript"), "/style.css": ("style.css", "text/css")}  # fmt: skip
NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
REPLAY_TABLES = 20  # tables per run that keep a full hand-by-hand replay
MAX_TABLES = 5000
KEEP_RUNS = 40  # runs kept in the session; replays only for the newest few
KEEP_REPLAYS = 8
FAILURE_NOTES = 5  # first N failure details kept per entry

_spec = importlib.util.spec_from_file_location("mini_sim", ROOT / "devtest" / "mini_sim.py")
mini_sim = importlib.util.module_from_spec(_spec)
sys.modules["mini_sim"] = mini_sim
_spec.loader.exec_module(mini_sim)

# ---------------------------------------------------------------------------- organizers' kit
KIT: Path | None = None  # the kit's `poker-agent` executable, when found
HISTORY_DIR = ROOT / "hand-history"
KIT_CHUNKS = 9  # a kit run is split into this many `poker-agent play` calls for progress and error bars


def find_kit(explicit=None) -> Path | None:
    """The kit's `poker-agent`: --kit, $POKER_AGENT, next to this Python, or on PATH."""
    candidates = [explicit, os.environ.get("POKER_AGENT"),
                  Path(sys.executable).parent / "poker-agent", shutil.which("poker-agent")]  # fmt: skip
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate).absolute()
    return None


def find_replay() -> Path | None:
    """The kit's hand viewer command, installed beside `poker-agent`."""
    for candidate in (KIT and KIT.parent / "replay", shutil.which("replay")):
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
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
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
_load_counter = 0
_load_lock = threading.Lock()


def bot_folders() -> list[Path]:
    """Every folder at depth 1 or 2 under ROOT that holds an agent.py."""
    found = []
    for first in sorted(ROOT.iterdir()):
        if not first.is_dir() or first.name.startswith(".") or first.name in SKIP_DIRS:
            continue
        candidates = [first] + sorted(p for p in first.iterdir() if p.is_dir()
                                      and not p.name.startswith(".") and p.name not in SKIP_DIRS)  # fmt: skip
        found += [f for f in candidates if (f / "agent.py").is_file() and f.resolve().is_relative_to(ROOT)]
    return found


def discover_bots() -> list[dict]:
    bots = []
    for folder in bot_folders():
        agent = folder / "agent.py"
        try:
            problems = mini_sim.check(agent)
        except Exception as error:  # noqa: BLE001
            problems = [f"check failed: {error}"]
        bots.append({"path": folder.relative_to(ROOT).as_posix(), "name": folder.name,
                     "modified": agent.stat().st_mtime, "problems": problems})  # fmt: skip
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


def load_agent_fresh(folder: Path):
    """Like mini_sim.load_agent, but compiles the source directly so a stale .pyc is never used."""
    global _load_counter
    with _load_lock:
        _load_counter += 1
        name = f"uibot_{_load_counter}"
    path = folder / "agent.py"
    module = types.ModuleType(name)
    module.__file__ = str(path)
    code = compile(path.read_text(encoding="utf-8"), str(path), "exec")
    sys.modules[name] = module  # dataclasses and friends look the module up while it executes
    sys.path.insert(0, str(folder))
    try:
        exec(code, module.__dict__)  # noqa: S102 - running the team's own bot is the point
    finally:
        sys.path.remove(str(folder))
        sys.modules.pop(name, None)
    return module.Agent()


def clone_bot(source_rel, new_name) -> str:
    source = resolve_bot(source_rel)
    if not isinstance(new_name, str) or not NAME_RE.match(new_name):
        raise ValueError("Name may use only letters, digits, underscore and hyphen (1-64 chars).")
    target = (source.parent / new_name).resolve()
    if not target.is_relative_to(ROOT) or target.parent != source.parent.resolve():
        raise ValueError("bad target")
    if target.exists():
        raise ValueError(f"{target.relative_to(ROOT).as_posix()} already exists; pick another name.")
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return target.relative_to(ROOT).as_posix()


# ---------------------------------------------------------------------------- runs
class Rules:
    """The attributes mini_sim.Table reads from its argparse namespace."""

    def __init__(self, settings):
        self.stack = settings["stack"]
        self.decision_ms = 1
        self.bank_ms = 100
        self.hand_cap = settings["hand_cap"]
        self.hands_per_level = settings["hands_per_level"]
        self.payouts = tuple(settings["payouts"])


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
    return {
        "engine": engine,
        "lineup": lineup,
        "tables": _int(body.get("tables", 50), 1, MAX_TABLES, "Tables"),
        "seed": seed,
        "hand_cap": _int(body.get("hand_cap", 250), 1, 2000, "Hand cap"),
        "hands_per_level": _int(body.get("hands_per_level", 20), 1, 1000, "Hands per level"),
        "stack": _int(body.get("stack", 2000), 20, 10**7, "Starting stack"),
        "payouts": payouts,
        "replay_tables": _int(body.get("replay_tables", REPLAY_TABLES), 0, 50, "Replay tables"),
    }


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
                {k: e[k] for k in ("label", "bot", "average_points", "se", "failed_decisions")}
                for e in self.results["entries"]], "par": self.results["par"]}  # fmt: skip
        return out

    # The match loop mirrors mini_sim.play exactly (same per-table RNG and seat shuffle),
    # so a seed gives the same deals as `mini_sim.py play --seed`.
    def execute(self):
        s = self.settings
        self.status, self.started = "running", time.time()
        bots = [resolve_bot(rel) for rel in s["lineup"]]
        labels = [f"{bot.name}#{index}" for index, bot in enumerate(bots)]
        if s["engine"] == "kit":
            return self.execute_kit(s, bots, labels)
        try:
            loaded = {}
            for bot, rel in zip(bots, s["lineup"]):
                if bot not in loaded:
                    self.bot_mtimes[rel] = (bot / "agent.py").stat().st_mtime
                    loaded[bot] = load_agent_fresh(bot)
        except Exception:  # noqa: BLE001
            self.status, self.error = "error", "Could not load a bot:\n" + traceback.format_exc(limit=-4)
            self.finished = time.time()
            return
        n = len(bots)
        points = [[] for _ in labels]
        places = [Counter() for _ in labels]
        failures = [0] * n
        notes = [[] for _ in labels]
        latency = [[] for _ in labels]
        # The server keeps old runs' replays in memory, and a full cyclic-GC pass over them takes
        # ~100 ms. If one landed inside a timed decision it would count as a false timeout, so the
        # collector is paused while tables play and run between tables instead.
        gc.collect()
        gc.freeze()
        gc.disable()
        try:
            self.play_tables(s, bots, labels, loaded, points, places, failures, notes, latency)
        finally:
            gc.enable()
            gc.collect()
            gc.freeze()
        self.finish(s, labels, points, places, failures, notes, latency)

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

    def play_tables(self, s, bots, labels, loaded, points, places, failures, notes, latency):
        rules = Rules(s)
        n = len(bots)
        for number in range(s["tables"]):
            if self.cancel:
                self.status = "cancelled"
                break
            rng = random.Random(f"{s['seed']}:{number}")
            order = list(range(n))
            rng.shuffle(order)
            # Bots that use the global `random` module get a per-table seed too, so the same
            # seed replays the same match (the CLI leaves it unseeded).
            random.seed(f"{s['seed']}:{number}:bots")

            def on_failure(seat, hand, reason, detail, number=number, order=order):
                entry = order[seat]
                if len(notes[entry]) < FAILURE_NOTES:
                    notes[entry].append({"table": number, "hand": hand, "reason": reason, "detail": detail})

            record = number < s["replay_tables"]
            table = mini_sim.Table([loaded[bots[i]] for i in order], rng, rules, f"mini-{number}",
                                   record=record, on_failure=on_failure)  # fmt: skip
            result = table.play()
            finish = table.places()
            for seat, index in enumerate(order):
                points[index].append(result[seat])
                places[index][finish[seat]] += 1
                failures[index] += table.failures[seat]
                latency[index].extend(table.latency[seat])
            if record:
                self.replays.append({
                    "table": number,
                    "seats": [{"label": labels[i], "bot": s["lineup"][i], "entry": i} for i in order],
                    "places": finish, "points": [round(p, 3) for p in result],
                    "failures": table.failures[:], "hands": table.hands,
                })  # fmt: skip
            self.done = number + 1
            gc.collect(1)  # young generations only: cheap, and outside any timed decision

    def finish(self, s, labels, points, places, failures, notes, latency, weights=None):
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
            par = sum(s["payouts"]) / n
        entries = []
        for i, label in enumerate(labels):
            mean, se = stats(points[i])
            times = sorted(latency[i]) if latency else []
            entries.append({
                "label": label, "bot": s["lineup"][i], "tables": tables,
                "average_points": round(mean, 3), "se": round(se, 3), "vs_par": round(mean - par, 3),
                "places": {str(k): v for k, v in sorted(places[i].items())},
                "finish_rates": {str(p): round(places[i][p] / tables, 4) for p in (1, 2, 3)},
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
            by_bot.append({"bot": rel, "seats": len(idx), "average_points": round(mean, 3),
                           "se": round(se, 3), "vs_par": round(mean - par, 3),
                           "failed_decisions": sum(failures[i] for i in idx)})  # fmt: skip
        self.points, self.weights = points, weights
        self.results = {"par": round(par, 3), "tables": tables, "entries": entries, "by_bot": by_bot,
                        "seconds": round(time.time() - self.started, 2), "engine": s["engine"],
                        "se_rough": rough, "chunks": len(weights) if kit else None}  # fmt: skip
        if self.status == "running":
            self.status = "done"
        self.finished = time.time()


class Store:
    def __init__(self):
        self.lock = threading.Lock()
        self.runs: dict[int, Run] = {}
        self.queue: list[Run] = []
        self.wake = threading.Condition(self.lock)
        self.next_id = 1
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

    def get(self, run_id) -> Run:
        run = self.runs.get(run_id)
        if run is None:
            raise LookupError("no such run")
        return run


def compare(a: Run, b: Run) -> dict:
    if not (a.results and b.results):
        raise ValueError("Both runs need results.")
    # Paired = the same deals in the same order: same engine, seed and split into tables/chunks.
    paired = (a.settings["engine"] == b.settings["engine"] and a.settings["seed"] == b.settings["seed"]
              and len(a.points) == len(b.points) and a.weights == b.weights
              and len(a.points[0]) == len(b.points[0]) and a.status == b.status == "done")  # fmt: skip
    tables = min(a.results["tables"], b.results["tables"])
    rough = a.results["se_rough"] or b.results["se_rough"]
    rows = []
    for seat in range(max(len(a.points), len(b.points))):
        ea = a.results["entries"][seat] if seat < len(a.points) else None
        eb = b.results["entries"][seat] if seat < len(b.points) else None
        row = {"seat": seat, "a": ea and {k: ea[k] for k in ("label", "bot", "average_points", "se",
                                                               "failed_decisions")},
               "b": eb and {k: eb[k] for k in ("label", "bot", "average_points", "se", "failed_decisions")}}  # fmt: skip
        if ea and eb:
            if paired and not rough:
                diffs = [after - before for before, after in zip(a.points[seat], b.points[seat])]
                mean, se = summarize(diffs, a.weights)
            else:
                mean = eb["average_points"] - ea["average_points"]
                se = math.sqrt(ea["se"] ** 2 + eb["se"] ** 2)
            row.update(diff=round(mean, 3), se=round(se, 3))
        rows.append(row)
    return {"a": a.id, "b": b.id, "paired": paired and not rough, "tables": tables, "rows": rows,
            "unit": "chunk" if a.settings["engine"] == "kit" else "table",
            "engines": [a.settings["engine"], b.settings["engine"]],
            "same_settings": {k: a.settings[k] == b.settings[k]
                              for k in ("engine", "seed", "tables", "hand_cap", "hands_per_level", "stack",
                                        "payouts")}}  # fmt: skip


# ---------------------------------------------------------------------------- HTTP
STORE = Store()
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
                                "default": "kit" if KIT else "mini"})  # fmt: skip
            elif parts == ["api", "bots"]:
                self.send_json({"bots": discover_bots()})
            elif parts == ["api", "runs"]:
                self.send_json({"runs": [r.public(full=False) for r in sorted(STORE.runs.values(),
                                                                                key=lambda r: -r.id)]})  # fmt: skip
            elif len(parts) == 3 and parts[:2] == ["api", "runs"]:
                self.send_json(STORE.get(int(parts[2])).public())
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
            elif parts == ["api", "compare"]:
                query = parse_qs(url.query)
                self.send_json(compare(STORE.get(int(query["a"][0])), STORE.get(int(query["b"][0]))))
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
            elif len(parts) == 4 and parts[:2] == ["api", "runs"] and parts[3] == "cancel":
                STORE.get(int(parts[2])).cancel = True
                self.send_json({"ok": True})
            elif len(parts) == 4 and parts[:2] == ["api", "runs"] and parts[3] == "viewer":
                run = STORE.get(int(parts[2]))
                if not run.history_file or not run.history_file.is_file():
                    raise ValueError("This run has no saved hand history.")
                self.send_json({"url": open_viewer(run.history_file)})
            elif parts == ["api", "clone"]:
                self.send_json({"path": clone_bot(body.get("source"), body.get("name"))})
            else:
                self.send_json({"error": "not found"}, 404)
        except LookupError as error:
            self.send_json({"error": str(error)}, 404)
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, 400)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", default="127.0.0.1", help="Default 127.0.0.1 (this machine only).")
    parser.add_argument("--kit", help="Path to the kit's poker-agent executable (default: look on PATH).")
    options = parser.parse_args()
    global KIT
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
