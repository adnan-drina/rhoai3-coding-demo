# Scaffold Repos

Source-of-truth staging for the GitHub scaffold repositories that the golden-path templates (registered by stage 050's RHDH component) copy from. Each staging folder lives with its consuming stage. The templates never mutate these repos: every template run copies a golden repo into a fresh per-run repository (topic `rhoai3-golden-path`), so demo runs are isolated and reset is cheap.

| Scaffold repo (github.com/adnan-drina) | Consumed by template | Source of truth |
|---------------------------------------|----------------------|-----------------|
| `agentic-quarkus-scaffold` | `agentic-quarkus-scaffold` (stage 070) | Authored here in `agentic-quarkus-scaffold/` |
| `quarkus-migration-scaffold` | `app-migration` (stage 080) | Authored in `stages/080-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold/` |

## Usage

```bash
# Create or reset the golden repos (requires gh auth with repo scope)
./scripts/bootstrap-scaffold-repos.sh
```

Re-running force-pushes the staged scaffold state — this is the reset mechanism for the golden sources. Per-run repos created by templates are cleaned up separately (delete repos carrying the `rhoai3-golden-path` topic).
