---
name: inventory-entry-points
description: Inventory REST/JPA entry points for M1
version: 1.1.0
author: rhoai3-harness-team
license: Apache-2.0
platforms: [linux]
metadata:
  hermes:
    tags:
    - analysis
    - m1
    category: analysis
---
# Entry-point inventory

## When to Use

- Before M2 plan / Kanban populate (precondition)
- After slices land (drift check)
- Against `legacy@3.x` (`harvest_referent`), not an invented list

## Procedure

```bash
python3 "${HERMES_SKILL_DIR}/scripts/inventory-entry-points.py" \
  /projects/.derived/legacy-at-3 \
  -o migration/entry-point-inventory.json
```

Kinds: `http`, `non-http` (`lifecycle`, `scheduled`, `messaging`, `cli`, `event`).
Execution evidence is always recorded (`ran: true`) so zero entry points ≠ "did not scan."


## Verification

- Scripts under `scripts/` exit 0 on a healthy seat.
- Conformance lint passes for this skill.
