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
│  GitOps (ArgoCD)    Dev Spaces    Pipelines (Tekton)    Monitoring    │
├───────────────────────────────────────────────────────────────────────┤
│                     Infrastructure (AWS)                              │
│                                                                       │
│             2x NVIDIA L4 GPU nodes (g6e.2xlarge)                      │
└───────────────────────────────────────────────────────────────────────┘
```

## Demo Storyline

### Developer Perspective

The demo begins from the **developer's point of view** inside the OpenShift AI dashboard. The developer browses deployed AI assets — models and MCP servers — through the GenAI Studio. In the Models-as-a-Service area, they locate an available NVIDIA Nemotron model and test it in the built-in Playground, exploring prompts, system settings, and optional MCP server integrations.

Once validated, the developer copies the model endpoint URL, generates an API token, and switches to **OpenShift Dev Spaces** — the organization's containerized development environment. Inside a prepared VS Code workspace, they configure the **Continue** extension (an open-source AI coding assistant) to connect to the private model endpoint. The demo culminates with the developer sending source code to the model and asking it to make the code more "enterprise-grade."

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
# Step 01: RHOAI Platform
./steps/step-01-rhoai/deploy.sh

# Step 02: GPU Infrastructure & Prerequisites
./steps/step-02-gpu-and-prereq/deploy.sh

# Step 03: LLM Serving with Models-as-a-Service
./steps/step-03-llm-serving-maas/deploy.sh

# Step 04: Observability & Governance Dashboard
./steps/step-04-observability/deploy.sh

# Step 05: Dev Spaces & AI Code Assistant
./steps/step-05-devspaces/deploy.sh
```

## Step Details

| Step | Name | Capability | Ref |
|------|------|-----------|-----|
| 01 | [RHOAI Platform](steps/step-01-rhoai/README.md) | RHOAI Operator, DataScienceCluster, GenAI Studio, Hardware Profiles | [RHOAI 3.4 Installation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/installing_and_uninstalling_openshift_ai_self-managed/index) |
| 02 | [GPU & Prerequisites](steps/step-02-gpu-and-prereq/README.md) | NFD, GPU Operator, Serverless, LeaderWorkerSet, RHCL, Monitoring | [Installing dependencies](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/installing_and_uninstalling_openshift_ai_self-managed/installing-the-distributed-workloads-components_install) |
| 03 | [LLM Serving + MaaS](steps/step-03-llm-serving-maas/README.md) | vLLM on GPU, NVIDIA Nemotron, MaaS tiers, rate limits, telemetry | [MaaS Code Assistant Quickstart](https://docs.redhat.com/en/learn/ai-quickstarts/rh-maas-code-assistant) |
| 04 | [Observability](steps/step-04-observability/README.md) | Grafana, MaaS usage dashboards, ServiceMonitor, Prometheus | [Managing observability](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_openshift_ai/managing-observability_managing-rhoai) |
| 05 | [Dev Spaces + Continue](steps/step-05-devspaces/README.md) | OpenShift Dev Spaces, VS Code, Continue extension, coding exercises | [Dev Spaces documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/) |

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
├── gitops/                          # Kubernetes manifests (Kustomize)
│   ├── argocd/app-of-apps/          # One ArgoCD Application per step
│   ├── step-01-rhoai/base/          # RHOAI operator, DSC, hardware profiles
│   ├── step-02-gpu-and-prereq/base/ # NFD, GPU, Serverless, LWS, RHCL
│   ├── step-03-llm-serving-maas/base/ # Models, MaaS, tiers, rate limits
│   ├── step-04-observability/base/  # Grafana, dashboards, ServiceMonitor
│   └── step-05-devspaces/base/      # Dev Spaces operator, workspaces
├── steps/                           # Per-step deploy/validate/README + app code
│   ├── step-01-rhoai/
│   ├── step-02-gpu-and-prereq/
│   ├── step-03-llm-serving-maas/
│   ├── step-04-observability/
│   └── step-05-devspaces/
│       └── coding-exercises/        # Python games for "improve this code" demo
├── env.example                      # Template for .env
└── README.md
```

## Demo Credentials

| Username | Password | Role | MaaS Tier |
|----------|----------|------|-----------|
| `admin` | Set in `.env` | Platform Admin | Enterprise |
| `user1`-`user5` | Set in `.env` | Developer | Premium |

## References

- [Red Hat OpenShift AI — Product Page](https://www.redhat.com/en/products/ai/openshift-ai)
- [Red Hat OpenShift AI — Datasheet](https://www.redhat.com/en/resources/red-hat-openshift-ai-hybrid-cloud-datasheet)
- [RHOAI 3.4 Documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/)
- [RHOAI 3.4 Release Notes](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/release_notes/index)
- [MaaS Code Assistant Quickstart](https://docs.redhat.com/en/learn/ai-quickstarts/rh-maas-code-assistant)
- [NVIDIA Nemotron Models](https://build.nvidia.com/nvidia/nemotron-3-nano-30b-a3b)
- [Continue — Open-Source AI Code Assistant](https://www.continue.dev/)
- [OpenShift Dev Spaces Documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/)
- [Governing LLM access with Models-as-a-Service](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/govern_llm_access_with_models-as-a-service/index)
