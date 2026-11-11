# Instructions for Claude sessions in this repo

## Practice page version

The practice web page (`ui/`) shows its version at the top right, with a menu of every
version and when it was made. The list is `VERSIONS` at the top of `ui/app.js`, newest
first.

Whenever you change the page, add a new entry at the top of `VERSIONS` in the same commit:

- **What counts:** any change to `ui/index.html`, `ui/app.js` or `ui/style.css`, and any
  change to `ui/server.py` or the simulator that alters what the page shows or does.
- **The entry:** the next number (`v4` after `v3`), the exact time with its UTC offset from
  `date -Iminutes` (for example `2026-11-11T02:13-05:00`), and one plain line saying what
  changed.
- **One entry per merged change**, not per edit: several edits made together share one
  version. Never renumber or delete earlier entries.
- Tell the user the new version number when you report the change, so they can check that
  the page they have open is the current one.
