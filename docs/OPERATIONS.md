# Operations Guide

This document explains how to deploy, validate, and operate the workshop environment. The README files teach the architecture and product story; this guide is the operational companion for people running the demo.

The executable source of truth remains the scripts:

- `scripts/bootstrap.sh`
- `steps/step-XX-*/deploy.sh`
- `steps/step-XX-*/validate.sh`

Use this guide to understand when to run those scripts, what they do, and how to interpret the results.

## Operating Model

The repository follows a GitOps-first pattern:

1. `scripts/bootstrap.sh` installs and configures OpenShift GitOps.
2. Each `deploy.sh` applies one Argo CD `Application`.
3. Argo CD reconciles manifests from `gitops/step-XX-*/base`.
4. Sync waves and in-cluster Jobs perform cluster-specific setup.
5. Each `validate.sh` confirms that the step reached the expected operational state.

The deploy scripts do not imperatively install every component themselves. They hand ownership to Argo CD.

## Prerequisites

Before deploying the workshop, confirm:

- You are logged into the target OpenShift cluster with sufficient privileges.
- The cluster has enough capacity for GPU nodes and model-serving workloads.
- `oc`, `git`, `bash`, `curl`, and `jq` are available locally.
- You are using the intended branch and remote for the GitOps source.
- `env.example` has been copied to `.env` and configured with required credentials.
- `OPENAI_API_KEY` is set in `.env` if external model inference (gpt-4o, gpt-4o-mini) will be exercised.
- Optional: `SLACK_BOT_TOKEN` and/or `BRIGHTDATA_API_TOKEN` in `.env` if those MCP servers are needed.

Recommended checks:

```bash
oc whoami
oc whoami --show-server
git remote -v
git status --short
```

Optional MCP integrations have their own prerequisites. The base deployment includes the read-only OpenShift MCP server (uses ServiceAccount RBAC, no token needed). Slack and BrightData MCP components remain disabled unless their credential Secrets exist in `coding-assistant` and the Kustomize components are uncommented in `gitops/step-03-llm-serving-maas/base/kustomization.yaml`.

## Bootstrap

Run bootstrap once per cluster:

```bash
cp env.example .env
oc login --token=<token> --server=<api>
./scripts/bootstrap.sh
```

`bootstrap.sh` performs these actions:

- Auto-detects the Git remote and updates Argo CD Applications for forks.
- Installs the OpenShift GitOps operator.
- Grants the Argo CD application controller cluster-admin permissions for the demo.
- Sets Argo CD resource tracking to `annotation`.
- Configures custom health checks for resources such as PVCs and InferenceServices.
- Creates the `rhoai-demo` Argo CD project.

Monitor GitOps:

```bash
oc get pods -n openshift-gitops
oc get route openshift-gitops-server -n openshift-gitops
```

## Deployment Order

Deploy steps in order:

```bash
./steps/step-01-rhoai-platform/deploy.sh
./steps/step-02-gpu-infra/deploy.sh
./steps/step-03-llm-serving-maas/deploy.sh
./steps/step-04-devspaces/deploy.sh
./steps/step-05-mta/deploy.sh
./steps/step-06-developer-hub/deploy.sh
```

Each script applies one file from `gitops/argocd/app-of-apps/`.

| Step | Argo CD app | Purpose |
|------|-------------|---------|
| 01 | `step-01-rhoai-platform` | OpenShift AI platform foundation |
| 02 | `step-02-gpu-infra` | NFD, GPU Operator, GPU MachineSets |
| 03 | `step-03-llm-serving-maas` | MaaS, models, gateway, governance, observability |
| 04 | `step-04-devspaces` | Dev Spaces, workspaces, AI coding tools |
| 05 | `step-05-mta` | MTA, Developer Lightspeed, MaaS integration |
| 06 | `step-06-developer-hub` | Red Hat Developer Hub portal |

## Validation Strategy

Run the matching validation script after each step:

```bash
./steps/step-03-llm-serving-maas/validate.sh
```

Validation scripts use these exit codes:

| Exit code | Meaning |
|-----------|---------|
| `0` | All checks passed |
| `1` | One or more critical failures |
| `2` | Warnings only |

Warnings are acceptable only when the script clearly explains that the condition is temporary or expected. For a polished demo, aim for zero warnings.

Check all Argo CD apps:

```bash
oc get applications -n openshift-gitops \
  -o custom-columns='APP:.metadata.name,SYNC:.status.sync.status,HEALTH:.status.health.status'
```

## Argo CD Operations

Inspect an application:

```bash
oc get application step-03-llm-serving-maas -n openshift-gitops -o yaml
```

List resources managed by an application:

```bash
oc get application step-03-llm-serving-maas -n openshift-gitops -o json \
  | jq -r '.status.resources[]? | [.kind,.namespace,.name,.status,.health.status] | @tsv'
```

Force a sync from the CLI if needed:

```bash
argocd app sync step-03-llm-serving-maas
```

If the `argocd` CLI is unavailable, use the OpenShift GitOps UI or wait for automated sync. Most applications have automated sync enabled.

