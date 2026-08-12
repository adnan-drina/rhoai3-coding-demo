# OpenShift Deployment (SUPPLEMENTARY — third-party sources)

> **Provenance warning.** Nothing in this file is official Nous Research
> documentation, and none of it is docs.redhat.com product documentation
> either. Sources: a Red Hat Developers ARTICLE (blog-tier) and a
> community GitHub repo. Use as deployment inspiration for stage 080;
> never cite as official Hermes behavior — the official extraction
> (`official-doc-extraction.md`) always wins on conflicts, and the
> conflicts section below lists the known ones.

## Sources

| Source | What | Date |
|---|---|---|
| https://developers.redhat.com/articles/2026/06/02/deploy-hermes-agent-openshift-ai-vllm-model-serving | Article: Hermes Agent on OpenShift AI with KServe/vLLM (author: Gerald Trotman) | 2026-06-02 |
| https://github.com/aicatalyst-team/hermes-openshift | Companion repo: Dockerfile.ubi, 9 kustomize manifests, examples (10 stars; pushed 2026-06-02) | 2026-06-02 |

Captured 2026-08-12 by the reviewer (manifests read directly from the
repo). Note the sources predate the v0.20.0 product anchor by two months —
Hermes moves fast; treat every mechanism claim as potentially stale.

## Architecture (as shipped by the sources)

Two components in one namespace (`hermes`):

1. **vLLM InferenceService** (KServe, `RawDeployment` mode,
   `vllm-cuda-runtime`, 1× `nvidia.com/gpu`, model from S3 data
   connection — `Qwen/Qwen2.5-3B-Instruct` in the manifests, 7B in the
   article) exposing OpenAI-compatible `/v1` in-cluster:
   `http://hermes-llm-predictor.hermes.svc.cluster.local:8080/v1`.
2. **Hermes Agent Deployment** — custom UBI9 image
   (`quay.io/aicatalyst/hermes-agent:latest`), 1 replica,
   `command: ["/opt/hermes/venv/bin/python", "-m", "hermes_cli.main"]`
   `args: ["gateway"]`, PVC-backed `HERMES_HOME=/opt/data`, ConfigMap
   env, Service + Route, HTTP probes on `/health`:8080.

## Reusable parts (verified compatible with official captures)

- **UBI9 image recipe**: Node.js 20 via NodeSource (UBI9 ships 16.x —
  official TUI requires Node ≥ 20), Python 3.11 venv at
  `/opt/hermes/venv`, non-root UID 1001.
- **Restricted-SCC-compatible securityContext**: `runAsNonRoot`,
  `allowPrivilegeEscalation: false`, `capabilities.drop: [ALL]`,
  `seccompProfile: RuntimeDefault` — matches the official "run as
  non-root" checklist item and the managed-scope enforcement model.
- **Single replica + PVC-backed HERMES_HOME**: consistent with official
  facts — one agent process per Hermes home (memory corruption
  otherwise), `state.db`/`kanban.db` are single-host SQLite. The
  article's own note ("multi-replica requires distributed state") aligns.
- **Secrets via Kubernetes Secret objects** (e.g. `TELEGRAM_BOT_TOKEN`)
  rather than baked into the image — compatible with the official
  secrets rule of thumb.
- **Kustomize layout** (9 numbered manifests) — fits this repo's GitOps
  conventions.

## VERIFIED CONFLICTS with official documentation — do not copy these

| Repo/article practice | Official position (verified in our extractions) |
|---|---|
| `GATEWAY_ALLOW_ALL_USERS: "true"` committed in the ConfigMap | Gateway Deployment Checklist item 1: "Set explicit allowlists — never use `GATEWAY_ALLOW_ALL_USERS=true` in production"; default is fail-closed ("If no allowlists are configured… all users are denied") |
| Qwen2.5-3B-Instruct (32K default context; article uses 7B, also 32K default) | "Hermes requires at least 64,000 tokens of context for agent use with tools" — smaller windows "rejected at startup". Serve a ≥64K-context model or explicitly configure a larger window server-side AND set `model.context_length` |
| Model wiring via `LLM_MODEL` env var; gateway port via `GATEWAY_PORT` | NEITHER variable exists in the official Environment Variables reference (verified absent 2026-08-12). Official model wiring is the `config.yaml` `model:` block (`provider: custom`, `base_url`, `default`, `context_length`, `max_tokens`). `OPENAI_BASE_URL` IS official ("Base URL for custom endpoint (VLLM, SGLang, etc.)") |
| No `config.yaml` at all — env-only configuration | Officially, secrets go in `.env`, "everything else goes in `config.yaml`"; no compression/context/max_tokens tuning is possible via env ("no environment variables for" those, by design) |
| Webhook-style per-platform gateway endpoints (`POST /telegram`, …); article admits "basic HTTP endpoints" with production limitations | The documented gateway is `hermes gateway run/start` with platform adapters; supervised deployments must honor the exit-75 restart contract. Treat the repo's HTTP shim as its own code, not Hermes's gateway surface |
| No admin-tier config pinning | Managed Scope exists for exactly this shape: mount a read-only ConfigMap at `/etc/hermes` (or bake `HERMES_MANAGED_DIR` into the image/Deployment env — official guidance: fixed by the administrator, "not left user-settable") to pin `model.*`, `security.redact_secrets`, approvals posture fleet-wide |

## Stage 080 adaptation notes (our platform, our rules)

- Wire the model per the official mechanism: `model:` block with
  `provider: custom`, `base_url` pointing at the vLLM/MaaS endpoint,
  explicit `context_length` and `max_tokens` (see
  `hermes-configuration`; stage 080 field experience: pin context and
  output caps explicitly — server defaults bite).
- Pin fleet policy via Managed Scope, not per-seat config: ConfigMap →
  `/etc/hermes/config.yaml` mount is the natural OpenShift mapping (see
  `hermes-managed-scope`; managed `.env` is world-readable — non-sensitive
  values only; provider keys via Secret-backed env or vault sources).
- Headless gateway pods need the hooks-consent escape hatch
  (`HERMES_ACCEPT_HOOKS=1`) if shell hooks are configured, and an
  explicit approvals posture (see `hermes-hooks`, `hermes-cli`).
- Kanban dispatch requires the gateway process; the board is single-host —
  one board per pod, bridged externally if needed (see `hermes-kanban`).
- `hermes update` doesn't apply in containers (official: "Updating is
  done by running a new image") — image rebuild pipeline, which fits this
  repo's GitOps model anyway.
