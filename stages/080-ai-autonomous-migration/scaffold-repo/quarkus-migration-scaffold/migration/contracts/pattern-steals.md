# Pattern-steals contract (Loiane → migration scaffold)

**Status:** binding for workspace gates · **Not** a copy of Loiane's toolkit  
**Sources:** Architect `E-20260808T061327Z`; Research toolkit + `.specs/` docs  
**Placement:** this golden scaffold only (consumed in `/projects/modernized`).  
Never `harness-refactoring/` authoring trees; never committed `.specify/`.

AD-S / Hermes / Kanban / `github/spec-kit` stand. These are **fail-closed
shapes** we absorb; enforcement lives in skill **`sdd-readiness`**
(`.hermes/skills/sdd-readiness/`).

**Companion:** brief identity carry-forward, graph layering, and re-plan
authority live in `migration/contracts/sdd-ordering.md` (**AD-S §S.6**).
Homes: `.hermes/LAYOUT.md`.

## Sequencing (Lead)

| Pri | Steal | Land |
|-----|--------|------|
| P0 | No-invention + open-question exit; Non-Goals | **Landed** — skill `sdd-readiness` (+ AD-S Non-Goals override) |
| P0 | Task packet shape (`AC-IDs`, `files_in_scope`, deps) | **Landed** — same skill; Kanban body fill rides phase schema |
| P0 | Waiver re-open triggers | **Landed** — `migration/schemas/mta-exception.md` + readiness lint |
| P1 | Baseline-aware brownfield | **After** first specimen runs — `_baseline`-shaped artifact under `migration/` |
| P1 | EARS-lite / AC traceability | **After** M3 SPECIFY path produces stable AC IDs — evaluate companion |
| P1 | Single validate entrypoint | **Landed** — skill `harness-validate` |
| P2 | Confirmed-red (assertion-red only) | **After** fixtures; optional pre-IMPLEMENT; does not replace G-1 |
| P2 | Forbid skip / silent threshold drop | **With** CI/factory preflight |

Cut-order inventory → fixtures → mta-cli → NetworkPolicy → Review §11 **does not pause** for P1/P2.

## Out of scope

Tri-platform trees, Java 25 / Boot 4 / Angular pins, replacing AD-S `specify init`,
treating `/onboard` as M1 reverse-spec, Loiane coverage floors as G-4 substitutes.

## P0 shapes

### Spec / brief readiness

Before Kanban-ready / phase advance:

1. Active specs **must** include a non-empty `## Non-Goals` section (AD-S).
2. Unresolved open questions (`Q-*` with unchecked `- [ ]` or explicit
   `status: open`) **block** readiness.
3. Invention outside Non-Goals / AC set is a process violation (sensors + review).

### Task packets (Kanban / `migration/tasks/*.json`)

Every IMPLEMENT task packet **must** carry:

| Field | Meaning |
|-------|---------|
| `ac_ids` | AC / contract refs this task closes |
| `files_in_scope` | Paths the worker may edit |
| `deps` | Task ids that must be done first |

Out-of-scope edits are refuse-worthy where the gate can see the path list.

### `mta-exception` / baseline waivers

Every waiver **must** include a checkable `re_open_trigger` (command, version
gate, or condition) — never bare `"skipped"`. See
`migration/schemas/mta-exception.md`.
