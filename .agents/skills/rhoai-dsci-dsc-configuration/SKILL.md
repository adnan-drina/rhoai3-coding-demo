---
name: rhoai-dsci-dsc-configuration
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use when documenting, reviewing, or rebuilding Red Hat OpenShift AI
  DSCInitialization and DataScienceCluster configuration: predefined and custom
  namespaces, DataScienceCluster component managementState values,
  workbenchNamespace, model registry namespace, Kueue defaults, DSCI monitoring
  handoff, installed component status, schema verification, GitOps CR
  authoring, and progressive demo-step component enablement by patching the
  platform-owned DataScienceCluster. Do NOT use for Operator Subscription
  channel policy (use rhoai-update-channels), initial install flow (use
  rhoai-self-managed-installation), component-specific tuning (use the
  relevant rhoai-* skill), or live cluster troubleshooting (use
  env-troubleshoot).
---

# RHOAI DSCI And DSC Configuration

Use this skill for the OpenShift AI control-plane custom resources that define
component installation and shared platform configuration.

## Source Grounding

1. Read `docs/PLATFORM_BASELINE.md`.
2. Read `.agents/rules/rhoai.md`.
3. Use `references/source-capture.md` for official source provenance.
4. Use `references/official-doc-extraction.md` for supported behavior.
5. Use `references/validation-checklist.md` before finalizing CR content.

## Scope

- `DataScienceCluster` component lifecycle and `managementState`.
- `DSCInitialization` shared platform configuration such as monitoring.
- Predefined and custom namespace handling.
- Validation of component readiness through `status.installedComponents`.
- GitOps review of CRs derived from official CLI or console guidance.

## Demo Policy

- Use predefined namespaces by default:
  - `redhat-ods-operator`
  - `redhat-ods-applications`
  - `rhods-notebooks`
- Use custom namespaces only when the reimplementation records a clear reason.
- Set each component explicitly to `Managed` or `Removed`; do not leave
  component intent implicit in demo GitOps.
- Follow the CoP-inspired progressive DSC pattern:
  - the first RHOAI platform step owns the base `DSCInitialization` and
    `DataScienceCluster`
  - later steps introduce new RHOAI capabilities through Kustomize Components
    or patches that update the same platform overlay
  - only one Argo CD Application should own the rendered DSC/DSCI objects
- Do not invent CR fields. Verify uncertain fields with official docs and
  `oc explain`.
- Apply active CRs through ArgoCD once the GitOps skeleton exists; direct
  `oc apply` is for investigation or manual validation only.

## Workflow

1. Identify whether the change belongs in `DataScienceCluster` or
   `DSCInitialization`.
2. Confirm the active baseline and component-specific prerequisite skill.
3. If a demo step enables a new RHOAI component, add a focused patch to the
   platform-owned DSC overlay instead of introducing a competing full DSC in
   the step Application.
4. Check official examples for field placement.
5. Verify fields through schema inspection when possible:

   ```bash
   oc explain datasciencecluster.spec
   oc explain dscinitialization.spec
   ```

6. Validate readiness with readonly commands after the OpenShift safety guard
   passes.

## Related Skills

- `rhoai-self-managed-installation` for overall install flow.
- `rhoai-update-channels` for Operator Subscription channel policy.
- `rhoai-observability` for DSCI monitoring stack details.
- `rhoai-api-tiers` for API support posture.
- `project-red-hat-operator-gitops` for the CoP-inspired GitOps layout and
  progressive DSC patching model.
- Component-specific `rhoai-*` skills for each managed component.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/dsci-dsc-review-pattern.md`
