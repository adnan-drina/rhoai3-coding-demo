---
name: rhoai-workbench-image-import
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when an administrator imports an existing custom workbench image through
  the OpenShift AI dashboard (Settings, Environment setup, Workbench images):
  registry reachability, tag or digest, name, hardware profile identifier, software
  and package metadata, enabling or disabling the imported image. Not deployed
  in this demo. Do NOT use for building images or registering them in Git (use
  rhoai-workbenches-custom-images), NB_PREFIX routing (use
  rhoai-workbench-gateway-api-migration) or GPU enablement (use
  rhoai-nvidia-gpu-accelerators).
---

# RHOAI Workbench Image Import

Thin skill: repo decisions and pitfalls here, product behavior in the linked
OpenShift AI 3.5 sections.

**Not deployed in this demo.** No image has been imported and Git holds no
workbench `ImageStream`. The dashboard Workbench images menu keeps its default
(visible): `disableBYONImageStream` is not set in
`gitops/stages/010-openshift-ai-platform-foundation/rhoai-platform/odhdashboardconfig.yaml`.

## When to use

- A one-off trial of a custom workbench image in the live demo.
- Deciding between a dashboard import and a Git-managed ImageStream.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| A lasting image belongs in Git as an ImageStream, not a dashboard import; a dashboard import is live state Argo CD does not track | (none yet; see `rhoai-workbenches-custom-images`) | [Import a custom workbench image][import] |
| A GPU image recommends one of the Stage 020 profiles (`gpu-rtxpro6000`, `gpu-reserved-demo`) through the form's optional "Hardware profile identifier"; do not use the row's Create profile action, profiles live in Git | `gitops/stages/020-gpu-infrastructure-private-ai/gpu-quotas/hardware-profiles/` | [Import a custom workbench image][import] |

## Procedure

1. Confirm the image is reachable from the cluster and the image owner
   supports it (Red Hat supports the import, not the contents;
   [Import a custom workbench image][import]).
2. Import it in the dashboard; record the image reference and the date in
   `docs/OPERATIONS.md`.
3. Check after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   oc get imagestream -n redhat-ods-applications -l opendatahub.io/notebook-image=true
   ```

4. If the image stays, move it to Git (`rhoai-workbenches-custom-images`) and
   delete the dashboard import so there is one owner.

## Pitfalls

- An imported image that ignores `NB_PREFIX` starts but does not load in the
  browser (`rhoai-workbench-gateway-api-migration`).
- Keep private registry credentials out of Git and docs (`.env` only).

## Official documentation (OpenShift AI 3.5)

| Topic | Section |
|---|---|
| Import (administrator) | [Import a custom workbench image][import] |
| Same task in the custom image chapter | [Import a custom workbench image (custom images)][import-ci] |

## Related skills

`rhoai-workbenches-custom-images`, `rhoai-workbench-gateway-api-migration`,
`rhoai-hardware-profiles`, `rhoai-nvidia-gpu-accelerators`,
`rhoai-dashboard-customization`.

[import]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_resources/index#importing-a-custom-workbench-image_resource-mgmt
[import-ci]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#importing-a-custom-workbench-image_custom-images
