---
name: dispatch-phase
description: >
  Use at dest-init to mint M1 ANALYZE and M2 PLAN together with
  --idempotency-key so a repeated postStart is a no-op. Do not mint M3
  or M4. Do not kanban daemon --force. The RHDH autoStartMigration
  checkbox defaults true now that this consumer exists; off skips mint.
  Do not use for story implementation.
license: Apache-2.0
compatibility: Linux seat; Hermes Kanban; dest-init postStart
metadata:
  author: rhoai3-harness-team
  version: "1.0.0"
  hermes:
    tags:
    - harness
    - dest-init
    category: harness
    kind: guidance
---
# Auto-start M1+M2 (dest-init consumer)

`scripts/autostart-migration.sh --root <project>` mints the T0 chain the
way dest-13 did by hand: M1 ANALYZE then M2 PLAN parented to M1.
Writes `.hermes/AUTOSTART-STATUS`. Must not fail the workspace start —
the destfile/GitOps hook is `|| echo WARN`.

M3 comes from `k4_mint` during M2. M4 is minted with the M3 stories as
parents. This script must not create those cards.
