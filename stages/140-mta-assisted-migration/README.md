# Stage 140: Application Migration with MTA

Stage 130 shows a migration run by an autonomous agent harness. This stage shows the same kind of work the way the product documents it: a developer migrates a Spring Boot 2.x service to Quarkus in VS Code, with the migration toolkit for applications (MTA) 8.3 extension and Red Hat Developer Lightspeed for MTA, inside an OpenShift Dev Spaces workspace that the platform provisions from a golden-path template.

The message for platform teams: the MTA Hub is the single place that holds the migration rules, the developer's identity and the model access. The developer signs in once; the extension analyzes the code, and Developer Lightspeed proposes fixes through the Hub's LLM proxy to the private model served by Models-as-a-Service. No developer holds a model key.

## What You'll Do

You will **provision** a migration project from the **Migrate Spring Boot to Quarkus with MTA** template (a writable copy of any Spring Boot 2.x repository, a workspace, a namespace and the delivery pipeline), **open** a workspace whose MTA extensions, analyzer and settings are already in place, **sign in** to the MTA Hub with the platform identity, **analyze** the service against the Quarkus migration profile the template adds, **resolve** the issues with Developer Lightspeed in agent mode, **run** the migrated service in Quarkus dev mode and **push** it through the same pipeline that built the legacy code.

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
4. Click **Review**, then **Create**, and watch the steps run: read the platform endpoints → check the MTA Hub → copy the Spring Boot service (its default branch) → add the workspace, analysis profile and catalog files → publish to GitLab → enroll in the delivery pipeline.
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
2. On the Overview page, the **Links** card carries Source Repo, Dev Spaces, SonarQube and MTA Hub for this project. The `demo.rhoai.io/migrated-from` annotation records the source repository.
3. Open the **CI** tab. Once the enrollment request is processed (about two minutes), a seed PipelineRun builds the Spring Boot code as it is: clone → `mvn package` → SonarQube scan → image build and push.

**What you should see:** the `coolstore-cart-dev` namespace, the `project-coolstore-cart` Argo CD application and the seed PipelineRun. The project's `Containerfile` packages either a Spring Boot jar or a Quarkus fast-jar, so the same pipeline builds the service before and after the migration.

---

## Step 4: Open the workspace

1. Click **Dev Spaces** in the Links card. The workspace starts from the project's `devfile.yaml`.
2. When VS Code opens, look at the **Extensions** view.

**What you should see:**

- One folder, `coolstore-cart`, opened through the project's `.code-workspace` file.
- **Migration Toolkit for Applications Core** 8.3.3, **MTA Java** 8.3.3 and **Language Support for Java by Red Hat**. This is the documented install of the core extension with one language extension.
- The Java language server in Standard mode (the status bar shows the Java project once it is imported), which MTA Java needs to provide its analysis.

The workspace settings that make this work live in the repository's `.code-workspace` file: `java.server.launchMode: Standard`, `mta-core.analyzerPath` pointing at the analyzer baked into the image, `mta-core.genai.enabled: true` and `mta-core.hub.auth.method: oidc`. The devfile sets the Hub connection (`HUB_URL`, `FORCE_HUB_ENABLED`) for this cluster's MTA Hub.

---

## Step 5: Sign in to the MTA Hub

1. Open the **Migration Toolkit for Applications** view in the activity bar.
2. Open **Configure Hub Settings**. The Hub URL is already set for this cluster, with OIDC authentication.
3. Click **Sign In**. A browser tab opens the platform sign-in page; sign in as `ai-developer`.

**What you should see:** the Hub connection shown as connected. From now on Developer Lightspeed reaches the model through the Hub's LLM proxy with your signed-in identity.

> **Why the Hub:** the platform enabled the LLM proxy on the Tackle
> resource (`kai_llm_proxy_enabled: true`) and stored the Models-as-a-Service
> key once, in the `openshift-mta` namespace. Every developer request goes
> through the Hub with the developer's token, so access, audit and
> emergency shutdown stay with the platform team.

---

## Step 6: Analyze the legacy service

1. In the MTA view, open **Analysis profiles** and select **quarkus-profile**. The template adds it under `.konveyor/profiles/quarkus-profile/`; it targets Quarkus, Quarkus 3 and Jakarta EE with the default rule sets.
2. Click **Start** to start the analyzer server.
3. Click **Run Analysis**.

**What you should see:** the **Analysis Results** view lists the issues by category; the cart shows about 21 issues with 43 incidents in 7 files: Spring Boot starters and annotations to replace, `javax` packages to move to `jakarta`, and the Jersey and OpenFeign usages. Each issue links to the affected lines.

---

## Step 7: Resolve the issues with Developer Lightspeed

