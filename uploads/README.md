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
| `v9_fc9b02c4` | `fc9b02c4` | 73,949 | 19:29:05 | v7 plus `final`'s `open` table: small blind 0.45 to 0.70, button 0.40 to 0.55, cutoff 0.28 to 0.33 | active from 19:29, round 2 (19:33) |

Measurements: `skills/STATE.md` on `main`.
