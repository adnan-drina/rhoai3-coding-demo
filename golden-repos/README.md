# Golden Repositories

Source-of-truth staging for the GitHub "golden repositories" that the stage
050 golden-path templates copy from. The templates never mutate these repos:
every template run copies a golden repo into a fresh per-run repository
(topic `rhoai3-golden-path`), so demo runs are isolated and reset is cheap.

| Golden repo (github.com/adnan-drina) | Consumed by template | Source of truth |
|---------------------------------------|----------------------|-----------------|
| `parasol-insurance` | `assisted-quarkus-feature` (stage 060) | Derived by `scripts/bootstrap-golden-repos.sh` from `redhat-ads-tech/parasol-insurance` (Kafka/messaging stripped) + the overlay in `parasol-insurance-overlay/` |
| `agentic-quarkus-scaffold` | `agentic-quarkus-scaffold` (stage 070) | Authored here in `agentic-quarkus-scaffold/` |
| `migiq-spring-boot-sample` | `autonomous-migration` (stage 080) | Already golden upstream; verified only |

## Usage

```bash
# Create or reset the golden repos (requires gh auth with repo scope)
./scripts/bootstrap-golden-repos.sh
```

Re-running force-pushes the golden state — this is the reset mechanism for
the golden sources. Per-run repos created by templates are cleaned up
separately (delete repos carrying the `rhoai3-golden-path` topic).

## Verification note

`parasol-insurance-overlay/.continue/config.yaml` references
`${MAAS_API_BASE_URL}` / `${MAAS_API_KEY}`. Continue's documented config
syntax for secret references differs (`${{ secrets.* }}`) — verify the
interpolation in a live workspace before the stage 060 demo relies on it
(review finding A6 in the enrichment review).
