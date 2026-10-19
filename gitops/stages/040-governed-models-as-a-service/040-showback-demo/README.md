# Showback demo (`040-showback-demo`)

This optional Application packages the Qwen-only qualification slice of the three-team showback scenario in one lifecycle boundary. The source is prepared for review; it has not been deployed or qualified against live models. Its publisher is stopped, its selected-report ConfigMap is empty, and its native configuration documents are inert.

## Why

The demo connects governed team identities to explicit financial allocation and service-offer statements. A dedicated Application keeps its access grants, financial views, report publisher and archive workspace together without changing ordinary Stage 040 deployment or transferring shared platform ownership.

## What

The root Kustomize render contains exactly 21 resources with `components/qwen-only` enabled (23 with that Component removed after full-model qualification):

| Files | Objects and namespace |
|---|---|
| `team-*-subscription.yaml`, `team-*-auth-policy.yaml` | Two active `MaaSSubscription` / `MaaSAuthPolicy` pairs in `models-as-a-service`: Engineering and Support use Qwen. The generated full-scenario files retain the Marketing pair and Support Mistral reference; the enabled Component removes them from the active render |
| `archive-namespace.yaml`, `archive-rolebinding.yaml` | Retained Namespace `showback-reporting` and its `showback-mlflow-edit` RoleBinding to the existing native `edit` ClusterRole, whose aggregated MLflow experiment read/write permissions are checked before deployment |
| `dashboard-showback-*.yaml` | Three bounded allocation `PersesDashboard` resources in `redhat-ods-monitoring` |
| `publisher-*.yaml` | Deployment `showback-report-publisher` at zero replicas, HTTP configuration and empty selected-report ConfigMaps, Service and ServiceMonitor in `redhat-ods-monitoring` |
| `service-views/` | Five monthly service-offer `PersesDashboard` resources in `redhat-ods-monitoring` |
| `native-inputs/` | Two inert ConfigMaps: Loki review inputs in `redhat-ods-monitoring`, metering review inputs in `redhat-ai-gateway-infra` |

`model-drafts/mistral/` contains a separately renderable, zero-replica `LLMInferenceService` and `MaaSModelRef` candidate. It is **excluded from the root render**. The model's runtime, resource envelope and resulting policy health remain unqualified. Promoting it into this Application requires a reviewed root Kustomize change and model qualification; moving the files here does not deploy it.

