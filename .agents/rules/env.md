---
name: env
skill-group: Demo Environment
skill-prefix: env-
applies-to:
  - .env
  - .env.*
  - env.example
  - docs/OPERATIONS.md
  - docs/TROUBLESHOOTING.md
  - stages/010-openshift-ai-platform-foundation/deploy.sh
  - scripts/shared/lib.sh
  - scripts/shared/validate-lib.sh
  - scripts/platform/validate-stage-flow.sh
  - stages/*/deploy.sh
  - stages/*/validate.sh
  - "**/deploy.sh"
  - "**/*secret*.yaml"
---

# Demo Environment

Use the `env-*` skills as the source of truth for work with live OpenShift demo environments:

- `.agents/skills/rhoai-troubleshoot/SKILL.md`
- `.agents/skills/resume-gpu-demo/SKILL.md`
- `.agents/skills/manage-resources/SKILL.md`
- `.agents/skills/validate-demo-step/SKILL.md`
- `.agents/skills/manage-devspaces/SKILL.md`

Before live cluster work, load the repo-local environment, verify the expected API server guard, and keep credentials scoped to this project.

## OpenShift Safety Guard

- Before running live `oc`/`kubectl` commands, verify the target cluster against
  the repo-local environment guard.
- Set `RHOAI_EXPECTED_API_SERVER` in the local `.env` to a unique target
  API-server substring before deploy, validate, bootstrap, or resource-management scripts run.
- Do not bypass the guard with `RHOAI_ALLOW_UNGUARDED_CLUSTER=true` unless the
  user explicitly confirms the current cluster and the command is low risk.

## Bootstrap Configuration (set by Stage 010 `deploy.sh`)

- ArgoCD `resourceTrackingMethod` MUST be `annotation` (not `label` or `annotation+label`)
- The `rhoai-demo` AppProject MUST exist; all Applications use `project: rhoai-demo`
- The ArgoCD application controller has `cluster-admin` via ClusterRoleBinding (acceptable for demo)
- Custom health checks are configured for PVC (WaitForFirstConsumer), InferenceService, and TrustyAIService

## Self-Signed Certificates

The demo cluster uses self-signed certificates. Skipping TLS verification is fine everywhere: `--insecure-skip-tls-verify=true` (oc), `-k` (curl), `verify=False` / unverified SSL contexts (Python), `insecureSkipTLSVerify` or `skipTLSVerify` in product config. Do not implement production PKI, CA distribution or certificate rotation for this demo. Keep CA trust that already works; do not add more.

## Secrets Handling

- Secrets are created by `deploy.sh` reading `.env`, by idempotent Argo CD sync
  or PostSync Jobs, or by explicit `oc` commands documented in operations docs.
- Demo secrets with placeholder values are committed to GitOps with a
  `DEMO VALUES ONLY` comment header.
- Never commit real credentials.

### Security Posture (Demo Context)

**Keep security configuration simple.** This is a demo environment. Use the product's default or documented basic
security setup and do not add hardening layers that the demo does not need. Do not implement, unless the user asks
or a stage's story is about that control:
- extra ValidatingAdmissionPolicies, per-object `resourceNames` scoping or other least-privilege refinement beyond
  a plain namespaced Role;
- token expiry guards, automated credential rotation or rotation tooling;
- extra NetworkPolicies, egress restrictions or egress proxies;
- certificate handling beyond what already works.
Prefer the simplest configuration that works and is documented by the product. When a security finding comes up,
record it (component README or BACKLOG) instead of building a control, and say so.

This does not relax the controls the demo *shows*: MaaS identity, API keys, quotas and rate limits (Stage 040),
persona separation between `ai-admin` and `ai-developer`, and governed model access stay as designed. Do not remove
an existing, working control just to simplify; simplify it when you are changing that area anyway.

What we accept for the demo:
- Self-signed certs with TLS verification bypassed
- Demo-value secrets committed to GitOps (with `DEMO VALUES ONLY` header)
- `cluster-admin` RBAC for ArgoCD application controller
- No NetworkPolicies (except where operators create them)
- Secrets in env vars for database passwords (MinIO, MariaDB, PostgreSQL)

What we do NOT accept even for the demo:
- Real credentials committed to git (always use `.env` + `load_env`)
- `privileged: true` on any workload container
- `hostPath` volume mounts
- Docker/containerd socket mounts
- Wildcard RBAC (`*` verbs on `*` resources) outside of ArgoCD

### ODH Managed Label

Do NOT add `opendatahub.io/managed: "true"` to secrets in GitOps manifests. The ODH model controller watches for this label and deletes secrets it didn't create, causing an infinite create-delete loop with ArgoCD.

## Environment File

- Template: `env.example` (no leading dot for visibility)
- User copy: `.env` (gitignored)
- Load pattern: `deploy.sh` sources `.env` via `lib.sh:load_env()`

## Agent Behavior

- Before running `oc` commands that modify cluster state, verify the cluster
  context: `oc whoami` and `oc project`
- Before modifying a stage, read its README first
- Every implemented stage has at least three deliverables: `deploy.sh`,
  `validate.sh`, and `README.md`. Workflow-only stages (110, 120, 130) have only `validate.sh` and README — their platform resources are owned by Stage 070.
