# Dev Spaces dispatcher posture (tip-bank B5 / B6)

**Basis:** in-tree harness obligations (sibling contracts + skills).
**Status:** interim documentation until v14 orchestrator-mint (AD-016)

## B5 — daemon vs gateway

Official Hermes Kanban dispatch is a **gateway-embedded** loop. Standalone
`hermes kanban daemon` is deprecated; two dispatchers on one `kanban.db` are
unsupported (claim races).

**Dev Spaces seats** in this demo have no long-lived Hermes gateway process.
Measured posture (v13):

```bash
export HERMES_MANAGED_DIR=/projects/.platform/hermes
export HERMES_HOME=/projects/modernized/.hermes/home
hermes kanban daemon --force # single dispatcher; document if started
```

Do **not** invent Class-A dispatch wrappers. Prefer documenting this seat
constraint and feeding it into v14 graph design (orchestrator-owned mint
dispatch) rather than normalizing dual-dispatchers.

## B6 — promote vs park-at-birth

Create-path law: M3 children are **parked/blocked at birth** (serial drain).
Native Hermes may auto-promote children when the parent Planning task reaches
`done` (observed v13: all nine M3s flipped ready on M2b complete).

**Interim control (until v14):** after Planning-task Done, human steward re-parks
non-GO stories and promotes exactly one serial GO. Do not resurrect custom
dispatch wrappers to fight the engine.

**v14 intent:** orchestrator-mint dissolves the mismatch — birth state and
fan-out are graph-owned, not post-hoc nursing.
