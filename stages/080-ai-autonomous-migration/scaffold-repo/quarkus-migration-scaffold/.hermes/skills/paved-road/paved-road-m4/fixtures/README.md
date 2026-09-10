# paved-road-m4 fixtures

Each fixture is an official kanban log plus the KEEP artifacts the audit reads.

- `green-m4` — the five steps in order, every KEEP present → PASS.
- `verdict-before-runner` — the pre-verdict runner never ran → REFUSE (silence): the
  verdict would cite receipts nothing produced.
- `no-oracles` — the source oracles were never captured → REFUSE: an expected runtime
  value has no source.
- `runner-red-no-rerun` — the runner exited 1 and was not re-run → REFUSE.
- `missing-verdict` — every step ran but `evidence/verdicts/m4-verdict.json` is absent
  → REFUSE (missing KEEP): a phase that produced no verdict did not verify anything.
