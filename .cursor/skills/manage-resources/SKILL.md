---
name: manage-resources
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  rhoai-version: "3.4"
  ocp-version: "4.20"
disable-model-invocation: true
description: >
  Scale models and GPU MachineSets up or down in the RHOAI demo environment.
  Use when the user wants to stop/start models, scale GPU nodes, save costs,
  manage cluster resources, reduce cloud spend overnight, or prepare for a
  demo by bringing resources back up. Also use when the user asks "how do I
  shut down the demo?" or "which models can I stop safely?".
  Do NOT use for deploying or re-deploying steps (use deploy.sh scripts),
  troubleshooting failures (use rhoai-troubleshoot), or manifest review
  (use manifest-reviewer agent).
---

# Manage Demo Resources

Scale InferenceServices (models) and MachineSets (GPU nodes) without
conflicting with ArgoCD. Steps that manage GPU nodes or model scaling
should use `selfHeal: false` so manual changes show OutOfSync but are
not auto-reverted.

## Prerequisites

- Logged in with `oc` (cluster-admin)
- ArgoCD Applications for scaling-managed steps have `selfHeal: false`

## Resource Inventory

Discover the current state before making changes:

```bash
# Models (if any deployed)
oc get isvc -A -o custom-columns='NAMESPACE:.metadata.namespace,NAME:.metadata.name,READY:.status.conditions[?(@.type=="Ready")].status,MIN_REPLICAS:.spec.predictor.minReplicas'

# GPU MachineSets
oc get machineset -n openshift-machine-api -o custom-columns='NAME:.metadata.name,DESIRED:.spec.replicas,READY:.status.readyReplicas'

# ArgoCD sync status (all apps)
oc get applications -n openshift-gitops -o custom-columns='APP:.metadata.name,SYNC:.status.sync.status,HEALTH:.status.health.status'
```

## Scale Down a Model

Set `minReplicas: 0` — KServe scales the predictor pod to zero after the
grace period (~60s). The ISVC resource remains; only the pod is removed.

```bash
oc patch isvc <MODEL_NAME> -n <NAMESPACE> --type merge \
  -p '{"spec":{"predictor":{"minReplicas":0}}}'
```

## Scale Down a GPU MachineSet

Scale the MachineSet to 0 replicas. The GPU node drains and terminates.
Pods on that node are evicted (models become unavailable).

```bash
# Scale down
oc scale machineset <MACHINESET_NAME> -n openshift-machine-api --replicas=0

# Monitor node drain
oc get nodes -l node-role.kubernetes.io/gpu --watch
```

**Dependency chain — scale down in this order:**

1. Stop models that use the GPU node first
2. Then scale down the MachineSet

## Scale Back Up

Reverse order — start the MachineSet first, wait for the node, then start models.

```bash
# 1. Scale up MachineSet
oc scale machineset <MACHINESET_NAME> -n openshift-machine-api --replicas=1

# 2. Wait for node ready (~5 min for GPU nodes)
oc get nodes -l node-role.kubernetes.io/gpu --watch

# 3. Restore model
oc patch isvc <MODEL_NAME> -n <NAMESPACE> --type merge \
  -p '{"spec":{"predictor":{"minReplicas":1}}}'
```

## Restore Full Git State

To bring everything back to the Git-declared state, sync via ArgoCD:

```bash
# Sync a specific app
oc patch application <STEP_NAME> -n openshift-gitops \
  --type merge -p '{"operation":{"sync":{}}}'
```

Or click **Sync** in the ArgoCD UI on the OutOfSync application.

## Verification

After any scaling operation, verify the state:

```bash
# Check ArgoCD shows expected status
oc get applications -n openshift-gitops \
  -o custom-columns='APP:.metadata.name,SYNC:.status.sync.status,HEALTH:.status.health.status'

# Check model readiness (if applicable)
oc get isvc -A

# Check node availability
oc get nodes -l node-role.kubernetes.io/gpu
```

## ArgoCD Behavior Reference

| Action | ArgoCD Status | Auto-heal? |
|--------|---------------|------------|
| Manual scale down model | OutOfSync | No (selfHeal=false on that step) |
| Manual scale down MachineSet | OutOfSync | No (selfHeal=false on that step) |
| Push Git change to the step | Auto-syncs | Yes (automated=true) |
| Click Sync in ArgoCD UI | Synced | Restores Git state |
