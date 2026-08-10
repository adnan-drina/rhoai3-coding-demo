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

```bash
python3 .hermes/skills/sdd-readiness/scripts/check-operand-count.py .
python3 .hermes/skills/sdd-readiness/scripts/check-operand-count.py . migration/bodies/m3-s-010.json
```
