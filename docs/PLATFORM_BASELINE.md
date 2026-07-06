# Platform Baseline

This file is the canonical platform target for the demo and shared skills.
Update it first when preparing an upgrade.

## Current Baseline

| Component | Version | Documentation |
|-----------|---------|---------------|
| Red Hat OpenShift AI Self-Managed | 3.4 | https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/ |
| Red Hat OpenShift Container Platform | 4.20 | https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/ |
| Red Hat OpenShift Data Foundation | 4.20 | https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.20/ |
| Red Hat Connectivity Link | 1.3.4 compatibility hold | https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html/release_notes/rhcl-release-notes |
| Red Hat OpenShift Cluster Observability Operator | 1.4.0 compatibility hold | https://docs.redhat.com/en/documentation/red_hat_openshift_cluster_observability_operator/1-latest/ |
| Red Hat build of OpenTelemetry | 3.9 | https://docs.redhat.com/en/documentation/red_hat_build_of_opentelemetry/3.9 |
| Red Hat OpenShift distributed tracing platform | 3.9 | https://docs.redhat.com/en/documentation/red_hat_openshift_distributed_tracing_platform/3.9 |
| Red Hat OpenShift Pipelines | 1.22 | https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.22/ |
| Red Hat OpenShift Lightspeed | 1.0 | https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0 |

## Version Match Rule

Project documentation, skills, and GitOps review notes must use the official
Red Hat documentation version that matches the pinned baseline for each product
family.

For the current baseline, RHOAI product-documentation links should use:

```text
https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/
```

For the current baseline, OCP product-documentation links should use:

```text
https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/
```

For the current baseline, ODF product-documentation links should use:

```text
https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.20/
```

For the current baseline, Red Hat build of OpenTelemetry documentation links
should use:

```text
https://docs.redhat.com/en/documentation/red_hat_build_of_opentelemetry/3.9/
```

For the current baseline, Red Hat OpenShift distributed tracing platform
documentation links should use:

```text
https://docs.redhat.com/en/documentation/red_hat_openshift_distributed_tracing_platform/3.9/
```

For the current baseline, Red Hat OpenShift Pipelines documentation links
should use:

```text
https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.22/
```

For the current baseline, Red Hat OpenShift Lightspeed documentation links
should use:

```text
https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/
```

Do not use `latest` or another product version for product configuration unless
the Red Hat documentation landing page intentionally links to an unversioned
Customer Portal article or no version-specific document exists. Record that as
an explicit exception in the relevant README, review note, or skill reference.

OpenShift Data Foundation is pinned to `4.20` because the demo OpenShift
baseline is OCP `4.20`. Red Hat ODF update guidance says the ODF version should
match the OCP minor version, and on OCP `4.20`, ODF `4.20` is the latest
compatible ODF version that can be installed.

The Cluster Observability Operator is held at
`cluster-observability-operator.v1.4.0` for the RHOAI 3.4 observability
dashboard. This is an OLM lifecycle compatibility hold, not an operand image
pin: the operator still manages Perses, Prometheus, and related operand images.
Remove the hold only after validating that the active RHOAI 3.4 build generates
Perses resources compatible with the newer Cluster Observability Operator CRD
schema and operand behavior.

Red Hat Connectivity Link is held at `rhcl-operator.v1.3.4` for the RHOAI 3.4
MaaS Gateway path. RHCL 1.4.0 is deprecated in the official RHCL 1.4 release
notes, which direct upgrade customers to pin Connectivity Link and dependent
operators to the latest 1.3.z version. Stage 040 therefore also GitOps-manages
the RHCL dependency Subscriptions for Authorino, DNS, and Limitador with
manual approval and 1.3.x `startingCSV` values. Do not approve RHCL 1.4.x
InstallPlans until Red Hat publishes a supported replacement path and the Stage
220 MaaS Gateway, dashboard, API-key, local-model, external-model, and
Playground regression gates pass.

This baseline pins product documentation versions and selected operator
lifecycle policy where required. It does not pin generated operand image
fields, copied CSV content, or operator-created Deployments. If a generated
operand is incompatible with the installed operator or CRD, update the
Subscription lifecycle policy, product baseline, or a documented product CR
field; do not treat generated image fields as project-owned desired state.

## Red Hat OpenShift AI 3.4 Documentation Index

Use the official RHOAI 3.4 landing page as the entry point:
https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/

