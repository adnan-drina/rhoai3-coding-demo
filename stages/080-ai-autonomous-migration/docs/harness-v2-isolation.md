# Harness v2 isolation (branch `harness-v2`)

Operator GO 2026-08-21: v2 authoring stays in the same Stage 080 path as
v1. Isolation is a **new GitHub golden name**, not a sibling tree and not
a GitHub rename of v1.

| Surface | v1 (live) | v2 (this branch) |
|---|---|---|
| Platform git | `overlay-a8-publish` | **`harness-v2`**. Do not merge until dest cutover GO. Overlay takes no new v1 harness commits except **v42 harvest**. |
| Authoring | `stages/080-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold/` | **Same path** on this branch |
| Golden GitHub | `adnan-drina/quarkus-migration-scaffold` | **`adnan-drina/quarkus-migration-scaffold-v2`**. Do not GitHub-rename v1 (breaks v42 + live template URL). |
| Publish | `scripts/bootstrap-scaffold-repos.sh` | `scripts/bootstrap-migration-scaffold-v2.sh` |
| RHDH template `fetch:plain` | v1 golden (live Argo) | v2 golden **in this branch's** `gitops/.../app-migration/template.yaml` only |
| Dest | `petclinic-rest-v*` (v42 live) | Cut from Developer Hub **Application migration** when Operator is ready. Never `greeting-v2`. |

**Aborted isolation (do not resume):** sibling `scaffold-repo-v2/`; dest
git `adnan-drina/greeting-v2` (repo may still exist; do not provision; do
not add `rhoai3-scaffolded` / `rhoai3-golden-path`).

**OBJECT:** `bootstrap-scaffold-repos.sh` from this branch (force-pushes
v1); dest-apply overlay onto v42; dest-complete Operator ack gates;
`kanban daemon --force`; wipe v42 before HV-1 harvest.

Architecture: Stage 080 factory SAD
`stages/080-ai-autonomous-migration/SOLUTION-ARCHITECTURE.md` (this folder
only; not dest; not the workshop SAD). Campaign law:
`harness-refactoring/architecture/SOLUTION-ARCHITECTURE-v2.md` (AD-019;
nested ledger, not in this git). Research prompt (rev 2):
`docs/RESEARCH-PROMPT-V2-NATIVE-HARNESS.md` beside this file.
