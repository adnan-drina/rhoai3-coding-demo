---
name: ocp-pipelines-as-code
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "ocp"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Platform"
description: >
  Use when configuring or using Pipelines as Code (PAC): GitHub App setup,
  webhook configuration, Repository CR, .tekton directory conventions,
  PipelineRun templates, CEL expressions, on-event and on-target-branch
  annotations, incoming webhooks, Git provider integration (GitHub, GitLab,
  Bitbucket), tkn pac CLI, and Pipelines as Code administration for OpenShift
  Pipelines 1.22. Do NOT use for core pipeline concepts (use
  ocp-pipelines-about), installing pipelines (use ocp-pipelines-install-config),
  creating CI/CD pipelines without PAC (use ocp-pipelines-cicd), or security
  (use ocp-pipelines-security).
---

# OCP Pipelines as Code

Use this skill to ground Pipelines as Code (PAC) guidance in the
official Red Hat OpenShift Pipelines 1.22 PAC guide for the active
baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority.

## Repository Custom Resource

The `Repository` CR (`pipelinesascode.tekton.dev/v1alpha1`) is the central
configuration object. It:

- Tells PAC which Git URL to process events from
- Determines the namespace where PipelineRuns execute
- References secrets for Git provider authentication
- Stores last pipeline run status
- Supports `concurrency_limit`, `pipelinerun_provenance`, custom `params`, and
  `incoming` webhook configuration

Key fields: `spec.url`, `spec.git_provider`, `spec.settings`,
`spec.concurrency_limit`, `spec.incoming`, `spec.params`.

## GitHub App Integration

GitHub App is the recommended integration method. Setup options:

1. `tkn pac bootstrap github-app` (CLI-based, main controller only)
2. Administrator perspective in OpenShift web console (main controller only)
3. Manual GitHub App creation + secret (`pipelines-as-code-secret`)

Required permissions: Checks (R/W), Contents (R/W), Issues (R/W), Metadata
(Read-only), Pull request (R/W), Organization Members (Read-only).

Required event subscriptions: Check run, Check suite, Commit comment, Issue
comment, Pull request, Push.

## Webhook Integration (GitHub, GitLab, Bitbucket)

For environments where a GitHub App is not feasible:

- **GitHub Webhook**: Uses personal access token; no Checks API; status reported
  as PR comments; no `/retest` or `/ok-to-test` support.
- **GitLab**: Personal access token with `api` scope; webhook URL points to PAC
  controller route.
- **Bitbucket Cloud**: App password with Pull requests R/W; IP-based security
  (no webhook secret support).
- **Bitbucket Data Center**: Personal token with `PROJECT_ADMIN` and
  `REPOSITORY_ADMIN` permissions.

## .tekton Directory Conventions

- Pipeline run definitions live in `.tekton/` at repository root
- Files must have `.yaml` or `.yml` extension
- PAC processes all matching PipelineRun definitions in the directory
- Definitions can reference other YAML files in the same directory
- By default, PAC uses definitions from the source branch of the event; set
  `pipelinerun_provenance: "default_branch"` for security

## PipelineRun Annotation-Based Triggers

### Event Matching

| Annotation | Purpose |
|------------|---------|
| `pipelinesascode.tekton.dev/on-event` | Match `pull_request` or `push` |
| `pipelinesascode.tekton.dev/on-target-branch` | Target branch (supports globs, refs, tags) |
| `pipelinesascode.tekton.dev/on-comment` | Match PR comment by regex (Tech Preview) |
| `pipelinesascode.tekton.dev/on-cel-expression` | CEL-based advanced filtering |

### Event Filtering

| Annotation | Purpose |
|------------|---------|
| `pipelinesascode.tekton.dev/on-path-changed` | Match if listed paths changed |
| `pipelinesascode.tekton.dev/on-path-changed-ignore` | Exclude if only listed paths changed |
| `pipelinesascode.tekton.dev/on-label` | Match PR labels (Tech Preview) |

### Pipeline Run Control

| Annotation | Purpose |
|------------|---------|
| `pipelinesascode.tekton.dev/max-keep-runs` | Retain N most recent runs |
| `pipelinesascode.tekton.dev/cancel-in-progress` | Cancel older runs on new push (Tech Preview) |
| `pipelinesascode.tekton.dev/target-namespace` | Explicit namespace targeting |

### Resolver Annotations

