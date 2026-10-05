# Stage 010 foundation design review

Status: user-authorized implementation, 2026-10-05. The isolated candidate has passed source review and static/mocked checks. Publication awaits explicit user authorization; no platform deployment or live acceptance is demonstrated. OpenShell/Hermes hosting remains a later design decision.

## Reconciliation gate

The primary checkout remains on `59169d28` with its preserved changes. An isolated managed worktree was created at cached upstream `bfd6cc39`, preserving all 47 intervening commits. The private checkpoint in `tmp/platform-migration/checkpoint-20261005/` contains the original tracked diff and 12 grouped scripts with modes/checksums. Seven upstream overlaps were reconciled without textual conflicts; existing Kilo, workspace creation, catalog and MaaS routing regressions pass against the resulting tree.

Cleanup is committed separately as `a1637d29`; Stage 010 source and helper fixes follow on `codex/stage-010-foundation-35`. No primary checkout branch, index or history was changed. Deployment must use a published immutable candidate SHA matching local GitOps, stage scripts and executed shared helpers. The script refuses unpublished or mismatched content. External publication is currently blocked by automatic approval review pending explicit user authorization for the repository/branch and draft PR.

## Target and source boundaries

The observed environment is AWS OpenShift 4.22.14; reusable inventory and provider ownership are recorded in [Operations](../OPERATIONS.md). The candidate selects RHOAI 3.5 and ODF 4.22; the initial inventory recorded the previous 3.4/4.20 source selections as historical evidence. The [supported configuration matrix](https://access.redhat.com/articles/rhoai-supported-configs-3.x), updated 2026-10-02, includes x86_64 OCP 4.22 for RHOAI 3.5. The [3.5 installation guide](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/installing_and_uninstalling_openshift_ai_self-managed/installing-and-deploying-openshift-ai_install) still lists older OCP versions; retain this documentation discrepancy and prefer the newer support matrix for compatibility.

### Dependency selection and catalog evidence

The read-only catalog inventory at 2026-10-05 07:39:31 UTC on OCP 4.22.14 confirmed all six proposed channels in `redhat-operators`. Evidence is retained in `tmp/platform-migration/catalog-20261005/catalog-sanitized.json`. The architect selected these observed CSVs for the demo under reviewed Manual approval on unbounded observability streams. Availability and source review do not establish installed health or a Red Hat-tested tuple.

| Component | Previous source baseline | Selected channel | Observed CSV head | Evidence and selection gate |
|---|---|---|---|---|
| RHOAI | `stable-3.4` | `stable-3.5` | `rhods-operator.3.5.1` | Support matrix above; verify installed 3.5 schema and native operands |
| GitOps | `gitops-1.20` | `gitops-1.21` | `openshift-gitops-operator.v1.21.4` | [1.21 release notes](https://docs.redhat.com/en/documentation/red_hat_openshift_gitops/1.21/html/release_notes/gitops-release-notes) cover OCP 4.22; bootstrap acceptance required |
| ODF MCG | `stable-4.20` | `stable-4.22` | `odf-operator.v4.22.5-rhodf` | [4.22 release notes](https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.22/html/4.22_release_notes/overview); validate StorageCluster schema and storage; old 4.20 channel absent |
| COO | Manual hold at 1.4.0 | `stable` | `cluster-observability-operator.v1.5.3` | [COO release notes](https://docs.redhat.com/en/documentation/red_hat_openshift_cluster_observability_operator/1-latest/html/red_hat_openshift_cluster_observability_operator_release_notes/cluster-observability-operator-release-notes); [Official advisory evidence](https://access.redhat.com/security/cve/cve-2026-48779) names 1.5.3; public release notes end at 1.5.2. Verify patch details and native acceptance |
| OpenTelemetry | Product 3.9 reference | `stable` | `opentelemetry-operator.v0.158.0-2` | [Researched 3.10 release notes](https://docs.redhat.com/en/documentation/red_hat_build_of_opentelemetry/3.10/html/release_notes_for_the_red_hat_build_of_opentelemetry/otel_rn); [Red Hat bundle catalog](https://catalog.redhat.com/en/software/containers/rhosdt/opentelemetry-operator-bundle/615618406feffc5384e84400) confirms the bundle; Bundle CPE confirms product 3.11; collector version and exact support-table coverage remain unverified |
| Tempo | Product 3.9 reference | `stable` | `tempo-operator.v0.22.0-2` | [Researched 3.10 release notes](https://docs.redhat.com/en/documentation/red_hat_openshift_distributed_tracing_platform/3.10/html/release_notes_for_distributed_tracing/distr-tracing-rn); [Official 3.11 documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_distributed_tracing_platform/3.11) and bundle CPE confirm product 3.11; operand version/support coverage remain gates |
| cert-manager | Provider-installed Red Hat 1.20.1 | Reuse existing owner | Already installed; no new selection | [Operator lifecycle matrix](https://access.redhat.com/support/policy/updates/openshift_operators); no duplicate Subscription or CertManager singleton |

Recommend bounded RHOAI `stable-3.5`. For an unbounded channel, propose Manual approval as a project control for minor drift; `startingCSV` alone is not an upper bound. Bundle CPE metadata maps OpenTelemetry and Tempo to product 3.11; exact public support coverage and native acceptance remain gates. No exact Red Hat-tested RHOAI/COO/OpenTelemetry/Tempo tuple was established.

Retain full tracing in the proposed Stage 010 scope. Metrics-only is an alternative requiring user alignment if native tracing compatibility cannot be established. TRACING-6381 is documented for OpenTelemetry 3.10.0/3.10.1; applicability to the observed 0.158 bundle is unknown. Inspect the generated collector for `k8s_cluster` and verify native permissions/functionality; do not presume a blocker or patch generated ClusterRoles. [Native RHOAI observability](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/managing_openshift_ai/managing-observability_managing-rhoai) supplies metrics dashboards without additional dashboard RBAC. Centralized observability remains [Technology Preview](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/release_notes/technology-preview-features_relnotes); example retention/storage parameters are not measured capacity.

[ODF MCG minimums](https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.22/html/planning_your_deployment/infrastructure-requirements_rhodf) total 3–4 CPU/10–12 GiB for core, database and one or two endpoints, excluding platform/storage headroom. Validate standalone MCG/gp3 against the installed CRD; retain native NooBaa image ownership.

## Resource and ownership decisions

| Resource | Current source or owner | Proposed treatment |
|---|---|---|
| GitOps bootstrap | `gitops/bootstrap/`; GitOps 1.20 | Native GitOps 1.21 Operator installation |
| RHOAI Subscription, DSCI and DSC | `gitops/stages/010-openshift-ai-platform-foundation/base/rhoai/` | Bounded 3.5 channel, verified schema; Stage 010 owns MLflow and TrustyAI |
| Dashboard, workbenches, model registry | Stage 010 DSC Managed components | Retain; validate each service independently |
| ODF MCG, object bucket and access resources | Stage 010 `base/odf/` and `base/access/` | ODF 4.22 standalone MCG; operator owns generated object-storage operands |
| Observability operators and instances | Stage 010 manifests | Native ownership; reviewed exact CSVs, live functional exits pending |
| Existing Keycloak, cert-manager and Lightspeed | Provider-supplied environment state | Preserve; explicitly decide integration scope before project subscriptions overlap |
| KServe, MaaS and LlamaStack | Later Stage 030/040 DSC writers | Keep later-stage ownership; revalidate old LlamaStack schema dependency |

Stage 020 writes Kueue as Unmanaged; Stage 030/040 own KServe and LlamaStack changes. The Stage 010 Argo application ignores those fields plus AI pipelines, but no longer ignores TrustyAI or MLflow because they are now foundation-owned. Group membership is assigned through access setup and ignored by GitOps self-heal. All 17 served DSC component keys are explicit: Dashboard, Workbenches, Model Registry, MLflow and TrustyAI are Managed; new unused components including ogx, trainer, AI gateway, MCP lifecycle and Spark are Removed.

## Existing workarounds and cleanup review

The fresh target uses the stable COO overlay and deployment-side exact InstallPlan ownership/CSV approval instead of the old 1.4 hold and approval job. Legacy TLS synchronization, Perses NetworkPolicy and dashboard RBAC are excluded from the native target; their files remain until live native acceptance validates removal conditions in [Backlog](../../BACKLOG.md). Console plugin jobs remain ordinary one-shot Jobs appending shared Console configuration. No generated operand is patched.

Preserve singleton OCSInitialization, generated NooBaa credentials and registry database ownership. Existing Argo health shortcuts for Pending PVCs and subscriptions are scheduling aids, not service acceptance.

## New features and stage boundaries

[Dashboard customization](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/managing_resources/customizing-the-dashboard) documents `agentsCatalog: true` as Developer Preview. Agent Catalog discovers starter kits; it does not establish runtime hosting or automatic AgentCard registration. `agentOps` and `agentConfigManagement` are separate preview flags. The deprecated `mlflow` UI flag is not the enabling mechanism; operator presence controls its UI. The candidate removes deprecated `maasAuthPolicies`, sets AutoRAG and AutoML false and enables schema-verified `agentsCatalog`.

[Developer Preview release notes](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/release_notes/developer-preview-features_relnotes) describe OpenShell via Helm, not a DSC component. OpenShell hosting and standalone per-project Hermes remain later Stage 050/080 design after MaaS; packaging, discovery and runtime compatibility are unproven. Do not introduce obsolete Kagenti operators. The [OpenShell guide](https://github.com/opendatahub-io/agent-ops/blob/main/guides/getting-started-openshell-openshift.md) uses privileged SCC, while [upstream SCC requirements](https://github.com/opendatahub-io/agent-ops/blob/main/scc-requirements.md) describe root and elevated capabilities. Resolve security, tenant isolation and topology separately; no SCC grant is included here.

### Proposed Stage 010 feature additions

Enable built-in Agent Catalog discovery with `agentsCatalog: true`. Install one shared MLflow service and TrustyAI-managed EvalHub after their durable storage prerequisites. The [support matrix](https://access.redhat.com/articles/rhoai-supported-configs-3.x) labels MLflow 3.14 GA and EvalHub 0.3 Technology Preview; the screenshot does not override that source.

The [MLflow installation guide](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/working_with_mlflow/installing-mlflow_mlflow) uses DSC `mlflowoperator: Managed` and an `mlflow.opendatahub.io/v1` MLflow CR. Propose dedicated PostgreSQL and S3, with `serveArtifacts` proxying for durable evidence. Use `redhat-ods-applications` for MLflow because of the dashboard known issue. The exact shipped CRD confirms MLflow is cluster-scoped; the candidate omits metadata.namespace, and native operator ownership places its service in `redhat-ods-applications`.

The [EvalHub guide](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/evaluating_ai_systems/evaluating-llms-with-evalhub_evaluate) uses a TrustyAI-managed `v1` EvalHub CR, recommends PostgreSQL rather than in-memory SQLite, and describes tenant labels, RBAC and MLflow experiment tracking. Make MLflow Ready an explicit gate before creating EvalHub, as [known issue RHOAIENG-67534](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/release_notes/known-issues_relnotes) requires.

EvalHub uses the dedicated `evalhub` namespace recommended by the evaluation guide. RHOAIENG-66068 names EvalHub in its heading but MLflow in its body/workaround, so dashboard discovery remains a live gate. The dashboard guide's `disableLMEval` versus evaluation guide's `disableEvalHub` discrepancy remains explicit; no invented flag was added. Native catalog, MLflow and EvalHub UI discovery must be verified independently.

For the demo registry, retain the operator-provided PostgreSQL option with an explicit nonproduction posture. The [3.5 registry guide](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/managing_model_registries/creating-a-model-registry_managing-model-registries) permits that default for nonproduction and recommends external PostgreSQL 16 for production. Do not reuse the provider Keycloak database for registry, MLflow or EvalHub.

## Proposed implementation dependency sequence

With reconciliation and source review complete: guarded bootstrap → native operators/CRD verification → storage and dedicated PostgreSQL/S3 prerequisites → RHOAI core and native observability → model registry and MLflow service → verified MLflow Ready → EvalHub creation and MLflow integration → access setup and Stage 010 persona acceptance. Enable Agent Catalog discovery after schema verification. First real model evaluation follows available Stage 030/040 endpoints; it is a separate later acceptance gate.

## Acceptance criteria

1. Reconciliation and exact-version/schema decisions are reviewed before editing manifests.
2. Bootstrap uses the shared guarded environment loading and cluster identity checks; no guard bypass or unbounded bespoke login validation.
3. Verify required CSVs, DSCI/DSC conditions, operator-owned services, storage and observability independently of Argo sync.
4. Run platform readiness, then explicit access setup, then final persona acceptance. Access setup must fail visibly on group membership failures and preserve existing identity providers.
5. Verify appropriately privileged non-kubeadmin administration and ordinary developer access through actual group/project permissions, including the 3.5 authentication configuration rather than presumed defaults.
6. Validate the demo registry instance, database and authorized API access, plus usable S3 credentials and an explicit functional object-storage exit. Operator readiness or a bound PVC alone is insufficient.
7. In Stage 010, prove MLflow PostgreSQL persistence, authorized artifact write/read through S3, MLflow readiness before EvalHub creation, and EvalHub platform health, dashboard discovery, tenant authentication/RBAC and MLflow integration. Verify Agent Catalog discovery separately from runtime hosting.
8. After Stage 030/040 supplies a model endpoint, run the first actual tenant-isolated evaluation and prove durable experiment/artifact evidence. Until then, end-to-end evaluation is unqualified.
9. Confirm excluded components remain disabled and later-stage DSC ownership is preserved. Report each unknown or blocked exit separately; baseline readiness does not qualify the full demo.

## Remaining gates and implementation evidence

Publication to `github.com/adnan-drina/rhoai3-coding-demo` on `codex/stage-010-foundation-35`, with a draft PR and no merge, requires explicit user authorization after automatic approval review rejected external code egress. The clean isolated candidate is ready locally. Native deployment, exact installed CSV/CRD validation, S3 functional write/read, registry API access, native metrics/traces and dashboard discovery remain unproven.

The user selected existing OpenID usernames `ai-admin` and `ai-developer`; no htpasswd or provider account changes are included. Group membership may precede first login, but final acceptance requires their private authenticated sessions. The non-kubeadmin installation account has bootstrap permissions and matches neither persona. Provider OAuth/Keycloak ownership remains intact.

`DISABLE_DSC_CONFIG=true` suppresses the operator-created default DSCI so GitOps owns initialization; the self-managed bootstrap path does not auto-create a DSC. Native Auth, DSC, DSCI and dashboard fields passed the exact shipped bundle schema audit. MLflow is cluster-scoped and EvalHub namespaced. Runtime helpers create missing dedicated database credentials, validate/reuse existing secrets without rotation, and derive EvalHub's tracking URI only after current-generation MLflow availability. Each service has separate PVC-backed PostgreSQL 16; plaintext namespace-local DB connections, NetworkPolicies and no HA establish a durable demo boundary, not production readiness. No provider database is reused.

The demo project carries the empty EvalHub tenant presence label and an explicit Role/GroupBinding for virtual evaluations, collections, providers and MLflow experiments, following [sections 2.28–2.30](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/evaluating_ai_systems/evaluating-llms-with-evalhub_evaluate). The server namespace stays unlabelled. Operator-owned tenant job identities, bindings and CA discovery are not duplicated. Static checks preserve exact verbs and subjects without wildcards; real persona SAR/API access remains a live exit.

Validation completed locally: per-file Bash syntax; embedded Python parsing; five stage Kustomize renders; Kilo, workspace creation, catalog and MaaS routing regressions; exact owned InstallPlan approval with rejection of foreign ownership/extra CSVs; 13 service helper credential/reuse/fault/readiness/RBAC/timeout cases; functional-helper mock endpoint flow and stale-registry rejection; diff whitespace and scoped secret/private-endpoint scans. No live platform or evaluation claim follows from these results.

Exact newer OpenTelemetry/OCP 4.22 support-table coverage and an official tested observability tuple remain unverified. Full native tracing is selected; metrics-only would require separate user alignment if native compatibility fails. Missing AWS root credentials may affect native object-store provisioning: inspect actual NooBaa/BackingStore status before considering documented pv-pool resources; make no speculative cloud IAM change. First real evaluation and durable evaluation evidence await Stage 030/040 endpoints. OpenShell/Hermes hosting remains outside Stage 010.
