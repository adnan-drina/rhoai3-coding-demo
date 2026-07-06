# Official Documentation Extraction

This extraction is derived from the official RHOAI 3.4 chapter captured in
`source-capture.md`.

## Purpose

Custom workbench images supplement the workbench images provided by Red Hat and
independent software vendors. They let administrators expose images tailored to
a project or team so data scientists can select them when creating a project
workbench.

## Support Boundary

Red Hat supports adding custom workbench images to OpenShift AI so that they
are available for workbench creation. Red Hat does not support the contents of
the custom image. If a custom image is selectable but fails to create a usable
workbench, the image content remains customer-owned.

Document this boundary whenever a README or runbook introduces custom
workbench images.

## Prerequisites

- The operator is logged in to OpenShift AI with administrator privileges.
- The custom image exists in an image registry reachable from OpenShift AI.
- The dashboard menu item is enabled:

  ```text
  Settings -> Environment setup -> Workbench images
  ```

- When associating an accelerator, the accelerator identifier is known.
- GPU support is enabled before associating accelerator metadata.
- NVIDIA GPU association requires Node Feature Discovery and NVIDIA GPU
  Operator setup.

## Dashboard Procedure

Official dashboard path:

```text
OpenShift AI dashboard -> Settings -> Environment setup -> Workbench images
```

Procedure summary:

1. Open Workbench images.
2. Review previously imported images.
3. Enable or disable an existing imported image with the Enable column toggle
   when needed.
4. If accelerator association is needed and no accelerator or hardware profile
   exists, create the profile from the image row after the image has the
   required accelerator identifier.
5. Click Import new image, or Import image if no images exist.
6. Enter the image location.
7. Enter a name.
8. Optionally enter a description.
9. Optionally select an accelerator identifier.
10. Optionally add software metadata.
11. Optionally add package metadata.
12. Import the image.

## Image Location

The image location field accepts a repository URL by tag or digest.

Documented shapes include:

```text
quay.io/my-repo/my-image:tag
quay.io/my-repo/my-image@sha256:<digest>
docker.io/my-repo/my-image:tag
```

For this project, digest pinning is not the default repeatability mechanism.
Use a digest only when Red Hat guidance, validated artifact guidance, or an
approved non-operator demo-app exception requires it.

## Accelerator Identifier

The Accelerator identifier list can mark an accelerator as recommended for the
image.

Important details:

- If the image contains only one accelerator identifier, it displays by
  default.
- If the image does not contain an accelerator identifier, configure one
  manually before creating an associated accelerator profile or hardware
  profile.
- Accelerator metadata should match the active GPU setup and hardware profile
  design.

## Software Metadata

The Software tab allows optional metadata entries. After import, this metadata
appears on the workbench creation page.

Each software entry includes:

- software name
- software version

Multiple software entries can be added.

## Package Metadata

The Packages tab allows optional package metadata entries. After import, this
metadata appears on the workbench creation page.

Each package entry includes:

- package name
- package version

Multiple package entries can be added.

## Verification

After import:

- the custom image appears in the Workbench images table
- the custom image is available for selection when a user creates a workbench

## Out Of Scope For This Chapter

This chapter does not define:

- how to build the custom workbench image
- full runtime compatibility requirements for custom images
- ImageStream GitOps registration fields
- Notebook custom resources
- pull-secret and private registry strategy
- exact accelerator profile or hardware profile fields
- image signing, vulnerability scanning, or rebuild policy

Use `rhoai-workbenches-custom-images`, `rhoai-dashboard-customization`, and
`rhoai-nvidia-gpu-accelerators` for those areas.
