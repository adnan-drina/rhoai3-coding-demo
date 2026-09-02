# Scaffold Repos

Source-of-truth staging for the GitHub scaffold repositories that the golden-path templates (registered by stage 050's RHDH component) copy from. Each staging folder lives with its consuming stage. The templates never mutate these repos: every template run copies a golden repo into a fresh per-run repository (topic `rhoai3-golden-path`), so demo runs are isolated and reset is cheap.

| Scaffold repo (github.com/adnan-drina) | Consumed by template | Source of truth |
|---------------------------------------|----------------------|-----------------|
| `agentic-quarkus-scaffold` | `agentic-quarkus-scaffold` (stage 070) | Authored here in `agentic-quarkus-scaffold/` |
| `quarkus-migration-scaffold` | `app-migration` on `overlay-a8-publish` (v1 live) | Authored in `stages/080-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold/` |
| `quarkus-migration-scaffold-v2` | `app-migration` on `harness-v2` | Same authoring path; publish with `scripts/bootstrap-migration-scaffold-v2.sh`. Do not GitHub-rename v1. |

## Usage

```bash
# v1 goldens (overlay-a8-publish). Do not run this from harness-v2.
./scripts/bootstrap-scaffold-repos.sh

# harness-v2 Stage 080 golden only (never force-pushes v1)
./scripts/bootstrap-migration-scaffold-v2.sh
```

Re-running force-pushes the staged scaffold state — this is the reset mechanism for the golden sources. Per-run repos created by templates are cleaned up separately (delete repos carrying the `rhoai3-golden-path` topic).
