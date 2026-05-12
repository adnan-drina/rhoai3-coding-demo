# mca-coolstore Candidate Assessment

## Source

Repository assessed: <https://github.com/rhpds/mca-coolstore.git>

Inspected revision:

```text
b9f0ed2cb88726ec3b4507e887ecff79ba46bc1c
2026-04-28 18:10:29 +0200
initial commit
```

The repository was cloned locally and reviewed as a candidate main application for the planned "From Vibe Coding to Agentic Engineering" developer workflow stages.

## Summary Recommendation

Use `rhpds/mca-coolstore` as the primary brownfield modernization application for the demo, but do not make it the only application artifact for every stage.

It is a strong anchor for enterprise AI development because it has realistic Java EE modernization pressure, manual runtime setup, built-in Konveyor profiles, custom audit-library migration rules, a system-scoped local dependency, legacy frontend assets, and no automated tests. Those are exactly the kinds of constraints that make the shift from vibe coding to agentic engineering meaningful.

The best demo shape is a two-track application story:

- `mca-coolstore` is the brownfield source application for discovery, code explanation, README alignment, characterization tests, MTA analysis, Developer Lightspeed for MTA, Scribe-backed rule generation, and supply-chain review.
- A smaller demo-owned `coolstore-inventory-service` becomes the golden-path target for stages that need clean Quarkus development, OpenShift deployment, Pipelines-as-Code, GitOps, and trusted software supply-chain promotion. The repository candidate is `adnan-drina/coding-exercises`, which should be renamed to `coolstore-inventory-service` and carry source, app-local GitOps state, `.tekton/` assets, rollout notes, promotion notes, and rollback evidence in one repository for the first demo. The target-service rationale is captured in the [`Quarkus target service options`](quarkus-target-service-options.md) assessment.

This keeps the modernization story realistic without forcing a fragile full monolith conversion into the first live coding iteration.

## What The Repository Contains

The application is a Java EE 7 monolith packaged as a WAR for JBoss EAP 7.4. The README describes manual setup for PostgreSQL, Keycloak 20.0.5, JBoss EAP datasource configuration, JMS topic creation, WAR deployment, and a two-node clustering test.

Important implementation signals:

- Maven WAR project with final artifact `ROOT.war`.
- Java EE 7 APIs, EJBs, JAX-RS endpoints, JPA entities, JMS, Flyway, Keycloak configuration, and JSP/static frontend assets.
- `src/main/java` contains 30 Java source files.
- `src/test` is absent and Maven is configured with `maven.test.skip=true`.
- `src/main/webapp/bower_components` contains vendored AngularJS and PatternFly-era frontend assets.
- `lib/` contains local audit logging library JARs, while the active POM dependency uses `audit-logging-library-1.0.0.jar` through Maven `systemPath`.
- `.konveyor/profiles/` contains a Quarkus profile and an audit-logging profile with custom rules.
- The POM includes an explicit `TODO` for adding an OpenShift profile.
- There is no `devfile.yaml`, `catalog-info.yaml`, Dockerfile, Containerfile, Tekton pipeline, GitOps manifest, or OpenShift deployment artifact in this repository.

Local static check:

```text
mvn -q package
```

Result: package build completed successfully with Java 21 and Maven 3.9.10, producing `target/ROOT.war`. This is a compile/package signal only, because tests are skipped and no test sources exist.

## Why It Fits The Story

### It Creates A Real Enterprise Constraint Surface

The app is not a clean greenfield sample. It has old APIs, app-server assumptions, local dependencies, manual runtime configuration, clustering notes, JMS behavior, and legacy web assets. That gives the demo credible material for showing why enterprise engineers cannot accept broad AI rewrites without controls.

### It Already Points Toward MTA And Developer Lightspeed

The repository has Konveyor profile material in-tree, and the related `rhpds/mca-devspaces` workspace points to this repository as the Coolstore project for Developer Lightspeed for MTA. That makes it a better fit for Stage 160 than a generic sample with no modernization scaffolding.

### It Has A Concrete Custom-Rule Story

The audit-logging rules detect migration from a custom `audit-logging-library` 1.x API to a 2.x Java 21-oriented API. The production code uses `FileSystemAuditLogger` in `OrderService`, so the rule set is tied to actual source. This is a strong Scribe and OpenCode use case: generate, validate, review, and apply modernization rules under human control.

### It Supports Quality-Bar Demonstrations

The lack of tests, skipped test configuration, local system-scoped dependency, vendored frontend assets, and missing OpenShift packaging make it easy to show AI near misses:

- AI can claim deployment readiness that is not present.
- AI can produce code changes without characterization tests.
- AI can ignore local proprietary or internal JAR provenance.
- AI can propose broad Java EE to Quarkus rewrites without understanding runtime behavior.
- AI can update README text without matching implementation evidence.

