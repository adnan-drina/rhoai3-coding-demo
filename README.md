# RHOAI3 Coding Demo — Private AI Code Assistant

**A private, governed AI code assistant built with Red Hat AI Factory and NVIDIA, delivered through Models-as-a-Service on OpenShift.**

This demo showcases how Red Hat OpenShift AI and NVIDIA models combine to give developers AI-assisted coding inside familiar enterprise tools — while platform teams retain full control over access, quotas, and observability.

## Architecture

```text
┌───────────────────────────────────────────────────────────────────────┐
│                       Developer Experience                            │
│                                                                       │
│  OpenShift Dev Spaces ──→ Continue Extension ──→ AI Code Assistant    │
│       (VS Code)              (open source)        (private model)     │
├───────────────────────────────────────────────────────────────────────┤
│                    Models-as-a-Service (MaaS)                         │
│                                                                       │
│  RHOAI Dashboard           MaaS Gateway (HTTPS)      MaaS API        │
│  ├── GenAI Studio          ├── Authorino (AuthN)     ├── Model CRUD   │
│  ├── AI asset endpoints    ├── Kuadrant policies     ├── API tokens   │
│  └── Playground            └── TLS termination       └── PostgreSQL   │
│                                                                       │
│  Model Endpoints    Tier-Based Access    Rate Limits    Usage Metrics  │
│  (vLLM on GPU)      (free/premium/ent)   (RHCL)        (Prometheus)   │
├───────────────────────────────────────────────────────────────────────┤
│                   RHOAI 3.4 — AI/ML Platform                          │
│                                                                       │
│  GenAI Studio    Model Catalog    Hardware Profiles    KServe          │
│  Llama Stack     Model Registry   TrustyAI            AI Pipelines    │
├───────────────────────────────────────────────────────────────────────┤
│              Observability & Governance                                │
│                                                                       │
│  Grafana Dashboards    ServiceMonitor    User Workload Monitoring      │
│  (MaaS usage metrics)  (inference)       (Prometheus)                  │
├───────────────────────────────────────────────────────────────────────┤
│              OpenShift Container Platform 4.20                        │
│                                                                       │
│  NFD    NVIDIA GPU    Serverless    Service Mesh    Red Hat            │
│         Operator      (Knative)     (Istio)         Connectivity Link │
│                                                                       │
│  GitOps (ArgoCD)    Dev Spaces    cert-manager    Monitoring          │
├───────────────────────────────────────────────────────────────────────┤
│                     Infrastructure (AWS)                              │
│                                                                       │
│             2x NVIDIA L4 GPU nodes (g6e.2xlarge)                      │
└───────────────────────────────────────────────────────────────────────┘
```

## Demo Storyline

### Developer Perspective

The demo begins from the **developer's point of view** inside the OpenShift AI dashboard. The developer navigates to **GenAI Studio > AI asset endpoints** and selects the `maas` project. The page shows deployed models from multiple sources — Internal (LLMInferenceService) and MaaS (via the MaaS API) — each with status, endpoint, and playground access.

The developer clicks **View** on the NVIDIA Nemotron model to see its external API endpoint and generates an API token. They test the model in the built-in **Playground**, exploring prompts, system settings, and optional MCP server integrations.

Once validated, the developer switches to **OpenShift Dev Spaces** — the organization's containerized development environment. Inside a prepared VS Code workspace, they configure the **Continue** extension (an open-source AI coding assistant) to connect to the private model endpoint. The demo culminates with the developer sending source code to the model and asking it to make the code more "enterprise-grade."

### Platform Administrator Perspective

The demo then shifts to the **platform administrator's view**. Models-as-a-Service enables centralized model access management: admins define access policies, quotas, and token rate limits based on user tiers (free, premium, enterprise). These tiers map to cluster user groups, aligning AI access with organizational governance.

Using a **Grafana dashboard** connected to the cluster's observability stack, administrators monitor model usage across tiers, users, and deployed models — supporting capacity planning, cost tracking, and internal chargeback.

## What You Need

- OpenShift 4.20+ cluster on AWS
- 2x GPU nodes with 48GB VRAM each (e.g., `g6e.2xlarge` with NVIDIA L4)
- Cluster admin access
- `oc` CLI installed

## Quick Start

```bash
git clone https://github.com/adnan-drina/rhoai3-coding-demo.git && cd rhoai3-coding-demo
cp env.example .env              # Edit with your config
oc login --token=<token> --server=<api>
./scripts/bootstrap.sh           # Install ArgoCD + auto-detects fork URL
```

