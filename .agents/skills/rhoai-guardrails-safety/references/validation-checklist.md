# Validation Checklist

Use this checklist before accepting RHOAI guardrails README content, GitOps
manifests, examples, runbooks, notebooks, or scripts.

## Source Alignment

- Product links use the active baseline in `docs/PLATFORM_BASELINE.md`.
- The official Guardrails guide is recorded when NeMo, FMS, detector, or
  guardrails gateway behavior is introduced.
- NeMo is the default for new guardrailing work.
- FMS is clearly labeled legacy when used.
- Model-serving endpoint behavior is checked with
  `rhoai-model-serving-platform`.
- Llama Stack behavior is checked with `rhoai-llama-stack`.
- OpenTelemetry and metrics platform behavior is checked with
  `rhoai-observability`.
- Formal safety measurement, risk assessment, Garak, EvalHub, and LM-Eval
  claims are checked with `rhoai-evaluation`.
- API support posture is checked with `rhoai-api-tiers` when API durability
  matters.

## NeMo Guardrails Review

- TrustyAI is `Managed` in the active `DataScienceCluster`.
- Namespace choice is explicit and matches the model endpoint namespace when
  required.
- `NemoGuardrails` uses the active documented API version.
- Route authentication is enabled for shared demo services with
  `security.opendatahub.io/enable-auth: 'true'`.
- ConfigMaps contain only non-secret configuration: `config.yaml`,
  `prompts.yml`, `rails.co`, and reviewed Python action files when used.
- Model API keys and service account tokens are referenced from Secrets.
- `OPENAI_API_KEY` is not committed as a real value.
- `openai_api_base` and `model_name` match the target model endpoint.
- `/v1/guardrail/checks` is used when no generation should occur.
- `/v1/chat/completions` is used only when the service should proxy guarded
  generation.
- Policy prompts and custom actions are reviewed as code.
- Self-check model separation is documented when the main model should not
  perform its own policy checks.

## FMS Guardrails Review

- FMS use is explicitly justified as legacy or source-required.
- `GuardrailsOrchestrator` uses the active documented API version.
- `enableBuiltInDetectors`, `enableGuardrailsGateway`, and `autoConfig` are
  intentionally selected.
- Detector services are deployed, labeled, and reachable before orchestrator
  pipelines depend on them.
- Detector runtime images come from Red Hat registry or have documented demo
  exception provenance.
- Detector model artifacts and `storageUri` values are reviewed before
  committing.
- Developer Preview custom detector behavior is labeled and not presented as a
  stable product contract.
- Guardrails Gateway pipelines are tested with safe and unsafe examples before
  demo claims are made.

## Optional Read-Only Checks

Run only after following the OpenShift safety guard in `AGENTS.md`:

```bash
oc get datasciencecluster default-dsc -o yaml
oc get nemoguardrails -A
oc get guardrailsorchestrator -A
oc get pods -A | rg -i 'nemo|guardrails|trustyai|detector'
oc get routes -A | rg -i 'nemo|guardrails|detector'
```

Schema checks:

```bash
oc explain nemoguardrails.spec
oc explain guardrailsorchestrator.spec
oc explain datasciencecluster.spec.components.trustyai
oc explain servingruntime.spec
oc explain inferenceservice.spec
```

Endpoint checks:

```bash
curl -k -H "Authorization: Bearer $(oc whoami -t)" \
  "$GUARDRAILS_ROUTE/v1/guardrail/checks"

curl -k "$DETECTOR_ROUTE/health"
```

## Fail Conditions

Stop and correct the work if any of these are true:

- Guardrails claims are not grounded in the official active-baseline guide.
- FMS Guardrails is presented as the preferred path for new work.
- Route authentication is omitted for a shared demo guardrails service.
- Secrets contain real model API keys, service account tokens, or external
  provider keys in Git.
- A detector image or model artifact is copied from an example without
  provenance review.
- Policy prompts or custom Python actions are unreviewed.
- A README claims compliance, safety, or risk reduction without measured
  evidence or a clear limitation statement.
- A live cluster command bypasses the OpenShift safety guard.
