# Stage 070: Developer Portal and Self-Service

## Why This Matters

Platform capabilities change day-to-day engineering behavior only when teams can find them, understand ownership, and follow a supported path to consume them. Without a portal, the AI platform remains scattered across dashboards, routes, namespaces, GitOps applications, and README files.

Stage 070 establishes Red Hat Developer Hub as the front door for the demo platform.

## Architecture

![Stage 070 layered capability map](../../docs/assets/architecture/stage-070-capability-map.svg)

## What This Stage Adds

This stage adds the developer portal foundation.

- Red Hat Developer Hub 1.9 deployed through operator-managed resources.
- Application configuration, runtime secrets, and dynamic plugin configuration managed as platform state.
- OIDC authentication through the MTA Keycloak / Red Hat build of Keycloak realm, brokered back to OpenShift OAuth.
- Developer Lightspeed for Red Hat Developer Hub.
- OpenShift launcher integration.
- Initial catalog content for demo users, teams, ownership, lifecycle, and Coolstore-related components.
- Developer Hub component entries for `getting-started-ai-coding`, `coolstore-inventory-service`, and `mca-coolstore`.
- Component-specific Dev Spaces links that open one repository per workspace.
- TechDocs publishing for the governed developer workspace guide.

The portal becomes the place to describe ownership, lifecycle, source links, documentation, and relationships around the AI-assisted development workflow.

## What To Notice And Why It Matters

Stage 070 makes platform consumption discoverable.

- Developers open Developer Hub from the OpenShift launcher and sign in through the OpenShift-backed identity chain.
- Catalog entities make ownership, lifecycle, tags, source links, and workflow docs visible.
- Component-specific Dev Spaces links route developers into the correct controlled workspace instead of asking them to assemble repository URLs manually.
- Developer Lightspeed for RHDH adds an AI-assisted portal experience without embedding unmanaged provider credentials.
- TechDocs publishes the Dev Spaces workflow guide from this repository.

This matters because regulated enterprises need a visible governance surface for ownership, access control, documentation, and self-service consumption.

## How Red Hat And Open Source Make It Work

Red Hat Developer Hub provides an enterprise developer portal based on Backstage. Backstage supplies the catalog model for components, ownership, lifecycle, systems, APIs, resources, and documentation. Red Hat packages that portal for OpenShift with operator-based deployment, supported configuration patterns, and dynamic plugin management.

In this demo, Developer Hub uses OIDC through the MTA Keycloak / Red Hat build of Keycloak realm, which brokers identity back to OpenShift OAuth. GitOps-managed catalog configuration keeps the portal reproducible rather than hand-maintained.

## Trust Boundaries

Developer Hub is a discovery and self-service surface. It should link to approved platform paths rather than embed provider secrets, kubeconfigs, or unmanaged credentials. Production identity, access, and governance decisions remain the responsibility of the organization's approved identity and platform teams.

## Red Hat Products Used

- **[Red Hat Developer Hub](https://www.redhat.com/en/technologies/cloud-computing/developer-hub)** provides the enterprise developer portal and software catalog.
- **[Developer Lightspeed for Red Hat Developer Hub](https://developers.redhat.com/products/rhdh/developer-lightspeed)** provides the assistant capability in the portal layer.
- **[Red Hat OpenShift](https://www.redhat.com/en/technologies/cloud-computing/openshift)** provides runtime, routes, console launcher integration, and OAuth identity foundation.
- **[Red Hat build of Keycloak](https://access.redhat.com/products/red-hat-build-of-keycloak)** provides the OIDC identity broker reused from MTA.

## Open Source Projects To Know

- [Backstage](https://backstage.io/) is the upstream developer portal framework behind Developer Hub.
- [Backstage Software Catalog](https://backstage.io/docs/features/software-catalog/) models components, ownership, APIs, systems, resources, and documentation.
- [TechDocs](https://backstage.io/docs/features/techdocs/) turns repository documentation into portal-hosted technical documentation.

## Next Enhancements

- Add direct Coolstore links for MTA, MaaS, and OpenShift Console.
- Add MaaS `Resource` and `API` catalog entities for private and governed external models.
- Move the demo TechDocs publisher from the local builder to external object storage before treating it as a production pattern.
- Add a Software Template for "Modernize Java EE application with MTA."
- Add OpenShift and Argo CD plugins for resource and GitOps visibility.
- Evaluate the OpenShift AI Connector after the base portal story is stable.

## Deploy And Validate

```bash
./stages/070-developer-portal-self-service/deploy.sh
./stages/070-developer-portal-self-service/validate.sh
```

Manifests: [`gitops/stages/070-developer-portal-self-service/base/`](../../gitops/stages/070-developer-portal-self-service/base/)

## References

- [Red Hat Developer Hub 1.9 documentation](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.9)
- [Red Hat Advanced Developer Suite](https://www.redhat.com/en/products/advanced-developer-suite)
- [Developer Lightspeed for Red Hat Developer Hub](https://developers.redhat.com/products/rhdh/developer-lightspeed)
- [Installing RHDH on OpenShift](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.9/html/installing_red_hat_developer_hub_on_openshift_container_platform/index)
- [Configuring RHDH](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.9/html-single/configuring_red_hat_developer_hub/index)
- [RHDH authentication](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.9/html-single/authentication_in_red_hat_developer_hub/authentication_in_red_hat_developer_hub)
- [RHDH dynamic plugins](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.9/html/installing_and_viewing_plugins_in_red_hat_developer_hub/index)

## Next Stage

This is the final implemented stage. Use [Operations](../../docs/OPERATIONS.md) for day-2 work, or extend Developer Hub with the items listed above.
