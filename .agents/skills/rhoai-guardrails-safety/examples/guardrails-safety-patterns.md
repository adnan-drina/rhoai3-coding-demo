# Guardrails Safety Patterns

These are review patterns derived from the official Guardrails guide. Verify
CRDs, TrustyAI state, routes, model endpoint auth, Secrets, and detector image
provenance before copying anything into GitOps or runbooks.

## NeMo Standalone Validation Pattern

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: nemo-quickstart-config
data:
  config.yaml: |
    rails:
      config:
        sensitive_data_detection:
          input:
            entities:
              - EMAIL_ADDRESS
              - PERSON
              - PHONE_NUMBER
        regex_detection:
          input:
            patterns:
              - "\\b(password|secret|api[_-]?key|token)\\b"
            case_insensitive: true
      input:
        flows:
          - detect sensitive data on input
          - regex check input
  rails.co: |
    # Built-in rails only
---
apiVersion: trustyai.opendatahub.io/v1alpha1
kind: NemoGuardrails
metadata:
  name: nemo-quickstart
  annotations:
    security.opendatahub.io/enable-auth: 'true'
spec:
  nemoConfigs:
    - name: nemo-quickstart-config
      configMaps:
        - nemo-quickstart-config
  env:
    - name: OPENAI_API_KEY
      value: not-used
```

Review points:

- Use this pattern for validation-only safety gates and detector smoke tests.
- `OPENAI_API_KEY: not-used` is acceptable only when no LLM calls occur.
- Expected safe output has `status: success`.
- Expected unsafe output has `status: blocked` and rail status details.

## NeMo Guarded Model Endpoint Pattern

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: nemo-model-config
data:
  config.yaml: |
    models:
      - type: main
        engine: openai
        parameters:
          openai_api_base: "https://<model-route>/v1"
          model_name: "<model-name>"
    rails:
      input:
        flows:
          - self check input
      output:
        flows:
          - self check output
  prompts.yml: |
    prompts:
      - task: self_check_input
        content: |
          Check whether the user message complies with the approved demo policy.
          Respond only with yes or no.
  rails.co: |
    # Self-check rails with reviewed policy prompts
---
apiVersion: trustyai.opendatahub.io/v1alpha1
kind: NemoGuardrails
metadata:
  name: nemo-model-guardrails
  annotations:
    security.opendatahub.io/enable-auth: 'true'
spec:
  nemoConfigs:
    - name: nemo-model-config
      configMaps:
        - nemo-model-config
  env:
    - name: OPENAI_API_KEY
      valueFrom:
        secretKeyRef:
          name: model-api-token
          key: token
```

Review points:

- Keep model endpoint tokens in Secrets.
- Confirm whether `openai_api_base` must include `/v1` for the target runtime.
- Use `/v1/chat/completions` when the NeMo service should perform guarded
  generation.
- Use a separate self-check model when latency, cost, or policy separation
  requires it.

## FMS Legacy Orchestrator Pattern

```yaml
apiVersion: trustyai.opendatahub.io/v1alpha1
kind: GuardrailsOrchestrator
metadata:
  name: guardrails-orchestrator
  annotations:
    security.opendatahub.io/enable-auth: 'true'
spec:
  autoConfig:
    inferenceServiceToGuardrail: <inference_service_name>
    detectorServiceLabelToMatch: <detector_service_label>
  enableBuiltInDetectors: true
  enableGuardrailsGateway: true
  replicas: 1
```

Review points:

- Use only when legacy FMS behavior is required.
- Confirm detector service labels and model `InferenceService` names before
  enabling AutoConfig.
- Test regex, PII, HAP, or prompt-injection detections through the documented
  endpoints before making safety claims.

## Evidence Record

```text
Guardrails path: NeMo | FMS legacy
Namespace: <namespace>
Model endpoint: <endpoint-or-none>
Validation endpoint: /v1/guardrail/checks | /v1/chat/completions | FMS endpoint
Rails or detectors: <names>
Expected safe sample: pass
Expected unsafe sample: blocked
Secrets: <names only>
Telemetry: enabled | disabled | deferred
Limitations: <known false positives/false negatives and support posture>
```

Review points:

- Capture enough evidence for README/presentation claims without exposing
  prompt secrets or API keys.
- Record false positives and false negatives as expected guardrails tuning
  work, not as failures to hide.
- Link formal safety measurement to `rhoai-evaluation` when metrics are used.
