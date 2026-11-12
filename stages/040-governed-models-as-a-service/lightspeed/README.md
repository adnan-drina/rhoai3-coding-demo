# OpenShift Lightspeed model selection

OpenShift Lightspeed answers on Qwen, the private production model, through Models-as-a-Service. Nemotron 3 Ultra, an
approved external model on the same MaaS gateway, subscription and key, is configured as a second provider for while
Qwen is parked. Lightspeed uses one default provider and has no automatic failover (`spec.ols.defaultProvider` in the
`OLSConfig`), and its readiness probe calls that provider, so the console assistant stops answering while its default
model is down. This script moves the default between the two.

| Script | When to run |
|---|---|
| `select-model.sh nemotron` | Before parking Qwen, or when Lightspeed reports `ApiReady=False` because Qwen is parked. Lightspeed then sends cluster questions and the resources it reads to an external provider. |
| `select-model.sh qwen` | Once Qwen serves again. Refused while Qwen has no replicas. |

The selection is a Kustomize patch on the `040-openshift-lightspeed` Argo CD Application, beside the provider URLs that
`deploy.sh` sets there: Argo CD would revert a direct `OLSConfig` edit. Each switch restarts the Lightspeed app server
(about a minute); conversation history stays in its PostgreSQL. A Stage 040 `deploy.sh` run returns Lightspeed to Qwen,
and `validate.sh` warns while the fallback is selected. Details and the reasons for the model choice are in the
[component README](../../../gitops/stages/040-governed-models-as-a-service/040-openshift-lightspeed/README.md).
