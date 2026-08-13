# Quarantine survives dispatch (Class A)

**Status:** binding (in-tree).

## Problem

Wiping files from the live destination tree (`dir:/projects/modernized`) does **not** guarantee they stay gone across the next task dispatch. Observed on S-004: after abort quarantine of `springdatajpa/*RepositoryOverride.java`, a later dispatch restored a pre-quarantine polluted copy (~4 minutes into the run). Worker wrote zero Override files; git did not restore (paths were untracked). Resurrected bytes matched abort-run pollution (not raw legacy `@Profile` sources).

## Rule

1. Every intentional wipe of destination pollution must **register a tombstone** under `migration/quarantine/tombstones.json`.
2. Create / dispatch / reclaim gates must **assert tombstones hold** (paths absent from dest). Fail closed if a tombstoned path reappears.
3. Wipe helpers must move bytes into `migration/quarantine/<id>/` **and** register tombstones in one step.
4. Tombstones are measurement-neutral harness state (not product invent).

## Schema

`migration/quarantine/tombstones.json` — `rhoai3.quarantine-tombstones/v1`:

```json
{
 "schema": "rhoai3.quarantine-tombstones/v1",
 "tombstones": [
 {
 "path": "src/main/java/.../PetRepositoryOverride.java",
 "reason": "abort-run OOS Override residue",
 "task_id": "t_cc936c8b",
 "quarantine_dir": "migration/quarantine/abort-t_cc936c8b-run39/",
 "registered_at": "2026-08-11T17:12:00Z"
 }
 ]
}
```

Paths are workspace-relative under `/projects/modernized`.

## Scripts

- `register-quarantine-tombstone.py` — add/update tombstones after wipe
- `assert-quarantine-tombstones.py` — fail if any tombstoned path exists in dest
- Wired into `create-m3-implementer.sh` (pre-create) and `dispatch-phase.sh` (pre-dispatch)

## Sync mechanism (corrected — ABSORB )

| Mechanism | Role on S-004 cascade |
|-----------|------------------------|
| **Residual Hermes worker** | **Primary cause** — abort/terminal without process kill left run#39 / PID 85052 writing post-quarantine Overrides on shared `dir:/projects/modernized` |
| Hermes `workspace_kind=worktree` materialize | **Not used** — card is `dir:/projects/modernized` |
| `git checkout` / tracked restore | **Ruled out** — paths untracked |
| Raw `/projects/legacy` copy | **Ruled out** — legacy still has `@Profile` |
| Provisioning-snapshot theory | **Superseded** as primary (steward forensics; absorbed) |

Tombstones remain useful at **dispatch-time**. Mid-run zombie writes require
`governance/contracts/residual-worker-kill.md` (kill+verify at abort/terminal).
