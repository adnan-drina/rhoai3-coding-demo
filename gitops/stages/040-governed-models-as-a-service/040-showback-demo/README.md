# Showback demo (`040-showback-demo`)

This optional Application holds the cluster side of the three-team showback demo: team access, Marketing's dedicated Mistral model, three live offer dashboards and external-model metering. The demo flow, load scripts and dashboard guide are in [showback-demo](../../../../stages/040-governed-models-as-a-service/showback-demo/README.md).

## Why

The demo needs its own team subscriptions, a dedicated model, dashboards and a metering ledger without changing how ordinary Stage 040 deploys or who owns the shared Qwen model, gateway and monitoring stack. One manual-sync Application keeps all of it together and removable.

## What

| Files | Objects |
|---|---|
| `team-*-subscription.yaml`, `team-*-auth-policy.yaml` | `MaaSSubscription` and `MaaSAuthPolicy` per team in `models-as-a-service`: Engineering → Qwen; Marketing → Mistral; Support → Qwen, GPT-6 Luna, Claude Sonnet 5.5 and Nemotron. Each is owned by the team user `showback-<team>` |
| `dedicated/` | `LLMInferenceService` and `MaaSModelRef` for Mistral Small 4 119B NVFP4 in `internal-models`, zero replicas in Git, one RTX PRO 6000 when scaled up, routed only on the Gateway listener `mistral-small4`; Marketing's subscription and auth policy; `model-registry-metadata.json` (registry labels and properties; Stage 040 `deploy.sh` registers the model whether or not this component is installed and links the deployment once it exists) |
| (traces) | No object: `generate-load.sh` writes its traces to the MLflow workspace of the MaaS project `models-as-a-service` (owned by `040-maas-database`), where `rhods-admins` already have `admin`, which aggregates the MLflow operator's edit and view roles. Traces hold prompts and answers; no other group has a role there that reaches MLflow |
| `quality/` | Hourly quality scoring of the request traces in `models-as-a-service`: ServiceAccount `maas-quality-judge`, its own `MaaSSubscription` and `MaaSAuthPolicy` (Claude Sonnet 5.5 only, 300,000 tokens per hour, cost centre `ai-platform`), a Role for its key Secret, endpoint ConfigMap and MLflow `experiments` (read traces, write feedback), a Role in `openshift-ingress` to read the MaaS Gateway hostname, read-only Roles for the MaaS model references (`internal-models`, `external-models`, with the ExternalModels for their provider) and the offer catalog (`redhat-ods-monitoring`), so the scorer keeps one MLflow experiment per MaaS model with its offering and provider tags, the Sync hook `provision-maas-quality-judge` that mints the judge key (the Stage 050 key procedure), and the CronJob `maas-quality-scorer` with its script ConfigMap. The judge calls the public MaaS hostname through the internal gateway Service; the scorer authenticates to MLflow with `kubernetes-namespaced` |
| `offer-catalog.yaml` | `PrometheusRule` (`monitoring.rhobs/v1`) in `redhat-ods-monitoring` recording, per private model, its offering, sponsor, GPU worker price, demonstrated capacity, and (shared only) on-demand and committed tariffs and per-subscription commitments |
| `dashboard-offer-*.yaml` | Model-agnostic `PersesDashboard`s **Offer · Shared private**, **Offer · Dedicated private** and **Offer · External model** in `redhat-ods-monitoring`, querying the RHOAI datasource live and joining on the offer catalog |
| `metering/` | Metering backend and PostgreSQL 16 (retained PVC), database Secret, price catalog, profile ConfigMap, ImageStream, Services, ServiceMonitor and the NetworkPolicy for gateway-to-backend traffic; `metering/build/` holds the BuildConfig and the two reviewed patches that build the backend image in the cluster ([build README](metering/build/README.md)) |

The Application owns no shared Namespace, Qwen resource, Gateway, operator or MaaS `Config`. Qwen stays with `040-local-models` and GPU capacity with Stage 020. The metering plugin entry in the MaaS-owned `openshift-ingress/payload-processing-plugins` ConfigMap is written by the targeted deployment from `metering/profile.yaml`, not by Argo CD, so reverting the Application alone does not remove it.

