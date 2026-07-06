---
name: rhoai-workbench-image-import
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use when documenting, reviewing, or performing the Red Hat OpenShift AI
  dashboard workflow for importing a custom workbench image: support boundary
  for custom image contents, Workbench images dashboard menu prerequisites,
  registry reachability, image tag or digest entry, name and description
  metadata, optional accelerator identifier association, optional software and
  package metadata, enabling or disabling imported images, and verifying that
  the image appears for workbench creation. Do NOT use for building custom
  images, ImageStream GitOps registration, Notebook CR authoring, custom
  workbench runtime compatibility, or GPU Operator installation; use
  rhoai-workbenches-custom-images or rhoai-nvidia-gpu-accelerators instead.
---

# RHOAI Workbench Image Import

Use this skill for the OpenShift AI dashboard workflow that imports an existing
custom workbench image so users can select it when creating project
workbenches.

## Source Grounding

Read `references/source-capture.md` before using product behavior details.
Official Red Hat documentation is product authority. This skill adapts the
official Managing resources chapter to this repo's demo governance model.

## Scope

This skill covers:

- importing a custom workbench image through the OpenShift AI dashboard
- understanding Red Hat's support boundary for custom image contents
- verifying the Workbench images dashboard navigation is enabled
- entering an image registry URL by tag or digest
- setting image name and description metadata
- enabling or disabling previously imported images
- associating an accelerator identifier when GPU support is enabled
- adding optional software and package metadata for the workbench creation page
- validating that the imported image appears in the table and workbench flow

Use `rhoai-workbenches-custom-images` for custom image build guidance,
ImageStream resources, Notebook resources, OAuth proxy patterns, PVCs, custom
CA behavior, and GitOps registration.

## Demo Policy

For this repo:

- Prefer GitOps-managed `ImageStream` resources for stable demo desired state,
  but treat dashboard import as an official product workflow and useful
  operator runbook.
- Do not claim Red Hat supports the contents of a custom image. Red Hat
  supports making custom workbench images selectable in OpenShift AI.
- Avoid digest pinning as a default repeatability mechanism. Use the image
  reference documented by Red Hat or the image owner, and use a digest only
  when Red Hat guidance, validated artifact guidance, or an approved
  non-operator demo-app exception requires it.
- Do not import images from registries that are unreachable from the OpenShift
  cluster.
- Use accelerator metadata only after GPU support and the accelerator
  identifier are confirmed.
- Keep private registry credentials out of docs and GitOps examples.

## Workflow

1. Confirm the active baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/source-capture.md` and
   `references/official-doc-extraction.md`.
3. Confirm the operator has OpenShift AI administrator privileges.
4. Confirm the custom image exists in a registry accessible to OpenShift AI.
5. Confirm the dashboard path is visible:

   ```text
   OpenShift AI dashboard -> Settings -> Environment setup -> Workbench images
   ```

6. Use Import new image or Import image.
7. Enter the image location, name, and optional description.
8. Optionally set accelerator identifier, software metadata, and package
   metadata.
9. Import the image and validate with `references/validation-checklist.md`.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/workbench-image-import-patterns.md`
