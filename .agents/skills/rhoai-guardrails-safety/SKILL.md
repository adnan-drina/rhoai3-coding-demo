---
name: rhoai-guardrails-safety
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when changing or reviewing runtime guardrails in this repo: the Stage 040
  dashboard flag `guardrails`, the optional dashboard initialization that
  creates the `NemoGuardrails` resource `nemoguardrails` in `demo-sandbox`, the TrustyAI
  component it depends on (Stage 050), or a proposal to add NeMo or FMS
  Guardrails, detectors, PII masking or prompt-injection rails. Do NOT use for
  playground guardrail toggles (use rhoai-gen-ai-playground), Garak risk scans
  and EvalHub (use rhoai-evaluation), TrustyAI bias and drift (use
  rhoai-monitoring-trustyai), or the Hermes tool-loop guardrails of Stage 130.
---

# RHOAI Guardrails Safety

Thin skill: repo decisions and pitfalls here, product behavior in the linked
OpenShift AI 3.5 sections. No guardrail resource is declared in Git; the
dashboard creates one on request. Detailed record:
`gitops/stages/040-governed-models-as-a-service/040-maas-platform/README.md`.

## When to use

- The playground offers no guardrails, or guardrail initialization fails.
- Someone proposes a `NemoGuardrails` or `GuardrailsOrchestrator` resource,
  detector models, or guardrails in front of MaaS models.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Dashboard flag `guardrails: true` set by the `job-enable-dsc-maas` Sync hook on a delegated Stage 010 field; `stages/040-governed-models-as-a-service/validate.sh` requires it | `gitops/stages/040-governed-models-as-a-service/040-maas-platform/jobs/enable-maas-job.yaml` | [NeMo Guardrails][nemo] |
| TrustyAI component `Managed` from Stage 050 (the `NemoGuardrails` API group is `trustyai.opendatahub.io`) | `gitops/stages/050-model-evaluation/050-mlflow/dsc-enablement/` | [Basic deployment][basic] |
| Playground: no guardrail CR in Git; the dashboard's own initialization creates it once the flag is on (the former wrapper `studio-api.sh --initialize-guardrails`, which accepted only a resource named `nemoguardrails`, is in git history at `82092e01`) | — | [CR configuration reference][crref] |
| NeMo Guardrails only; no FMS `GuardrailsOrchestrator` (3.5 documents migrating from FMS to NeMo) | not in Git | [Migrate from FMS to NeMo][migrate] |
| Playground guardrail: guarded models are reached through MaaS; no detector or self-check model is deployed | `gitops/stages/040-governed-models-as-a-service/040-local-models/` | [Separate self-check model][selfcheck] |
| Qualification candidate guardrail `candidate-guardrails` (`evaluated-models`, Git-managed, 2026-10-23): self-check input and output rails judged by Nemotron 3 Ultra through its own MaaS subscription `candidate-guardrails`, `enable_thinking: false` (about 0.5 s per check instead of 8 to 14 s); the guarded model through its internal predictor Service; `config.yaml` written by the Stage 050 hook because it carries the MaaS hostname | `gitops/stages/050-model-evaluation/050-model-qualification/guardrails/`, `.../maas-key-provisioner.yaml`, `gitops/stages/040-governed-models-as-a-service/040-model-access/candidate-guardrails-access.yaml` | [Separate self-check model][selfcheck], [Jailbreak detection][withllm] |
| The qualification pipeline scans the guarded endpoint with the same Context-aware vulnerability scan as the bare model; the guarded attack success rate is the risk gate, the bare model's is reported | `stages/050-model-evaluation/qualification/pipeline.py` | not product guidance |

## Procedure

1. Enable or change the flag only through the Stage 040 Job, then:

   ```bash
   ./stages/040-governed-models-as-a-service/deploy.sh
   ./stages/040-governed-models-as-a-service/validate.sh
   ```

