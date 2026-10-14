# MaaS operators (`040-maas-operators`)

This Application installs the operators that OpenShift AI Models-as-a-Service (MaaS) and Distributed Inference with llm-d build on: Red Hat Connectivity Link (Kuadrant) with its Authorino, Limitador and DNS operators, OpenShift Service Mesh 3, and the Leader Worker Set Operator. It creates no policy or gateway itself. The `040-gateway-governance` component creates the Kuadrant and Authorino instances on top of these operators, and the OpenShift AI MaaS controller generates the AuthPolicy and TokenRateLimitPolicy objects that they enforce.

| | |
|---|---|
| Argo CD Application | `040-maas-operators` ([manifest](../../../argocd/app-of-apps/040-governed-models-as-a-service/maas-operators.yaml)) |
| Deployed by | `stages/040-governed-models-as-a-service/deploy.sh` (deploy-order 1) |
| Validated by | `stages/040-governed-models-as-a-service/validate.sh` → `validate-native.py` ("Six selected operators and current workloads"); `scripts/platform/check-operator-policy.py --verify` (channel and minimum version); `approve-operators.sh` (read-only wait for Automatic resolution) |
| Sync | Automated, `prune: true`, `selfHeal: true`; `CreateNamespace`, `SkipDryRunOnMissingResource`, `ServerSideDiff`, `RespectIgnoreDifferences`; compare-option `ServerSideDiff=true`; retry 10x with backoff 5s to 3m |
| Depends on | Stage 010 (OpenShift AI 3.5.1 and the `redhat-operators` catalog) |
| Used by | `040-gateway-governance` (Kuadrant and Authorino CRs), the OpenShift AI MaaS controller (generated AuthPolicy and TokenRateLimitPolicy), `040-local-models` (llm-d serving through the MaaS Gateway) |

## Why

MaaS enforces API-key authentication and per-subscription token limits through Red Hat Connectivity Link. The OpenShift AI 3.5 MaaS guide lists Connectivity Link 1.4.x in `openshift-operators`, with a ready `Kuadrant` resource in `kuadrant-system`, as a platform prerequisite [1]. Connectivity Link uses Authorino for authentication and Limitador for rate limiting [1]. The Connectivity Link 1.4 installation guide uses the `stable` channel and expects the Authorino, DNS and Limitador operators to be present after installation [2].

The Leader Worker Set Operator is the OpenShift operator for leader/worker pod groups [4]. The llm-d guide needs it only for multi-node deployments [3]. This demo serves single-node models, so LWS is installed as a prerequisite for that option, not for the current models.

All operators share one Application because they share one lifecycle: an operator upgrade is a platform change. Model, access and policy changes live in other components and do not touch the operators.

## What

### `lws/`: Leader Worker Set Operator

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| Namespace | `openshift-lws-operator` | (cluster) | Operator namespace (wave 1) |
| OperatorGroup | `lws-operator` | `openshift-lws-operator` | Own-namespace install, `upgradeStrategy: Default` (wave 2) |
| Subscription | `leader-worker-set` | `openshift-lws-operator` | Channel `stable-v1.0`, Automatic (wave 3) |
| LeaderWorkerSetOperator | `cluster` | (cluster) | Operator instance, `managementState: Managed`, log level `Normal` (wave 7, `SkipDryRunOnMissingResource`) |

### `rhcl/`: Connectivity Link and its dependencies

All Subscriptions are in `openshift-operators` (global OperatorGroup), source `redhat-operators`, approval Automatic, wave 3.

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| Subscription | `rhcl-operator` | `openshift-operators` | Connectivity Link (Kuadrant) operator, channel `stable`, with `config.env` and `config.resources` (see How) |
| Subscription | `authorino-operator` | `openshift-operators` | Authorino operator, channel `stable` |
| Subscription | `limitador-operator` | `openshift-operators` | Limitador operator, channel `stable` |
| Subscription | `dns-operator` | `openshift-operators` | DNS operator, channel `stable` |
| Subscription | `servicemeshoperator3` | `openshift-operators` | OpenShift Service Mesh 3 operator, channel `stable-3.4` |

### Objects not in Git

| Object | Owner |
|---|---|
| InstallPlans, CSVs, operator Deployments | OLM |
| `Kuadrant`/`Authorino` instances, `kuadrant-system` namespace | `040-gateway-governance` |
| `Limitador` instance `limitador` in `kuadrant-system` | Kuadrant operator (created from the `Kuadrant` CR) |
| `AuthPolicy maas-gateway-auth`, `TokenRateLimitPolicy` objects (`gateway-default-deny`, `maas-trlp-<model>`) | OpenShift AI MaaS controller |

Live installed CSVs (read 2026-10-14): `rhcl-operator.v1.4.3`, `authorino-operator.v1.4.3`, `limitador-operator.v1.4.2`, `dns-operator.v1.4.2`, `servicemeshoperator3.v3.4.3`, `leader-worker-set.v1.0.1`.

## How