## Step-Specific Operational Notes

### Step 01

Step 01 installs OpenShift AI and platform dependencies. Operator reconciliation can take several minutes.

Useful checks:

```bash
oc get datasciencecluster default-dsc -o yaml
oc get pods -n redhat-ods-applications
oc get odhdashboardconfig odh-dashboard-config -n redhat-ods-applications -o yaml
```

### Step 02

Step 02 creates GPU infrastructure. New GPU nodes can take several minutes to provision and join the cluster.

Useful checks:

```bash
oc get machineset -n openshift-machine-api | grep -i gpu
oc get nodes -l node-role.kubernetes.io/gpu
oc get clusterpolicy -A
```

### Step 03

Step 03 is the most complex step. It deploys local models, external model registrations, MaaS governance, gateway policy, and observability.

**Credential provisioning:** `deploy.sh` reads `.env` and provisions secrets before applying the Argo CD Application:

| `.env` variable | Secret created | Namespace | Purpose |
|----------------|----------------|-----------|---------|
| `OPENAI_API_KEY` | `openai-api-key` | `maas` | Credential injection for external models (gpt-4o, gpt-4o-mini) |
| `SLACK_BOT_TOKEN` | `slack-mcp-credentials` | `coding-assistant` | Slack MCP server authentication |
| `BRIGHTDATA_API_TOKEN` | `brightdata-mcp-credentials` | `coding-assistant` | BrightData MCP server authentication |

The Argo CD Application has `ignoreDifferences` configured for these Secrets so `selfHeal` does not revert provisioned values to the GitOps placeholder.

If you need to update a credential after initial deployment:

```bash
oc create secret generic openai-api-key -n maas \
    --from-literal=api-key="sk-proj-YOUR-KEY" \
    --dry-run=client -o yaml | oc apply -f -
oc label secret openai-api-key -n maas inference.networking.k8s.io/bbr-managed=true --overwrite
```

Useful checks:

```bash
oc get llminferenceservice -n maas
oc get maasmodelref -n maas
oc get externalmodel -n maas
oc get maasauthpolicy,maassubscription -n models-as-a-service
oc get gateway maas-default-gateway -n openshift-ingress
oc get secret openai-api-key -n maas -o jsonpath='{.data.api-key}' | base64 -d | head -c10
```

### Step 04

Step 04 installs Dev Spaces and pre-provisions workspaces.

Useful checks:

```bash
oc get checluster devspaces -n openshift-devspaces
oc get devworkspace -A
oc get pods -n openshift-devspaces
```

### Step 05

Step 05 installs MTA and configures Developer Lightspeed to use MaaS.

Useful checks:

```bash
oc get tackle mta -n openshift-mta -o yaml
oc get deployment -n openshift-mta
oc get secret kai-api-keys -n openshift-mta -o jsonpath='{.data.OPENAI_API_BASE}' | base64 -d
```

### Step 06

Step 06 installs Red Hat Developer Hub and configures OIDC through MTA Keycloak.

Useful checks:

```bash
oc get backstage developer-hub -n rhdh -o yaml
oc get pods -n rhdh
oc get route -n rhdh
oc get consolelink rhdh -o yaml
```

## Updating The Demo

For GitOps-managed behavior:

1. Edit manifests under `gitops/`.
2. Commit and push changes to the branch referenced by the Argo CD Applications.
3. Let Argo CD reconcile or manually sync.
4. Run the matching `validate.sh`.

For documentation-only changes:

1. Edit `README.md`, `steps/*/README.md`, or files under `docs/`.
2. Run `git diff --check`.
3. Check that links and references still match the repo.

## Cleanup Guidance

The Argo CD Applications intentionally do not include finalizers. Deleting an Application by itself orphans the resources that it created.

For a full cleanup, prefer an explicit Argo CD cascade delete from the OpenShift GitOps UI or CLI:

```bash
argocd app delete step-06-developer-hub --cascade
argocd app delete step-05-mta --cascade
argocd app delete step-04-devspaces --cascade
argocd app delete step-03-llm-serving-maas --cascade
argocd app delete step-02-gpu-infra --cascade
argocd app delete step-01-rhoai-platform --cascade
```

Delete in reverse deployment order. Review GPU MachineSets and persistent volumes separately before removing them because cloud infrastructure and storage cleanup can be environment-specific.

If the `argocd` CLI is unavailable, use the OpenShift GitOps UI and choose cascade deletion. Avoid broad namespace deletion unless you have confirmed no shared cluster resources are still needed.

## When To Use Which Document

| Need | Use |
|------|-----|
| Understand the architecture and value | `README.md` and step READMEs |
| Deploy and validate the environment | This file |
| Diagnose failures | `docs/TROUBLESHOOTING.md` |
| See exact executable behavior | `deploy.sh` and `validate.sh` scripts |

## References

- [OpenShift GitOps documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_gitops/)
- [Red Hat OpenShift AI documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/)
- [OpenShift CLI documentation](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/cli_tools/openshift-cli-oc)
- [Argo CD documentation](https://argo-cd.readthedocs.io/)