| Annotation | Purpose |
|------------|---------|
| `pipelinesascode.tekton.dev/task` | Reference remote tasks (Hub, URL, local path) |
| `pipelinesascode.tekton.dev/task-N` | Additional task references |
| `pipelinesascode.tekton.dev/pipeline` | Reference remote pipeline definition |

## CEL Expression Support

CEL expressions enable advanced event filtering. Available variables:

- `event`: `push` or `pull_request`
- `target_branch`: target branch name
- `source_branch`: origin branch name
- `event_title`: commit title or PR title
- `.pathChanged()`: suffix function for glob-based path matching
- `headers['...']`: webhook payload headers (Tech Preview)
- `body.*`: webhook payload body fields (Tech Preview)

CEL takes priority over `on-target-branch`, `on-event`, `on-label`, and
path-based annotations when used in the same PipelineRun.

## Dynamic Variables

| Variable | Value |
|----------|-------|
| `{{ repo_owner }}` | Repository owner |
| `{{ repo_name }}` | Repository name |
| `{{ repo_url }}` | Repository full URL |
| `{{ revision }}` | Full SHA of triggering commit |
| `{{ sender }}` | Username of commit sender |
| `{{ source_branch }}` | Branch where event originated |
| `{{ target_branch }}` | Branch event targets |
| `{{ pull_request_number }}` | PR/MR number (pull_request only) |
| `{{ git_auth_secret }}` | Auto-generated auth secret name |

## tkn pac CLI Commands

| Command | Description |
|---------|-------------|
| `tkn pac bootstrap github-app` | Create GitHub App and configure PAC |
| `tkn pac create repo` | Create Repository CR and configure webhook |
| `tkn pac list` | List all PAC repositories |
| `tkn pac repo describe` | Describe repository and associated runs |
| `tkn pac generate` | Generate pipeline run template with language detection |
| `tkn pac resolve` | Resolve pipeline run as PAC would execute it |
| `tkn pac logs -n <ns> -L` | Follow last pipeline run logs |
| `tkn pac webhook add` | Add webhook to existing Repository CR |
| `tkn pac webhook update-token` | Update personal access token |
| `tkn pac cel` | Evaluate CEL expressions against payloads (Tech Preview) |

## Administration and Configuration

PAC is configured via `TektonConfig` CR under
`spec.platforms.openshift.pipelinesAsCode`:

- `enable`: Enable/disable PAC installation
- `settings`: Key-value configuration parameters
- `additionalPACControllers`: Support multiple GitHub Apps
- `options.configMaps.pac-config-logging`: Logging configuration

Key settings: `application-name`, `secret-auto-create`, `remote-tasks`,
`hub-url`, `hub-catalog-name`, `max-keep-run-upper-limit`,
`default-max-keep-runs`, `auto-configure-new-github-repo`,
`error-log-snippet`, `error-detection-from-container-logs`,
`secret-github-app-token-scoped`, `secret-github-app-scope-extra-repos`,
`enable-cancel-in-progress-on-pull-requests`,
`enable-cancel-in-progress-on-push`.

## Incoming Webhooks

Trigger pipeline runs externally without a Git event:

```yaml
spec:
  incoming:
    - targets:
      - main
      secret:
        name: repo-incoming-secret
      type: webhook-url
```

Trigger with:
```bash
curl -X POST 'https://control.pac.url/incoming?secret=<secret>&repository=<repo>&branch=<branch>&pipelinerun=<name>'
```

## GitOps Comments

| Command | Effect |
|---------|--------|
| `/test` | Restart all pipeline runs |
| `/retest` | Restart all pipeline runs |
| `/test <name>` | Start/restart specific pipeline run |
| `/cancel` | Cancel all pipeline runs |
| `/cancel <name>` | Cancel specific pipeline run |
| `/ok-to-test` | Approve PR from non-collaborator |

## Workflow

1. Confirm the active OpenShift baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md`.
3. Identify the PAC integration pattern (GitHub App, webhook, incoming).
4. For GitOps manifests, verify Repository CR and TektonConfig fields against
   the extraction before committing.
5. For live operations, use the repo environment guard.
6. Validate with `references/source-capture.md` boundaries.

## Related Skills

- Use `ocp-pipelines-about` for core Tekton concepts and CRDs.
- Use `ocp-pipelines-install-config` for installation and configuration.
- Use `ocp-pipelines-cicd` for creating CI/CD solutions without PAC.
- Use `ocp-pipelines-security` for pipeline security concerns.
- Use `ocp-pipelines-observability` for pipeline monitoring.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
