---
name: ocp-web-console
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: ocp
  docs-version: "4.22"
  skill-group: "OpenShift Platform"
description: >
  Use when reviewing or changing OpenShift web console configuration in this
  repo: the full console plugin list on consoles.operator.openshift.io/cluster
  (Stage 010 console-observability/console-plugins.yaml, Application
  010-console-observability), the COO monitoring UIPlugin, ConsoleLink
  application-menu entries for RHDH and MTA, console dashboard ConfigMaps, or
  a plugin that shows Disabled. Do NOT use for dashboard content and metrics
  (use ocp-observability) or Dev Spaces and its web IDE (use
  ocp-devspaces-admin).
---

# OCP web console

Thin skill: repo decisions and pitfalls here, product behavior in the linked
OpenShift Container Platform 4.22 sections. Detailed record:
`gitops/stages/010-openshift-ai-platform-foundation/console-observability/README.md`.

## When to use

- A stage installs an operator that ships a `ConsolePlugin`.
- A change touches `console-observability/`, a `consolelink.yaml`, or a
  ConfigMap labelled `console.openshift.io/dashboard`.
- A console plugin, menu link or dashboard is missing.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Complete `spec.plugins` list declared in Git (`monitoring-plugin`, `networking-console-plugin`, `monitoring-console-plugin`, `gitops-plugin`, `odf-console`, `kuadrant-console-plugin`, `lightspeed-console-plugin`, `pipelines-console-plugin`), owned by server-side apply on this one object, restored by self-heal; deviation from the documented append patch | `gitops/stages/010-openshift-ai-platform-foundation/console-observability/console-plugins.yaml` | [Dynamic plugins][plugins] |
| `Console/cluster` carries `ServerSideApply=true,Prune=false,Delete=false`: Git owns only `spec.plugins`, never deletes the singleton | same file | — |
| Own deploy and validate scripts for the plugin list and UIPlugin | `stages/010-openshift-ai-platform-foundation/deploy-console-observability.sh`, `stages/010-openshift-ai-platform-foundation/validate-console-observability.sh` | — |
| Perses dashboards in Observe through the COO `UIPlugin` `monitoring` | `gitops/stages/010-openshift-ai-platform-foundation/console-observability/monitoring-uiplugin.yaml` | [COO UI plugins][coo-ui] |
| Application-menu links `rhdh` and `mta`: placeholder `href` in Git, patched to the live Route by Sync hooks; `ignoreDifferences` on `href`/`imageURL` | `gitops/stages/070-advanced-app-platform/rhdh/rhdh-instance/consolelink.yaml`, `gitops/stages/070-advanced-app-platform/mta/mta-instance/consolelink.yaml` | [Customizing the web console][customize] |
| GPU dashboard as a console dashboard ConfigMap in `openshift-config-managed` | `gitops/stages/020-gpu-infrastructure-private-ai/nvidia-gpu-operator/console-dashboard/` | [About OpenShift monitoring][monitoring] |
| Not configured: console route/branding customization, quick starts, web terminal, disabling the console | — | [Configuring the web console][configure] |

## Procedure

1. Add a plugin by adding its name to `console-plugins.yaml` and publishing;
   a listed plugin whose `ConsolePlugin` is not installed yet is skipped.
2. Deploy and validate:
   `./stages/010-openshift-ai-platform-foundation/deploy-console-observability.sh`
   (also run by Stage 010 `deploy.sh`), then
   `./stages/010-openshift-ai-platform-foundation/validate-console-observability.sh`.
3. By hand, after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   oc get console.operator.openshift.io cluster -o jsonpath='{.spec.plugins}{"\n"}'
   oc get consoleplugins; oc get consolelinks
   ```

## Pitfalls

- `spec.plugins` is replaced whole by any writer; never `oc patch` it, self-heal
  reverts the patch and a rewrite elsewhere drops entries
  (`docs/TROUBLESHOOTING.md#console-plugins-disappear-from-the-web-console`).
- `validate-console-observability.sh` fails when an installed `ConsolePlugin`
  is missing from Git, so a new operator plugin needs a Git change.
- ConsoleLink `href` drift is expected (hook-patched); do not "fix" it in Git.
- `ServerSideApply=true` is allowed on the `Console` resource only;
  `.agents/rules/gitops.md` forbids it at Application level.

## Official documentation (OCP 4.22)

| Topic | Section |
|---|---|
| Overview | [Web console overview][overview] |
| Plugins | [Dynamic plugins][plugins] |
| Configure and customize | [Configuring the web console][configure], [Customizing the web console][customize] |
| Dashboards | [Using the dashboard to get cluster information][dashboards], [About OpenShift monitoring][monitoring], [COO UI plugins (COO 1-latest)][coo-ui] |
| Not used here | [Web terminal][terminal], [Quick start tutorials][quickstart], [Disabling the web console][disable] |

## Related skills

`ocp-observability`, `ocp-gitops-operator`, `rhdh-configure`, `mta-install`.

[overview]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/web_console/index#web-console-overview
[plugins]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/web_console/index#dynamic-plugins
[configure]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/web_console/index#configuring-web-console
[customize]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/web_console/index#customizing-web-console
[dashboards]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/web_console/index#using-dashboard-to-get-cluster-info
[terminal]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/web_console/index#web-terminal
[quickstart]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/web_console/index#creating-quick-start-tutorials
[disable]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/web_console/index#disabling-web-console
[monitoring]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/monitoring/index#about-ocp-monitoring
[coo-ui]: https://docs.redhat.com/en/documentation/red_hat_openshift_cluster_observability_operator/1-latest/html-single/ui_plugins_for_red_hat_openshift_cluster_observability_operator/index#monitoring-ui-plugin
