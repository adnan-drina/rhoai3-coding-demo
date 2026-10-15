---
name: rhoai-llama-stack
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when working with OGX, the OpenShift AI 3.5 successor of Llama Stack, in
  this repo: the DSC `ogx` component that the Stage 040 enable-maas Job turns
  on, the `default-ogx` component CR, the playground `OGXServer`
  `lsd-genai-playground` in `demo-sandbox` and its retained state PVC, the
  deprecated `llamastackoperator` field kept Removed in Stage 010, or planning
  an OGX server, vector store, OpenAI-compatible API, auth or ABAC change. Do
  NOT use for playground user workflows, custom endpoints and MCP lists (use
  rhoai-gen-ai-playground), AutoRAG runs (use rhoai-autorag), RAG application
  design (use rhoai-enterprise-rag), or NeMo Guardrails (use
  rhoai-guardrails-safety).
---

# RHOAI Llama Stack (OGX)

Thin skill: repo decisions and pitfalls here, product behavior in the linked
OpenShift AI 3.5 sections. In 3.5 the Llama Stack guide is replaced by "Build
AI/Agentic Applications with OGX" (book `working_with_ogx`); the skill keeps
its old name. Detailed record:
`gitops/stages/040-governed-models-as-a-service/040-maas-platform/README.md` and
`gitops/stages/040-governed-models-as-a-service/040-genai-studio/README.md`.

## When to use

- `default-ogx` is not Ready, or the dashboard cannot create a playground.
- Someone proposes enabling `llamastackoperator` or authoring an
  `LlamaStackDistribution` from older material.
- Planning a project OGX server, vector database, OpenAI-compatible client or
  OAuth/ABAC setup beyond the playground.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| `llamastackoperator` stays `Removed` and is not delegated, so Argo CD enforces it; the live 3.5 CRD marks it deprecated in favour of `ogx` | `gitops/stages/010-openshift-ai-platform-foundation/010-rhoai-platform/datasciencecluster.yaml` | [Llama Stack to OGX migration][migration] |
| `ogx` set `Managed` by the `job-enable-dsc-maas` Sync hook (delegated Stage 010 field); the Job waits for `default-ogx` Ready | `gitops/stages/040-governed-models-as-a-service/040-maas-platform/jobs/enable-maas-job.yaml` | [Activate the OGX Operator][activate] |
| No OGX server in Git: the only server is the playground `lsd-genai-playground`, created from the dashboard with its pgvector database | not in Git (dashboard-owned) | [Resources created with a playground][playres] |
| The retained PVC `genai-playground-state` is attached to a freshly created playground through `spec.workload.overrides` (the former `studio-api.sh --install-model` that did this is in git history at `82092e01`) | `gitops/stages/040-governed-models-as-a-service/040-genai-studio/` | [Deploy an OGX server][deploy] |
| Models reach OGX only through MaaS endpoints, never through provider keys in an OGX configuration | `gitops/stages/040-governed-models-as-a-service/` | [OGX API provider support][providers] |

## Procedure

1. Enablement changes go through the Stage 040 Job, never the live DSC:

   ```bash
   ./stages/040-governed-models-as-a-service/deploy.sh
   ./stages/040-governed-models-as-a-service/validate.sh
   ```

2. Inspect read-only, after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   oc get datasciencecluster default-dsc -o jsonpath='{.spec.components.ogx.managementState} {.spec.components.llamastackoperator.managementState}{"\n"}'
   oc get ogxs.components.platform.opendatahub.io default-ogx -o jsonpath='{range .status.conditions[*]}{.type}={.status} {end}{"\n"}'
   oc get ogxservers.ogx.io,pvc -n demo-sandbox
   ```

3. A new OGX server outside the playground needs its own GitOps component and
   README: server CR, PostgreSQL metadata store, vector provider, Secrets from
   `.env` helpers, and a validate step. Read the [security reference][security]
   first and keep the demo security posture in `.agents/rules/env.md`.

## Pitfalls

- Older skills and examples use `LlamaStackDistribution` and the Llama Stack
  operator; follow the [migration chapter][migration] instead of porting them.
- Do not pre-author or patch the playground's generated pgvector resources;
  they are service-owned (`docs/OPERATIONS.md`, Stage 040 GenAI Studio).
- Moving existing playground state needs the backup and restore procedure in
  `docs/OPERATIONS.md`; attach the PVC only to a new playground, never to an
  existing one.
- Playground answer or tool failures:
  `docs/TROUBLESHOOTING.md#gen-ai-playground-gets-no-answer-from-external-models`,
  `docs/TROUBLESHOOTING.md#gen-ai-playground-mcp-tools-fail-or-return-no-tools`.
- The OGX book pages read state no support level for the OGX APIs; check API
  stability with `rhoai-api-tiers` before promising it.

## Official documentation (OpenShift AI 3.5)

| Topic | Section |
|---|---|
| Overview, migration from Llama Stack | [Overview][overview], [Migration][migration] |
| Operator and server | [Activate the OGX Operator][activate], [Deploy an OGX server][deploy] |
| APIs and providers | [OGX APIs][apis], [OpenAI-compatible APIs][openai], [Provider support][providers] |
| Vector databases, PostgreSQL | [Select a vector database][vectordb], [PostgreSQL in OGX][postgres], [Custom PostgreSQL for playground RAG][playpg] |
| Security, auth, ABAC | [Security reference][security], [OAuth][oauth], [ABAC][abac], [Self-signed certificates][certs] |
| Multi-tenancy, HA | [Multi-tenancy][tenancy], [HA and autoscaling][ha] |

## Related skills

`rhoai-gen-ai-playground`, `rhoai-enterprise-rag`, `rhoai-autorag`,
`rhoai-guardrails-safety`, `rhoai-maas-governance`, `rhoai-api-tiers`,
`rhoai-dsci-dsc-configuration`.

[overview]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ogx/index#overview-of-ogx_rag
[migration]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ogx/index#llama-stack-to-ogx-migration_rag
[activate]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ogx/index#activating-the-ogx-operator_rag
[deploy]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ogx/index#deploying-ogx-server_rag
[apis]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ogx/index#ogx-apis_rag
[openai]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ogx/index#openai-compatible-apis-in-ogx_rag
[providers]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ogx/index#ogx-provider-support_rag
[vectordb]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ogx/index#select-and-deploy-a-vector-database_rag
[postgres]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ogx/index#using-postgresql-in-ogx_rag
[playres]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ogx/index#resources-created-when-you-create-a-playground_rag
[playpg]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ogx/index#configuring-a-custom-postgresql-instance-for-playground-rag_rag
[security]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ogx/index#ogx-security-guide_rag
[oauth]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ogx/index#auth-on-ogx_rag
[abac]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ogx/index#ogx-core-access-control_rag
[certs]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ogx/index#about-using-self-signed-certificates-with-ogx_rag
[tenancy]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ogx/index#ogx-multi-tenancy_rag
[ha]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ogx/index#ogx-high-avail-and-auto_rag
