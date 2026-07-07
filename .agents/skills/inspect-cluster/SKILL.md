---
name: inspect-cluster
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Demo Environment"
description: >
  Safely gather OpenShift cluster state for the RHOAI demo. Use when
  troubleshooting deployment failures, validating stage completion, or
  gathering diagnostic information. Must be used in readonly mode — no
  mutations. Do NOT use for remediation (use rhoai-troubleshoot), resource
  scaling (use manage-resources), or manifest review (use
  review-manifest-compliance or review-doc-alignment).
---

# Inspect Cluster

Gather diagnostic information from the cluster without modifying anything.
Summarize findings so the caller can decide on actions.

## When to invoke

- Troubleshooting a deployment failure
- Validating stage completion
- Gathering pre-change cluster state
- Diagnosing pod or operator issues

## Prerequisite

Verify `oc` login status before running any commands:

```bash
oc whoami --show-server
```

If not logged in, report that immediately instead of failing on every command.

## Standard inspection sequence

When asked to inspect a stage or component:

1. Check ArgoCD Application sync status:

```bash
oc get application <stage-app-name> -n openshift-gitops \
  -o jsonpath='{.status.sync.status}/{.status.health.status}'
```

2. Check pod status in the target namespace:

```bash
oc get pods -n <namespace> -l app.kubernetes.io/part-of=<component>
```

3. For failing pods, get events and recent logs:

```bash
oc describe pod <pod-name> -n <namespace> | tail -30
oc logs <pod-name> -n <namespace> --tail=50
```

4. For InferenceServices, check readiness:

```bash
oc get isvc -n <namespace>
```

5. For operators, check CSV status:

```bash
oc get csv -n <namespace> | grep -i <operator>
```

## Key namespaces

| Namespace | Components |
|-----------|-----------|
| redhat-ods-applications | RHOAI Dashboard, DSC, GenAI Studio |
| redhat-ods-operator | RHOAI Operator |
| openshift-gitops | ArgoCD |
| openshift-operators | Subscriptions (NFD, GPU, Service Mesh) |

Additional namespaces are created as stages are deployed. Check Argo CD
Applications for the target namespace of each stage.

## Output format

Return a structured summary:

```
Component: <name>
ArgoCD: <Synced/OutOfSync> / <Healthy/Degraded>
Pods: <X/Y ready>
Issues: <list of problems found, or "None">
Recommendation: <what to do next>
```

## Safety constraints

- Never run `oc delete`, `oc patch`, `oc scale`, or `oc apply`
- If a stage has a `validate.sh` script, suggest running it for comprehensive
  checks

## Related skills

- `rhoai-troubleshoot` — active troubleshooting and remediation
- `manage-resources` — scale or modify cluster resources
- `validate-demo-step` — structured stage validation
