# Validation Checklist

Use this checklist before accepting official RHOAI evaluation README content,
GitOps manifests, SDK examples, CLI commands, notebooks, runbooks, or demo
scripts.

## Source Alignment

- Product links use the active baseline in `docs/PLATFORM_BASELINE.md`.
- The official Evaluating AI systems source is recorded when official
  EvalHub, LM-Eval, or risk-assessment behavior is introduced.
- Legacy repo-specific Step 08 or RAGAS behavior is checked with
  `rhoai-model-evaluation`, not treated as product docs.
- MLflow tracking behavior is checked with `rhoai-mlflow`.
- AI Pipelines and KFP behavior is checked with `rhoai-ai-pipelines` and
  `rhoai-kfp-pipeline-authoring`.
- Model endpoint behavior is checked with `rhoai-model-serving-platform`.
- S3 credential and object-store behavior is checked with
  `rhoai-s3-object-storage-data`.
- API support posture is checked with `rhoai-api-tiers` when API stability
  matters.

## EvalHub Deployment Review

- TrustyAI component is `Managed` in the active `DataScienceCluster`.
- KServe `RawDeployment` requirement is satisfied before EvalHub deployment.
- EvalHub uses a dedicated namespace unless a documented exception exists.
- PostgreSQL Secret contains `db-url` and is not committed with real
  credentials.
- `EvalHub` custom resource fields are verified against official docs or
  `oc explain`.
- Provider and collection lists are intentional.
- MLflow and OpenTelemetry configuration are enabled only when dependencies
  and credentials are ready.
- EvalHub authentication is not disabled in shared or production-shaped demo
  environments.
- Health endpoint and provider listing are verified after deployment.

## EvalHub Tenant And Job Review

- Tenant namespace is explicit.
- `X-Tenant` header, CLI tenant, or SDK tenant matches the intended namespace.
- ServiceAccounts and RoleBindings grant only required access.
- Model endpoint authentication uses Secrets or ServiceAccount tokens.
- Provider, benchmark, collection, pass criteria, and threshold choices are
  meaningful for the model claim being evaluated.
- Job state transitions and results are captured.
- Cancel versus hard delete behavior is understood before deleting jobs.
- Custom providers, adapters, collections, and ConfigMaps are reviewed as code.
- OCI export and MLflow tracking destinations have credential, retention, and
  ownership notes.

## LM-Eval Review

- `LMEvalJob` API version and fields are verified against active CRD schema.
- Online access is enabled only when required.
- Remote code execution is enabled only when required and explicitly justified.
- Hugging Face tokens and model endpoint tokens are stored in Secrets.
- Custom Unitxt cards, templates, system prompts, and LLM-as-a-judge metrics
  are reviewed as code.
- PVC or S3 storage is intentionally selected and accessible.
- S3 Secrets contain required AWS-style keys.
- KServe/vLLM evaluations use the correct endpoint path.
- Dashboard evaluations are treated as product workflow evidence, not as a
  substitute for custom business validation unless the README says so.

## Risk Assessment Review

- Pipeline server exists before risk assessment is promised.
- Target, judge, SDG, attacker, and evaluator model endpoints are documented
  and OpenAI-compatible.
- Target model and judge model are not accidentally the same unless explicitly
  justified.
- Model API keys and S3 credentials are stored in Kubernetes Secrets.
- Benchmark ID is `intents` and provider ID is `garak-kfp`.
- KFP endpoint, namespace, S3 Secret, bucket, prefix, and TLS settings match
  the target environment.
- Disconnected clusters either use pre-downloaded translation models in S3 or
  disable the translation attack strategy.
- Custom harm categories, policy taxonomy CSVs, and intents CSVs are reviewed
  before use.
- MLflow experiment grouping is set when comparing risk assessments over time.

### garak-kfp field lessons (repo-verified 2026-07-06)

- **Read the garak report, not the EvalHub aggregate.** The EvalHub job
  result `attack_success_rate` has been observed inconsistent with its own
  garak scan (reported `0.0` where the scan hit rate was ~0.24). The garak
  `html_report` / `scan.report.jsonl` is authoritative. In the report, the
  percentage is the *resilience* (pass) rate — higher is better; `DC-1` (red)
  is critical, `DC-5` (green) is best.
- **Separate no-coverage from real failures.** Probes with
  `total_evaluated: 0` are scored `0%`/`DC-1` too and inflate "Critical"
  modules. Compute per-probe `passed/total_evaluated`; only `total > 0` with
  low pass rate is a genuine finding.
- **Benchmark selection.** `intents` is the guide's headline flow but
  hardcodes an SDG + multilingual (Helsinki-NLP translation) + LLM-judge
  chain that is fragile on constrained/connected clusters. `owasp_llm_top10`
  (and the `avid*` suites) are standard `probe_tags` scans scored by garak's
  built-in detectors — target model only, far more robust, and an
  industry-recognised framing. Prefer them unless the SDG/judge/translation
  machinery is provisioned.
- **The garak `html_report` is a module-script SPA** — it renders blank from
  `file://` (browsers block ES modules over `file://`). Serve it over HTTP or
  open it from the KFP Runs UI.
- **Guard→prove pattern.** Point the same scan at a guarded OpenAI-compatible
  endpoint (e.g. a NeMo Guardrails service) as well as the raw model to
  measure attack-surface reduction. Compare *rates*, not raw counts — garak
  attempt counts vary run-to-run, so it is a directional before/after, not a
  controlled A/B.

## Optional Read-Only Checks

Run only after following the OpenShift safety guard in `AGENTS.md`:

```bash
oc get datasciencecluster default-dsc -o yaml
oc get evalhub -A -o yaml
oc get pods -A -l app=eval-hub
oc get lmevaljob -A
oc get datasciencepipelinesapplications -A
oc get secrets -A | rg -i 'eval|s3|oci|token|api'
```

Schema checks:

```bash
oc explain evalhub.spec
oc explain lmevaljob.spec
oc explain datasciencecluster.spec.components.trustyai
```

EvalHub read-only API checks:

```bash
curl -k "$EVALHUB_URL/api/v1/health"
evalhub providers list
evalhub benchmarks list --provider lm_evaluation_harness
```

## Fail Conditions

Stop and correct the work if any of these are true:

- EvalHub, LM-Eval, or risk assessment claims are not grounded in the official
  active-baseline guide.
- EvalHub authentication is disabled for a shared environment.
- Tenant namespace is omitted from EvalHub API, SDK, or CLI workflows.
- Secrets contain real database, S3, OCI, service account, or model endpoint
  credentials in Git.
- `allowOnline` or `allowCodeExecution` is enabled without a reason.
- S3 credentials are missing required keys.
- Risk assessment is promised without pipeline server, model endpoint, judge
  endpoint, S3 storage, and model API Secret readiness.
- Disconnected risk assessment relies on translation models without cached
  Helsinki-NLP models or disabled translation strategy.
- Custom providers, adapters, Unitxt definitions, or harm categories are used
  without code review.
- A risk-assessment result is reported from the EvalHub aggregate
  `attack_success_rate` without cross-checking the garak report — the
  aggregate has been observed wrong (`0.0` vs a real ~0.24).
