# Implementation Detail Boundary

Stage READMEs are not deployment runbooks, but they must contain enough implementation detail that a reader can understand the system without reading every manifest. This reference defines what belongs in a README versus what belongs in `docs/OPERATIONS.md` or the manifests alone.

## The Boundary Rule

> **Include implementation details that affect understanding, troubleshooting,
> or cross-stage dependencies. Exclude operational procedures, step-by-step
> commands, and transient runtime state.**

A reader of the README should be able to answer:
- What mechanism deploys this component? (hook Job, overlay, direct CR, script)
- What are the key governance boundaries? (quotas, RBAC, rate limits)
- Why are specific values chosen? (sizing rationale, compatibility guards)
- What does this stage provide to downstream stages?

A reader should NOT find in the README:
- Shell commands to run
- Login credentials or secret values
- Step-by-step deployment walkthroughs
- Validation output or log excerpts
- Transient cluster state or timestamps

## What Belongs in a README

### Deployment Mechanisms

When a component is deployed through a non-obvious mechanism, name it:

| Pattern | README should say |
|---------|-------------------|
| Argo CD Sync hook Job patches a shared CR | "via an Argo CD Sync hook Job (`job-name`) using a dedicated ServiceAccount" |
| Overlay patches a Subscription channel | "operator channel pinned via kustomize overlay at `path`" |
| Script creates imperative resources | "created imperatively by `script-name.sh`; not GitOps-managed" |
| ConsoleLink patched from live route | "ConsoleLink URL patched at sync time from route via hook Job" |

Naming the mechanism helps troubleshooting: when a sync fails, the reader knows whether to look at a Job, an overlay, or a script.

### Quota, Sizing, and Rate Limit Rationale

When a numeric value has a reason, state it:

- "CPU quota `40` / `128Gi` — sized for model serving workloads"
- "Prometheus retention `15d` — covers benchmark iteration history"
- "MaaS subscription: 2M tokens/h — sized for burst development sessions"

When a value is a default with no special rationale, omit the explanation.

### Cross-Stage Dependencies

When a resource in this stage serves a downstream stage, document it:

- "`rhoai-maas` gateway provides governed API endpoints consumed by Stage 060
  developer workspaces and Stage 080 MTA"
- "`gpu-pool` Kueue ClusterQueue is shared by Stage 030 private model serving"

This prevents the downstream README from being the only place the dependency is documented.

### RBAC Topology

Document who can access what at the component level:

- "`rhods-admins` → admin on model serving namespace"
- "`rhoai-developers` → edit on registry namespace, viewer on Grafana"

Omit per-resource RoleBinding details unless they are non-obvious.

### Compatibility Guards

When an operator is pinned or held, explain why in the README:

- "GPU Operator held at `v24.9` — validated with RHOAI 3.3 for vLLM serving"
- "Kuadrant pinned to stable channel — required for gateway policy"

## What Does NOT Belong in a README

| Content type | Correct home |
|--------------|--------------|
| `oc apply` commands, script invocations | `docs/OPERATIONS.md` |
| Login steps, credential setup | `docs/OPERATIONS.md` |
| Error symptoms and recovery | `docs/TROUBLESHOOTING.md` |
| Validation check output | `docs/OPERATIONS.md` |
| Full manifest YAML excerpts | The manifest itself; cite path instead |
| Transient cluster state (pod names, timestamps) | Nowhere permanent |
| Deferred features with no implementation | `BACKLOG.md` |

## Review Checklist for Implementation Details

After writing or updating a stage README, verify:

- [ ] Every GitOps-managed operator states its channel and namespace
- [ ] Non-obvious deployment mechanisms are named (hook Jobs, overlay patches)
- [ ] Cross-stage resources document their downstream consumer
- [ ] Quota/sizing values with cross-stage rationale include the reasoning
- [ ] Compatibility guards explain the specific incompatibility they prevent
- [ ] RBAC grants are documented at the component level
- [ ] No operational procedures or shell commands appear in the README
- [ ] The architecture diagram accurately reflects all deployed components
