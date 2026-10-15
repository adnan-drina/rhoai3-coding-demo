---
name: ocp-etcd
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: ocp
  docs-version: "4.22"
  skill-group: "OpenShift Platform"
description: >
  Use when a question touches OpenShift etcd on the demo cluster: control-plane
  health or quorum risk, etcd backup, restore, member replacement, encryption,
  or the node-size gate in scripts/platform/require-node-sizing.sh that exists
  to protect the control plane. Read-only by default; every etcd change needs
  explicit user approval. Do NOT use for worker sizing or MachineSets (use
  ocp-machine-management) or node scheduling (use ocp-nodes).
---

# OpenShift etcd

Thin skill: this repo deploys and configures nothing for etcd. It records the
repo's one etcd-related guard and links the OpenShift Container Platform 4.22
etcd book for everything else.

## When to use

- A deploy or validate run reports API-server timeouts, control-plane nodes
  `NotReady`, or etcd alerts.
- `scripts/platform/require-node-sizing.sh` refuses a deploy.
- Someone asks for an etcd backup, restore, member replacement, defragmentation
  or encryption change.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| No etcd configuration, backup schedule or encryption setting is kept in Git; etcd stays as installed by the cluster provisioner | none (absence checked with a repository search) | [Overview of etcd][overview] |
| Every stage `deploy.sh` first refuses control-plane and CPU-worker nodes below 16 vCPU / 60 GiB (m6a.4xlarge class), because an undersized control plane put etcd quorum at risk on 2026-07-20; GPU nodes are exempt | `scripts/platform/require-node-sizing.sh` | [Recommended etcd practices][practices], [Reliable etcd performance and scalability][performance] |
| Backup, restore, member replacement and encryption are cluster-administrator operations outside the demo flow: no script in `scripts/` or `stages/` performs them | none | [Backing up and restoring etcd data][backup] |

## Procedure

1. Read-only checks, after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   oc get clusteroperator etcd kube-apiserver
   oc get pods -n openshift-etcd -l app=etcd -o wide
   oc get nodes -l node-role.kubernetes.io/control-plane -o wide
   ```

2. For an undersized control plane, run `scripts/platform/require-node-sizing.sh`
   and resize the nodes through the provisioner; do not lower
   `REQUIRED_NODE_VCPU` / `REQUIRED_NODE_MEM_GIB` to get a deploy through.
3. Any backup, restore, member replacement, defragmentation or encryption change:
   stop, describe the operation and its blast radius, and get explicit user
   approval. Follow the linked 4.22 section verbatim; never improvise etcd
   commands.

## Pitfalls

- Control-plane exhaustion presents first as API timeouts and kubelet status
  loss, not as etcd errors; check node capacity before suspecting etcd
  (`scripts/platform/require-node-sizing.sh` header records the incident).
- A restore to a previous cluster state is a disaster-recovery path, not a way
  to undo a bad sync; GitOps re-sync is the repo's recovery path
  ([Disaster recovery][dr]).
- Turning on etcd encryption re-encrypts resources and takes time; plan it as a
  cluster change, not a demo step ([Enabling etcd encryption][encrypt]).

## Official documentation (OpenShift Container Platform 4.22)

| Topic | Section |
|---|---|
| Overview | [Overview of etcd][overview] |
| Practices and performance | [Recommended etcd practices][practices], [Reliable etcd performance and scalability][performance] |
| Backup and restore | [Backing up and restoring etcd data][backup], [Backing up etcd data][backup-data], [Replacing an unhealthy etcd member][unhealthy], [Disaster recovery][dr] |
| Encryption | [Enabling etcd encryption][encrypt] |

## Related skills

`ocp-machine-management`, `ocp-nodes`, `ocp-observability`, `inspect-cluster`.

[overview]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/etcd/index#etcd-overview
[practices]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/etcd/index#etcd-practices
[performance]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/etcd/index#etcd-performance
[backup]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/etcd/index#backing-up-and-restoring-etcd-data
[backup-data]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/etcd/index#backing-up-etcd-data_etcd-backup
[unhealthy]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/etcd/index#replace-unhealthy-etcd-member
[dr]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/etcd/index#etcd-disaster-recovery
[encrypt]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/etcd/index#etcd-encrypt
