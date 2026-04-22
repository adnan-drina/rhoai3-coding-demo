# Step 02: GPU Infrastructure and Prerequisites
**"GPU-accelerated foundation"** — Deploy the operator stack that RHOAI 3.4 and the MaaS code assistant demo depend on: GPU enablement, serverless serving, connectivity link for rate limiting, and cluster monitoring.

## Overview

Before models can be served or developers can use AI-assisted coding, the cluster needs GPU hardware, the operators that manage it, and the observability plumbing to track what happens. This step deploys the full operator prerequisite stack for RHOAI 3.4 on OCP 4.20, including NVIDIA GPU support, OpenShift Serverless for KServe, LeaderWorkerSet for distributed inference, and Red Hat Connectivity Link for MaaS rate limiting.

### What Gets Deployed

```text
GPU Infrastructure & Prerequisites
├── User Workload Monitoring     → Prometheus metrics for user projects
├── NFD Operator + Instance      → Hardware feature detection on nodes
├── GPU Operator + ClusterPolicy → NVIDIA driver, DCGM, device plugin
├── OpenShift Serverless         → KnativeServing for model serving
├── LeaderWorkerSet Operator     → Multi-node GPU workload orchestration
├── Red Hat Connectivity Link    → Gateway policies, rate limiting (MaaS)
└── GPU MachineSets (AWS)        → 2x g6e.2xlarge with NVIDIA L4
```

Manifests: [`gitops/step-02-gpu-and-prereq/base/`](../../gitops/step-02-gpu-and-prereq/base/)

<details>
<summary>Deploy</summary>

```bash
./steps/step-02-gpu-and-prereq/deploy.sh
./steps/step-02-gpu-and-prereq/validate.sh
```

</details>

<details>
<summary>What to Verify After Deployment</summary>

| Check | Command | Pass Criteria |
|-------|---------|---------------|
| NFD CRD | `oc get crd nodefeaturediscoveries.nfd.openshift.io` | CRD exists |
| GPU Operator | `oc get csv -n nvidia-gpu-operator` | Phase: Succeeded |
| Serverless | `oc get knativeserving -n knative-serving` | Ready: True |
| LWS | `oc get csv -n openshift-lws-operator` | Phase: Succeeded |
| RHCL | `oc get crd authpolicies.kuadrant.io` | CRD exists |
| GPU nodes | `oc get nodes -l node-role.kubernetes.io/gpu` | At least 2 nodes |

</details>

## References

- [RHOAI 3.4 Installation Guide](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/installing_and_uninstalling_openshift_ai_self-managed/index)
- [Installing distributed inference dependencies](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/installing_and_uninstalling_openshift_ai_self-managed/installing-the-distributed-workloads-components_install)
- [NVIDIA GPU Operator on OpenShift](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/openshift/contents.html)
- [Red Hat Connectivity Link](https://docs.redhat.com/en/documentation/red_hat_connectivity_link/)

## Next Steps

- **Step 03**: [LLM Serving with Models-as-a-Service](../step-03-llm-serving-maas/README.md) — Deploy NVIDIA Nemotron models with tier-based access and rate limiting
