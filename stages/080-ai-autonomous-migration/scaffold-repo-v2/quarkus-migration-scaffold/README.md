# Quarkus Migration Scaffold (harness-v2)

Empty destination scaffold for the AD-019 rebuild. **Not provisioned.**
The live workshop still uses v1 (`scaffold-repo/quarkus-migration-scaffold`
on `overlay-a8-publish`).

When this tree is eventually cloned as `/projects/modernized`, the workspace
shape stays the platform default:

| Folder | Role |
|---|---|
| `/projects/legacy` | Application being migrated — read-only, workspace-only |
| `/projects/modernized` | This repository — Quarkus destination |

Until then this directory is authoring-only: pins + a user-tier Hermes
config stub. Model credentials and provider URLs belong in Managed Scope
(`.env` / `$HERMES_MANAGED_DIR`), never in git.

## Pins

See `.hermes/pins.json`. Re-verify at first provision. Official docs are
product authority (Hermes live pages; Spec Kit repo at the pinned
`specify-cli` version).

## Suggested dest (not created)

Do **not** reuse `petclinic-rest-v*` (v34–v42 harvest / v42 live) and do
**not** use the RHDH `app-migration` template as it stands — that template
bootstraps **v1** golden.

| Field | Suggestion | Why |
|---|---|---|
| Project name | `greeting-v2` | Template pattern `^[a-z][a-z0-9-]{2,40}$`; no collision with `petclinic-rest-v42-refac` |
| Dest git | New empty repo, unpublished until GO | Isolation from `adnan-drina/quarkus-migration-scaffold` |
| Namespace / DevWorkspace | same as project name | Platform convention; keep off v42’s namespace |
| Legacy | New ≤2-endpoint Spring Boot app, **not** PetClinic | AD-019 first success; disjoint from the v1 specimen |
| First success | That dest reaches **M4** with zero dest-patches | Kernel must not grow before this |

Provision path when Operator GOs dest (not now): clone **this** tree into
the new dest repo, add a dest `devfile.yaml` in a later increment, open a
Dev Spaces workspace from that dest — never from a recut of v1.

## Custom kernel (not in this tree yet)

AD-019 day-one KEEP/REHOST only: typed body + digest, `pre_tool_call`
write fence, park-at-birth via native parents + `ack_gate`, thin mint
converter, authoring-side hermeticity. Everything else starts out.
