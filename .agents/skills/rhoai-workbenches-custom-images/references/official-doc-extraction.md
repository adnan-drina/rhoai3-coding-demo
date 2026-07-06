# Official Doc Extraction

This extraction is derived from the official RHOAI 3.4 documents captured in
`source-capture.md`.

## Workbench Overview

In OpenShift AI, a workbench is an isolated environment where a data scientist
can examine and work with machine learning models. A workbench uses a workbench
image. OpenShift AI provides default workbench images, and administrators can
provide custom images when teams require specific tools or library versions.

Creation options include:

- CRDs and the OpenShift CLI
- OpenShift APIs
- OpenShift AI dashboard

This skill covers both product dashboard workflows and GitOps adaptation.

## Custom Image Purpose And Support Boundary

OpenShift AI includes default workbench images. Administrators can also import
custom workbench images when teams need frequently used libraries, specific
library versions, OS packages, or applications that data scientists cannot
install in a running workbench because they do not have root access.

A custom workbench image is a container image built with a Containerfile or
Dockerfile. The image can start from an existing image and add required
elements.

Red Hat supports adding custom workbench images to OpenShift AI so they are
available during workbench creation. Red Hat does not support the contents of
the custom image or provide fixes if the custom image itself fails to create a
usable workbench.

## Building From A Default OpenShift AI Image

Default workbench images are available in the OpenShift console under
`Builds -> ImageStreams` in the `redhat-ods-applications` project after
OpenShift AI is installed.

Prerequisites:

- know which default image to use as the base
- have `cluster-admin` access
- for Elyra compatibility, use a base OpenShift AI image that already contains
  the Elyra extension

Workflow:

1. Inspect the desired default `ImageStream` in `redhat-ods-applications`.
2. Read the tag entry under `spec.tags`.
3. Use the tag's `from.name` image reference as the `FROM` image in the custom
   Containerfile.
4. For OS packages, switch to `USER 0`, install packages, clean package
   metadata, then switch back to `USER 1001`.
5. For Python packages, use `USER 1001`, copy `requirements.txt`, and install
   with `pip`.
6. Build and push the image to a registry accessible to OpenShift AI, or use an
   OpenShift `BuildConfig`.

Subscription boundary: package operations such as `dnf install` or `dnf update`
can require active Red Hat subscriptions for the relevant RHEL/RHEL EUS package
content.

## Building A Compatible Custom Image

When starting from a non-OpenShift-AI base image, the image must be compatible
with OpenShift and OpenShift AI.

Basic compatibility guidance:

- design the image to run with `USER 1001`
- support OpenShift's random UID model with GID `0`
- avoid placing persistent artifacts directly in `$HOME`
- use `/opt/app-root/src` as the default persisted data location because the
  workbench personal volume is mounted there
- implement `/api` for non-Jupyter IDEs because readiness and liveness probes
  query that endpoint

Advanced compatibility guidance:

- prefer a newer base image over running `dnf update` on an older base image
- group `RUN` commands to reduce layers
- use multi-stage builds when compiling software
- set file/folder ownership to `1001:0` or set permissions so the random UID
  can write where needed
- set `WORKDIR /opt/app-root/src` for persisted data
- fix Python site-package permissions when required for OpenShift runtime
  access
- serve all workbench content from the path represented by `/${NB_PREFIX}`
- ensure a service answers at `${NB_PREFIX}/api`, otherwise probes can fail and
  the workbench pod can be deleted
- implement `${NB_PREFIX}/api/kernels` with the expected JSON shape when idle
  culling must work
- use CRB/EPEL only according to Red Hat base-image and package guidance

## Dashboard Enablement And Import

By default, OpenShift AI administrators can import custom workbench images from
the dashboard path:

```text
OpenShift AI dashboard -> Settings -> Environment setup -> Workbench images
```

If the Settings menu is not visible, check OpenShift AI administrator
permissions. The docs describe default administrator visibility for members of
`rhods-admins`, and OpenShift `cluster-admin` users automatically have
OpenShift AI administrator access.

If the Workbench images item is missing under Settings, check the dashboard
configuration option `dashboardConfig: disableBYONImageStream`. The documented
default is `false`, which makes the Workbench images menu item visible.

Import prerequisites:

- logged in to OpenShift AI with administrator privileges
- custom image exists in a registry accessible to OpenShift AI
- Workbench images dashboard navigation is enabled
- optional accelerator association requires an accelerator identifier and GPU
  support enabled in OpenShift AI, including Node Feature Discovery and the
  NVIDIA GPU Operator for NVIDIA GPU use

Import fields and metadata:

- image location can use a tag or digest, such as
  `quay.io/my-repo/my-image:tag` or
  `quay.io/my-repo/my-image@sha256:<digest>`
