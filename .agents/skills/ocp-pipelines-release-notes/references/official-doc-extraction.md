# Official Doc Extraction

Use this extraction to keep OpenShift Pipelines release information grounded in
the official Red Hat OpenShift Pipelines 1.22 release notes. All version
numbers, component names, and behavioral changes are taken directly from the
official documentation.

## Compatibility and Support Matrix

### OpenShift Pipelines 1.22

| Component | Version | Support Status |
|-----------|---------|----------------|
| Operator | 1.22 | GA |
| Pipelines | 1.9.x | GA |
| Triggers | 0.35.x | GA |
| CLI | 0.44.x | GA |
| Chains | 0.26.x | GA |
| Hub | 1.23.x | TP |
| Pipelines as Code | 0.42.x | GA |
| Results | 0.18.x | GA |
| Manual Approval Gate | 0.8.x | TP |
| Pruner | 0.3.x | GA |
| Cache | 0.3.x | GA |

Supported OCP versions: 4.14, 4.16, 4.17, 4.18, 4.19, 4.20, 4.21, 4.22

### Previous Versions (for upgrade context)

| Operator | Pipelines | Triggers | CLI | Chains | Hub | PaC | Results | MAG | Pruner | Cache | OCP Versions |
|----------|-----------|----------|-----|--------|-----|-----|---------|-----|--------|-------|--------------|
| 1.21 | 1.6.x | 0.34.x | 0.43.x | 0.26.x (GA) | 1.23.x (TP) | 0.39.x (GA) | 0.17.x (GA) | 0.7.x (TP) | 0.3.x (GA) | 0.3.x (GA) | 4.14–4.21 |
| 1.20 | 1.3.x | 0.33.x | 0.42.x | 0.25.x (GA) | 1.22.x (TP) | 0.37.x (GA) | 0.16.x (GA) | 0.6.x (TP) | 0.2.x (TP) | 0.2.x (TP) | 4.14–4.21 |

The console plugin for OpenShift Pipelines follows the same version as the
Operator.

## Release Notes for 1.22.4

Available on OCP 4.14, 4.16, and later.

### Fixed Issues

- **Multicluster proxy permissions consolidated**: removed orphaned
  `tekton-multicluster-proxy-aae-role` role and
  `tekton-multicluster-proxy-aae-rolebinding` role binding that were created
  even when multicluster was disabled. Permissions moved to
  `tekton-scheduler-role`. (SRVKP-12211)

## Release Notes for 1.22.3

Available on OCP 4.14, 4.16, and later.

### Fixed Issues

- **UI: current status column rendering** — fixed overlapping text in the
  Current status column. (SRVKP-9448)
- **Security: webhook request validation for GitHub App credentials** — forged
  HTTP headers could trick Pipelines as Code into sending GitHub App
  credentials to attacker-controlled servers. Fixed by validating webhook
  requests. Upgrade recommended. (SRVKP-12216)
- **CEL expression evaluation on Bitbucket Cloud** — CEL expressions now
  evaluate correctly; previously PipelineRuns using
  `pipelinesascode.tekton.dev/on-cel-expression` were skipped with parsing
  errors. (SRVKP-9635)
- **Security: GitHub App installation token scoping** — tokens are now scoped
  to only the triggering repository by default. Additional repositories require
  explicit configuration via `secret-github-app-scope-extra-repos` in the
  `pipelines-as-code` ConfigMap. Also fixes a bug where cached remote Pipeline
  and Task objects could be mutated during inlining. (SRVKP-12241)

## Release Notes for 1.22.2

Available on OCP 4.14, 4.16, and later.

### New Features and Enhancements

- **Pipelines as Code: webhook signature validation for Forgejo and Gitea** —
  enforces validation that was previously skipped, preventing unauthenticated
  or spoofed requests. (SRVKP-10609)
- **UI: console plugin upgraded to React 18 and PatternFly 6** — ensures
  compatibility with OCP 4.22 and later. No functional workflow changes.
  (SRVKP-9276, SRVKP-9273)

## Release Notes for 1.22.1

Available on OCP 4.14, 4.16, and later. Stability release with no separately
documented features or fixes.

## Release Notes for 1.22 (Initial GA)

