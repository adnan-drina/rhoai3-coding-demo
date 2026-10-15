---
name: rhoai-dashboard-applications
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when an administrator wants to add an application tile with an
  OdhApplication, stop users from adding applications (enablement), hide
  application info panels or support badges (disableInfo, disableISVBadges),
  hide the default basic workbench tile (notebookController.enabled), or
  disable a connected application in this demo. Do NOT use for the user-facing
  Applications > Enabled flow (use rhoai-connected-applications), other
  dashboard feature flags (use rhoai-dashboard-customization), or custom
  workbench images (use rhoai-workbench-image-import).
---

# RHOAI dashboard applications

Thin skill: administrator control of dashboard application tiles. Not
customized in this demo: no `OdhApplication` is in Git and the tile options
keep their documented defaults. Product behavior is in the linked OpenShift AI
3.5 sections.

## When to use

- A request to add, hide or remove a tile on the dashboard Applications page.
- The Start basic workbench tile should disappear for a demo.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| No `OdhApplication` (`dashboard.opendatahub.io/v1`) objects in Git; only product-provided tiles appear | none under `gitops/` | [Add an application to the dashboard][add] |
| `enablement`, `disableInfo` and `disableISVBadges` are not set, so they keep their defaults | `gitops/stages/010-openshift-ai-platform-foundation/010-rhoai-platform/odhdashboardconfig.yaml` (fields absent) | [Prevent users from adding applications][prevent], [Show or hide information][info] |
| `spec.notebookController` is not set; the basic workbench tile stays, because DSC `workbenches` is `Managed` and personas use workbenches in `demo-sandbox` | same file; `gitops/stages/010-openshift-ai-platform-foundation/010-rhoai-platform/datasciencecluster.yaml` | [Hide the default basic workbench application][hide-wb] |

## Procedure

If a tile change is needed:

1. Add the field to `odhdashboardconfig.yaml` (owned by `010-rhoai-platform`)
   or put a new `OdhApplication` manifest in the component that delivers the
   application, in `redhat-ods-applications`. Read the schema first:
   `oc explain odhapplication.spec` after the OpenShift safety guard in `AGENTS.md`.
2. Add a tile only for a capability the demo deploys and validates.
3. Record the choice in the owning component README and validate the stage
   (`./stages/010-openshift-ai-platform-foundation/validate.sh` for Stage 010).
4. Read-only check:

   ```bash
   oc get odhapplications -n redhat-ods-applications
   oc get odhdashboardconfig odh-dashboard-config -n redhat-ods-applications \
     -o jsonpath='{.spec.notebookController}{"\n"}'
   ```

## Pitfalls

- Disabling a connected application means uninstalling its Operator
  ([Disable applications connected to OpenShift AI][disable]); that is
  destructive here because GitOps owns the Subscriptions. Ask first and remove
  it through Git.
- Hiding the basic workbench tile does not remove workbenches; DSC
  `workbenches` still controls the component.

## Official documentation (OpenShift AI 3.5)

| Topic | Section |
|---|---|
| Chapter | [Manage applications that show in the dashboard][chapter] |
| Tiles | [Add an application][add], [Prevent users from adding applications][prevent] |
| Visibility | [Show or hide information about available applications][info], [Hide the default basic workbench application][hide-wb] |
| Connected applications | [Disable applications connected to OpenShift AI][disable] |
| Field defaults | [Dashboard configuration options][options] |

## Related skills

`rhoai-connected-applications`, `rhoai-dashboard-customization`,
`rhoai-basic-workbenches`, `rhoai-workbench-image-import`.

[chapter]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#managing-applications-that-show-in-the-dashboard
[add]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#adding-an-application-to-the-dashboard_dashboard
[prevent]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#preventing-users-from-adding-applications-to-the-dashboard_dashboard
[disable]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#disabling-applications-connected_dashboard
[info]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#showing-hiding-information-about-available-applications_dashboard
[hide-wb]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#hiding-the-default-basic-workbench-application_dashboard
[options]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_resources/index#ref-dashboard-configuration-options_dashboard