- **Installation.** Every Subscription uses Automatic approval on a named channel, without `startingCSV`. The repository's fresh-install policy (`scripts/platform/check-operator-policy.py`) refuses a channel other than the reviewed one and an installed version outside the qualified minor line (`rhcl-operator` 1.4.3+, `authorino-operator` 1.4.3+, `limitador-operator` 1.4.2+, `dns-operator` 1.4.2+, `servicemeshoperator3` 3.4.3+, `leader-worker-set` 1.0.1+). `deploy.sh` runs it before it applies the Applications, and `approve-operators.sh` waits read-only for resolution. It never approves an InstallPlan.
- **Ordering.** Namespace (wave 1), OperatorGroup (wave 2), Subscriptions (wave 3), then the LWS instance (wave 7) once its CRD exists. `SkipDryRunOnMissingResource` lets the first sync pass before the CRD is registered. Argo CD retry covers the CRD race.
- **Connectivity Link Subscription `config`.** The `rhcl-operator` Subscription sets `AUTH_SERVICE_TIMEOUT=2s` on the Kuadrant operator and raises its requests and limits to 500m/512Mi and 2 CPU/1Gi. The Kuadrant operator Deployment reads `AUTH_SERVICE_TIMEOUT`, but the Connectivity Link 1.4 installation guide does not describe it. The manifest gives no reason for the value.
- **Explicit dependency Subscriptions.** Authorino, Limitador and DNS are declared as their own Subscriptions, so their channel is reviewed and drift is visible in Argo CD. The installation guide has you verify these operators after installing Connectivity Link [2].
- **Service Mesh.** The MaaS Gateway uses the OpenShift Gateway API controller (`openshift.io/gateway-controller/v1`). The Ingress Operator installs its own lightweight Istio control plane for that controller [5]. Connectivity Link 1.3 and later do not need a separate Service Mesh installation, and the guide says to use 3.4 if you do install it [2]. The demo installs `servicemeshoperator3` on `stable-3.4`.
- **No delegated fields.** The Application has no `ignoreDifferences`.
- **Secrets.** None.
- **Cluster-specific values.** None.

## Validation

`validate-native.py` renders the stage and requires exactly six Subscriptions. For each one, the live channel, source, approval and `startingCSV` must match Git, `installedCSV` must equal `currentCSV`, the CSV phase must be `Succeeded`, and every Deployment the CSV declares must be owned by that CSV and available. The `deploy.sh` preflight (`preflight.py`) refuses existing Subscriptions that another owner tracks.

By hand:

```bash
oc get subscription rhcl-operator authorino-operator limitador-operator dns-operator servicemeshoperator3 -n openshift-operators \
  -o custom-columns=NAME:.metadata.name,CHANNEL:.spec.channel,CSV:.status.installedCSV
oc get subscription leader-worker-set -n openshift-lws-operator -o jsonpath='{.status.installedCSV}{"\n"}'
```

## Alignment with official guidance

| Topic | Official guidance (link) | This repository | Status |
|---|---|---|---|
| Connectivity Link version and namespace | MaaS needs Connectivity Link 1.4.x in `openshift-operators` [1] | `rhcl-operator` 1.4.3 in `openshift-operators` | Aligned |
| Connectivity Link channel | `stable` channel [2] | `stable` | Aligned |
| Authorino, Limitador, DNS operators | Present after installation; the guide has you verify them [2] | Explicit Subscriptions on `stable` | Aligned |
| Gateway API provider | OpenShift Gateway controller is the default. No separate Service Mesh is required for Connectivity Link 1.3+; use 3.4 if installed [2][5] | `servicemeshoperator3` on `stable-3.4`; the Gateway uses the OpenShift controller | Aligned on the version. Gap: no consumer of the separate Service Mesh operator is documented |
| LWS for llm-d | Needed only for multi-node llm-d deployments [3] | Installed; all served models are single-node | Deviation (justified: kept ready for a multi-node topology; not used by the current models) |
| LWS installation | Leader Worker Set Operator chapter, OpenShift 4.22 [4] | `openshift-lws-operator`, own-namespace OperatorGroup, `stable-v1.0`, CR `cluster` | Aligned |
| Upgrade approval | OLM Automatic or Manual are both supported | Automatic, gated by a channel and minimum-version policy | Aligned (repository policy) |
| Kuadrant operator tuning | Not covered by the installation guide [2] | `AUTH_SERVICE_TIMEOUT=2s`, raised resources | Gap: the reason for the setting is not recorded |

## References

1. Govern LLM access with Models-as-a-Service, sections 1.2 "Platform and Operator prerequisites for Models-as-a-Service" and 1.18.2 (Kuadrant observability), Red Hat OpenShift AI Self-Managed 3.5. https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/govern_llm_access_with_models-as-a-service/index
2. Install Connectivity Link on OpenShift Container Platform, sections 1.1.1, 1.2 and 1.3, Red Hat Connectivity Link 1.4. https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html/install_connectivity_link/rhcl-install-on-ocp
3. Deploy models using Distributed Inference with llm-d, section 1.1 "Enable Distributed Inference with llm-d", Red Hat OpenShift AI Self-Managed 3.5. https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/deploy_models_using_distributed_inference_with_llm-d/index
4. AI workloads, "Leader Worker Set Operator" (3.3.1 "Installing the Leader Worker Set Operator"), OpenShift Container Platform 4.22. https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html/ai_workloads/leader-worker-set-operator
5. Ingress and load balancing, "Configuring Gateway API" (3.2.1), OpenShift Container Platform 4.22. https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html/ingress_and_load_balancing/configuring-gateway-api
