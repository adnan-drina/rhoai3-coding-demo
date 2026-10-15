# Platform baseline history

Moved unchanged from `docs/PLATFORM_BASELINE.md` on 2026-10-15, when product documentation
versions moved to `.agents/references/red-hat-doc-map.yaml`. Historical record only; versions here are not current.

## Default environment and foundation (2026-10-05)

The new default environment is **observed OCP 4.22.14 / Kubernetes v1.35.6 on AWS**. Its inventory, preinstalled add-on ownership, exceptions and repeatable provisioning contract are maintained in [OPERATIONS](../OPERATIONS.md#fresh-environment-baseline-2026-10-05). The table below is a historical reference; the Stage 010 selections and deployment evidence are recorded separately.

**RHOAI 3.5.1 is installed for Stage 010**, with MLflow; the native registry/catalogs have been adopted by Stage 030 through the protected f38-based ownership bridge. MLflow/EvalHub/TrustyAI belong to Stage 050 after serving/MaaS; OpenShell/Hermes hosting remains later design. AutoRAG and AutoML are excluded. Fresh Stage 010 source excludes MLflow. The deployed seven-resource MLflow handoff to Stage 050 completed on 2026-10-06 through the protected `eb75e665` core bridge; Stage 050 `af39a8b7` provides ready native EvalHub/TrustyAI with separate persistent PostgreSQL. Existing MLflow records, credentials and artifact storage are retained; no evaluation or model/GPU restart is part of this service foundation. Revised source groups Model Registry, Model Catalog and Agent Catalog in Stage 030; Stage 030 is deployed at `147b6208` with current native KServe and persistent monitoring. Genuine persona login and sandbox role separation passed (sanitized local evidence: `/private/tmp/persona-auth-20261005/independent-persona-validation.json`, 2026-10-05 13:21 UTC); actual dashboard/browser acceptance remains separate. The [supported-configurations matrix](https://access.redhat.com/articles/rhoai-supported-configs-3.x), updated 2026-10-02, includes OCP 4.22 for x86_64 RHOAI 3.5; its version range differs from the installation guide's narrower platform list. Consult both as documented in OPERATIONS.

Use version-matched 3.5/OCP 4.22 documentation for migration design and retain the following documented legacy references. The inventory verified the Stage 010 RHOAI 3.4 and ODF 4.20 manifest selections; other product entries and exact pins require per-stage source and runtime verification and can contain historical drift. Upgrade one stage's manifests, scripts, documentation and acceptance evidence together. Historical observations do not establish readiness on this environment.

## Stage 010 source selections

The isolated candidate source selects GitOps `gitops-1.21`, RHOAI `stable-3.5` and ODF `stable-4.22`, with native Automatic COO/OpenTelemetry/Tempo subscriptions and qualified version baselines 1.5.3/0.158.0-2/0.22.0-2. Bundle CPE metadata maps the latter two to product 3.11; exact public support-table coverage remains a documented limit. Native registry, metrics, Perses backend and exact trace retrieval checks passed; MLflow synthetic artifact/database persistence passed, and genuine persona login/sandbox role separation passed; actual dashboard browser acceptance remains separate. [The migration plan](010-foundation-plan.md) records acceptance gates and remaining decisions; retain the historical table below for stage-by-stage reference.

## Stage 070 documentation targets (2026-10-13)

The user authorized refreshing product skills to current versions alongside
the Stage 070 upgrade. These are verified documentation targets, not a claim
that the upgraded components have been deployed or accepted on this cluster.

| Product | Current documentation reviewed | Branch deployment selection |
|---|---|---|
| MTA | 8.3 / 8.3.1 | Operator/operands 8.3.1 selected from the Red Hat catalog; workspace CLI/RPC remains independently qualified at 8.3.0 |
| OpenShift Vertical Pod Autoscaler | OCP4.22 Nodes and live4.22 CRD, reviewed2026-10-14 | Official stable4.22.0-202609291750; one memory-only MTA controller policy |
| OpenShift Dev Spaces | 3.30 / 3.30.2 | 3.30.2 |
| OpenShift Pipelines | 1.24, including 1.24.1 | 1.24.0; qualify the newer security patch before repinning |
| Red Hat Developer Hub | 1.10, including 1.10.5 | 1.10.5 |

Current MTA/Dev Spaces/Pipelines workflow skills use these versioned sources.
Five Developer Hub skills have a refreshed 1.10 source review. Detailed earlier
extractions retain their provenance and are superseded by the verified-update
sections; unrecaptured fields still require current guide/CLI/CRD verification.

Dev Spaces 3.30 now uses topic URLs rather than the old administration/user
book routes. Pipelines 1.24 removes PAC's Tekton Hub integration. MTA's native
Agents are Developer Preview, distinct from Technology Preview Lightspeed.
RHDH 1.10 removes several embedded plugin wrappers and requires external OCI
packages. The current RHDH lifecycle matrix includes OCP 4.22 for 1.10, resolving
the narrower list in its upgrade guide; actual live acceptance remains separate.

Other skill families have not been relabeled wholesale: their older captured
documentation remains explicit. In particular OCP 4.20, ODF 4.20 and RHOAI 3.4
captures require review against the active 4.22/4.22/3.5 platform before use.
Documentation freshness must not silently change a frozen migration run.

## Documented legacy reference baseline

| Component | Version | Documentation |
|-----------|---------|---------------|
| Red Hat OpenShift AI Self-Managed | 3.4 | https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/ |
| Red Hat OpenShift Container Platform | 4.20 | https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/ |
| Red Hat OpenShift Data Foundation | 4.20 | https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.20/ |
| Red Hat Connectivity Link | 1.3.4 (1.4.0 deprecated) | https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.3 |
| Red Hat OpenShift Cluster Observability Operator | `stable`, Automatic (installed 1.5.3; the 1.4.0 hold for RHOAI 3.4 is retired) | https://docs.redhat.com/en/documentation/red_hat_openshift_cluster_observability_operator/1-latest/ |
| Red Hat build of OpenTelemetry | 3.9 | https://docs.redhat.com/en/documentation/red_hat_build_of_opentelemetry/3.9 |
| Red Hat OpenShift distributed tracing platform | 3.9 | https://docs.redhat.com/en/documentation/red_hat_openshift_distributed_tracing_platform/3.9 |
| Red Hat OpenShift Pipelines | 1.22 | https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.22/ |
| Red Hat OpenShift Lightspeed | 1.0 | https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0 |
| Red Hat OpenShift Dev Spaces | 3.28 | https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.28 |
| Red Hat Developer Hub | 1.10 | https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10 |
| Red Hat Trusted Profile Analyzer | 2.2 | https://docs.redhat.com/en/documentation/red_hat_trusted_profile_analyzer/2.2 |
| Migration Toolkit for Applications | 8.2 | https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.2 |
| Red Hat Advanced Developer Suite - software supply chain | 1.9 | https://docs.redhat.com/en/documentation/red_hat_advanced_developer_suite_-_software_supply_chain/1.9 |

## Stage 040 current runtime checkpoint (2026-10-05)

Stage 040 at `6ab5e6f9ee35c89d189c6f48973f8bf40be620f1` reconciled successfully. Two pinned private Qwen models, Red Hat MiniMax streaming, genuine key lifecycle, isolated quota enforcement and the key-list backend repair passed. All 18 retained registry/MLflow/OBC metadata identities were independently preserved; core 010 stays on the retention bridge. GPT account credits, unqualified EPP execution and user-owned Studio visual checks prevent a full Stage 040 acceptance claim. [Technical evidence](040-governed-serving-plan.md#final-bounded-runtime-evidence).

The future [Automatic operator policy](035-operator-automatic-policy.md) supersedes historical Manual lifecycle instructions for the RHOAI 3.5 source. Historical 3.4/1.3 receipts below remain historical; current RHCL baseline is 1.4.3.