Those are useful Stage 120 and Stage 130 moments.

## Main Risks

### It Is Not Yet A Fast Live Demo App

The runtime path depends on manual JBoss EAP, Keycloak, PostgreSQL, datasource, JMS, and optional clustering setup. That is appropriate for enterprise modernization, but it is too heavy for every developer-workflow stage unless we prebuild the environment.

### It Has No Automated Quality Baseline

The project currently has no test sources and skips tests at Maven level. Before using it for code updates, the first AI-assisted work should add characterization tests around small, deterministic units such as `Transformers`, cart item deduplication behavior, or service-level logic that can be isolated.

### It Is Not A Quarkus Target

The repository is a Java EE source app with a Quarkus-oriented Konveyor profile, not a ready target implementation. Stage 140 should not promise a full conversion of this monolith in one pass. It should extract or recreate a bounded Coolstore capability as a new governed Quarkus service.

### It Does Not Provide Delivery Artifacts

There are no OpenShift manifests, Tekton resources, GitOps resources, container build assets, or Developer Hub catalog metadata. Stages 100, 140, 150, and 155 need additional demo-owned artifacts.

## Fit By Demo Stage

| Stage | Fit | Assessment |
|-------|-----|------------|
| Stage 100: Governed Developer Entry Point | Partial | Good catalog candidate after we add `catalog-info.yaml`, TechDocs ownership, source links, Dev Spaces launch links, and model-use policy. |
| Stage 110: Enterprise Vibe Coding With Continue | Good | Strong for explanation, README alignment, small test generation, and code comprehension prompts. Keep tasks bounded to a class or feature slice. |
| Stage 120: Quality Bar Breakpoint | Excellent | The skipped tests, local JAR, missing OpenShift profile, manual runtime setup, and modernization complexity make it ideal for demonstrating AI near misses. |
| Stage 130: Agentic Engineering With OpenCode | Excellent | Strong candidate for `.AGENTS.md`, scoped skills, coding rules, MCP context boundaries, Scribe rule generation, and eval-driven review. |
| Stage 140: Golden Path Quarkus Service | Good with target service | Use Coolstore domain knowledge to scaffold or seed the demo-owned `coolstore-inventory-service`, but do not present the monolith as already converted. |
| Stage 150: Governed Pipeline And Deployment | Good with target service | Build pipeline and GitOps examples around `coolstore-inventory-service`; keep `mca-coolstore` as the brownfield source rather than the first deployment target. |
| Stage 155: Red Hat Trusted Software Supply Chain | Strong | The local system dependency, vendored frontend assets, custom workspace image from `mca-devspaces`, generated agent artifacts, and selected target service all create supply-chain evidence needs. |
| Stage 160: Modernization At Scale With MTA And Developer Lightspeed | Excellent | Best fit. It has Java EE modernization concerns, Konveyor profiles, custom rules, and alignment with the Developer Lightspeed Dev Spaces reference. |
| Stage 170: Agent Mesh Modernization Pattern | Good | Use it as one portfolio application coordinated by specialized modernization, testing, documentation, rule-generation, and supply-chain agents. |

## Recommended Storyline Use

### First Segment: Developer Entry And Vibe Coding

Register Coolstore as a Developer Hub catalog component and open it in Dev Spaces. Use Continue with a private or approved model to explain the application, identify runtime dependencies, and compare README claims against the POM and source tree.

Good first prompts:

```text
Explain the checkout flow from the REST endpoint to order persistence. Cite the classes involved and identify runtime services required.
```

```text
Compare the README deployment instructions with the repository contents. Identify claims that are supported by code and claims that are missing implementation artifacts.
```

```text
Generate a characterization test plan for the order JSON transformation code before proposing any modernization changes.
```

### Second Segment: Quality Bar Breakpoint

Ask for a tempting but unsafe update, such as "add OpenShift support" or "modernize the audit logger." Then show why the output needs review: tests are missing, the active audit dependency is local and system-scoped, the OpenShift profile is only a TODO, and runtime behavior crosses JMS, JPA, and EAP configuration.

This stage should create the case for moving into OpenCode with explicit rules and review gates.

### Third Segment: Agentic Engineering

Introduce OpenCode agents and project rules for Coolstore:

- inspect before changing;
- never claim live deployment without manifests and validation;
- add characterization tests before refactoring;
- treat `.konveyor` rules as code;
- use Scribe only for reviewed Konveyor rule drafts;
- document assumptions and evidence;
- avoid broad Java EE to Quarkus rewrites unless scoped to a bounded context.

This is where `mca-coolstore` is strongest as a governance demonstration.

### Fourth Segment: Golden Path Target

