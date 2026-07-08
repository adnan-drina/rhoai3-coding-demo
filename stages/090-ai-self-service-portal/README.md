# Stage 090: AI Self-Service Portal

## Why This Matters

Platform capabilities change day-to-day engineering behavior only when teams can find them, understand ownership, and follow a supported path to consume them. Without a portal, the AI platform remains scattered across dashboards, routes, namespaces, GitOps applications, and README files.

Stage 090 establishes Red Hat Developer Hub as the front door for the demo platform.

## Architecture

![Stage 090 layered capability map](../../docs/assets/architecture/stage-090-capability-map.svg)

## What This Stage Adds

This stage adds the developer portal foundation.

- Red Hat Developer Hub 1.9 deployed through the RHDH operator (channel `fast-1.9`).
- OIDC authentication through the Stage 070 MTA Keycloak / Red Hat build of Keycloak realm (`mta`), with client `rhdh` and `signInPage: oidc` — brokered back to OpenShift OAuth.
- Runtime catalog generated from the Git-tracked template by a Sync hook Job (`generate-rhdh-catalog.yaml`), with cluster-specific Dev Spaces links resolved at deploy time.
- Catalog entities: users (`ai-admin`, `ai-developer`), group (`ai-modernization-team`), system (`coolstore`), components (`getting-started-ai-coding`, `coolstore` titled "MCA Coolstore", `coolstore-inventory-service`), and a `maas-private-code-model-nemotron` resource.
- Component-specific Dev Spaces links that open one repository per workspace (getting-started-ai-coding, mca-coolstore via `rhpds/mca-coolstore`, coolstore-inventory-service).
- TechDocs publishing for the governed developer workspace guide (`builder: local`, `publisher: local`).
- Application configuration and dynamic plugin configuration managed as platform state; runtime secrets (`SESSION_SECRET`, `RHDH_OIDC_CLIENT_SECRET`, `RHDH_BASE_URL`, `RHBK_METADATA_URL`, `RHDH_CATALOG_URL`) patched by a PostSync Job.
- OpenShift ConsoleLink for the launcher menu.

## What To Notice And Why It Matters

Stage 090 makes platform consumption discoverable.

- Developers open Developer Hub from the OpenShift launcher and sign in through the OpenShift-backed identity chain (OpenShift OAuth brokered through RHBK).
- Catalog entities make ownership, lifecycle, tags, source links, and workflow docs visible — the catalog entity name is `coolstore` (title "MCA Coolstore"), matching the `rhpds/mca-coolstore` repository used by Stage 050 Dev Spaces links.
- Component-specific Dev Spaces links route developers into the correct controlled workspace instead of asking them to assemble repository URLs manually.
- TechDocs publishes the Dev Spaces workflow guide from this repository. The local builder and publisher pattern is sufficient for demos; production use needs external object storage for the publisher.

This matters because regulated enterprises need a visible governance surface for ownership, access control, documentation, and self-service consumption.

## How Red Hat And Open Source Make It Work

Red Hat Developer Hub provides an enterprise developer portal based on Backstage. Backstage supplies the catalog model for components, ownership, lifecycle, systems, APIs, resources, and documentation. Red Hat packages that portal for OpenShift with operator-based deployment, supported configuration patterns, and dynamic plugin management.

In this demo, Developer Hub uses OIDC through the MTA Keycloak / Red Hat build of Keycloak realm, which brokers identity back to OpenShift OAuth. The catalog is not static — a Sync hook Job fetches the Git-tracked template, resolves Dev Spaces and TechDocs placeholders with cluster-specific URLs, and writes the result to a runtime ConfigMap mounted into the RHDH pod. A PostSync Job then discovers routes, creates the OIDC client in RHBK, generates session secrets, patches the `rhdh-secrets` Secret, and restarts the deployment. Stage 070 MTA/RHBK must be healthy before the PostSync OIDC configuration can succeed.

Dynamic plugins are configured via a `dynamic-plugins-rhdh` ConfigMap. In this base deployment, only default plugins are included (`plugins: []`); additional plugins (OpenShift, ArgoCD, TechDocs) are tracked for a future phase.

## Trust Boundaries

Developer Hub is a discovery and self-service surface. It should link to approved platform paths rather than embed provider secrets, kubeconfigs, or unmanaged credentials. Production identity, access, and governance decisions remain the responsibility of the organization's approved identity and platform teams.

The OIDC client secret and session secret are generated at deploy time and stored in the `rhdh-secrets` Kubernetes Secret — they are not committed to Git.