Available on OCP 4.14 and later supported versions.

### New Features and Enhancements

#### Pipelines

- **hostUsers support in podTemplate** — enables Kubernetes-native user
  namespace isolation on OCP 4.20+ without legacy CRI-O annotations.
  (SRVKP-9726)
- **HTTP resolver hash verification** — optional `hash` parameter accepts
  SHA-256 or SHA-512 for content integrity verification. (SRVKP-8511)
- **Resolver caching** — bundle, git, and cluster resolvers support caching
  in three modes: `always`, `never`, `auto` (default). Configurable globally
  via resolver config maps or per task via `cache` parameter. (SRVKP-7037)
- **Array values in `when` expressions** — array values can be resolved in
  the `input` attribute. (SRVKP-11214)
- **Step display names** — `displayName` field on step objects improves
  readability. (SRVKP-11214)
- **Pipelines-in-pipelines** — embedded pipelines via `PipelineSpec` field
  under tasks. (SRVKP-11214)
- **Concurrent StepAction resolution** — StepActions resolved concurrently
  instead of sequentially, reducing startup time. (SRVKP-11214)
- **PVC quota resilience** — PipelineRuns requeue when PVC quota is hit instead
  of failing immediately. (SRVKP-11214)
- **Per-task timeout overrides** — individual task timeouts can be overridden at
  PipelineRun level via `spec.taskRunSpecs[].timeout`. (SRVKP-11214)

#### Operator

- **ServiceMonitor for Results and webhook** — Operator creates
  `ServiceMonitor` resources for Tekton Results and
  `tekton-pipelines-webhook`, enabling automatic Prometheus discovery.
  (SRVKP-7683)

#### Pipelines as Code

- **Changed-file caching** — caches file list per event to reduce VCS API
  calls when evaluating `path.pathChanged()` or `on-path-change`.
  (SRVKP-9228)
- **Update comment strategy** — new `update` strategy for GitLab and GitHub
  maintains a single status comment instead of posting multiple comments.
  (SRVKP-9998)
- **Skip-CI commit tags** — case-insensitive tags `[skip ci]`, `[ci skip]`,
  `[skip tkn]`, `[tkn skip]` prevent pipeline execution. Note: GitLab shows
  one additional pipeline entry for the same commit SHA. (SRVKP-11542,
  SRVKP-8933)
- **Glob pattern support for GitHub App token scoping** — wildcard patterns
  like `my-org/*` supported in global config maps and repository-level
  configurations. (SRVKP-10030)
- **Webhook signature validation for Forgejo and Gitea** — enforces
  validation that was previously skipped. (SRVKP-10609)
- **CEL expressions in pipeline templates** — `cel:` prefix for inline
  logic including ternary operators, presence checks, and string
  compositions. (SRVKP-9979)
- **Optimized GitHub API calls** — GraphQL API for batched .tekton file
  retrieval instead of individual REST calls. (SRVKP-11470)

#### User Interface

- **ANSI color support** — log viewer supports ANSI color codes for TaskRun
  and PipelineRun logs. (SRVKP-10407)

### Technology Preview Features

- **Multi-cluster configuration in TektonConfig** — `scheduler` section with
  `multi-cluster-disabled` and `multi-cluster-role` (Hub or Spoke) fields.
  (SRVKP-8979)
- **Automatic scaling for Tekton Results in Hub mode** — `tekton-results-watcher`
  and `tekton-results-retention-policy-agent` replicas set to zero on Hub when
  multicluster is enabled. (SRVKP-8983)
- **Tekton Scheduler (Tekton-Kueue)** — new `scheduler` section in
  TektonConfig CR. Requires upstream Kueue. (SRVKP-10005)
- **Federated PipelineRun UI indicator** — icon distinguishes local hub
  PipelineRun from federated PipelineRun based on `managedBy` field.
  (SRVKP-10807)

### Breaking Changes

- **Legacy static console plugin removed** — the limited Pipelines navigation
  entry that appeared when the console plugin was disabled is no longer
  supported. Console plugin must be explicitly enabled. (SRVKP-9456)

### Known Issues

