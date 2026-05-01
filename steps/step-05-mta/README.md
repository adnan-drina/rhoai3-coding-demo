# Step 05: AI-Assisted EAP/Java EE Modernization To Quarkus

## Why This Matters

Enterprise AI is most valuable when it is embedded into real engineering workflows. Application modernization is a good example: large organizations have portfolios of Java EE and JBoss EAP applications that need to move toward modern runtimes such as Quarkus, but the work is repetitive, specialized, and risky.

Generic AI prompting is not enough. Modernization needs analysis, rules, portfolio context, developer review, and repeatable workflows. This step shows how Migration Toolkit for Applications (MTA) and Developer Lightspeed can use governed models to assist modernization without bypassing platform controls.

## What This Step Adds

Step 05 adds the modernization layer:

```text
MTA modernization layer
+-- MTA 8.1 Operator
+-- Tackle CR
+-- MTA Hub and UI
+-- Developer Lightspeed services
+-- Solution Server and database
+-- LLM proxy
+-- kai-api-keys Secret for MaaS access
+-- OpenShift OAuth federation through MTA Keycloak / RHBK
+-- ConsoleLink for OpenShift launcher access
```

The demo uses [konveyor-ecosystem/coolstore](https://github.com/konveyor-ecosystem/coolstore), a Java EE / JBoss-style sample application. The `main` branch is the legacy starting point and the `quarkus` branch is the completed reference target.

## What To Notice In The Demo

Show the workflow, not only the generated code.

1. MTA analyzes Coolstore and identifies migration issues.
2. The developer opens the same application in Dev Spaces.
3. The MTA VS Code extension brings migration issues into the IDE.
4. Developer Lightspeed requests an AI-assisted fix.
5. The LLM request flows through the MTA LLM proxy to MaaS.
6. The developer reviews and applies a targeted change.
7. Analysis is run again to show progress.

The important message is precision. MTA gives the model migration context from rules and static analysis. The AI is not guessing from a vague prompt; it is assisting a governed modernization workflow.

## How Red Hat And Open Source Make It Work

MTA provides the analysis engine, application inventory, migration rules, and developer extension. Developer Lightspeed adds AI-assisted code resolution. The LLM proxy centralizes model credentials. MaaS publishes the model endpoint. OpenShift OAuth and RHBK provide the identity chain.

```text
Developer in Dev Spaces
  -> MTA VS Code extension
  -> MTA Hub
  -> LLM proxy
  -> MaaS Gateway
  -> Private Nemotron model
  -> Suggested migration fix
```

The primary demo path uses the private MaaS-published Nemotron model. MTA can also point to other OpenAI-compatible MaaS models when policy allows.

## Red Hat Products Used

- **Migration Toolkit for Applications 8.1** provides the modernization analysis, application inventory, migration rules, and developer workflow integration.
- **Developer Lightspeed for MTA** adds AI-assisted code resolution to the modernization workflow.
- **Red Hat OpenShift AI MaaS** provides the governed model endpoint used by the MTA LLM proxy.
- **Red Hat OpenShift Dev Spaces** hosts the developer workspace and MTA VS Code extension.
- **Red Hat build of Keycloak** provides the identity layer used by MTA and the federated OpenShift login flow.
- **Red Hat OpenShift** provides the runtime platform, identity integration, routes, storage, and operations foundation.

## Open Source Projects To Know

- [Konveyor](https://www.konveyor.io/) is the upstream community for application modernization capabilities behind MTA.
- [Kantra](https://github.com/konveyor/kantra) provides CLI-based application analysis capabilities in the Konveyor ecosystem.
- [Kai](https://github.com/konveyor/kai) is the upstream AI-assisted modernization effort behind Developer Lightspeed-style workflows.
- [Coolstore](https://github.com/konveyor-ecosystem/coolstore) is the Java EE sample application used to demonstrate the migration path to Quarkus.

## Trust Boundaries

- For sensitive code, use the private MaaS model path so prompts and source context remain on the OpenShift platform.
- If an organization approves external models for selected modernization tasks, MaaS can expose those models through the same controlled interface.
- Developers do not manage provider credentials in the primary flow; the LLM proxy uses centrally managed credentials.

## Why This Is Worth Knowing

This step shows that AI-assisted development is not limited to chat windows and autocomplete. With the right platform pattern, AI can support strategic engineering work such as application modernization.

The reusable lesson is:

- Static analysis provides trusted context.
- The model access layer provides governance.
- The developer extension provides workflow integration.
- Human review remains part of the process.

That combination is much more credible for enterprise modernization than unmanaged AI prompting.

## Where This Fits In The Full Platform

| Earlier capability | How MTA uses it |
|--------------------|-----------------|
| Step 01 platform identity | MTA login is federated through OpenShift OAuth |
| Step 03 MaaS | Developer Lightspeed calls a governed model endpoint |
| Step 04 Dev Spaces | The MTA extension runs in the developer workspace |
| Step 06 Developer Hub | The modernization workflow can become a portal golden path |

## Deploy And Validate

Operational commands are kept here for workshop operators.

```bash
./steps/step-05-mta/deploy.sh
./steps/step-05-mta/validate.sh
```

Manifests: [`gitops/step-05-mta/base/`](../../gitops/step-05-mta/base/)

## References

- [Coolstore sample application](https://github.com/konveyor-ecosystem/coolstore)
- [MTA 8.1 documentation](https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.1/)
- [MTA 8.1 installation guide](https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.1/html-single/installing_the_migration_toolkit_for_applications/index)
- [Developer Lightspeed for MTA 8.1](https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.1/html-single/configuring_and_using_red_hat_developer_lightspeed_for_mta/index)
- [MTA VS Code extension 8.1](https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.1/html-single/configuring_and_using_the_visual_studio_code_extension_for_mta/index)
- [MaaS code assistant quickstart](https://docs.redhat.com/en/learn/ai-quickstarts/rh-maas-code-assistant)

## Next Step

[Step 06: Red Hat Developer Hub](../step-06-developer-hub/README.md) turns the platform capabilities into a self-service developer portal experience.
