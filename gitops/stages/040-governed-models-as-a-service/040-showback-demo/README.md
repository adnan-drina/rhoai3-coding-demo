# Showback demo (`040-showback-demo`)

This optional Application packages the Qwen-only slice of the three-team showback scenario in one lifecycle boundary. Its first stopped deployment reconciled Synced/Healthy at `4349dd62429d15e68bb0e6935d3f1f0e617cdbc8`, with strict readback of 21 resources. Subsequent bounded inference, exact attribution, accounting and archive acceptance passed. Corrected release `adecf57cab87982f5b5a48c966860376474f8f62` is Synced/Healthy with exact 21-object readback, one Ready publisher and a current healthy native scrape (`up=1`). Actual financial queries reproduce the selected R2 report. Native configuration documents stay inert. See the [qualified run and correction evidence](../../../../stages/040-governed-models-as-a-service/showback-demo/evidence/qwen-live-20261019/README.md).

## Why

The demo connects governed team identities to explicit financial allocation and service-offer statements. A dedicated Application keeps its access grants, financial views, report publisher and archive workspace together without changing ordinary Stage 040 deployment or transferring shared platform ownership.

## What

The root Kustomize render contains exactly 24 resources with `components/qwen-only` enabled (26 with that Component removed after full-model qualification):

| Files | Objects and namespace |
|---|---|
| `team-*-subscription.yaml`, `team-*-auth-policy.yaml` | Two active `MaaSSubscription` / `MaaSAuthPolicy` pairs in `models-as-a-service`: Engineering and Support use Qwen. The generated full-scenario files retain the Marketing pair and Support Mistral reference; the enabled Component removes them from the active render |
| `archive-namespace.yaml`, `archive-rolebinding.yaml` | Retained Namespace `showback-reporting` and its `showback-mlflow-edit` RoleBinding to the existing native `edit` ClusterRole, whose aggregated MLflow experiment read/write permissions are checked before deployment |
| `dashboard-showback-*.yaml` | Three bounded allocation `PersesDashboard` resources in `redhat-ods-monitoring` |
| `dashboard-offer-*.yaml` | Three additional offer comparison dashboards: all external models, dedicated private and shared private; observed data and explicit missing states |
| `publisher-*.yaml` | Deployment `showback-report-publisher` at one Ready replica, HTTP configuration and selected R2 report ConfigMaps, Service and ServiceMonitor in `redhat-ods-monitoring`; live financial scraping verified |
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

This path uses the cluster guard, published-source selection and ownership preflight, checks existing namespaces, CRDs and the native `edit` role’s actual MLflow experiment permissions, then applies, syncs and waits for this Application only. It reconciles the report/publisher state authored in source, without provider/database setup, key minting, model startup or native metering activation. It retains the normal Synced/Healthy requirement. The Qwen-only Component removes every active Mistral access reference; no degraded-health exception is supplied. The existing Qwen checkpoint, quantization and serving owner remain unchanged.

The explicit bounded profile is [qualification-qwen-only.json](../../../../stages/040-governed-models-as-a-service/showback-demo/qualification-qwen-only.json): Engineering/Support, existing Qwen NVFP4, three 120-second phases, at most 24 requests, 128 approximate input tokens and 32 output tokens. The completed workload had 14 successful SSE requests and 1,753 tokens. Its R2 allocated-capacity estimate is $0.34: Engineering $0.15, Support $0.07 and platform idle $0.12, with other/unresolved allocation zero. This is not qualification of Qwen FP8, Mistral, actual AWS billed lifecycle or a full monthly service offer. `scenario.json` and the six generated access files remain the complete later scenario; do not regenerate those files from the qualification profile.

