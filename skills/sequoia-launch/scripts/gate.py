"""Stage 4: the safety gate. One command, PASS or FAIL, before every upload. Never skipped.

    python gate.py <bot folder>                 # kit when installed, else mini simulator
    python gate.py <bot folder> --tables 30     # behind the clock: fewer tables, same checks
    python gate.py <bot folder> --mini          # force the mini simulator and stand-in SDK

Checks, all against the Rules Card (rules_card.json), nothing hard-coded:
  static    runner's `check`, agent.py size, folder size and entry count, import time
  fuzz      random states: act() never raises, every action legal, memory is bytes within the
            limit; on CLEAN states (the variant's own shapes, valid memory) no exception is
            even raised inside the bot, because the try/except in act() would hide it as a
            silent check/fold
  timing    p99, p99.9, overrun rate and max of act() against decision_ms with margins
  memory    a full-length table of busy hands: the blob stays under a fraction of the limit
  tables    3 line-ups x --tables on the runner: zero failed decisions; on the mini simulator
            also the no-time-bank upload test imitation
Exit code 0 only on PASS. Timing counts only on the machine the bot was built on; the build
machine's numbers are the ones to trust.
"""

import argparse
import collections
import dataclasses
import random
import subprocess
import sys
import time
from pathlib import Path

import common

RESULTS: list[tuple[str, str, str]] = []


def report(ok, name: str, detail: str) -> None:
    status = "PASS" if ok is True else "WARN" if ok is None else "FAIL"
    RESULTS.append((status, name, detail))
    print(f"[{status}] {name}: {detail}", flush=True)


def make(cls, **values):
    """Build an SDK dataclass by field name, so extra or missing fields in the real SDK do not matter."""
    if not dataclasses.is_dataclass(cls):
        return cls(**values)
    kwargs = {}
    for field in dataclasses.fields(cls):
        if field.name in values:
            kwargs[field.name] = values[field.name]
        elif field.default is dataclasses.MISSING and field.default_factory is dataclasses.MISSING:
            kwargs[field.name] = None
    return cls(**kwargs)


BAD_MEMORY = (b"\xff\xfe\x00junk", b"null", b"[]", b'{"hands":', b'{"hands":"x","raises":[]}',
              b'{"hands":3,"raises":{"1":"x"}}', b"0" * 70000, b"{}", b" ")  # fmt: skip


