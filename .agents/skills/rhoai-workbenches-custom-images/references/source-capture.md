# Source Capture

## Official Product Sources

| Document | Chapter | URL | Category | Retrieved | Sections used |
|----------|---------|-----|----------|-----------|---------------|
| Red Hat OpenShift AI Self-Managed | Creating custom workbench images | https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_openshift_ai/creating-custom-workbench-images | Administer | 2026-06-10 | 2.1 through 2.4: default-image derivation, own-image guidelines, dashboard enablement, image import |
| Red Hat OpenShift AI Self-Managed | Creating a workbench | https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/creating_a_workbench/index | Develop | 2026-06-10 | Overview; creating a custom image with `ImageStream`; creating a workbench with `Notebook` |
| Red Hat OpenShift AI Self-Managed | Importing a custom workbench image | https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_resources/importing-a-custom-workbench-image_resource-mgmt | Administer / Managing resources | 2026-06-10 | Dashboard import workflow, support boundary, optional accelerator/software/package metadata, verification |
| Red Hat OpenShift AI Self-Managed | Introducing the Kubernetes Gateway API for custom image migration | https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_resources/introducing-kubernetes-gateway-api_resource-mgmt | Administer / Managing resources | 2026-06-10 | Path-based routing, `NB_PREFIX`, health endpoint, culling endpoints, relative URLs, NGINX translation |

Product baseline: `docs/PLATFORM_BASELINE.md`.

## Related Official Sources

| Source | Role |
|--------|------|
| https://access.redhat.com/articles/rhoai-supported-configs-3.x | Default workbench images and supported configurations |
| https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/images/index | OpenShift image creation, ImageStreams, and BuildConfig background |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/working_on_projects/using-project-workbenches_projects | Dashboard-created project workbenches |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/working_with_accelerators/working-with-hardware-profiles_accelerators | Hardware profile integration |

## Supporting Project Sources

| Source | Role |
|--------|------|
| `docs/PLATFORM_BASELINE.md` | Active RHOAI/OCP baseline and source hierarchy |
| `AGENTS.md` | OpenShift safety guard and GitOps operating constraints |
| `.agents/skills/rhoai-certificate-management/SKILL.md` | Custom CA bundle behavior for workbenches |
| `.agents/skills/rhoai-nvidia-gpu-accelerators/SKILL.md` | Optional NVIDIA GPU accelerator readiness context |
| `.agents/skills/rhoai-hardware-profiles/SKILL.md` | Optional hardware profile and recommended accelerator context |
| `.agents/skills/rhoai-distributed-workloads/SKILL.md` | Optional Kueue queueing context |

## Source Boundaries

- Product authority: official Red Hat documentation above.
- GitOps adaptation: project policy, not a Red Hat product requirement.
- Red Hat supports adding custom workbench images so they are selectable in
  OpenShift AI, but the contents and runtime behavior of custom images remain
  customer responsibility.
- Generic container image hardening, signing, and vulnerability management are
  outside this skill unless official RHOAI docs define a product requirement.
- Do not treat dashboard-generated timestamps or user activity annotations as
  stable desired state.
- Use `dashboardConfig: disableBYONImageStream` only for the documented
  Workbench images dashboard visibility setting. Do not invent other dashboard
  configuration fields.
- If active CRDs differ from the examples, verify with `oc explain` and record
  the chosen schema.