2. Optional initialization (no model calls) runs from the dashboard; check
   the result after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   oc get nemoguardrails.trustyai.opendatahub.io -n demo-sandbox
   ```

3. A Git-managed rail set (ConfigMap with `config.yaml` and rails, auth to a
   MaaS model, Secrets from `.env` helpers) needs a new GitOps component with a
   README and a validate check that sends one allowed and one blocked request.

## Pitfalls

- Initialization proves only that the resource exists; model-backed input and
  output checks are separate and not automated (the helper says so).
- A second, differently named guardrail resource in `demo-sandbox` makes the
  helper refuse; remove it or adopt it deliberately.
- NeMo authentication to a model needs a token or ServiceAccount; MaaS keys
  are minted per subscription (`rhoai-maas-governance`). See
  [Configure authentication][auth].
- Guardrails on OGX Responses API traffic are a separate integration
  ([OGX guardrails security][ogxguard]).
- `/v1/chat/completions` is not a transparent proxy and does not carry tool
  calls: keep the guardrail away from the coding agents' traffic.
- Garak counts an HTTP error as a refusal, so a failing or rate-limited judge
  makes a guarded scan look safer than it is; check the guardrail's errors
  before trusting a guarded attack success rate.
- The MaaS gateway answers TLS only for its listener hostnames and the
  `NemoGuardrails` CR has no `hostAliases`, so a guardrail reaches MaaS through
  the public hostname, not the gateway's internal Service.
- Nemotron 3 Ultra reasons by default; send
  `chat_template_kwargs.enable_thinking: false` for yes/no judging, directly
  under the model's `parameters`: the 3.5.2 server (nemoguardrails 0.24) sends
  `parameters` verbatim, so a LangChain `extra_body` gets HTTP 400.
- 3.5.2 operator quirks: set `caBundleConfig.configMapNamespace`; keep one
  ConfigMap per `nemoConfigs` entry (several mount at the same path); with
  `enable-auth`, callers need unnamed `get` on services in the project.

## Official documentation (OpenShift AI 3.5)

| Topic | Section |
|---|---|
| NeMo Guardrails | [Overview][nemo], [Standalone quick start][quickstart], [Deploy with an LLM][withllm], [Basic deployment][basic] |
| Authentication | [Configure authentication][auth] |
| Rails | [Custom Python actions][actions], [Self-check rails][selfcheckrails], [Separate self-check model][selfcheck], [Check content without generation][checkonly] |
| Reference | [CR configuration reference][crref], [Library flows][flows], [Common examples][examples] |
| Observability | [OpenTelemetry for NeMo][otel] |
| MCP gateway tool calls | [NeMo with MCP gateway][mcp] |
| FMS (legacy) | [Migrate from FMS to NeMo][migrate], [FMS Guardrails][fms] |

## Related skills

`rhoai-gen-ai-playground`, `rhoai-llama-stack`, `rhoai-evaluation`,
`rhoai-monitoring-trustyai`, `rhoai-maas-governance`.

[nemo]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/enabling_ai_safety_with_guardrails/index#enabling-ai-safety-with-nemo-guardrails_nemo-guardrails
[quickstart]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/enabling_ai_safety_with_guardrails/index#nemo-guardrails-standalone-quick-start_nemo-guardrails
[withllm]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/enabling_ai_safety_with_guardrails/index#deploying-the-nemo-guardrails-service-with-an-llm_nemo-guardrails
[basic]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/enabling_ai_safety_with_guardrails/index#configuring-nemo-guardrails-basic-deployment_nemo-guardrails
[auth]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/enabling_ai_safety_with_guardrails/index#configure-nemo-guardrails-authentication_nemo-guardrails
[actions]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/enabling_ai_safety_with_guardrails/index#adding-custom-rails-with-python-actions_nemo-guardrails
[selfcheckrails]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/enabling_ai_safety_with_guardrails/index#adding-llm-self-check-guardrails_nemo-guardrails
[selfcheck]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/enabling_ai_safety_with_guardrails/index#using-a-separate-model-for-self-check-guardrails_nemo-guardrails
[checkonly]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/enabling_ai_safety_with_guardrails/index#checking-content-against-guardrails-without-generating-responses_nemo-guardrails
[crref]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/enabling_ai_safety_with_guardrails/index#nemo-guardrails-custom-resource-configuration-reference_nemo-guardrails
[flows]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/enabling_ai_safety_with_guardrails/index#nemo-guardrails-library-flows-reference_nemo-guardrails
[examples]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/enabling_ai_safety_with_guardrails/index#common-guardrail-configuration-examples_nemo-guardrails
[otel]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/enabling_ai_safety_with_guardrails/index#configuring-observability-for-nemo-guardrails-with-opentelemetry_nemo-guardrails
[mcp]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/enabling_ai_safety_with_guardrails/index#nemo-guardrails-mcp-gateway-integration-overview_nemo-guardrails
[migrate]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/enabling_ai_safety_with_guardrails/index#migrating-from-fms-to-nemo-guardrails_migrating-from-fms-to-nemo-guardrails
[fms]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/enabling_ai_safety_with_guardrails/index#enabling-ai-safety-with-guardrails_safety
[ogxguard]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ogx/index#ogx-guardrails-security-int_rag
