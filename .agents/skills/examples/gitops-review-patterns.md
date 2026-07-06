# GitOps Review Patterns

These examples are review patterns, not copy-paste manifests. The OCP GitOps
overview does not provide detailed Argo CD or OpenShift GitOps Operator schema.
Verify the separate Red Hat OpenShift GitOps docs and active cluster CRDs
before committing resources.

## Source Boundary Review

Use this decision flow:

| Task | Skill |
|------|-------|
| Explain what OpenShift GitOps is in OCP terms | `ocp-gitops-operator` |
| Install or configure the OpenShift GitOps Operator | `ocp-gitops-operator` plus separate Red Hat OpenShift GitOps docs |
| Author `gitops/**`, Kustomize, Argo CD Applications, sync waves, or app-of-apps | `project-gitops-authoring` |
| Review manifest correctness and security posture | `project-manifest-review` |
| Deploy or troubleshoot against a live cluster | relevant `env-*` skill plus the OpenShift safety guard |

## Read-Only Discovery Pattern

After the OpenShift safety guard confirms the target cluster:

```bash
oc get subscription -A | grep -i gitops
oc get csv -A | grep -i gitops
oc api-resources | grep -Ei 'argo|gitops'
oc get crd | grep -Ei 'argo|gitops'
```

Review points:

- Discover the installed Operator and exposed APIs before authoring manifests.
- Do not assume a Red Hat OpenShift GitOps minor version from the OCP version.
- Do not assume upstream Argo CD defaults are Red Hat product defaults.

## Demo Application Policy Handoff

Project-specific Argo CD Application authoring belongs in
`project-gitops-authoring`, including:

- `project: rhoai-demo`
- `targetRevision` policy
- sync waves
- app-of-apps layout
- Kustomize source paths
- `manifest-generate-paths`
- project labels and annotations
- PVC ignore-differences rules
- `resourceTrackingMethod: annotation`

Use this OCP skill to verify the platform and product boundary, then use the
project skill for repo implementation details.

## Live Operation Risk Pattern

Treat these as platform-sensitive operations:

- installing or uninstalling the OpenShift GitOps Operator
- creating or modifying the Argo CD instance
- changing repository or cluster credentials
- changing SSO, TLS, notifications, RBAC, or cluster roles
- changing resource tracking behavior
- deleting Argo CD Applications or AppProjects

Require explicit approval and use the environment guard before running live
commands.
