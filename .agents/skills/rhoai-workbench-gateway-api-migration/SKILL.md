---
name: rhoai-workbench-gateway-api-migration
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use when documenting, reviewing, or rebuilding custom workbench image
  compatibility with the Red Hat OpenShift AI Kubernetes Gateway API routing
  model: path-based routing, NB_PREFIX handling, full-prefix request paths,
  health check endpoint behavior, idle culling endpoints, relative URLs,
  framework base path configuration, NGINX reverse-proxy path translation,
  redirect prefix preservation, WebSocket proxy headers, and Gateway Controller
  no-route diagnostics. Do NOT use for dashboard import of custom workbench
  images, ImageStream registration, Notebook CR authoring, Gateway API
  installation, or generic ingress design; use the matching rhoai-* skill.
---

# RHOAI Workbench Gateway API Migration

Use this skill when custom workbench images must be made compatible with the
OpenShift AI Kubernetes Gateway API path-based routing model for the active
baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior details.
Official Red Hat documentation is product authority. This skill adapts the
official Managing resources chapter to this repo's custom workbench image
review model.

## Scope

This skill covers:

- the migration from route-host based workbench access to Gateway API
  path-based routing
- `NB_PREFIX` as the runtime prefix that workbench applications must honor
- health endpoint behavior at `/${NB_PREFIX}/api`
- idle-culling endpoints at `/${NB_PREFIX}/api/kernels` and
  `/${NB_PREFIX}/api/terminals`
- relative URL requirements for static assets and API calls
- framework base path configuration for Python and JavaScript applications
- NGINX reverse-proxy path translation when an application cannot be configured
  for a base path
- verification with browser checks, in-pod curl checks, and Gateway Controller
  log review

Use `rhoai-workbenches-custom-images` for image build and runtime compatibility
more broadly, `rhoai-workbench-image-import` for dashboard image import, and
`rhoai-dashboard-customization` for dashboard feature visibility.

## Demo Policy

For this repo:

- Treat Gateway API path compatibility as mandatory for custom workbench images
  that are expected to run on the active baseline.
- Do not accept a custom workbench image as demo-ready until the workbench page,
  static assets, API calls, health endpoint, and culling endpoints behave under
  the `NB_PREFIX` path.
- Prefer native application base-path configuration over an NGINX translation
  layer when the application framework supports it.
- Use NGINX only when the application cannot avoid absolute paths or cannot be
  configured to serve under `NB_PREFIX`.
- Keep Gateway API migration details in image build/runbook documentation, not
  step READMEs, unless a step teaches custom workbench images.

## Workflow

1. Confirm the active baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/source-capture.md` and
   `references/official-doc-extraction.md`.
3. Confirm prerequisites:
   - OpenShift version is at least 4.19.
   - OpenShift AI Operator version is at least 3.0.
   - the team can rebuild the custom workbench image.
4. Audit the workbench application for absolute paths, redirects, and static
   asset URLs that ignore `NB_PREFIX`.
5. Configure the application base path to use `NB_PREFIX`, or add an NGINX
   reverse proxy when native base-path support is not possible.
6. Implement the required health endpoint and culling endpoints under the
   prefixed path.
7. Validate with `references/validation-checklist.md`.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/gateway-api-migration-patterns.md`
