# etcd Operations Patterns

## Read-Only Review Note

```text
Scope: Control plane and etcd health snapshot before RHOAI deployment.
Official source: OCP etcd guide for the active baseline.
Commands: read-only `oc get` and `oc logs` checks after environment guard.
Decision: no mutation; escalate to official etcd procedures if etcd or API
server operators are degraded.
```

## Backup Requirement Note

```text
Before changing etcd encryption, disk placement, tuning, or member state, take
an official etcd backup with `/usr/local/bin/cluster-backup.sh` from a control
plane debug shell. Preserve both the snapshot and static Kubernetes resources
archive outside the repository. If encryption is enabled, treat the static
resources archive as restore-key material.
```

## Encryption Configuration Shape

Use this only as a field-placement reminder. Verify the exact procedure against
the official docs before applying to a live cluster.

```yaml
apiVersion: config.openshift.io/v1
kind: APIServer
metadata:
  name: cluster
spec:
  encryption:
    type: aesgcm
```

Valid `spec.encryption.type` values from the captured OCP docs are:

- `aesgcm`
- `aescbc`
- `identity`

## Hardware Speed Review Pattern

```text
Symptom: frequent leader elections caused by timeouts or missed heartbeats.
Current state: capture `oc describe etcd/cluster | grep "Control Plane Hardware Speed"`.
Official knob: `spec.controlPlaneHardwareSpeed`, valid values "", "Standard",
and "Slower".
Decision: change only with explicit approval, backup, and rollout verification.
```

## Stretched Cluster Architecture Note

```text
Do not present a cluster spanning many data centers as disaster recovery.
For region/site resilience, prefer one OpenShift cluster per region or site
and manage them with multi-cluster tooling unless official platform-specific
support guidance approves a stretched design.
```
