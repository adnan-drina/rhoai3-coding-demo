# Validation Checklist

Use this checklist before accepting custom workbench image import docs,
runbooks, or demo operations.

## Source Review

- Product links use the active baseline in `docs/PLATFORM_BASELINE.md`.
- The official chapter URL uses the active `/3.4/` baseline path.
- The work is limited to dashboard import of an existing custom image.
- Custom image build guidance is delegated to `rhoai-workbenches-custom-images`.
- Dashboard visibility controls are delegated to `rhoai-dashboard-customization`.
- GPU setup is delegated to `rhoai-nvidia-gpu-accelerators`.

## Prerequisite Review

- Operator has OpenShift AI administrator privileges.
- Custom image exists in a registry reachable from OpenShift AI.
- Workbench images dashboard navigation is enabled.
- Private registry authentication is handled outside of committed docs and
  examples.
- If accelerator metadata is used, GPU support is already enabled.
- If NVIDIA acceleration is used, Node Feature Discovery and the NVIDIA GPU
  Operator are installed and validated.

## Import Field Review

- Image location uses the intended registry, tag, or digest.
- Digest-pinned image references are used only when Red Hat guidance,
  validated artifact guidance, or an approved non-operator demo-app exception
  requires them.
- Name is clear for data scientists choosing a workbench image.
- Description explains the image purpose without overstating support.
- Accelerator identifier matches the active accelerator and hardware profile
  design.
- Software metadata names and versions match the image contents.
- Package metadata names and versions match the image contents.
- No credentials, tokens, or private endpoints are entered into visible
  metadata fields.

## Dashboard Workflow Review

Use the official dashboard path:

```text
OpenShift AI dashboard -> Settings -> Environment setup -> Workbench images
```

Check:

- existing imported images are reviewed before importing duplicates
- Enable column toggle state matches whether the image should be selectable
- Import new image or Import image opens the import dialog
- optional Software and Packages metadata is confirmed before import
- import completes without image registry or permission errors

## Verification Review

After import:

- image appears in the Workbench images table
- image is enabled when users should be able to select it
- image appears during project workbench creation
- user-facing metadata is accurate on the workbench creation page
- accelerator recommendation appears only when configured and supported
- a smoke-test workbench using the image starts before the image is presented
  as demo-ready

## Fail Conditions

- The image is imported from a registry the cluster cannot reach.
- The Workbench images menu is hidden while the runbook expects dashboard
  import.
- The image is presented as Red Hat-supported beyond the documented support
  boundary.
- Accelerator metadata is set before GPU support or the identifier is verified.
- Software or package metadata does not match the actual image.
- A selectable image is treated as usable without a workbench start smoke test.
