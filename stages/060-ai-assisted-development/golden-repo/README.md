# Golden Repo

Source-of-truth staging for the GitHub "golden repositories" that the Stage 050 golden-path templates copy from. The templates never mutate these repos: every template run copies a golden repo into a fresh per-run repository (topic `rhoai3-golden-path`), so demo runs are isolated and reset is cheap.

| Golden repo (github.com/adnan-drina) | Consumed by template | Source of truth |
|---------------------------------------|----------------------|-----------------|
| `agentic-quarkus-scaffold` | `agentic-quarkus-scaffold` (stage 070) | Authored here in `agentic-quarkus-scaffold/` |

## Usage

```bash
# Create or reset the golden repos (requires gh auth with repo scope)
./scripts/bootstrap-golden-repos.sh
```

Re-running force-pushes the golden state — this is the reset mechanism for the golden sources. Per-run repos created by templates are cleaned up separately (delete repos carrying the `rhoai3-golden-path` topic).
