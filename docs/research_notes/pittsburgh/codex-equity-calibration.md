**Preflop is materially optimistic; flop is generally pessimistic; turn is mildly optimistic, especially at the extremes.** On uniformly random hands, average `bot − equity` was **+6.64, −3.18, +1.74 percentage points**, respectively.

All equities below are **computed Monte Carlo estimates**, using each player’s exact `db_discard` policy before revealing rivers, then eval7 showdown evaluation. One shared retained pair serves both boards. Random opponents, no folding or betting-range selection. These are policy-specific equities, not optimal-play values. `±` denotes **one standard error**, accounting for both boards within each deal.

Preflop: **30,000 deals per hand**. Bot values are exact first returns from `db_preflop`; equity and error columns are percentages.

| Hand | Bot | Equity ± SE | Bot overstatement |
|---|---:|---:|---:|
| As Ah Kd | 85.30 | 77.75 ± 0.16 | 7.55 |
| As Ah 2d | 85.30 | 77.50 ± 0.16 | 7.80 |
| As Ks Qh | 67.20 | 61.97 ± 0.19 | 5.23 |
| As Kd Qh | 65.10 | 60.13 ± 0.19 | 4.97 |
| Ks Kh 2d | 82.30 | 73.76 ± 0.18 | 8.54 |
| Qs Qh Jd | 80.20 | 70.76 ± 0.18 | 9.44 |
| Js Jh 2d | 77.50 | 67.14 ± 0.19 | 10.36 |
| Ts Th 9d | 74.90 | 64.65 ± 0.19 | 10.25 |
| 9s 9h 2d | 72.10 | 60.74 ± 0.20 | 11.36 |
| 2s 2h Ad | 54.80 | 44.81 ± 0.19 | 9.99 |
| 2s 2h 3d | 50.40 | 39.19 ± 0.19 | 11.21 |
| 7s 8s 9s | 50.70 | 47.27 ± 0.20 | 3.43 |
| 7s 8d 9h | 48.00 | 45.86 ± 0.20 | 2.14 |
| Ks Qs Js | 63.50 | 57.83 ± 0.19 | 5.67 |
| 7s 2d 3h | 36.70 | 35.14 ± 0.18 | 1.56 |

Multiway: **30,000 deals per hand/opponent count**, every opponent also using `db_discard`.

| Hand | One opponent | Two opponents | Three opponents |
|---|---:|---:|---:|
| As Ah Kd | 77.75 ± 0.16 | 61.62 ± 0.19 | 49.70 ± 0.20 |
| As Ks Qh | 61.97 ± 0.19 | 45.55 ± 0.19 | 36.06 ± 0.19 |
| 7s 2d 3h | 35.14 ± 0.18 | 20.90 ± 0.16 | 15.09 ± 0.14 |

Postflop: **300,000 independent deals**, scored on both flop and turn before discard. Deciles here mean fixed strength intervals of width 0.1; no observations below 0.2. Equity columns are percentages.

| Raw strength | Flop mean strength | Flop equity ± SE | Flop N | Turn mean strength | Turn equity ± SE | Turn N |
|---|---:|---:|---:|---:|---:|---:|
| [0.2, 0.3) | .2674 | 31.92 ± 0.16 | 38,587 | .2705 | 22.55 ± 0.22 | 17,645 |
| [0.3, 0.4) | .3545 | 40.86 ± 0.12 | 72,731 | .3559 | 33.32 ± 0.13 | 56,151 |
| [0.4, 0.5) | .4509 | 48.02 ± 0.13 | 65,005 | .4499 | 43.45 ± 0.14 | 61,650 |
| [0.5, 0.6) | .5400 | 56.46 ± 0.12 | 69,418 | .5447 | 53.05 ± 0.11 | 78,561 |
| [0.6, 0.7) | .6430 | 65.13 ± 0.18 | 29,999 | .6452 | 63.26 ± 0.13 | 49,564 |
| [0.7, 0.8) | .7366 | 73.28 ± 0.21 | 19,484 | .7367 | 73.05 ± 0.18 | 25,813 |
| [0.8, 0.9) | .8356 | 79.83 ± 0.42 | 4,266 | .8392 | 81.54 ± 0.27 | 9,027 |
| [0.9, 1.0] | .9089 | 86.57 ± 1.03 | 510 | .9215 | 86.85 ± 0.59 | 1,589 |

**Recommended correction:** use those postflop bin means as a small lookup. A global linear fit misses the high-turn overstatement.

```python
FLOP = (.3192, .4086, .4802, .5646, .6513, .7328, .7983, .8657)
TURN = (.2255, .3332, .4345, .5305, .6326, .7305, .8154, .8685)
equity = (FLOP if street == 3 else TURN)[min(7, max(0, int(10*s) - 2))]
```

Apply only to the final `db_postflop` strength return with three hole cards on flop/turn. Keep draw flags and `_db_value`/`db_discard` unchanged; changing discard selection would change the measured policy. River was not calibrated.

For preflop, a single best-pair linear fit still misses AA by roughly five points. A small hand-class fit performed better:

| Three-card structure | Fitted heads-up equity |
|---|---|
| Three different ranks | `0.05890 + 0.10728*m + 0.74613*u` |
| Exactly one pocket pair | `-0.15478 + 0.95933*p + 0.17325*k` |
| Three identical ranks | `-0.29592 + 1.23494*p` |

Here `m=max(pair equities)`, `u=mean(pair equities)`, `p=_EQUITY[pocket_pair]`, and `k=max(non-pocket-pair equities)`. Clamp to `[0,1]`.

These are **computed fits** from another 300,000 random deals: 248,609 unpaired, 50,730 paired, 661 trips. The trips fit has substantially less support. Across the 15 independently simulated hands above, this correction reduced equity-estimation RMSE from **7.96 to 1.04 points**, with maximum residual **2.44 points**. Keep `_DB_MARKS` and its existing percentile calculation unchanged.

All corrections are heads-up and distribution-dependent. No files changed, network used, or uploads performed; simulation batches took approximately **26–53 seconds each**.