## Red Hat Products Used

- **[Red Hat Developer Hub](https://www.redhat.com/en/technologies/cloud-computing/developer-hub)** provides the enterprise developer portal and software catalog.
- **[Red Hat OpenShift](https://www.redhat.com/en/technologies/cloud-computing/openshift)** provides runtime, routes, console launcher integration, and OAuth identity foundation.
- **[Red Hat build of Keycloak](https://access.redhat.com/products/red-hat-build-of-keycloak)** provides the OIDC identity broker reused from Stage 070 MTA (realm `mta`, client `rhdh`).

## Open Source Projects To Know

- [Backstage](https://backstage.io/) is the upstream developer portal framework behind Developer Hub.
- [Backstage Software Catalog](https://backstage.io/docs/features/software-catalog/) models components, ownership, APIs, systems, resources, and documentation.
- [TechDocs](https://backstage.io/docs/features/techdocs/) turns repository documentation into portal-hosted technical documentation.

## Next Enhancements

- Add direct Coolstore links for MTA, MaaS, and OpenShift Console.
- Add MaaS `Resource` and `API` catalog entities for private and governed external models.
- Configure Developer Lightspeed for Red Hat Developer Hub (not yet implemented — `dynamic-plugins.yaml` has `plugins: []`).
- Move the demo TechDocs publisher from the local builder to external object storage before treating it as a production pattern.
- Add a Software Template for "Modernize Java EE application with MTA."
- Add OpenShift and Argo CD plugins for resource and GitOps visibility.
- Evaluate the OpenShift AI Connector after the base portal story is stable.

## Demo Script

### Part 1 — Everything discoverable, one identity

**Know.** Coolstore now runs a governed AI development platform — but a platform nobody can find is shelf-ware. Developer Hub is where the whole arc becomes one self-service surface: catalog, docs, workspaces, and AI assistance behind a single OpenShift-federated login.

**Show.**
- Open Developer Hub from the console launcher; sign in with OpenShift (the OIDC chain runs through the same Keycloak as MTA — one identity, end to end).
- Open the catalog: the demo components (`getting-started-ai-coding`, `coolstore-inventory-service`, `coolstore` / "MCA Coolstore") with ownership, lifecycle, source links.
- Click a component's Dev Spaces link: "one click from catalog entry to the exact governed workspace we used in Stages 050 and 060 — no assembling repository URLs, no tribal knowledge."
- Open TechDocs for the developer workspace guide: the platform documents itself where developers already are.

### Part 2 — The arc, wrapped

**Know.** Each stage of this demo added one layer: private models, governed access, assisted coding, agentic development, autonomous migration, trusted delivery. The portal is where a new team member experiences all of it as one product.

**Show.** Walk the stage tiles backwards from the catalog: workspace, AI-assisted change, skills-guided agent, migration evidence, pipeline readiness — "every capability you saw today is discoverable, documented, and reachable from this page. That is the difference between a pile of AI tools and an AI development platform."

(Upgrade tracked in BACKLOG: RHDH software templates for self-service scaffolding of components + governed workspaces, per showroom module 4.)

## Deploy And Validate

```bash
./stages/090-ai-self-service-portal/deploy.sh
./stages/090-ai-self-service-portal/validate.sh
```

Manifests: [`gitops/stages/090-ai-self-service-portal/base/`](../../gitops/stages/090-ai-self-service-portal/base/)

Flow dependency: Stage 070 (Autonomous Application Migration). Stage 070 MTA/RHBK must be healthy before the PostSync OIDC client configuration can succeed.

## References

| Topic | Link |
|-------|------|
| Red Hat Developer Hub 1.9 documentation | https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.9 |
| Red Hat Advanced Developer Suite | https://www.redhat.com/en/products/advanced-developer-suite |
| Installing RHDH on OpenShift | https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.9/html/installing_red_hat_developer_hub_on_openshift_container_platform/index |
| Configuring RHDH | https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.9/html-single/configuring_red_hat_developer_hub/index |
| RHDH authentication | https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.9/html-single/authentication_in_red_hat_developer_hub/authentication_in_red_hat_developer_hub |
| RHDH dynamic plugins | https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.9/html/installing_and_viewing_plugins_in_red_hat_developer_hub/index |

## Next Stage

This is the final implemented stage. Use [Operations](../../docs/OPERATIONS.md) for day-2 work, or extend Developer Hub with the items listed in Next Enhancements.
