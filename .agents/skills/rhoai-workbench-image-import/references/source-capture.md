# Source Capture

## Official Product Source

| Field | Value |
|-------|-------|
| Product baseline | `docs/PLATFORM_BASELINE.md` |
| Document title | Configure user access, storage, and telemetry in OpenShift AI |
| Chapter title | Chapter 3. Importing a custom workbench image |
| Chapter URL | https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_resources/importing-a-custom-workbench-image_resource-mgmt |
| Documentation category | Administer / Managing resources |
| Retrieved date | 2026-06-10 |
| Sections used | Chapter introduction, support boundary, prerequisites, import procedure, software metadata, package metadata, verification, additional resources |

## Related Official Sources

| Source | Role |
|--------|------|
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_openshift_ai/creating-custom-workbench-images | Building and enabling custom workbench images |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_resources/customizing-the-dashboard | Dashboard configuration, including Workbench images menu visibility |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/working_with_accelerators/enabling-nvidia-gpus_accelerators | NVIDIA GPU support when associating accelerator metadata |
| https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/images/index | ImageStreams and BuildConfig background from OpenShift |

## Supporting Project Sources

| Source | Role |
|--------|------|
| `docs/PLATFORM_BASELINE.md` | Active RHOAI/OCP baseline and source hierarchy |
| `AGENTS.md` | OpenShift safety guard and GitOps operating constraints |
| `.agents/skills/rhoai-workbenches-custom-images/SKILL.md` | Broader custom image build, ImageStream, Notebook, and GitOps patterns |
| `.agents/skills/rhoai-dashboard-customization/SKILL.md` | Dashboard feature visibility and `OdhDashboardConfig` behavior |
| `.agents/skills/rhoai-nvidia-gpu-accelerators/SKILL.md` | NVIDIA GPU support and accelerator identifiers |

## Source Boundaries

- Product authority: the official Red Hat OpenShift AI 3.4 Managing resources
  chapter above.
- This chapter defines a dashboard import workflow, not a full image-build or
  GitOps registration pattern.
- Red Hat supports adding custom workbench images to OpenShift AI so they can
  be selected. The contents and runtime behavior of the custom image remain the
  customer's responsibility.
- Accelerator association depends on GPU support, Node Feature Discovery, the
  NVIDIA GPU Operator, and a known accelerator identifier.
- Verification: dashboard table visibility and workbench creation selection.

## Unresolved Or Environment-Specific Items

- Final image registry, tag, digest, and pull-secret strategy.
  Verification: choose during active implementation and keep credentials out of
  Git.
- Whether dashboard import or GitOps ImageStream registration is the active
  demo path.
  Verification: prefer GitOps for stable desired state and document dashboard
  import as an operator runbook.
- Accelerator metadata values.
  Verification: confirm the active cluster's accelerator identifier and
  hardware profile design before using the metadata.
