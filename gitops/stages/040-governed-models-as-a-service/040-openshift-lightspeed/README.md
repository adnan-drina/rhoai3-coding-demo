# 040-openshift-lightspeed

OpenShift Lightspeed, the assistant in the OpenShift web console, answers on the demo's private production model:
Qwen 3.8 through Models-as-a-Service, with its own subscription, quota and metering. Nemotron 3 Ultra, an approved
external model behind the same gateway, subscription and key, is its fallback while Qwen is parked. The environment
provisioner installs the Lightspeed operator and a first `OLSConfig` with an Azure OpenAI provider; this component takes
over that `OLSConfig`, adds Qwen as the default provider and Nemotron as the fallback, and keeps Azure as a further,
selectable one.

| | |
|---|---|
| Application | [040-openshift-lightspeed](../../../applications/040-openshift-lightspeed.yaml), deploy-order 8, after `040-model-access` |
| Deployed by | `stages/040-governed-models-as-a-service/deploy.sh`, which passes the cluster-specific provider URLs as a `source.kustomize` patch |
| Validated by | `stages/040-governed-models-as-a-service/validate.sh` (Qwen and Nemotron are providers at this cluster's MaaS api listener, the default is one of them, both key Secrets carry `apitoken`, the Lightspeed API is Ready; a selected fallback is a warning) |
| Operated by | [`stages/040-governed-models-as-a-service/lightspeed/select-model.sh`](../../../../stages/040-governed-models-as-a-service/lightspeed/README.md) `qwen\|nemotron` selects the default model |
| Requires | The Lightspeed operator (OLSConfig API) preinstalled by the provisioner, `qwen3-8-27b`, `nemotron-3-ultra-550b-a55b` and the `openshift-lightspeed` subscription in `040-model-access` |

## Why

- **Private model.** Cluster questions and the resources Lightspeed reads stay on the private model instead of
  leaving for an external provider, and Lightspeed traffic is governed and metered like every other MaaS consumer.
- **Documented provider path.** The Lightspeed "Configure" guide documents Red Hat OpenShift AI as a provider: type
  `rhoai_vllm`, a URL ending in `/v1`, and a Secret whose key is `apitoken` [1]. MaaS serves the OpenAI-compatible
  `/v1` API on its gateway; its certificate is publicly trusted, so no `additionalCAConfigMapRef` is needed.
- **Governed fallback.** Lightspeed sends each request to one default provider; it has no failover between providers,
  and its readiness probe calls the default model, so a parked Qwen stops the console assistant [1]. Nemotron 3 Ultra is
  configured as a second `rhoai_vllm` provider on the same MaaS gateway, subscription and key, and
  [`select-model.sh`](../../../../stages/040-governed-models-as-a-service/lightspeed/README.md) moves the default to it
  and back. Nemotron accepts Lightspeed's Chat Completions request (`top_p`, `frequency_penalty`,
  `max_completion_tokens`, tool calls) and stays metered under the `openshift-lightspeed` subscription. GPT-6 Luna is
  not the fallback: the `rhoai_vllm` provider always sends `top_p`, which Luna rejects, and the `openai` provider calls the
  Responses API, which the MaaS external-model route for Luna (`openai-chat`) does not serve; the passthrough format
  that would is not token-metered. While Nemotron is selected, cluster questions and the resources Lightspeed reads
  leave the cluster for NVIDIA's API; the IP-address query filter still applies.
- **Stage 040.** Lightspeed consumes a governed model, so it is configured once MaaS, Qwen and the subscriptions exist,
  like the playground and Dev Spaces key provisioners.

## What

