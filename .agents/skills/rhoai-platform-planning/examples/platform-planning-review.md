# Platform Planning Review

Use this pattern when starting a new demo capability.

## Questions

- Which RHOAI baseline is active?
- Which OpenShift baseline is active?
- Is the component GA, Technology Preview, Developer Preview, deprecated, or
  removed?
- Does the component require object storage, a database, cert-manager, Kueue,
  Gateway API, GPUs, Service Mesh, OpenTelemetry, Tempo, or ODF?
- Which component skill owns implementation details?

## Minimum Checks

```bash
oc version
oc get clusterversion
oc get storageclass
oc get nodes
```

Record findings in the implementation note, not in the skill.
