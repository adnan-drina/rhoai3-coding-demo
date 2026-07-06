# Official Doc Extraction

Use this extraction to keep Pipelines as Code content grounded in official Red
Hat sources. When implementation needs exact CR fields, verify the active cluster
schema with `oc explain` or `oc get crd` before authoring GitOps manifests.

## Repository CR Structure and Configuration

The `Repository` CR is the central PAC resource. It must exist in the namespace
where pipeline runs will execute.

```yaml
apiVersion: "pipelinesascode.tekton.dev/v1alpha1"
kind: Repository
metadata:
  name: project-repository
  namespace: my-pipeline-ci
spec:
  url: "https://github.com/<owner>/<repo>"
  git_provider:
    secret:
      name: "webhook-config"
      key: "provider.token"
    webhook_secret:
      name: "webhook-config"
      key: "webhook.secret"
  settings:
    pipelinerun_provenance: "default_branch"
    github_app_token_scope_repos:
    - "owner/other-repo"
  concurrency_limit: 3
  params:
    - name: company
      value: "My Company"
    - name: registry-url
      value: "registry.example.com"
      filter: pac.event_type == "push"
    - name: secret-param
      secret_ref:
        name: my-secret
        key: value-key
  incoming:
    - targets:
      - main
      secret:
        name: repo-incoming-secret
      type: webhook-url
```

Key behaviors:
- If many Repository CRs match the same event, PAC processes only the oldest one
- Use `pipelinesascode.tekton.dev/target-namespace` annotation to prevent
  malicious targeting of unauthorized namespaces
- Repository CR and referenced secrets must be in the same namespace
- `concurrency_limit` queues excess pipeline runs alphabetically
- `pipelinerun_provenance: "default_branch"` fetches definitions from default
  branch instead of source branch (security best practice)
- Custom `params` support `value`, `secret_ref`, and CEL `filter` fields

## GitHub App Setup and Webhook Configuration

### GitHub App (Recommended)

Three setup methods:

**1. CLI-based:**
```bash
tkn pac bootstrap github-app
# For GitHub Enterprise:
tkn pac bootstrap github-app --github-api-url https://github.com/enterprises/my-enterprise
```

**2. Web console:**
Administrator perspective → Pipelines → Setup GitHub App

**3. Manual setup:**

Required GitHub App permissions:
- Repository: Checks (R/W), Contents (R/W), Issues (R/W), Metadata (Read-only),
  Pull request (R/W)
- Organization: Members (Read-only)

Required event subscriptions: Check run, Check suite, Commit comment, Issue
comment, Pull request, Push

Get webhook URL:
```bash
echo https://$(oc get route -n openshift-pipelines pipelines-as-code-controller -o jsonpath='{.spec.host}')
```

Generate webhook secret:
```bash
openssl rand -hex 20
```

Create the PAC secret:
```bash
oc -n openshift-pipelines create secret generic pipelines-as-code-secret \
  --from-literal github-private-key="$(cat <PATH_PRIVATE_KEY>)" \
  --from-literal github-application-id="<APP_ID>" \
  --from-literal webhook.secret="<WEBHOOK_SECRET>"
```

### GitHub Webhook (Alternative)

Token permissions (fine-grained): Administration (Read-only), Metadata
(Read-only), Content (Read-only), Commit statuses (R/W), Pull request (R/W),
Webhooks (R/W).

Classic token scope: `public_repo` (public) or `repo` (private).

```bash
oc -n target-namespace create secret generic github-webhook-config \
  --from-literal provider.token="<GITHUB_PERSONAL_ACCESS_TOKEN>" \
  --from-literal webhook.secret="<WEBHOOK_SECRET>"
```

```yaml
apiVersion: "pipelinesascode.tekton.dev/v1alpha1"
kind: Repository
metadata:
  name: my-repo
  namespace: target-namespace
spec:
  url: "https://github.com/owner/repo"
  git_provider:
    secret:
      name: "github-webhook-config"
      key: "provider.token"
    webhook_secret:
      name: "github-webhook-config"
      key: "webhook.secret"
```

