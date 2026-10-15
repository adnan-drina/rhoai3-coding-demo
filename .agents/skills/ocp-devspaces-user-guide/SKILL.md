---
name: ocp-devspaces-user-guide
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: ocp_devspaces
  docs-version: "3.30"
  skill-group: "OpenShift Platform"
description: >
  Use when authoring or reviewing what runs inside Dev Spaces 3.30 workspaces
  in this demo: the agentic-coolstore DevWorkspaces and the Developer Hub
  template devfiles, factory URLs with revision and existing parameters,
  DEFAULT_EXTENSIONS and baked VSIX files, mounted Secrets and ConfigMaps
  (workspace-maas-credentials, migration-model-profiles with mount-on-start),
  the postStart tool bootstrap, and governed MaaS access instead of the
  product AI-provider feature. Do NOT use for CheCluster or project
  administration (use ocp-devspaces-admin), the operator install (use
  ocp-devspaces-install), MTA extension specifics (use mta-vscode), or
  creating, deleting and debugging live workspaces (use manage-devspaces).
---

# Dev Spaces workspaces and devfiles

Thin skill: repo decisions and pitfalls here, devfile and workspace behavior
in the linked Dev Spaces 3.30 topics. Detailed record:
`gitops/stages/070-advanced-app-platform/devspaces/README.md`.

## When to use

- A change touches `devspaces/agentic-workspace.yaml`, the template devfiles
  under `gitops/stages/070-advanced-app-platform/rhdh/templates/*/skeleton/devfile.yaml`,
  or the mounted MaaS credentials and bootstrap ConfigMaps.
- A workspace starts without its tools, extensions or model credentials.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Standing DevWorkspace `agentic-coolstore` (`started: false`) in `wksp-ai-developer` and `wksp-ai-admin`, UDI image pinned by digest; `070-gitlab` patches its remote | `gitops/stages/070-advanced-app-platform/devspaces/agentic-workspace.yaml` | [Devfile in Dev Spaces][devfile] |
| New workspaces come from Developer Hub templates as factory URLs `…#<gitlab repo>?revision=main&existing=<name>` | `gitops/stages/070-advanced-app-platform/rhdh/templates/app-migration/template.yaml` | [Start from a Git URL][fromurl], [Existing workspace name][existing] |
| Kilo Code VSIX downloaded at postStart and loaded through `DEFAULT_EXTENSIONS`; migration workspaces load baked MTA VSIX files | `agentic-workspace.yaml`; `.../app-migration/skeleton/devfile.yaml` | [Pre-install extensions][defext], [Automate VS Code extensions][autoext] |
| MaaS credentials: Secret `workspace-maas-credentials` mounted as env (`MAAS_API_KEY`, `MAAS_API_BASE_URL`, model id), written by the key Job | `devspaces/maas-api-key-provisioning.yaml` | [Mount Secrets][secrets] |
| Model profile table `migration-model-profiles` mounted as file at `/etc/rhoai3/model-profiles` with `mount-on-start` | `devspaces/kustomization.yaml`, `devspaces/model-profiles.json` | [Mount ConfigMaps][configmaps] |
| Tool bootstrap `init-ai-tools.sh` from ConfigMap `devspace-ai-tools-init` at postStart (Kilo Code, OpenCode, Hermes) | `devspaces/maas-api-key-provisioning.yaml` | [Customize workspace components][components] |
| Model access goes through governed MaaS keys, not the product AI-provider registration | Stage 040, `devspaces/maas-api-key-provisioning.yaml` | [AI assistants][ai], [Register an AI provider][aiprov] |
| A DevWorkspace that sets `MIGRATION_RUN_NAME` must be named exactly that (ValidatingAdmissionPolicy) | `devspaces/migration-workspace-name-policy.yaml` | — |

## Procedure

1. Change devfiles and workspace manifests in Git; template changes reach
   developers through the Developer Hub catalog (`rhdh` component), and
   existing workspaces keep their devfile.