| Kind | Name | Namespace | Notes |
|---|---|---|---|
| ServiceAccount, Role, RoleBinding | `lightspeed-maas-key-provisioner` | `openshift-lightspeed` | Owns the MaaS subscription; may create Secrets and update only `qwen-maas-api-keys` and `nemotron-maas-api-keys`. Wave 18 |
| Role, RoleBinding | `lightspeed-maas-key-provisioner-gateway-reader` | `openshift-ingress` | Reads the MaaS Gateway's api hostname. Wave 18 |
| Job (Sync hook) | `provision-lightspeed-maas-key` | `openshift-lightspeed` | Keeps a MaaS key in Secret `qwen-maas-api-keys` (key `apitoken`, plus `key_id`, `expires_at`); re-uses an active key, re-mints an expired or revoked one, and copies it to `nemotron-maas-api-keys` (the operator mounts one volume per provider Secret and rejects a Secret shared by two providers). Wave 19 |
| OLSConfig | `cluster` | cluster | Providers `qwen-maas` (`rhoai_vllm`, `https://maas.<cluster-domain>/v1`, model `publishers/internal-models/models/qwen3-8-27b`, 128k context, 4096 response tokens), `nemotron-maas` (same type and URL, Secret `nemotron-maas-api-keys`, model `nemotron-3-ultra-550b-a55b`, 128k context, 4096 response tokens) and `Azure` (the provisioner's). Default `qwen-maas`. Other settings are the provisioner's. Wave 20 |

The MaaSSubscription and MaaSAuthPolicy `openshift-lightspeed` (Qwen and Nemotron, 2,000,000 tokens per hour each,
priority 60) live in `040-model-access` with the other subscriptions.

## How

- **Cluster-specific values.** Git holds placeholder URLs. `deploy.sh` patches `providers/0/url` and `providers/1/url`
  with `https://maas.<ingress domain>/v1` and `providers/2/url` with the Azure endpoint read from the live `OLSConfig`
  (never committed); without an Azure provider it removes that entry.
- **Model selection.** `select-model.sh nemotron` adds one more patch to the same Application, replacing
  `spec.ols.defaultProvider` and `defaultModel`; `select-model.sh qwen` removes it, and so does the next `deploy.sh`.
  Argo CD self-heal would revert a direct `OLSConfig` edit. The operator restarts the app server on each switch (about a
  minute); conversation history stays in PostgreSQL. One key covers both providers; the Job writes it to both Secrets, so
  a re-minted key needs the same single restart.
- **Key lifecycle.** Keys default to the MaaS maximum (90 days). Every sync re-checks the key; an expired one is
  re-minted. `credentialHotReload` stays off, so a re-minted key reaches Lightspeed after its app server restarts
  (`oc rollout restart deployment/lightspeed-app-server -n openshift-lightspeed`).
- **Operator version.** The provisioner's `stable` channel installed operator 2.0.1. Red Hat published the 2.0
  documentation set on 2026-11-12; this component's links stay on the "1.0" set the repository's documentation map pins.
  The fields used here are in both sets' OLSConfig reference and the installed CRD.

## Validation

```bash
oc get olsconfig cluster -o jsonpath='{.spec.ols.defaultProvider} {.spec.ols.defaultModel}{"\n"}'
oc get olsconfig cluster -o jsonpath='{range .status.conditions[*]}{.type}={.status}{"\n"}{end}'
```

Ask a question in the console's Lightspeed panel; the answer comes from the selected model (MaaS metering shows the
`openshift-lightspeed` subscription with `qwen3-8-27b`, or `nemotron-3-ultra-550b-a55b` while the fallback is
selected).

## Alignment with official guidance

| Topic | Official guidance | This component | Status |
|---|---|---|---|
| Provider | Red Hat OpenShift AI provider: `rhoai_vllm`, URL ending in `/v1`, Secret key `apitoken` [1] | Same, pointed at the MaaS gateway's OpenAI-compatible API with a MaaS key | Aligned |
| Trusted CA | `additionalCAConfigMapRef` for a provider behind a private CA [1] | Not set: the MaaS gateway certificate is publicly trusted | Aligned |
| Multiple providers | Several providers, one default [1] | `qwen-maas` default, `nemotron-maas` fallback, provisioner's `Azure` kept | Aligned |
| Provider failover | Not offered: one default provider; the OLSConfig has no fallback field [1] | Default moved by `select-model.sh` through the Argo CD Application | Gap: manual switch |
| Documentation version | Red Hat publishes "1.0" and, since 2026-11-12, "2.0" | Installed operator 2.0.1; links on "1.0" (the map's pin); fields used exist in both and the installed CRD | Gap: links not moved to 2.0 yet |

## References

1. Configure, "Creating the credentials secret" and "Creating the Lightspeed custom resource file", Red Hat OpenShift Lightspeed 1.0. https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/configure/index
