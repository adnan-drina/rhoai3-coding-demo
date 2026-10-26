---
name: rhoai-api-tiers
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when a manifest in this repo adds or changes an OpenShift AI API version
  (DataScienceCluster/DSCInitialization v2, Auth v1alpha1, OdhDashboardConfig
  v1alpha, HardwareProfile, LLMInferenceService v1alpha2, InferenceService,
  ServingRuntime, MaaS maas.opendatahub.io, ExternalProvider/ExternalModel,
  MLflow, ModelRegistry, EvalHub, MCPServer, KFP Pipeline), when a README states
  how stable an API is, or when planning an upgrade that may deprecate an API.
  Holds the repo's API inventory and the review rule; tier values come from the
  Red Hat "OpenShift AI: API Tiers" article. Do NOT use for feature support
  posture (use rhoai-release-and-support-posture), field-level schemas (use
  oc explain and the component skill), or manifest structure review (use
  review-manifest-compliance).
---

# RHOAI API Tiers

Thin skill: the OpenShift AI APIs this repo writes, and how to classify them.
Tier meanings and the API-to-tier table are in the Red Hat Customer Portal
article [OpenShift AI: API Tiers][tiers]; the table requires a subscriber login.

## When to use

- A manifest under `gitops/stages/` changes `apiVersion` for an OpenShift AI kind.
- A README or slide calls an interface "stable" or "supported".
- Before a minor upgrade, to list APIs that may be deprecated.

## Repo decisions

API inventory (kinds this repo writes; one example path each):

| API | Kind | Where in Git |
|---|---|---|
| `datasciencecluster.opendatahub.io/v2`, `dscinitialization.opendatahub.io/v2` | DataScienceCluster, DSCInitialization | `gitops/stages/010-openshift-ai-platform-foundation/010-rhoai-platform/` |
| `services.platform.opendatahub.io/v1alpha1` | Auth | `010-rhoai-platform/auth.yaml` |
| `opendatahub.io/v1alpha` | OdhDashboardConfig | `010-rhoai-platform/odhdashboardconfig.yaml` |
| `infrastructure.opendatahub.io/v1` | HardwareProfile | `gitops/stages/020-gpu-infrastructure-private-ai/020-gpu-quotas/hardware-profiles/` |
| `serving.kserve.io/v1alpha2` | LLMInferenceService, LLMInferenceServiceConfig | `gitops/stages/040-governed-models-as-a-service/040-local-models/` |
| `serving.kserve.io/v1beta1`, `serving.kserve.io/v1alpha1` | InferenceService, ServingRuntime | `gitops/stages/050-model-evaluation/050-model-qualification/candidate-qwen3-8-27b-nvfp4.yaml`, `gitops/stages/050-model-evaluation/050-model-qualification/serving-runtime.yaml` |
| `maas.opendatahub.io/v1alpha1` | MaaSModelRef, MaaSSubscription, MaaSAuthPolicy | `gitops/stages/040-governed-models-as-a-service/040-model-access/`, `.../local-models/qwen38-27b-maas-modelref.yaml` |
| `inference.opendatahub.io/v1alpha1` | ExternalProvider, ExternalModel | `gitops/stages/040-governed-models-as-a-service/040-external-models/` |
| `mlflow.opendatahub.io/v1` | MLflow | `gitops/stages/050-model-evaluation/050-mlflow/mlflow.yaml` |
| `modelregistry.opendatahub.io/v1beta1` | ModelRegistry | `gitops/stages/030-private-model-serving/030-private-model-serving/model-discovery/registry/modelregistry-demo.yaml` |
| `trustyai.opendatahub.io/v1` | EvalHub | `gitops/stages/050-model-evaluation/050-evalhub/evalhub.yaml` |
| `mcp.x-k8s.io/v1alpha1` | MCPServer | `gitops/stages/060-agent-runtime-and-agentops/060-agent-tools/hosting/mcpserver.yaml` |
| `pipelines.kubeflow.org/v2beta1` | Pipeline, PipelineVersion | `gitops/stages/050-model-evaluation/050-model-qualification/pipeline/` |

| Decision | Where in Git | Official section |
|---|---|---|
| Configure components through the DSC only; per-component CRs (`*.components.platform.opendatahub.io`) are read for readiness, never written | `gitops/stages/040-governed-models-as-a-service/040-maas-platform/jobs/enable-maas-job.yaml`, `gitops/stages/050-model-evaluation/050-mlflow/dsc-enablement/enable-job.yaml` | [Install components by CLI][comp-cli] |
| Use the API version of the 3.5 documented example (DSC and DSCI `v2`) | `010-rhoai-platform/datasciencecluster.yaml`, `010-rhoai-platform/README.md` | [Install components by CLI][comp-cli] |
| Tier per API is not recorded here: the article table is login-gated and was not readable on review (2026-10-15); write "tier unverified" rather than infer it | this skill | [API Tiers][tiers] |

## Procedure

1. List the API versions a change touches (`git grep -n '^apiVersion:' -- gitops/stages/<stage>`).
2. Look each up in the [API Tiers][tiers] article (logged in). Do not infer a
   tier from the version string: an `alpha` version can be a supported tier and
   a `v1` can be internal.
3. Record the tier and its article date in the component README Alignment
   table when the API is user-facing; label preview APIs as the feature's
   posture (see `rhoai-release-and-support-posture`).
4. Confirm the served schema before writing fields, after the OpenShift safety
   guard in `AGENTS.md`:

   ```bash
   oc api-resources --api-group=serving.kserve.io
   oc explain llminferenceservice.spec --api-version=serving.kserve.io/v1alpha2
   ```

5. Before an upgrade, re-read [Support removals][removals] for deprecated APIs
   in the inventory above and update this table if an API version changes.

## Pitfalls

- The 3.4-era copy of the tier table formerly in this skill listed DSC/DSCI
  `v1` and LLMInferenceService `v1alpha1`; this repo now uses `v2` and
  `v1alpha2`. Never reuse old tier values for new versions.
- `odhdashboardconfigs` is `opendatahub.io/v1alpha` (no digit after alpha); copy
  it exactly.
- `MCPServer` (`mcp.x-k8s.io`) is exposed by the Technology Preview MCP
  Lifecycle Operator component (`stages/060-agent-runtime-and-agentops/README.md`);
  label it with that posture.

## Official documentation (OpenShift AI 3.5)

| Topic | Section |
|---|---|
| API tier meanings, deprecation windows, API table | [OpenShift AI: API Tiers][tiers] (Customer Portal, login) |
| DSC API version used in examples | [Install components by CLI][comp-cli] |
| Deprecated and removed APIs | [Support removals][removals] |

## Related skills

`rhoai-release-and-support-posture`, `rhoai-dsci-dsc-configuration`,
`review-manifest-compliance`, `review-gitops-change`.

[tiers]: https://access.redhat.com/articles/7047935
[comp-cli]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#installing-openshift-ai-components-using-cli_component-install
[removals]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/release_notes/index#support-removals_relnotes
