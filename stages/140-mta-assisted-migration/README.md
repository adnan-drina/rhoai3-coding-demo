# Stage 140: Application Migration with MTA

Stage 130 shows a migration run by an autonomous agent harness. This stage shows the same kind of work the way the product documents it: a developer migrates a Spring Boot 2.x service to Quarkus in VS Code, with the migration toolkit for applications (MTA) 8.3 extension and Red Hat Developer Lightspeed for MTA, inside an OpenShift Dev Spaces workspace that the platform provisions from a golden-path template.

The message for platform teams: the workspace arrives ready. The platform provisions the extensions, the analyzer and the model access with the workspace, so the developer opens it and starts migrating. Developer Lightspeed proposes fixes with the private model served by Models-as-a-Service, using the developer's own MaaS key, so Models-as-a-Service stays the place where model access, quotas and usage are governed.

## What You'll Do

You will **provision** a migration project from the **Migrate Spring Boot to Quarkus with MTA** template (a writable copy of any Spring Boot 2.x repository, a workspace, a namespace and the delivery pipeline), **open** a workspace whose MTA extensions, analyzer, model access and settings are already in place, **analyze** the service against the Quarkus migration profile the template adds, **resolve** the issues with Developer Lightspeed in agent mode, **run** the migrated service in Quarkus dev mode and **push** it through the same pipeline that built the legacy code.

