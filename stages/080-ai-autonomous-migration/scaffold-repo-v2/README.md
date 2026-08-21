# scaffold-repo-v2 (AD-019)

Authoring-side golden tree for the **harness-v2** campaign. It is **not**
the live Stage 080 scaffold.

| Tree | Path | Branch | Dest-apply |
|---|---|---|---|
| v1 (live) | `scaffold-repo/quarkus-migration-scaffold/` | `overlay-a8-publish` | yes (existing RHDH template) |
| v2 (this) | `scaffold-repo-v2/quarkus-migration-scaffold/` | `harness-v2` | **no** until a separate Operator GO |

Architecture: `harness-refactoring/architecture/SOLUTION-ARCHITECTURE-v2.md`
(nested ledger; not in this git).

## What this increment contains

- `quarkus-migration-scaffold/README.md`
- `quarkus-migration-scaffold/.hermes/pins.json`
- `quarkus-migration-scaffold/.hermes/config.yaml` (Managed-Scope-compatible stub)

No skills, no mint, no `validate.sh`, no `devfile.yaml`, no dest.

## Forbidden until a later GO

- Pointing `gitops/.../app-migration/template.yaml` at this tree (today it
  clones v1 `adnan-drina/quarkus-migration-scaffold`).
- Argo / RHDH recut from `harness-v2`.
- Provisioning a dest workspace from this tree.
- Copying v1 `scaffold-repo/` scripts into this directory.

Kernel (K1–K5) is named in AD-019. It is not implemented here.