Generators and accounting tools remain in [showback-demo](../../../../stages/040-governed-models-as-a-service/showback-demo/README.md). Committed YAML in this component is the sole deployment output. Regenerate it with the package's `render-access.sh --write`, `generate-dashboards.sh --write`, `service-views/generate-dashboards.sh --write` and `native/render-integration.sh --write`; their `--check` modes detect drift. Never maintain duplicate manifests in the package or apply this component directly outside Argo CD.

The three bounded showback dashboards present cost allocation through a native horizontal bar chart and exact six-bucket table, usage through exact-count tables, and efficiency through capacity rows and full-width live charts. Evidence type and UTC report period remain visible; audit identities and source text sit in folded sections. Tables keep a bounded column width, hide metadata's constant `1`, map boolean states to text and preserve absent values as Unknown. Numeric formatting disables abbreviation. The bar adds human-readable labels to the unchanged allocation values; no second accounting formula is introduced. Browser acceptance at the deployed revision must verify both narrow and desktop layouts, exact counts, team versus idle allocation and no horizontal scrolling inside authored panels; API acceptance alone does not prove presentation.

The three offer comparison views use a separate definition file in the same generic generator. They preserve the bounded dashboards and five service-view candidates. External inventory and bounded request receipts remain separate from monthly provider charges; a trial endpoint does not establish a zero-price tariff. Dedicated has no observed agreement, sponsor or capacity evidence, and the shared Qwen run is never relabelled dedicated. Shared retains the observed bounded allocation while monthly tariff/recovery inputs remain Unknown. Monthly and probe queries use their own observed identity/hash guards. Metadata fallbacks distinguish missing evidence from publisher failure and never supply money. These new views require separate deployed browser acceptance.

## Validation

Offline checks render source only and start no workload:

```bash
kustomize build gitops/stages/040-governed-models-as-a-service/040-showback-demo
kustomize build gitops/stages/040-governed-models-as-a-service/040-showback-demo/model-drafts/mistral
./stages/040-governed-models-as-a-service/showback-demo/validate.sh
scripts/stage-apps.sh check-static 040
scripts/validate-stage-flow.sh
```

The normal Stage 040 validator checks shared policies separately from this optional bundle. When installed, this component receives dedicated source/ownership checks. Current source pairs one publisher replica with the nonempty R2 `metrics.prom` selection and report-hash annotation; validation requires exact selected-data readback and a current, fully Ready Deployment. The historical stopped branch requires zero replicas, no publisher Pods and an empty report. Mixed states are rejected. The explicit read-only mode requires the Application to exist:

```bash
./stages/040-governed-models-as-a-service/validate.sh --component 040-showback-demo
```

The Qwen run separately proved genuine user-owned keys, isolated JSON/SSE token attribution, missing/invalid-key 401 denials and reconciled accounting. Native collector configuration and samples established 30-second cadence; R2 calibrated boundary tolerance to 30 seconds while replaying unchanged raw inputs and retaining the original unresolved report. Both archive runs passed full hash readback as genuine `ai-admin`; Engineering access returned 403. All eight dashboards passed API ingestion and seven operational selector queries passed against the configured datasource. Publisher runtime and actual financial queries also passed at the corrected release. The three bounded dashboards subsequently passed [browser acceptance](../../../../stages/040-governed-models-as-a-service/showback-demo/evidence/qwen-live-20261019/dashboard-demo-ready-browser-readback.json) at `4231cec87ef2a50f3645874c3028eea66704a72b`: all 37 panels were checked at 788 px and 1440 px, exact counts and six cost buckets were verified, and authored panels had no horizontal overflow. The native app tab strip still scrolls, and long audit strings use hover.

The live selected canonical report SHA-256 is `b1d090696543beb0842108c528b7734cedc108789d14f6254eaa698fae26f44a`. Independent financial panel queries return $0.34 total, $0.15 Engineering, $0.07 Support and $0.12 idle, with pricing/allocation completeness 1 and unique selected-report/consumer rows. The current Ready Pod has the single healthy `up=1` scrape. Historical `up=0` belongs to the recorded failed startup Pod; guarded financial panels exclude it. See [publisher readback](../../../../stages/040-governed-models-as-a-service/showback-demo/evidence/qwen-live-20261019/publisher-live-readback.json) and [preserved startup correction](../../../../stages/040-governed-models-as-a-service/showback-demo/evidence/qwen-live-20261019/publisher-startup-correction.json).

