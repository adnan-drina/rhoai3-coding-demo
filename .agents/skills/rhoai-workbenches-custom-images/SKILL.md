---
name: rhoai-workbenches-custom-images
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when someone proposes a custom OpenShift AI workbench image or a
  Git-managed workbench for this demo: building from a default image or a
  compatible own image (USER 1001), registering it as an ImageStream in
  redhat-ods-applications, declaring a Notebook CR, showing or hiding
  pre-installed images, or the dashboard Workbench images menu
  (disableBYONImageStream). Not deployed in this demo. Do NOT use for the
  dashboard import form (use rhoai-workbench-image-import), NB_PREFIX and
  Gateway API path routing (use rhoai-workbench-gateway-api-migration),
  project workbench lifecycle (use rhoai-project-workflows) or Dev Spaces
  images (use manage-devspaces).
---

# RHOAI Workbenches and Custom Images

Thin skill: repo decisions and pitfalls here, product behavior in the linked
OpenShift AI 3.5 sections.

**Not deployed in this demo.** Git holds no `ImageStream` for workbenches, no
`Notebook` CR and no `disableBYONImageStream` setting. The Workbenches
component is `Managed`
(`gitops/stages/010-openshift-ai-platform-foundation/010-rhoai-platform/datasciencecluster.yaml`)
and users create project workbenches from the pre-installed images.

## When to use

- A notebook workflow needs packages that many workbenches share.
- Someone wants a workbench declared in Git instead of created in the dashboard.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Pre-installed images only; developer tooling lives in Dev Spaces images (Stage 070) | `gitops/stages/010-openshift-ai-platform-foundation/010-rhoai-platform/datasciencecluster.yaml`, `stages/070-advanced-app-platform/README.md` | [Default workbench images][defaults] |
| `disableBYONImageStream` not set in `odh-dashboard-config`, so the Workbench images menu keeps its documented default (visible) | `gitops/stages/010-openshift-ai-platform-foundation/010-rhoai-platform/odhdashboardconfig.yaml` | [Enable custom images][enable] |
| No workbench objects in Git; users create workbenches in projects such as `demo-sandbox` | `gitops/stages/010-openshift-ai-platform-foundation/010-access/README.md` | [Custom workbench from a CRD][crd] |

## If you add a custom image

1. Build it as the docs describe ([from a default image][from-default] or
   [from your own image][from-own]); Red Hat supports importing custom images,
   not their contents.
2. Register it in Git as an `image.openshift.io/v1` ImageStream in
   `redhat-ods-applications` with label `opendatahub.io/notebook-image: 'true'`
   ([ImageStream CRD][is-crd]). Put it in its own component folder with an
   Argo CD Application and README (see `project-demo-stage-authoring`,
   `review-gitops-change`); do not add it to `010-rhoai-platform`, which owns
   only the platform singletons.
3. Make the image honor `NB_PREFIX` (`rhoai-workbench-gateway-api-migration`).
4. A Git-managed workbench is a `Notebook` CR in its project
   ([Notebook CRD][nb-crd]). Read the served schema first:
   `oc explain notebook.spec` (the 3.5 page does not state the API version).
   Give it a hardware profile whose LocalQueue exists in that project
   (`rhoai-hardware-profiles`).
5. Validate after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   oc get imagestream -n redhat-ods-applications -l opendatahub.io/notebook-image=true
   oc get notebooks.kubeflow.org -A
   ```

## Pitfalls

- An image not built for a random UID with GID 0 fails at start; follow the
  `USER 1001` guidance in [from your own image][from-own].
- Hiding a pre-installed image is a dashboard toggle with no documented field;
  record it in `docs/OPERATIONS.md` rather than inventing one
  ([Hide and show images][hide]).
- Do not copy dashboard-generated annotations (timestamps, last activity) into Git.

## Official documentation (OpenShift AI 3.5)

| Topic | Section |
|---|---|
| Build | [From a default image][from-default], [From your own image][from-own] |
| Enable and show | [Enable custom images][enable], [Hide and show images][hide], [Default images][defaults] |
| CRD path | [Custom workbench from a CRD][crd], [ImageStream CRD][is-crd], [Notebook CRD][nb-crd] |

## Related skills

`rhoai-workbench-image-import`, `rhoai-workbench-gateway-api-migration`,
`rhoai-project-workflows`, `rhoai-hardware-profiles`,
`rhoai-dashboard-customization`, `rhoai-data-science-ide-workflows`, `manage-devspaces`.

[from-default]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#creating-a-custom-image-from-default-image_custom-images
[from-own]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#creating-a-custom-image-from-your-own-image_custom-images
[enable]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#enabling-custom-images_custom-images
[hide]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#hiding-and-showing-preinstalled-workbench-images_custom-images
[defaults]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_on_projects/index#default-workbench-images_projects
[crd]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/creating_a_workbench/index#api-workbench-overview_api-workbench
[is-crd]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/creating_a_workbench/index#api-custom-image-creating_api-workbench
[nb-crd]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/creating_a_workbench/index#api-workbench-creating_api-workbench
