# Quarkus Target Service Options

## Purpose

This note selects the smaller Quarkus target service that should carry the rest of the "From Vibe Coding to Agentic Engineering" demo after `rhpds/mca-coolstore` establishes the brownfield modernization source.

The target service must be small enough for live AI-assisted development, but rich enough to support:

- Stage 140 golden-path Quarkus work;
- Stage 150 governed pipeline and deployment work;
- Stage 155 trusted software supply-chain evidence;
- Stage 160 comparison back to the brownfield Coolstore source.

## Summary Recommendation

Create a demo-owned `coolstore-inventory-service` as the target Quarkus service.

Use a single service repository for the first live demo. The service repository is `https://github.com/adnan-drina/coolstore-inventory-service`, with local adaptation work on branch `feature/coolstore-inventory-service-plan`. Keep Quarkus source, app-local GitOps state, `.tekton/` Pipelines-as-Code assets, rollout notes, promotion notes, and rollback evidence in that repository.

Use these sources as references, not as direct imports:

- `adnan-drina/coolstore-inventory-service` as the service repository for the target service.
- `rh-mad-workshop/coolstore-microservice/inventory` for a current public Quarkus 3 and Java 21 service shape.
- Local `coolstore-demo/inventory` for the closer Coolstore inventory domain, REST path, H2/PostgreSQL profile split, health check, metrics, tests, Dev Spaces commands, and GitOps/Tekton examples.
- `konveyor-ecosystem/coolstore` `quarkus` branch as a comparison reference for a full Quarkus migration, not as the Stage 140 target.
- `rhpds/mca-coolstore` as the brownfield source of truth for modernization context.

The target should be intentionally bounded: inventory/product availability only. It should not attempt checkout, cart state, JMS, Keycloak, frontend modernization, or full monolith conversion in the first implementation.

## Candidate Findings

| Candidate | Fit | What It Gives Us | Main Issue |
|-----------|-----|------------------|------------|
| `adnan-drina/coolstore-inventory-service` | Service repo | Existing Dev Spaces, Continue, and OpenCode workspace setup; now has the first Quarkus scaffold, `AGENTS.md`, `catalog-info.yaml`, `.tekton/`, `Containerfile`, app-local GitOps, and evidence docs on the planning branch | Still needs live PaC validation, live deployment evidence, PostgreSQL runtime binding, and supply-chain artifacts. |
| `rh-mad-workshop/coolstore-microservice/inventory` | Strong reference | Public repo, Quarkus 3.35.2, Java 21, REST, Panache, PostgreSQL, health, metrics, Jib, OpenShift extension, tests | Its model is product catalog-like rather than the original Coolstore inventory shape; local tests require Docker-backed Quarkus Dev Services or a configured datasource. |
| Local `coolstore-demo/inventory` | Strong seed | Coolstore-shaped inventory domain with `itemId`, `location`, `quantity`, `link`; H2 default profile; PostgreSQL OpenShift profile; health; metrics; tests; Dev Spaces commands; GitOps and Tekton examples | Old Quarkus 2.2.3 Red Hat build, Java 11, older OpenShift resources, private/local repository origin. |
| `konveyor-ecosystem/coolstore` `quarkus` branch | Secondary reference | Full Quarkus migration branch, Java 21, Quarkus 3.12.3, PostgreSQL and Flyway, useful for comparison against legacy monolith | Still monolith-scale, README remains legacy EAP-oriented, not small enough for Stage 140 live coding. |
| `rhpds/mca-coolstore` | Brownfield source | Java EE source app, in-tree Konveyor profiles, audit-library migration rules, realistic modernization pressure | Not a Quarkus target and not pipeline-ready. |
| Generic Quarkus tutorial apps | Weak | Clean Quarkus examples and template patterns | Not Coolstore domain-specific. |

## Validation Notes From Inspection

`rhpds/mca-coolstore`:

- `mvn -q package` passed locally on Java 21.
- No test confidence because the project has no tests and skips tests.

Local `coolstore-demo/inventory`:

- `mvn -q test` failed on Java 21 because the old Quarkus 2.2.3 stack cannot handle Java 21 class files.
- `mvn -q test` passed when run with the local Java 11 GraalVM runtime.

