# Validation Checklist

Use this checklist before approving RHOAI platform planning content.

## Baseline

- `docs/PLATFORM_BASELINE.md` is current.
- RHOAI and OCP versions are compatible.
- Any ODF, OpenTelemetry, or tracing claims match their pinned baselines.

## Prerequisites

- Cluster-admin access is available.
- The target cluster has a default dynamic storage class.
- The target cluster has a configured identity provider.
- Required registry and internet access are documented for connected install.
- Object storage decision is documented for RHOAI components that need S3.

## Component Planning

- Component support status is checked against Red Hat supported configurations.
- Component prerequisites are routed to specific skills before manifest
  authoring.
- Preview or unsupported features are labeled through
  `rhoai-release-and-support-posture`.

## Verification Commands

Run only after the OpenShift safety guard passes:

```bash
oc version
oc get clusterversion
oc get storageclass
oc get oauth cluster -o yaml
oc get nodes
```
