"""Fast streaming audit of a participant download; standard library only.

Usage: python3 audit_history.py hands.jsonl.gz output.json
Validates table/private pairs, reports hero results and failures, and keeps
five large positive examples. It never loads the entire history in memory.
"""
import argparse
import collections
import importlib.util
import json
import math
from pathlib import Path
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('history', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--reader', type=Path, help='Path to the kit hand-history/read.py')
    args = parser.parse_args()
    started = time.perf_counter()
    repo = Path(__file__).resolve().parents[4]
    candidates = [args.reader] if args.reader else [
        repo / 'starter-kit/hand-history/read.py',
        repo.parent / 'starter-kit/hand-history/read.py',
        Path.home() / 'starter-kit/hand-history/read.py',
        Path.home() / 'work/starter-kit/hand-history/read.py',
    ]
    reader_path = next((p for p in candidates if p.is_file()), None)
    if reader_path is None:
        parser.error('Kit history reader not found; pass --reader /path/to/hand-history/read.py')
    spec = importlib.util.spec_from_file_location('history_reader', reader_path)
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    counts = collections.Counter()
    stage = collections.defaultdict(collections.Counter)
    blocks = collections.defaultdict(collections.Counter)
    examples = []
    seen = set()
    score_values = collections.Counter()
    for header, table, own in reader.read_history(args.history):
        ident = (table['iteration'], table['table'])
        if ident in seen:
            raise ValueError(f'Duplicate table {ident}')
        seen.add(ident)
        s = own['seat']
        counts['all_tables'] += 1
        if table['fillers'][s]:
            counts['hero_filler_tables'] += 1
            continue
        counts['tables'] += 1
        hands = table['hands']
        points = hands[-1]['equity_after'][s]
        score_values[str(points)] += 1
        counts['points'] += points
        counts['points_squared'] += points * points
        counts['initial_points'] += hands[0]['equity_before'][s]
        counts['automatic'] += len(own['automatic'])
        counts['tables_with_automatic'] += bool(own['automatic'])
        counts['unfinished_tables'] += sum(v > 0 for v in hands[-1]['stacks_after']) > 1
        block = blocks[(counts['tables'] - 1) // 2000]
        block['tables'] += 1
        block['points'] += points
        for handnum, eventidx in own['automatic']:
            h = next(h for h in hands if h['hand'] == handnum)
            counts['automatic_' + h['events'][eventidx]['kind']] += 1
        for k, h in enumerate(hands):
            before, after = h['stacks_before'], h['stacks_after']
            if sum(before) != sum(after):
                raise ValueError(f'Chips not conserved: {ident}, hand {h["hand"]}')
            if before[s] <= 0:
                continue
            counts['hero_hands'] += 1
            alive = sum(x > 0 for x in before)
            st = '5-8' if alive >= 5 else ('3-4' if alive >= 3 else 'HU')
            de = h['equity_after'][s] - h['equity_before'][s]
            stage[st]['hands'] += 1
            stage[st]['points_change'] += de
            block['stage_' + st] += de
            ev = h['events']
            acts = [e for e in ev if e.get('seat') == s]
            counts['decisions'] += sum(e['kind'] in ('fold', 'check', 'call', 'raise', 'bet', 'discard') for e in acts)
            for kind in ('prize_rivers_seen', 'prize_scoops'):
                counts[kind] += sum(e['kind'] == kind for e in acts)
            shown = any(e['kind'] == 'show' for e in acts)
            folded = any(e['kind'] == 'fold' for e in acts)
            cls = 'showdown' if shown else ('fold' if folded else 'uncontested')
            stage[st][cls + '_hands'] += 1
            stage[st][cls + '_points_change'] += de
            if de > 0 and (len(examples) < 5 or de > examples[-1]['points_change']):
                examples.append(dict(iteration=ident[0], table=ident[1], hand=h['hand'],
                                     seat=s, stage=st, cards=own['cards'][k],
                                     points_change=de, chip_change=after[s]-before[s],
                                     events=ev))
                examples.sort(key=lambda x: -x['points_change'])
                examples = examples[:5]
    n = counts['tables']
    if not n:
        parser.error('History contains no scored hero tables')
    mean = counts['points'] / n
    se = math.sqrt(max(0, counts['points_squared'] / n - mean * mean) / max(1, n - 1))
    delta = sum(x['points_change'] for x in stage.values())
    if abs(counts['initial_points'] + delta - counts['points']) > 0.01:
        raise ValueError('Stage accounting does not reconcile with final points')
    result = dict(tournament_id=header['tournament_id'], counts=counts,
                  mean=mean, standard_error=se, approximate_95_interval=[mean-1.96*se, mean+1.96*se],
                  stage=dict(stage), score_distribution=score_values,
                  blocks=dict(blocks), examples=examples,
                  elapsed_seconds=round(time.perf_counter()-started, 3))
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k:v for k,v in result.items() if k != 'examples'}, indent=2))


if __name__ == '__main__':
    main()
