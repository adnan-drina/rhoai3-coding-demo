# Stage 100: Vibe Coding - Developer Onboarding With Continue

## Status

This is a planned developer workflow stage. It is not part of [`../../flows/default.yaml`](../../flows/default.yaml) and does not include deploy scripts, validate scripts, GitOps manifests, or an Argo CD Application.

Live rehearsal uses the implemented Stage 070 Dev Spaces assets and Stage 090 Developer Hub assets.

## Why This Matters

The developer workflow should start from the platform, not from personal tools, copied API keys, and undocumented model choices. This stage shows the first user-facing path after the platform is installed: Developer Hub for discovery, Dev Spaces for the workspace, MaaS for governed model access, and Continue for IDE assistance.

In this demo, "vibe coding" means human-led, prompt-driven IDE work. The developer explains intent in natural language, reviews the output, runs validation, records evidence, and remains accountable for the result.

Stage 100 is intentionally small. It proves the governed entry point and the first useful Continue workflow before introducing reusable skills, OpenCode agents, or multi-file autonomous work. The former Stage 110 spec and README-alignment placeholder has been merged into this stage as review discipline for responsible vibe coding, not as a separate implementation stage.

## What This Stage Adds

This planned stage adds the first developer onboarding exercise.

- A Developer Hub entry point for `getting-started-ai-coding`, `coolstore-inventory-service`, and `mca-coolstore`.
- Single-repository Dev Spaces links for each component.
- Continue validation against `nemotron-3-nano-30b-a3b` through MaaS.
- A safe opening prompt that confirms repository, model, and read-only platform context without printing secrets.
- A one-shot Red Hat build of Quarkus Hello World exercise to demonstrate the limits and value of prompt-driven work.
- Bounded Continue prompts for explanation, gap-listing, test ideas, README/API alignment, and documentation drafting.
- A Code-to-Docs style review pattern where the assistant proposes documentation changes and the developer explicitly accepts or rejects them.
- Human review gates for generated code, tests, documentation, dependencies, and model-boundary evidence.
- Sanitized evidence expectations for model path, validation, and blockers.

## Platform Capabilities Consumed

- Stage 040 provides governed MaaS access.
- Stage 050 can provide approved external models for non-sensitive tasks when policy allows.
- Stage 060 provides MCP context integration.
- Stage 070 provides Dev Spaces with Continue and OpenCode tooling.
- Stage 090 provides Developer Hub as the portal and catalog entry point.

## Developer Workflow

The developer signs in as `ai-developer`, opens Red Hat Developer Hub, selects the relevant component, and opens its Dev Spaces link.

Expected component and repository mapping:

| Component | Repository | Use |
|-----------|------------|-----|
| `getting-started-ai-coding` | `adnan-drina/getting-started-ai-coding` | Stage 100 onboarding and MaaS client checks |
| `coolstore-inventory-service` | `adnan-drina/coolstore-inventory-service` | Future engineering workflow stages tracked in the backlog |
| `mca-coolstore` | `rhpds/mca-coolstore` | Future modernization workflow stages tracked in the backlog |

The onboarding workspace should contain only `getting-started-ai-coding`. Continue configuration is rendered from the Stage 070 MaaS API key Secret into `~/.continue/config.yaml`. Do not edit committed templates with real routes or keys.

Detailed user steps are in [`../../docs/DEVELOPER_WORKSPACE_GUIDE.md`](../../docs/DEVELOPER_WORKSPACE_GUIDE.md). Validation expectations are in [`../../docs/techdocs/stage-100-validation.md`](../../docs/techdocs/stage-100-validation.md).

## Opening Continue Prompt

Use this prompt first. It proves Continue can reach the governed model path and use safe local and read-only platform context.

```text
Explore this repository, the configured LLM, and the connected environment.

Return exactly four bullets:
- Model: the configured model ID.
- Model access: the governed access layer used by the configured model path.
- Project: the repository name and a short description from the README file.
- Platform: the namespace or cluster context visible through tools.

Do not change cluster state. Do not print sensitive information, concrete
endpoint URLs, API keys, tokens, source code, credentials, private hostnames, or
full environment variables. If any check cannot be verified, say "not verified"
for that bullet.
```

