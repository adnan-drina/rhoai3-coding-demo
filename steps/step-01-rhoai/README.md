# Step 01: Red Hat OpenShift AI 3.4 Platform
**"Governed AI platform layer"** — Install the full RHOAI 3.4 platform — GenAI Studio, Hardware Profiles, model serving, distributed training, and governance — on an OpenShift 4.20 cluster.

## Overview

Teams need one **consistent, self-service environment** instead of ad hoc stacks per project. This step deploys **Red Hat OpenShift AI 3.4** — the full AI platform layer that turns governed GPU capacity into a shared place to develop, serve, and observe models. Built on the **open-source** Open Data Hub project, RHOAI provides GenAI Studio for rapid prototyping, Hardware Profiles for GPU placement, and a DataScienceCluster that manages serving, training, pipelines, and governance in one surface.

This step demonstrates RHOAI's **model development and customization**, **optimized model serving**, **AI pipelines**, **model observability and governance**, and **agentic AI UIs** — all managed through a single DataScienceCluster.

### What Gets Deployed

```text
RHOAI 3.4 Platform
├── RHOAI Operator         → stable-3.x channel, manages all components
├── DSCInitialization      → Service Mesh 3 auto-installed
├── DataScienceCluster     → Full component stack (see table)
├── GenAI Studio           → Agent Playground + Model Catalog UI
└── Hardware Profiles      → GPU/CPU profiles with GPU node scheduling
```

| Component | State | Purpose |
|-----------|-------|---------|
| Dashboard | Managed | RHOAI web console |
| Workbenches | Managed | Jupyter notebooks, VS Code, RStudio |
| AI Pipelines | Managed | ML Pipelines (formerly `datasciencepipelines`) |
| LlamaStack Operator | Managed | GenAI Playground, agentic workflows |
| GenAI Studio | Enabled | Agent Playground + Model Catalog UI |
| KServe | Managed | Model serving (RawDeployment mode) |
| Model Registry | Managed | Model versioning and catalog |
| Training Operator | Managed | Kubernetes-native distributed training |
| Ray | Managed | Distributed computing framework |
| TrustyAI | Managed | Explainability, bias detection, drift monitoring |
| Feast Operator | Managed | Feature store for ML features |

**Hardware Profiles** (global, in `redhat-ods-applications`):

| Profile | Display Name | Scheduling |
|---------|-------------|------------|
| cpu-small | Small (CPU Only) | Node (direct) |
| default-profile | NVIDIA L4 1GPU (Default) | Node (direct) |
| nvidia-l4-1gpu | NVIDIA L4 1GPU | Node (direct) |
| nvidia-l4-4gpu | NVIDIA L4 4GPUs | Node (direct) |

Manifests: [`gitops/step-01-rhoai/base/`](../../gitops/step-01-rhoai/base/)

<details>
<summary>RHOAI and OCP Features in This Step</summary>

| | Feature | Status |
|---|---|---|
| RHOAI | Agentic AI and gen AI UIs (GenAI Studio) | Introduced |
| RHOAI | Intelligent GPU and hardware speed (Hardware Profiles) | Introduced |
| OCP | Service Mesh 3 (Istio) | Introduced |

</details>

<details>
<summary>Design Decisions</summary>

> **GPU scheduling via Hardware Profiles:** All GPU Hardware Profiles use direct `nodeSelector` and `tolerations` for GPU node placement. No workload queuing is used.

> **GenAI Studio enabled by default:** `genAiStudio: true` in `OdhDashboardConfig` plus `llamastackoperator: Managed` in the DSC activate the Agent Playground and Model Catalog for all users. The RHOAI operator may reset this field during reconciliation, so `deploy.sh` patches it explicitly after DSC is Ready.

> **DSCI CA bundle (runtime patch):** `deploy.sh` patches `DSCInitialization` with the cluster CA certificate (`kube-root-ca.crt`) so LlamaStack distributions can reach internal services over TLS. This is a runtime patch because the CA cert is cluster-specific and should not be committed to git. Ref: [Working with certificates](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/installing_and_uninstalling_openshift_ai_self-managed/working-with-certificates_certs).

> **Service Mesh 3 install plan approval (Manual, enforced by operator):** The RHOAI operator auto-creates the `servicemeshoperator3` Subscription with `installPlanApproval: Manual` and reconciles it back to `Manual` if patched to `Automatic`. `deploy.sh` must explicitly approve pending Service Mesh install plans. Without this step, the Gateway controller never starts and the RHOAI Dashboard becomes unreachable.

</details>

<details>
<summary>Deploy</summary>

```bash
./steps/step-01-rhoai/deploy.sh     # ArgoCD app: RHOAI operator + DSC + Hardware Profiles
./steps/step-01-rhoai/validate.sh   # Verify Dashboard, GenAI Studio, DSC health
```

</details>

<details>
<summary>What to Verify After Deployment</summary>

| Check | What It Tests | Pass Criteria |
|-------|--------------|---------------|
| Dashboard URL | RHOAI console accessible | `https://data-science-gateway.apps.<cluster>` responds |
| GenAI Studio visible | Agent Playground and Model Catalog in left nav | Both menu items present |
| Hardware Profiles | Four profiles listed in Settings | CPU Small, L4 1GPU, L4 1GPU Default, L4 4GPU |
| DataScienceCluster Ready | `default-dsc` phase | Ready with all components managed |
| Service Mesh 3 | Auto-installed by DSCInitialization | KServe traffic management operational |

