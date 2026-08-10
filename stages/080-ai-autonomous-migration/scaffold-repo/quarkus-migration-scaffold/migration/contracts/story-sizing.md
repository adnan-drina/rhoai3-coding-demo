# Story sizing denominator (Architect E-20260810T104925Z / E-20260810T110403Z)

**Status:** binding proving-min  
**Sources:** Architect BIND story sizing · Lead land `check-operand-count.py`

## Rule

M3 scope **MUST** carry a measured operand count. Phase-name sizing **REJECT**.
Bigger wall **REJECT**. Decompose when units exceed the effort-class cap.

## Authoring fields

On M3 `identity`:

| Field | Rule |
|-------|------|
| `operand_count` | required int ≥ 1; **MUST** equal measured dest `src/**` write count |
| `sizing_basis` | required; must be `operand_count` (not `phase_name`) |

Measured count uses the same dest normalization as implementer checkpoints
(`files_writable` preferred, else `files_in_scope` destination `src/` paths).

## Caps (proving-min)

| `effort_class` | Max operands |
|----------------|--------------|
| default / unset | 40 |
| `high` / `effort-high` | 80 |

Over-cap → **REFUSE** create / body lint (`BODY_SIZE`). Split the story; do not
raise the wall.

## Wall-fit (Architect E-20260810T111450Z)

Count caps alone are unsound for “decompose when units > wall”. At **create**
time (`create-m3-implementer.sh` passes `--wall-fit`):

`estimated_seconds = operand_count × 75` (proving-min seconds/operand)

Refuse when `estimated_seconds > runtime_budget_sec` (or phase default
2700 / effort-high 3600). Example: **60 × 75 = 4500 > 3600** → REFUSE.

Board-wide `check-kanban-body` keeps count/caps only (no `--wall-fit`) so a
named verification undecomposed body does not freeze unrelated authoring.

```bash
python3 .hermes/skills/sdd-readiness/scripts/check-operand-count.py .
python3 .hermes/skills/sdd-readiness/scripts/check-operand-count.py . migration/bodies/m3-s-010.json --wall-fit
```
