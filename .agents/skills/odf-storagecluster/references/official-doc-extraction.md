# Official Doc Extraction

## Planning And Architecture

- ODF provides storage services through storage classes and object interfaces,
  including block storage, shared and distributed file storage, multicloud
  object storage, and on-premises object storage.
- Multicloud Object Gateway is the lightweight S3-compatible object storage
  layer and can be deployed as the object-storage-only footprint for this demo.
- Full StorageCluster/Ceph deployment is appropriate only when the demo needs
  ODF-provided block or file storage in addition to object storage.

## AWS Deployment Posture

- The AWS deployment guide covers ODF deployment on existing OpenShift clusters
  on AWS infrastructure.
- AWS deployment supports internal ODF clusters and a standalone Multicloud
  Object Gateway deployment.
- For this demo, prefer standalone MCG first because it satisfies the common
  RHOAI need for S3-compatible object storage with a smaller footprint.
- If a full StorageCluster is selected, review the AWS deployment guide for the
  supported device and storage-system path before writing manifests.

## Validation Signals

Use readonly checks first:

```bash
oc get csv -n openshift-storage
oc get pods -n openshift-storage
oc get storageclass
oc get noobaa -n openshift-storage
```

Expected validation themes from official docs:

- ODF operator, OCS operator, and NooBaa pods exist in `openshift-storage`.
- Dashboard status for StorageCluster and Object service should be healthy.
- A standalone MCG deployment should expose object service state through
  NooBaa resources and ODF dashboards.
- Full ODF deployments commonly create storage classes for Ceph block, CephFS,
  and NooBaa object storage.

## Update Alignment

- Keep the ODF version aligned with the OpenShift minor version unless Red Hat
  support guidance says otherwise.
- For the active baseline, use ODF 4.20 documentation with OCP 4.20.

## Troubleshooting Boundaries

- Start troubleshooting with ODF status, pods, dashboards, events, and
  must-gather.
- Use the ODF must-gather image for the active ODF version when collecting
  diagnostics.
- Do not run unsupported Ceph commands. Red Hat warns that unsupported Ceph
  commands can cause data loss unless instructed by Red Hat support or docs.