`rh-mad-workshop/coolstore-microservice/inventory`:

- `mvn -q package -DskipTests` passed locally on Java 21.
- `mvn -q test` failed locally because Quarkus tried to start PostgreSQL Dev Services and Docker was not available. This is a configuration issue, not a bad target shape.

`konveyor-ecosystem/coolstore` `quarkus` branch:

- `mvn -q test` and `mvn -q package -DskipTests` passed locally on Java 21.
- It remains too large for the golden-path target service.

## Proposed Target Shape

Service name:

```text
coolstore-inventory-service
```

Package:

```text
com.redhat.coolstore.inventory
```

Primary responsibility:

```text
Expose product inventory availability for Coolstore item IDs.
```

Initial endpoints:

```text
GET /api/inventory
GET /api/inventory/{itemId}
GET /api/inventory/{itemId}/availability
```

Possible second iteration endpoint:

```text
POST /api/inventory/{itemId}/reservations
```

The reservation endpoint is useful for AI-assisted development because it creates a bounded code change with real quality gates: validation, transaction handling, inventory underflow behavior, tests, documentation, and pipeline evidence.

Initial data model:

```text
InventoryItem
- id
- itemId
- location
- quantity
- link
```

Preferred test profile:

- Current scaffold: in-memory data with deterministic tests and no runtime database.
- Later persistence iteration: H2 or Dev Services configured so tests pass without a manually running database.
- Later OpenShift runtime: PostgreSQL profile using the OpenShift Developer Catalog / Red Hat PostgreSQL image path for the first demo.
- Import data aligned with `mca-coolstore` SKUs so the target service remains connected to the monolith story.

Recommended Quarkus extensions:

- REST JSON support.
- SmallRye Health.
- Micrometer Prometheus.
- Hibernate ORM with Panache and JDBC PostgreSQL only when the persistence iteration starts.
- OpenShift or Kubernetes extension only if it matches the selected deployment path.
- OpenTelemetry later, when Stage 170 AgentOps/tracing needs it.

## Why Inventory Is The Best First Slice

Inventory is the right target because it is small, concrete, and already present in both the monolith and the candidate service references.

It supports all remaining stages:

- Stage 140 can scaffold, upgrade, or extend the service under a golden-path contract.
- Stage 150 can build a compact Pipelines-as-Code path around tests, package, image, and app-local GitOps handoff.
- Stage 155 can produce SBOM, image, provenance, signing, scan, and policy evidence for one service image.
- Stage 160 can compare the target back to the brownfield source and MTA findings.

It avoids the first-iteration risks of cart/session state, JMS order processing, Keycloak login flow, full frontend modernization, and distributed transactions.

## Stage Mapping

| Stage | How The Target Service Helps |
|-------|------------------------------|
| Stage 100 | Developer Hub shows three separated entry points: `getting-started-ai-coding` for onboarding, `coolstore-inventory-service` for AI-assisted engineering, and `mca-coolstore` for modernization. Each entry opens its own single-repository Dev Spaces workspace. |
| Stage 110 | Continue can explain the legacy inventory path and compare it with the target service README, API contract, and test plan. |
| Stage 120 | The quality-bar breakpoint can show an unsafe AI-generated endpoint or docs claim, then require tests and README alignment. |
| Stage 130 | OpenCode rules can require bounded edits, approved Quarkus versions, test-first changes, and no invented deployment claims. |
| Stage 140 | The target service becomes the golden-path Quarkus exercise. |
| Stage 150 | The service is small enough for a complete Pipelines-as-Code path. |
| Stage 155 | One service image is enough to demonstrate SBOM, signing, provenance, scanning, and policy gates. |
| Stage 160 | MTA and Developer Lightspeed can show how the brownfield inventory model informs the target design. |
| Stage 170 | The service becomes one modernization output that an agent mesh pattern could coordinate with testing, docs, security, and deployment agents. |

## Implementation Strategy

### Iteration 1: Target Contract

Add documentation only:

- service contract;
- API shape;
- data model;
- approved Red Hat build of Quarkus `3.27.x` and Java 21 baseline;
- OpenShift Developer Catalog / Red Hat PostgreSQL image path for first-demo runtime persistence;
- validation commands;
- Stage 140 prompt packet;
- first Continue task for README, API, and test-plan alignment;
- first OpenCode task for the reservation endpoint.

