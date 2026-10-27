---
name: rhoai-feature-store
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when someone proposes the OpenShift AI Feature Store (Feast): the
  default-dsc `feastoperator` component, a FeatureStore instance in a
  project, offline/online stores and the registry, feature definitions,
  workbench connections, or Ray/Spark compute engines. Not deployed in this
  demo (`feastoperator: Removed`). Do NOT use for Spark itself (use
  rhoai-kubeflow-spark-operator), Ray jobs (use
  rhoai-distributed-workload-workflows), or S3 data in notebooks (use
  rhoai-s3-object-storage-data).
---

# RHOAI Feature Store

Thin skill: Feature Store in OpenShift AI 3.5. **Not deployed in this demo**;
the demo has no tabular feature workloads.

## When to use

- A stage proposes Feature Store, or a change touches `feastoperator` in
  `default-dsc`.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| `feastoperator.managementState: Removed`; the field is not delegated to any stage | `gitops/stages/010-openshift-ai-platform-foundation/010-rhoai-platform/datasciencecluster.yaml`, `.../rhoai-platform/README.md` | [Enable the Feature Store component][enable] |

## If enabled

1. Delegate `/spec/components/feastoperator` in the Stage 010 Application
   and set it `Managed` from a Sync hook in the owning stage (pattern:
   `gitops/stages/050-model-evaluation/050-model-qualification/evaluation-enablement/enable-job.yaml`;
   rules in `rhoai-distributed-workloads` and the Stage 010 README).
2. Declare the `FeatureStore` instance, its storage and RBAC in that
   stage's GitOps folder; check fields with `oc explain` against the
   installed CRD. Database and object-store credentials come from cluster
   Secrets, not Git.
3. Use a database-backed registry and online store before scaling feature
   servers beyond one replica (see the single-replica limitations section).
4. Read-only check after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   oc get datasciencecluster default-dsc -o jsonpath='{.spec.components.feastoperator}{"\n"}'
   ```

## Pitfalls

- Editing `default-dsc` by hand is reverted by Argo CD while the field is
  not delegated.
- The Ray and Spark compute engines need those components, which are also
  `Removed` here.

## Official documentation (OpenShift AI 3.5)

| Topic | Section |
|---|---|
| Overview | [Overview of Feature Store][overview], [Workflow][workflow] |
| Set up | [Set up Feature Store][setup], [Enable the component][enable], [Create an instance][instance], [RBAC][rbac] |
| Configuration | [Customize the configuration][custom], [Single-replica limitations][single], [OIDC authentication][oidc] |
| Features | [Define features][define], [Retrieve features for training][retrieve] |
| Workbenches | [Integration with workbenches][workbenches] |
| Compute engines | [Compute engines][compute] |
| CLI | [Command line reference][cli] |

## Related skills

`rhoai-dsci-dsc-configuration`, `rhoai-distributed-workloads`,
`rhoai-kubeflow-spark-operator`, `rhoai-basic-workbenches`.

[overview]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_machine_learning_features/index#overview-of-feature-store_featurestore
[workflow]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_machine_learning_features/index#feature-store-workflow_featurestore
[setup]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_machine_learning_features/index#setting-up-feature-store_featurestore
[enable]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_machine_learning_features/index#enabling-the-feature-store-component_featurestore
[instance]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_machine_learning_features/index#creating-a-feature-store-instance-in-a-project_featurestore
[rbac]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_machine_learning_features/index#configuring-and-managing-role-based-access-control_featurestore
[custom]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_machine_learning_features/index#customizing-your-feature-store-configuration_customizing-your-feature-store-configuration
[single]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_machine_learning_features/index#single_replica_limitations_for_the_feature_store_operator
[oidc]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_machine_learning_features/index#enabling-oidc-authentication-for-feature-store
[define]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_machine_learning_features/index#defining-ml-features_featurestore
[retrieve]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_machine_learning_features/index#retrieving-features-for-model-training_featurestore
[workbenches]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_machine_learning_features/index#feature-store-integration-with-workbenches_featurestore
[compute]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_machine_learning_features/index#understanding-compute-engines-in-feature-store_featurestore
[cli]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_machine_learning_features/index#feature-store-command-line-interface-reference_featurestore
