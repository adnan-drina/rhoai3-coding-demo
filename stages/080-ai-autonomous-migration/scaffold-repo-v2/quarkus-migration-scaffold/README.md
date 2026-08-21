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

## Suggested dest (Lead creates git only)

| Field | Suggestion | Why |
|---|---|---|
| Project / GitHub repo | `greeting-v2` (`adnan-drina/greeting-v2`) | No collision with `petclinic-rest-v42-refac` |
| How | `gh repo create` from **this** tree (Lead commission) | Template still publishes **v1** golden |
| Topics | none of `rhoai3-scaffolded` / `rhoai3-golden-path` | Those trigger Argo / v1 golden reset |
| Legacy | New ≤2-endpoint Spring Boot app, **not** PetClinic | AD-019 first success |
| First success | Dest reaches **M4** with zero dest-patches | Kernel must not grow before this |

Provision (Dev Spaces) is a **later** Operator GO. Git exists first.

## Custom kernel (not in this tree yet)

AD-019 day-one KEEP/REHOST only: typed body + digest, `pre_tool_call`
write fence, park-at-birth via native parents + `ack_gate`, thin mint
converter, authoring-side hermeticity. Everything else starts out.
