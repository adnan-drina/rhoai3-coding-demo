---
name: rhoai-model-catalog-sources
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when changing or reviewing which sources feed the OpenShift AI Model
  Catalog or the Developer Preview Agent Catalog in this repo: the Stage 030
  enable-model-discovery Job (disableModelCatalog, agentsCatalog), the
  agent-catalog-sources ConfigMap in rhoai-model-registries, a proposed
  model-catalog-sources ConfigMap or Hugging Face source, or a catalog that
  shows no models or a source load error. Do NOT use for browsing, registering
  or deploying catalog models (use rhoai-model-catalog-workflows), registry
  instances (use rhoai-model-registry), or MCP catalog entries (Stage 060).
---

# RHOAI Model Catalog Sources

Thin skill: repo decisions and pitfalls here, product behavior in the linked
OpenShift AI 3.5 sections. Detailed record:
`gitops/stages/030-private-model-serving/030-private-model-serving/README.md`
("model-discovery").

## When to use

- Someone proposes adding, disabling or filtering a Model Catalog source.
- The Agent Catalog cards (`opencode`, `hermes`) change or disappear.
- AI hub → Catalog is empty or reports a source load error.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Model Catalog uses the default Red Hat sources only; no `model-catalog-sources` ConfigMap and no Hugging Face source in Git | not in Git (absence is the decision) | [View sources][view], [Configure sources in OpenShift][cm] |
| Catalog and registry are enabled by a Sync-hook Job: `modelregistry` Managed with `registriesNamespace: rhoai-model-registries`; `disableModelCatalog: false`, `agentsCatalog: true` on delegated Stage 010 fields | `gitops/stages/030-private-model-serving/030-private-model-serving/model-discovery/enable-job.yaml` | [Manage sources in the dashboard][dashboard] |
| Stage 010 ships the catalog hidden (`disableModelCatalog: true`) so the base platform validates alone | `gitops/stages/010-openshift-ai-platform-foundation/010-rhoai-platform/odhdashboardconfig.yaml` | [Manage sources in the dashboard][dashboard] |
| Agent Catalog (Developer Preview) source `governed-coding-agents` with two metadata-only cards pointing at Stage 060; schema pinned to an upstream model-registry commit because 3.5 documents custom sources only for the Model Catalog | `gitops/stages/030-private-model-serving/030-private-model-serving/model-discovery/agent-catalog-sources.yaml` | [Configure sources in OpenShift][cm] (Model Catalog only) |
| `preflight-agent-catalog.sh` adopts only an empty `agent-catalog-sources` ConfigMap | `stages/030-private-model-serving/preflight-agent-catalog.sh` | not documented |
| Safety-insights tab needs EvalHub `get evaluations` in `rhoai-model-registries` for both groups | `gitops/stages/050-model-evaluation/050-evalhub/tenant/catalog-insights-role.yaml` | see `rhoai-evaluation` |

## Procedure

1. A new Model Catalog source needs a README decision in the Stage 030
   component first (provenance, visibility patterns, who reviews). Then declare
   it as a `model-catalog-sources` ConfigMap in `rhoai-model-registries` under
   `gitops/stages/030-private-model-serving/030-private-model-serving/model-discovery/`,
   disabled until reviewed; do not add sources from the dashboard only.
2. Agent cards change only in `agent-catalog-sources.yaml`; keep image,
   template and credentials out of the cards.
3. Deploy and validate after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   ./stages/030-private-model-serving/deploy.sh
   ./stages/030-private-model-serving/validate-model-discovery.sh
   oc get configmap -n rhoai-model-registries | grep -i catalog
   ```

   `validate-model-discovery.sh` requires catalog items and exactly one
   `opencode` and one `hermes` card from `governed-coding-agents`.

## Pitfalls

- Hugging Face sources: public, non-gated models only, and the cluster needs
  network access to Hugging Face ([Hugging Face limits][hf]).
- Default catalog sources cannot be deleted, only disabled ([Delete][delete]).
- Custom sources are not supported on `s390x` ([Configure sources in OpenShift][cm]).
- Agent Catalog format is undocumented in 3.5; re-check the pinned upstream
  schema on every RHOAI upgrade.
- Source load error after a reboot:
  `docs/TROUBLESHOOTING.md#model-catalog-crash-loops-after-a-cluster-reboot-source-load-error-in-the-dashboard`.
- Safety insights spinner:
  `docs/TROUBLESHOOTING.md#model-catalog-safety-and-security-insights-tab-spins-forever`.

## Official documentation (OpenShift AI 3.5)

| Topic | Section |
|---|---|
| Dashboard governance | [Manage sources in the dashboard][dashboard], [View][view], [Enable or disable][enable], [Visibility patterns][visibility] |
| Hugging Face limits | [Hugging Face limits][hf] |
| Add, manage, delete | [Add][add], [Manage][manage], [Delete][delete] |
| ConfigMap sources | [Configure sources in OpenShift][cm] |

## Related skills

`rhoai-model-catalog-workflows`, `rhoai-model-registry`,
`rhoai-dashboard-customization`, `rhoai-evaluation`.

[dashboard]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/manage_and_govern_model_catalog_sources/index#manage-model-catalog-sources-in-dashboard_manage-govern-model-catalog-sources
[view]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/manage_and_govern_model_catalog_sources/index#view_model_catalog_sources
[enable]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/manage_and_govern_model_catalog_sources/index#enable_or_disable_catalog_sources
[visibility]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/manage_and_govern_model_catalog_sources/index#configure_model_visibility_settings_to_allow_and_disallow_models
[hf]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/manage_and_govern_model_catalog_sources/index#limitations_for_hugging_face_model_sources
[add]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/manage_and_govern_model_catalog_sources/index#add-model-catalog-source_manage-govern-model-catalog-sources
[manage]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/manage_and_govern_model_catalog_sources/index#manage-model-catalog-source_manage-govern-model-catalog-sources
[delete]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/manage_and_govern_model_catalog_sources/index#delete-model-catalog-source_manage-govern-model-catalog-sources
[cm]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/manage_and_govern_model_catalog_sources/index#configuring-model-catalog-sources-in-openshift_manage-govern-model-catalog-sources