- **What's New**:
  [Release Notes](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/release_notes),
  [Red Hat OpenShift AI lifecycle](https://access.redhat.com/support/policy/updates/rhoai-sm/lifecycle)
- **Get started**:
  [Get started with projects, workbenches, and pipelines](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/getting_started_with_red_hat_openshift_ai_self-managed),
  [Fraud detection tutorial](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/openshift_ai_tutorial_-_fraud_detection_example)
- **Plan**:
  [Prepare your platform and hardware for Red Hat AI](https://docs.redhat.com/en/documentation/red_hat_ai/3/html/supported_product_and_hardware_configurations/index),
  [Choose a validated model](https://docs.redhat.com/en/documentation/red_hat_ai/3/html/validated_models/index)
- **Install**:
  [Installing and uninstalling OpenShift AI Self-Managed](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/installing_and_uninstalling_openshift_ai_self-managed),
  [Installing in a disconnected environment](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/installing_and_uninstalling_openshift_ai_self-managed_in_a_disconnected_environment)
- **Administer**:
  [Managing OpenShift AI](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_openshift_ai),
  [Managing resources](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_resources),
  [Working with accelerators](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/working_with_accelerators),
  [Configuring your model-serving platform](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/configuring_your_model-serving_platform),
  [Working with Llama Stack](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/working_with_llama_stack),
  [Managing model registries](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_model_registries),
  [Manage and govern model catalog sources](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/manage_and_govern_model_catalog_sources/index),
  [Managing and monitoring models](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_and_monitoring_models)
- **Develop**:
  [Working with model registries](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/working_with_model_registries),
  [Working with the model catalog](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/working_with_the_model_catalog),
  [Experimenting with models in the gen AI playground](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/experimenting_with_models_in_the_gen_ai_playground),
  [Working with AutoRAG](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_with_autorag/index),
  [Working with distributed workloads](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/working_with_distributed_workloads),
  [Working with data in an S3-compatible object store](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_with_data_in_an_s3-compatible_object_store/index),
  [Working on projects](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/working_on_projects),
  [Working in your data science IDE](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_in_your_data_science_ide/index),
  [Working with connected applications](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_with_connected_applications/index),
  [Creating distributed data processing applications with the Kubeflow Spark Operator](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/creating_distributed_data_processing_applications_with_the_kubeflow_spark_operator/index),
  [Working with AI pipelines](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_with_ai_pipelines/index),
  [Working with machine learning features](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_with_machine_learning_features/index),
  [Working with AutoML](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_with_automl/index),
  [Working with MLflow](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_with_mlflow/index)
- **Train**:
  [Customize Models for Gen AI and Agentic AI Applications](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/customize_models_for_gen_ai_and_agentic_ai_applications/index)
- **Evaluate**:
  [Evaluating AI systems](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/evaluating_ai_systems/index)
- **Maintain Safety**:
  [Ensuring AI safety with guardrails](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/enabling_ai_safety_with_guardrails/index)
- **Monitor**:
  [Monitoring your AI systems](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/monitoring_your_ai_systems/index)
- **Deploy**:
  [Deploying models](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/deploying_models/index),
  [Govern LLM access with Models-as-a-Service](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/govern_llm_access_with_models-as-a-service/index),
  [Deploy models using Distributed Inference with llm-d](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/deploy_models_using_distributed_inference_with_llm-d/index)
- **Learn**:
  [RHOAI supported configurations](https://access.redhat.com/articles/rhoai-supported-configs-3.x),
  [Red Hat AI Foundations](https://docs.redhat.com/en/ai-foundations),
  [Red Hat AI learning hub](https://docs.redhat.com/en/learn/ai)

## OpenShift Container Platform 4.20 Documentation Index

Use the official OCP 4.20 landing page as the entry point:
https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/

- **Configure**:
  [etcd](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html-single/etcd/index)
- **Update and migrate**:
  [Updating clusters](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/updating_clusters/index)
- **Authentication and authorization**:
  [Authentication and authorization](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/authentication_and_authorization/index)
- **Security and compliance**:
  [Security and compliance](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/security_and_compliance/index)
- **Observability**:
  [Observability overview](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/observability_overview/index),
  [Monitoring](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/monitoring/index),
  [Logging](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/logging/index),
  [Cluster Observability Operator](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/cluster_observability_operator/index),
  [Red Hat build of OpenTelemetry](https://docs.redhat.com/en/documentation/red_hat_build_of_opentelemetry/3.9),
  [Red Hat OpenShift distributed tracing platform](https://docs.redhat.com/en/documentation/red_hat_openshift_distributed_tracing_platform/3.9)
- **AI workloads**:
  [AI workloads](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/ai_workloads/index)
- **CI/CD, GitOps, and builds**:
  [CI/CD overview](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/cicd_overview/index),
  [GitOps](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/gitops/index),
  [Builds using Shipwright](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/builds_using_shipwright/index),
  [Builds using BuildConfig](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/builds_using_buildconfig/index)
- **Machine management, machine configuration, and nodes**:
  [Machine management](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/machine_management/index),
  [Machine configuration](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/machine_configuration/index),
  [Nodes](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/nodes/index)
- **Specialized hardware and driver enablement**:
  [Specialized hardware and driver enablement](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/specialized_hardware_and_driver_enablement/index)
- **CLI and web console**:
  [CLI tools](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/cli_tools/index),
  [Web console](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/web_console/index)
- **Networking**:
  [Networking](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/networking/index),
  [Ingress and load balancing](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/ingress_and_load_balancing/index),
  [Networking Operators](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/networking_operators/index)
- **Storage**:
  [Storage](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/storage/index)
- **Images, registry, and mirroring**:
  [Images](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/images/index),
  [Registry](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/registry/index),
  [Disconnected environments](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/disconnected_environments/index)

## Red Hat OpenShift Pipelines 1.22 Documentation Index

Use the official OpenShift Pipelines 1.22 landing page as the entry point:
https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.22/

- **About**:
  [Release notes](https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.22/html/release_notes/index),
  [About OpenShift Pipelines](https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.22/html/about_openshift_pipelines/index)
- **Installing and configuring**:
  [Installing and configuring](https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.22/html/installing_and_configuring/index),
  [Managing performance and resource use](https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.22/html/managing_performance_and_resource_use/index)
- **Security**:
  [Securing OpenShift Pipelines](https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.22/html/securing_openshift_pipelines/index)
- **Observability**:
  [Observability in OpenShift Pipelines](https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.22/html/observability_in_openshift_pipelines/index)
- **Pipelines as Code**:
  [Pipelines as Code](https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.22/html/pipelines_as_code/index)
- **Creating CI/CD pipelines**:
  [Creating CI/CD pipelines](https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.22/html/creating_cicd_pipelines/index)
- **Custom Tekton Hub instance**:
  [Custom Tekton Hub instance](https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.22/html/custom_tekton_hub_instance/index)
- **Reference**:
  [Pipelines CLI (tkn) reference](https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.22/html/pipelines_cli_tkn_reference/index)

## Red Hat OpenShift Lightspeed 1.0 Documentation Index

Use the official OpenShift Lightspeed 1.0 landing page as the entry point:
https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0

- **About**:
  [Introduction to OpenShift Lightspeed](https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html/about/index),
  [Release Notes](https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html/release_notes/index),
  [Verifying version compatibility](https://access.redhat.com/support/policy/updates/openshift_operators)
- **Installing**:
  [Installing OpenShift Lightspeed](https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html/install/index)
- **Configuring**:
  [Configuring OpenShift Lightspeed](https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html/configure/index)
- **Operations**:
  [Using OpenShift Lightspeed](https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html/operate/index)
- **Troubleshoot**:
  [Troubleshooting OpenShift Lightspeed](https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html/troubleshoot/index)

## OpenShift Data Foundation 4.20 Documentation Index

Use the official ODF 4.20 landing page as the entry point:
https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.20/

- **Planning**:
  [4.20 Release Notes](https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.20/html/4.20_release_notes/index),
  [Planning your deployment](https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.20/html-single/planning_your_deployment/index),
  [Red Hat OpenShift Data Foundation architecture](https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.20/html-single/red_hat_openshift_data_foundation_architecture/index)
- **Deploying**:
  [Deploying OpenShift Data Foundation using Amazon Web Services](https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.20/html-single/deploying_openshift_data_foundation_using_amazon_web_services/index),
  [Deploying OpenShift Data Foundation on any platform](https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.20/html-single/deploying_openshift_data_foundation_on_any_platform/index)
- **Managing**:
  [Managing hybrid and multicloud resources](https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.20/html/managing_hybrid_and_multicloud_resources/index),
  [Managing and allocating storage resources](https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.20/html-single/managing_and_allocating_storage_resources/index)
- **Updating**:
  [Updating OpenShift Data Foundation](https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.20/html-single/updating_openshift_data_foundation/index)
- **Monitoring and troubleshooting**:
  [Monitoring OpenShift Data Foundation](https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.20/html-single/monitoring_openshift_data_foundation/index),
  [Troubleshooting OpenShift Data Foundation](https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.20/html-single/troubleshooting_openshift_data_foundation/index)

## ODF Demo Storage Intent

The demo should start with the minimum ODF footprint needed by RHOAI:

- Prefer standalone Multicloud Object Gateway (MCG/NooBaa) for S3-compatible
  object storage used by model artifacts, AI Pipelines, MLflow, evaluation
  evidence, and other RHOAI object-store integrations.
- Prefer `ObjectBucketClaim` resources for project-scoped buckets and
  generated ConfigMaps/Secrets containing S3 connection information.
- Keep full ODF StorageCluster/Ceph block and file storage as an explicit
  implementation decision only when the demo needs ODF-provided RWO/RWX PVCs
  beyond the underlying OpenShift storage classes.
- Use the Red Hat Developer ODF article as narrative and implementation context
  for lightweight MCG and OBC workflows; product configuration truth remains
  the ODF 4.20 documentation above.

## Source Hierarchy

1. Official Red Hat product documentation for the active baseline.
2. Official Red Hat articles, blogs, and product messaging for narrative and examples.
3. `/Users/adrina/Sandbox/rh-brain/Red Hat Brain` as read-only research input.
4. Existing repo implementation, scripts, and READMEs.
5. Live cluster schema verification with commands such as `oc explain` and `oc get crd`.

Official product documentation remains the source of truth for supported
configuration. Do not invent CR fields, API versions, annotations, or operator
configuration.

## Skill Metadata Policy

Shared skills should reference this repository baseline rather than repeating
exact platform versions in every skill frontmatter. Use exact version-specific
reference files only when a workflow genuinely differs across platform versions.
