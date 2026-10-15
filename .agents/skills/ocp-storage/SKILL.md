---
name: ocp-storage
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: ocp
  docs-version: "4.22"
  skill-group: "OpenShift Platform"
description: >
  Use when reviewing or changing block storage in this repo: PVCs and
  volumeClaimTemplates that name storageClassName gp3-csi (cluster monitoring,
  MaaS database, MLflow and EvalHub PostgreSQL, SonarQube, the Stage 070 Git
  server), the requirement that gp3-csi is the default StorageClass, PVC
  expansion, or nodes evicting pods for ephemeral storage. Do NOT use for ODF,
  NooBaa or ObjectBucketClaims (use odf-storagecluster, odf-storage-classes,
  odf-object-bucket-claims) or OpenShift AI workbench storage settings (use
  rhoai-storage-classes, rhoai-cluster-pvc-size).
---

# OpenShift storage

Thin skill: repo decisions and pitfalls here, product behavior in the linked
OpenShift Container Platform 4.22 sections. The repo creates no StorageClass:
block storage is the AWS EBS CSI class `gp3-csi` the installer provides, and
object storage is ODF Multicloud Object Gateway (see the `odf-*` skills).

## When to use

- A manifest adds or changes a PVC, a `volumeClaimTemplate`, or a
  `storageClassName`.
- A component expects the default StorageClass.
- A pod is evicted for ephemeral storage or a PVC stays `Pending`.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| No StorageClass is defined in Git; RWO block volumes name `gp3-csi` explicitly (AWS EBS CSI driver, installer-created) | `gitops/stages/040-governed-models-as-a-service/040-maas-database/statefulset.yaml`, `gitops/stages/050-model-evaluation/050-mlflow/postgresql-pvc.yaml`, `gitops/stages/050-model-evaluation/050-evalhub/postgresql-pvc.yaml`, `gitops/stages/070-advanced-app-platform/070-sonarqube/` | [AWS EBS CSI Driver Operator][ebs], [Defining a storage class][define-sc] |
| `gp3-csi` must be the default StorageClass: Stage 070 `deploy.sh` fails otherwise, because MTA 8.3 creates default-class RWO claims | `stages/070-advanced-app-platform/deploy.sh` | [Managing the default storage class][default-sc] |
| Platform and user-workload monitoring persist on `gp3-csi` (40Gi and 20Gi); `stages/030-private-model-serving/validate.sh` checks the reviewed class and size | `gitops/stages/010-openshift-ai-platform-foundation/010-observability-operators/cluster-monitoring/` | [Understanding persistent storage][pv] |
| Object storage is ODF MCG (`openshift-storage.noobaa.io` ObjectBucketClaims), owned by the `odf-*` skills | `gitops/stages/010-openshift-ai-platform-foundation/010-odf/` | see `odf-storagecluster` |
| GPU worker root disks are 200 GB encrypted gp3, set in the generated MachineSets (node image cache for modelcars) | `gitops/stages/020-gpu-infrastructure-private-ai/020-gpu-machinesets/` | [Understanding ephemeral storage][ephemeral] |

## Procedure

1. New stateful component: add a PVC with `storageClassName: gp3-csi` and an
   explicit size next to the component; do not rely on the default unless the
   operator gives no choice (then record it, as Stage 070 does for MTA).
2. Validate the owning stage with its `validate.sh`; the default-class check
   runs at the start of `./stages/070-advanced-app-platform/deploy.sh`.
3. Read-only checks, after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   oc get storageclass
   oc get storageclass gp3-csi -o jsonpath='{.metadata.annotations.storageclass\.kubernetes\.io/is-default-class}{"\n"}'
   oc get pvc -A | grep -v Bound
   oc get clustercsidriver ebs.csi.aws.com
   ```

## Pitfalls

- Absent or multiple default StorageClasses leave default-class claims
  `Pending` or bound to the wrong class ([Absent or multiple defaults][multi-default]).
- EBS volumes are zonal and RWO: a pod moved to another zone cannot attach its
  volume; keep stateful replicas at one or use zone-aware placement.
- PVC expansion needs `allowVolumeExpansion` on the class and is one-way
  ([Expanding persistent volumes][expand]).
- Node disk pressure from cached modelcar and build images evicts pods for
  ephemeral storage:
  `docs/TROUBLESHOOTING.md#pipeline-or-workspace-pods-evicted-for-ephemeral-storage`.

## Official documentation (OpenShift Container Platform 4.22)

| Topic | Section |
|---|---|
| Overview | [Storage overview][overview], [Understanding persistent storage][pv], [Understanding ephemeral storage][ephemeral] |
| CSI | [Configuring CSI volumes][csi], [AWS EBS CSI Driver Operator][ebs], [CSI volume snapshots][snapshots] |
| Storage classes | [Dynamic provisioning][dynamic], [Defining a storage class][define-sc], [Managing the default storage class][default-sc], [Absent or multiple defaults][multi-default] |
| Expansion | [Expanding persistent volumes][expand] |

## Related skills

`odf-storagecluster`, `odf-storage-classes`, `odf-object-bucket-claims`,
`rhoai-storage-classes`, `rhoai-cluster-pvc-size`, `ocp-machine-management`.

[overview]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/storage/index#storage-overview
[pv]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/storage/index#understanding-persistent-storage
[ephemeral]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/storage/index#understanding-ephemeral-storage
[csi]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/storage/index#persistent-storage-csi
[ebs]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/storage/index#persistent-storage-csi-ebs
[snapshots]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/storage/index#persistent-storage-csi-snapshots
[dynamic]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/storage/index#dynamic-provisioning
[define-sc]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/storage/index#dynamic-provisioning-defining-storage-class_dynamic-provisioning
[default-sc]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/storage/index#persistent-storage-csi-sc-manage
[multi-default]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/storage/index#persistent-storage-csi-sc-multiple-none_persistent-storage-csi-sc-manage
[expand]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/storage/index#expanding-persistent-volumes