2. Validate after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   ./stages/070-advanced-app-platform/validate.sh --static
   python3 scripts/demo/check-workspace-creation.py --live
   ```

3. Inspect a workspace read-only:

   ```bash
   oc get devworkspace -n wksp-ai-developer
   oc get secret workspace-maas-credentials -n wksp-ai-developer -o jsonpath='{.metadata.labels}{"\n"}'
   ```

## Pitfalls

- A `mount-to-devworkspace` Secret or ConfigMap without `mount-on-start`
  restarts running workspaces when it changes; only the model profiles carry
  it (README Alignment table "Mounted credentials").
- postStart output lives on the workspace PVC
  (`/projects/.platform/poststart.log`):
  `docs/TROUBLESHOOTING.md#red-hat-openshift-dev-spaces-workspace-does-not-start`.
- Missing Kilo Code: `docs/TROUBLESHOOTING.md#kilo-code-is-missing-from-a-dev-spaces-workspace`.
- Interrupted factory creation leaves a suffixed duplicate:
  `docs/TROUBLESHOOTING.md#factory-creates-a-suffixed-duplicate-workspace`.
- Ephemeral-storage evictions:
  `docs/TROUBLESHOOTING.md#pipeline-or-workspace-pods-evicted-for-ephemeral-storage`.
- The UDI image is 3.29.1 under Dev Spaces 3.30.2 (recorded Gap).

## Official documentation (Dev Spaces 3.30)

| Topic | Section |
|---|---|
| Devfiles | [Devfile in Dev Spaces][devfile], [Customize components][components], [Fix devfile errors][devfileerr] |
| Starting workspaces | [From a Git URL][fromurl], [From a raw devfile URL][rawdevfile], [Existing workspace name][existing], [Factory badge][badge] |
| Credentials and config | [How it works][credcon], [Mount Secrets][secrets], [Mount ConfigMaps][configmaps], [Mount Git configuration][gitcfg] |
| Extensions | [Pre-install extensions][defext], [Automate VS Code extensions][autoext], [Add or remove extensions][addext] |
| AI assistants (not used) | [AI assistants][ai], [Register an AI provider][aiprov] |
| Idling and storage | [Prevent idling][idle], [Persistent storage][pvc] |
| Troubleshooting | [Workspace logs (CLI)][logs], [Debug a workspace][debug], [Startup failures][startup] |

## Related skills

`manage-devspaces`, `ocp-devspaces-admin`, `mta-vscode`, `rhoai-maas-governance`.

[devfile]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/develop-con_devfile_introduction
[components]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/develop-con_customizing_workspace_components
[devfileerr]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/troubleshoot-ref_troubleshooting_devfile_issues
[fromurl]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/get_started-proc_starting_a_workspace_from_a_git_repository_url
[rawdevfile]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/develop-proc_starting_a_workspace_from_a_raw_devfile_url
[existing]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/develop-ref_url_parameter_for_the_existing_workspace_name
[badge]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/develop-proc_adding_factory_badge_for_contributors
[credcon]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/develop-con_using_credentials_and_configurations_in_workspaces
[secrets]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/develop-proc_mounting_secrets
[configmaps]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/develop-proc_mounting_configmaps
[gitcfg]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/develop-proc_mounting_git_configuration
[defext]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/extend-proc_configuring_default_extensions
[autoext]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/develop-proc_automating_installation_of_vscode_extensions
[addext]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/extend-proc_adding_or_removing_extensions_in_a_workspace
[ai]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/develop-con_using_ai_assistants_in_workspaces
[aiprov]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/extend-proc_configuring_ai_providers
[idle]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/develop-proc_preventing_workspace_idling_for_long_running_commands
[pvc]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/develop-con_requesting_persistent_storage_for_workspaces
[logs]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/troubleshoot-proc_viewing_workspace_logs_in_cli
[debug]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/troubleshoot-proc_debugging_a_workspace
[startup]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/troubleshoot-ref_troubleshooting_workspace_startup_failures
