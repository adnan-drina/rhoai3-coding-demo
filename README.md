# RHOAI3 Coding Demo — Private AI Code Assistant

**A private, governed AI code assistant built with Red Hat AI Factory and NVIDIA, delivered through Models-as-a-Service on OpenShift.**

This demo shows how organizations can deliver a private AI code assistant experience using Red Hat AI Factory with NVIDIA. It walks through how a developer discovers a centrally managed model, tests it, connects it to a coding workflow, and uses it from a familiar development environment. It also highlights how platform administrators can govern, rate limit, and observe model usage across teams — without relying on a public hosted AI service.

> Based on the public quickstart: [Accelerate enterprise software development with NVIDIA and MaaS](https://docs.redhat.com/en/learn/ai-quickstarts/rh-maas-code-assistant)

## Why It Matters

AI in the enterprise is not just about models. It is about delivering AI capabilities through a governed platform that gives teams:

- **Privacy** — AI-assisted coding without sending source code to external services
- **Governance** — centralized control over model access, rate limits, and usage visibility
- **Developer experience** — familiar tools (VS Code, Dev Spaces) backed by private model endpoints

**Target audience:** Solution Architects, Platform Engineers, and Developer Experience leads evaluating private AI code assistant patterns on Red Hat OpenShift AI.

## Key Takeaways

- **For developers:** A familiar AI code assistant experience inside OpenShift Dev Spaces, backed by a private NVIDIA model endpoint — no code leaves the organization's infrastructure.
- **For platform teams:** Centralized control over model access, user tiers, rate limits, quotas, and observability — the same governance patterns used for any shared platform service.
- **For the organization:** A practical pattern for delivering AI that is useful for developers, manageable for platform teams, and ready to scale across the enterprise.

## What This Demo Shows

This quickstart demonstrates a private AI code assistant powered by:

- [Red Hat OpenShift AI](https://www.redhat.com/en/products/ai/openshift-ai)
- [Models-as-a-Service](https://docs.redhat.com/en/learn/ai-quickstarts/rh-maas-code-assistant)
- [NVIDIA Nemotron models](https://build.nvidia.com/nvidia/nemotron-3-nano-30b-a3b)
- [OpenShift Dev Spaces](https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/)
- [Continue](https://www.continue.dev/), an open-source AI code assistant extension
- vLLM and llm-d for scalable model serving
- Optional observability dashboards using Grafana

The demo is shown from two perspectives:

1. **Developer experience** — A developer retrieves model connection details, tests the model, and connects it to a code assistant inside a Dev Spaces workspace.
2. **Platform administrator experience** — An administrator manages model access, rate limits, user tiers, and usage visibility across the environment.

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
│  MaaS API (operator)       MaaS Gateway (HTTPS)    Authorino (AuthN) │
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

From the developer's perspective, the model is accessed through a simple API endpoint. Behind that endpoint, the platform provides a governed and scalable inference architecture using the Models-as-a-Service stack, including vLLM and llm-d. This separation allows developers to focus on building software while platform teams retain control over how AI services are deployed, exposed, secured, and monitored.

## Demo Storyline

### Platform Foundation (Steps 01–02)

Before the demo begins, the platform team lays the foundation. [Step 01](steps/step-01-rhoai-platform/README.md) installs **Red Hat OpenShift AI 3.3** with all platform dependencies — OpenShift Serverless, Service Mesh, cert-manager, and user workload monitoring — and configures the RHOAI Dashboard with GenAI Studio, hardware profiles, and demo users. [Step 02](steps/step-02-gpu-infra/README.md) enables GPU compute by deploying the **NFD Operator** and **NVIDIA GPU Operator**, then provisions GPU worker nodes (2x NVIDIA L4) to run inference workloads. Together, these steps create a governed AI platform with GPU-accelerated compute — ready for model serving.

### Model Serving and Governance (Step 03)

[Step 03](steps/step-03-llm-serving-maas/README.md) deploys NVIDIA models on vLLM and exposes them through **Models-as-a-Service** with tier-based access control, rate limiting, and usage telemetry. A developer discovers a centrally managed NVIDIA Nemotron model in the **GenAI Studio** dashboard, tests it in the built-in **Playground**, and retrieves the model endpoint URL and API token. A platform administrator manages model access through tier-based policies (free, premium, enterprise) with per-tier rate limits enforced by **Red Hat Connectivity Link**, and monitors usage through **Grafana** dashboards — supporting capacity planning and internal chargeback.

- Full demo walkthrough: [Step 03 — The Demo](steps/step-03-llm-serving-maas/README.md#the-demo)

### AI Code Assistant (Step 04)

[Step 04](steps/step-04-devspaces/README.md) deploys **OpenShift Dev Spaces** and demonstrates the developer experience end-to-end. The developer configures the **Continue** extension (an open-source AI code assistant) with the MaaS model endpoint, then asks the model to improve sample code — showing a private AI coding workflow that never leaves the organization's infrastructure.

- Full demo walkthrough: [Step 04 — The Demo](steps/step-04-devspaces/README.md#the-demo)

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

## RHOAI 3.3 Features Covered

This demo covers 4 of the 11 features from the [Red Hat OpenShift AI datasheet](https://www.redhat.com/en/resources/red-hat-openshift-ai-hybrid-cloud-datasheet):

| RHOAI Feature | Benefit (from datasheet) | Demo Steps |
|---------------|--------------------------|------------|
| **Intelligent GPU and hardware speed** | Self-service GPU access with hardware profiles, workload scheduling, and visibility of use | Steps 01, 02, 03 |
| **Optimized model serving** | Serves models via vLLM, optimized for high throughput and low latency. llm-d supports scalable performance and efficient resource management | Step 03 |
| **Agentic AI and gen AI UIs** | GenAI Studio dashboard experience for model discovery, playground testing, and MCP server integration | Steps 01, 03 |
| **Models-as-a-Service** | Managed, built-in API gateway for self-service model access and usage tracking | Step 03 |

## OCP 4.20 Features Used

| OCP Feature | What It Provides | Demo Steps |
|-------------|------------------|------------|
| **Operator Lifecycle Manager (OLM)** | Manages operator install, update, and RBAC across clusters | Steps 01, 02, 03 |
| **Node Feature Discovery (NFD)** | Detects hardware features, labeling nodes for GPU workload scheduling | Step 02 |
| **NVIDIA GPU Operator** | Automates GPU driver, DCGM, and device plugin deployment on worker nodes | Step 02 |
| **OpenShift Serverless** | Serverless containers with dynamic scaling for KServe model endpoints | Step 01 |
| **Service Mesh 3** | Istio-based gateway, traffic management, and zero-trust networking for KServe | Step 01 |
| **Monitoring** | Prometheus-based metrics — platform metrics, user workload metrics, dashboards | Steps 01, 03 |
| **Authentication and Authorization** | Built-in OAuth with identity providers and RBAC for multi-tenant access control | Step 01 |
| **OpenShift GitOps (ArgoCD)** | Declarative GitOps delivery — Git as the single source of truth | All steps |
| **OpenShift Dev Spaces** | Containerized cloud-native IDEs running on the cluster | Step 04 |
| **Red Hat Connectivity Link** | API gateway policies — rate limiting, authentication, TLS termination | Step 03 |

## GitOps Architecture

- **Per-step deployment** — each `deploy.sh` applies its own ArgoCD Application (`oc apply -f`), giving control over ordering and runtime setup (secrets, SCC grants, model uploads) between syncs.
- **`targetRevision: main`** — acceptable for a demo project where the single branch is the source of truth.
- **Fork-friendly** — `bootstrap.sh` auto-detects the git remote URL and updates all ArgoCD Applications. No manual URL changes needed for forks.
- **Operator-native MaaS** — the RHOAI operator deploys `maas-api` in `redhat-ods-applications` via `modelsAsService: Managed` in the DSC. Governance policies and auth fixes are applied via GitOps and in-cluster Jobs. See [BACKLOG.md](BACKLOG.md) for workarounds that can be removed when RHOAI 3.4 GA ships.

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
| `ai-admin` | `<demo-password>` | demo-htpasswd | RHOAI Admin (rhoai-admins group) | Enterprise |
| `ai-developer` | `<demo-password>` | demo-htpasswd | RHOAI User (rhoai-users group) | Premium |

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
<summary>MaaS tab shows "No models available as a service"</summary>

The operator's `gateway-auth-policy` has a `tier-access` authorization step that extracts model names from URL paths. This breaks for the `/maas-api/v1/models` management endpoint. The `configure-kuadrant` Job patches both AuthPolicies to fix this. If the operator reconciles and overwrites the patches, re-run:
```bash
oc patch authpolicy gateway-auth-policy -n openshift-ingress --type=merge \
  -p '{"spec":{"rules":{"authentication":{"user-tokens":{"kubernetesTokenReview":{"audiences":["https://kubernetes.default.svc"]},"metrics":false,"priority":1,"defaults":{"userid":{"expression":"auth.identity.user.username"}}}}}}}'
oc patch authpolicy maas-api-auth-policy -n redhat-ods-applications \
  --type=merge -p '{"spec":{"rules":{"authorization":{}}}}'
```
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
- [rh-ai-quickstart/maas-code-assistant](https://github.com/rh-ai-quickstart/maas-code-assistant) — upstream quickstart source