Limitations: No GitHub Check Runs API; status reported as PR comments; no
`/retest` or `/ok-to-test` support.

### GitLab

Token requirement: Personal access token with `api` scope.

```bash
oc -n target-namespace create secret generic gitlab-webhook-config \
  --from-literal provider.token="<GITLAB_PERSONAL_ACCESS_TOKEN>" \
  --from-literal webhook.secret="<WEBHOOK_SECRET>"
```

```yaml
apiVersion: "pipelinesascode.tekton.dev/v1alpha1"
kind: Repository
metadata:
  name: my-repo
  namespace: target-namespace
spec:
  url: "https://gitlab.com/owner/repo"
  git_provider:
    # url: "https://gitlab.example.com/"  # For private instances
    secret:
      name: "gitlab-webhook-config"
      key: "provider.token"
    webhook_secret:
      name: "gitlab-webhook-config"
      key: "webhook.secret"
```

### Bitbucket Cloud

App password permissions: Pull requests (R/W). Add Webhooks (R/W) for CLI setup.

```bash
oc -n target-namespace create secret generic bitbucket-cloud-token \
  --from-literal provider.token="<BITBUCKET_APP_PASSWORD>"
```

```yaml
apiVersion: "pipelinesascode.tekton.dev/v1alpha1"
kind: Repository
metadata:
  name: my-repo
  namespace: target-namespace
spec:
  url: "https://bitbucket.com/workspace/repo"
  branch: "main"
  git_provider:
    user: "<BITBUCKET_USERNAME>"
    secret:
      name: "bitbucket-cloud-token"
      key: "provider.token"
```

No webhook secret support; IP-based security via
`bitbucket-cloud-check-source-ip` setting.

### Bitbucket Data Center

Token requirement: `PROJECT_ADMIN` and `REPOSITORY_ADMIN` permissions.

```bash
oc -n target-namespace create secret generic bitbucket-datacenter-webhook-config \
  --from-literal provider.token="<PERSONAL_TOKEN>" \
  --from-literal webhook.secret="<WEBHOOK_SECRET>"
```

```yaml
apiVersion: "pipelinesascode.tekton.dev/v1alpha1"
kind: Repository
metadata:
  name: my-repo
  namespace: target-namespace
spec:
  url: "https://bitbucket.com/workspace/repo"
  git_provider:
    url: "https://bitbucket.datacenter.api.url/rest"
    user: "<BITBUCKET_USERNAME>"
    secret:
      name: "bitbucket-datacenter-webhook-config"
      key: "provider.token"
    webhook_secret:
      name: "bitbucket-datacenter-webhook-config"
      key: "webhook.secret"
```

Note: `tkn pac create` and `tkn pac bootstrap` are not supported on Bitbucket
Data Center.

## .tekton Directory Conventions

- Place PipelineRun definitions in `.tekton/` at repository root
- Files must have `.yaml` or `.yml` extension
- Subdirectories are supported for organizing related resources
- PAC processes all PipelineRun definitions that match the triggering event
- Supporting resources (Pipeline, Task, StepAction CRs) can be defined in
  separate files in the same directory
- By default, PAC uses definitions from the source branch of the PR/push
- Set `pipelinerun_provenance: "default_branch"` to always use the default
  branch (security: forces merge review before PAC runs new definitions)

Example directory structure:
```
.tekton/
├── pull-request.yaml      # PipelineRun for PR events
├── push-main.yaml         # PipelineRun for push to main
├── shared-tasks/
│   └── custom-task.yaml   # Reusable task definitions
└── pipeline.yaml          # Shared pipeline definition
```

## PipelineRun Annotation-Based Triggers

### Basic Event Matching

Match pull request targeting main or release branches:
```yaml
apiVersion: tekton.dev/v1
kind: PipelineRun
metadata:
  name: pipeline-pr-main
  annotations:
    pipelinesascode.tekton.dev/on-target-branch: "[main, release-nightly]"
    pipelinesascode.tekton.dev/on-event: "[pull_request]"
```

