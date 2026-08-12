# S-008 quarantine / resurrection ordering (W4)

**Cite:** Architect E-163136Z · quarantine-survives-dispatch.md · W4 plan row

## Rule

When Owner / Pet / Visit (or equivalent specimen triad) land after a quarantine
wipe, **partition order is**:

1. **Owner** (and Owner-owned models/repos) first — parent of Pet/Visit graphs  
2. **Pet** next — depends on Owner  
3. **Visit** last — depends on Pet (and often Owner)

Create/remint must not resurrect tombstoned Override pollution
(`assert-quarantine-tombstones.py`). New partition cards use **parent-chain**
links (Pet→Owner, Visit→Pet) so official Kanban deps enforce order; FIS ≤ ~5
per card (`check-operand-count.py --v13`).

## Verification

- Tombstones hold across create/dispatch (existing assert).  
- Partition plan for S-008-class work lists Owner → Pet → Visit with parent ids.  
- False `pre-exists` on wiped paths fails D1 (`assert-dependency-closure.py`).
