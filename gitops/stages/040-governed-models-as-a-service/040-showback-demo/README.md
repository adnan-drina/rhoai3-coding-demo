# Showback demo (`040-showback-demo`)

This optional Application holds the cluster side of the three-team showback demo: team access, four live showback dashboards, external-model metering and the daily quality scoring of the demo's MLflow request traces. The demo flow, load scripts and dashboard guide are in [showback-demo](../../../../stages/040-governed-models-as-a-service/showback-demo/README.md).

## Why

The demo needs its own team subscriptions, dashboards and a metering ledger without changing how ordinary Stage 040 deploys or who owns the models, gateway and monitoring stack. Both private models, Qwen and Marketing's dedicated Mistral, are served and published to MaaS by `040-local-models`. One manual-sync Application keeps all of it together and removable.

## What

| Files | Objects |
|---|---|
| `team-*-subscription.yaml`, `team-*-auth-policy.yaml` | `MaaSSubscription` and `MaaSAuthPolicy` per team in `models-as-a-service`: Engineering → Qwen; Marketing → Mistral; Support → Qwen, GPT-6 Luna, Claude Sonnet 5.5 and Nemotron. Each is owned by the team user `showback-<team>` |
| `dedicated/` | Marketing's subscription and auth policy for Mistral Small 4 119B NVFP4 (`internal-models/mistral-small4-119b`, served by `040-local-models`) |
| (traces) | No object: `generate-load.sh` writes its traces to the MLflow workspace of the MaaS project `models-as-a-service` (owned by `040-maas-database`), where `rhods-admins` already have `admin`, which aggregates the MLflow operator's edit and view roles. Traces hold prompts and answers; no other group has a role there that reaches MLflow |
| `quality/` | Daily quality scoring of the request traces in `models-as-a-service` (a batch job at 17:00 UTC, the end of the working day): ServiceAccount `maas-quality-judge`, its own `MaaSSubscription` and `MaaSAuthPolicy` (the private models as judges: Qwen 3.8, 2,000,000 tokens per hour, grades every model but itself; Mistral Small 4, 1,000,000 tokens per hour, grades Qwen; cost centre `ai-platform`), a Role for its key Secret, endpoint ConfigMap and MLflow `experiments` (read traces, write feedback), a Role in `openshift-ingress` to read the MaaS Gateway hostname, read-only Roles for the MaaS model references (`internal-models`, `external-models`, with the ExternalModels for their provider) and the offer catalog (`redhat-ods-monitoring`), so the scorer keeps one MLflow experiment per MaaS model with its offering and provider tags, the Sync hook `provision-maas-quality-judge` that mints the judge key (the Stage 050 key procedure), and the CronJob `maas-quality-scorer` with its script ConfigMap. The judge calls the public MaaS hostname through the internal gateway Service; the scorer authenticates to MLflow with `kubernetes-namespaced` |
| `offer-catalog.yaml` | `PrometheusRule` (`monitoring.rhobs/v1`) in `redhat-ods-monitoring` recording the team of every MaaS subscription (Engineering, Support, Marketing, Platform) and, per private model, its offering, sponsor, GPU worker price, demonstrated capacity, and (shared only) on-demand and committed tariffs and per-subscription commitments |
| `dashboard-offer-*.yaml` | Model-agnostic `PersesDashboard`s **Showback 1 · By team**, **Showback 2 · Shared private**, **Showback 3 · Dedicated private** and **Showback 4 · External model** in `redhat-ods-monitoring`, querying the RHOAI datasource live and joining on the offer catalog (the fifth tab, **Showback 5 · Break-even**, is the Stage 040 platform dashboard `dashboard-6-tokenomics-break-even-admin`) |
| `metering/` | Metering backend and PostgreSQL 16 (retained PVC), database Secret, price catalog, profile ConfigMap, ImageStream, Services, ServiceMonitor and the NetworkPolicy for gateway-to-backend traffic; `metering/build/` holds the BuildConfig and the two reviewed patches that build the backend image in the cluster ([build README](metering/build/README.md)) |

The Application owns no shared Namespace, model, Gateway, operator or MaaS `Config`. Qwen and Mistral stay with `040-local-models` and GPU capacity with Stage 020. The metering plugin entry in the MaaS-owned `openshift-ingress/payload-processing-plugins` ConfigMap is written by the targeted deployment from `metering/profile.yaml`, not by Argo CD, so reverting the Application alone does not remove it.

The dashboards are the generated output of a small, uncommitted generator; edit the YAML directly for small changes. Tokens come from the MaaS counter `authorized_hits_total` (per user, subscription and model; a team is the catalog's mapping of the subscription, because the counter does not carry the subscription's cost centre), running time from the presence of vLLM metrics, prices and offer membership from the catalog, external spend from the metering gauges. Onboarding a private model to an offering is a catalog entry, not a dashboard change.

## How

[040-showback-demo](../../../applications/040-showback-demo.yaml) uses the `rhoai-demo` project and the `openshift-gitops` destination, with `demo.rhoai.io/optional: 'true'`, a `deploy-script` annotation, no `deploy-order` and no automated sync. It ignores the image of the metering Deployment, which the OpenShift image trigger resolves. Deploy and validate only through the stage entrypoints:

```bash
./stages/040-governed-models-as-a-service/deploy.sh --component 040-showback-demo --revision <full-sha>
RHOAI_STAGE040_SHOWBACK_EXPECTED_REVISION=<full-sha> \
  ./stages/040-governed-models-as-a-service/validate.sh --component 040-showback-demo
```

Mistral needs a second GPU worker (`stages/020-gpu-infrastructure-private-ai/deploy.sh --gpus 2`); its replicas belong to `040-local-models`.

## Validation

Offline:

```bash
kustomize build gitops/stages/040-governed-models-as-a-service/040-showback-demo
./stages/040-governed-models-as-a-service/showback-demo/validate.sh
scripts/stage-apps.sh check-static 040
scripts/validate-stage-flow.sh
```

Live, `validate.sh --component 040-showback-demo` checks the Application's revision, sync and health, every owned object, metering readiness, the bound PVC and the loaded processing profile. Broad Stage 040 validation prints `SKIP 040-showback-demo (not activated)` while the Application is absent. Running `showback-demo/generate-load.sh` and watching the dashboards is the functional check.

Rollback is a revert of this component's source. Disable metering first through `metering/profile.yaml`, keep the metering PVC, revoke team keys through MaaS and leave shared model, gateway and monitoring resources with their owners.

## Alignment with official guidance

| Topic | Repository choice | Status |
|---|---|---|
| MaaS identity and quotas [1] | One user-owned subscription and matching authorization policy per team; users mint their own keys | Engineering and Support keys verified; Marketing and the external models for Support take effect at the next deployment |
| Usage and metering [1] | MaaS usage counters for private models; the shipped IPP external-metering plugin feeds a community backend for external models | Counters verified; external metering deployed, first real requests pending; Developer Preview plugin, community backend |
| Model serving [2] | Mistral Small 4 NVFP4 on one RTX PRO 6000 through llm-d, served by `040-local-models` | Running on this cluster since 2026-10-27; qualification pending (`BACKLOG.md`) |
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