Match push event:
```yaml
metadata:
  annotations:
    pipelinesascode.tekton.dev/on-target-branch: "[refs/heads/main]"
    pipelinesascode.tekton.dev/on-event: "[push]"
```

Branch specifications support:
- Simple names: `"[main, develop]"`
- Full refs: `"[refs/heads/main]"`
- Globs: `"[refs/heads/*]"`
- Tags: `"[refs/tags/1.*]"`

### Comment Matching (Tech Preview)

```yaml
metadata:
  annotations:
    pipelinesascode.tekton.dev/on-comment: "^/merge-pr"
```

### Path-Based Filtering

```yaml
metadata:
  annotations:
    pipelinesascode.tekton.dev/on-event: "[pull_request]"
    pipelinesascode.tekton.dev/on-target-branch: "[main]"
    pipelinesascode.tekton.dev/on-path-changed: "[src/**, pkg/*]"
    pipelinesascode.tekton.dev/on-path-changed-ignore: "[docs/**]"
```

Wildcards: `*` matches files in directory, `**` matches files in directory and
all subdirectories.

### Label Matching (Tech Preview)

```yaml
metadata:
  annotations:
    pipelinesascode.tekton.dev/on-label: "[bug, defect]"
```

Supported providers: GitHub, Gitea, GitLab.

### Cancel-in-Progress (Tech Preview)

```yaml
metadata:
  annotations:
    pipelinesascode.tekton.dev/cancel-in-progress: "true"
```

### Resolver Annotations

Reference remote tasks from Tekton Hub:
```yaml
metadata:
  annotations:
    pipelinesascode.tekton.dev/task: "[git-clone, golang-test, tkn]"
```

Reference specific version:
```yaml
    pipelinesascode.tekton.dev/task: "[git-clone:0.1]"
```

Reference by URL:
```yaml
    pipelinesascode.tekton.dev/task: "https://remote.url/task.yaml"
```

Reference local file:
```yaml
    pipelinesascode.tekton.dev/task: "share/tasks/git-clone.yaml"
```

Multiple task annotations:
```yaml
    pipelinesascode.tekton.dev/task: "git-clone"
    pipelinesascode.tekton.dev/task-1: "golang-test"
    pipelinesascode.tekton.dev/task-2: "tkn"
```

Reference remote pipeline:
```yaml
    pipelinesascode.tekton.dev/pipeline: "https://git.provider/raw/pipeline.yaml"
```

### Max Keep Runs

```yaml
metadata:
  annotations:
    pipelinesascode.tekton.dev/max-keep-runs: "5"
```

## CEL Expression Support

CEL expressions provide advanced event matching via the
`pipelinesascode.tekton.dev/on-cel-expression` annotation.

### Available Variables

- `event`: `push` or `pull_request`
- `target_branch`: target branch name
- `source_branch`: origin branch (same as target for push)
- `event_title`: commit title (push) or PR title (pull_request)
- `headers['...']`: webhook headers (Tech Preview)
- `body.*`: webhook payload body fields (Tech Preview)

### Suffix Functions

- `.pathChanged()`: glob-based path matching (GitHub and GitLab only)

### Examples

```yaml
# Match PR to main from wip branch
pipelinesascode.tekton.dev/on-cel-expression: |
  event == "pull_request" && target_branch == "main" && source_branch == "wip"

# Match if docs changed
pipelinesascode.tekton.dev/on-cel-expression: |
  event == "pull_request" && "docs/*.md".pathChanged()

# Match PR title prefix
pipelinesascode.tekton.dev/on-cel-expression: |
  event == "pull_request" && event_title.startsWith("[DOWNSTREAM]")

# Skip experimental branch
pipelinesascode.tekton.dev/on-cel-expression: |
  event == "pull_request" && target_branch != "experimental"

# Body-based filtering (Tech Preview)
pipelinesascode.tekton.dev/on-cel-expression: |
  body.pull_request.base.ref == "main" &&
    body.pull_request.user.login == "superuser" &&
    body.action == "synchronize"
```

CEL takes priority over `on-target-branch`, `on-event`, `on-label`, and
path-change annotations when used in the same PipelineRun.

