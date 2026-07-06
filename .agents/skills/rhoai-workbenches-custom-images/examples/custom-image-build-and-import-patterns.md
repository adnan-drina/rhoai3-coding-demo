# Custom Image Build And Import Patterns

These examples are minimal patterns for RHOAI custom workbench image review.
Verify active image references, subscriptions, and cluster settings before use.

## Derive From A Default OpenShift AI Image

Find the base image from the default workbench `ImageStream`:

```bash
oc get imagestream -n redhat-ods-applications
oc get imagestream pytorch -n redhat-ods-applications -o yaml
```

Use the desired tag's `spec.tags[].from.name` value as the Containerfile
`FROM` image.

```Dockerfile
FROM quay.io/modh/odh-pytorch-notebook@sha256:<digest>

USER 0
RUN INSTALL_PKGS="java-11-openjdk java-11-openjdk-devel" && \
    dnf install -y --setopt=tsflags=nodocs ${INSTALL_PKGS} && \
    dnf -y clean all --enablerepo=*

USER 1001
COPY requirements.txt ./requirements.txt
RUN pip install -r requirements.txt
```

Only use package installation commands when the required Red Hat package
subscriptions and repositories are available.

## Own-Image Compatibility Checklist

When the base image is not a default OpenShift AI image, keep these constraints
visible in the Containerfile review:

```Dockerfile
USER 1001
WORKDIR /opt/app-root/src
```

Review notes:

- support OpenShift random UID execution with GID `0`
- avoid placing expected persistent artifacts directly in `$HOME`
- make writable paths accessible to UID `1001` and group `0`, or to the random
  UID used by OpenShift
- for non-Jupyter IDEs, implement an `/api` endpoint for probes
- serve browser content below `/${NB_PREFIX}`
- implement `${NB_PREFIX}/api/kernels` if idle culling is expected
- prefer a current base image over running broad `dnf update`
- use grouped `RUN` commands and multi-stage builds to limit image size

## Publish And Import

Publish to a registry reachable by OpenShift AI:

```bash
podman build -t registry.example.com/team/rhoai-workbench:1.0 .
podman push registry.example.com/team/rhoai-workbench:1.0
```

Import through:

```text
OpenShift AI dashboard -> Settings -> Environment setup -> Workbench images
```

Capture these values for GitOps or operations notes:

```text
Image location: registry.example.com/team/rhoai-workbench@sha256:<digest>
Name: Team Workbench
Description: RHOAI demo workbench image for team notebooks
Software metadata: Python, JupyterLab, CUDA tooling, or other visible tools
Package metadata: package names and versions shown during workbench creation
Accelerator identifier: nvidia.com/gpu, only when GPU support is enabled
```

Use a digest for stable demo images when possible. If a mutable tag is used,
document the rebuild and retest expectation.