The Application owns no shared Namespace, Qwen resource, Gateway, operator, MaaS `Config`, IPP plugin ConfigMap, LokiStack, database or backend workload. Shared Qwen remains owned by `040-local-models`; the [package's Qwen FP8 component](../../../../stages/040-governed-models-as-a-service/showback-demo/model-drafts/qwen-fp8/) is review input for that existing owner. Stage 020 retains GPU infrastructure and queue ownership. Stage 050 retains MLflow and artifact-store ownership. Users, keys, real tariffs and report evidence are runtime inputs, not committed resources.

## How

Application [040-showback-demo](../../../applications/040-showback-demo.yaml) uses the existing `rhoai-demo` project and fixed `openshift-gitops` destination. Every namespaced resource declares its actual namespace. It has `demo.rhoai.io/optional: 'true'` and a `deploy-script` annotation, with no `deploy-order`, automated sync or destructive finalizer. The Stage 040 aggregate includes it for static ownership checks; ordinary deployment does not apply or sync it. A missing optional Application is reported as not activated; an installed Application must reconcile normally at its own reviewed immutable revision.

After source publication, human review and separate deployment authorization, the supported targeted entrypoint is:

```bash
./stages/040-governed-models-as-a-service/deploy.sh --revision <reviewed-ref> --component 040-showback-demo
```

This path uses the cluster guard, published-source selection and ownership preflight, checks existing namespaces, CRDs and the native `edit` role’s actual MLflow experiment permissions, then applies, syncs and waits for this Application only. It does not run provider/database setup, mint keys, select a financial report, start models or enable native metering. It retains the normal Synced/Healthy requirement. The Qwen-only Component removes every active Mistral access reference; no degraded-health exception is supplied. It does not alter the existing Qwen checkpoint, quantization or serving owner. Stopped-source reconciliation does not establish inference or enforcement.

The explicit bounded profile is [qualification-qwen-only.json](../../../../stages/040-governed-models-as-a-service/showback-demo/qualification-qwen-only.json): Engineering/Support, existing Qwen NVFP4, three 120-second phases, at most 24 requests, 128 approximate input tokens and 32 output tokens. It is not qualification of Qwen FP8 or the full two-model scenario. `scenario.json` and the six generated access files remain the complete later scenario; do not regenerate those files from the qualification profile.\n\nGenerators and accounting tools remain in [showback-demo](../../../../stages/040-governed-models-as-a-service/showback-demo/README.md). Committed YAML in this component is the sole deployment output. Regenerate it with the package's `render-access.sh --write`, `generate-dashboards.sh --write`, `service-views/generate-dashboards.sh --write` and `native/render-integration.sh --write`; their `--check` modes detect drift. Never maintain duplicate manifests in the package or apply this component directly outside Argo CD.

## Validation

Offline checks render source only and start no workload:

```bash
kustomize build gitops/stages/040-governed-models-as-a-service/040-showback-demo
kustomize build gitops/stages/040-governed-models-as-a-service/040-showback-demo/model-drafts/mistral
./stages/040-governed-models-as-a-service/showback-demo/validate.sh
scripts/stage-apps.sh check-static 040
scripts/validate-stage-flow.sh
```

The normal Stage 040 validator checks shared policies separately from this optional bundle. When installed, this component also receives dedicated source/ownership checks, including zero publisher replicas, no publisher Pods and an empty selected-report ConfigMap. The explicit read-only mode requires the Application to exist:

```bash
./stages/040-governed-models-as-a-service/validate.sh --component 040-showback-demo
```

These checks establish a stopped source state only. Model inference, user/key enforcement, dashboard rendering, report scraping, native delivery and financial completeness remain separate acceptance gates. Not validated against a live cluster. Static review only.

Rollback is a reviewed revert of this optional component's source. A later live rollback must stop only owned work, preserve archived evidence and the retained workspace, revoke demo keys through the existing API, and use the normal non-cascading Application procedure. Shared model/Gateway/MLflow resources remain under their existing owners.

## Alignment with official guidance

| Topic | Repository choice | Status |
|---|---|---|
| MaaS identity and quotas [1] | One user-owned subscription and matching authorization policy per team; no committed keys | Candidate source; live enforcement unqualified |
| Native usage and showback [1] | Reuse existing MaaS/Gateway/observability; inert review inputs activate nothing | No native metering deployment or billing-grade claim |
| Model serving [2] | Shared Qwen stays with its owner; excluded Mistral draft stays stopped | Model qualification deferred |
| GitOps [3] | One disjoint Application, manual opt-in, immutable revision selection and normal health checks | Repository lifecycle policy; live reconciliation unqualified |
| MLflow [4] | Reuse the existing service and role; retain an isolated evidence workspace | Archive access/readback and retention qualification pending |

## References

1. [OpenShift AI 3.5: Govern LLM access with Models-as-a-Service](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/govern_llm_access_with_models-as-a-service/deploy-and-manage-models-as-a-service)
2. [OpenShift AI 3.5: Deploy models using distributed inference with llm-d](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/deploy_models_using_distributed_inference_with_llm-d/index)
3. [Red Hat OpenShift GitOps 1.21 documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_gitops/1.21)
4. [OpenShift AI 3.5: Working with MLflow](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_mlflow/index)
5. [Scenario and implementation plan](../../../../stages/040-governed-models-as-a-service/showback-demo/PLAN.md), [operations](../../../../stages/040-governed-models-as-a-service/showback-demo/OPERATIONS.md) and [implementation handoff](../../../../stages/040-governed-models-as-a-service/showback-demo/IMPLEMENTATION-HANDOFF.md)
