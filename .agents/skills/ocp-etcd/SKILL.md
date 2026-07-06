---
name: ocp-etcd
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "ocp"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Platform"
description: >
  Use when documenting, reviewing, or rebuilding OpenShift Container Platform
  etcd guidance from official OCP documentation: operator-managed etcd
  behavior, control plane quorum, storage and latency practices, hardware
  validation, disk latency and consensus monitoring, defragmentation, moving
  etcd to a different disk, timer tuning, database size, network jitter and
  peer RTT, Kubernetes API transaction rate, backup and restore, unhealthy
  member replacement, disaster recovery, etcd encryption, and stretched-cluster
  caveats. Do NOT use for RHOAI component CRs; use rhoai-* skills. Do NOT use
  for ODF storage service behavior; use odf-* skills once created. Do NOT run
  live cluster operations without the env safety guard and explicit approval.
---

# OCP etcd

Use this skill to ground OpenShift etcd documentation, runbooks, GitOps review
notes, and live-environment planning in the official OpenShift Container
Platform etcd documentation for the active baseline in
`docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority. This skill extracts supported etcd
operations and validation patterns; it does not replace the full official
procedure for destructive recovery work.

## Safety Posture

Treat etcd as cluster-critical state:

- Prefer read-only health checks and documentation review before mutation.
- Take an official etcd backup before any maintenance, replacement, restore,
  encryption, disk-move, or tuning change that can affect the control plane.
- Do not store etcd snapshots, static pod resources, encryption keys, or
  kubeconfigs in this repository.
- Do not patch `unsupportedConfigOverrides` unless following an official Red
  Hat procedure and the user has explicitly approved the recovery action.
- Do not treat a cluster that spans sites as a disaster-recovery design.
- For live `oc` or `kubectl` commands, use the repo environment guard and pair
  this skill with the appropriate `env-*` skill.

## OCP etcd Model

Use the official docs to frame etcd as the OpenShift control plane data store
managed by the OpenShift etcd Operator. The main responsibilities for this demo
are:

- keep etcd quorum and control plane health visible in operations docs
- avoid unsupported low-level etcd changes in GitOps manifests
- document backup, restore, and disaster-recovery boundaries clearly
- review latency, disk, storage, and stretched-cluster assumptions for AWS demo
  environments
- ensure RHOAI and ODF planning respects etcd and API server performance limits

## Workflow

1. Confirm the active OpenShift baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md`.
3. Decide whether the task is read-only guidance, planned maintenance, or
   disaster recovery.
4. For read-only guidance, use the validation commands in
   `references/validation-checklist.md`.
5. For any mutation or recovery action, capture:
   - target cluster and API server guard status
   - current `ClusterVersion` and control plane operator status
   - backup location and age
   - official procedure URL and section name
   - rollback or support-escalation plan
6. For README or architecture content, describe the operational value without
   teaching unsupported etcd internals.
7. Validate the output with `references/validation-checklist.md`.

## Related Skills

- Use `project-red-hat-doc-skill-authoring` to create additional `ocp-*`
  skills from official OCP chapters.
- Use `project-gitops-authoring` for demo GitOps manifests.
- Use `project-manifest-review` for Kubernetes/OpenShift manifest review.
- Use `env-troubleshoot` for live environment diagnostics.
- Use `env-deploy-and-evaluate` or `env-manage-resources` for guarded live
  deployment and resource-management workflows once active scripts exist.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/etcd-operations-patterns.md`
