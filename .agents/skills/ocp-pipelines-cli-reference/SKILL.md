---
name: ocp-pipelines-cli-reference
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "ocp"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Platform"
description: >
  Use when referencing tkn CLI commands for OpenShift Pipelines: tkn pipeline,
  tkn pipelinerun, tkn task, tkn taskrun, tkn clustertask, tkn hub,
  tkn triggerbinding, tkn triggertemplate, tkn eventlistener, tkn condition,
  opc results, and CLI installation for OpenShift Pipelines 1.22. Do NOT use
  for pipeline concepts (use ocp-pipelines-about), installing the operator
  (use ocp-pipelines-install-config), or creating CI/CD pipelines (use
  ocp-pipelines-cicd).
---

# OCP Pipelines CLI Reference

Use this skill to ground tkn CLI command reference in the
official Red Hat OpenShift Pipelines 1.22 CLI reference for the active
baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority.

## CLI Command Groups

### Installation

- `tkn` — available via tar.gz archive (Linux, macOS, Windows) or RPM
- `tkn-pac` — Pipelines as Code CLI (bundled)
- `opc` — OpenShift Pipelines Client (Technology Preview, bundled)

### Utility Commands

- `tkn` — parent command, displays all options
- `tkn completion [bash|zsh]` — shell prompt completion code
- `tkn version` — print version information

### Pipeline Management (`tkn pipeline`)

- `tkn pipeline --help` — display help
- `tkn pipeline delete <name> -n <namespace>` — delete a pipeline
- `tkn pipeline describe <name>` — describe a pipeline
- `tkn pipeline list` — list pipelines
- `tkn pipeline logs -f <name>` — stream live logs
- `tkn pipeline start <name>` — start a pipeline

### Pipeline Run Management (`tkn pipelinerun`)

- `tkn pipelinerun -h` — display help
- `tkn pipelinerun cancel <name> -n <namespace>` — cancel a pipeline run
- `tkn pipelinerun delete <name1> <name2> -n <namespace>` — delete runs
- `tkn pipelinerun delete -n <namespace> --keep 5` — delete all except N most recent
- `tkn pipelinerun delete --all` — delete all (skips running since Pipelines 1.6)
- `tkn pipelinerun describe <name> -n <namespace>` — describe a run
- `tkn pipelinerun list -n <namespace>` — list runs
- `tkn pipelinerun logs <name> -a -n <namespace>` — display all task/step logs

### Task Management (`tkn task`)

- `tkn task -h` — display help
- `tkn task delete <name1> <name2> -n <namespace>` — delete tasks
- `tkn task describe <name> -n <namespace>` — describe a task
- `tkn task list -n <namespace>` — list tasks
- `tkn task start <name> -s <service_account> -n <namespace>` — start a task

### Task Run Management (`tkn taskrun`)

- `tkn taskrun -h` — display help
- `tkn taskrun cancel <name> -n <namespace>` — cancel a task run
- `tkn taskrun delete <name1> <name2> -n <namespace>` — delete task runs
- `tkn taskrun delete -n <namespace> --keep 5` — delete all except N most recent
- `tkn taskrun describe <name> -n <namespace>` — describe a task run
- `tkn taskrun list -n <namespace>` — list task runs
- `tkn taskrun logs -f <name> -n <namespace>` — display live logs

### Pipeline Resource Management (`tkn resource`)

- `tkn resource -h` — display help
- `tkn resource create -n <namespace>` — create (interactive)
- `tkn resource delete <name> -n <namespace>` — delete
- `tkn resource describe <name> -n <namespace>` — describe
- `tkn resource list -n <namespace>` — list

### Trigger Management

#### EventListener (`tkn eventlistener`)

- `tkn eventlistener -h` — display help
- `tkn eventlistener delete <name1> <name2> -n <namespace>` — delete
- `tkn eventlistener describe <name> -n <namespace>` — describe
- `tkn eventlistener list -n <namespace>` — list
- `tkn eventlistener logs <name> -n <namespace>` — display logs

#### TriggerBinding (`tkn triggerbinding`)

- `tkn triggerbinding -h` — display help
- `tkn triggerbinding delete <name1> <name2> -n <namespace>` — delete
- `tkn triggerbinding describe <name> -n <namespace>` — describe
- `tkn triggerbinding list -n <namespace>` — list

#### TriggerTemplate (`tkn triggertemplate`)

- `tkn triggertemplate -h` — display help
- `tkn triggertemplate delete <name1> <name2> -n <namespace>` — delete
- `tkn triggertemplate describe <name> -n <namespace>` — describe
- `tkn triggertemplate list -n <namespace>` — list

#### ClusterTriggerBinding (`tkn clustertriggerbinding`)

- `tkn clustertriggerbinding -h` — display help
- `tkn clustertriggerbinding delete <name1> <name2>` — delete (cluster-scoped)
- `tkn clustertriggerbinding describe <name>` — describe
- `tkn clustertriggerbinding list` — list all

### Hub Interaction (`tkn hub`)

- `tkn hub -h` — display help
- `tkn hub --api-server <url>` — interact with a hub API server
- `tkn hub downgrade task <name> --to <version> -n <namespace>` — downgrade resource
- `tkn hub get [pipeline|task] <name> --from <catalog> --version <version>` — get manifest
- `tkn hub info task <name> --from <catalog> --version <version>` — display info
- `tkn hub install task <name> --from <catalog> --version <version> -n <namespace>` — install
- `tkn hub reinstall task <name> --from <catalog> --version <version> -n <namespace>` — reinstall
- `tkn hub search --tags <tag>` — search by tags
- `tkn hub upgrade task <name> --to <version> -n <namespace>` — upgrade resource

## Global Options

- `--help, -h` — display help for any command
- `-n <namespace>` — target namespace (available on most commands)

## Key Behaviors

- `tkn pipelinerun delete --all` does not delete running resources (since Pipelines 1.6)
- `tkn resource create` is interactive and prompts for resource type and values
- `tkn hub` commands require a Tekton Hub API server (default: api.hub.tekton.dev)
- `opc` is Technology Preview and not supported for production use
- Tab completion is available for bash and zsh via `tkn completion`

## Workflow

1. Confirm the active OpenShift baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md` for full command details.
3. Identify the relevant command group (pipeline, task, trigger, hub).
4. Use the exact command syntax documented above.
5. For live operations, use the repo environment guard.
6. Validate with `references/source-capture.md` boundaries.

## Related Skills

- Use `ocp-pipelines-about` for pipeline concepts and Tekton CRDs.
- Use `ocp-pipelines-install-config` for installing the operator.
- Use `ocp-pipelines-release-notes` for release notes and known issues.
- Use `ocp-cicd-builds` for OpenShift Builds (BuildConfig, Shipwright).

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
