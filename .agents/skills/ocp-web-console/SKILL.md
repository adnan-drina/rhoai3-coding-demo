---
name: ocp-web-console
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "ocp"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Platform"
description: >
  Use when documenting, reviewing, or rebuilding OpenShift Container Platform
  web console guidance from official OCP documentation: console access,
  dashboard information, user preferences, Console configuration, logout
  redirects, quick start visibility, custom branding, console links, console
  and download routes, login-page customization, external log links,
  notification banners, CLI downloads, YAML examples, perspectives, developer
  catalog customization, dynamic plugins, ConsolePlugin resources, web
  terminal, DevWorkspace behavior, disabling the web console, and quick start
  tutorial content. Do NOT use as a replacement for RHOAI dashboard behavior;
  use rhoai-dashboard-* skills. Do NOT run live console changes without the env
  safety guard and explicit approval.
---

# OCP Web Console

Use this skill to ground OpenShift web console access, administration,
customization, dynamic plugins, web terminal, and quick start guidance in the
official OpenShift Container Platform Web console guide for the active baseline
in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority. This skill covers the OpenShift
Container Platform web console and Console Operator resources; it does not
replace RHOAI dashboard skills, application UI implementation skills, or
general OpenShift authentication guidance.

## Demo Posture

For this AWS-hosted RHOAI demo:

- Use the OpenShift web console primarily for cluster visibility, guided
  operator workflows, console URL discovery, dashboard checks, and human
  validation steps.
- Keep persistent console configuration in GitOps only after verifying the
  `Console`, `ConsoleLink`, `ConsolePlugin`, `ConsoleQuickStart`, route, and
  related API shapes against the active cluster or official docs.
- Treat console customization, dynamic plugin enablement, web terminal
  installation, and disabling the console as live cluster changes that require
  the repo environment guard and explicit user approval.
- Do not confuse OpenShift console customization with RHOAI dashboard
  customization. Use `rhoai-dashboard-customization`,
  `rhoai-dashboard-applications`, and related RHOAI skills for OpenShift AI
  dashboard behavior.
- Do not claim a console quick start, plugin, or web terminal workflow exists
  until it is implemented and validated in the active environment.

## Web Console Model

Use the official docs to frame:

- **Access**: the web console is browser-accessible and can be discovered from
  installer output or with `oc whoami --show-console` on existing clusters.
- **Console workload**: the console runs as a pod and serves static assets
  needed for the web UI.
- **Dashboard**: Home > Overview gives high-level cluster details, inventory,
  status, utilization, and activity.
- **User preferences**: theme, default project, topology view, form or YAML
  editing preference, language, notifications, and default resource type are
  user-level settings.
- **Console configuration**: `console.config.openshift.io/cluster` controls
  configuration such as logout redirect, while
  `consoles.operator.openshift.io/cluster` controls operator-managed console
  behavior and customization.
- **Customization**: administrators can configure branding, links, routes,
  login page, log links, banners, CLI downloads, YAML examples, perspectives,
  and developer catalog visibility.
- **Dynamic plugins**: `ConsolePlugin` resources register runtime UI
  extensions, and cluster administrators enable plugins in the Console Operator
  configuration.
- **Web terminal**: the Web Terminal Operator provides an embedded terminal and
  installs DevWorkspace Operator as a dependency.
- **Quick starts**: quick starts are guided tutorials with tasks, steps, and
  check-your-work content available from the Help menu.

## Workflow

1. Confirm the active OpenShift baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md`.
3. Identify whether the task concerns:
   - console URL discovery or access validation
   - dashboard or user preference documentation
   - `Console` config or operator customization
   - custom branding, links, routes, login page, banners, downloads, YAML
     examples, perspectives, or developer catalog settings
   - dynamic plugin registration, proxy, CSP, or troubleshooting
   - web terminal installation, configuration, use, troubleshooting, or removal
   - disabling the web console
   - quick start tutorial authoring or visibility
4. For GitOps manifests, verify the API group and field shape before writing
   resources.
5. For live console operations, use the repo environment guard and pair this
   skill with `env-deploy-and-evaluate`, `env-troubleshoot`, or
   `env-manage-resources`.
6. Validate the output with `references/validation-checklist.md`.

## Related Skills

- Use `ocp-authentication-identity-providers` when console access depends on
  OAuth, identity provider, user, or group configuration.
- Use `ocp-ingress-gateway-routes` for general route, ingress, and TLS
  behavior outside console-specific component routes.
- Use `ocp-observability` for monitoring, metrics, logging, and cluster
  observability beyond console dashboard interpretation.
- Use `rhoai-dashboard-customization`, `rhoai-dashboard-applications`, and
  `rhoai-users-groups-access` for OpenShift AI dashboard behavior.
- Use `project-documentation-authoring` for demo README and operator-facing
  documentation content.
- Use `project-gitops-authoring` and `project-manifest-review` for manifests.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/console-review-patterns.md`
