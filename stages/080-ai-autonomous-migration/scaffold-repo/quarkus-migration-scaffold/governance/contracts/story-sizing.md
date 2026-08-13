# Story sizing denominator

**Status:** binding proving-min
**Basis:** story sizing · land `check-operand-count.py`

## Rule

M3 scope **MUST** carry a measured operand count. Phase-name sizing **REJECT**.
Bigger wall **REJECT**. Decompose when units exceed the effort-class cap.

## Authoring fields

On M3 `identity`:

| Field | Rule |
|-------|------|
| `operand_count` | required int ≥ 1; **MUST** equal measured dest write count for the class |
| `sizing_basis` | required; must be `operand_count` (not `phase_name`) |
| `operand_class` | optional; default `src_code`. Use `build_config` for pom.xml / resources-only CONFIG stories |

### Operand classes (specimen-agnostic)

| `operand_class` | Measured destinations | Default max | Sec/operand (wall-fit) |
|-----------------|----------------------|-------------|-------------------------|
| `src_code` (default) | dest paths under `src/**` | 40 (80 high) | 90 |
| `build_config` | `pom.xml`, `src/main/resources/**`, `src/test/resources/**` | 12 (20 high) | 180 |

Measured count uses `files_writable` preferred, else `files_in_scope` destination
paths, filtered by class. **Do not** invent `src/` placeholders to satisfy
`src_code` when the story is build/config — set `operand_class=build_config`.

## Caps (proving-min)

| `effort_class` | Max operands (`src_code`) | Max (`build_config`) |
|----------------|---------------------------|----------------------|
| default / unset | 40 | 12 |
| `high` / `effort-high` | 80 | 20 |

Over-cap → **REFUSE** create / body lint (`BODY_SIZE`). Split the story; do not
raise the wall.

## Wall-fit (R-M3.9 )

Count caps alone are unsound for “decompose when units > wall”. At **create**
time (`create-m3-implementer.sh` passes `--wall-fit` on **the body being created**):

`estimated_seconds = operand_count × seconds_per_operand(class)`

Refuse when `estimated_seconds > runtime_budget_sec` (or phase default
2700 / effort-high 3600). Example (`src_code`): **42 × 90 = 3780 > 3600** → REFUSE.
**Reject** blind wall raise alone — prefer **JPA-repos vs JDBC-repos** split.

Also refuse dual-stack (`…/jpa/…` **and** `…/jdbc/…`) when measured ≥ 20
(R-M3.9, `src_code` only) even if the arithmetic barely fits.

## Create vs corpus validation

- **Create path:** `check-kanban-body.py ROOT --body <this.json>` +
 `check-operand-count.py ROOT <this.json> --wall-fit` — single body only.
- **Corpus / R0:** `check-kanban-body.py ROOT` (no `--body`) scans all bodies;
 incomplete siblings must not block an individual create.

```bash
python3 .hermes/skills/sdd/check-spec-readiness/scripts/check-operand-count.py .
python3 .hermes/skills/sdd/check-spec-readiness/scripts/check-operand-count.py . evidence/bodies/m3-s-010.json --wall-fit
python3 .hermes/skills/sdd/check-spec-readiness/scripts/check-kanban-body.py . --body evidence/bodies/m3-s-001.json
```
