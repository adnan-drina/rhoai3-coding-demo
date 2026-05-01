# Step 06: Red Hat Developer Hub As The Self-Service Portal

## Why This Matters

A trusted AI platform is only useful if developers can find and consume it. Without a portal, platform capabilities remain scattered across dashboards, routes, namespaces, and documentation.

This step shows the role of Red Hat Developer Hub: it becomes the front door for the platform. Developers should be able to discover the application they own, understand its lifecycle, find modernization context, and follow trusted paths to the tools and models approved by the platform team.

## What This Step Adds

Step 06 adds the portal layer:

```text
Developer portal layer
+-- Red Hat Developer Hub Operator
+-- Backstage CR
+-- app-config-rhdh ConfigMap
+-- dynamic plugins ConfigMap
+-- runtime secrets
+-- OIDC client in MTA Keycloak / RHBK
+-- ConsoleLink in the OpenShift launcher
+-- initial catalog content
```

The first catalog entry is `coolstore`, the legacy Java EE application used in the modernization workflow. The catalog also includes the demo users and team ownership model.

## What To Notice In The Demo

Show the portal as the place where the story comes together:

1. Open Developer Hub from the OpenShift launcher.
2. Sign in through the OIDC flow backed by MTA Keycloak and OpenShift OAuth.
3. Search for `coolstore`.
4. Explain ownership, lifecycle, tags, and source links.
5. Connect the catalog entry back to the previous steps: workspaces, models, MTA analysis, and modernization.

For the current implementation, present Developer Hub as the portal foundation. The next demo increment is to add direct links, model entities, TechDocs, and a software template so the portal becomes the primary handoff point for the full workflow.

## How Red Hat And Open Source Make It Work

Red Hat Developer Hub provides an enterprise-supported developer portal based on Backstage. The software catalog gives teams a place to describe applications, ownership, lifecycle, documentation, APIs, and platform relationships.

In this demo, Developer Hub authenticates through OIDC against the MTA Keycloak / RHBK realm, which already brokers identity from OpenShift OAuth:

```text
Developer Hub
  -> MTA Keycloak / RHBK
  -> OpenShift OAuth
  -> demo HTPasswd users
```

That identity chain reinforces the platform story: the same OpenShift-backed identity can be used across RHOAI, Dev Spaces, MTA, and Developer Hub.

## Red Hat Products Used

- **Red Hat Developer Hub 1.9** provides the enterprise developer portal and software catalog.
- **Red Hat OpenShift** provides the runtime platform, route, console launcher integration, and OAuth identity foundation.
- **Red Hat build of Keycloak** is reused as the OIDC identity broker through the MTA realm.
- **Red Hat OpenShift AI**, **Dev Spaces**, and **MTA** are the platform capabilities that Developer Hub is intended to make discoverable.

## Open Source Projects To Know

- [Backstage](https://backstage.io/) is the upstream developer portal framework behind Red Hat Developer Hub.
- The [Backstage Software Catalog](https://backstage.io/docs/features/software-catalog/) provides the model for describing components, ownership, APIs, systems, resources, and documentation.
- [TechDocs](https://backstage.io/docs/features/techdocs/) can turn repository documentation into portal-hosted technical documentation.

## Why This Is Worth Knowing

Developer portals are where platform engineering becomes usable. The previous steps create powerful capabilities, but developers should not need to understand every operator, CRD, route, and secret to start work.

Developer Hub is the natural place to publish:

- Application ownership and lifecycle.
- Approved model endpoints and AI APIs.
- Modernization runbooks.
- Golden paths such as "Modernize Java EE application with MTA."
- Links to Dev Spaces, MTA analysis, GitOps status, and OpenShift resources.

This turns the AI platform from a set of components into a self-service developer experience.

## Where This Fits In The Full Platform

| Platform capability | Developer Hub role |
|---------------------|--------------------|
| Coolstore modernization | Catalog entry provides ownership, lifecycle, and source context |
| Dev Spaces | Future catalog link or template can launch the developer workspace |
| MTA | Future catalog link or template can direct users to analysis and remediation workflows |
| MaaS models | Future Resource/API entities can show approved private and external model endpoints |
| GitOps | Future Argo CD plugin integration can show deployment state |

## Next Enhancements

- Add direct Coolstore links for Dev Spaces, MTA, MaaS, and OpenShift Console.
- Add MaaS `Resource` and `API` catalog entities for private and governed external models.
- Add TechDocs for the Coolstore modernization runbook.
- Add a Software Template for "Modernize Java EE application with MTA."
- Add OpenShift and Argo CD plugins for resource and GitOps visibility.
- Evaluate the OpenShift AI Connector once the base portal story is stable.

## Deploy And Validate

Operational commands are kept here for workshop operators.

```bash
./steps/step-06-developer-hub/deploy.sh
./steps/step-06-developer-hub/validate.sh
```

Manifests: [`gitops/step-06-developer-hub/base/`](../../gitops/step-06-developer-hub/base/)

## References

- [Red Hat Developer Hub 1.9 documentation](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.9)
- [Installing RHDH on OpenShift](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.9/html/installing_red_hat_developer_hub_on_openshift_container_platform/index)
- [Configuring RHDH](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.9/html-single/configuring_red_hat_developer_hub/index)
- [RHDH authentication](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.9/html-single/authentication_in_red_hat_developer_hub/authentication_in_red_hat_developer_hub)
- [RHDH dynamic plugins](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.9/html/installing_and_viewing_plugins_in_red_hat_developer_hub/index)

## Next Step

This is the final implemented step. Use [Operations](../../docs/OPERATIONS.md) for day-2 work, or extend Developer Hub with the future catalog, TechDocs, and template items listed above.