Use the Coolstore domain to create or extend the demo-owned `coolstore-inventory-service`, but keep the target bounded to inventory availability for Coolstore item IDs. Save cart, checkout, JMS order processing, Keycloak integration, and full frontend modernization for later iterations.

This target service should be the artifact that receives Tekton, GitOps, OpenShift, and trusted software supply-chain promotion.

### Fifth Segment: Modernization At Scale

Run MTA analysis against `mca-coolstore`, review findings, use Developer Lightspeed for MTA for selected remediations, and use Scribe to draft or validate custom rules from approved standards.

This is the clearest place to connect Red Hat MTA, Developer Lightspeed, Scribe, RAG-backed standards, eval-driven development, and AgentOps.

## Best Initial Code Examples

Use small examples first:

- Characterization tests for `Transformers.shoppingCartToJson` and `Transformers.jsonToOrder`.
- README alignment review against `README.md`, `pom.xml`, `.konveyor`, and the absence of deployment artifacts.
- Audit-library migration analysis using the existing Konveyor rules and `OrderService`.
- An OpenShift readiness review that starts from the POM `TODO` and produces a plan, not immediate deployment claims.
- A bounded Quarkus target service generated from the inventory availability domain.

Avoid first:

- full monolith-to-Quarkus rewrite;
- live EAP clustering;
- frontend modernization;
- broad dependency upgrades without provenance and regression checks.

## Candidate Scorecard

| Dimension | Score | Notes |
|-----------|-------|-------|
| Brownfield modernization anchor | 9/10 | Strong Java EE, MTA, custom-rule, and app-server modernization signals. |
| AI-assisted coding exercises | 7/10 | Good if scoped to small classes and docs; weak if treated as a fast full-stack app. |
| Agentic governance exercises | 9/10 | Excellent for project rules, tests-first constraints, MCP boundaries, and reviewed rule generation. |
| Quarkus golden-path target | 5/10 | Good domain source, but not itself a Quarkus target implementation. |
| Pipeline and deployment readiness | 6/10 | The target service branch now has `Containerfile`, `.tekton/`, and app-local GitOps review assets, but still needs live Pipelines-as-Code and deployment validation. |
| Trusted software supply chain | 8/10 | Strong evidence needs because of local JARs, vendored assets, generated rules, and future workspace images. |
| Live-demo reliability today | 5/10 | Build is easy; runtime requires manual infrastructure and product setup. |

## Recommended Project Decision

Adopt `rhpds/mca-coolstore` as the canonical brownfield modernization source for Stage 160 and as the main legacy application used in Stage 110 through Stage 130 examples.

Keep Stage 140 and Stage 150 centered on the demo-owned `coolstore-inventory-service`. Use `adnan-drina/coding-exercises` as the repository to rename and reshape into the service repository. The first-demo repository should include the Quarkus source, app-local GitOps desired state under `gitops/`, Pipelines-as-Code assets under `.tekton/`, and documented promotion and rollback evidence. The service should be testable, pipeline-ready, deployable on OpenShift, and small enough for live AI-assisted development.

This gives the demo one coherent application narrative:

```text
Discover Coolstore -> understand and test Coolstore -> catch AI near misses -> govern agents -> extract a Quarkus service -> deliver it through approved pipelines -> modernize the larger estate with MTA and agent mesh patterns.
```

## Open Questions

- Should the demo use `rhpds/mca-coolstore` exclusively, or keep `konveyor-ecosystem/coolstore` as a secondary reference for Quarkus migration examples?
- How should downstream links be updated after the GitHub repository is renamed from `coding-exercises` to `coolstore-inventory-service`?
- What additional repo layout convention should be used for rollout notes beyond the selected `gitops/`, `.tekton/`, and `docs/evidence/` paths?
- What is the minimum live runtime we need for the first demo: compile-only, unit tests, Dev Spaces only, MTA analysis only, or full EAP runtime?
- Which corporate standards document should drive the first Scribe-generated Konveyor rule?
- How should local audit JAR provenance be represented in Stage 155: SBOM finding, internal artifact promotion example, or policy failure?

## References

- [rhpds/mca-coolstore](https://github.com/rhpds/mca-coolstore)
- [rhpds/mca-devspaces](https://github.com/rhpds/mca-devspaces)
- [Quarkus target service options](quarkus-target-service-options.md)
- [coding-exercises application repository plan](coding-exercises-app-repo-plan.md)
- [Migration Toolkit for Applications](https://developers.redhat.com/products/mta)
- [Configuring and using Red Hat Developer Lightspeed for MTA](https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.1/html-single/configuring_and_using_red_hat_developer_lightspeed_for_mta/index)
- [Configuring and using rules for an MTA analysis](https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.1/html-single/configuring_and_using_rules_for_an_mta_analysis/index)
- [sshaaf/scribe](https://github.com/sshaaf/scribe)
