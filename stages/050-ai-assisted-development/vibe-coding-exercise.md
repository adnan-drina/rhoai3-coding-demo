# Stage 050: AI-Assisted Development (vibe-coding exercise)

## Why This Matters

Stages 010-040 build the governed AI platform for platform teams. Stage 050 changes the point of view: an enterprise developer now uses that platform to perform real development work. This is the moment where the architecture has to prove that productivity, governance, and human accountability can coexist.

The developer workflow should start from the platform, not from personal tools, copied API keys, and undocumented model choices. This stage shows the first developer-facing path after the platform is installed: Developer Hub for discovery, Dev Spaces for the workspace, MaaS for governed model access, and Continue for IDE assistance.

For enterprise architects, the business value is the same value demonstrated in the platform stages, but now seen from the developer side: sensitive source code can use a private model path, approved external models can still be centrally controlled, and developers can use familiar tools without bypassing policy.

Stage 050 is intentionally small. It proves the governed entry point and the first useful Continue workflow before introducing reusable skills, OpenCode agents, or multi-file autonomous work. The former Stage 110 spec and README-alignment placeholder has been merged into this stage as review discipline for responsible vibe coding, not as a separate stage.

## Key Concepts

| Concept | Meaning in this demo |
|---------|----------------------|
| **Governed model** | A model made available through MaaS with platform-owned access controls, credentials, identity, quotas, telemetry, and policy. Developers consume the approved model from the workspace instead of bringing personal model endpoints or API keys. |
| **AI coding assistant** | An IDE-integrated assistant, here Continue, configured inside Dev Spaces to use the governed model path. It helps the developer inspect context and produce small reviewable changes while the workspace and model access remain platform-managed. |
| **Vibe coding** | Human-led, prompt-driven exploration in the IDE. The developer describes intent in natural language, uses the assistant to create or explain small artifacts, and reviews every result. Vibe coding is useful for fast discovery and small testable changes, but it is not a substitute for tests, review, or engineering judgment. |
| **Prompt engineering** | The practice of writing instructions, context, constraints, and acceptance criteria so the model produces relevant, reviewable output. In this stage, durable behavior belongs in the Continue system prompt and Quarkus-specific requirements belong in the one-shot prompt. |

The order matters: the platform publishes a governed model, the IDE assistant consumes it, the developer uses vibe coding for a bounded task, and prompt engineering makes the request specific enough to review.

## What This Stage Adds

This stage turns the platform into a developer workflow.

- IDE integration with the `nemotron-3-nano-30b-a3b` model through MaaS.
- A safe opening prompt that confirms the AI coding assistants configuration.
- A one-shot Red Hat build of Quarkus Hello World exercise to demonstrate the limits and value of prompt-driven work.
- Human review gates for generated code, tests, documentation, dependencies, and model-boundary evidence.

## Developer Workflow

The developer starts in Red Hat Developer Hub and opens the `getting-started-ai-coding` component in Red Hat OpenShift Dev Spaces. The workspace is already prepared with the repository, IDE, runtime, and AI assistant configuration needed for the exercise.

Inside the workspace, the developer first checks that the AI coding assistant is using the governed model path. After that, the developer asks Continue to create a small Quarkus project, reviews the generated files, and validates the result outside the assistant.

## Continue

Continue is an open source AI coding assistant extension for IDEs. It gives developers control over model choice, provider endpoints, context sources, prompts, and assistant behavior through configuration files. Because Continue is fully open source, teams can inspect how it works and adapt it to their own development standards.

In this stage, Continue is preconfigured by Dev Spaces with the MaaS model catalog. `nemotron-3-nano-30b-a3b` is the default model for the hands-on flow, while other approved MaaS models remain available when policy allows. That keeps the developer experience familiar while model access, credentials, and policy remain platform-managed.

## Opening Prompt

Use this prompt first. It verifies the AI coding assistants configuration for this workspace.

