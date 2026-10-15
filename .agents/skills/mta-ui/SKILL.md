---
name: mta-ui
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: mta
  docs-version: "8.3"
  skill-group: "Application Modernization"
description: >
  Use when working with the MTA 8.3 Hub and web UI in this demo: Hub analysis,
  analysis profiles, assessments, task logs, and the native MTA Agents
  (Developer Preview) wired to MaaS through the konveyor.io Gateway maas-qwen,
  the agentic_enabled Tackle flag and the agentic-controller. Do NOT use for
  the install, SSO or storage (use mta-install), the Lightspeed proxy (use
  mta-lightspeed), workspace CLI analysis (use mta-cli), or rule authoring
  (use mta-rules).
---

# MTA user interface and Hub Agents

Thin skill: repo decisions and pitfalls here, product behavior in the linked
MTA 8.3 UI guide. Native Agents are Developer Preview. Detailed record:
`gitops/stages/070-advanced-app-platform/070-mta/README.md`.

## When to use

- A change touches `agentic_enabled`/`agentic_steer_enabled` in the Tackle CR
  or the Gateway `maas-qwen` in `070-mta/jobs/configure-ai.yaml`.
- Native Agents or the `agentic-controller` fail; Hub analysis or task logs
  need review.
- A workspace or Stage 130 run cannot find the Hub (`MTA_HUB_URL`).

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Native Agents on: `agentic_enabled: true`, `agentic_steer_enabled: false` | `gitops/stages/070-advanced-app-platform/070-mta/mta-instance/tackle.yaml` | [Enable agent in Tackle][enable] |
| Gateway `maas-qwen` (`konveyor.io/v1alpha1`): provider `openai`, `credentialRef` → `kai-api-keys`/`OPENAI_API_KEY` (not the doc example Secret), model `publishers/internal-models/models/qwen3-8-27b`, `contextWindow: 262144`, tier `efficient` | `070-mta/jobs/configure-ai.yaml` | [LLM gateway secret][gwsecret], [Gateway configuration][gwconf] |
| Gateway `endpoint` is a placeholder in Git; hook `configure-mta-ai` (wave 11, after the Gateway) writes the bare MaaS origin; Argo CD ignores `/spec/endpoint` | `070-mta/jobs/configure-ai.py`, Application `ignoreDifferences` | [Gateway configuration][gwconf] |
| Prerequisite Agent Sandbox controller comes from Stage 060 | `gitops/stages/060-agent-runtime-and-agentops/` | [Agent prerequisites][prereq] |
| `agentic-controller` memory sized by VPA (`070-mta/controller-sizing/`) | `070-mta/controller-sizing/agentic-memory.yaml` | see `mta-install` |
| Hub URL for workspaces: ConfigMap `mta-hub-config` (`MTA_HUB_URL`) in `wksp-*` | `070-mta/jobs/mta-hub-workspace-config.yaml` | [Connect the CLI to the Hub][hub] |
| Personas: `ai-admin` → `role.admin`, `ai-developer` → `role.architect` | `070-mta/jobs/configure-mta-platform-sso.yaml` | see `mta-install` |

## Procedure

1. Change the Tackle flags or Gateway in Git; keep the endpoint out of Git.
2. Validate after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   ./stages/070-advanced-app-platform/validate.sh          # "MTA 8.3 native Agents" rows
   ./stages/070-advanced-app-platform/validate.sh --static # product-schemas, stage070-upgrade tests
   ```

3. Read-only checks:

   ```bash
   oc get gateways.konveyor.io maas-qwen -n openshift-mta -o jsonpath='{.spec.endpoint}{"\n"}'
   oc get deployment agentic-controller -n openshift-mta
   oc get route mta -n openshift-mta -o jsonpath='{.spec.host}{"\n"}'
   ```

4. Agent, workflow and skill-card configuration happen in the UI
   ([Agents, skills and workflows][skills]); none is stored in Git.

## Pitfalls

- Endpoint contract: Gateway endpoint without `/v1` (the controller appends
  `/v1/models`); Tackle `kai_llm_baseurl` with `/v1`:
  `docs/TROUBLESHOOTING.md#mta-83-solution-server-crashes-or-its-agentic-controller-oomkills`.
- Native Agents do not need the Solution Server; a disabled Solution Server
  is reported as deferred, not broken.
- The controller can show 128Mi in its Deployment while running larger: the
  VPA acts on pods (`docs/OPERATIONS.md#mta-native-agents-and-controller-memory-sizing`).
- Missing Hub endpoint refuses the migration template:
  `docs/TROUBLESHOOTING.md#stage-070-workspace-tools-or-mta-ai-are-unavailable`.

## Official documentation (MTA 8.3)

| Topic | Section |
|---|---|
| Agents | [Workflow][flow], [Prerequisites][prereq], [Enable in Tackle][enable], [Gateway secret][gwsecret], [Gateway configuration][gwconf], [Deploy gateways][gwdeploy], [Skills and workflows][skills], [Runs][runs], [Troubleshooting][ts] |
| Hub analysis | [Run an analysis][analysis], [Analysis profiles][profiles], [Task logs][tasklog] |
| Instance setup | [Credentials][creds], [Custom migration targets][targets] |
| Assessment | [Assess an application][assess] |

## Related skills

`mta-install`, `mta-lightspeed`, `mta-cli`, `mta-rules`, `rhoai-maas-governance`.

[flow]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_managing_the_migration_toolkit_for_applications_user_interface/index#agent-workflow_configuring-and-using-mta-agents
[prereq]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_managing_the_migration_toolkit_for_applications_user_interface/index#agent-prerequisites_configuring-and-using-mta-agents
[enable]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_managing_the_migration_toolkit_for_applications_user_interface/index#enable-agent-in-tackle_cluster-configuration
[gwsecret]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_managing_the_migration_toolkit_for_applications_user_interface/index#llm-gateway-secret_cluster-configuration
[gwconf]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_managing_the_migration_toolkit_for_applications_user_interface/index#llm-gateway-configuration_cluster-configuration
[gwdeploy]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_managing_the_migration_toolkit_for_applications_user_interface/index#deploy-large-language-model-gateways_cluster-configuration
[skills]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_managing_the_migration_toolkit_for_applications_user_interface/index#agents-skills-and-workflow-configuration_configuring-and-using-mta-agents
[runs]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_managing_the_migration_toolkit_for_applications_user_interface/index#configuring-and-using-agent-and-workflow-runs_configuring-and-using-mta-agents
[ts]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_managing_the_migration_toolkit_for_applications_user_interface/index#troubleshooting-agents_configuring-and-using-mta-agents
[analysis]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_managing_the_migration_toolkit_for_applications_user_interface/index#configuring-and-running-an-application-analysis_analyzing-applications
[profiles]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_managing_the_migration_toolkit_for_applications_user_interface/index#centralized-configurations_user-interface-guide
[tasklog]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_managing_the_migration_toolkit_for_applications_user_interface/index#reviewing-a-task-log_controlling-tasks-with-task-manager
[creds]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_managing_the_migration_toolkit_for_applications_user_interface/index#configuring-credentials_configuring-mta-instance-environment
[targets]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_managing_the_migration_toolkit_for_applications_user_interface/index#creating-custom-migration-targets_configuring-mta-instance-environment
[assess]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_managing_the_migration_toolkit_for_applications_user_interface/index#assessing-an-application_assessing-applications
[hub]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/using_the_migration_toolkit_for_applications_command-line_interface/index#connect-cli-hub_analyzing-apps-profiles
