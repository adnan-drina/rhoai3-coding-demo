# Official Doc Extraction

Use this extraction to keep OpenShift Pipelines CLI reference content grounded
in official Red Hat sources. When using tkn commands on a live cluster, verify
available commands and flags with `tkn <command> --help`.

## Installing tkn

The OpenShift Pipelines CLI archives and RPMs contain three executables:

- `tkn` — primary CLI tool for managing pipelines
- `tkn-pac` — Pipelines as Code CLI
- `opc` — OpenShift Pipelines Client (Technology Preview)

### Linux (tar.gz)

```bash
tar xvzf <file>
```

Available architectures: x86_64/amd64, s390x, ppc64le, aarch64/arm64.

### Linux (RPM — RHEL 8)

```bash
subscription-manager register
subscription-manager refresh
subscription-manager list --available --matches '*pipelines*'
subscription-manager attach --pool=<pool_id>

# x86_64
subscription-manager repos --enable="pipelines-1.22-for-rhel-8-x86_64-rpms"
# s390x
subscription-manager repos --enable="pipelines-1.22-for-rhel-8-s390x-rpms"
# ppc64le
subscription-manager repos --enable="pipelines-1.22-for-rhel-8-ppc64le-rpms"
# aarch64
subscription-manager repos --enable="pipelines-1.22-for-rhel-8-aarch64-rpms"

yum install openshift-pipelines-client
```

### macOS (tar.gz)

Available architectures: x86_64, ARM.

### Windows (zip)

Download and extract zip archive.

### Verify installation

```bash
tkn version
```

## Configuring Tab Completion

```bash
tkn completion bash > tkn_bash_completion
sudo cp tkn_bash_completion /etc/bash_completion.d/
```

Supported shells: `bash`, `zsh`.

## Basic Syntax

```
tkn [command or options] [arguments...]
```

Global option: `--help, -h`

## Utility Commands

### tkn

Parent command — displays all available subcommands and options.

```bash
tkn
```

### tkn completion

Print shell completion code for interactive completion.

```bash
tkn completion bash
tkn completion zsh
```

### tkn version

Print version information.

```bash
tkn version
```

## Pipeline Management Commands (`tkn pipeline`)

### tkn pipeline

Manage pipelines.

```bash
tkn pipeline --help
```

### tkn pipeline delete

Delete a pipeline.

```bash
tkn pipeline delete <pipeline_name> -n <namespace>
```

### tkn pipeline describe

Describe a pipeline.

```bash
tkn pipeline describe <pipeline_name>
```

### tkn pipeline list

Display a list of pipelines.

```bash
tkn pipeline list
```

### tkn pipeline logs

Display logs for a specific pipeline.

```bash
# Stream live logs
tkn pipeline logs -f <pipeline_name>
```

Key flag: `-f` for follow/stream.

### tkn pipeline start

Start a pipeline.

```bash
tkn pipeline start <pipeline_name>
```

## Pipeline Run Commands (`tkn pipelinerun`)

### tkn pipelinerun

Manage pipeline runs.

```bash
tkn pipelinerun -h
```

### tkn pipelinerun cancel

Cancel a pipeline run.

```bash
tkn pipelinerun cancel <pipeline_run_name> -n <namespace>
```

### tkn pipelinerun delete

Delete pipeline runs.

```bash
# Delete specific runs
tkn pipelinerun delete <name_1> <name_2> -n <namespace>

# Delete all except N most recent
tkn pipelinerun delete -n <namespace> --keep 5

# Delete all (does NOT delete running resources since Pipelines 1.6)
tkn pipelinerun delete --all
```

Key flags:
- `--keep <N>` — retain N most recently executed runs
- `--all` — delete all non-running pipeline runs

### tkn pipelinerun describe

Describe a pipeline run.

```bash
tkn pipelinerun describe <pipeline_run_name> -n <namespace>
```

### tkn pipelinerun list

List pipeline runs.

```bash
tkn pipelinerun list -n <namespace>
```

### tkn pipelinerun logs

Display logs of a pipeline run.

```bash
# Display all task and step logs
tkn pipelinerun logs <pipeline_run_name> -a -n <namespace>
```

Key flag: `-a` for all tasks and steps.

## Task Management Commands (`tkn task`)

### tkn task

Manage tasks.

```bash
tkn task -h
```

### tkn task delete

Delete tasks.

```bash
tkn task delete <task_name_1> <task_name_2> -n <namespace>
```

### tkn task describe

Describe a task.

```bash
tkn task describe <task_name> -n <namespace>
```

### tkn task list

List tasks.

```bash
tkn task list -n <namespace>
```

### tkn task start

Start a task.

```bash
tkn task start <task_name> -s <service_account_name> -n <namespace>
```

Key flag: `-s` for service account.

## Task Run Commands (`tkn taskrun`)

### tkn taskrun

Manage task runs.

```bash
tkn taskrun -h
```

### tkn taskrun cancel

Cancel a task run.

```bash
tkn taskrun cancel <task_run_name> -n <namespace>
```

### tkn taskrun delete

Delete task runs.

```bash
# Delete specific runs
tkn taskrun delete <name_1> <name_2> -n <namespace>

# Delete all except N most recent
tkn taskrun delete -n <namespace> --keep 5
```

