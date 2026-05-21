# Stage 100 Validation

Stage 100 proves that developer onboarding and the first Continue-based
enterprise vibes check work before any AI-assisted code change begins.
The term "vibe coding" is referenced from Andrej Karpathy's original X post,
while the enterprise definition follows Red Hat's AI-assisted application
development guidance: the developer uses natural-language prompts in an IDE,
reviews the result, and remains accountable for validation.
In the four-increment developer story, this is the **vibes** stage: intuitive
exploration and idea-sharing inside a governed workspace.

## Green Bar

Stage 100 is green only when all of these checks pass:

- Developer Hub is reachable.
- These catalog entities are visible:
  - `System:default/coolstore`
  - `Component:default/getting-started-ai-coding`
  - `Component:default/coolstore`
  - `Component:default/coolstore-inventory-service`
  - `Resource:default/maas-private-code-model-nemotron`
- Each component shows only `Source Repo`, `Dev Spaces`, and
  `Getting Started`.
- The `Getting Started` link opens this TechDocs site.
- The `getting-started-ai-coding` component points to
  `adnan-drina/getting-started-ai-coding`.
- The `coolstore` component points to `rhpds/mca-coolstore`.
- The `coolstore-inventory-service` component points to
  `adnan-drina/coolstore-inventory-service` on `main`.
- Each `Dev Spaces` link opens a controlled single-repository workspace.
- The onboarding workspace contains only `getting-started-ai-coding`.
- The inventory workspace contains only `coolstore-inventory-service`.
- The modernization workspace contains only `mca-coolstore`.
- Red Hat OpenShift Dev Spaces is reachable.
- The `wksp-ai-developer/getting-started-ai-coding`,
  `wksp-ai-developer/coolstore-inventory-service`, and
  `wksp-ai-developer/mca-coolstore` workspaces exist without a failed phase.
- `Secret/wksp-ai-developer/maas-devspace-api-keys` exists and is not copied
  into Git.
- `~/.continue/config.yaml` is generated in the workspace only.
- Continue completes the opening onboarding prompt against
  `nemotron-3-nano-30b-a3b` through MaaS.
- Continue completes the one-shot Quarkus vibe-coding prompt from the Stage 100
  README by creating files and reporting a concise sanitized summary.
- Human-run validation confirms the Quarkus Hello World app includes the
  required POM, source, test, and resources files, is tested, deployed only into
  the `hello-quarkus-vibe` namespace, verified with `GET /hello`, and reported
  with sanitized evidence.
- A generated Quarkus app that has only `pom.xml`, reports `No tests to run`,
  or compiles with Java source/target 8 fails validation.
- Human review confirms the generated app uses `quarkus-rest`,
  `quarkus-openshift`, `quarkus-junit5`, Rest Assured tests, Red Hat build of
  Quarkus Maven plugin coordinates, and current `Deployment` terminology.
- The assistant did not use Helm tools, list or read Kubernetes Secrets, try
  terminal execution, claim "Command executed in remote terminal", or report
  unverified deployment results.
- No route hostnames, API keys, kubeconfigs, model tokens, or provider keys are
  committed as evidence.

## Opening Continue Prompt

Use this prompt in Continue agent mode:

```text
Explore this repository, the configured LLM, and the connected environment.

Return exactly four bullets:
- Model: the configured model ID.
- Model access: the governed access layer used by the configured model path.
- Project: the repository name and a short description from the README file.
- Platform: the namespace or cluster context visible through tools.

Do not change cluster state. Do not print sensitive information, endpoint URLs,
API keys, tokens, source code, credentials, private hostnames, or full
environment variables. If any check cannot be verified, say "not verified" for
that bullet.
```

Record only:

- the selected model ID;
- whether the prompt succeeded;
- the date of the check;
- any blocker that prevented completion.

## One-Shot Vibe Coding Check

Use the one-shot Quarkus prompt from the Stage 100 README after the opening
Continue prompt succeeds.

Record only:

- project directory;
- model ID;
- test result;
- deployment resource names;
- route verification result with the hostname redacted;
- blocker, if any.

Do not record endpoint URLs, API keys, tokens, source code, credentials,
private hostnames, or full environment variables.

## Agentic Engineering Handoff

The OpenCode agentic engineering segment can start only after Stage 100 has a
working Developer Hub entry point, a running Dev Spaces workspace, and verified
MaaS connectivity from Continue.