class States:
    def __init__(self, sdk, card, seed):
        self.sdk, self.rng = sdk, random.Random(seed)
        self.config, self.variant = card["config"], card["variant"]
        ranks = "6789TJQKA" if self.variant["deck_cards"] == 36 else "23456789TJQKA"
        self.deck = [rank + suit for rank in ranks for suit in "cdhs"]
        shapes = self.variant.get("phase_shapes") or []
        self.shapes = [(s["phase"], s["cards"], s["board"], s["kinds"]) for s in shapes] or [
            ("betting", self.variant["hole_cards"], board, None) for board in (0, 0, 3, 4, 5)]  # fmt: skip

    def state(self, clean: bool, hand: int | None = None, busy: bool = False):
        sdk, rng, config = self.sdk, self.rng, self.config
        players = config["players"] if clean else rng.choice((2, 3, config["players"], 10))
        hero = rng.randrange(players)
        small, big = rng.choice(config["blinds"])[:2]
        if not clean and rng.random() < 0.05:
            small, big = 0, rng.choice((0, 1))
        cap = config["hand_cap"]
        hand = hand or rng.choice((1, cap, cap - 1, rng.randint(1, cap)))
        seats = []
        for seat in range(players):
            status = "active" if seat == hero else rng.choice(("active", "active", "folded", "all_in", "busted"))
            stack = 0 if status in ("all_in", "busted") else rng.choice(
                (1, 3, 7, max(1, big), rng.randint(1, config["starting_stack"] * players)))  # fmt: skip
            bet = 0 if status == "busted" else rng.choice((0, 0, small, big, rng.randint(0, 3 * big + 1)))
            seats.append(make(sdk.Seat, seat=seat, stack=stack, bet=bet, status=status, shown_cards=()))
        me = seats[hero]
        phase, hole, board_count, kinds = rng.choice(self.shapes)
        if not clean:
            hole = rng.choice((hole, 1, 2, 3, 4, 5, 6))
            board_count = rng.choice((board_count, 0, 1, 2, 3, 4, 5))
            if rng.random() < 0.15:
                phase = rng.choice(("select", "discard", "bid", "mystery"))  # a phase the bot may not know
                kinds = [phase]
        dealt = rng.sample(self.deck, hole + board_count)
        field = {}
        if "boards" in ((self.variant.get("state_variant_field") or [{}])[0] or {}):  # a two-board game
            second = rng.sample([card for card in self.deck if card not in dealt], board_count)
            field = {"boards": [list(dealt[hole:]), second], "discarded": []}
            if not clean and rng.random() < 0.3:  # a field the bot must survive, not understand
                field = rng.choice(({}, {"boards": "??"}, {"boards": [second]}, {"boards": [[], second[:2]]}))
        to_call = rng.choice((0, 0, rng.randint(1, max(1, me.stack if clean else 2 * me.stack))))
        if phase == "betting":  # betting amounts are built here; a shape's kinds matter only for other phases
            legal = [sdk.LegalAction("fold"), sdk.LegalAction("call")] if to_call else [sdk.LegalAction("check")]
            if me.stack > to_call and rng.random() < 0.7:
                top = me.bet + me.stack
                legal.append(sdk.LegalAction("raise", min(top, me.bet + to_call + rng.choice((1, max(1, big), 2 * big + 1))), top))
        else:
            legal = [sdk.LegalAction(kind) for kind in kinds]
        others = [seat for seat in range(players) if seat != hero]
        events = [sdk.Event("hand", None, hand), sdk.Event("blind", rng.choice(others), small),
                  sdk.Event("blind", rng.choice(range(players)), big)]  # fmt: skip
        for _ in range(3 * players if busy else rng.randint(0, 6)):
            events.append(sdk.Event(rng.choice(("fold", "check", "call", "raise", "raise")),
                                    rng.choice(others), rng.randint(0, 4 * big + 1)))  # fmt: skip
        if board_count:
            events.append(sdk.Event("board", None, 0, tuple(dealt[hole:])))
        if not clean:
            events += [sdk.Event("mystery", None, -1), sdk.Event("raise", 99, 5), sdk.Event("show", hero, 0, ("??",))]
            rng.shuffle(events)
        levels = tuple(sdk.BlindLevel(*level[:2]) for level in config["blinds"])
        payouts = tuple(config["payouts"]) if clean else rng.choice(((100,), (50, 30, 20), (40, 25, 15, 10, 10), ()))
        table = make(sdk.TableConfig, table_id="gate", seat=hero, players=players, variant=self.variant["name"],
                     starting_stack=config["starting_stack"], blinds=levels,
                     hands_per_level=config["hands_per_level"], hand_cap=cap, payouts=payouts,
                     decision_ms=config["decision_ms"], memory_bytes=config["memory_bytes"],
                     time_bank_ms=config["time_bank_ms"])  # fmt: skip
        return make(
            sdk.GameState, events=tuple(events), hand_number=hand, seat=hero, cards=tuple(dealt[:hole]),
            board=tuple(dealt[hole:]), pot=sum(seat.bet for seat in seats) + rng.randint(0, 5 * big + 1),
            to_call=to_call, legal_actions=tuple(legal), history=tuple(events), seats=tuple(seats),
            button=rng.randrange(players), blind_level=0, blinds=sdk.BlindLevel(small, big),
            hands_until_next_level=rng.randint(1, config["hands_per_level"]),
            players_remaining=sum(seat.status != "busted" for seat in seats), bust_order=(), config=table,
            variant=field, phase=phase, time_bank_ms=float(config["time_bank_ms"]),
        )  # fmt: skip