Key flag: `--keep <N>` — retain N most recently executed runs.

### tkn taskrun describe

Describe a task run.

```bash
tkn taskrun describe <task_run_name> -n <namespace>
```

### tkn taskrun list

List task runs.

```bash
tkn taskrun list -n <namespace>
```

### tkn taskrun logs

Display task run logs.

```bash
# Stream live logs
tkn taskrun logs -f <task_run_name> -n <namespace>
```

Key flag: `-f` for follow/stream.

## Pipeline Resource Management Commands (`tkn resource`)

### tkn resource

Manage Pipeline Resources.

```bash
tkn resource -h
```

### tkn resource create

Create a Pipeline Resource (interactive — prompts for name, type, and values).

```bash
tkn resource create -n <namespace>
```

### tkn resource delete

Delete a Pipeline Resource.

```bash
tkn resource delete <resource_name> -n <namespace>
```

### tkn resource describe

Describe a Pipeline Resource.

```bash
tkn resource describe <resource_name> -n <namespace>
```

### tkn resource list

List Pipeline Resources.

```bash
tkn resource list -n <namespace>
```

## Trigger Management Commands

### EventListener (`tkn eventlistener`)

```bash
# Display help
tkn eventlistener -h

# Delete EventListeners
tkn eventlistener delete <name_1> <name_2> -n <namespace>

# Describe an EventListener
tkn eventlistener describe <name> -n <namespace>

# List EventListeners
tkn eventlistener list -n <namespace>

# Display logs
tkn eventlistener logs <name> -n <namespace>
```

### TriggerBinding (`tkn triggerbinding`)

```bash
# Display help
tkn triggerbinding -h

# Delete TriggerBindings
tkn triggerbinding delete <name_1> <name_2> -n <namespace>

# Describe a TriggerBinding
tkn triggerbinding describe <name> -n <namespace>

# List TriggerBindings
tkn triggerbinding list -n <namespace>
```

### TriggerTemplate (`tkn triggertemplate`)

```bash
# Display help
tkn triggertemplate -h

# Delete TriggerTemplates
tkn triggertemplate delete <name_1> <name_2> -n <namespace>

# Describe a TriggerTemplate
tkn triggertemplate describe <name> -n <namespace>

# List TriggerTemplates
tkn triggertemplate list -n <namespace>
```

### ClusterTriggerBinding (`tkn clustertriggerbinding`)

Cluster-scoped — no `-n` flag needed.

```bash
# Display help
tkn clustertriggerbinding -h

# Delete ClusterTriggerBindings
tkn clustertriggerbinding delete <name_1> <name_2>

# Describe a ClusterTriggerBinding
tkn clustertriggerbinding describe <name>

# List ClusterTriggerBindings
tkn clustertriggerbinding list
```

## Hub Interaction Commands (`tkn hub`)

### tkn hub

Interact with Tekton Hub.

```bash
# Display help
tkn hub -h

# Specify API server
tkn hub --api-server https://api.hub.tekton.dev
```

### tkn hub downgrade

Downgrade an installed resource to an older version.

```bash
tkn hub downgrade task <name> --to <version> -n <namespace>
```

Key flag: `--to <version>` — target version.

### tkn hub get

Get a resource manifest by name, kind, catalog, and version.

```bash
tkn hub get [pipeline|task] <name> --from <catalog> --version <version>
```

Key flags:
- `--from <catalog>` — source catalog (e.g., `tekton`)
- `--version <version>` — specific version

### tkn hub info

Display information about a resource.

```bash
tkn hub info task <name> --from <catalog> --version <version>
```

### tkn hub install

Install a resource from a catalog.

```bash
tkn hub install task <name> --from <catalog> --version <version> -n <namespace>
```

### tkn hub reinstall

Reinstall a resource.

```bash
tkn hub reinstall task <name> --from <catalog> --version <version> -n <namespace>
```

### tkn hub search

Search for resources by name, kind, or tags.

```bash
tkn hub search --tags <tag>
```

Key flag: `--tags` — filter by tags.

### tkn hub upgrade

Upgrade an installed resource to a new version.

```bash
tkn hub upgrade task <name> --to <version> -n <namespace>
```

Key flag: `--to <version>` — target version.

## Common Flag Reference

| Flag | Scope | Purpose |
|------|-------|---------|
| `-h, --help` | All commands | Display help |
| `-n <namespace>` | Most commands | Target namespace |
| `-f` | logs commands | Follow/stream live logs |
| `-a` | pipelinerun logs | Show all tasks and steps |
| `-s <sa>` | task start | Service account name |
| `--keep <N>` | delete commands | Retain N most recent runs |
| `--all` | delete commands | Delete all (non-running) |
| `--from <catalog>` | hub commands | Source catalog |
| `--version <version>` | hub commands | Specific version |
| `--to <version>` | hub upgrade/downgrade | Target version |
| `--tags <tag>` | hub search | Filter by tags |
| `--api-server <url>` | hub | Hub API server URL |

## Technology Preview: opc

The `opc` CLI tool is bundled with the OpenShift Pipelines installation but is
a Technology Preview feature. It is not supported with Red Hat production SLAs
and may not be functionally complete. Do not use in production environments.