## Dynamic Variables

Use `{{ variable_name }}` syntax in PipelineRun definitions:

| Variable | Description |
|----------|-------------|
| `{{ repo_owner }}` | Repository owner |
| `{{ repo_name }}` | Repository name |
| `{{ repo_url }}` | Repository full URL |
| `{{ revision }}` | Full SHA revision of triggering commit |
| `{{ sender }}` | Username or account ID of sender |
| `{{ source_branch }}` | Branch where event originated |
| `{{ target_branch }}` | Branch the event targets |
| `{{ pull_request_number }}` | PR/MR number (pull_request events only) |
| `{{ git_auth_secret }}` | Auto-generated secret for private repo checkout |

Important: Dynamic variables cannot be used in `default:` fields of pipeline or
task parameters; only in `value:` fields.

### Private Repository Support

PAC auto-creates `pac-gitauth-<OWNER>-<REPO>-<RANDOM>` secrets. Reference in
PipelineRun:

```yaml
workspace:
- name: basic-auth
  secret:
    secretName: "{{ git_auth_secret }}"
```

## tkn pac CLI Commands

### Bootstrap

```bash
tkn pac bootstrap github-app
tkn pac bootstrap github-app --github-api-url https://github.com/enterprises/example
tkn pac bootstrap --route-url <public_url>
```

### Repository Management

```bash
tkn pac create repo                    # Create Repository CR interactively
tkn pac list                           # List all PAC repositories
tkn pac repo describe                  # Describe repository and runs
```

### Pipeline Run Operations

```bash
tkn pac generate                       # Generate pipeline run template
tkn pac resolve .tekton/pr.yaml        # Resolve as PAC would
tkn pac resolve -f .tekton/pr.yaml | oc apply -f -  # Apply resolved run
tkn pac resolve -f .tekton/pr.yaml -p revision=main -p repo_name=myrepo
tkn pac logs -n <namespace> -L         # Follow last pipeline run
tkn pac logs -n <namespace>            # Interactive log selection
```

### Webhook Management

```bash
tkn pac webhook add -n <namespace>           # Add webhook to existing repo
tkn pac webhook update-token -n <namespace>  # Update access token
```

### CEL Evaluation (Tech Preview)

```bash
tkn pac cel -b body.json -H headers.txt [-p github]
echo 'event == "pull_request"' | tkn pac cel -b body.json -H headers.txt
```

## Administration and Configuration Options

### TektonConfig PAC Settings

```yaml
apiVersion: operator.tekton.dev/v1alpha1
kind: TektonConfig
metadata:
  name: config
spec:
  platforms:
    openshift:
      pipelinesAsCode:
        enable: true
        settings:
          application-name: "Pipelines as Code CI"
          secret-auto-create: "true"
          remote-tasks: "true"
          hub-url: "https://api.hub.tekton.dev/v1"
          hub-catalog-name: tekton
          bitbucket-cloud-check-source-ip: "true"
          max-keep-run-upper-limit: ""
          default-max-keep-runs: ""
          auto-configure-new-github-repo: "false"
          auto-configure-repo-namespace-template: "{repo_name}-pipelines"
          error-log-snippet: "true"
          error-log-snippet-number-of-lines: "3"
          error-detection-from-container-logs: "true"
          error-detection-max-number-of-lines: "50"
          secret-github-app-token-scoped: "true"
          secret-github-app-scope-extra-repos: ""
          enable-cancel-in-progress-on-pull-requests: "false"
          enable-cancel-in-progress-on-push: "false"
```

### Additional PAC Controllers (Multiple GitHub Apps)

```yaml
spec:
  platforms:
    openshift:
      pipelinesAsCode:
        additionalPACControllers:
          pac_controller_2:
            enable: true
            secretName: pac_secret_2
            settings:
              # Override settings for this controller
```

Controller name must be unique, max 25 characters.

### Logging Configuration

```yaml
spec:
  platforms:
    openshift:
      pipelinesAsCode:
        options:
          configMaps:
            pac-config-logging:
              data:
                loglevel.pac-watcher: warn
                loglevel.pipelines-as-code-webhook: warn
                loglevel.pipelinesascode: warn
```

