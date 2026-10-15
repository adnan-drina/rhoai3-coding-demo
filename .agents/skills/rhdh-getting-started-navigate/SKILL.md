---
name: rhdh-getting-started-navigate
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhdh
  docs-version: "1.10"
  skill-group: "Developer Hub"
description: >
  Use when guiding a developer or presenter through this demo's Developer
  Hub on day one: signing in through the Keycloak platform realm as
  ai-developer or ai-admin, the global header and its application links,
  finding coolstore-inventory-service, running the "New Quarkus app" or
  "Application migration" template, reading TechDocs, and what the portal does
  not offer here (Developer Lightspeed chat, Extensions installs). Do NOT use
  for installing or configuring the instance (use
  rhdh-getting-started-setup).
---

# RHDH getting started: navigate

Thin skill: what a user finds in this portal; generic navigation is in the
linked Developer Hub 1.10 sections. Detailed record:
`gitops/stages/070-advanced-app-platform/rhdh/README.md` and the Stage 070
README `stages/070-advanced-app-platform/README.md`.

## When to use

- Preparing or giving the Stage 070 portal walkthrough, or the entry steps of
  Stages 110–130.
- A user cannot sign in, cannot see an entity, or cannot run a template.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Sign-in only through OIDC (`signInPage: oidc`) to Keycloak realm `platform`; no guest | `gitops/stages/070-advanced-app-platform/rhdh/rhdh-instance/app-config-configmap.yaml` | [Log in to RHDH][login] |
| Two personas: `ai-admin` (RBAC policy admin) and `ai-developer` (`role:default/developer`) | `rhdh/catalog/all.yaml`, `rhdh/rhdh-instance/rbac-policy.yaml` | [Log in and verify your profile][profile] |
| Portal title "RHOAI Coding Demo Portal"; the global header is declared explicitly (full default header kept) | `app-config-configmap.yaml` (`app.title`, `dynamicPlugins.frontend` global header) | [Using the global header][header] |
| Catalog scope: one Component `coolstore-inventory-service`, API `inventory-api`, System `coolstore`, Resource `maas-private-code-model-qwen`, two templates | `rhdh/catalog/all.yaml` | [Find software components][find] |
| Templates: `agentic-quarkus-scaffold` ("New Quarkus app") and `app-migration` ("Application migration") | `rhdh/templates/` | [Create a component from a template][template] |
| Developer Lightspeed chat is not configured (recorded Gap); the AI help chapters do not apply | `rhdh/README.md` (Alignment) | [AI-assisted help][ai] |
| The portal is reached from the OpenShift application menu (ConsoleLink `rhdh`) | `rhdh/rhdh-instance/consolelink.yaml` | — |

## Procedure

1. Open the portal from the OpenShift console application menu, sign in as
   `ai-developer`, check the profile shows `user:default/ai-developer`.
2. Catalog: filter by kind Component, open `coolstore-inventory-service`; the
   Docs, Topology, CI and Argo CD tabs come from the plugins
   (`rhdh-dynamic-plugins-usage`).
3. Create: choose a template; inputs, refusals and the created workspace are
   described in the template files and `rhdh/templates/app-migration/delivery-path.md`.
4. If something is missing, check read-only after the OpenShift safety guard
   in `AGENTS.md`:

   ```bash
   oc get route -n rhdh
   oc get consolelink rhdh -o jsonpath='{.spec.href}{"\n"}'
   ```

## Pitfalls

- 504 on sign-in after a cluster resume: restart the portal
  (`docs/TROUBLESHOOTING.md#red-hat-developer-hub-oidc-sign-in-fails-with-504-gateway-timeout`).
- A user who is not a catalog User entity cannot sign in (static entities,
  `preferredUsernameMatchingUserEntityName` resolver).
- `ai-developer` cannot register or delete entities; that is intended
  (`rhdh-develop`).
- Coolstore missing from the catalog:
  `docs/TROUBLESHOOTING.md#red-hat-developer-hub-catalog-does-not-load-coolstore`.

## Official documentation (Developer Hub 1.10)

| Topic | Section |
|---|---|
| Onboarding | [Onboarding workflow][onboarding] |
| Sign-in and interface | [Log in to RHDH][login], [Navigate the interface][interface], [Global header][header] |
| Catalog and APIs | [Find software components][find], [Verify API contracts][api] |
| Templates | [Create a component from a template][template] |
| TechDocs and search | [Search TechDocs][techdocs], [Find resources using search][search] |
| AI help (not configured) | [AI-assisted help][ai] |
| Extensions, settings, starred items | [Extensions][extensions], [Interface settings][settings], [Starred items][starred] |

## Related skills

`rhdh-getting-started-setup`, `rhdh-develop`, `rhdh-dynamic-plugins-usage`,
`rhdh-techdocs-manage`, `rhdh-authentication`, `rhdh-developer-lightspeed`.

[onboarding]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/navigate_red_hat_developer_hub_on_your_first_day/index#overview-of-the-onboarding-workflow_purpose-and-structure-of-rhdh
[profile]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/navigate_red_hat_developer_hub_on_your_first_day/index#log-in-and-verify-your-profile
[login]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/navigate_red_hat_developer_hub_on_your_first_day/index#log-in-to-rhdh_purpose-and-structure-of-rhdh
[interface]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/navigate_red_hat_developer_hub_on_your_first_day/index#navigate-the-rhdh-interface_log-in-to-rhdh
[header]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/navigate_red_hat_developer_hub_on_your_first_day/index#using-the-global-header
[find]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/navigate_red_hat_developer_hub_on_your_first_day/index#find-software-components-to-discover-assets_purpose-and-structure-of-rhdh
[api]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/navigate_red_hat_developer_hub_on_your_first_day/index#verify-api-contracts-before-integrating-with-backend-services_search-for-relevant-content-in-technical-documentation-techdocs
[template]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/navigate_red_hat_developer_hub_on_your_first_day/index#create-a-software-component-using-software-templates_import-and-use-an-existing-software-template-for-faster-development
[techdocs]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/navigate_red_hat_developer_hub_on_your_first_day/index#search-for-relevant-content-in-technical-documentation-techdocs_import-and-use-an-existing-software-template-for-faster-development
[search]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/navigate_red_hat_developer_hub_on_your_first_day/index#find-resources-and-documentation-using-search_verify-api-contracts-before-integrating-with-backend-services
[ai]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/navigate_red_hat_developer_hub_on_your_first_day/index#get-ai-assisted-help-for-your-development-tasks_find-resources-and-documentation-using-search
[extensions]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/navigate_red_hat_developer_hub_on_your_first_day/index#integrate-and-customize-your-daily-tools-using-extensions_get-ai-assisted-help-for-your-development-tasks
[settings]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/navigate_red_hat_developer_hub_on_your_first_day/index#customize-your-rhdh-interface-settings_get-ai-assisted-help-for-your-development-tasks
[starred]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/navigate_red_hat_developer_hub_on_your_first_day/index#manage-starred-items-for-quick-access_customize-your-rhdh-interface-settings
