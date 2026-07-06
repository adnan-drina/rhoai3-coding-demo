# Validation Checklist

Use this checklist before accepting image, registry, or mirroring guidance.

## Source Validation

- The active OCP baseline is read from `docs/PLATFORM_BASELINE.md`.
- The source URL uses the pinned OCP documentation version.
- Registry, image stream, mirror, and image configuration fields come from
  official OCP docs or active cluster schema.
- Product image names come from the relevant product skill and official docs.
- Disconnected mirroring is clearly marked future or active implementation
  intent.

## Manifest Review

- Pull-secret material is never committed.
- Registry credentials are referenced through secrets.
- Internal registry changes are documented as cluster-level operations.
- `ImageDigestMirrorSet` and `ImageTagMirrorSet` resources are generated or
  verified from supported mirroring workflows.
- Image references use official Red Hat registries when required by product
  docs.

## Discovery Commands

Run only after the OpenShift safety guard confirms the target cluster:

```sh
oc get configs.imageregistry.operator.openshift.io cluster -o yaml
oc get image.config.openshift.io cluster -o yaml
oc get imagestream -A
oc get imagedigestmirrorset,imagetagmirrorset
oc get secret pull-secret -n openshift-config -o yaml
oc get clusteroperator image-registry -o yaml
```

For schema checks:

```sh
oc explain configs.imageregistry.operator.openshift.io.spec
oc explain image.config.openshift.io.spec
oc explain imagedigestmirrorset.spec
oc explain imagetagmirrorset.spec
```
