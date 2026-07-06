# Validation Checklist

Use this checklist before accepting authentication, identity-provider, or group
guidance.

## Source Validation

- The active OCP baseline is read from `docs/PLATFORM_BASELINE.md`.
- The source URL uses the pinned OCP documentation version.
- Identity-provider fields come from official OCP docs or active cluster
  schema.
- Provider-specific secrets, config maps, and namespaces match official docs.
- Any htpasswd guidance is clearly marked development or demo only.
- Direct external OIDC guidance includes a recovery-access warning.

## Manifest Review

- `apiVersion` and `kind` are verified for `OAuth` and related resources.
- `metadata.name` for the cluster OAuth resource is `cluster`.
- Referenced secrets are not committed.
- Identity mapping behavior is explicit.
- RHOAI access groups are not changed here unless paired with the relevant
  RHOAI access skill.

## Discovery Commands

Run only after the OpenShift safety guard confirms the target cluster:

```sh
oc get oauth cluster -o yaml
oc get users
oc get identities
oc get groups
oc get secret -n openshift-config
oc auth can-i '*' '*' --all-namespaces
```

For schema checks:

```sh
oc explain oauth.config.openshift.io.spec.identityProviders
oc explain oauth.config.openshift.io.spec.identityProviders.mappingMethod
```