For a subsequent report promotion, generate a validated ConfigMap with the package's `publish-report.sh --scenario FROZEN_SCENARIO --report REPORT --output METRICS --configmap-output CANDIDATE`. Review its public labels and financial values, replace canonical `publisher-report.yaml` with that selection and set `publisher-deployment.yaml` to one replica in the same reviewed, published revision. Sync only this Application through the targeted stage entrypoint. Keep private raw evidence outside Git. Returning to the stopped state requires both zero replicas and an empty report in source; never patch the live ConfigMap or scale the Deployment outside its owner.

The stock Apache wrapper initializes its native configuration before startup. Pass `-f /etc/showback/httpd.conf`, with each argument free of spaces; that file includes `/etc/httpd/conf/httpd.conf` before overriding the report directory. The earlier `-c "Include /etc/showback/httpd.conf"` invocation printed Apache's CLI usage and exited with code 1 at release `89036c17908519bc3ccc8d03f441f9b6cf60b7da`. The pinned image's verified registry configuration confirms the original config directory. The [upstream wrapper](https://github.com/sclorg/httpd-container/blob/master/2.4/root/usr/bin/run-httpd) expands arguments unquoted, which splits the earlier multiword directive; the running image's wrapper could not be extracted from the failed container. The subsequent targeted deployment at `adecf57cab87982f5b5a48c966860376474f8f62` passed runtime and financial-scrape acceptance.

Rollback is a reviewed revert of this optional component's source. A later live rollback must stop only owned work, preserve archived evidence and the retained workspace, revoke demo keys through the existing API, and use the normal non-cascading Application procedure. Shared model/Gateway/MLflow resources remain under their existing owners.

## Alignment with official guidance

| Topic | Repository choice | Status |
|---|---|---|
| MaaS identity and quotas [1] | Genuine user-owned subscriptions and matching authorization policies; no committed keys | Engineering/Support Qwen access and 401 denials passed; quota exhaustion and full cross-model matrix unqualified |
| Native usage and showback [1] | Reuse existing MaaS/Gateway/observability; inert review inputs activate nothing | No native metering deployment or billing-grade claim |
| Model serving [2] | Shared Qwen NVFP4 stays with its owner; excluded Mistral draft stays stopped | Bounded current-Qwen inference passed; FP8/Mistral and broader performance qualification deferred |
| GitOps [3] | One disjoint Application, manual opt-in, immutable revision selection and normal health checks | First Qwen-only stopped reconciliation passed at the recorded revision |
| MLflow [4] | Reuse the existing service and role; retain an isolated evidence workspace | Original/R2 upload and full hash readback passed; Engineering denied; retention enforcement unproven |

## References

1. [OpenShift AI 3.5: Govern LLM access with Models-as-a-Service](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/govern_llm_access_with_models-as-a-service/deploy-and-manage-models-as-a-service)
2. [OpenShift AI 3.5: Deploy models using distributed inference with llm-d](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/deploy_models_using_distributed_inference_with_llm-d/index)
3. [Red Hat OpenShift GitOps 1.21 documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_gitops/1.21)
4. [OpenShift AI 3.5: Working with MLflow](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_mlflow/index)
5. [Scenario and implementation plan](../../../../stages/040-governed-models-as-a-service/showback-demo/PLAN.md), [operations](../../../../stages/040-governed-models-as-a-service/showback-demo/OPERATIONS.md) and [implementation handoff](../../../../stages/040-governed-models-as-a-service/showback-demo/IMPLEMENTATION-HANDOFF.md)
