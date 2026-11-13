"""Compare two trusted an.py aggregate caches without rereading hand histories."""
import argparse
import json
import math
import pickle
from pathlib import Path


def summarize(path):
    with path.open('rb') as stream:
        header, counts = pickle.load(stream)
    hero = header['you']
    n = counts[hero, 'tables']
    if n < 2:
        raise ValueError('At least two scored hero tables are required')
    def c(*key):
        return counts[(hero,) + key]
    def frequency(prefix, middle, actions, selected):
        total = sum(c(prefix, *middle, a) for a in actions)
        return dict(opportunities=total,
                    rate=sum(c(prefix, *middle, a) for a in selected) / total if total else None)
    mean = c('pts') / n
    variance = max(0, (c('pts2') - n * mean * mean) / (n - 1))
    result = dict(tournament_id=header['tournament_id'], tables=n,
                  mean_points=mean, standard_error=math.sqrt(variance / n),
                  places={p: c('place', p) / n for p in range(1, 9)},
                  cash_rate=sum(c('place', p) for p in (1, 2, 3)) / n,
                  heads_up_reach=c('hu_reach') / n,
                  heads_up_win=c('hu_won') / c('hu_reach') if c('hu_reach') else None,
                  heads_up_start_share=c('hu_share') / c('hu_reach') if c('hu_reach') else None,
                  stage={}, heads_up_actions={})
    for stage in ('5-8', '3-4', 'HU'):
        hands = c('h', stage)
        result['stage'][stage] = dict(
            hands=hands, points_per_table=c('eq', stage) / n,
            vpip=1-c('cls_h', stage, 'novol') / hands if hands else None,
            positions={p: c('eqp', stage, p) / n for p in ('BTN', 'SB', 'BB', 'oth')},
            classes={label: dict(hands=c('cls_h', stage, label),
                                points_per_table=c('cls_eq', stage, label) / n)
                     for label in ('novol', 'pre_only', 'allin_pre_shove', 'allin_pre_call',
                                   'post_agg', 'post_call', 'post_passive')})
    for depth in ('e<=10', 'e10-25', 'e>25'):
        result['heads_up_actions'][depth] = dict(
            button_raise=frequency('hu_btn', (depth,), ('fold', 'limp', 'raise', 'shove'), ('raise', 'shove')),
            bb_fold_to_raise=frequency('hu_bb_vs_raise', (depth,), ('fold', 'call', 'raise', 'shove'), ('fold',)),
            bb_reraise=frequency('hu_bb_vs_raise', (depth,), ('fold', 'call', 'raise', 'shove'), ('raise', 'shove')),
            bb_call_shove=frequency('hu_bb_vs_shove', (depth,), ('fold', 'call'), ('call',)))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('previous', type=Path)
    parser.add_argument('current', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    before, after = summarize(args.previous), summarize(args.current)
    delta = after['mean_points'] - before['mean_points']
    se = math.hypot(before['standard_error'], after['standard_error'])
    result = dict(previous=before, current=after, points_change=delta,
                  approximate_95_change_interval=[delta-1.96*se, delta+1.96*se],
                  stage_change={s: after['stage'][s]['points_per_table']-before['stage'][s]['points_per_table']
                                for s in before['stage']},
                  caveat='Unpaired descriptive comparison; interval assumes independent tables. Opponents, bot versions and runouts may differ.')
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('previous', 'current')}, indent=2))


if __name__ == '__main__':
    main()