def problem(result, state, limit) -> str | None:
    if not (isinstance(result, tuple) and len(result) == 2):
        return f"act returned {type(result).__name__}, not (Action, bytes)"
    action, memory = result
    allowed = state.can(getattr(action, "kind", None))
    if allowed is None:
        return f"illegal kind {getattr(action, 'kind', action)!r} in phase {state.phase}"
    if action.kind == "raise" and not (type(action.amount) is int and allowed.min_amount <= action.amount <= allowed.max_amount):
        return f"raise to {action.amount!r} outside [{allowed.min_amount}, {allowed.max_amount}]"
    if not isinstance(memory, bytes):
        return f"memory is {type(memory).__name__}, not bytes"
    if len(memory) > limit:
        return f"memory {len(memory)} bytes over the {limit} limit"
    return None


def fuzz(agent, states: States, count: int, agent_file: str, limit: int) -> None:
    rng = states.rng
    raised: collections.Counter = collections.Counter()
    seen: set[int] = set()

    def on_exception(code, offset, exception):
        # GeneratorExit is an abandoned next()/any() generator being closed, not an error.
        if code.co_filename == agent_file and id(exception) not in seen and not isinstance(exception, GeneratorExit):
            seen.add(id(exception))
            line = next((ln for start, end, ln in code.co_lines() if start <= offset < end), 0)
            raised[f"{type(exception).__name__} in {code.co_name} line {line}"] += 1

    monitoring = sys.monitoring
    monitoring.use_tool_id(monitoring.PROFILER_ID, "gate")
    events = monitoring.events.RAISE | monitoring.events.EXCEPTION_HANDLED
    for event in (monitoring.events.RAISE, monitoring.events.EXCEPTION_HANDLED):
        monitoring.register_callback(monitoring.PROFILER_ID, event, on_exception)
    problems: collections.Counter = collections.Counter()
    passive = clean_count = 0
    memory = b""
    for index in range(count):
        clean = index % 2 == 0
        state = states.state(clean)
        blob = memory if clean or rng.random() < 0.3 else rng.choice(BAD_MEMORY)
        seen.clear()
        monitoring.set_events(monitoring.PROFILER_ID, events if clean else 0)
        try:
            result = agent.act(state, blob)
        except Exception as error:  # the platform would count this as a failed decision
            problems[f"act raised {type(error).__name__}: {error} ({'clean' if clean else 'dirty'} state)"] += 1
            continue
        finally:
            monitoring.set_events(monitoring.PROFILER_ID, 0)
        found = problem(result, state, limit)
        if found:
            problems[found + (" (clean state)" if clean else " (dirty state)")] += 1
        elif clean:
            memory = result[1]
            clean_count += 1
            passive += result[0].kind in ("check", "fold")
    monitoring.free_tool_id(monitoring.PROFILER_ID)
    top = "; ".join(f"{n}x {text}" for text, n in problems.most_common(4))
    report(not problems, "fuzz legality", f"{count} states, {sum(problems.values())} bad" + (f": {top}" if top else ""))
    top = "; ".join(f"{n}x {text}" for text, n in raised.most_common(4))
    report(not raised, "fuzz hidden exceptions", f"{sum(raised.values())} raised inside the bot on {count // 2} clean states"
           + (f": {top}" if top else "") + f"; check/fold share on clean states {passive / max(1, clean_count):.0%}")  # fmt: skip


def timing(agent, states: States, count: int, card) -> None:
    batch = [states.state(True) for _ in range(count)]
    memory, times = b"", []
    for state in batch:
        began = time.perf_counter_ns()
        try:
            _, memory = agent.act(state, memory)
        except Exception:
            memory = b""
        times.append(time.perf_counter_ns() - began)
    times.sort()
    limit_us = card["config"]["decision_ms"] * 1000
    margins = card["margins"]
    p50, p99, p999, worst = (times[min(len(times) - 1, int(len(times) * q))] / 1000 for q in (0.5, 0.99, 0.999, 1.0))
    over = sum(t / 1000 > limit_us for t in times) / len(times)
    bank_us = card["config"]["time_bank_ms"] * 1000
    ok = (p99 <= margins["p99"] * limit_us and p999 <= margins["p999"] * limit_us
          and over <= margins["overrun_rate"] and worst <= max(limit_us, bank_us / 4))  # fmt: skip
    report(ok, "timing", f"{count} decisions in-process: p50 {p50:.0f} µs, p99 {p99:.0f} (allowed {margins['p99'] * limit_us:.0f}), "
           f"p99.9 {p999:.0f} (allowed {margins['p999'] * limit_us:.0f}), max {worst:.0f}, over {limit_us:.0f} µs: "
           f"{over:.3%} (allowed {margins['overrun_rate']:.3%})")  # fmt: skip