- **buildah-ns task fails on OCP 4.20+** — the CRI-O annotation-based user
  namespace mechanism `io.kubernetes.cri-o.userns-mode: "auto"` was removed
  in OCP 4.20. Workaround: use standard `buildah` task with
  `hostUsers: false` in PodTemplate. (SRVKP-9256)
- **tkn CLI limited in multicluster** — `tkn taskrun list`,
  `tkn pipelinerun describe`, `tkn pipelinerun logs`, and
  `tkn pipelinerun cancel` fail on Hub. On Spoke, list commands only work
  while runs are active. (SRVKP-10629)
- **opc results logs get limits output to 300 lines** — use
  `opc results pipelinerun logs` or `opc results taskrun logs` instead.
  (SRVKP-11362)

### Fixed Issues

#### Pipelines

- Affinity Assistant pods inherit PipelineRun service account instead of
  `default`. (SRVKP-7327)
- Misconfigured TaskRun pods fail early with clear error messages instead of
  silent timeouts. (SRVKP-9987)
- Pipeline runs without timeouts no longer cause excessive reconciliation and
  CPU usage. (SRVKP-9988)
- Pipeline parameter defaults correctly resolve references to other
  parameters, including circular dependency detection. (SRVKP-9989)
- PipelineRuns retry on retryable TaskRef reconciliation errors instead of
  failing. (SRVKP-11214)
- Kubernetes-native sidecars correctly handle signals. (SRVKP-11214)
- TaskRun pods retained when timeouts occur with `keep-pod-on-cancel` enabled.
  (SRVKP-11214)
- StepAction status displays in correct order. (SRVKP-11214)
- Task runs execute successfully on arm64 clusters. (SRVKP-11214)
- Pipeline run status updates reduce API server load via consistent array
  ordering. (SRVKP-11214)

#### Operator

- Webhooks (`proxy.operator.tekton.dev`, `validation.pipelinesascode.tekton.dev`,
  `namespace.operator.tekton.dev`) cleaned up when Operator namespace is
  deleted. (SRVKP-8901)
- Prometheus metrics collection works when Operator is in a custom namespace.
  (SRVKP-10509)

#### Pipelines as Code

- Custom parameters supported in CEL expressions via Repository CR.
  (SRVKP-10082)
- `[skip ci]` respected in GitLab merge requests. (SRVKP-10440)
- Non-HTTP(S) pipeline URLs no longer cause "invalid port" errors.
  (SRVKP-10880)
- `tkn pac cel` command enforces required flags. (SRVKP-9400)
- `pull_request_number` variable reliably populated for push events via
  exponential backoff retry. (SRVKP-9474)
- GitLab push events evaluate all modified files (pagination fix).
  (SRVKP-9708)
- GitLab commit statuses correctly reflect pipeline state. (SRVKP-9459)
- GitLab MR comments limited to permission failures only. (SRVKP-9442)
- `tkn pac cel` handles invalid GitLab input safely (nil pointer fix).
  (SRVKP-9396)
- `/ok-to-test` approval re-evaluated per commit when `remember-ok-to-test=false`.
  (SRVKP-9200)
- Skipped push events logged at `info` instead of `error`. (SRVKP-8909)
- Bitbucket Cloud shows individual status per pipeline run. (SRVKP-9636)
- CEL expressions correctly evaluate pull request label events. (SRVKP-8491)
- Deleted or canceled PipelineRuns update Git provider commit status.
  (SRVKP-8318)

#### User Interface

- Pipeline run logs preserve whitespace and provide horizontal scrolling.
  (SRVKP-10035)
- TaskSidebar displays correctly in Pipeline Builder. (SRVKP-11533)

### Deprecated Features

- **openshift-pipelines-client RPM** — deprecated, may be removed in Pipelines
  1.23. (SRVKP-9444)
- **pipelinerun_status field in Repository CR** — deprecated, may be removed
  in Pipelines 1.23. (SRVKP-9223)

### Removed Features

- **disable-affinity-assistant field** — removed from TektonConfig
  `spec.pipeline`. Migrate to `coschedule` feature flag. (SRVKP-8267)
- **Public Tekton Hub as default catalog** — hub.tekton.dev removed and no
  longer supported. Use custom self-hosted Tekton Hub instances.
  (SRVKP-11213)