### Iteration 2: Service Scaffold

Create the service in the `coolstore-inventory-service` repository. The repository has already been reshaped from a Python exercise workspace into the service repo.

The first implementation should include:

- Quarkus project with approved baseline;
- inventory model and REST resource;
- deterministic tests that pass without a live cluster;
- local dev profile;
- PostgreSQL runtime profile in a later persistence iteration;
- health endpoint;
- README and TechDocs-ready notes.

### Iteration 3: Agentic Extension

Use OpenCode to implement the reservation endpoint or another bounded feature. The agent should:

- produce a plan before edits;
- add or update tests first;
- implement the smallest useful change;
- update README only for implemented behavior;
- run validation.

### Iteration 4: Pipeline And Supply Chain

Generate pipeline and app-local GitOps artifacts from approved templates. The selected first packet now uses `.tekton/` Pipelines-as-Code, an app-local `Containerfile`, Buildah, the OpenShift internal registry, and app-local Kustomize state under `gitops/`. Use local `coolstore-demo/inventory-gitops` only as a historical reference:

- tests must run before image build;
- avoid legacy `DeploymentConfig` unless the demo intentionally teaches modernization of OpenShift resources;
- prefer current Tekton API versions where possible;
- add SBOM, signature, provenance, image scan, and policy evidence hooks when Stage 155 becomes executable.

## Decision Record

Recommended decision:

```text
Use a demo-owned Coolstore Inventory Quarkus service as the Stage 140-155 target, with source, app-local GitOps desired state, `.tekton/` Pipelines-as-Code assets, rollout notes, promotion notes, and rollback evidence in one service repository for the first demo.
```

Recommended repository:

```text
https://github.com/adnan-drina/coolstore-inventory-service
```

Recommended source strategy:

```text
Use `coolstore-inventory-service` as the target repository, then seed or refine the implementation from the public `rh-mad-workshop/coolstore-microservice/inventory` Quarkus 3 shape and the local `coolstore-demo/inventory` Coolstore domain shape.
```

Recommended baseline:

```text
Red Hat build of Quarkus 3.27.x with Java 21.
```

Recommended first PostgreSQL path:

```text
OpenShift Developer Catalog / Red Hat PostgreSQL image path.
```

Recommended first AI-assisted tasks:

```text
Use Continue for README, API, and test-plan alignment. Then use OpenCode for POST /api/inventory/{itemId}/reservations.
```

Recommended non-goals for the first implementation:

- full monolith conversion;
- frontend rewrite;
- cart checkout;
- JMS order processing;
- live Keycloak integration;
- native image build;
- multi-service mesh.

## Open Questions

- Which downstream documentation and Dev Spaces links still need live validation after the repository rename rollout?
- Which concrete OpenShift Developer Catalog / Red Hat PostgreSQL image parameters should the first live deployment use?
- Should Stage 140 start by upgrading the old local `coolstore-inventory` service, or scaffold a clean service that copies only the domain contract?
- Which directory convention should hold rollout notes beyond the existing `docs/evidence/` promotion and rollback records?
- Which supply-chain checks become advisory versus blocking after the first live PipelineRun?

## References

- [rhpds/mca-coolstore](https://github.com/rhpds/mca-coolstore)
- [adnan-drina/coolstore-inventory-service](https://github.com/adnan-drina/coolstore-inventory-service)
- [konveyor-ecosystem/coolstore](https://github.com/konveyor-ecosystem/coolstore)
- [rh-mad-workshop/coolstore-microservice](https://github.com/rh-mad-workshop/coolstore-microservice)
- [coolstore-inventory-service application repository plan](coolstore-inventory-service-app-repo-plan.md)
- [Red Hat build of Quarkus](https://developers.redhat.com/products/quarkus)
- [Quarkus OpenShift guide](https://quarkus.io/guides/deploying-to-openshift)
- [Red Hat OpenShift Pipelines documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/)
- [Red Hat Trusted Software Supply Chain](https://developers.redhat.com/products/trusted-software-supply-chain)