def memory_growth(agent, states: States, card) -> None:
    limit = card["config"]["memory_bytes"]
    memory, largest = b"", 0
    for hand in range(1, card["config"]["hand_cap"] + 1):
        for _ in range(4):
            try:
                _, memory = agent.act(states.state(True, hand=hand, busy=True), memory)
            except Exception:
                pass
            largest = max(largest, len(memory) if isinstance(memory, bytes) else limit + 1)
    allowed = card["margins"]["memory_fraction"] * limit
    report(largest <= allowed, "memory growth", f"largest blob {largest} bytes over a {card['config']['hand_cap']}-hand busy table "
           f"(allowed {allowed:.0f} = {card['margins']['memory_fraction']:.0%} of {limit})")  # fmt: skip


def static(bot: Path, command, engine, card, sdk_kind) -> None:
    limits = card["limits"]
    checked = common.practice.run(command, ["check", str(bot / "agent.py")])
    report(checked.returncode == 0, f"{engine} check", "passed" if checked.returncode == 0 else (checked.stdout + checked.stderr)[-400:])
    build = common.ROOT / "tools" / "build.py"
    if bot.parent.name == "bots" and build.is_file():  # a generated bot must match its source
        drift = subprocess.run([sys.executable, str(build), "--check"], capture_output=True, text=True)
        report(drift.returncode == 0, "build check", "bots/ match tools/core_agent.py" if drift.returncode == 0
               else "bots/ differ from tools/core_agent.py: run tools/build.py. " + (drift.stdout + drift.stderr)[-300:])  # fmt: skip
    code = (bot / "agent.py").stat().st_size
    report(code <= limits["code_bytes"], "agent.py size", f"{code} bytes (limit {limits['code_bytes']})")
    files = [path for path in bot.rglob("*") if path.is_file() and "__pycache__" not in path.parts]
    total = sum(path.stat().st_size for path in files)
    ok = len(files) <= limits["entries"] and total <= limits["unpacked_bytes"]
    report(ok if total <= limits["upload_bytes"] or not ok else None, "upload size",
           f"{len(files)} files (limit {limits['entries']}), {total} bytes unpacked (limits: {limits['upload_bytes']} uploaded, "
           f"{limits['unpacked_bytes']} unpacked)" + ("" if total <= limits["upload_bytes"] else "; check the zip's own size"))  # fmt: skip
    path = [str(bot)] + ([str(common.ROOT / "devtest" / "shim")] if sdk_kind == "shim" else [])
    probe = f"import sys,time; sys.path[:0]={path!r}; t=time.perf_counter(); import agent; print(time.perf_counter()-t)"
    spent = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, cwd=str(bot))
    allowed = card["margins"]["import_seconds"]
    if spent.returncode != 0:
        report(False, "import", spent.stderr[-400:])
    else:
        report(float(spent.stdout) <= allowed, "import time", f"{float(spent.stdout):.3f} s (our margin {allowed} s; no official limit known)")


