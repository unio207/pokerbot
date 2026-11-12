"""Probe bot: NOT for upload. Plays call/check so hands reach every phase, and writes what it
sees of `state` (config, phases, legal actions, card counts, event kinds) to a temp file for
scripts/probe.py. Writes each new observation once."""

import dataclasses
import json
import os
import tempfile

import poker_agent_sdk
from poker_agent_sdk import Action

OUT = os.path.join(tempfile.gettempdir(), "nl26_probe.jsonl")
_seen = set()


def dump(value, depth=0):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if depth > 4:
        return repr(value)
    if isinstance(value, dict):
        return {str(k): dump(v, depth + 1) for k, v in value.items()}
    if isinstance(value, (tuple, list, set, frozenset)):
        return [dump(v, depth + 1) for v in value]
    if dataclasses.is_dataclass(value):
        return {f.name: dump(getattr(value, f.name), depth + 1) for f in dataclasses.fields(value)}
    if hasattr(value, "__dict__"):
        return {k: dump(v, depth + 1) for k, v in vars(value).items() if not k.startswith("_")}
    return repr(value)


def note(kind, value):
    line = json.dumps([kind, value], sort_keys=True, default=repr)
    if line not in _seen:
        _seen.add(line)
        with open(OUT, "a") as handle:
            handle.write(line + "\n")


class Agent(poker_agent_sdk.Agent):
    def act(self, state, memory):
        try:
            config = dump(state.config)
            if isinstance(config, dict):
                config.pop("table_id", None)
                config.pop("seat", None)
            note("config", config)
            note("state_fields", sorted(name for name in dir(state) if not name.startswith("_")))
            note("phase", [state.phase, len(state.cards), len(state.board),
                           [[a.kind, a.min_amount > 0, a.max_amount > 0] for a in state.legal_actions]])  # fmt: skip
            note("variant", dump(getattr(state, "variant", None)))
            for event in tuple(state.events) + tuple(state.history):
                note("event", [event.kind, sorted(k for k, v in dump(event).items() if v not in (None, [], ""))])
            note("seat_fields", sorted(dump(state.seats[0])))
        except Exception as error:  # the probe must keep playing whatever the SDK looks like
            note("probe_error", repr(error))
        if state.can("call"):
            return Action.call(), memory
        first = state.legal_actions[0]
        return Action(first.kind, first.min_amount), memory
