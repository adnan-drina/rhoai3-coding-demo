# scaffold-repo-v2 (AD-019)

Authoring-side golden tree for the **harness-v2** campaign. It is **not**
the live Stage 080 scaffold.

| Tree | Path | Branch | Dest-apply |
|---|---|---|---|
| v1 (live) | `scaffold-repo/quarkus-migration-scaffold/` | `overlay-a8-publish` | yes (existing RHDH template) |
| v2 (this) | `scaffold-repo-v2/quarkus-migration-scaffold/` | `harness-v2` | **no** until a separate Operator GO |

Architecture: `harness-refactoring/architecture/SOLUTION-ARCHITECTURE-v2.md`
(nested ledger; not in this git). Lead cards: `docs/LEAD-COMMISSION-HARNESS-V2-DEST-GIT.md`.

## Clean-slate (BIND)

- v2 commits touch **only** `scaffold-repo-v2/`. A v2 commit that edits `scaffold-repo/` is a defect.
- `overlay-a8-publish` takes no new v1 harness work except **v42 harvest**.
- v42 is ephemeral — harvest before wipe (HV-1). Not this tree’s job.
- Never `scripts/bootstrap-scaffold-repos.sh` for v2 (force-pushes v1 golden). Future golden name: `quarkus-migration-scaffold-v2`.

## Dest git (Lead; not provisioned)

| Field | Value |
|---|---|
| GitHub | `adnan-drina/greeting-v2` |
| Source | `quarkus-migration-scaffold/` in this directory |
| Topics | **none** of `rhoai3-scaffolded` / `rhoai3-golden-path` until provision GO |
| Template | Do **not** use RHDH `app-migration` (still clones v1) |

## What this tree contains

- `quarkus-migration-scaffold/README.md`
- `quarkus-migration-scaffold/.hermes/pins.json`
- `quarkus-migration-scaffold/.hermes/config.yaml` (Managed-Scope-compatible stub)
- `docs/` — research prompt rev 2, Lead dest-git commission

No skills, no mint, no `validate.sh`, no dest provision.
