---
name: rhoai-evaluation
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when running, changing or debugging Stage 050 EvalHub evaluations: the
  `EvalHub` CR in namespace `evalhub`, the single tenant `evaluated-models`,
  the MaaS key Secret `evalhub-model-auth-maas`, Kueue queue `lq-cpu-default`,
  custom `agentic-coding-*` collections and `inspect-coding`/`garak-coding`/
  `swebench` providers, the EvalHub MCP server, or OCI result export
  (gitops/stages/050-model-evaluation/). Do NOT use for the MLflow server (use
  rhoai-mlflow), the qualification pipeline server (use rhoai-ai-pipelines),
  or TrustyAI bias and drift monitoring (use rhoai-monitoring-trustyai).
---

# RHOAI Evaluation (EvalHub)

Thin skill: repo decisions and pitfalls here, product behavior in the linked
OpenShift AI 3.5 sections. Detailed record:
`gitops/stages/050-model-evaluation/050-evalhub/README.md` (also
`050-model-qualification/`, `050-evaluation-content/` and `050-oci-export/` READMEs).

## When to use

- An evaluation job fails, scores 0, or never finishes against a MaaS model.
- Adding a provider, collection or qualification gate.
- Granting evaluation access to a user, ServiceAccount or MCP client.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| `EvalHub` CR in dedicated namespace `evalhub`, PostgreSQL 16 StatefulSet, Secret `evalhub-db-credentials` with `db-url` (from `stages/050-model-evaluation/deploy.sh`) | `gitops/stages/050-model-evaluation/050-evalhub/evalhub.yaml` | [Deploy EvalHub][deploy], [Database configuration][dbconf] |
| One admin-only tenant `evaluated-models`; Role `evalhub-evaluator` holds the documented virtual-resource and MLflow `experiments` rules | `gitops/stages/050-model-evaluation/050-model-qualification/access.yaml` | [Set up a tenant][tenant], [Roles][roles] |
| Models reached through MaaS with subscription `model-qualification`; hook mints Secret `evalhub-model-auth-maas` (`api-key`) for `model.auth.secret_ref` | `gitops/stages/050-model-evaluation/050-model-qualification/maas-key-provisioner.yaml` | [API key authentication][apikey] |
| Jobs routed through LocalQueue `lq-cpu-default` (Technology Preview) | `gitops/stages/050-model-evaluation/050-model-qualification/local-queues.yaml` | [Route jobs through Kueue][kueue] |
| Qualification gates are versioned `agentic-coding-*-vN` collections; a new gate is a new `-vN`, never an edit; every id is listed in `spec.providers`/`spec.collections` | `gitops/stages/050-model-evaluation/050-evaluation-content/edd/` | [Collection by ConfigMap][collcm], [Provider by ConfigMap][provcm] |
| MCP server on, with `spec.mcp.authSecret` and `EVALHUB_TENANT=evaluated-models` (not in the guide's procedure); clients use ServiceAccount `evaluated-models/evalhub-automation` | `gitops/stages/050-model-evaluation/050-evalhub/mcp-client-identity.yaml` | [Deploy the MCP server][mcp] |
| OCI export to the internal registry default route, Secret `evalhub-oci-registry` (`kubernetes.io/dockerconfigjson`) | `gitops/stages/050-model-evaluation/050-oci-export/oci-export.yaml` | [Export results to OCI][oci] |
| Catalog safety-insights tab: `get` on `evaluations` in `rhoai-model-registries` for `rhods-admins`, `rhoai-developers`; not a tenant | `gitops/stages/050-model-evaluation/050-evalhub/tenant/` | [Grant access][grant] |
| No LMEvalJob use; LM-Eval is deprecated in 3.5 | none | [Evaluation of AI systems][overview] |

## Procedure

1. Deploy and validate Stage 050 at one SHA:

   ```bash
   ./stages/050-model-evaluation/deploy.sh
   ./stages/050-model-evaluation/validate.sh
   ```

2. Submit from the dashboard **Develop & train → Evaluations** (or the
   documented EvalHub REST API, [Submit][submit]) in tenant `evaluated-models`,
   and record the result as custom properties on the model version in the
   dashboard model version **Properties**. From a terminal, the task scripts
   `stages/050-model-evaluation/evaluation/submit.sh` and `record.sh` do both;
   the former `swebench-run.sh` is in git history at `82092e01`. Check the service after the OpenShift safety
   guard in `AGENTS.md`:

   ```bash
   oc get evalhub evalhub -n evalhub -o jsonpath='{.status.phase} {.status.ready}{"\n"}'
   ```

3. Collections, step times, cleanup and the pipeline flow:
   `docs/OPERATIONS.md#stage-050-governed-evaluations-2026-10-09` and
   `docs/OPERATIONS.md#stage-050-model-qualification-pipeline-2026-10-12`.

## Pitfalls

- The evaluation sidecar aborts each model request after 30 s and the
  lighteval adapter stops after one hour: keep the code-only prompt and
  512-token cap, bound the number of examples, and serve 16 concurrent
  sequences. Per-provider parameters (`tokenizer`, `max_seconds`,
  `max_samples`, `/v1` URLs):
  `docs/TROUBLESHOOTING.md#evalhub-provider-jobs-fail-or-never-finish-against-maas-models`.
- **Start evaluation run** lists only project `InferenceService` objects; MaaS
  models go through **Other (External endpoint)**:
  `docs/TROUBLESHOOTING.md#start-evaluation-run-offers-no-model-to-choose`.
- An id longer than 36 characters stops the new EvalHub pod while the old pod
  keeps serving.
- SWE-bench grading cannot run inside EvalHub on 3.5.1 (adapters get no
  Kubernetes token):
  `docs/TROUBLESHOOTING.md#swe-bench-grading-job-fails-with-invalid-kube-config-file`.
- MCP 401/403: `docs/TROUBLESHOOTING.md#evalhub-mcp-server-returns-403-401-or-forbidden-from-its-tools`.
- The 3.5 dashboard chapter names the flag `disableEvalHub`, but the installed
  3.5.1 `OdhDashboardConfig` schema has only `disableLMEval` (checked with
  `oc explain odhdashboardconfig.spec.dashboardConfig`, 2026-10-15); the repo
  hook sets `disableLMEval: false`. Re-check on each z-stream
  ([dashboard prerequisites][dashprereq]).

## Official documentation (RHOAI 3.5)

| Topic | Section |
|---|---|
| Overview, architecture | [EvalHub][evalhub], [Architecture][arch] |
| SDK and CLI | [Install the SDK and CLI][sdk] |
| Jobs | [Submit][submit], [Track][track], [Cancel and delete][cancel], [Job fields][jobfields] |
| Built-in collections | [Built-in collections][builtin] |
| Data | [S3 data][s3], [PVC data][pvc] |
| MLflow tracking | [MLflow experiment tracking][mlflow] |
| Multi-tenancy | [Multi-tenancy and RBAC][rbac] |
| Dashboard | [Evaluate with the dashboard][dashboard] |
| Evaluation cards | [Evaluation cards][cards] |
| Risk assessment (Garak) | [Automated risk assessment][risk] |

## Related skills

`rhoai-mlflow`, `rhoai-ai-pipelines`, `rhoai-maas-governance`,
`rhoai-kueue-workload-management`, `rhoai-model-registry-workflows`,
`rhoai-model-evaluation`, `rhoai-guardrails-safety`.

[overview]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/evaluating_ai_systems/index#overview-evaluating-ai-systems_evaluate
[evalhub]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/evaluating_ai_systems/index#evalhub-overview_evaluate
[arch]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/evaluating_ai_systems/index#evalhub-architecture-overview_evaluate
[deploy]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/evaluating_ai_systems/index#evalhub-deploy-with-the-trustyai-operator_evaluate
[sdk]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/evaluating_ai_systems/index#evalhub-install-the-evalhub-sdk-and-cli_evaluate
[kueue]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/evaluating_ai_systems/index#evalhub-route-evaluation-jobs-through-kueue_evaluate
[submit]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/evaluating_ai_systems/index#evalhub-submit-an-evaluation-job_evaluate
[track]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/evaluating_ai_systems/index#evalhub-track-evaluation-jobs-and-results_evaluate
[cancel]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/evaluating_ai_systems/index#evalhub-cancel-and-delete-jobs_evaluate
[builtin]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/evaluating_ai_systems/index#evalhub-built-in-collections_evaluate
[apikey]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/evaluating_ai_systems/index#evalhub-configure-api-key-authentication_evaluate
[s3]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/evaluating_ai_systems/index#evalhub-use-custom-data-from-s3_evaluate
[pvc]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/evaluating_ai_systems/index#evalhub-provide-evaluation-test-data-from-pvc_evaluate
[oci]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/evaluating_ai_systems/index#evalhub-export-evaluation-results-to-oci-registry_evaluate
[mlflow]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/evaluating_ai_systems/index#evalhub-configure-mlflow-experiment-tracking_evaluate
[provcm]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/evaluating_ai_systems/index#evalhub-add-a-custom-provider-configmap_evaluate
[collcm]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/evaluating_ai_systems/index#evalhub-add-a-collection-configmap_evaluate
[jobfields]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/evaluating_ai_systems/index#job_submission_fields
[dbconf]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/evaluating_ai_systems/index#database_configuration
[rbac]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/evaluating_ai_systems/index#evalhub-multi-tenancy-and-rbac_evaluate
[tenant]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/evaluating_ai_systems/index#evalhub-set-up-a-tenant-namespace_evaluate
[grant]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/evaluating_ai_systems/index#evalhub-grant-access-to-evalhub_evaluate
[roles]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/evaluating_ai_systems/index#evalhub-roles-reference_evaluate
[dashboard]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/evaluating_ai_systems/index#evalhub-use-the-dashboard-to-evaluate-your-system_evaluate
[dashprereq]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/evaluating_ai_systems/index#prerequisites
[mcp]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/evaluating_ai_systems/index#evalhub-deploy-mcp-server_evaluate
[cards]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/evaluating_ai_systems/index#evalhub-evaluation-cards_evaluate
[risk]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/evaluating_ai_systems/index#test-model-safety-with-automated-risk-assessment_evaluate