```text
Check the AI coding assistants configuration for this workspace.

Return exactly four bullets:
- Client: the AI coding assistant being used.
- Model: the configured model ID.
- Model access: whether the model is reached through MaaS or not verified.
- Workspace: the repository name and workspace namespace if safely visible.
```

## Vibe Coding

Vibe coding is useful when the task is small, the reviewer understands the code, and validation is close at hand. The practice breaks down when intent, constraints, and decisions live only in a chat transcript. Stage 050 therefore treats assistant output as a draft and teaches the developer to move from conversation to durable engineering artifacts.

In this stage, vibe coding means asking Continue for a small, bounded application and then treating the generated output as something to review, test, and own.

## Prompt Engineering

Red Hat's prompt-pattern guidance describes prompt engineering as the practice
of designing instructions that guide a language model toward accurate,
relevant, and contextual output. That guidance matters here because LLMs
generate from patterns, not from real understanding of this repository,
Red Hat build of Quarkus, Maven repository behavior, OpenShift deployment, or
enterprise source-code boundaries.

In Stage 050, prompt engineering is the developer practice of turning intent
into a bounded request the assistant can act on and the human can review. The
prompt should state the outcome, scope, product coordinates, known constraints,
and acceptance criteria. It should also define the expected response shape so
the developer can quickly compare output with intent.

The same control pattern shows up across common prompt-engineering guidance:
put instructions first, separate instructions from context, use clear sections
or delimiters, include domain facts where correctness depends on them, and give
examples only when they clarify the desired format. For enterprise development,
that control is not cosmetic. It reduces ambiguity, limits context leakage,
and makes model output easier to review.

The developer also acts as an editor. Prompts should include only
task-relevant context: dumping large logs, unrelated files, or broad repository
content makes the prompt more expensive and can make the answer less focused.

The prompt also demonstrates the tradeoff between big and small prompts. A
single large prompt is easier to run live and is useful for Stage 050 vibe coding: one
request can create a small app and explain assumptions. Validation stays
outside the prompt because this Continue workflow does not provide reliable
terminal evidence. The downside is that a big prompt costs more context, can
drift, and still needs review. Later stages move this same intent into specs,
skills, and agents so the work can be split into smaller, more focused,
repeatable steps.

For broader work, the developer should ask the assistant to decompose the task
into a plan, checklist, or gap list before accepting edits. That keeps the human
in control of direction while still using the model for acceleration.

Prompt split used in this demo:

- **Continue system prompt** in `~/.continue/config.yaml` carries durable workspace behavior: write files to disk, use repository-relative paths, keep edits inside the requested project directory, keep examples minimal, and avoid printing secrets or concrete route hosts.
- **Quarkus one-shot prompt** carries task-specific details: Red Hat build of Quarkus coordinates, Maven repository and plugin XML, Jakarta imports, OpenShift deployment properties, and generated-file requirements.

## Good Practices

Use these Red Hat-aligned practices during the exercise:

- keep prompts scoped to a small, reviewable outcome;
- structure prompts with clear sections, boundaries, and expected output format;
- put the most important instructions before supporting context;
- include only task-relevant product facts, file paths, examples, and constraints;
- put durable constraints in rules, specs, tests, or README text rather than relying on memory;
- describe what the assistant should do, not only what it must avoid;
- ask for a plan or gap list before accepting broad edits;
- validate generated code outside the assistant when shell or cluster evidence is needed;
- keep model path, task type, files changed, validation result, and rejected suggestions as evidence;
- keep secrets, private route hostnames, source dumps, tokens, and full environment variables out of prompts and evidence;
- treat documentation generation as a review workflow: AI can propose, but a human decides what is true.

## One-Shot Quarkus Prompt

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

## Human Validation

After reviewing the generated files, run validation outside Continue:

