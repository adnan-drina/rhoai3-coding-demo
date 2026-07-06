# API Tier Map

This table captures the Red Hat OpenShift AI API Tiers excerpt supplied for the
active repo baseline. Recheck the upstream Red Hat source when the baseline
changes.

## Tier 1

| API version example | Tier |
|---------------------|------|
| `hardwareprofiles.infrastructure.opendatahub.io/v1` | Tier 1 |
| LLM-D Batch Gateway Batches REST API v1 | Tier 1 |
| LLM-D Batch Gateway Files REST API v1 | Tier 1 |
| `notebooks.kubeflow.org/v1` | Tier 1 |
| `odhapplications.dashboard.opendatahub.io/v1` | Tier 1 |
| `odhdocuments.dashboard.opendatahub.io/v1` | Tier 1 |
| `odhquickstarts.console.openshift.io/v1` | Tier 1 |
| OpenVino Model Server API, Open Inference Protocol v2.0 | Tier 1 |
| `pytorchjobs.kubeflow.org/v1` | Tier 1 |
| `rayclusters.ray.io/v1` | Tier 1 |

## Tier 2

| API version example | Tier |
|---------------------|------|
| CodeFlare SDK 0.16.0 | Tier 2 |
| `datasciencecluster.opendatahub.io/v1` | Tier 2 |
| `dscinitialization.opendatahub.io/v1` | Tier 2 |
| DSP Server API, REST endpoint v2 | Tier 2 |
| Feast Online Feature Server REST API | Tier 2 |
| Feast Registry Server REST API v1 | Tier 2 |
| `feastoperators.components.platform.opendatahub.io/v1` | Tier 2 |
| `inferenceservice.serving.kserve.io/v1beta1` | Tier 2 |
| `llminferenceservices.serving.kserve.io/v1alpha1` | Tier 2 |
| `llminferenceserviceconfigs.serving.kserve.io/v1alpha1` | Tier 2 |
| MLflow REST API v2 and v3 | Tier 2 |
| `mlflows.opendatahub.io/v1` | Tier 2 |
| Model Registry Python client 0.3.3 | Tier 2 |
| Model Registry REST API for Dashboard v1alpha3 | Tier 2 |
| `modelregistry.opendatahub.io/v1beta1` | Tier 2 |
| `rayjobs.ray.io/v1` | Tier 2 |
| `servingruntime.serving.kserve.io/v1alpha1` | Tier 2 |
| TrustyAI Python library 0.6.0 | Tier 2 |
| TrustyAI REST API v1alpha1 | Tier 2 |
| `trustyai.opendatahub.io/v1alpha1` | Tier 2 |

## Tier 4

| API version example | Tier |
|---------------------|------|
| `*.argoproj.io/v1alpha1` | Tier 4 |
| `codeflares.components.platform.opendatahub.io/v1alpha1` | Tier 4 |
| Dashboard REST API | Tier 4 |
| `dashboards.components.platform.opendatahub.io/v1alpha1` | Tier 4 |
| `datasciencepipelinesapplications.opendatahub.io/v1` | Tier 4 |
| `featuretrackers.dscinitialization.opendatahub.io` | Tier 4 |
| `kserves.components.platform.opendatahub.io/v1alpha1` | Tier 4 |
| `kueues.components.platform.opendatahub.io/v1alpha1` | Tier 4 |
| `modelcontrollers.components.platform.opendatahub.io/v1alpha1` | Tier 4 |
| `modelmeshservings.components.platform.opendatahub.io/v1alpha1` | Tier 4 |
| `modelregistries.components.platform.opendatahub.io/v1alpha1` | Tier 4 |
| `monitorings.services.platform.opendatahub.io/v1alpha1` | Tier 4 |
| Ray cluster job API, REST endpoint 4.0.0 | Tier 4 |
| `rays.components.platform.opendatahub.io/v1alpha1` | Tier 4 |
| `trainingoperators.components.platform.opendatahub.io/v1alpha1` | Tier 4 |
| `trustyais.components.platform.opendatahub.io/v1alpha1` | Tier 4 |
| `workbenches.components.platform.opendatahub.io/v1alpha1` | Tier 4 |

## Beta

| API version example | Tier |
|---------------------|------|
| `llamastackdistributions.llamastack.io/v1alpha1` | Beta |

## Alpha

| API version example | Tier |
|---------------------|------|
| `*.serving.kserve.io/v1alpha1` except the listed KServe exceptions | Alpha |
| `auths.services.platform.opendatahub.io/v1alpha1` | Alpha |
| Llama Stack REST API | Alpha |
| `odhdashboardconfigs.opendatahub.io/v1alpha` | Alpha |
| `sparkoperator.k8s.io/v1beta2` | Alpha |

## KServe Footnote

All APIs in `*.serving.kserve.io/v1alpha1` are currently Alpha except:

- `inferenceservice`
- `llminferenceserviceconfigs`
- `llminferenceservices`
- `servingruntime`
