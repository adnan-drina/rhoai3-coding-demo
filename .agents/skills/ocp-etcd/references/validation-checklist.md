# Validation Checklist

Use this checklist when reviewing OCP etcd guidance, operations notes, or
GitOps changes that could affect the control plane.

## Source And Baseline

- The OpenShift baseline is read from `docs/PLATFORM_BASELINE.md`.
- The etcd source URL points to the matching OCP documentation version.
- Any README, runbook, or GitOps comment links to the official section used.
- Any uncertainty is captured with an `oc explain`, CRD, operator status, or
  official documentation follow-up.

## Safety Gate For Live Commands

- The command is necessary; prefer read-only checks where possible.
- The repo-local environment guard is satisfied before live `oc` or `kubectl`
  commands.
- The user explicitly approved any operation that mutates etcd, control plane
  configuration, MachineConfig, encryption, disk layout, or recovery state.
- An official etcd backup exists before mutation or recovery work.
- Backup artifacts and kubeconfigs are outside the Git repository.
- Red Hat Support involvement is considered for production-like disaster
  recovery, quorum loss, storage corruption, or uncertain procedures.

## Read-Only Health Snapshot

Use these commands only after the live-cluster guard is satisfied:

```bash
oc get clusterversion
oc get clusteroperators etcd kube-apiserver openshift-apiserver authentication
oc get etcd/cluster -o yaml
oc get nodes -l node-role.kubernetes.io/control-plane
oc -n openshift-etcd get pods -l k8s-app=etcd -o wide
oc -n openshift-etcd logs -l k8s-app=etcd --tail=100
```

If deeper etcd endpoint checks are needed, follow the official docs for using
`oc rsh` into an etcd pod and running `etcdctl`. Do not improvise cert paths or
etcdctl flags.

## Backup And Restore Review

- Backup procedure uses the official `/usr/local/bin/cluster-backup.sh`
  workflow from a control plane debug shell.
- The backup includes both `snapshot_<datetimestamp>.db` and
  `static_kuberesources_<datetimestamp>.tar.gz`.
- Restore planning accounts for API unavailability and SSH access to control
  plane hosts.
- Restore notes explicitly state that disaster recovery is cluster-wide and
  high risk.

## Encryption Review

- `APIServer` `spec.encryption.type` uses only `aesgcm`, `aescbc`, or
  `identity`.
- Backups are not taken while encryption or decryption is still in progress.
- Verification checks the `Encrypted` condition on OpenShift API server,
  Kubernetes API server, and OpenShift OAuth API server.
- Documentation states that values are encrypted, but resource types,
  namespaces, and object names are not.

## Spanned Cluster Review

- Documentation does not frame a stretched cluster as disaster recovery.
- Multi-site assumptions are linked to official OCP guidance and support
  posture.
- ODF or other layered-product latency requirements are deferred to the
  relevant product docs and active `odf-*` skills.

## Fail Conditions

Stop and correct the work if any of these are true:

- A control plane mutation is proposed without an official source section.
- A backup, restore, or encryption workflow stores sensitive artifacts in the
  repo.
- `unsupportedConfigOverrides` is used outside an explicit official recovery
  procedure.
- A stretched cluster is described as a replacement for disaster recovery.
- ODF storage behavior is inferred from OCP etcd docs instead of official ODF
  documentation.