> **Using a fork?** `bootstrap.sh` auto-detects your git remote and updates all ArgoCD Applications. No manual `sed` needed.

Deploy steps in order:

```bash
# Step 01: RHOAI Platform (operator + dependencies + configuration)
./steps/step-01-rhoai-platform/deploy.sh

# Step 02: GPU Infrastructure (NFD + GPU Operator + MachineSets)
./steps/step-02-gpu-infra/deploy.sh

# Step 03: LLM Serving + MaaS + Observability (models + governance + dashboards)
./steps/step-03-llm-serving-maas/deploy.sh

# Step 04: Dev Spaces + AI Code Assistant
./steps/step-04-devspaces/deploy.sh
```

## Step Details

| Step | Name | Capability | Ref |
|------|------|-----------|-----|
| 01 | [RHOAI Platform](steps/step-01-rhoai-platform/README.md) | RHOAI Operator, DSC, Monitoring, Serverless, cert-manager, GenAI Studio, Hardware Profiles | [RHOAI 3.4 Installation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/installing_and_uninstalling_openshift_ai_self-managed/index) |
| 02 | [GPU Infrastructure](steps/step-02-gpu-infra/README.md) | NFD Operator, NVIDIA GPU Operator, ClusterPolicy, GPU MachineSets | [OCP Hardware Accelerators](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/hardware_accelerators/nvidia-gpu-architecture) |
| 03 | [LLM Serving + MaaS](steps/step-03-llm-serving-maas/README.md) | LWS, RHCL, Kuadrant, vLLM + NVIDIA Nemotron, MaaS tiers, rate limits, Grafana dashboards | [MaaS Code Assistant Quickstart](https://docs.redhat.com/en/learn/ai-quickstarts/rh-maas-code-assistant) |
| 04 | [Dev Spaces + Continue](steps/step-04-devspaces/README.md) | OpenShift Dev Spaces, VS Code, Continue extension, coding exercises | [Dev Spaces documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/) |

## GitOps Architecture

- **Per-step deployment** — each `deploy.sh` applies its own ArgoCD Application (`oc apply -f`), giving control over ordering and runtime setup (secrets, SCC grants, model uploads) between syncs.
- **`targetRevision: main`** — acceptable for a demo project where the single branch is the source of truth.
- **Fork-friendly** — `bootstrap.sh` auto-detects the git remote URL and updates all ArgoCD Applications. No manual URL changes needed for forks.

## Project Structure

```text
rhoai3-coding-demo/
├── scripts/                         # Bootstrap, shared shell libs, validation
│   ├── bootstrap.sh                 # Install GitOps operator + configure ArgoCD
│   ├── lib.sh                       # Shared logging, env, oc helpers
│   ├── validate-lib.sh              # Shared validation check functions
│   └── validate-demo-flow.sh
├── gitops/                             # Kubernetes manifests (Kustomize)
│   ├── argocd/app-of-apps/             # One ArgoCD Application per step
│   ├── step-01-rhoai-platform/base/    # RHOAI operator, monitoring, serverless, cert-mgr
│   ├── step-02-gpu-infra/base/         # NFD, GPU Operator, ClusterPolicy
│   ├── step-03-llm-serving-maas/base/  # LWS, RHCL, Gateway, models, governance
│   └── step-04-devspaces/base/          # Dev Spaces operator, workspaces
├── steps/                              # Per-step deploy/validate/README + app code
│   ├── step-01-rhoai-platform/
│   ├── step-02-gpu-infra/
│   ├── step-03-llm-serving-maas/
│   └── step-04-devspaces/
│       └── coding-exercises/        # Python games for "improve this code" demo
├── env.example                      # Template for .env
└── README.md
```

## Demo Credentials

| Username | Password | Identity Provider | Role | MaaS Tier |
|----------|----------|-------------------|------|-----------|
| `ai-admin` | `redhat123` | demo-htpasswd | RHOAI Admin (rhoai-admins group) | Enterprise |
| `ai-developer` | `redhat123` | demo-htpasswd | RHOAI User (rhoai-users group) | Premium |

> Credentials are defined in `gitops/step-01-rhoai-platform/base/users/htpasswd-secret.yaml`. MaaS tier group membership is defined in `gitops/step-03-llm-serving-maas/base/governance/maas-groups.yaml`.

## Troubleshooting

<details>
<summary>MaaS tab shows "Models as a Service could not be loaded" or models show as loading forever</summary>

The MaaS Gateway must have an **HTTPS listener with TLS termination** in addition to the HTTP listener. The RHOAI dashboard's `gen-ai-ui` and `maas-ui` containers call the MaaS API via `https://maas.<cluster-domain>/maas-api/`. Without TLS, these calls time out (504).

Verify the Gateway has both listeners:
```bash
oc get gateway maas-default-gateway -n openshift-ingress -o jsonpath='{.spec.listeners[*].name}'
# Expected: http https
```

If the `https` listener is missing, the `job-patch-gateway-hostname` Job in step-03 creates it automatically. Re-sync the ArgoCD Application or re-run `deploy.sh`.
</details>

<details>
<summary>Authorino returns TLS errors or MaaS API auth fails</summary>

Authorino needs `SSL_CERT_FILE` and `REQUESTS_CA_BUNDLE` env vars to trust OpenShift's internal service-ca certificates. The `job-configure-kuadrant` Job sets these automatically.

Verify:
```bash
oc get deployment authorino -n kuadrant-system -o jsonpath='{.spec.template.spec.containers[0].env[*].name}'
# Expected output should include: SSL_CERT_FILE REQUESTS_CA_BUNDLE
```
</details>

<details>
<summary>API key generation fails with "MaaS service is not available"</summary>

Two issues can cause this:

1. **Tier mapping**: The `tier-to-group-mapping` ConfigMap must include your actual user groups. The operator creates defaults (`system:authenticated`, `premium-users`, `enterprise-users`), but demo users are in `rhoai-admins`/`rhoai-users`. Patch the ConfigMap to add your groups, then restart `maas-api`:
```bash
# Verify tier lookup works for your groups
oc exec deploy/maas-api -n redhat-ods-applications -- \
  curl -sk https://localhost:8443/v1/tiers/lookup \
  -H "Content-Type: application/json" \
  -H "X-MaaS-Username: ai-admin" \
  -H 'X-MaaS-Group: ["rhoai-admins"]' \
  -d '{"groups": ["rhoai-admins"]}'
# Expected: {"tier":"enterprise","displayName":"Enterprise Tier"}
```

2. **Authorino `@tostr` expression (EA2)**: The operator-managed `AuthPolicy` uses `auth.identity.user.groups.@tostr` to set the `X-MaaS-Group` response header, but this expression doesn't produce output in the deployed Authorino version. The `maas-api` requires this header for write operations and returns 500 without it.

**Workaround** — Generate API keys via CLI from within the cluster:
```bash
oc exec deploy/rhods-dashboard -n redhat-ods-applications -c maas-ui -- \
  curl -sk -H "X-MaaS-Username: ai-admin" \
       -H 'X-MaaS-Group: ["rhoai-admins","rhoai-users"]' \
       -H "Content-Type: application/json" \
       -X POST -d '{"name":"my-key"}' \
       https://maas-api.redhat-ods-applications.svc:8443/v1/api-keys
```

The response contains the API key (starts with `sk-oai-`). Use this key in the `Authorization: Bearer sk-oai-...` header for MaaS API calls.
</details>

<details>
<summary>Model deployments show "Failed" in RHOAI dashboard but pods run fine</summary>

This typically means the HTTPRoute's `AuthPolicyAffected` condition is `False`. Ensure Red Hat Connectivity Link (RHCL) is installed and the `AuthPolicy` targeting `maas-api-route` is correctly configured. Check:
```bash
oc get httproute -n redhat-ods-applications -o wide
oc get authpolicy -n redhat-ods-applications -o yaml
```
</details>

## References

- [Red Hat OpenShift AI — Product Page](https://www.redhat.com/en/products/ai/openshift-ai)
- [Red Hat OpenShift AI — Datasheet](https://www.redhat.com/en/resources/red-hat-openshift-ai-hybrid-cloud-datasheet)
- [RHOAI 3.4 Documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/)
- [RHOAI 3.4 Release Notes](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/release_notes/index)
- [Experimenting with models in the GenAI Playground](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/experimenting_with_models_in_the_gen_ai_playground/)
- [MaaS Code Assistant Quickstart](https://docs.redhat.com/en/learn/ai-quickstarts/rh-maas-code-assistant)
- [Governing LLM access with Models-as-a-Service](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/govern_llm_access_with_models-as-a-service/index)
- [NVIDIA Nemotron Models](https://build.nvidia.com/nvidia/nemotron-3-nano-30b-a3b)
- [Continue — Open-Source AI Code Assistant](https://www.continue.dev/)
- [OpenShift Dev Spaces Documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/)
