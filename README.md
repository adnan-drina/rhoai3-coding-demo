# RHOAI3 Coding Demo — Private AI Code Assistant

**A private, governed AI code assistant built with Red Hat AI Factory and NVIDIA, delivered through Models-as-a-Service on OpenShift.**

This demo showcases how Red Hat OpenShift AI and NVIDIA models combine to give developers AI-assisted coding inside familiar enterprise tools — while platform teams retain full control over access, quotas, and observability.

> Based on the public quickstart: [Accelerate enterprise software development with NVIDIA and MaaS](https://docs.redhat.com/en/learn/ai-quickstarts/rh-maas-code-assistant)

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
│  MaaS API (dev-preview)    MaaS Gateway (HTTPS)    Authorino (AuthN) │
│  ├── Model discovery       ├── Kuadrant policies   ├── Token review  │
│  ├── API token generation  ├── TLS termination     └── Tier mapping  │
│  └── Tier-based access     └── Rate limiting                         │
│                                                                       │
│  Model Endpoints    Tier-Based Access    Rate Limits    Usage Metrics  │
│  (vLLM on GPU)      (free/premium/ent)   (RHCL)        (Prometheus)   │
├───────────────────────────────────────────────────────────────────────┤
│                   RHOAI 3.3 — AI/ML Platform                          │
│                                                                       │
│  GenAI Studio    Hardware Profiles    KServe    Model Registry         │
│  Llama Stack     TrustyAI            Workbenches                      │
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

The demo begins from the **developer's point of view** inside the OpenShift AI dashboard. The developer navigates to **GenAI Studio > AI asset endpoints** and selects the `maas` project. Models deployed through the MaaS dev-preview API appear with MaaS source badges, endpoints, and playground access.

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
| 01 | [RHOAI Platform](steps/step-01-rhoai-platform/README.md) | RHOAI 3.3 Operator, DSC, Monitoring, Serverless, cert-manager, GenAI Studio, Hardware Profiles | [RHOAI 3.3 Installation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.3/html-single/installing_and_uninstalling_openshift_ai_self-managed/index) |
| 02 | [GPU Infrastructure](steps/step-02-gpu-infra/README.md) | NFD Operator, NVIDIA GPU Operator, ClusterPolicy, GPU MachineSets | [OCP Hardware Accelerators](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/hardware_accelerators/nvidia-gpu-architecture) |
| 03 | [LLM Serving + MaaS](steps/step-03-llm-serving-maas/README.md) | LWS, RHCL, Kuadrant, vLLM + NVIDIA Nemotron, MaaS tiers, rate limits, Grafana dashboards | [MaaS Code Assistant Quickstart](https://docs.redhat.com/en/learn/ai-quickstarts/rh-maas-code-assistant) |
| 04 | [Dev Spaces + Continue](steps/step-04-devspaces/README.md) | OpenShift Dev Spaces, VS Code, Continue extension, coding exercises | [Dev Spaces documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/) |

## GitOps Architecture

- **Per-step deployment** — each `deploy.sh` applies its own ArgoCD Application (`oc apply -f`), giving control over ordering and runtime setup (secrets, SCC grants, model uploads) between syncs.
- **`targetRevision: main`** — acceptable for a demo project where the single branch is the source of truth.
- **Fork-friendly** — `bootstrap.sh` auto-detects the git remote URL and updates all ArgoCD Applications. No manual URL changes needed for forks.
- **Dev-preview MaaS API** — deployed separately via `oc apply -k` in `deploy.sh` because RHOAI 3.3 does not include MaaS natively. See [BACKLOG.md](BACKLOG.md) for revert instructions when RHOAI 3.4 GA ships.

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
│   │   └── maas-api/                   # Dev-preview MaaS API (remote kustomize base)
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
<summary>MaaS Gateway not reachable (504 timeout or connection refused)</summary>

The MaaS Gateway must have an **HTTPS listener with TLS termination**. The `job-patch-gateway-hostname` Job in step-03 creates both HTTP and HTTPS listeners and patches the cluster-specific hostname.

Verify:
```bash
oc get gateway maas-default-gateway -n openshift-ingress -o jsonpath='{.spec.listeners[*].name}'
# Expected: http https
```
</details>

<details>
<summary>Authorino returns TLS errors or MaaS API auth fails</summary>

Authorino needs `SSL_CERT_FILE` and `REQUESTS_CA_BUNDLE` env vars. The `job-configure-kuadrant` Job sets these automatically.

Verify:
```bash
oc get deployment authorino -n kuadrant-system -o jsonpath='{.spec.template.spec.containers[0].env[*].name}'
# Expected output should include: SSL_CERT_FILE REQUESTS_CA_BUNDLE
```
</details>

<details>
<summary>Dev-preview maas-api pod not starting</summary>

The dev-preview `maas-api` runs in the `maas-api` namespace. Check pod status and logs:
```bash
oc get pods -n maas-api
oc logs deployment/maas-api -n maas-api
```

Common issues:
- RBAC: the `maas-api` ServiceAccount needs cluster-wide access to `LLMInferenceService`, `HTTPRoute`, `Namespace`, `ServiceAccount`, and `ConfigMap` resources.
- The remote kustomize base deploys its own Gateway — ours in step-03 takes precedence. Check that only one `maas-api-route` HTTPRoute exists.
</details>

<details>
<summary>Dashboard config (genAiStudio/modelAsService) not taking effect</summary>

The RHOAI 3.3 operator may overwrite `OdhDashboardConfig`. Re-apply after the operator reconciles:
```bash
oc apply -f gitops/step-01-rhoai-platform/base/rhoai-operator/dashboard-config.yaml --force
oc delete pods -l app=rhods-dashboard -n redhat-ods-applications
oc rollout status deploy/rhods-dashboard -n redhat-ods-applications
```
</details>

## References

- [MaaS Code Assistant Quickstart](https://docs.redhat.com/en/learn/ai-quickstarts/rh-maas-code-assistant) — the public quickstart this demo is based on
- [Red Hat OpenShift AI — Product Page](https://www.redhat.com/en/products/ai/openshift-ai)
- [RHOAI 3.3 Documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.3/)
- [RHOAI 3.3 Release Notes](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.3/html/release_notes/index)
- [NVIDIA Nemotron Models](https://build.nvidia.com/nvidia/nemotron-3-nano-30b-a3b)
- [Continue — Open-Source AI Code Assistant](https://www.continue.dev/)
- [OpenShift Dev Spaces Documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/)
- [opendatahub-io/models-as-a-service](https://github.com/opendatahub-io/models-as-a-service) — MaaS API dev-preview source
