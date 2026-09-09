---
name: dispatch-phase
description: >
  Use at dest-init to mint M1 ANALYZE with --idempotency-key so a repeated
  postStart is a no-op, and — only when .hermes/pins.json
  pins.planner.activation is "activated", or "pilot" with a seal naming the
  evidence bundle on disk — M2 PLAN as a child of M1 with the fixed key
  m2-plan. Never mints M3 or M4 (K4 mints those from an
  ADMITTED admission receipt). Never creates cards in triage; never
  specify, decompose, swarm, or kanban daemon --force. The RHDH
  autoStartMigration checkbox defaults true; off skips mint. Do not use
  for story implementation.
license: Apache-2.0
compatibility: Linux seat; Hermes Kanban; dest-init postStart
metadata:
  author: rhoai3-harness-team
  version: "2.0.0"
  hermes:
    tags:
    - harness
    - dest-init
    category: harness
    kind: guidance
---
# Auto-start M1 ANALYZE (dest-init consumer)

`scripts/autostart-migration.sh --root <project>` mints M1 ANALYZE and
writes `.hermes/AUTOSTART-STATUS`. Must not fail the workspace start —
the destfile/GitOps hook is `|| echo WARN`.

| pins.planner.activation | Cards minted | Why |
|---|---|---|
| `not-activated` (golden default) or absent | **M1 only** | The replacement planner has not passed the activation gate (SOLUTION-ARCHITECTURE §12). M2 stays unavailable; a hand-minted M2 card blocks at its first step. |
| `activated` (named GO after the gate) | M1, then **M2 PLAN** as a child of M1 (`--idempotency-key m2-plan`, `--skill paved-road-m2`) | The dispatcher promotes M2 when M1 is `done`; M2 runs the deterministic planner and K4 mints M3/M4 only from an ADMITTED receipt. |
| `pilot` (Operator seal `{run_id, authorized_by, evidence_bundle_sha256}`) | At dest-init, **M1 only** (no bundle exists yet). Once the seal names the bundle on disk, re-running this script mints **M2 PLAN** (M1 is idempotent). A seal for another bundle mints nothing. | The same `planner.pins.activation_gaps` check gates the first M2 step, admission and K4; the seal is written by the Operator into the dest's `.hermes/pins.json`, never by a worker. |

The script reads the pin; it never changes it. M3 and M4 come from
`k4_mint.py` during M2 (receipt-bound idempotency keys, including M4).