The dashboards are the generated output of a small, uncommitted generator; edit the YAML directly for small changes. Tokens come from the MaaS counter `authorized_hits_total` (per user, subscription and model), running time from the presence of vLLM metrics, prices and offer membership from the catalog, external spend from the metering gauges. Onboarding a private model to an offering is a catalog entry, not a dashboard change.

## How

[040-showback-demo](../../../applications/040-showback-demo.yaml) uses the `rhoai-demo` project and the `openshift-gitops` destination, with `demo.rhoai.io/optional: 'true'`, a `deploy-script` annotation, no `deploy-order` and no automated sync. It ignores `spec.replicas` of the Mistral model, which is scaled for demos. Deploy and validate only through the stage entrypoints:

```bash
./stages/040-governed-models-as-a-service/deploy.sh --component 040-showback-demo --revision <full-sha>
RHOAI_STAGE040_SHOWBACK_EXPECTED_REVISION=<full-sha> \
  ./stages/040-governed-models-as-a-service/validate.sh --component 040-showback-demo
```

Mistral needs a second GPU worker (`stages/020-gpu-infrastructure-private-ai/deploy.sh --gpus 2`) before it is scaled to one replica.

## Validation

Offline:

```bash
kustomize build gitops/stages/040-governed-models-as-a-service/040-showback-demo
./stages/040-governed-models-as-a-service/showback-demo/validate.sh
scripts/stage-apps.sh check-static 040
scripts/validate-stage-flow.sh
```

Live, `validate.sh --component 040-showback-demo` checks the Application's revision, sync and health, every owned object (Mistral replicas excepted), metering readiness, the bound PVC and the loaded processing profile. Broad Stage 040 validation prints `SKIP 040-showback-demo (not activated)` while the Application is absent. Running `showback-demo/generate-load.sh` and watching the dashboards is the functional check.

Rollback is a revert of this component's source. Disable metering first through `metering/profile.yaml`, keep the metering PVC, revoke team keys through MaaS and leave shared model, gateway and monitoring resources with their owners.

## Alignment with official guidance

| Topic | Repository choice | Status |
|---|---|---|
| MaaS identity and quotas [1] | One user-owned subscription and matching authorization policy per team; users mint their own keys | Engineering and Support keys verified; Marketing and the external models for Support take effect at the next deployment |
| Usage and metering [1] | MaaS usage counters for private models; the shipped IPP external-metering plugin feeds a community backend for external models | Counters verified; external metering deployed, first real requests pending; Developer Preview plugin, community backend |
| Model serving [2] | Mistral Small 4 NVFP4 on one RTX PRO 6000 through llm-d, stopped in Git | Not yet started on this cluster |
| Observability [3] | `PersesDashboard`s on the RHOAI datasource, shown on the OpenShift AI Observability page | Queries verified against the live datasource |
| Quality scoring [5] | Not documented for OpenShift AI 3.5: MLflow online judges need the MLflow AI Gateway and server job execution, which the product ships disabled | A CronJob runs MLflow judges (`make_judge`) with the SDK and logs feedback on the traces; upstream MLflow behaviour, verified on MLflow 3.14 |
| Request traces [5] | The MaaS project as the MLflow workspace for the traces; authentication with the caller's OpenShift token; access through RBAC on `mlflow.kubeflow.org` | Traces written with OTLP/HTTP to MLflow `/v1/traces`, which is upstream MLflow (3.6+), not described in the Red Hat MLflow book; verified on MLflow 3.14 |
| GitOps [4] | One optional manual-sync Application with immutable revisions; shared fields keep their owners | Deployed and validated through the stage entrypoints |

## References

1. [OpenShift AI 3.5: Govern LLM access with Models-as-a-Service](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/govern_llm_access_with_models-as-a-service/deploy-and-manage-models-as-a-service)
2. [OpenShift AI 3.5: Deploy models using distributed inference with llm-d](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/deploy_models_using_distributed_inference_with_llm-d/index)
3. [OpenShift AI 3.5: Managing OpenShift AI, observability dashboards](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#observability-dashboards_managing-rhoai)
4. [Red Hat OpenShift GitOps 1.21 documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_gitops/1.21)
5. [OpenShift AI 3.5: Working with MLflow](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_mlflow/index); upstream [MLflow OpenTelemetry ingestion](https://mlflow.org/docs/latest/genai/tracing/opentelemetry/ingest/)