</details>

## The Demo

> In this demo, we tour the RHOAI 3.4 platform — the self-service AI environment that data scientists and ML engineers will use for every subsequent step. We see the Dashboard, Hardware Profiles that control GPU scheduling, and the Model Catalog with validated models ready to deploy.

### RHOAI Dashboard

> The starting point for every AI practitioner on the platform. The RHOAI Dashboard provides a unified console for managing models, pipelines, notebooks, and monitoring — without direct infrastructure access.

1. Open `https://data-science-gateway.apps.<cluster>` and log in as `ai-admin` / `redhat123`
2. Explore the left navigation — GenAI Studio, Data Science Projects, Model Serving

**Expect:** The RHOAI Dashboard with GenAI Studio in the left navigation — Agent Playground, Model Catalog, AI Available Assets.

> This is the self-service AI platform. Data scientists get a curated environment — models, pipelines, notebooks, and monitoring — without managing infrastructure. Red Hat OpenShift AI provides this out of the box on any OpenShift cluster.

### Hardware Profiles

> Hardware Profiles replace the old Accelerator Profiles from RHOAI 2.x. They define exactly which node type a workload lands on — the platform admin creates these once, and every user selects from the same curated list.

1. Navigate to **Settings** -> **Hardware profiles**

**Expect:** Four profiles — CPU Small, NVIDIA L4 1GPU, NVIDIA L4 1GPU (Default), NVIDIA L4 4GPUs. Each shows nodeSelector and tolerations targeting the correct GPU node type.

> Intelligent GPU and hardware acceleration — self-service GPU access with workload scheduling that ensures the right workload lands on the right hardware. No guessing, no overprovisioning, no resource conflicts between teams.

### Model Catalog

> Red Hat OpenShift AI ships with a curated library of validated models — tested against the platform, available immediately with no external dependencies.

1. Navigate to **GenAI Studio** -> **Model Catalog**

**Expect:** Red Hat Validated models from IBM, Meta, Mistral, Qwen, and others. Each card shows parameter count, license, and recommended hardware.

> Models in OCI ModelCar format — Red Hat-tested and ready to deploy directly from the catalog using the cluster's pull secret. No HuggingFace account needed, no external model downloads, no supply chain concerns.

## Key Takeaways

**For business stakeholders:**

- Turn governed GPU capacity into a shared AI platform for teams
- Give data scientists, developers, and platform teams one consistent workspace
- Build on open source with a supported Red Hat AI platform

**For technical teams:**

- Install the core OpenShift AI stack through one managed platform layer
- Use hardware profiles to match workloads to the right compute
- Centralize serving, development, and governance in one DataScienceCluster

<details>
<summary>Troubleshooting</summary>

### Dashboard "Application is not available" — Gateway stuck at "Waiting for controller"

**Symptom:** Browsing to `https://data-science-gateway.apps.<cluster>` shows the OpenShift "Application is not available" page.

**Root Cause:** The Service Mesh 3 operator CSV is stuck in `Pending` (e.g. due to a failed upgrade where the ServiceAccount was never created). Without the operator, istiod never starts, the `data-science-gateway` GatewayClass has no controller, and the Gateway cannot be programmed.

**Diagnosis:**
```bash
oc get gateway data-science-gateway -n openshift-ingress
# PROGRAMMED column shows "Unknown"

oc get csv -n openshift-operators | grep servicemesh
# Phase shows "Pending" instead of "Succeeded"

oc get pods -n openshift-operators | grep mesh
# No operator pod running
```

**Solution:**
```bash
# 1. Delete the stuck CSV (replace version as needed)
oc delete csv servicemeshoperator3.v3.1.0 -n openshift-operators

# 2. Find and approve the pending install plan for the next version
oc get installplan -n openshift-operators | grep servicemesh
oc patch installplan <plan-name> -n openshift-operators --type merge -p '{"spec":{"approved":true}}'

# 3. Wait for the CSV to reach Succeeded (~1-2 minutes)
oc get csv -n openshift-operators -w | grep servicemesh

# 4. Verify the gateway becomes Programmed
oc get gateway data-science-gateway -n openshift-ingress
# PROGRAMMED should show "True"

# 5. Verify dashboard responds (302 = redirect to login)
curl -sk -o /dev/null -w '%{http_code}' https://data-science-gateway.apps.<cluster>
```

> **Note:** The DSCI auto-installs Service Mesh 3 with `installPlanApproval: Manual`. On shared demo clusters where the operator catalog updates, pending upgrades require manual approval.

</details>

## References

- [RHOAI 3.4 Release Notes](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/release_notes/index)
- [RHOAI 3.4 Installation Guide](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/installing_and_uninstalling_openshift_ai_self-managed/index)
- [Configuring Hardware Profiles](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_with_accelerators/index#working-with-hardware-profiles)
- [Red Hat OpenShift AI — Product Page](https://www.redhat.com/en/products/ai/openshift-ai)
- [Red Hat OpenShift AI — Datasheet](https://www.redhat.com/en/resources/red-hat-openshift-ai-hybrid-cloud-datasheet)

## Next Steps

- **Step 02**: [GPU Infrastructure & Prerequisites](../step-02-gpu-and-prereq/README.md) — NFD, GPU Operator, Serverless, LeaderWorkerSet, Red Hat Connectivity Link
