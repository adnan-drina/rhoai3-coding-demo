---
name: rhoai-connected-applications
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use when documenting, reviewing, or operating Red Hat OpenShift AI connected
  application workflows from the Working with connected applications guide:
  viewing applications from Applications -> Explore, enabling SaaS-based
  connected applications, understanding Operator-installed application
  boundaries, finding API endpoints on Enabled tiles, removing disabled
  application tiles from the dashboard, starting and updating the Start basic
  workbench connected application, and routing basic workbench JupyterLab
  notebook, Git, and package workflows. Do NOT use for administrator dashboard
  application tile authoring or OdhApplication/OdhDashboardConfig manifests
  (use rhoai-dashboard-applications), global user/group access management (use
  rhoai-users-groups-access), project workbench lifecycle (use
  rhoai-project-workflows), general JupyterLab/code-server IDE workflows (use
  rhoai-data-science-ide-workflows), basic workbench administrator controls
  (use rhoai-basic-workbenches), or live cluster changes without the OpenShift
  safety guard.
---

# RHOAI Connected Applications

Use this skill for user-facing connected application workflows in the
OpenShift AI dashboard on the active product baseline in
`docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product workflow details.
Official Red Hat documentation is product authority. This skill adapts the
official Working with connected applications guide to this repo's demo
workflow and documentation model.

## Scope

This skill covers:

- viewing available connected applications from Applications -> Explore
- identifying when an Enable button is available on a tile
- enabling SaaS-based connected applications from the dashboard
- understanding on-cluster and Operator-installed application boundaries
- finding API endpoints and resource links on enabled application tiles
- removing tiles for applications that an administrator has already disabled
- using the Start basic workbench connected application
- selecting basic workbench images, versions, container size, accelerator
  count, and environment variables
- restarting a basic workbench to update settings
- routing basic workbench JupyterLab notebook, Git, and package workflows to
  the IDE workflow skill

Use other skills for adjacent work:

- `rhoai-dashboard-applications` for administrator-side dashboard application
  tile resources, connected application disablement, and OdhApplication or
  OdhDashboardConfig review
- `rhoai-users-groups-access` for OpenShift AI user/admin group membership
  and access permission errors
- `rhoai-project-workflows` for preferred project workbench creation,
  connections, storage, and project lifecycle
- `rhoai-data-science-ide-workflows` for JupyterLab notebook, Git, package,
  and code-server workflows
- `rhoai-basic-workbenches` for administrator-side basic workbench management,
  idle timeout, pod tolerations, and troubleshooting
- `rhoai-nvidia-gpu-accelerators` for accelerator enablement and GPU workbench
  support posture

## Demo Policy

For this repo:

- Prefer project-based workbenches for the main demo architecture because they
  organize data science work, connections, storage, models, and pipelines in a
  project boundary.
- Use Start basic workbench only for lightweight Jupyter access, imported
  notebooks with no project dependencies, or administrator-approved simple
  demos.
- Do not treat dashboard connected application tiles as proof that the backing
  application, Operator, endpoint, or credentials are installed and working.
- Do not add or remove dashboard tiles in GitOps through this skill; use
  `rhoai-dashboard-applications` for administrator-side tile manifests.
- Treat SaaS service keys and application credentials as secrets. Never commit
  them in READMEs, notebooks, scripts, or examples.
- Use endpoint URLs from Enabled tiles only after verifying the application
  actually exposes an endpoint; some applications provide resources such as
  notebook images rather than endpoint links.
- Respect namespace requirements documented on application tiles, especially
  for independent software vendor applications.
- Mark software-catalog or third-party Operator deployments as potentially
  outside full Red Hat support unless an official support statement confirms
  otherwise.
- Use accelerator selections only when accelerator support is enabled and the
  selected workbench image supports the requested accelerator type.

## Workflow

1. Confirm the active baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/source-capture.md` and
   `references/official-doc-extraction.md`.
3. Decide whether the task is:
   - connected application discovery
   - SaaS connected application enablement
   - disabled tile removal
   - API endpoint or resource link review
   - Start basic workbench access or settings update
   - JupyterLab handoff to IDE workflow guidance
4. Use `examples/connected-application-patterns.md` for focused review
   patterns.
5. For live cluster work, follow the OpenShift safety guard in `AGENTS.md`.
6. Validate with `references/validation-checklist.md`.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/connected-application-patterns.md`
