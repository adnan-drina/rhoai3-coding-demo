# dest-14 M2 official-log fixture

The full dest-14 M2 log is not in git. This fixture harvests the
`[exit 1]` command lines dest-cited from dest-14 M2 `t_332d6a0f`
(2026-08-28) plus `skill_view` for mandated skills, omitted-rc
`k4_convert.py` success, the unmandated malformed `python3 -c` red,
and `assert-m2-story-headings.py` `[exit 1]` (directory path under
`plan-migration-partition` — must **not** be attributed to that skill
step).

Four `[exit 1]` on the live card: `check-partition-coverage.py`,
`assert-m2-speckit-conformance.py`, `k4_mint.py --exec`, malformed
`python3 -c`. `preparing kanban_complete` (and `kanban_complete call
succeeded`), zero `preparing kanban_block`.

Audit must **REFUSE** naming `check-partition-coverage.py` and
`assert-m2-speckit-conformance.py`, not `plan-migration-partition`.
KEEP `evidence/partition.json` is present so the refuse is the unmatched
reds, not a missing producer artifact.
