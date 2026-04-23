# Step 01: RHOAI Platform
**"The governed AI platform"** — Install Red Hat OpenShift AI 3.4 with all platform dependencies, GenAI Studio, Hardware Profiles, and the full DataScienceCluster component stack on OCP 4.20.

## Overview

This step deploys the complete **Red Hat OpenShift AI 3.4** platform layer, including all operator dependencies required for the AI platform to function. After this step, the RHOAI Dashboard is accessible, GenAI Studio is enabled, and the platform is ready for GPU enablement and model serving.

### What Gets Deployed

```text
RHOAI Platform
├── Platform Dependencies
│   ├── User Workload Monitoring  → Prometheus metrics for user projects
│   ├── cert-manager Operator     → TLS certificates for KServe, Llama Stack
│   ├── OpenShift Serverless      → KnativeServing for model serving
│   └── Service Mesh 3            → Auto-installed via DSCInitialization
├── RHOAI Operator                → stable-3.x channel
├── DSCInitialization             → Monitoring, Service Mesh, CA bundle
├── DataScienceCluster            → Full 3.4 component stack
│   ├── modelsAsService: Managed  → MaaS API + governance
│   └── llamastackoperator: Managed → Required for GenAI Playground
├── Users & Authentication
│   ├── HTPasswd Secret           → ai-admin, ai-developer (demo-htpasswd)
│   ├── OAuth Configuration       → demo-htpasswd identity provider
│   └── RHOAI Groups              → rhoai-admins, rhoai-users
├── OdhDashboardConfig            → GenAI Studio, MaaS, MLflow, Observability
├── Hardware Profiles             → CPU-small, L4-1GPU, L4-4GPU
└── In-Cluster Jobs
    ├── approve-sm-installplan    → Auto-approve ServiceMesh install plan
    └── patch-dsci-ca             → Patch DSCI with CA bundle
```

Manifests: [`gitops/step-01-rhoai-platform/base/`](../../gitops/step-01-rhoai-platform/base/)

<details>
<summary>Deploy</summary>

```bash
./steps/step-01-rhoai-platform/deploy.sh
./steps/step-01-rhoai-platform/validate.sh
```

</details>

## References

- [RHOAI 3.4 Installation Guide](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/installing_and_uninstalling_openshift_ai_self-managed/index)
- [RHOAI 3.4 Release Notes](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/release_notes/index)
- [Playground Prerequisites (Llama Stack, MCP)](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/experimenting_with_models_in_the_gen_ai_playground/playground-prerequisites_rhoai-user)
- [Red Hat OpenShift AI — Product Page](https://www.redhat.com/en/products/ai/openshift-ai)

## Next Steps

- **Step 02**: [GPU Infrastructure](../step-02-gpu-infra/README.md) — NFD, GPU Operator, and GPU MachineSets
