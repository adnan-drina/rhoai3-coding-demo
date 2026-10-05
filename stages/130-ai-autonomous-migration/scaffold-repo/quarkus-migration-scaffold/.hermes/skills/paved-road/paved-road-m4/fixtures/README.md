# paved-road-m4 fixtures

Each fixture is an official kanban log plus the KEEP artifacts the audit reads.

- `green-m4` — the steps in order, every KEEP present → PASS. The generator runs
  between the parity runner and the pre-verdict runner, and KEEPs
  `evidence/tests/generated-manifest.json`: the rebuild the runner drives is what
  executes the generated cases.
  The commit step then runs between the generator and every gate that reads the
  tree: the generated files are written into a tree `assert-retrievable-tree`
  still requires to be committed.
- `verdict-before-runner` — the pre-verdict runner never ran → REFUSE (silence): the
  verdict would cite receipts nothing produced.
- `no-oracles` — the source oracles were never captured → REFUSE: an expected runtime
  value has no source.
- `runner-red-no-rerun` — the runner exited 1 and was not re-run → REFUSE.
- `missing-verdict` — every step ran but `evidence/verdicts/m4-verdict.json` is absent
  → REFUSE (missing KEEP): a phase that produced no verdict did not verify anything.
- `read-after-runner` — PASS: the v9 t_caf2ad51 shape (2026-09-22). The runner ran once and passed; a later `grep … run-m4-pre-verdict.sh` the worker ran while reading it exited 1. A read that names a mandated script is not a run of it, so its exit code is not the step's.
