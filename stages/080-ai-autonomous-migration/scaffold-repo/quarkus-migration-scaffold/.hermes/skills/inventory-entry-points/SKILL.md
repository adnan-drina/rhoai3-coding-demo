---
name: inventory-entry-points
description: >
  Scan a Java tree for HTTP and non-HTTP entry points (W2 §11.3). Use before
  plan/Kanban populate and as a completion drift check. Ship even if near-empty.
---

# Entry-point inventory

## When to use

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
