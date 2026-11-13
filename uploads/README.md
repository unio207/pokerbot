# Uploaded bots, Pittsburgh regional, 2026-11-12

The exact files uploaded to the team page, by submission id. Sizes match the portal's `size_bytes`.

| Folder | Submission | Bytes | Uploaded (EST) | What it is | Played |
| --- | --- | --- | --- | --- | --- |
| `v0_7e4d8e8e` | `7e4d8e8e` | 70,036 | 18:20:31 | `final`, unconverted | nothing |
| `v1_920a2429` | `920a2429` | 73,246 | 18:30:54 | first conversion to Pittsburgh | practice 1 (18:34) |
| `v2_066139f9` | `066139f9` | 75,994 | 18:43:35 | Vedaant's v3a (`pittsburgh-v2` bc36edb) | practice 2 (18:45) |
| `v3_393c48a3` | `393c48a3` | 73,364 | 18:52:04 | v1 plus the looser preflop settings | practice 3 (18:54) |
| `v4_d55b4134` | `d55b4134` | 73,673 | 18:58:00 | v1 plus the heads-up big-blind fix; equals `bots/final/agent.py` at `9daa6a9` | practice 4 (19:04), round 1 (19:14) |
| `v6_0e986661` | `0e986661` | 73,890 | 19:18:20 | v4 plus a heads-up big-blind call of a non-committing raise: top 50%, price up to 0.40, at most 12% of the stack (`hu_defend` in `preflop`) | nothing |
| `v7_10809172` | `10809172` | 73,759 | 19:20:38 | v4 plus one line in `_call_all_in`: the shover rule (call only the top 13% against a seat that shoved over 30% of its hands) is off when two players are left | practice 5 (19:24) |
| `v9_fc9b02c4` | `fc9b02c4` | 73,949 | 19:29:05 | v7 plus `final`'s `open` table: small blind 0.45 to 0.70, button 0.40 to 0.55, cutoff 0.28 to 0.33 | nothing (active 19:29 to 19:33) |
| `v11_469e96f5` | `469e96f5` | 74,862 | 19:33:57 | v9 plus a first draft of the big-blind re-raises (`bb_reraise`), a call with any pair in the big blind, heads-up call of an all-in of 10 bb or less with any ace, king or pair, wider shoves first in at 5 bb or less | round 2 (19:34): 11.64 ± 0.23 |
| `v90_f4025ac6` | `f4025ac6` | 45,312 | 19:43:06 | the launch session's port of `zoo/claude_exploiter_1` with Pittsburgh handlers, not built from `tools/core_agent.py` | practice 6 (19:45): 11.02 ± 0.50 |
| `v13_1b9ad55e` | `1b9ad55e` | 73,996 | 19:48:33 | v4 plus postflop only: flop and turn calls need 0.10 more strength, a draw alone calls at 0.20 or less, `value_bet` 0.70, `medium_bet` 0.52, `cbet_air` 0.6, raise a flop or turn bet at 0.78. No v7, v9 or v11 change | round 3 (19:55): 12.31 ± 0.22 |
| `v91_e140891a` | `e140891a` | 74,507 | 19:56:16 | v13 plus nine lines of lighter re-raises against one raise (p2's build; big blind 0.15, small blind 0.12, others 0.06, times 0.6 when it is a shove) | practice 7 (20:06): 12.78 ± 0.32 |
| `v17_20a9e4ae` | `20a9e4ae` | 75,006 | 20:12:48 | v13 plus the endgame package (heads-up button 0.90, heads-up big blind reshoves the top half and calls short all-ins with the top half, wider shoves three-handed, `points_tight` 0) | round 4 (20:15) |
| `v94_881d49d6` | `881d49d6` | 79,563 | 20:22:21 | v13 plus p2's `_cloned()` preflop (v93 with round 1's top-ten frequencies) plus the one-board lock rule | practice 8 (20:26): 14.90 ± 0.38 |
| `v96_25276ffb` | `25276ffb` | 79,712 | 20:31:12 | p2's build on the v94 file: round 3's top-ten tables, `icm_scale` 0, `points_tight` 0, `bubble_margin` 0, `call_margin` 0.02, `push_scale` 1.1, shares times 1.1 with three or fewer left | round 5 (20:35): 15.37 ± 0.28, 21st of 112 |
| `v971_2f1d6444` | `2f1d6444`, uploaded again at 20:52:17 as `eb6caf1a` (same 80,989 bytes) | 80,989 | 20:45:55 | p2's v96 with the preflop percentile from the measured three-card pot share, no 1.1 multiplier, `call_margin` 0.05, `push_scale` 0.9, opens of 2.3 bb; equals `bots/final/agent.py` built from the core | round 6 (20:55), as `eb6caf1a` |

Measurements: `skills/STATE.md` on `main`.