def tables(bot: Path, command, engine, count: int, card) -> None:
    lineups = list(common.practice.lineups(bot).items())[:3]
    failed = decisions = played = 0
    for name, bots in lineups:
        result = common.practice.run(command, ["play", *map(str, bots), "--tables", str(count), "--seed", "gate", "--no-history",
                                               *common.mini_args(card, engine)])  # fmt: skip
        entry = common.summary(result)[f"{bot.name}#0"]
        failed += entry["failed_decisions"]
        decisions += entry.get("decisions", 0)
        played += count
    report(failed == 0, f"{engine} tables", f"{played} tables over {len(lineups)} line-ups, {failed} failed decisions"
           + (f" of {decisions}" if decisions else ""))  # fmt: skip
    if engine != "mini":
        report(None, "upload test imitation", "skipped: the kit's play always gives the time bank; the timing check above stands in")
        return
    variant = card["variant"]
    if variant.get("mini_name"):
        report(None, "variant coverage", f"tables played the mini simulator's own `{variant['mini_name']}` ruleset, our "
               "reading of the rules, not the kit's engine")  # fmt: skip
    elif variant["hole_cards"] != 2 or variant["deck_cards"] != 52 or set(variant["phases"]) != {"betting"}:
        report(None, "variant coverage", "these tables were plain hold'em on the mini simulator: the variant's phases, card "
               "counts and action formats were exercised by the fuzz only. Run the gate where the kit is installed before uploading")  # fmt: skip
    spar = common.ROOT / "sparring" / "check_or_fold"
    result = common.practice.run(command, ["play", str(bot), str(spar), "--tables", "300", "--hand-cap", "20",
                                           "--bank-ms", "0", "--payouts", "50", "--seed", "upload",
                                           *common.mini_args(card, engine)])  # fmt: skip
    entry = common.summary(result)[f"{bot.name}#0"]
    rate = entry["failed_decisions"] / max(1, entry["decisions"])
    allowed = card["margins"]["upload_test_fail_rate"]
    report(rate <= allowed, "upload test imitation", f"no time bank, heads-up, 20 hands x 300: {entry['failed_decisions']} of "
           f"{entry['decisions']} failed ({rate:.2%}; ours allowed {allowed:.0%}, platform rejects over "
           f"{card['limits']['upload_test_fail_rate']:.0%})")  # fmt: skip


def main() -> None:
    parser = argparse.ArgumentParser(description="Safety gate: PASS or FAIL.")
    parser.add_argument("bot")
    parser.add_argument("--tables", type=int, default=100, help="Tables per line-up (3 line-ups).")
    parser.add_argument("--states", type=int, default=20000, help="Random states for fuzzing; as many again for timing.")
    parser.add_argument("--mini", action="store_true")
    options = parser.parse_args()
    bot = common.bot_dir(options.bot)
    sdk_kind = common.use_sdk(options.mini)
    command, engine = common.runner(options.mini)
    card = common.card()
    print(f"gate: {bot}\nrunner: {engine}   sdk: {sdk_kind}   rules card: {'rules_card.json' if card['_filled'] else 'TEMPLATE DEFAULTS'} "
          f"({card['source']})\nlimits: decision {card['config']['decision_ms']} ms, bank {card['config']['time_bank_ms']} ms, "
          f"memory {card['config']['memory_bytes']} bytes\n")  # fmt: skip
    if not card["_filled"]:
        report(None, "rules card", "not filled: limits are the pre-announcement defaults")

    static(bot, command, engine, card, sdk_kind)
    import poker_agent_sdk as sdk

    try:
        States(sdk, card, 0).state(True)
    except Exception as error:
        report(None, "sdk", f"could not build states with the kit's SDK ({error!r}); fuzzing with the stand-in instead")
        common.use_sdk(force_shim=True)
        import poker_agent_sdk as sdk
    sys.path.insert(0, str(bot))
    try:
        import agent as module

        agent = module.Agent()
    except Exception as error:
        report(False, "import", repr(error))
    else:
        limit = card["config"]["memory_bytes"]
        fuzz(agent, States(sdk, card, 1), options.states, module.__file__, limit)
        repo_fuzz = common.ROOT / "tools" / "fuzz.py"
        if repo_fuzz.is_file():  # the repo's own fuzzer: a second, independent stream of states
            ran = subprocess.run([sys.executable, str(repo_fuzz), str(bot), "--states", "5000"], capture_output=True, text=True)
            report(ran.returncode == 0, "tools/fuzz.py", ((ran.stdout + ran.stderr).strip().splitlines() or ["no output"])[-1][:300])
        timing(agent, States(sdk, card, 2), options.states, card)
        memory_growth(agent, States(sdk, card, 3), card)
        tables(bot, command, engine, options.tables, card)

    failures = [name for status, name, _ in RESULTS if status == "FAIL"]
    warnings = [name for status, name, _ in RESULTS if status == "WARN"]
    print()
    if warnings:
        print("warnings: " + ", ".join(warnings))
    print("GATE: " + ("FAIL (" + ", ".join(failures) + ")  -> do not upload" if failures else "PASS"))
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