Record only the client, selected model ID, pass/fail result, and blocker.

## Bounded Continue Tasks

After the opening check passes, Continue can be used for short IDE-assistance tasks before or after the Quarkus one-shot exercise. Keep each request small enough to review, and ask for gaps or a plan before accepting edits.

Useful tasks from the retired Stage 110 placeholder now belong here:

- explain a service or endpoint in terms of inputs, outputs, dependencies, and observable behavior;
- identify the safest small behavior to test first;
- propose a unit or integration test using project conventions;
- compare README, API notes, tests, and implementation;
- produce a README-vs-code or spec-vs-code gap list before editing documentation;
- draft documentation only for behavior visible in implementation, tests, or an accepted spec.

Recommended starter prompts:

```text
Explain this service in terms of inputs, outputs, dependencies, and the safest small behavior to test first. Do not edit files.
```

```text
Review the README, API description, and tests. List gaps between documented behavior, implemented behavior, and missing verification. Do not rewrite files yet.
```

```text
Write a unit or integration test for this endpoint using the conventions already present in the project. Explain the behavior the test proves.
```

```text
Draft documentation for this endpoint. Include only behavior that is visible in the implementation or tests.
```

Expected developer actions:

- select the source file, test file, or README section intentionally;
- ask Continue for a plan before accepting code or documentation changes;
- review the generated diff;
- run validation outside Continue when shell evidence is needed;
- accept documentation changes only after the gap list is reviewed;
- record model name, task type, prompt summary, files changed, validation result, and rejected suggestions.

Review and quality gates:

- generated tests must compile and pass in the selected project;
- documentation changes must start as proposed gaps, not silent rewrites;
- documentation updates must match implemented behavior, tests, or an accepted spec;
- no unsupported dependency or version change is accepted without review;
- no credentials, keys, private URLs, or full environment variables are introduced;
- the developer owns the final diff and can explain it without relying on the assistant transcript.

Source-code prompts should use the private model path unless the organization explicitly approves the data classification for external processing. MaaS centralizes access to private and approved external models, but it does not make provider-side processing private.

## One-Shot Quarkus Vibe Coding Prompt

After the opening check passes, use this exercise to demonstrate a strong but still prompt-driven workflow. Continue Agent mode in Dev Spaces can write files, but remote terminal execution is not reliable enough to use as evidence for this exercise. The assistant must create files only and report a concise summary.

Latest findings from testing:

- Red Hat build of Quarkus artifacts must resolve from the Red Hat GA Maven
  repository.
- Do not use Maven repository id `central` for the Red Hat GA repository. Use
  `red-hat-enterprise-maven-repository`.
- Java 21 must be active in the `tooling-container`.
- The generated POM must set the Maven compiler release to 21; Java 21 on the
  PATH is not enough if Maven still compiles with source/target 8.
- For this throwaway exercise, keep Maven repository configuration in `pom.xml`
  and do not generate `.mvn/settings.xml`; that avoids malformed local settings
  while keeping the demo self-contained.
- The OpenShift deploy command and generated application configuration must pin
  the intended namespace explicitly because Dev Spaces can leave the `oc`
  context and in-cluster build client on the workspace namespace.
- The generated application configuration must include route exposure. If
  `src/main/resources/application.properties` is missing, no Route is generated.
- A "Files Created" list is not evidence by itself. The generated project must
  contain the source, test, resources, and POM files on disk before validation.
- The OpenShift Route should use edge TLS termination and allow insecure HTTP
  traffic, so the same route host can be tested with both HTTP and HTTPS.
- The Route insecure edge termination policy lives at
  `.spec.tls.insecureEdgeTerminationPolicy`. The JSONPath
  `.spec.insecureEdgeTerminationPolicy` is wrong.
- Do not rely on `oc project` or the current Kubernetes context for deployment
  targeting. The Maven command and application properties must both select the
  `hello-quarkus-vibe` namespace.
- Validation and cleanup commands are kept outside the one-shot prompt. The
  assistant should only create files and report a concise summary.
