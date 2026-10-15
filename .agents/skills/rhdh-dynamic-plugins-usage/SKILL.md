---
name: rhdh-dynamic-plugins-usage
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhdh
  docs-version: "1.10"
  skill-group: "Developer Hub"
description: >
  Use when a developer or demo presenter uses the Developer Hub plugins this
  demo enables: the Topology, Kubernetes, CI (Tekton) and Argo CD tabs on the
  coolstore-inventory-service entity or on a project created from a template,
  and when one of those tabs is empty for a user. Do NOT use for enabling or
  configuring plugins (use rhdh-dynamic-plugins-configure or
  rhdh-dynamic-plugins-install), or for catalog and template workflows (use
  rhdh-develop).
---

# RHDH dynamic plugins: usage

Thin skill: what this portal shows and why a tab can be empty; how to use
each plugin is in the linked Developer Hub 1.10 sections. Detailed record:
`gitops/stages/070-advanced-app-platform/070-rhdh/README.md`.

## When to use

- Demonstrating delivery state of a project in the portal (Stage 070 and the
  Stage 110–130 workflows).
- A user reports an empty Topology, Kubernetes, CI or Argo CD tab.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Plugins in use: Topology, Kubernetes, Tekton (CI tab), Argo CD; no Keycloak, JFrog, Nexus or Ansible plugins | `gitops/stages/070-advanced-app-platform/070-rhdh/rhdh-instance/dynamic-plugins-configmap.yaml` | [Topology][topology], [Tekton][tekton], [Argo CD][argocd] |
| The reference entity `component:default/coolstore-inventory-service` carries `backstage.io/kubernetes-id`, `janus-idp.io/tekton` and `argocd/app-name: project-coolstore-inventory-service` | `070-rhdh/catalog/all.yaml` | [Enable users to use Topology][topology-users] |
| Template-created projects get the same three annotations, with Argo CD app `project-<name>` created by the enrollment coordinator | `070-rhdh/templates/app-migration/skeleton/catalog-info.yaml`, `070-rhdh/templates/agentic-quarkus-scaffold/skeleton/catalog-info.yaml` | [Topology][topology] |
| Role `role:default/developer` (`ai-developer`) may read Kubernetes clusters and resources; no catalog writes | `070-rhdh/rhdh-instance/rbac-policy.yaml` | see `rhdh-authorization` |
| Plugin reads use the `rhdh-kubernetes-reader` ServiceAccount (ClusterRole `view`), not the signed-in user | `070-rhdh/rhdh-instance/kubernetes-reader.yaml` | [Enable users to use Topology][topology-users] |

## Procedure

1. Sign in as `ai-developer` or `ai-admin` (Keycloak `platform` realm) and open
   the entity; the tabs need the project's namespace, PipelineRuns and the
   `project-<name>` Argo CD Application to exist.
2. If a tab is empty, check the objects behind it (read-only, after the
   OpenShift safety guard in `AGENTS.md`):

   ```bash
   oc get deployment,pipelinerun -n <project>-dev -l backstage.io/kubernetes-id=<name>
   oc get application project-<name> -n openshift-gitops
   ```

3. Platform-side checks: `./stages/070-advanced-app-platform/validate.sh`
   ("Coolstore pipeline installed", "Runtime is reconciled from delivery Git").

## Pitfalls

- Every Kubernetes-backed tab shows "Problem retrieving Kubernetes objects"
  when the cluster CA is not trusted process-wide:
  `docs/TROUBLESHOOTING.md#developer-hub-topologycikubernetes-tabs-show-problem-retrieving-kubernetes-objects`.
- The Coolstore entity disappears when the runtime catalog is stale or
  refused: `docs/TROUBLESHOOTING.md#red-hat-developer-hub-catalog-does-not-load-coolstore`
  and `docs/TROUBLESHOOTING.md#rhdh-catalog-generator-refuses-factory_bundle_mismatch`.
- Workloads must carry the `backstage.io/kubernetes-id` label as well as the
  entity annotation, or Topology shows nothing ([Kubernetes plugin annotations][k8s-annot]).
- Tabs for a new project appear only after the enrollment coordinator has
  created the namespace and Application (`ocp-pipelines-cicd`).

## Official documentation (Developer Hub 1.10)

| Topic | Section |
|---|---|
| Argo CD tab | [Use the Argo CD plugin][argocd] |
| CI tab | [Use the Tekton plugin][tekton] |
| Topology | [Use the Topology plugin][topology], [Enable users to use it][topology-users] |
| Annotations and labels | [Kubernetes plugin annotations][k8s-annot] |
| Plugins not used here | [Keycloak][keycloak], [JFrog Artifactory][jfrog], [Nexus][nexus] |

## Related skills

`rhdh-dynamic-plugins-configure`, `rhdh-develop`,
`rhdh-getting-started-navigate`, `rhdh-authorization`, `ocp-pipelines-cicd`.

[argocd]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/using_dynamic_plugins_in_red_hat_developer_hub/index#use-the-argo-cd-plugin_using-dynamic-plugins-in-rhdh
[tekton]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/using_dynamic_plugins_in_red_hat_developer_hub/index#use-the-tekton-plugin_using-dynamic-plugins-in-rhdh
[topology]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/using_dynamic_plugins_in_red_hat_developer_hub/index#use-the-topology-plugin_using-dynamic-plugins-in-rhdh
[topology-users]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/using_dynamic_plugins_in_red_hat_developer_hub/index#enable-users-to-use-the-topology-plugin_use-the-topology-plugin
[keycloak]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/using_dynamic_plugins_in_red_hat_developer_hub/index#use-keycloak_using-dynamic-plugins-in-rhdh
[jfrog]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/using_dynamic_plugins_in_red_hat_developer_hub/index#use-the-jfrog-artifactory-plugin_using-dynamic-plugins-in-rhdh
[nexus]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/using_dynamic_plugins_in_red_hat_developer_hub/index#use-the-nexus-repository-manager-plugin_using-dynamic-plugins-in-rhdh
[k8s-annot]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/configuring_dynamic_plugins/index#add-entity-annotations-and-labels-for-the-kubernetes-plugin_manage-labels-and-annotations-for-topology-plugins
