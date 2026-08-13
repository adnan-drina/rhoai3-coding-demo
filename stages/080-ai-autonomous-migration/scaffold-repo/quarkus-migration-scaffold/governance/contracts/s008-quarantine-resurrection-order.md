# S-008 quarantine / resurrection ordering (W4)

**Status:** binding (in-tree).

## Rule

When a **parent → child → grandchild** entity triad (S-008 scar roles; do not
paste specimen type names into guidance) lands after a quarantine wipe,
**partition order is**:

1. **Parent** (and parent-owned models/repos) first
2. **Child** next — depends on parent
3. **Grandchild** last — depends on child (and often parent)

Create/remint must not resurrect tombstoned Override pollution
(`assert-quarantine-tombstones.py`). New partition cards use **parent-chain**
links (child→parent, grandchild→child) so official Kanban deps enforce order;
FIS ≤ ~5 per card (`check-operand-count.py --v13`).

The create-path lint (`check-s008-resurrection-order.py`) still matches the
scar role tokens in partition/bodies; this contract states the order without
embedding specimen slash-forms.

## Verification

- Tombstones hold across create/dispatch (existing assert).
- Partition plan for S-008-class work lists parent → child → grandchild with
  parent ids.
- False `pre-exists` on wiped paths fails D1 (`assert-dependency-closure.py`).
- **Lint:** `check-s008-resurrection-order.py` — create/remint
  (`create-m3-implementer.sh`, `dispatch-phase.sh`) refuse child-before-parent
  or grandchild-before-child when the triad co-occurs in `partition.json` /
  bodies.
