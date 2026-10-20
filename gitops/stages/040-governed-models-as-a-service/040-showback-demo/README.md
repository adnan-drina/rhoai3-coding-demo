# Showback demo (`040-showback-demo`)

This optional Application packages the three-team showback demo in one lifecycle boundary: team access, the selected cost report and its publisher, the financial dashboards, the evidence workspace and continuous external metering. Generators, accounting tools and the scenario live in [showback-demo](../../../../stages/040-governed-models-as-a-service/showback-demo/README.md); commands are in its [OPERATIONS.md](../../../../stages/040-governed-models-as-a-service/showback-demo/OPERATIONS.md).

## Why

The demo needs its own team subscriptions, dashboards and metering ledger without changing how ordinary Stage 040 deploys or who owns the shared model, gateway and MLflow resources. One manual-sync Application keeps all of that together and removable.

## What

With `components/qwen-only` enabled the root renders 33 resources: 22 for access, reporting and dashboards, and 11 for metering.

| Files | Objects |
|---|---|
| `team-*-subscription.yaml`, `team-*-auth-policy.yaml` | `MaaSSubscription` and `MaaSAuthPolicy` per team in `models-as-a-service`. `components/qwen-only` keeps only Engineering and Support on Qwen; the Marketing pair and Support's Mistral access stay in source for the full scenario |
| `archive-namespace.yaml`, `archive-rolebinding.yaml` | Namespace `showback-reporting` and a RoleBinding of `rhods-admins` to the native `edit` role, which carries the MLflow experiment permissions for evidence archives |
| `dashboard-showback-*.yaml` | Costs, Usage and Efficiency `PersesDashboard`s in `redhat-ods-monitoring` |
| `dashboard-offer-*.yaml` | External model, Dedicated private and Shared private offer dashboards |
| `service-views/` | Five monthly service-offer dashboards (platform-only candidates) |
| `publisher-*.yaml` | Deployment `showback-report-publisher` (digest-pinned UBI Apache, one replica), its configuration, the selected report ConfigMap, Service and ServiceMonitor |
| `metering/` | Metering backend and PostgreSQL 16 (retained PVC), database Secret, price catalog, profile ConfigMap, ImageStream, Services, ServiceMonitor and the NetworkPolicy for gateway-to-backend traffic |

`model-drafts/mistral/` holds a zero-replica Mistral Small 4 `LLMInferenceService` and `MaaSModelRef`. It is not part of the root render; adding it requires a reviewed Kustomize change and model qualification.

The Application owns no shared Namespace, Qwen resource, Gateway, operator, MaaS `Config` or LokiStack. Qwen stays with `040-local-models`, GPU capacity with Stage 020 and MLflow with Stage 050. The metering plugin entry in the MaaS-owned `openshift-ingress/payload-processing-plugins` ConfigMap is written by the targeted deployment from `metering/profile.yaml`, not by Argo CD, so reverting the Application alone does not remove it.

## How

[040-showback-demo](../../../applications/040-showback-demo.yaml) uses the `rhoai-demo` project and the `openshift-gitops` destination, with `demo.rhoai.io/optional: 'true'`, a `deploy-script` annotation, no `deploy-order` and no automated sync. Deploy and validate it only through the stage entrypoints:

```bash
./stages/040-governed-models-as-a-service/deploy.sh --component 040-showback-demo --revision <full-sha>
RHOAI_STAGE040_SHOWBACK_EXPECTED_REVISION=<full-sha> \
  ./stages/040-governed-models-as-a-service/validate.sh --component 040-showback-demo
```

Committed YAML here is the only deployment output. Regenerate it with the package's `render-access.sh --write`, `generate-dashboards.sh --write` and `service-views/generate-dashboards.sh --write`; each has a `--check` mode for drift. Do not edit generated files by hand or apply this folder outside Argo CD.

The publisher serves exactly one reviewed report. To change it, generate a ConfigMap with the package's `publish-report.sh --configmap-output`, replace `publisher-report.yaml` and deploy the new revision. To stop it, set zero replicas and an empty report in the same revision. Validation accepts only those two states.

## Validation

Offline:

```bash
kustomize build gitops/stages/040-governed-models-as-a-service/040-showback-demo
./stages/040-governed-models-as-a-service/showback-demo/validate.sh
scripts/stage-apps.sh check-static 040
scripts/validate-stage-flow.sh
```

Live, `validate.sh --component 040-showback-demo` checks the Application's revision, sync and health, every owned object, the publisher's report and readiness, and the metering profile. Broad Stage 040 validation prints `SKIP 040-showback-demo (not activated)` while the Application is absent.

Rollback is a revert of this component's source. Disable metering first through `metering/profile.yaml` (see the package operations), keep the archive namespace and the metering PVC, revoke demo keys through MaaS, and leave shared model, gateway and MLflow resources with their owners.

## Alignment with official guidance

| Topic | Repository choice | Status |
|---|---|---|
| MaaS identity and quotas [1] | One user-owned subscription and matching authorization policy per team; keys minted by the users, never committed | Engineering and Support verified on Qwen; Marketing, cross-model denials and quota exhaustion not yet tested |
| Usage and metering [1] | Native MaaS usage counters for allocation; the shipped IPP external-metering plugin feeds a community backend for external models | Allocation verified; external metering deployed, live acceptance open; Developer Preview plugin, community backend |
| Model serving [2] | Shared Qwen stays with its owner; Mistral draft stays stopped and outside the render | Mistral and Qwen FP8 not yet qualified |
| GitOps [3] | One optional manual-sync Application with immutable revisions; shared fields keep their owners | Deployed and validated through the stage entrypoints |
| MLflow [4] | Existing MLflow service and native `edit` role in a separate `showback-reporting` workspace | Archive upload and hash readback verified; Engineering user denied; retention not enforced |

## References

1. [OpenShift AI 3.5: Govern LLM access with Models-as-a-Service](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/govern_llm_access_with_models-as-a-service/deploy-and-manage-models-as-a-service)
2. [OpenShift AI 3.5: Deploy models using distributed inference with llm-d](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/deploy_models_using_distributed_inference_with_llm-d/index)
3. [Red Hat OpenShift GitOps 1.21 documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_gitops/1.21)
4. [OpenShift AI 3.5: Working with MLflow](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_mlflow/index)