- The one-shot prompt does not ask for terminal work. The assistant must not
  try to run commands or claim command output.

Prompt engineering in this demo:

Red Hat's prompt-pattern guidance describes prompt engineering as the practice
of designing instructions that guide a language model toward accurate,
relevant, and contextual output. That matters here because the model does not
understand Red Hat build of Quarkus, Maven repositories, OpenShift deployment,
or enterprise source-code boundaries the way an engineer does. The prompt must
carry enough product facts, constraints, and acceptance criteria for the model
to produce something reviewable.

The prompt also demonstrates the tradeoff between big and small prompts. A
single large prompt is easier to run live and is useful for Stage 100 vibe coding: one
request can create a small app and explain assumptions. Validation stays
outside the prompt because this Continue workflow does not provide reliable
terminal evidence. The downside is that a big prompt costs more context, can
drift, and still needs review. Later stages move this same intent into specs,
skills, and agents so the work can be split into smaller, more focused,
repeatable steps.

This one-shot prompt applies these practices:

- state the outcome and workspace boundary first;
- provide exact product coordinates where correctness matters;
- keep the file scope small and reviewable;
- include known failure modes as short constraints;
- avoid asking the model to validate work it cannot execute;
- require a sanitized summary instead of command output.

Prompt split used in this demo:

- Continue `rules:` carry durable workspace behavior: write files to disk, use
  repository-relative paths, keep edits inside the requested project directory,
  keep examples minimal, and avoid printing secrets or concrete route hosts.
- The one-shot prompt carries task-specific details: Red Hat build of Quarkus
  coordinates, Maven repository and plugin XML, Jakarta imports, OpenShift
  deployment properties, and generated-file requirements.
- Quarkus-specific requirements do not belong in the general Continue rules.
  They stay in the one-shot prompt so the workspace rules remain useful for
  later specs, skills, and agentic workflows.

The Quarkus exercise targets Java 21. Stage 070 owns that runtime baseline in
the Dev Spaces workspace configuration. Fresh workspaces should show Java 21
from both `java -version` and `mvn -v`; if they do not, fix the workspace
tooling image or startup configuration instead of adding Java-selection
workarounds to this one-shot prompt.

```text
Create a minimal Red Hat build of Quarkus REST API in this Dev Spaces workspace.

Scope:
- Write only the `hello-quarkus-vibe` project files listed below.
- Do not edit other files.
- Do not run terminal commands or claim command results.
- Do not create `.mvn` config, use Quarkus CLI/archetypes, Helm, or
  OpenShift manifests.

Return Markdown only.
Do not report "Files Created" unless each required path exists on disk. If any
required file is missing, create it before responding.

Create exactly these relative paths with no leading slash:
- `hello-quarkus-vibe/pom.xml`
- `hello-quarkus-vibe/src/main/java/com/redhat/demo/hello/HelloResource.java`
- `hello-quarkus-vibe/src/test/java/com/redhat/demo/hello/HelloResourceTest.java`
- `hello-quarkus-vibe/src/main/resources/application.properties`
Create the directory hierarchy needed for each file, including
`hello-quarkus-vibe/src/main/resources`.

Use these project coordinates:
- Java 21, `groupId` `com.redhat.demo`, `artifactId` `hello-quarkus-vibe`,
  version `1.0.0-SNAPSHOT`, package `com.redhat.demo.hello`.
- Red Hat build of Quarkus `3.27.3.SP1-redhat-00002`.
- BOM `com.redhat.quarkus.platform:quarkus-bom:3.27.3.SP1-redhat-00002`.
- Plugin `com.redhat.quarkus.platform:quarkus-maven-plugin:3.27.3.SP1-redhat-00002`.
- Dependencies: `quarkus-rest`, `quarkus-openshift`, `quarkus-junit5` test,
  and `rest-assured` test.
- The Red Hat BOM and Maven plugin use `com.redhat.quarkus.platform`. The
  Quarkus extension dependencies use `io.quarkus`. Rest Assured uses
  `io.rest-assured`.

POM requirements:
- Include `<properties>` with `<maven.compiler.release>21</maven.compiler.release>`
  and `<project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>`.
- Configure `https://maven.repository.redhat.com/ga/` under both
  `<repositories>` and `<pluginRepositories>` with id
  `red-hat-enterprise-maven-repository`.