View logs filtered by namespace:
```bash
oc logs pipelines-as-code-controller-<pod_id> -n openshift-pipelines | grep <namespace>
```

### Disable/Enable PAC

```bash
# Disable
oc patch tektonconfig config --type="merge" -p '{"spec": {"platforms": {"openshift":{"pipelinesAsCode": {"enable": false}}}}}'

# Enable
oc patch tektonconfig config --type="merge" -p '{"spec": {"platforms": {"openshift":{"pipelinesAsCode": {"enable": true}}}}}'
```

## Incoming Webhooks

Trigger pipeline runs externally without a Git event:

```yaml
apiVersion: "pipelinesascode.tekton.dev/v1alpha1"
kind: Repository
metadata:
  name: repo
  namespace: ns
spec:
  url: "https://github.com/owner/repo"
  git_provider:
    type: github
    secret:
      name: "owner-token"
  incoming:
    - targets:
      - main
      secret:
        name: repo-incoming-secret
      type: webhook-url
```

Secret:
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: repo-incoming-secret
  namespace: ns
type: Opaque
stringData:
  secret: <very_secure_shared_secret>
```

Trigger:
```bash
curl -X POST 'https://control.pac.url/incoming?secret=<secret>&repository=repo&branch=main&pipelinerun=target_pipelinerun'
```

PAC treats incoming webhooks as push events. Status is not reported back;
use `finally` tasks for notifications or inspect the Repository CRD.

## GitOps Comments for Pipeline Control

### Restart Commands
- `/test` — restart all pipeline runs for the PR
- `/retest` — restart all pipeline runs for the PR
- `/test <pipeline_run_name>` — start/restart specific pipeline run
- `/retest <pipeline_run_name>` — start/restart specific pipeline run

### Cancel Commands
- `/cancel` — cancel all pipeline runs
- `/cancel <pipeline_run_name>` — cancel specific pipeline run

### Access Control
- `/ok-to-test` — approve PR from non-collaborator to run pipelines

### Tag-Based Commands
- `/test tag:<tag_name>` — trigger pipeline runs for tagged commit
- `/retest tag:<tag_name>` — retrigger for tagged commit
- `/cancel tag:<tag_name>` — cancel runs for tagged commit

### Authorization
Comment authors must be: repository owner, collaborator, public org member, or
listed in `OWNERS` file (approvers/reviewers section).

## Complete PipelineRun Example

```yaml
apiVersion: tekton.dev/v1
kind: PipelineRun
metadata:
  name: maven-build
  annotations:
    pipelinesascode.tekton.dev/task: "[git-clone]"
    pipelinesascode.tekton.dev/on-event: "[pull_request]"
    pipelinesascode.tekton.dev/on-target-branch: "[main, release]"
    pipelinesascode.tekton.dev/on-path-changed: "[src/**]"
    pipelinesascode.tekton.dev/cancel-in-progress: "true"
    pipelinesascode.tekton.dev/max-keep-runs: "5"
spec:
  pipelineSpec:
    workspaces:
    - name: shared-workspace
    - name: basic-auth
    tasks:
      - name: fetch-repo
        taskRef:
          name: git-clone
        params:
        - name: url
          value: "{{ repo_url }}"
        - name: revision
          value: "{{ revision }}"
        workspaces:
        - name: output
          workspace: shared-workspace
        - name: basic-auth
          workspace: basic-auth
      - name: build-from-source
        runAfter:
        - fetch-repo
        taskRef:
          resolver: cluster
          params:
          - name: kind
            value: task
          - name: name
            value: maven
          - name: namespace
            value: openshift-pipelines
        workspaces:
        - name: source
          workspace: shared-workspace
  workspaces:
  - name: shared-workspace
    volumeClaimTemplate:
      spec:
        accessModes:
        - ReadWriteOnce
        resources:
          requests:
            storage: 1Gi
  - name: basic-auth
    secret:
      secretName: "{{ git_auth_secret }}"
```
