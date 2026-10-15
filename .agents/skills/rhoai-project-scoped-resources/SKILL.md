---
name: rhoai-project-scoped-resources
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when a team or project needs its own workbench image, hardware profile
  or KServe serving-runtime template visible only in one project, when
  deciding between a global resource in redhat-ods-applications and a
  project-scoped copy, or when the disableProjectScoped dashboard option comes
  up. Do NOT use for the global hardware profiles of Stage 020 (use
  rhoai-hardware-profiles), serving runtime details (use
  rhoai-model-serving-platform), custom image content (use
  rhoai-workbenches-custom-images), or creating projects (use
  rhoai-project-workflows).
---

# RHOAI project-scoped resources

Thin skill. Not deployed in this demo: every workbench image, hardware profile
and serving-runtime template that the dashboard offers is global (in
`redhat-ods-applications`). Product behavior is in the linked OpenShift AI 3.5
sections.

## When to use

- A demo step needs an option that only one project should see.
- Someone proposes copying a global profile or template into a project.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Hardware profiles are global only: `cpu-default`, `gpu-rtxpro6000`, `gpu-reserved-demo` in `redhat-ods-applications` | `gitops/stages/020-gpu-infrastructure-private-ai/gpu-quotas/hardware-profiles/` | [Create project-scoped resources][scoped] |
| No project-scoped `Template` with a `ServingRuntime`. The Stage 050 candidate ships a plain `ServingRuntime` `vllm-cuda-runtime` in `evaluated-models` with its InferenceService; it is not a dashboard template | `gitops/stages/050-model-evaluation/model-qualification/candidate-qwen3-8-27b-int4.yaml` | [Create project-scoped resources][scoped] |
| `disableProjectScoped` is not set, so it keeps its documented default (Developer Preview option) | `gitops/stages/010-openshift-ai-platform-foundation/rhoai-platform/odhdashboardconfig.yaml` (field absent) | [Dashboard configuration options][options] |

## If a project-scoped resource is needed

1. Put the copy in the GitOps component that owns the target project (for
   example the stage folder that creates the namespace), not in Stage 010.
2. Set `metadata.namespace` to the project and give it a name that is unique
   in that project, as the [procedure][scoped] requires.
3. A hardware profile copy that uses `Queue` scheduling also needs its
   LocalQueue in that project (see `rhoai-hardware-profiles`).
4. If the dashboard must show project-scoped items, add `disableProjectScoped`
   to `odhdashboardconfig.yaml` explicitly and record the Developer Preview
   status in the component README.
5. Read-only check after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   oc get hardwareprofile -A
   oc get templates -n redhat-ods-applications
   ```

## Pitfalls

- Global resources come from `redhat-ods-applications`; editing them changes
  every project.
- Users see a project-scoped resource only in projects where they have
  permissions ([Create project-scoped resources][scoped]).

## Official documentation (OpenShift AI 3.5)

| Topic | Section |
|---|---|
| Project-scoped workbench images, profiles, runtime templates | [Create project-scoped resources][scoped] |
| `disableProjectScoped` | [Dashboard configuration options][options] |
| Extra resources per user | [Allocate additional resources to OpenShift AI users][allocate] |

## Related skills

`rhoai-hardware-profiles`, `rhoai-model-serving-platform`,
`rhoai-workbenches-custom-images`, `rhoai-project-workflows`,
`rhoai-dashboard-customization`.

[scoped]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#creating-project-scoped-resources_managing-rhoai
[allocate]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#allocating-additional-resources-to-users_managing-rhoai
[options]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_resources/index#ref-dashboard-configuration-options_dashboard
