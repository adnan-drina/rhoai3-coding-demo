# Step 01: RHOAI Platform
**"The governed AI platform"** — Install Red Hat OpenShift AI 3.3 with platform dependencies, GenAI Studio, and a minimal DataScienceCluster on OCP 4.20.

## Overview

This step deploys the **Red Hat OpenShift AI 3.3** platform layer, including all operator dependencies required for the AI platform to function. After this step, the RHOAI Dashboard is accessible, GenAI Studio is enabled, and the platform is ready for GPU enablement and model serving.

> This configuration follows the [MaaS Code Assistant Quickstart](https://docs.redhat.com/en/learn/ai-quickstarts/rh-maas-code-assistant), using RHOAI 3.3 on the `stable-3.3` channel with a minimal DSC component set.

### What Gets Deployed

```text
RHOAI Platform
├── Platform Dependencies
│   ├── User Workload Monitoring  → Prometheus metrics for user projects
│   ├── cert-manager Operator     → TLS certificates for KServe, Llama Stack
│   ├── OpenShift Serverless      → KnativeServing for model serving
│   └── Service Mesh 3            → Auto-installed via DSCInitialization
├── RHOAI Operator                → stable-3.3 channel
├── DSCInitialization             → Monitoring, Service Mesh, CA bundle
├── DataScienceCluster            → Minimal component set (quickstart-aligned)
│   ├── kserve: Managed           → Model serving runtime
│   ├── llamastackoperator: Managed → Required for GenAI Playground
│   ├── dashboard: Managed        → RHOAI Dashboard
│   ├── workbenches: Managed      → Jupyter / VS Code workbenches
│   ├── modelmeshserving: Managed → ModelMesh
│   ├── modelregistry: Managed    → Model Registry
│   └── trustyai: Managed         → Model bias / explainability
├── Users & Authentication
│   ├── HTPasswd Secret           → ai-admin, ai-developer (demo-htpasswd)
│   ├── OAuth Configuration       → demo-htpasswd identity provider
│   └── RHOAI Groups              → rhoai-admins, rhoai-users
├── OdhDashboardConfig            → GenAI Studio, MaaS flags
├── Hardware Profiles             → CPU-small, L4-1GPU, L4-4GPU
├── Model Registry                → Enterprise model governance
│   ├── PostgreSQL 16             → Registry metadata database
│   ├── ModelRegistry CR          → demo-registry instance
│   ├── Internal Service          → Port 8080 for automation (bypasses OAuth)
│   └── RBAC                      → ai-admin (admin), ai-developer (user)
└── In-Cluster Jobs
    ├── approve-sm-installplan    → Auto-approve ServiceMesh install plan
    └── patch-dsci-ca             → Patch DSCI with CA bundle
```

Components **not** enabled (set to `Removed` or absent, matching quickstart):
- `aipipelines`, `ray`, `trainingoperator`, `feastoperator`, `mlflowoperator`, `nim`, `trainer`

Manifests: [`gitops/step-01-rhoai-platform/base/`](../../gitops/step-01-rhoai-platform/base/)

<details>
<summary>Deploy</summary>

```bash
./steps/step-01-rhoai-platform/deploy.sh
./steps/step-01-rhoai-platform/validate.sh
```

</details>

## References

- [Managing Model Registries](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.3/html/managing_model_registries)
- [RHOAI 3.3 Installation Guide](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.3/html-single/installing_and_uninstalling_openshift_ai_self-managed/index)
- [RHOAI 3.3 Release Notes](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.3/html/release_notes/index)
- [MaaS Code Assistant Quickstart](https://docs.redhat.com/en/learn/ai-quickstarts/rh-maas-code-assistant)
- [Red Hat OpenShift AI — Product Page](https://www.redhat.com/en/products/ai/openshift-ai)

## Next Steps

- **Step 02**: [GPU Infrastructure](../step-02-gpu-infra/README.md) — NFD, GPU Operator, and GPU MachineSets
