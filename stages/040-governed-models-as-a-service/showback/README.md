# Showback

Stage 040 shows what the private models cost in two custom Observability tabs (**Cost per token**, **Tokenomics ·
break-even (live)**) and can export measured MaaS usage for a time window. Neither is an invoice: prices are dashboard
variables, and the raw export stays unpriced (`../showback-ratecard.json` is the reviewed unpriced rate card it
requires).

| Script | When to run |
|---|---|
| `generate-dashboards.sh [--write\|--check]` | After changing a dashboard. Edit the generator, run `--write`, review and commit both files in `gitops/stages/040-governed-models-as-a-service/040-maas-platform/observability/`; Argo CD applies them. `--check` (read-only) fails when a committed dashboard differs from the generator; without an option it prints both. Offline, no cluster access. |
| `export-usage.sh --from UTC --to UTC --output FILE` | When you need raw governed usage for an explicit UTC window (1 minute to 89 days): tokens, authorized and limited calls per user, subscription and model from the native RHOAI Thanos, through a local port-forward. Read-only on the cluster. Writes a private CSV and `FILE.json` coverage receipt (mode 0600) and refuses to overwrite either; they contain identities, so keep them out of Git. For everyday usage, the dashboard **Usage** page's **Export as CSV** is the native path. |

The generator writes the files in PyYAML's `safe_dump` layout (the format they were first generated in) through
Ruby's libyaml emitter, so a regeneration without a content change leaves `git diff` empty.
