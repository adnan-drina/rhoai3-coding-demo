# Stage 010 foundation design review

Status: user-authorized implementation, 2026-10-05. Source preparation and review are in progress; deployment acceptance is not yet demonstrated. OpenShell/Hermes hosting remains a later design decision.

## Reconciliation gate

The working checkout is `59169d28`; cached `origin/main` is `bfd6cc39` (47 commits ahead). The private local checkpoint in `tmp/platform-migration/checkpoint-20261005/` preserves the tracked diff and 12 grouped scripts, their modes and checksums. Seven paths overlap cached upstream; temporary three-way probes found no textual conflicts. This does not establish semantic compatibility.

Before implementation, review the checkpoint and upstream scope, agree a controlled reconciliation procedure, then verify the resulting diff and rerun the existing cleanup checks. Do not deploy from an unreconciled checkout. No branch, index or reference was changed for this review.

## Target and source boundaries

The observed environment is AWS OpenShift 4.22.14; reusable inventory and provider ownership are recorded in [Operations](../OPERATIONS.md). RHOAI 3.5 is the proposed target, while manifests still select RHOAI 3.4 and ODF 4.20. The [supported configuration matrix](https://access.redhat.com/articles/rhoai-supported-configs-3.x), updated 2026-10-02, includes x86_64 OCP 4.22 for RHOAI 3.5. The [3.5 installation guide](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/installing_and_uninstalling_openshift_ai_self-managed/installing-and-deploying-openshift-ai_install) still lists older OCP versions; retain this documentation discrepancy and prefer the newer support matrix for compatibility.

### Dependency selection and catalog evidence

The read-only catalog inventory at 2026-10-05 07:39:31 UTC on OCP 4.22.14 confirmed all six proposed channels in `redhat-operators`. Evidence is retained in `tmp/platform-migration/catalog-20261005/catalog-sanitized.json`. Observed heads establish availability, not a chosen compatible tuple or installed health.

| Component | Current baseline | Proposed channel | Observed CSV head | Evidence and selection gate |
|---|---|---|---|---|
| RHOAI | `stable-3.4` | `stable-3.5` | `rhods-operator.3.5.1` | Support matrix above; verify installed 3.5 schema and native operands |
| GitOps | `gitops-1.20` | `gitops-1.21` | `openshift-gitops-operator.v1.21.4` | [1.21 release notes](https://docs.redhat.com/en/documentation/red_hat_openshift_gitops/1.21/html/release_notes/gitops-release-notes) cover OCP 4.22; bootstrap acceptance required |
| ODF MCG | `stable-4.20` | `stable-4.22` | `odf-operator.v4.22.5-rhodf` | [4.22 release notes](https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.22/html/4.22_release_notes/overview); validate StorageCluster schema and storage; old 4.20 channel absent |
| COO | Manual hold at 1.4.0 | `stable` | `cluster-observability-operator.v1.5.3` | [COO release notes](https://docs.redhat.com/en/documentation/red_hat_openshift_cluster_observability_operator/1-latest/html/red_hat_openshift_cluster_observability_operator_release_notes/cluster-observability-operator-release-notes); [Official advisory evidence](https://access.redhat.com/security/cve/cve-2026-48779) names 1.5.3; public release notes end at 1.5.2. Verify patch details and native acceptance |
| OpenTelemetry | Product 3.9 reference | `stable` | `opentelemetry-operator.v0.158.0-2` | [Researched 3.10 release notes](https://docs.redhat.com/en/documentation/red_hat_build_of_opentelemetry/3.10/html/release_notes_for_the_red_hat_build_of_opentelemetry/otel_rn); [Red Hat bundle catalog](https://catalog.redhat.com/en/software/containers/rhosdt/opentelemetry-operator-bundle/615618406feffc5384e84400) confirms the bundle; product/collector mapping and numeric OCP support remain unverified |
| Tempo | Product 3.9 reference | `stable` | `tempo-operator.v0.22.0-2` | [Researched 3.10 release notes](https://docs.redhat.com/en/documentation/red_hat_openshift_distributed_tracing_platform/3.10/html/release_notes_for_distributed_tracing/distr-tracing-rn); [Official 3.11 documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_distributed_tracing_platform/3.11) exists, but release mapping of this CSV and operand version remain unverified |
| cert-manager | Provider-installed Red Hat 1.20.1 | Reuse existing owner | Already installed; no new selection | [Operator lifecycle matrix](https://access.redhat.com/support/policy/updates/openshift_operators); no duplicate Subscription or CertManager singleton |

Recommend bounded RHOAI `stable-3.5`. For an unbounded channel, propose Manual approval as a project control for minor drift; `startingCSV` alone is not an upper bound. Resolve observability version mappings before selecting manifests. No exact Red Hat-tested RHOAI/COO/OpenTelemetry/Tempo tuple was established.

Retain full tracing in the proposed Stage 010 scope. Metrics-only is an alternative requiring user alignment if native tracing compatibility cannot be established. TRACING-6381 is documented for OpenTelemetry 3.10.0/3.10.1; applicability to the observed 0.158 bundle is unknown. Inspect the generated collector for `k8s_cluster` and verify native permissions/functionality; do not presume a blocker or patch generated ClusterRoles. [Native RHOAI observability](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/managing_openshift_ai/managing-observability_managing-rhoai) supplies metrics dashboards without additional dashboard RBAC. Centralized observability remains [Technology Preview](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/release_notes/technology-preview-features_relnotes); example retention/storage parameters are not measured capacity.

The [ODF infrastructure requirements](https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.22/html/planning_your_deployment/infrastructure-requirements_rhodf) allocate 1 CPU/4 GiB each to MCG core and database, plus 1 CPU/2 GiB per endpoint (default one or two): 3–4 CPU/10–12 GiB for those operands, excluding operator, storage and platform headroom. Validate standalone MCG/gp3 configuration against 4.22 CRDs; do not independently pin NooBaa.

## Resource and ownership decisions

| Resource | Current source or owner | Proposed treatment |
|---|---|---|
| GitOps bootstrap | `gitops/bootstrap/`; GitOps 1.20 | Retain native Operator installation; exact target pending |
| RHOAI Subscription, DSCI and DSC | `gitops/stages/010-openshift-ai-platform-foundation/base/rhoai/` | Change to verified 3.5 schema/channel after alignment; add MLflow and TrustyAI ownership |
| Dashboard, workbenches, model registry | Stage 010 DSC Managed components | Retain; validate each service independently |
| ODF MCG, object bucket and access resources | Stage 010 `base/odf/` and `base/access/` | Retain purpose; supported ODF version and object storage ownership pending |
| Observability operators and instances | Stage 010 manifests | Retain native ownership; exact version and health exits pending |
| Existing Keycloak, cert-manager and Lightspeed | Provider-supplied environment state | Preserve; explicitly decide integration scope before project subscriptions overlap |
| KServe, MaaS and LlamaStack | Later Stage 030/040 DSC writers | Keep later-stage ownership; revalidate old LlamaStack schema dependency |

Stage 020 also writes Kueue as Unmanaged. The Stage 010 Argo application ignores later component fields including Kueue, KServe, LlamaStack, AI pipelines, TrustyAI and MLflow. Preserve deliberate ownership boundaries only after checking the 3.5 schema and actual downstream writers; an ignored field is not an implemented feature.

## Existing workarounds and cleanup review

Current custom resources/jobs include the COO allowlist approval job, Prometheus TLS CA synchronization and console plugin jobs. The latter append shared Console plugin configuration, so ownership must remain explicit. Existing 3.4 overlays, the COO hold, TLS synchronization, Perses NetworkPolicy and RBAC are reachable resources with removal conditions in [Backlog](../../BACKLOG.md); none is safe to delete solely because it is old. The unused COO `operator/overlays/stable/` path is a candidate only after deciding the target COO policy; it might become the replacement.

Preserve operator ownership of the singleton OCSInitialization, generated NooBaa/OBC credentials and model registry database deployment. Review the current database TLS setting and registry role bindings against the target operator. Custom Argo health currently accepts all Pending PVCs and some statusless or matching-version resources; these scheduling/lifecycle workarounds must not substitute for actual service acceptance.

## New features and stage boundaries

[Dashboard customization](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/managing_resources/customizing-the-dashboard) documents `agentsCatalog: true` as Developer Preview. Agent Catalog discovers starter kits; it does not establish runtime hosting or automatic AgentCard registration. `agentOps` and `agentConfigManagement` are separate preview flags. The deprecated `mlflow` UI flag is not the enabling mechanism; operator presence controls its UI. Remove obsolete `maasAuthPolicies` and the current `autorag: true` target setting after schema verification; keep AutoRAG and AutoML excluded.

[Developer Preview release notes](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/release_notes/developer-preview-features_relnotes) describe OpenShell installation through Helm and linked upstream artifacts. This is a documented exception to native Operator installation, not a DSC component or evidence of supported Hermes integration. Do not introduce older Kagenti Agent/AgentRuntime/AgentCard operators. Shared OpenShell hosting and per-project standalone Hermes belong to later Stage 050/080 platform/use-case design after MaaS. Packaging, catalog discovery and runtime compatibility with Hermes remain unproven. The [linked OpenShell guide](https://github.com/opendatahub-io/agent-ops/blob/main/guides/getting-started-openshell-openshift.md) uses Helm and privileged SCC; [upstream SCC requirements](https://github.com/opendatahub-io/agent-ops/blob/main/scc-requirements.md) describe a different tested custom SCC with root and elevated capabilities. Neither establishes approval to grant permissions here. Resolve security, tenant isolation and topology before installation.

### Proposed Stage 010 feature additions

Enable built-in Agent Catalog discovery with `agentsCatalog: true`. Install one shared MLflow service and TrustyAI-managed EvalHub after their durable storage prerequisites. The current [support matrix](https://access.redhat.com/articles/rhoai-supported-configs-3.x) labels MLflow 3.14 GA and EvalHub 0.3 Technology Preview; the screenshot's EvalHub GA label does not override that source. User permission to explore previews does not resolve specific security or integration choices.

The [MLflow installation guide](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/working_with_mlflow/installing-mlflow_mlflow) uses DSC `mlflowoperator: Managed` and an `mlflow.opendatahub.io/v1` MLflow CR. Propose dedicated PostgreSQL and S3, with `serveArtifacts` proxying for durable evidence. Use `redhat-ods-applications` for MLflow because of the dashboard known issue. The guide calls the resource cluster-scoped while examples include namespaces: inspect the installed CRD scope before authoring resources.

The [EvalHub guide](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/evaluating_ai_systems/evaluating-llms-with-evalhub_evaluate) uses a TrustyAI-managed `v1` EvalHub CR, recommends PostgreSQL rather than in-memory SQLite, and describes tenant labels, RBAC and MLflow experiment tracking. Make MLflow Ready an explicit gate before creating EvalHub, as [known issue RHOAIENG-67534](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/release_notes/known-issues_relnotes) requires.

Do not select the EvalHub namespace or UI flag by guesswork. RHOAIENG-66068 names EvalHub in its heading but MLflow in its body/workaround, while the evaluation guide recommends a dedicated namespace. Verify dashboard discovery before choosing. The dashboard guide's `disableLMEval: false` and evaluation guide's `disableEvalHub: false` also need installed-schema/UI verification.

For the demo registry, retain the operator-provided PostgreSQL option with an explicit nonproduction posture. The [3.5 registry guide](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/managing_model_registries/creating-a-model-registry_managing-model-registries) permits that default for nonproduction and recommends external PostgreSQL 16 for production. Do not reuse the provider Keycloak database for registry, MLflow or EvalHub.

## Proposed implementation dependency sequence

After reconciliation and reviewed selections: guarded bootstrap → native operators/CRD verification → storage and dedicated PostgreSQL/S3 prerequisites → RHOAI core and native observability → model registry and MLflow service → verified MLflow Ready → EvalHub creation and MLflow integration → access setup and Stage 010 persona acceptance. Enable Agent Catalog discovery after schema verification. First real model evaluation follows available Stage 030/040 endpoints; it is a separate later acceptance gate.

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

## Pending alignment

Pending: production-support confirmation for the exact newer observability versions; MLflow CRD scope; EvalHub namespace and dashboard flag; dedicated PostgreSQL/S3 manifests and credentials ownership; provider Keycloak integration scope; native observability replacement/removal conditions; and final persona/functional acceptance commands. Reconciliation remains a prerequisite. OpenShell/Hermes installation is explicitly a later design decision, not part of Stage 010 acceptance.

## Implementation checkpoint

Implementation is prepared in an isolated managed worktree based on cached upstream `bfd6cc39`; the primary checkout and its credentials remain untouched. The reconciled cleanup preserves all 47 upstream commits and resolves the seven overlaps without textual conflicts. Source targets GitOps 1.21, bounded RHOAI 3.5 and ODF 4.22; full native tracing remains in scope. Catalog bundle CPE metadata maps OpenTelemetry 0.158 and Tempo 0.22 to product 3.11, independently of official support/version validation.

The user selected existing OpenID identities. Access setup preserves OAuth and provider Keycloak ownership; actual usernames and separate authenticated persona sessions remain inputs to final acceptance. Native Auth explicitly limits access to the two demo groups. `DISABLE_DSC_CONFIG=true` suppresses the operator-created default DSCI so GitOps owns initialization; the self-managed bootstrap path does not auto-create a DSC. New unused 3.5 DSC components are explicitly Removed; Stage 010 owns TrustyAI and MLflow. Legacy observability files are excluded from the fresh target but retained until native acceptance establishes removal conditions. No migration source has been deployed or published yet; deploy requires an explicit reviewed published revision.

The user authorized implementation and selected existing OpenID usernames `ai-admin` and `ai-developer`. The architect selected the exact observed COO 1.5.3, OpenTelemetry 0.158.0-2 and Tempo 0.22.0-2 CSVs under Manual approval, with native health and full metrics/traces acceptance. Bundle CPE metadata maps the latter two to product 3.11. The public lifecycle/support table has not established the exact OpenTelemetry/OCP 4.22 pairing; no production support or tested-tuple claim is implied by this demo selection.

The demo project is an EvalHub tenant with the empty presence label and explicit virtual-resource Role/RoleBinding for both persona groups, following [evaluation guide sections 2.28–2.30](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/evaluating_ai_systems/evaluating-llms-with-evalhub_evaluate). The server namespace remains unlabelled. Operator-owned tenant job identities, bindings and CA discovery are not duplicated. Static rendering must preserve those explicit resources/verbs without wildcards; real persona SAR/API access remains a live exit.
