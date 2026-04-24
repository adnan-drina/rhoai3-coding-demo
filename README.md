# RHOAI3 Coding Demo — Private AI Code Assistant

**A private, governed AI code assistant built with Red Hat AI Factory and NVIDIA, delivered through Models-as-a-Service on OpenShift.**

This demo shows how organizations can deliver a private AI code assistant experience using Red Hat AI Factory with NVIDIA. It walks through how a developer discovers a centrally managed model, tests it, connects it to a coding workflow, and uses it from a familiar development environment. It also highlights how platform administrators can govern, rate limit, and observe model usage across teams — without relying on a public hosted AI service.

> Based on the public quickstart: [Accelerate enterprise software development with NVIDIA and MaaS](https://docs.redhat.com/en/learn/ai-quickstarts/rh-maas-code-assistant)

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

From the developer's perspective, the model is accessed through a simple API endpoint. Behind that endpoint, the platform provides a governed and scalable inference architecture using the Models-as-a-Service stack, including vLLM and llm-d. This separation allows developers to focus on building software while platform teams retain control over how AI services are deployed, exposed, secured, and monitored.

## Demo Storyline

### Developer Flow

The developer begins in the **OpenShift AI dashboard**, where they can access projects, deployed models, MCP servers, and other AI assets.

From the **GenAI Studio** section, the developer opens **AI Asset Endpoints** and selects the appropriate project (e.g., `quickstart-demo`). In the **Models-as-a-Service** tab, they can view the models that have already been deployed and managed by the platform team. In this demo, the available model is an **NVIDIA Nemotron** model.

Before connecting the model to a coding workflow, the developer tests it in the **Playground**. The Playground allows the developer to:

- Select the target model
- Adjust the system prompt
- Optionally enable MCP servers
- Send test prompts to validate the model response

For example, the developer asks the model to explain NVIDIA Nemotron models in one to three sentences. Once the model responds successfully, the developer retrieves the model connection details from the Models-as-a-Service endpoint page:

- **Model endpoint URL**
- **API token**

These values are then used to configure the local code assistant.

#### Connecting the Model to OpenShift Dev Spaces

The developer then moves into their development environment. In this demo, the organization uses **OpenShift Dev Spaces**, which provides containerized development environments running on OpenShift. Dev Spaces is deployed on the same cluster as OpenShift AI, giving developers a streamlined path from model discovery to application development.

Inside the Dev Spaces workspace, the demo repository is already cloned into a VS Code-compatible environment. The workspace includes **Continue**, an open-source AI code assistant extension. Because Continue can connect to a model endpoint supplied by the user, the developer configures it with the Models-as-a-Service endpoint URL and API token retrieved from OpenShift AI. Once configured, Continue uses the private NVIDIA Nemotron model as the backend for AI-assisted coding.

#### Code Assistant Example

The repository includes several sample game exercises (in `steps/step-04-devspaces/coding-exercises/`) that can be used to demonstrate AI-assisted development. In the demo, the developer selects code from one of the game files and asks the model to *"make the code enterprise grade."* The model suggests improvements directly in the development environment. The developer can review and accept the proposed changes — showing how a private AI model integrates into a familiar coding workflow without sending code to a public hosted service.

### Platform Administrator Flow

After demonstrating the developer workflow, the demo switches to the **platform administrator** perspective. One of the key benefits of Models-as-a-Service in Red Hat AI is that administrators can centrally control how shared models are exposed across users and teams.

Administrators can define and manage:

- Access policies and model availability by group
- Rate limits and quotas
- User tiers (free, premium, enterprise)
- Usage visibility by model and tier

For example, the demo shows a token rate limit policy managed through the API gateway layer. Different user tiers receive different token-per-minute limits:

| User Tier | Example Token Limit |
|-----------|---------------------|
| Free | 100 tokens per minute |
| Premium | 50,000 tokens per minute |
| Enterprise | 100,000 tokens per minute |

These tiers map to cluster user groups, giving administrators a practical way to align AI model access with organizational policy. Model access can also be restricted by tier — for example, the NVIDIA Nemotron model may only be exposed to premium and enterprise users.

#### Observability and Usage Visibility

The demo includes an observability view for the Models-as-a-Service administrator. In the example environment, **Grafana** is used to visualize metric data collected through the cluster observability stack. While Grafana itself is not part of the Red Hat AI product, it provides a useful example of how platform metrics can be visualized.

The dashboard shows token usage across deployed models and user tiers. Administrators can filter usage data by:

- User
- Model
- Metrics data source
- Time range

This visibility helps platform teams understand how shared AI services are being consumed, where demand is growing, and how to plan future infrastructure capacity. It can also support internal chargeback or cost visibility models.

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

## Key Takeaways

This demo shows how Red Hat AI Factory with NVIDIA can help organizations deliver private AI-assisted development at enterprise scale.

- **For developers:** A familiar AI code assistant experience inside OpenShift Dev Spaces, backed by a private NVIDIA model endpoint — no code leaves the organization's infrastructure.
- **For platform teams:** Centralized control over model access, user tiers, rate limits, quotas, and observability — the same governance patterns used for any shared platform service.
- **For the organization:** A practical pattern for delivering AI that is useful for developers, manageable for platform teams, and ready to scale across the enterprise.

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
