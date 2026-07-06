# Official Doc Extraction

Use this extraction to keep image, registry, and mirroring work grounded in
official OCP sources. Verify exact fields with `oc explain` before authoring
manifests.

## Image Registry Operator

The Image Registry Operator manages the OpenShift internal image registry.
Registry configuration is cluster-scoped and can include management state,
replicas, storage, routes, certificates, and platform-specific storage
integration.

For this demo:

- Do not assume registry storage configuration unless the live cluster or
  official platform docs confirm it.
- Treat `configs.imageregistry.operator.openshift.io/cluster` changes as
  cluster-level operations.
- Keep registry credentials and pull secrets out of Git.

## Images And Image Streams

Image streams and image stream tags provide OpenShift-native references to
container images and imported image metadata. Image imports from private
registries require appropriate secrets and trust configuration.

Use image streams only when the implementation needs OpenShift image stream
behavior. Otherwise, use explicit official product images and validate image
source provenance through the relevant product skill.

## Mirroring

The OCP disconnected documentation covers the `oc-mirror` plugin v2 for image
set mirroring. The plugin is supported for OpenShift Container Platform and can
mirror release images, Operator catalog content, and additional images.

Important mirroring concepts:

- use the latest available `oc-mirror` plugin v2 for mirroring workflows
- define mirrored content with an image set configuration
- use mirror-to-disk, disk-to-mirror, or mirror-to-mirror workflows depending
  on connectivity
- apply generated mirror resources to configure clusters to use mirrored
  content
- `oc-mirror` workspace output can include `ImageDigestMirrorSet` and
  `ImageTagMirrorSet` manifests
- signature mirroring can be enabled when required by the environment

Do not add disconnected mirroring to the connected demo without a clear
implementation decision.

## Validation Signals

Healthy image and registry work should verify:

- Image Registry Operator state
- cluster image configuration
- pull-secret and registry trust posture
- image stream tags and imports, if used
- mirror-set resources, if disconnected mirroring is used
- official Red Hat image provenance for product components
