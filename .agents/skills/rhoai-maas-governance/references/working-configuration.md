# MaaS working configuration and lessons (Stage 040)

Repo-owned record for `rhoai-maas-governance`. Re-checked against Git on
2026-10-15 (RHOAI 3.5.1, Connectivity Link 1.4.3). The component READMEs under
`gitops/stages/040-governed-models-as-a-service/` are the detailed record of
what is deployed; this file keeps the cross-component map and the lessons that
Git comments do not hold. Product behavior: the links in `SKILL.md`.

## Where things live

| Area | Value | Owner in Git |
|---|---|---|
| Enablement | `default-dsc` `aigateway` + `aigateway.modelsAsAService` Managed, `ogx` Managed, `batchGateway` Removed | `040-maas-platform/jobs/enable-maas-job.yaml` (fields delegated by Stage 010) |
| Tenant | Default tenant only; controller-owned `MaaSTenantConfig` `default-tenant` in `models-as-a-service`, telemetry patched by the Job | `040-maas-platform/jobs/` |
| MaaS API | `maas-api` in `redhat-ai-gateway-infra` (operator-owned) | not in Git |
| Database | PostgreSQL 16 StatefulSet `maas-postgres` in `models-as-a-service-db` (not Kueue-managed); Secret `maas-db-config` key `DB_CONNECTION_URL` in `redhat-ai-gateway-infra` | `040-maas-database/`, `stages/040-governed-models-as-a-service/deploy.sh` |
| Gateway | `maas-default-gateway` in `openshift-ingress`, listeners `api` (`maas.<domain>`) and `qwen3-8` (`qwen3-8-maas.<domain>`), certificate `cert-manager-ingress-cert`, in-cluster ClusterIP `maas-gateway-internal` 172.30.250.250 | `040-gateway-governance/gateway/` |
| Kuadrant and Authorino | `kuadrant` and `authorino` in `kuadrant-system`, Authorino TLS via service CA | `040-gateway-governance/governance/`, `040-gateway-governance/jobs/` |
| Private model | `LLMInferenceService` + `MaaSModelRef` `qwen3-8-27b` (Qwen 3.8 27B NVFP4, one RTX PRO 6000) in `internal-models` | `040-local-models/` |
| External models | `gpt-6-luna` (OpenAI), `claude-sonnet-5-5` (Anthropic, OpenAI-compatible path), `nemotron-3-ultra-550b-a55b` (NVIDIA as `provider: openai`) in `external-models` | `040-external-models/` |
| Access | Subscriptions + auth policies `personal-kube-admin`, `personal-ai-developer`, `personal-ai-admin`, `devspaces-coding-models`, `playground-sandbox`, `model-qualification` in `models-as-a-service` | `040-model-access/` |
| Other subscriptions in that namespace | `hermes-private-qwen38`, `opencode-private-qwen38` (Stage 060), `mta-migration-ai` (Stage 070) | other stages |

Paths in the table are relative to `gitops/stages/040-governed-models-as-a-service/`.

## Lessons that still hold

- **Resource names are DNS-safe; provider ids go in `targetModel`.** The
  controller derives Kubernetes objects (HTTPRoutes) from the `ExternalModel`
  name, so a dotted or slashed provider id cannot be the name. Example in Git:
  `nemotron-3-ultra-550b-a55b` targets `nvidia/nemotron-3-ultra-550b-a55b`.
- **Readiness is not access.** CR `Ready`, dashboard listing and
  `/maas-api/v1/subscriptions` do not prove inference. Acceptance is
  `validate.sh --functional`: a temporary key, bounded completions, revoke.
- **OpenShift tokens are not the inference credential in this demo.** Clients
  call `/v1/chat/completions` with a MaaS API key minted against a
  subscription; every service consumer has its own key-minting ServiceAccount.
- **Change `maas-db-config` only with the script.** `stages/040-governed-models-as-a-service/deploy.sh`
  refuses a Secret that does not match the stored credentials and never
  rotates a password. If the Secret is ever changed by hand, restart
  `maas-api` in `redhat-ai-gateway-infra` and re-run the functional check;
  readiness can pass while key storage still fails.
- **Keep `service/maas-postgres` and the StatefulSet in the same sync wave**
  (both wave 8), so Argo CD does not wait for Service endpoints that the
  StatefulSet has not created yet.
- **Keep the database outside Kueue-managed namespaces.** `models-as-a-service`
  carries `kueue.openshift.io/managed=true`; `models-as-a-service-db` does not.
- **Generated policies and EnvoyFilters are controller output.** Validate source
  CR status and user paths, not generated object names; never patch them as a
  durable fix (`rhcl-configure`).
- **Long silent streams need the 3600 s ELB idle timeout** on the Gateway
  (`spec.infrastructure.annotations`); exact-60 s failures are the tell.
- **Validate operator upgrades end to end.** A Connectivity Link update can
  change generated Wasm or AuthConfig schemas; rerun functional validation before
  raising the minimum in `check_operator_policy` in `scripts/lib.sh`
  (`rhcl-update`).
- **Re-run schema checks after RHOAI or Connectivity Link upgrades**
  (`oc explain maassubscriptions.spec`, `oc api-resources | grep -i maas`).
  3.5 moved `maas-api` and `maas-db-config` from `redhat-ods-applications` to
  `redhat-ai-gateway-infra` and deprecated `Tenant`.

## Retired (do not reuse)

3.4-era notes from rhoai3-demo ("Stage 220", Nemotron Nano local model,
`gpt-4o-mini`, `maas-gateway-tls` copy Secret, `Tenant` CR, Llama Stack
playground repairs, `maas-api-key-cleanup` CronJob replacement, manually
pinned Connectivity Link 1.3.4) were removed on 2026-10-15; history is in Git.