- Use literal Red Hat BOM and plugin coordinates, not Maven property indirection.
- Do not define or use `quarkus.maven.plugin.groupId`,
  `${quarkus.maven.plugin.groupId}`, `${quarkus.platform.group-id}`,
  `${quarkus.platform.artifact-id}`, or `${quarkus.platform.version}`.
- Use this exact BOM dependency inside `<dependencyManagement>`:
  <dependency>
      <groupId>com.redhat.quarkus.platform</groupId>
      <artifactId>quarkus-bom</artifactId>
      <version>3.27.3.SP1-redhat-00002</version>
      <type>pom</type>
      <scope>import</scope>
  </dependency>
- Use this exact Quarkus Maven plugin in `<build><plugins>`:
  <plugin>
      <groupId>com.redhat.quarkus.platform</groupId>
      <artifactId>quarkus-maven-plugin</artifactId>
      <version>3.27.3.SP1-redhat-00002</version>
      <extensions>true</extensions>
      <executions>
          <execution>
              <goals>
                  <goal>build</goal>
                  <goal>generate-code</goal>
                  <goal>generate-code-tests</goal>
              </goals>
          </execution>
      </executions>
  </plugin>
- Do not use `io.quarkus` as the Red Hat BOM or plugin groupId. Never use
  `io.quarkus:quarkus-maven-plugin` with a Red Hat build version.
- If `pom.xml` contains `${quarkus.maven.plugin.groupId}`, the POM is wrong
  and must be fixed before reporting completion.
- Do not use repository id `central` for the Red Hat GA repository.
- Do not use `generate-private`, Mockito, DeploymentConfig assumptions, or
  unrelated dependencies.
- Do not replace `quarkus-rest` with `quarkus-resteasy`.

Application requirements:
- `HelloResource` exposes `GET /hello`.
- Use Jakarta REST imports only: `jakarta.ws.rs.GET`, `jakarta.ws.rs.Path`,
  `jakarta.ws.rs.Produces`, and `jakarta.ws.rs.core.MediaType`. Do not use
  `javax.ws.rs.*`; Quarkus 3 uses Jakarta packages.
- It returns exactly:
  `Hello from governed vibe coding`
- `application.properties` contains exactly:
  `quarkus.openshift.route.expose=true`
  `quarkus.openshift.route.tls.termination=edge`
  `quarkus.openshift.route.tls.insecure-edge-termination-policy=Allow`
  `quarkus.openshift.namespace=hello-quarkus-vibe`
  `quarkus.container-image.group=hello-quarkus-vibe`

Test requirements:
- Use `@QuarkusTest` and Rest Assured.
- Assert HTTP 200 and the exact response body.
- Use `org.hamcrest.CoreMatchers.equalTo(...)` for the response body assertion.

After writing the files to disk, report only:
- files created;
- assumptions;
- notable implementation choices or blockers.

