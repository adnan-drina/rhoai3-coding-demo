# M1 verifier (binding — M1 only)

**Status:** binding · **Authority:** Architect `E-20260818T095340Z` /
`E-20260818T095728Z` / `E-20260818T111730Z`. **M3 waits.** OBJECT a
`pre_tool_call` complete-deny hook as the first §A control.

A **verifier card** (not the M1 worker — AR-1.1) runs:

```text
python3 .hermes/skills/harness/dispatch-phase/scripts/check-m1-verifier.py /projects/modernized
```

**refuse-on-nonzero:** script exit is the authority.

| exit | action |
|---|---|
| 0 | `kanban_complete` the **M1 ACK GATE: findings** |
| 1 | do **not** complete; `hermes kanban block --kind needs_input <gate-id> "M1 verifier refuse-on-nonzero"` |
| 2 | harness defect — same `needs_input`; do not invent paths |

The M1 worker never grants `m1-findings.ack.yaml` and never completes the
gate. Unasserted residue → `needs_input`.
