# Official Documentation Extraction

This extraction is derived from the official RHOAI 3.4 guide captured in
`source-capture.md`.

## Evaluation Overview

OpenShift AI evaluation workflows in this guide use TrustyAI tools:

- EvalHub for standardized, scalable, multi-tenant LLM evaluation job
  orchestration across providers, benchmarks, and collections
- LM-Eval for direct evaluation jobs and dashboard-driven model evaluation
- automated risk assessment for adversarial safety testing with generated
  prompts, Garak/KFP, judge models, and reports

## EvalHub Concepts

EvalHub is an evaluation orchestration service with:

- REST API server backed by PostgreSQL
- SDK and CLI
- provider adapters packaged as container images
- benchmark metadata
- benchmark collections
- pass criteria and thresholds
- tenant-scoped evaluation jobs

Built-in providers captured by the guide include:

- `lm_evaluation_harness`
- `garak`
- `guidellm`
- `lighteval`

Evaluation job states:

- `pending`
- `running`
- `completed`
- `failed`
- `cancelled`
- `partially_failed`

## EvalHub Architecture And Deployment

EvalHub deployment prerequisites:

- cluster administrator privileges
- OpenShift CLI 4.12 or later
- TrustyAI component in the `DataScienceCluster` set to `Managed`
- KServe configured for `RawDeployment` mode
- PostgreSQL connection Secret with a `db-url` key

EvalHub is deployed through the TrustyAI Operator with an
`EvalHub` custom resource:

- `apiVersion: trustyai.opendatahub.io/v1alpha1`
- `kind: EvalHub`
- `spec.replicas`
- `spec.database.type`
- `spec.database.secret`
- `spec.providers`
- `spec.collections`
- optional OpenTelemetry configuration
- optional environment variables, including MLflow tracking configuration

The guide recommends a dedicated namespace for EvalHub rather than
`redhat-ods-applications`, because that namespace has restrictive
NetworkPolicies that can affect tenant communication.

Runtime behavior:

- each benchmark runs as a Kubernetes Job
- each Job pod contains an adapter container and a sidecar proxy container
- the sidecar authenticates to EvalHub by using a ServiceAccount token
- the sidecar can proxy authenticated requests to MLflow and OCI registries
- adapter containers can run framework-specific code without receiving direct
  credentials

## EvalHub SDK, CLI, And Multi-Tenancy

SDK and CLI prerequisites:

- Python 3.11 or later
- deployed EvalHub service
- network access to install Python packages

Package choices:

- `eval-hub-sdk[cli]` for SDK plus CLI
- `eval-hub-sdk[client]` for SDK only

CLI connection settings:

- base URL
- tenant namespace
- bearer token

All EvalHub API requests except `/api/v1/health` require tenant context through
the `X-Tenant` header. CLI profiles persist configuration under the user's
EvalHub config file.

## EvalHub Job Workflow

Typical workflow:

- list providers and benchmarks
- submit a job against a provider benchmark list or collection
- track job status, events, and results
- cancel or delete jobs when needed

Jobs can reference:

- model endpoint URL and model name
- API key Secret or ServiceAccount token
- provider benchmark IDs
- collection IDs
- pass criteria
- S3 custom data
- MLflow experiment configuration
- OCI result export configuration

Results can be exported to an OCI registry and tracked in MLflow when those
integrations are configured.

## EvalHub Customization

The guide covers:

- creating custom benchmark collections
- configuring API key authentication for model endpoints
- authenticating models with a ServiceAccount token
- using custom data from S3
- exporting evaluation results to OCI
- configuring MLflow experiment tracking
- adding custom providers through the API
- adding custom providers through a ConfigMap
- adding collections through a ConfigMap
- writing custom evaluation adapters with the Python SDK

Treat custom providers, adapters, collections, and benchmark definitions as
reviewed code artifacts. Validate container images, secrets, benchmark
semantics, pass criteria, and tenant scope before use.

## EvalHub API And Configuration

API areas captured by the guide:

- evaluation job endpoints
- provider endpoints
- collection endpoints
- health endpoint
- Prometheus metrics endpoint when enabled
- OpenAPI specification endpoint
- Swagger UI endpoint

