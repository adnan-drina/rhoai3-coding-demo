---
name: rhoai-installation-troubleshooting
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use when documenting, reviewing, or diagnosing Red Hat OpenShift AI
  installation problems from the official troubleshooting chapter: Operator
  image pull failures, unsupported infrastructure, failed OpenShift AI or
  Notebooks custom resource creation, inaccessible dashboard after install,
  reinstall failure caused by a leftover Auth custom resource, dedicated-admins
  RBAC creation failure, missing ODH parameter secret, must-gather evidence,
  and support escalation boundaries. Pair with env-troubleshoot for live
  cluster diagnosis. Do NOT use for day-2 workload failures, model serving
  runtime errors, pipeline run failures, notebook user issues, or non-install
  OpenShift troubleshooting.
---

# RHOAI Installation Troubleshooting

Use this skill to diagnose OpenShift AI installation failures for the active
baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product troubleshooting
details. Official Red Hat documentation is product authority. This skill adapts
the official installation troubleshooting chapter to this repo's GitOps and
support-evidence workflow.

## Scope

This skill covers installation-time failures in and around:

- Red Hat OpenShift AI Operator retrieval
- supported infrastructure checks
- OpenShift AI and Notebooks custom resource creation
- post-install dashboard access
- reinstall cleanup after uninstall
- dedicated-admins RBAC creation
- ODH parameter secret creation

Use `env-troubleshoot` with this skill when the user asks to inspect a live
cluster. Use `rhoai-logs-and-audit-records` when logger configuration, Operator
logs, or audit records are the main task.

## Support Boundary

Several official remedies are not local fixes. When the chapter says to contact
Red Hat Support, do not make up a remediation. Collect evidence, preserve the
official error signal, and recommend escalation.

Evidence should include:

- OpenShift AI Operator pod logs
- failing pod events
- relevant DSC and DSCI state
- install channel and Subscription state
- supported configuration evidence
- must-gather output when preparing a support case

## GitOps Policy

For this repo:

- Troubleshoot ArgoCD and GitOps sync state first, then map failures to the
  official RHOAI troubleshooting symptom.
- Do not manually mutate ArgoCD-managed install resources unless the user
  explicitly asks for live remediation.
- If a live fix is required, record the equivalent GitOps follow-up so the
  active repo does not drift from the cluster.
- Treat `Auth` custom resource deletion during reinstall as a destructive
  operation. Confirm uninstall state and user intent before deleting it.
- Do not commit raw must-gather archives or sensitive logs.

## Workflow

1. Confirm the active baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md`.
3. Classify the symptom using
   `examples/install-troubleshooting-symptom-map.md`.
4. If working on a live cluster, follow the OpenShift safety guard in
   `AGENTS.md` before any `oc` command.
5. Collect readonly evidence first:
   - Operator Subscription, CSV, pods, events, DSC, DSCI
   - `rhods-operator` pod logs
   - ArgoCD Application status for GitOps-managed install layers
6. Apply only official remediations or support escalation guidance.
7. Validate and document the result with
   `references/validation-checklist.md`.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/install-troubleshooting-symptom-map.md`
