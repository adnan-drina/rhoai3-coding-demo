# Platform Baseline

This file is the canonical platform target for the demo and shared skills. Update it first when preparing an upgrade.

READMEs explain capabilities for end users and state current product versions. Upgrade plans, environment migration history and technical migration commentary belong in `docs/migration/`. Reusable environment inventories, readiness findings and operational runbooks remain in the existing documents under `docs/`.

## Default environment and foundation (2026-10-05)

The new default environment is **observed OCP 4.22.14 / Kubernetes v1.35.6 on AWS**. Its inventory, preinstalled add-on ownership, exceptions and repeatable provisioning contract are maintained in [OPERATIONS](OPERATIONS.md#fresh-environment-baseline-2026-10-05). The table below is a historical reference; the Stage 010 selections and deployment evidence are recorded separately.

**RHOAI 3.5.1 is installed for Stage 010**, with MLflow; the native registry/catalogs have been adopted by Stage 030 through the protected f38-based ownership bridge. MLflow/EvalHub/TrustyAI belong to Stage 050 after serving/MaaS; OpenShell/Hermes hosting remains later design. AutoRAG and AutoML are excluded. Fresh Stage 010 source excludes MLflow. The deployed seven-resource MLflow handoff to Stage 050 completed on 2026-10-06 through the protected `eb75e665` core bridge; Stage 050 `af39a8b7` provides ready native EvalHub/TrustyAI with separate persistent PostgreSQL. Existing MLflow records, credentials and artifact storage are retained; no evaluation or model/GPU restart is part of this service foundation. Revised source groups Model Registry, Model Catalog and Agent Catalog in Stage 030; Stage 030 is deployed at `147b6208` with current native KServe and persistent monitoring. Genuine persona login and sandbox role separation passed (sanitized local evidence: `/private/tmp/persona-auth-20261005/independent-persona-validation.json`, 2026-10-05 13:21 UTC); actual dashboard/browser acceptance remains separate. The [supported-configurations matrix](https://access.redhat.com/articles/rhoai-supported-configs-3.x), updated 2026-10-02, includes OCP 4.22 for x86_64 RHOAI 3.5; its version range differs from the installation guide's narrower platform list. Consult both as documented in OPERATIONS.

Use version-matched 3.5/OCP 4.22 documentation for migration design and retain the following documented legacy references. The inventory verified the Stage 010 RHOAI 3.4 and ODF 4.20 manifest selections; other product entries and exact pins require per-stage source and runtime verification and can contain historical drift. Upgrade one stage's manifests, scripts, documentation and acceptance evidence together. Historical observations do not establish readiness on this environment.

## Stage 010 source selections

The isolated candidate source selects GitOps `gitops-1.21`, RHOAI `stable-3.5` and ODF `stable-4.22`, with native Automatic COO/OpenTelemetry/Tempo subscriptions and qualified version baselines 1.5.3/0.158.0-2/0.22.0-2. Bundle CPE metadata maps the latter two to product 3.11; exact public support-table coverage remains a documented limit. Native registry, metrics, Perses backend and exact trace retrieval checks passed; MLflow synthetic artifact/database persistence passed, and genuine persona login/sandbox role separation passed; actual dashboard browser acceptance remains separate. [The migration plan](migration/010-foundation-plan.md) records acceptance gates and remaining decisions; retain the historical table below for stage-by-stage reference.

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

## Version Match Rule

Project documentation, skills, and GitOps review notes must use the official Red Hat documentation version that matches the pinned baseline for each product family.

For the documented legacy reference baseline, RHOAI product-documentation links should use:

```text
https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/
```

For the documented legacy reference baseline, OCP product-documentation links should use:

```text
https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/
```

For the documented legacy reference baseline, ODF product-documentation links should use:

```text
https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.20/
```

For the documented legacy reference baseline, Red Hat build of OpenTelemetry documentation links should use:

```text
https://docs.redhat.com/en/documentation/red_hat_build_of_opentelemetry/3.9/
```

For the documented legacy reference baseline, Red Hat OpenShift distributed tracing platform documentation links should use:

```text
https://docs.redhat.com/en/documentation/red_hat_openshift_distributed_tracing_platform/3.9/
```

For the documented legacy reference baseline, Red Hat OpenShift Pipelines documentation links should use:

```text
https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.22/
```

For the documented legacy reference baseline, Red Hat OpenShift Lightspeed documentation links should use:

```text
https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/
```

For the documented legacy reference baseline, Red Hat OpenShift Dev Spaces documentation links should use:

```text
https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.28/
```

For the documented legacy reference baseline, Red Hat Developer Hub documentation links should use:

```text
https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/
```

For the documented legacy reference baseline, Red Hat Trusted Profile Analyzer documentation links should use:

```text
https://docs.redhat.com/en/documentation/red_hat_trusted_profile_analyzer/2.2/
```

For the documented legacy reference baseline, Migration Toolkit for Applications documentation links should use:

```text
https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.2/
```

For the documented legacy reference baseline, Red Hat Advanced Developer Suite - software supply chain documentation links should use:

```text
https://docs.redhat.com/en/documentation/red_hat_advanced_developer_suite_-_software_supply_chain/1.9/
```

Do not use `latest` or another product version for product configuration unless the Red Hat documentation landing page intentionally links to an unversioned Customer Portal article or no version-specific document exists. Record that as an explicit exception in the relevant document under `docs/`, review note, or skill reference.

Stage 010 selects OpenShift Data Foundation `stable-4.22` to match OCP `4.22` (installed 4.22.5). Red Hat ODF update guidance says the ODF version should match the OCP minor version. The earlier manifests pinned ODF `4.20` for the former OCP `4.20` baseline.

The Cluster Observability Operator follows the `stable` channel with Automatic approval (installed 1.5.3 on RHOAI 3.5.1). The earlier `cluster-observability-operator.v1.4.0` hold for the RHOAI 3.4 dashboard is retired; native metrics, Perses and trace checks passed on 1.5.3.

Red Hat Connectivity Link and its dependency Subscriptions (Authorino, DNS, Limitador) use Automatic approval on the `stable` channel without `startingCSV` (installed 2026-10-14: RHCL 1.4.3, Authorino 1.4.3, DNS 1.4.2, Limitador 1.4.2). The earlier `rhcl-operator.v1.3.4` hold for RHOAI 3.4 is retired. RHCL 1.4.0 stays deprecated; 1.4.3 has one known gateway issue (wasm-shim 0.14.2 holds responses without `usage.total_tokens`, see TROUBLESHOOTING).

This baseline pins product documentation versions and selected operator lifecycle policy where required. It does not pin generated operand image fields, copied CSV content, or operator-created Deployments. If a generated operand is incompatible with the installed operator or CRD, update the Subscription lifecycle policy, product baseline, or a documented product CR field; do not treat generated image fields as project-owned desired state.

## Red Hat OpenShift AI and OpenShift Container Platform Documentation Index

The cluster runs RHOAI 3.5.1 on OCP 4.22. The book-level index for both products, with the documentation version each
pin selects (RHOAI `3.5`, OCP `4.22`), lives in [`.agents/references/red-hat-doc-map.yaml`](../.agents/references/red-hat-doc-map.yaml) (`docs_slug`
`red_hat_openshift_ai_self-managed` and `openshift_container_platform`). Landing pages:
https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/ and
https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/

## Red Hat OpenShift Pipelines 1.24 Documentation Index

Use the official OpenShift Pipelines 1.24 landing page as the entry point: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/

- **About**: [Release notes](https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/release_notes/index), [About OpenShift Pipelines](https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/about_openshift_pipelines/index)
- **Installing and configuring**: [Installing and configuring](https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/installing_and_configuring/index), [Managing performance and resource use](https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/managing_performance_and_resource_use/index)
- **Security**: [Securing OpenShift Pipelines](https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/securing_openshift_pipelines/index)
- **Observability**: [Observability in OpenShift Pipelines](https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/observability_in_openshift_pipelines/index)
- **Pipelines as Code**: [Pipelines as Code](https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/pipelines_as_code/index)
- **Creating CI/CD pipelines**: [Creating CI/CD pipelines](https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/creating_cicd_pipelines/index)
- **Reference**: [Pipelines CLI (tkn) reference](https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/pipelines_cli_tkn_reference/index)

Pipelines 1.24 removes PAC Tekton Hub integration; use the current resolver guidance and Artifact Hub.

## Red Hat OpenShift Lightspeed 1.0 Documentation Index

Use the official OpenShift Lightspeed 1.0 landing page as the entry point: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0

- **About**: [Introduction to OpenShift Lightspeed](https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html/about/index), [Release Notes](https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html/release_notes/index), [Verifying version compatibility](https://access.redhat.com/support/policy/updates/openshift_operators)
- **Installing**: [Installing OpenShift Lightspeed](https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html/install/index)
- **Configuring**: [Configuring OpenShift Lightspeed](https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html/configure/index)
- **Operations**: [Using OpenShift Lightspeed](https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html/operate/index)
- **Troubleshoot**: [Troubleshooting OpenShift Lightspeed](https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html/troubleshoot/index)

## Red Hat Connectivity Link 1.3 Documentation Index

The demo pins `rhcl-operator.v1.3.4`. RHCL 1.4.0 is deprecated per the official 1.4 release notes. Skills are based on the 1.3 documentation.

Use the official RHCL 1.3 landing page as the entry point: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.3

- **Discover**: [Red Hat Connectivity Link](https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.3/html/red_hat_connectivity_link/index), [MCP gateway](https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.3/html/mcp_gateway/index)
- **What's New**: [Release notes](https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.3/html/release_notes/index)
- **Install**: [Installing Connectivity Link](https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.3/html/installing_connectivity_link/index), [Installing the MCP gateway](https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.3/html/installing_the_mcp_gateway/index)
- **Configure and Secure**: [Deploying Connectivity Link](https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.3/html/deploying_red_hat_connectivity_link/index), [Registering MCP servers and creating policies](https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.3/html/registering_mcp_servers_and_creating_policies/index)
- **Observe and Troubleshoot**: [Observability](https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.3/html/observability/index), [Troubleshooting](https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.3/html/troubleshooting/index)
- **Upgrade**: [Updating Red Hat Connectivity Link](https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.3/html/updating_red_hat_connectivity_link/index)

## Red Hat Advanced Developer Suite - Software Supply Chain 1.9 Documentation Index

Use the official RHADS-SSC 1.9 landing page as the entry point: https://docs.redhat.com/en/documentation/red_hat_advanced_developer_suite_-_software_supply_chain/1.9

- **Discover**: [Understanding RHADS-SSC](https://docs.redhat.com/en/documentation/red_hat_advanced_developer_suite_-_software_supply_chain/1.9/html/understanding_red_hat_advanced_developer_suite_-_software_supply_chain/index), [Release notes](https://docs.redhat.com/en/documentation/red_hat_advanced_developer_suite_-_software_supply_chain/1.9/html/release_notes_for_red_hat_advanced_developer_suite_-_software_supply_chain_1.9/index)
- **Get started**: [Getting Started](https://docs.redhat.com/en/documentation/red_hat_advanced_developer_suite_-_software_supply_chain/1.9/html/getting_started_with_red_hat_advanced_developer_suite_-_software_supply_chain/index), [Using standalone CLIs](https://docs.redhat.com/en/documentation/red_hat_advanced_developer_suite_-_software_supply_chain/1.9/html/using_standalone_clis/index)
- **Install**: [Installing](https://docs.redhat.com/en/documentation/red_hat_advanced_developer_suite_-_software_supply_chain/1.9/html/installing_red_hat_advanced_developer_suite_-_software_supply_chain/index)
- **CI/CD**: [Azure Pipelines](https://docs.redhat.com/en/documentation/red_hat_advanced_developer_suite_-_software_supply_chain/1.9/html/integrating_azure_pipelines/index), [GitHub Actions](https://docs.redhat.com/en/documentation/red_hat_advanced_developer_suite_-_software_supply_chain/1.9/html/integrating_github_actions/index), [GitLab CI](https://docs.redhat.com/en/documentation/red_hat_advanced_developer_suite_-_software_supply_chain/1.9/html/integrating_gitlab_ci/index), [Jenkins](https://docs.redhat.com/en/documentation/red_hat_advanced_developer_suite_-_software_supply_chain/1.9/html/integrating_jenkins/index), [Tekton](https://docs.redhat.com/en/documentation/red_hat_advanced_developer_suite_-_software_supply_chain/1.9/html/defining_pipelines_with_tekton/index)
- **Secure Your Software Supply Chain**: [Customizing](https://docs.redhat.com/en/documentation/red_hat_advanced_developer_suite_-_software_supply_chain/1.9/html/customizing_red_hat_advanced_developer_suite_-_software_supply_chain/index), [Inspecting SBOMs](https://docs.redhat.com/en/documentation/red_hat_advanced_developer_suite_-_software_supply_chain/1.9/html/inspecting_sboms/index), [Managing compliance](https://docs.redhat.com/en/documentation/red_hat_advanced_developer_suite_-_software_supply_chain/1.9/html/managing_compliance/index)

## Migration Toolkit for Applications 8.3 Documentation Index

Use the official MTA 8.3 landing page as the entry point: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3

- **What's New**: [Release Notes](https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/release_notes/index)
- **Install**: [Installing MTA](https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/installing_the_migration_toolkit_for_applications/index)
- **AI**: [Developer Lightspeed for MTA](https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_red_hat_developer_lightspeed_for_mta/index)
- **Using the Tools**: [CLI](https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/using_the_migration_toolkit_for_applications_command-line_interface/index), [UI](https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_managing_the_migration_toolkit_for_applications_user_interface/index), [VS Code Extension](https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_the_visual_studio_code_extension_for_mta/index), [IntelliJ IDEA plugin](https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/intellij_idea_plugin_guide/index)
- **Rules Development**: [Custom rules](https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_rules_for_an_mta_analysis/index)

## Red Hat Trusted Profile Analyzer 2.2 Documentation Index

Use the official Trusted Profile Analyzer 2.2 landing page as the entry point: https://docs.redhat.com/en/documentation/red_hat_trusted_profile_analyzer/2.2

- **Discover**: [Release Notes](https://docs.redhat.com/en/documentation/red_hat_trusted_profile_analyzer/2.2/html/release_notes/index)
- **Get Started**: [Quick Start Guide](https://docs.redhat.com/en/documentation/red_hat_trusted_profile_analyzer/2.2/html/quick_start_guide/index), [Deployment Guide](https://docs.redhat.com/en/documentation/red_hat_trusted_profile_analyzer/2.2/html/deployment_guide/index)
- **Reference**: [Administration Guide](https://docs.redhat.com/en/documentation/red_hat_trusted_profile_analyzer/2.2/html/administration_guide/index)

## Red Hat Developer Hub 1.10 Documentation Index

Use the official Red Hat Developer Hub 1.10 landing page as the entry point: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10

- **Discover**: [About Red Hat Developer Hub](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html/about_red_hat_developer_hub/index)
- **What's New**: [Release notes](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html/red_hat_developer_hub_release_notes/index), [Explore preview of emerging and supplemental capabilities](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html/explore_preview_of_emerging_and_supplemental_capabilities/index)
- **Get started**: [Setting up and configuring your first instance](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html/setting_up_and_configuring_your_first_red_hat_developer_hub_instance/index), [Navigate on your first day](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html/navigate_red_hat_developer_hub_on_your_first_day/index)
- **Install**: [On OpenShift Container Platform](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html/installing_red_hat_developer_hub_on_openshift_container_platform/index), [On AKS](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html/installing_red_hat_developer_hub_on_microsoft_azure_kubernetes_service_aks/index), [On EKS](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html/installing_red_hat_developer_hub_on_amazon_elastic_kubernetes_service_eks/index), [On OpenShift Dedicated on Google Cloud](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html/installing_red_hat_developer_hub_on_openshift_dedicated_on_google_cloud/index), [On GKE](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html/installing_red_hat_developer_hub_on_google_kubernetes_engine_gke/index), [In an air-gapped environment](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html/installing_red_hat_developer_hub_in_an_air-gapped_environment/index)
- **Upgrade**: [Upgrading Red Hat Developer Hub](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html/upgrading_red_hat_developer_hub/index)
- **Configure**: [Configuring](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html/configuring_red_hat_developer_hub/index), [Customizing](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html/customizing_red_hat_developer_hub/index), [TechDocs](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html/techdocs_for_red_hat_developer_hub/index)
- **Control access**: [Authentication](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html/authentication_in_red_hat_developer_hub/index), [Authorization](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html/authorization_in_red_hat_developer_hub/index)
- **Integrate**: [Git provider](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html/integrating_red_hat_developer_hub_with_your_git_provider/index), [Developer Lightspeed](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html/interacting_with_red_hat_developer_lightspeed_for_red_hat_developer_hub/index), [MCP tools](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html/interacting_with_model_context_protocol_tools_for_red_hat_developer_hub/index), [OpenShift AI Connector](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html/accelerate_ai_development_with_openshift_ai_connector_for_red_hat_developer_hub/index)
- **Develop**: [Software development and management](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html/streamline_software_development_and_management_in_red_hat_developer_hub/index), [Technical documentation management](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html/manage_and_consume_technical_documentation_within_red_hat_developer_hub/index)
- **Observability**: [Adoption Insights](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html/adoption_insights_in_red_hat_developer_hub/index), [Audit logs](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html/audit_logs_in_red_hat_developer_hub/index), [Monitoring and logging](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html/monitoring_and_logging/index), [Telemetry](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html/telemetry_data_collection_and_analysis/index), [Scorecards](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html/evaluate_project_health_using_scorecards/index), [Diagnostic data](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html/collect_diagnostic_data_to_streamline_support_resolution/index)
- **Extend**: [Orchestrator](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html/orchestrator_in_red_hat_developer_hub/index), [Develop and deploy dynamic plugins](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html/develop_and_deploy_dynamic_plugins_in_red_hat_developer_hub/index), [Installing and viewing plugins](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html/installing_and_viewing_plugins_in_red_hat_developer_hub/index), [Using dynamic plugins](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html/using_dynamic_plugins_in_red_hat_developer_hub/index), [Dynamic plugins reference](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html/dynamic_plugins_reference/index), [Configuring dynamic plugins](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html/configuring_dynamic_plugins/index)
- **Reference**: [Helm Chart configuration reference](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html/helm_chart_configuration_reference/index)

## Red Hat OpenShift Dev Spaces 3.30 Documentation Index

Use the current topic navigation: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/

- [Architecture](https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/discover-assembly_architecture)
- [Supported platforms](https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/plan-supported_platforms_ref)
- [GitOps installation](https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/install-proc_deploying_devspaces_using_gitops)
- [CheCluster fields](https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/configure-ref_checluster_custom_resource_fields)
- [Devfiles](https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/develop-con_devfile_introduction)
- [Workspace storage](https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/develop-con_requesting_persistent_storage_for_workspaces)
- [GitLab OAuth application](https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/integrate-proc_setting_up_the_gitlab_authorized_application)
- [GitLab OAuth Secret](https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/integrate-proc_applying_the_gitlab_authorized_application_secret)
- [Release notes](https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/whats_new-ref_release_notes)
- [3.30.2 patch](https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/whats_new-dev_spaces_3_30_patch_release_september_30__2026)

## OpenShift Data Foundation Documentation Index

ODF follows the OpenShift minor (`stable-4.22`). The book-level index lives in
[`.agents/references/red-hat-doc-map.yaml`](../.agents/references/red-hat-doc-map.yaml) (`docs_slug` `red_hat_openshift_data_foundation`). Landing page:
https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.22/

## ODF Demo Storage Intent

The demo should start with the minimum ODF footprint needed by RHOAI:

- Prefer standalone Multicloud Object Gateway (MCG/NooBaa) for S3-compatible object storage used by model artifacts, AI Pipelines, MLflow, evaluation evidence, and other RHOAI object-store integrations.
- Prefer `ObjectBucketClaim` resources for project-scoped buckets and generated ConfigMaps/Secrets containing S3 connection information.
- Keep full ODF StorageCluster/Ceph block and file storage as an explicit implementation decision only when the demo needs ODF-provided RWO/RWX PVCs beyond the underlying OpenShift storage classes.
- Use the Red Hat Developer ODF article as narrative and implementation context for lightweight MCG and OBC workflows; product configuration truth remains the ODF 4.22 documentation above.

## Source Hierarchy

1. Official Red Hat product documentation for the active baseline.
2. Official Red Hat articles, blogs, and product messaging for narrative and examples.
3. `/Users/adrina/Sandbox/rh-brain/Red Hat Brain` as read-only research input.
4. Existing repo implementation, scripts, and READMEs.
5. Live cluster schema verification with commands such as `oc explain` and `oc get crd`.

Official product documentation remains the source of truth for supported configuration. Do not invent CR fields, API versions, annotations, or operator configuration.

## Skill Metadata Policy

Shared skills should reference this repository baseline rather than repeating exact platform versions in every skill frontmatter. Use exact version-specific reference files only when a workflow genuinely differs across platform versions.


### Stage 040 current runtime checkpoint (2026-10-05)

Stage 040 at `6ab5e6f9ee35c89d189c6f48973f8bf40be620f1` reconciled successfully. Two pinned private Qwen models, Red Hat MiniMax streaming, genuine key lifecycle, isolated quota enforcement and the key-list backend repair passed. All 18 retained registry/MLflow/OBC metadata identities were independently preserved; core 010 stays on the retention bridge. GPT account credits, unqualified EPP execution and user-owned Studio visual checks prevent a full Stage 040 acceptance claim. [Technical evidence](migration/040-governed-serving-plan.md#final-bounded-runtime-evidence).

The future [Automatic operator policy](migration/035-operator-automatic-policy.md) supersedes historical Manual lifecycle instructions for the RHOAI 3.5 source. Historical 3.4/1.3 receipts below remain historical; current RHCL baseline is 1.4.3.