```bash
cd hello-quarkus-vibe
mvn -U test

oc whoami
oc new-project hello-quarkus-vibe || oc project hello-quarkus-vibe

oc delete deployment,service,route,buildconfig,imagestream hello-quarkus-vibe -n hello-quarkus-vibe --ignore-not-found
oc delete build -l buildconfig=hello-quarkus-vibe -n hello-quarkus-vibe --ignore-not-found

mvn install -Dquarkus.openshift.deploy=true

oc get deployment,service,route hello-quarkus-vibe -n hello-quarkus-vibe
oc get route hello-quarkus-vibe -n hello-quarkus-vibe \
  -o jsonpath='{.spec.tls.termination}{"\n"}{.spec.tls.insecureEdgeTerminationPolicy}{"\n"}'

ROUTE_HOST="$(oc get route hello-quarkus-vibe -n hello-quarkus-vibe -o jsonpath='{.spec.host}')"
curl -fsS "http://${ROUTE_HOST}/hello"
curl -k -fsS "https://${ROUTE_HOST}/hello"
```

## Platform Capabilities Consumed

- Stage 040 provides governed MaaS access.
- Stage 050 can provide approved external models for non-sensitive tasks when policy allows.
- Stage 070 provides MCP context integration.
- Stage 050 provides Dev Spaces with Continue and OpenCode tooling.
- Stage 090 provides Developer Hub catalog entries and component-specific Dev Spaces links.

## Red Hat Products Used

- **[Red Hat Developer Hub](https://www.redhat.com/en/technologies/cloud-computing/developer-hub)** provides the developer portal entry point.
- **[Red Hat OpenShift Dev Spaces](https://www.redhat.com/en/technologies/cloud-computing/openshift/dev-spaces)** provides controlled cloud workspaces.
- **[Red Hat OpenShift AI](https://www.redhat.com/en/technologies/cloud-computing/openshift/openshift-ai)** provides governed model access through MaaS.
- **[Red Hat OpenShift](https://www.redhat.com/en/technologies/cloud-computing/openshift)** provides identity, routing, RBAC, and runtime controls.

## Open Source Projects To Know

- [Eclipse Che](https://www.eclipse.org/che/) and DevWorkspace provide the workspace foundation.
- [Continue](https://www.continue.dev/) provides the IDE assistant workflow.

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
- [The uncomfortable truth about vibe coding](https://developers.redhat.com/articles/2026/02/17/uncomfortable-truth-about-vibe-coding)
- [Vibes, specs, skills, and agents: The four pillars of AI coding](https://developers.redhat.com/articles/2026/03/30/vibes-specs-skills-agents-ai-coding)
- [AI-powered documentation updates: From code diff to docs PR in one comment](https://developers.redhat.com/articles/2026/04/21/ai-powered-documentation-updates-code-diff-docs-pr-one-comment)
- [OpenCode: A model-neutral AI coding assistant for OpenShift Dev Spaces](https://developers.redhat.com/articles/2026/04/22/opencode-model-neutral-ai-coding-assistant-openshift-dev-spaces)
- [Generative AI large language model prompt patterns: Tips for developers](https://developers.redhat.com/articles/2024/10/08/ai-llm-prompt-patterns-developers)
- [Prompt engineering: Big vs. small prompts for AI agents](https://developers.redhat.com/articles/2026/02/23/prompt-engineering-big-vs-small-prompts-ai-agents)
- [Prompt Engineering Best Practices](https://launchdarkly.com/blog/prompt-engineering-best-practices/)
- [Best practices for prompt engineering with the OpenAI API](https://help.openai.com/en/articles/6654000-best-practices-for-prompt-engineering-with-the-openai-api)
- [Claude prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)
- [Karpathy X post introducing vibe coding](https://x.com/karpathy/status/1886192184808149383?lang=en)
- [Red Hat's enterprise guide to AI-assisted app dev](https://www.redhat.com/en/resources/ai-assisted-app-dev-enterprise-ebook)

## Next Developer Workflow

The former Stage 110 placeholder has been merged into this Stage 050 vibe-coding flow. Later developer workflow topics are deferred in [BACKLOG.md](../../BACKLOG.md) and should be recreated only when each has a concrete implementation plan and validation path.