Do not include validation commands, command output, endpoint URLs, API keys,
tokens, credentials, private hostnames, or full environment variables.
```

## What To Notice And Why It Matters

The proof point is that experimentation starts from a governed platform contract. Developer Hub makes the path discoverable. Dev Spaces makes the workspace reproducible. MaaS centralizes model access. Continue gives the developer a familiar IDE interaction.

This matters because uncontrolled entry points weaken every later claim about source-code boundaries, model governance, and auditability. The merged vibe-coding guidance shows the productive side of prompting without pretending free-form output is trusted by default: useful requests stay bounded, reviewable, and verifiable.

## How Red Hat And Open Source Make It Work

Red Hat Developer Hub provides the portal and catalog entry point. Red Hat OpenShift Dev Spaces provides the cloud workspace. Red Hat OpenShift AI and MaaS provide the approved model endpoint. Continue consumes the OpenAI-compatible endpoint inside the IDE.

The open source tooling remains replaceable, while the enterprise controls remain platform-owned.

The Code-to-Docs pattern is useful here: let AI inspect diffs and propose documentation updates, but require humans to approve which documentation changes are true.

## Red Hat Products Used

- **[Red Hat Developer Hub](https://www.redhat.com/en/technologies/cloud-computing/developer-hub)** provides the developer portal entry point.
- **[Red Hat OpenShift Dev Spaces](https://www.redhat.com/en/technologies/cloud-computing/openshift/dev-spaces)** provides controlled cloud workspaces.
- **[Red Hat OpenShift AI](https://www.redhat.com/en/technologies/cloud-computing/openshift/openshift-ai)** provides governed model access through MaaS.
- **[Red Hat OpenShift](https://www.redhat.com/en/technologies/cloud-computing/openshift)** provides identity, routing, RBAC, and runtime controls.

## Open Source Projects To Know

- [Backstage](https://backstage.io/) is the upstream foundation for Developer Hub.
- [Eclipse Che](https://www.eclipse.org/che/) and DevWorkspace provide the workspace foundation.
- [Continue](https://www.continue.dev/) provides the IDE assistant workflow.
- [Model Context Protocol](https://modelcontextprotocol.io/) can expose approved read-only context to AI clients.

## TODOs

- TODO: Add executable deploy and validate scripts only after the workflow has real GitOps resources.
- TODO: Decide whether Developer Hub MCP catalog and TechDocs tools become part of later agentic workflows.
- TODO: Add direct catalog validation for model assets once the OpenShift AI connector path is selected.
- TODO: Add versioned prompt-pack examples for bounded Continue tasks after the hands-on workflow is finalized.

## Deploy And Validate

This planned stage has no deploy or validate scripts. Use:

- [Stage 100 Validation](../../docs/techdocs/stage-100-validation.md)
- [Developer Workflow Validation](../../docs/DEVELOPER_WORKFLOW_VALIDATION.md)
- [Operations](../../docs/OPERATIONS.md)

## References

- [Red Hat Developer Hub documentation](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.9)
- [Red Hat OpenShift Dev Spaces documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/)
- [What is Model-as-a-Service?](https://www.redhat.com/en/topics/ai/what-is-models-as-a-service)
- [A guide to AI code assistants with Red Hat OpenShift Dev Spaces](https://developers.redhat.com/articles/2026/01/28/guide-ai-code-assistants-red-hat-openshift-dev-spaces)
- [Developing Red Hat build of Quarkus applications with Apache Maven](https://docs.redhat.com/en/documentation/red_hat_build_of_quarkus/3.27/html-single/developing_and_compiling_your_red_hat_build_of_quarkus_applications_with_apache_maven/index)
- [Deploying Red Hat build of Quarkus applications to OpenShift](https://docs.redhat.com/en/documentation/red_hat_build_of_quarkus/3.27/html-single/deploying_your_red_hat_build_of_quarkus_applications_to_openshift_container_platform/index)
- [Quarkus getting started guide](https://quarkus.io/guides/getting-started)
- [Quarkus OpenShift deployment guide](https://quarkus.io/guides/deploying-to-openshift)
- [Quarkus container image configuration](https://quarkus.io/guides/container-image)
- [Vibes, specs, skills, and agents: The four pillars of AI coding](https://developers.redhat.com/articles/2026/03/30/vibes-specs-skills-agents-ai-coding)
- [Generative AI large language model prompt patterns: Tips for developers](https://developers.redhat.com/articles/2024/10/08/ai-llm-prompt-patterns-developers)
- [Prompt engineering: Big vs. small prompts for AI agents](https://developers.redhat.com/articles/2026/02/23/prompt-engineering-big-vs-small-prompts-ai-agents)
- [Karpathy X post introducing vibe coding](https://x.com/karpathy/status/1886192184808149383?lang=en)
- [Red Hat's enterprise guide to AI-assisted app dev](https://www.redhat.com/en/resources/ai-assisted-app-dev-enterprise-ebook)

## Next Stage

The former Stage 110 placeholder has been merged into this Stage 100 vibe-coding flow. Later stages are deferred in [BACKLOG.md](../../BACKLOG.md) and should be recreated only when each has a concrete implementation plan and validation path.