EvalHub configuration can come from generated `config.yaml` and environment
variables. Environment variables take precedence. When deploying through the
TrustyAI Operator, the Operator generates configuration from the `EvalHub`
custom resource and environment variables in `spec.env`.

Important service configuration boundary:

- disabling EvalHub authentication allows unauthenticated access and must not
  be enabled for production or shared demo environments.

## EvalHub Tenant RBAC

EvalHub resources are tenant-scoped by namespace. Tenant setup includes:

- namespace labels/network access required by the deployment topology
- ServiceAccounts for evaluation jobs and clients
- RoleBindings that grant access to submit jobs and read results
- explicit access grants for users or service accounts

Use tenant namespaces to separate teams, projects, and demo stages.

## LM-Eval Workflows

LM-Eval uses `LMEvalJob` custom resources:

- `apiVersion: trustyai.opendatahub.io/v1alpha1`
- `kind: LMEvalJob`
- model selector and model arguments
- task list
- batch size
- sample logging
- environment variables and Secrets
- optional online access
- optional remote code execution
- optional PVC or S3 storage

The guide includes:

- setting up LM-Eval
- enabling online access and remote code execution through CLI or web console
- job properties
- custom Unitxt cards, templates, and system prompts
- dashboard-driven model evaluation
- metrics
- Hugging Face token handling
- PVC and S3 storage patterns
- KServe InferenceService evaluation
- LLM-as-a-judge metrics

KServe/vLLM endpoint evaluations require the correct model route or service URL
and, for completions-style examples, the `/v1/completions` endpoint.

## Automated Risk Assessment

Automated risk assessment tests safety controls against adversarial prompts.
It can run through:

- EvalHub API, where EvalHub orchestrates the KFP execution and result
  collection
- KFP Python SDK, when direct programmatic control is needed or EvalHub is not
  deployed

The assessment has two phases:

- prompt generation across harm categories with demographic, regional, and
  writing-style variation
- security testing against increasingly aggressive attack strategies

Risk assessment prerequisites include:

- configured pipeline server
- OpenAI-compatible target model endpoint
- OpenAI-compatible judge model endpoint
- S3-compatible storage for pipeline artifacts
- EvalHub token when using EvalHub API
- Kubernetes Secret containing model API key
- optional disconnected translation-model cache

For disconnected clusters, the translation attack strategy needs pre-downloaded
Helsinki-NLP translation models uploaded to S3, or the translation strategy
must be disabled.

Risk assessment uses benchmark `intents` with provider `garak-kfp`.

Configurable areas:

- KFP endpoint, namespace, S3 credentials, experiment name, prefix, and TLS
  options
- judge, SDG, attacker, and evaluator model endpoints and model names
- API key fallback names by role
- custom policy taxonomy CSV from S3
- custom intents CSV from S3
- SDG concurrency and token settings
- timeout and Garak advanced configuration
- Hugging Face translation cache path
- KFP caching behavior

Results are stored in S3 and can also appear as MLflow experiment artifacts
when EvalHub has MLflow integration.

## Verification Signals

Expected signals:

- TrustyAI component is managed
- EvalHub pod is running and health endpoint returns healthy
- EvalHub providers and benchmarks list successfully
- EvalHub jobs progress through expected states
- tenant namespace and ServiceAccount RBAC allow intended access
- MLflow records evaluation results when enabled
- OCI export writes expected result artifacts when configured
- `LMEvalJob` pod starts and writes output logs/results
- dashboard evaluation appears with expected status and metrics
- risk assessment writes S3 artifacts and optional MLflow artifacts

Failure signals:

- EvalHub authentication disabled in a shared environment
- missing `X-Tenant` header or wrong CLI tenant
- PostgreSQL `db-url` Secret missing or invalid
- model endpoint Secrets missing or committed
- online access or code execution enabled without justification
- `LMEvalJob` references the wrong namespace or model route
- S3 Secret lacks required AWS-style keys
- risk assessment uses translation strategy on a disconnected cluster without
  cached translation models
- custom provider or adapter image is unreviewed