1. Turn on **Agent Mode** in the Analysis Results view.
2. Pick an issue (start with a `javax` to `jakarta` one) and ask Developer Lightspeed for a solution.
3. Review the proposed changes in the diff view. In agent mode Developer Lightspeed also builds the project and works on the follow-up problems it finds, asking before each change.
4. Accept the changes you agree with; reject or edit the rest. Run the analysis again to see the issue count fall.
5. Repeat until the analysis shows the issues you plan to leave.

**What you should see:** source changes proposed file by file, each one a diff you accept or reject. The model is the private `qwen3-8-27b` served on OpenShift AI, reached through the Hub.

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
- **Governed AI assistance**: Developer Lightspeed reached the private model through the MTA Hub with the developer's own identity; no model key left the platform.
- **The developer decides**: every change was a diff the developer accepted, checked by the analysis and by the pipeline.

### Resetting the demo

Teardown is an operator action on the platform. Run `stages/070-advanced-app-platform/demo-reset/delete-project.sh coolstore-cart` (plan) and then with `--yes`; see [`demo-reset/README.md`](../070-advanced-app-platform/demo-reset/README.md). Delete the DevWorkspace afterwards. Create the project again anytime from the template.

### Stage files

| Path | Purpose |
|------|---------|
| [`validate.sh`](validate.sh) | Read-only checks of the MTA Hub, the LLM proxy, the template and the workspace image; `--project NAME` adds the checks of a created workspace |
| [`workspace-image/`](workspace-image/README.md) | The Stage 140 workspace image: its Dockerfile, the checksummed artifact lock and the build script |
| [`gitops/.../templates/migrate-with-mta/`](../../gitops/stages/070-advanced-app-platform/070-rhdh/templates/migrate-with-mta/template.yaml) | The Developer Hub template and its skeleton (devfile, `.code-workspace`, MTA analysis profile, catalog entry, Containerfile, runtime manifests) |

The template lives in the Stage 070 Developer Hub application, so this stage has no Argo CD application of its own. While Stage 140 is demonstrated, the Stage 130 **app-migration** template is not listed in the catalog; [docs/OPERATIONS.md](../../docs/OPERATIONS.md) describes how to list it again.

## Red Hat Products Used

- **[Migration Toolkit for Applications](https://developers.redhat.com/products/mta/overview)** provides the Hub, the analysis rules, the VS Code extension and Developer Lightspeed for MTA.
- **[Red Hat Developer Hub](https://developers.redhat.com/rhdh)** provides the golden-path template and the catalog.
- **[Red Hat OpenShift Dev Spaces](https://www.redhat.com/en/technologies/cloud-computing/openshift/dev-spaces)** provides the workspace.
- **[Red Hat OpenShift AI](https://www.redhat.com/en/technologies/cloud-computing/openshift/openshift-ai)** serves the private model through Models-as-a-Service.
- **[Red Hat OpenShift Pipelines](https://www.redhat.com/en/technologies/cloud-computing/openshift/pipelines)** builds and deploys the service.

## Open Source Projects To Know

- [Konveyor](https://konveyor.io/) is the upstream project of MTA: the Hub, the analyzer and the rule sets.
- [Konveyor AI (Kai)](https://github.com/konveyor/kai) is the upstream of Developer Lightspeed for MTA.
- [Quarkus](https://quarkus.io/) is the migration target.

## References

| Resource | Link |
|----------|------|
| Installing the MTA extension | https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_the_visual_studio_code_extension_for_mta/index#installing-vscode-extension_vsc-extension-guide |
| Installing the analyzer RPC binary | https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_the_visual_studio_code_extension_for_mta/index#installing-analyzer-rpc_vsc-extension-guide |
| OIDC authentication for the IDE extension | https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_the_visual_studio_code_extension_for_mta/index#configure-oidc-authentication-ide-extension_vsc-extension-guide |
| Analysis profiles | https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_the_visual_studio_code_extension_for_mta/index#analyzing-application-profiles_vsc-extension-guide |
| Analyzing an application | https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_the_visual_studio_code_extension_for_mta/index#vscode-analyzing-application_vsc-extension-guide |
| Reviewing and resolving issues | https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_the_visual_studio_code_extension_for_mta/index#vscode-reviewing-and-resolving-issues_vsc-extension-guide |
| Developer Lightspeed LLM proxy workflow | https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_red_hat_developer_lightspeed_for_mta/index#llm-proxy-workflow_getting-started |
| Enabling the LLM proxy | https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_red_hat_developer_lightspeed_for_mta/index#tackle-enable-llm-proxy_getting-started |
| Enabling agent mode | https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_red_hat_developer_lightspeed_for_mta/index#enabling-agent-mode_agent-ai |

## Previous Stage

[Stage 130: AI-Autonomous Migration](../130-ai-autonomous-migration/README.md) runs a migration with an autonomous agent harness.