The template takes any Spring Boot 2.x service built with Maven. This walkthrough uses the Coolstore cart, [`coolstore-cart-legacy`](https://github.com/adnan-drina/coolstore-cart-legacy): a Spring Boot 2.7 shopping cart on Java 11 with `javax` APIs, Jersey resources under `/api` and an OpenFeign client for the catalog service. The platform GitLab mirrors it as `rhoai-workloads/coolstore-cart-legacy`.

---

## Step 1: Sign in to Developer Hub

1. Open the Developer Hub URL and sign in as `ai-developer` (OpenShift OIDC).

**What you should see:** the RHDH home screen with the catalog search bar.

---

## Step 2: Create your migration project from the template

1. Click the **+** icon in the header and choose the **Migrate Spring Boot to Quarkus with MTA** template.
2. **Git repository URL**: the HTTPS URL of the Spring Boot 2.x service, on GitHub or the platform GitLab. For this walkthrough: `https://github.com/adnan-drina/coolstore-cart-legacy.git`, or the `rhoai-workloads/coolstore-cart-legacy` URL of the platform GitLab.
3. **Project name**: `coolstore-cart` (lowercase, hyphens; it becomes the repository, namespace and workspace name).
4. Click **Review**, then **Create**, and watch the steps run: read the platform endpoints → copy the Spring Boot service (its default branch) → add the workspace, analysis profile and catalog files → publish to GitLab → enroll in the delivery pipeline.
5. Read the **Next steps** panel.

**What you should see:** every step green, with **Source repository** and **Open in catalog** links at the bottom.

> **Why a copy:** the source repository stays the reference. The template
> publishes a new repository with the Spring Boot code as its single first
> commit, so every change of the migration is a reviewable diff on top of
> the original. The template adds what every migration project needs: the
> workspace (`devfile.yaml`, `.code-workspace`), the MTA analysis profile,
> the catalog entry, a `Containerfile` and the runtime manifests.

---

## Step 3: Explore the component and its first build

1. Click **Open in catalog**.
2. On the Overview page, the **Links** card carries Source Repo, Dev Spaces and SonarQube for this project. The `demo.rhoai.io/migrated-from` annotation records the source repository.
3. Open the **CI** tab. Once the enrollment request is processed (about two minutes), a seed PipelineRun builds the Spring Boot code as it is: clone → `mvn package` → SonarQube scan → image build and push.

**What you should see:** the `coolstore-cart-dev` namespace, the `project-coolstore-cart` Argo CD application and the seed PipelineRun. The project's `Containerfile` packages either a Spring Boot jar or a Quarkus fast-jar, so the same pipeline builds the service before and after the migration.

---

## Step 4: Open the workspace

1. Click **Dev Spaces** in the Links card. The workspace starts from the project's `devfile.yaml`.
2. When VS Code opens, look at the **Extensions** view.

**What you should see:**

- One folder, `coolstore-cart`, opened through the project's `.code-workspace` file.
- **Migration Toolkit for Applications Core** 8.3.3, **MTA Java** 8.3.3 and **Language Support for Java by Red Hat**. This is the documented install of the core extension with one language extension.
- The Java language server in Standard mode, which MTA Java needs to provide its analysis. Wait for **Java: Ready** in the status bar (about half a minute): until then the MTA view reports that no analysis providers are registered.

The workspace settings that make this work live in the repository's `.code-workspace` file: `java.server.launchMode: Standard`, `mta-core.analyzerPath` pointing at the analyzer baked into the image, `mta-core.genai.enabled: true` and `mta-core.genai.agentMode: true`. The devfile connects Developer Lightspeed to the model (next step).

---

## Step 5: Check the model connection

1. Open the **Migration Toolkit for Applications** view in the activity bar and click **Open Analysis Panel**.
2. Optional: run **Open the GenAI model provider configuration file** from the Command Palette to see the active provider.

**What you should see:** the **MTA Analysis View** with **Agent Mode** switched on and no model connection warning. The provider configuration names one active provider, `maas`: `ChatOpenAI` with the Models-as-a-Service endpoint and the `qwen3-8-27b` model. There is nothing to sign in to.

> **How the workspace reaches the model:** this is the documented agent
> mode without the LLM proxy. Stage 070 mounts the developer's own MaaS
> key into every workspace as environment variables. The devfile passes it
> to the extension as `OPENAI_API_KEY`, and at every start it writes
> `provider-settings.yaml` with the MaaS endpoint and model. The key never
> lands in a file or in Git, and Models-as-a-Service meters and limits the
> calls like any other client's.

---

## Step 6: Analyze the legacy service

1. In the MTA view, open **Analysis profiles** and select **quarkus-profile**. The template adds it under `.konveyor/profiles/quarkus-profile/`; it targets Quarkus, Quarkus 3 and Jakarta EE with the default rule sets.
2. Click **Start** to start the analyzer server.
3. Click **Run Analysis**.

**What you should see:** the **Analysis Results** view lists the issues by category; the cart shows about 21 issues with 43 incidents in 7 files: Spring Boot starters and annotations to replace, `javax` packages to move to `jakarta`, and the Jersey and OpenFeign usages. Each issue links to the affected lines.

---

## Step 7: Resolve the issues with Developer Lightspeed

1. **Agent Mode** is already on in the Analysis View (the workspace setting `mta-core.genai.agentMode`).
2. Pick an issue (start with a `javax` to `jakarta` one) and ask Developer Lightspeed for a solution.
3. Review the proposed changes in the diff view. In agent mode Developer Lightspeed also builds the project and works on the follow-up problems it finds, asking before each change.
4. Accept the changes you agree with; reject or edit the rest. Run the analysis again to see the issue count fall.
5. Repeat until the analysis shows the issues you plan to leave.

**What you should see:** source changes proposed file by file, each one a diff you accept or reject. The model is the private `qwen3-8-27b` served on OpenShift AI, reached through Models-as-a-Service with the developer's key.

> **The human stays the reviewer:** every proposed change is a diff the
> developer accepts. Stage 130 hands the same decisions to an agent
> harness with deterministic gates; this stage keeps them in the editor.

---

## Step 8: Run the migrated service

1. Open the **Run** commands of the workspace (Terminal → Run Task → devfile) and start **start-dev** (`mvn quarkus:dev`), or run it in a terminal:

```
mvn quarkus:dev -Dquarkus.http.host=0.0.0.0
```

2. In a second terminal, call the service (for the cart, its cart API):

```
curl -s localhost:8080/api/cart/demo
```

**What you should see:** Quarkus dev mode starts and the cart answers with a cart document. The **run-legacy** command (`mvn spring-boot:run`) runs the Spring Boot code before its migration.

---

## Step 9: Push and let the pipeline build it

1. Commit from the Source Control view (message: `Migrate to Quarkus with MTA`) and push.
2. Watch the **CI** tab: the project's pipeline runs clone → `mvn package` → SonarQube → image build and push, then deploys the new image to `coolstore-cart-dev`.

**What you should see:** a green run for the migrated service, built and deployed by the same pipeline that built the Spring Boot code.

---

## Wrap-up

### What you proved

- **Self-service migration projects**: repository, workspace, namespace and pipeline from one template for any Spring Boot 2.x service, with the original code as the reviewable starting point.
- **A workspace configured by the documentation**: the MTA core extension with the Java language extension, the analyzer baked into the image, and the settings in the repository.
- **Governed AI assistance**: Developer Lightspeed reached the private model through Models-as-a-Service with the developer's own key, configured by the platform with the workspace; no extra sign-in in the editor.
- **The developer decides**: every change was a diff the developer accepted, checked by the analysis and by the pipeline.

### Resetting the demo

Teardown is an operator action on the platform. Run `stages/070-advanced-app-platform/demo-reset/delete-project.sh coolstore-cart` (plan) and then with `--yes`; see [`demo-reset/README.md`](../070-advanced-app-platform/demo-reset/README.md). Delete the DevWorkspace afterwards. Create the project again anytime from the template.

### Stage files

| Path | Purpose |
|------|---------|
| [`validate.sh`](validate.sh) | Read-only checks of the MaaS credentials, the template and the workspace image; `--project NAME` adds the checks of a created workspace |
| [`workspace-image/`](workspace-image/README.md) | The Stage 140 workspace image: its Dockerfile, the checksummed artifact lock and the build script |
| [`gitops/.../templates/migrate-with-mta/`](../../gitops/stages/070-advanced-app-platform/070-rhdh/templates/migrate-with-mta/template.yaml) | The Developer Hub template and its skeleton (devfile, `.code-workspace`, MTA analysis profile, catalog entry, Containerfile, runtime manifests) |

The template lives in the Stage 070 Developer Hub application, so this stage has no Argo CD application of its own. While Stage 140 is demonstrated, the Stage 130 **app-migration** template is not listed in the catalog; [docs/OPERATIONS.md](../../docs/OPERATIONS.md) describes how to list it again.

## Red Hat Products Used

- **[Migration Toolkit for Applications](https://developers.redhat.com/products/mta/overview)** provides the analysis rules, the analyzer, the VS Code extension and Developer Lightspeed for MTA.
- **[Red Hat Developer Hub](https://developers.redhat.com/rhdh)** provides the golden-path template and the catalog.
- **[Red Hat OpenShift Dev Spaces](https://www.redhat.com/en/technologies/cloud-computing/openshift/dev-spaces)** provides the workspace.
- **[Red Hat OpenShift AI](https://www.redhat.com/en/technologies/cloud-computing/openshift/openshift-ai)** serves the private model through Models-as-a-Service, which issues the developer's key.
- **[Red Hat OpenShift Pipelines](https://www.redhat.com/en/technologies/cloud-computing/openshift/pipelines)** builds and deploys the service.

## Open Source Projects To Know

- [Konveyor](https://konveyor.io/) is the upstream project of MTA: the analyzer, the rule sets and the IDE extensions.
- [Konveyor AI (Kai)](https://github.com/konveyor/kai) is the upstream of Developer Lightspeed for MTA.
- [Quarkus](https://quarkus.io/) is the migration target.

## References

| Resource | Link |
|----------|------|
| Installing the MTA extension | https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_the_visual_studio_code_extension_for_mta/index#installing-vscode-extension_vsc-extension-guide |
| Installing the analyzer RPC binary | https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_the_visual_studio_code_extension_for_mta/index#installing-analyzer-rpc_vsc-extension-guide |
| Analysis profiles | https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_the_visual_studio_code_extension_for_mta/index#analyzing-application-profiles_vsc-extension-guide |
| Analyzing an application | https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_the_visual_studio_code_extension_for_mta/index#vscode-analyzing-application_vsc-extension-guide |
| Reviewing and resolving issues | https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_the_visual_studio_code_extension_for_mta/index#vscode-reviewing-and-resolving-issues_vsc-extension-guide |
| Developer Lightspeed workflows (agent mode without the LLM proxy) | https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_red_hat_developer_lightspeed_for_mta/index#llm-proxy-workflow_getting-started |
| LLM provider settings | https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_red_hat_developer_lightspeed_for_mta/index#llm-provider-settings_configuring-llm |
| Models served by OpenShift AI | https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_red_hat_developer_lightspeed_for_mta/index#llm-service-openshift-ai_configuring-llm |
| Enabling agent mode | https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_red_hat_developer_lightspeed_for_mta/index#enabling-agent-mode_agent-ai |

## Previous Stage

[Stage 130: AI-Autonomous Migration](../130-ai-autonomous-migration/README.md) runs a migration with an autonomous agent harness.
