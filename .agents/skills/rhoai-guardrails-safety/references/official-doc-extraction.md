# Official Documentation Extraction

This extraction is derived from the official RHOAI 3.4 Guardrails guide
captured in `source-capture.md`.

## Guardrails Overview

The guide covers two guardrails families:

- NeMo Guardrails for new guardrailing work in OpenShift AI.
- FMS Guardrails as a legacy TrustyAI Guardrails Orchestrator path that the
  guide says will be deprecated in a future OpenShift AI version.

Both paths are managed through TrustyAI Operator custom resources and are
deployed in model namespaces.

## NeMo Guardrails Concepts

NeMo Guardrails adds safety controls to deployed models by controlling LLM
inputs and outputs with rails for:

- sensitive data detection
- content filtering
- custom validation rules

The NeMo Guardrails service exposes two primary endpoints:

- `/v1/guardrail/checks` validates messages without generating an LLM
  response. Use it for tests, pre-LLM validation, RAG retrieval validation,
  and tool payload validation.
- `/v1/chat/completions` generates responses while applying guardrails to both
  input and output.

NeMo Guardrails is included with OpenShift AI and does not require a separate
NVIDIA subscription.

## NeMo Standalone Quickstart

The standalone quickstart uses only built-in detectors and no LLM calls.

Prerequisites:

- OpenShift AI installed and accessible.
- Sufficient permission to create ConfigMaps and `NemoGuardrails` custom
  resources in the project namespace.

Built-in detector examples:

- Presidio sensitive-data detection for entities such as email addresses,
  person names, and phone numbers.
- Regex pattern detection for secrets, API keys, tokens, and SSN-style
  patterns.

Core resources:

- ConfigMap containing NeMo `config.yaml` and `rails.co`.
- `apiVersion: trustyai.opendatahub.io/v1alpha1`
- `kind: NemoGuardrails`
- annotation `security.opendatahub.io/enable-auth: 'true'`
- `spec.nemoConfigs[].configMaps[]`
- `spec.env[]`

Healthy signal:

- `oc get nemoguardrails <name>` shows `PHASE` as `Ready`.
- `/v1/guardrail/checks` responses return `status: success` for passing
  content and `status: blocked` with rail details for blocked content.

## NeMo With A Model Endpoint

Prerequisites:

- OpenShift AI installed.
- TrustyAI component in the `DataScienceCluster` set to `Managed`.
- A model deployed on the model-serving platform.
- Permission to create ServiceAccounts, Secrets, ConfigMaps, and
  `NemoGuardrails` resources in the project namespace.

Authentication:

- A ServiceAccount can provide the identity for NeMo requests to internal model
  serving endpoints.
- A RoleBinding to the `view` ClusterRole lets the service account discover and
  communicate with model-serving endpoints in the namespace.
- A Kubernetes Secret can hold the generated service account token.
- External LLM services can use their own API keys or personal API keys.

Configuration:

- `config.yaml` defines model entries with `engine: openai`,
  `openai_api_base`, and `model_name`.
- `OPENAI_API_KEY` should come from a Secret when the model endpoint requires
  authentication.
- `prompts.yml` holds self-check prompts.
- `rails.co` holds Colang rails or comments when using built-in rails only.

Supported examples in the guide:

- basic deployment with sensitive-data detection
- custom rails with Python actions
- LLM self-check input and output rails
- separate model for self-check rails
- OpenTelemetry configuration and trace spans
- checking content without generation

## NeMo Flow And Policy Patterns

The guide describes NeMo library flow categories:

- input rails
- output rails
- retrieval rails
- statistics

Common guardrail examples:

- PII detection with Presidio
- masking PII instead of blocking
- jailbreak and prompt injection detection
- hate speech and profanity detection
- combined guardrails

Industry self-check examples:

- financial services policy prompts that avoid personalized investment, tax,
  return, and sensitive account guidance
- telecommunications prompts that avoid internal network, credential, customer
  account, and vulnerability details
- customization guidance for organization-specific policies, sensitivity, and
  realistic edge-case testing

Treat policy prompts as code. Review them for business accuracy, scope, and
unintended blocking before using them in a demo.

## FMS Guardrails Concepts

FMS Guardrails uses the TrustyAI Guardrails Orchestrator to invoke detections
on text-generation inputs and outputs and to perform standalone detections.

Important posture:

- The guide marks FMS Guardrails as legacy and directs users to NeMo
  Guardrails for guardrailing.

FMS resource and API concepts:

- `apiVersion: trustyai.opendatahub.io/v1alpha1`
- `kind: GuardrailsOrchestrator`
- built-in detector server
- Hugging Face detector serving runtime
- Guardrails Gateway
- AutoConfig
- OpenTelemetry exporter
- guardrails metrics

Built-in detector categories:

- `regex` detectors such as email, credit card, IP address, phone number, post
  code, US SSN, and custom regex
- `file_type` detectors for JSON, XML, YAML, and schema-validated content
- custom detector code is labeled Developer Preview in the guide

Detector endpoint:

- `/api/v1/text/contents`

Orchestrator/Gateway endpoints from examples:

- `/api/v2/text/detection/content`
- `/api/v2/chat/completions-detection`

## Detector Serving Runtime Notes

The guide shows Hugging Face detector runtime examples for KServe.

Relevant resource kinds and fields:

- `ServingRuntime` with `apiVersion: serving.kserve.io/v1alpha1`
- `InferenceService` with `apiVersion: serving.kserve.io/v1beta1`
- `serving.kserve.io/deploymentMode: RawDeployment`
- detector runtime image examples, including the Red Hat registry image
  `registry.redhat.io/rhoai/odh-guardrails-detector-huggingface-runtime-rhel9:v<your_rhoai_version>`
- `MODEL_DIR`, `HF_HOME`, and optional `SAFE_LABELS`
- detector model `storageUri`
- route to the detector predictor service

Review caveats:

- Replace `<your_rhoai_version>` with the active OpenShift AI version when a
  Red Hat registry runtime image is used.
- Treat testing registry examples and upstream model artifacts as examples
  until provenance is reviewed and approved for the demo.
- Verify architecture support when examples mention unsupported image
  architectures.

## Llama Stack And Guardrails

The guide includes an FMS Guardrails workflow for detecting PII by using
Guardrails with Llama Stack.

Use this skill for the guardrails and detector behavior. Use
`rhoai-llama-stack` for `LlamaStackDistribution`, provider, OAuth, ABAC, RAG,
and OpenAI-compatible API configuration.

## Metrics And Observability

Guardrails-specific OpenTelemetry and metrics configuration is covered in this
guide for NeMo and FMS.

Use `rhoai-observability` for the platform observability stack, collector,
Tempo, Prometheus, Alertmanager, dashboard visibility, and user workload
scrape-label policy.
