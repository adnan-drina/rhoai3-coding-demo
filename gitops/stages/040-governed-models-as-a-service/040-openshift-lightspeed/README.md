# 040-openshift-lightspeed

OpenShift Lightspeed, the assistant in the OpenShift web console, answers on the demo's private production model:
Qwen 3.8 through Models-as-a-Service, with its own subscription, quota and metering. The environment provisioner
installs the Lightspeed operator and a first `OLSConfig` with an Azure OpenAI provider; this component takes over that
`OLSConfig`, adds Qwen as the default provider and keeps Azure as a second, selectable one.

| | |
|---|---|
| Application | [040-openshift-lightspeed](../../../applications/040-openshift-lightspeed.yaml), deploy-order 8, after `040-model-access` |
| Deployed by | `stages/040-governed-models-as-a-service/deploy.sh`, which passes the cluster-specific provider URLs as a `source.kustomize` patch |
| Validated by | `stages/040-governed-models-as-a-service/validate.sh` (Qwen is the default provider at this cluster's MaaS api listener, the key Secret carries `apitoken`, the Lightspeed API is Ready) |
| Requires | The Lightspeed operator (OLSConfig API) preinstalled by the provisioner, `qwen3-8-27b` and the `openshift-lightspeed` subscription in `040-model-access` |

## Why

- **Private model.** Cluster questions and the resources Lightspeed reads stay on the private model instead of
  leaving for an external provider, and Lightspeed traffic is governed and metered like every other MaaS consumer.
- **Documented provider path.** The Lightspeed "Configure" guide documents Red Hat OpenShift AI as a provider: type
  `rhoai_vllm`, a URL ending in `/v1`, and a Secret whose key is `apitoken` [1]. MaaS serves the OpenAI-compatible
  `/v1` API on its gateway; its certificate is publicly trusted, so no `additionalCAConfigMapRef` is needed.
- **Stage 040.** Lightspeed consumes a governed model, so it is configured once MaaS, Qwen and the subscriptions exist,
  like the playground and Dev Spaces key provisioners.

## What

| Kind | Name | Namespace | Notes |
|---|---|---|---|
| ServiceAccount, Role, RoleBinding | `lightspeed-maas-key-provisioner` | `openshift-lightspeed` | Owns the MaaS subscription; may create the Secret and update only `qwen-maas-api-keys`. Wave 18 |
| Role, RoleBinding | `lightspeed-maas-key-provisioner-gateway-reader` | `openshift-ingress` | Reads the MaaS Gateway's api hostname. Wave 18 |
| Job (Sync hook) | `provision-lightspeed-maas-key` | `openshift-lightspeed` | Keeps a MaaS key in Secret `qwen-maas-api-keys` (key `apitoken`, plus `key_id`, `expires_at`); re-uses an active key, re-mints an expired or revoked one. Wave 19 |
| OLSConfig | `cluster` | cluster | Providers `qwen-maas` (`rhoai_vllm`, `https://maas.<cluster-domain>/v1`, model `publishers/internal-models/models/qwen3-8-27b`, 128k context, 4096 response tokens) and `Azure` (the provisioner's). Default `qwen-maas`. Other settings are the provisioner's. Wave 20 |

The MaaSSubscription and MaaSAuthPolicy `openshift-lightspeed` (Qwen, 2,000,000 tokens per hour, priority 60) live in
`040-model-access` with the other subscriptions.

## How

- **Cluster-specific values.** Git holds placeholder URLs. `deploy.sh` patches `providers/0/url` with
  `https://maas.<ingress domain>/v1` and `providers/1/url` with the Azure endpoint read from the live `OLSConfig`
  (never committed); without an Azure provider it removes that entry.
- **Key lifecycle.** Keys default to the MaaS maximum (90 days). Every sync re-checks the key; an expired one is
  re-minted. `credentialHotReload` stays off, so a re-minted key reaches Lightspeed after its app server restarts
  (`oc rollout restart deployment/lightspeed-app-server -n openshift-lightspeed`).
- **Operator version.** The provisioner's `stable` channel installed operator 2.0.0; Red Hat publishes the "1.0"
  documentation set only. The fields used here are in both the 1.0 API reference and the installed CRD.

## Validation

```bash
oc get olsconfig cluster -o jsonpath='{.spec.ols.defaultProvider} {.spec.ols.defaultModel}{"\n"}'
oc get olsconfig cluster -o jsonpath='{range .status.conditions[*]}{.type}={.status}{"\n"}{end}'
```

Ask a question in the console's Lightspeed panel; the answer comes from Qwen (MaaS metering shows the
`openshift-lightspeed` subscription).

## Alignment with official guidance

| Topic | Official guidance | This component | Status |
|---|---|---|---|
| Provider | Red Hat OpenShift AI provider: `rhoai_vllm`, URL ending in `/v1`, Secret key `apitoken` [1] | Same, pointed at the MaaS gateway's OpenAI-compatible API with a MaaS key | Aligned |
| Trusted CA | `additionalCAConfigMapRef` for a provider behind a private CA [1] | Not set: the MaaS gateway certificate is publicly trusted | Aligned |
| Multiple providers | Several providers, one default [1] | `qwen-maas` default, provisioner's `Azure` kept | Aligned |
| Documentation version | Red Hat publishes the "1.0" set | Installed operator 2.0.0; fields used exist in the 1.0 reference and the installed CRD | Gap: no 2.0 documentation yet |

## References

1. Configure, "Creating the credentials secret" and "Creating the Lightspeed custom resource file", Red Hat OpenShift Lightspeed 1.0. https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/configure/index
