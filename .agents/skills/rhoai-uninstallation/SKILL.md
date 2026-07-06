---
name: rhoai-uninstallation
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use when documenting, reviewing, planning, or executing Red Hat OpenShift AI
  Self-Managed uninstallation and decommissioning: Operator-managed resource
  removal, retained user resources, PVC backup requirements, the official CLI
  uninstall ConfigMap and addon-managed-odh-delete label workflow, deletion of
  redhat-ods-operator, verification of rhods-operator Subscription removal,
  namespace cleanup checks, GitOps/ArgoCD decommission sequencing, and safe
  distinction between shutdown and uninstall. Do NOT use for normal demo
  shutdown, GPU cost reduction, temporary resource scale-down, reinstall
  troubleshooting, or unrelated OpenShift namespace cleanup; use env-manage-
  resources, env-troubleshoot, or rhoai-installation-troubleshooting instead.
---

# RHOAI Uninstallation

Use this skill to plan or review OpenShift AI Self-Managed uninstallation for
the active baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product uninstallation
details. Official Red Hat documentation is product authority. This skill adapts
the official CLI uninstall procedure to this repo's GitOps operating model and
live-cluster safety guard.

## Hard Boundary

Uninstalling OpenShift AI is destructive and is not the same as shutting down
the demo to save cost.

Use:

- `env-manage-resources` for stopping models or scaling GPU nodes down.
- `rhoai-uninstallation` only when the user intentionally wants to decommission
  or remove RHOAI Self-Managed from a cluster.

Do not run live uninstall commands unless the user explicitly asks for
uninstallation and confirms the target cluster.

## Official Behavior Summary

The official Red Hat procedure recommends using the OpenShift CLI (`oc`) for
uninstallation because web console uninstall behavior can leave the final
cluster state unclear.

Uninstall removes Operator-created resources but retains user-created resources
to avoid accidental data loss.

Before uninstalling, persistent disks or volumes used by PVCs must be backed up.

## GitOps Policy

For this repo:

- Disable, remove, or retarget ArgoCD Applications that manage RHOAI resources
  before running the official uninstall flow, so ArgoCD does not recreate
  resources while the Operator is deleting them.
- Record uninstall as an environment decommission operation, not as a normal
  deployment step.
- Preserve enough GitOps state to redeploy into a fresh environment later.
- Do not delete retained user projects or CRDs automatically. Review them after
  uninstall and delete only what the user explicitly approves.
- Do not commit raw backup archives, kubeconfigs, or sensitive uninstall logs.

## Workflow

1. Confirm the active baseline in `docs/PLATFORM_BASELINE.md`.
2. Confirm this is uninstall/decommissioning, not shutdown or scale-down.
3. Read `references/official-doc-extraction.md`.
4. If a live cluster is involved, follow the OpenShift safety guard in
   `AGENTS.md`.
5. Confirm backup of persistent disks or PVC-backed data.
6. Suspend or remove relevant ArgoCD Applications for RHOAI-managed resources.
7. Run the official CLI uninstall sequence from
   `examples/official-cli-uninstall-sequence.md`.
8. Verify removed and retained resources with
   `references/validation-checklist.md`.
9. Review retained user resources and decide whether they should remain, be
   exported, or be deleted.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/official-cli-uninstall-sequence.md`