- name and optional description identify the image in the dashboard
- optional accelerator identifier can recommend an accelerator for the image
- optional software metadata and package metadata appear on the workbench
  creation page after import

Verification:

- imported image appears in the Workbench images table
- imported image is available when a user creates a workbench

## Custom Image With ImageStream

The official CRD path uses an OpenShift `ImageStream` custom resource to define
a custom workbench image. The `ImageStream` provides an image URL that can be
used by a workbench.

Prerequisites:

- cluster administrator privileges
- OpenShift CLI installed
- custom image available in a registry

Important dashboard discovery details:

- The default namespace for the custom image `ImageStream` is
  `redhat-ods-applications`.
- Dashboard-visible image streams require OpenShift AI labels and annotations.
- The `app.kubernetes.io/created-by: byon` label identifies a bring-your-own
  notebook image object.
- The image display name comes from
  `opendatahub.io/notebook-image-name`.
- The image description comes from
  `opendatahub.io/notebook-image-desc`.
- Image tags can describe Python dependencies, software versions, whether a tag
  is recommended, whether a tag is outdated, and the source build commit.
- The workbench image URL is formed from the `Image Repository` and tag, such
  as `<repository>:<tag>`.

Official verification:

```bash
oc describe imagestream <image-stream-name> -n redhat-ods-applications
```

## Workbench With Notebook

The official CRD path uses the Kubeflow `Notebook` custom resource to define a
workbench.

Prerequisites:

- cluster administrator privileges
- OpenShift CLI installed
- target project already exists
- image URL is known

Important `Notebook` details:

- API group and kind: `kubeflow.org/v1`, `Notebook`.
- `notebooks.opendatahub.io/inject-auth: "true"` marks the workbench as
  migrated to the OpenShift AI 3.x Gateway API access model. The RHOAI
  notebook controller uses this annotation to inject the `kube-rbac-proxy`
  sidecar, create the `*-kube-rbac-proxy` Service, and target that service
  from the generated HTTPRoute.
- `opendatahub.io/image-display-name` controls the image name visible in the
  dashboard.
- `openshift.io/display-name` controls the workbench display name.
- `notebooks.opendatahub.io/last-image-selection` records the selected image
  name and tag.
- `notebooks.opendatahub.io/last-image-version-git-commit-selection` records
  the selected workbench image build commit. The dashboard uses this annotation
  to decide whether the selected image version is current for the ImageStream
  tag.
- `opendatahub.io/connections` annotations can reference workbench
  connections.
- Optional Kueue scheduling uses `kueue.x-k8s.io/queue-name` with the name of
  an existing `LocalQueue` in the project.
- The main container sets CPU and memory requests/limits.
- The main container exposes port `8888` as `notebook-port`.
- `NOTEBOOK_ARGS` configures Jupyter base URL, token/password behavior,
  dashboard host, project prefix, and quit button behavior.
- `JUPYTER_IMAGE` should match the selected image URL.
- Custom CA environment variables can point to
  `/etc/pki/tls/custom-certs/ca-bundle.crt`.
- Workbench storage is mounted at `/opt/app-root/src`.
- `/dev/shm` is backed by an in-memory `emptyDir`.
- The custom CA bundle can be mounted from a ConfigMap and marked optional.
- The controller-injected `kube-rbac-proxy` container and related Service,
  ConfigMap, Secret, and HTTPRoute backend are generated operands. Do not copy
  generated image digests into Git; GitOps should own the supported Notebook
  annotations and core workbench spec.
- A Gateway-backed workbench is not proven reachable by the presence of a
  Service and HTTPRoute alone. Verify that the Notebook template, generated
  StatefulSet, and running pod include the injected `kube-rbac-proxy` sidecar,
  and that the generated `*-kube-rbac-proxy` Service has a ready EndpointSlice
  endpoint on port `8443`.
- When an already-created workbench is migrated to `inject-auth`, the generated
  StatefulSet might still lack the sidecar because the StatefulSet container
  list is immutable. Preserve the Notebook and PVC, and let the notebook
  controller recreate the generated StatefulSet from the corrected Notebook
  spec.

Official verification:

```bash
oc describe notebook -n <project-name>
oc get httproute -n redhat-ods-applications -l notebook-name=<workbench-name>
oc get endpointslice -n <project-name> \
  -l kubernetes.io/service-name=<workbench-name>-kube-rbac-proxy
```

## Unresolved Items

This document does not define:

- which storage class or PVC size to use
- enterprise image signing or vulnerability scanning policy
- exact project/RBAC model for team-owned workbenches
- complete queue design for Kueue-managed workbenches
- exact GitOps object or field backing every dashboard import setting
- enterprise lifecycle policy for rebuilding custom images when the base image
  or dependencies change

Use the relevant OpenShift, RHOAI, project, and security guidance before
implementing those areas.
