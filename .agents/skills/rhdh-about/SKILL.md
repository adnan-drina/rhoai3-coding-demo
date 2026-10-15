---
name: rhdh-about
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhdh
  docs-version: "1.10"
  skill-group: "Developer Hub"
description: >
  Use when explaining what Red Hat Developer Hub does in this demo and how the
  portal is built: role in Stage 070 (catalog, two software templates,
  TechDocs, Kubernetes/Topology/Tekton/Argo CD views), architecture and
  external dependencies, Operator vs Helm choice, single-replica sizing and
  local database posture, and supported platforms. Do NOT use for installing
  (use rhdh-install-ocp), configuring (use rhdh-configure), plugins (use
  rhdh-dynamic-plugins-configure), or access control (use rhdh-authorization).
---

# About Developer Hub in this demo

Thin skill: the repo's use of Developer Hub and its deliberate deviations;
product concepts in the linked Developer Hub 1.10 sections. Detailed record:
`gitops/stages/070-advanced-app-platform/rhdh/README.md` and
`stages/070-advanced-app-platform/README.md`.

## When to use

- Explaining the portal's place in the workshop (Stage 070 builds it,
  Stages 110–130 consume it).
- Reviewing sizing, high availability or database choices.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| One self-service entry point: catalog, templates `agentic-quarkus-scaffold` and `app-migration`, TechDocs, delivery views for each project | `gitops/stages/070-advanced-app-platform/rhdh/templates/`, `rhdh/catalog/all.yaml` | [Key features][features] |
| Operator deployment, not the Helm chart | `gitops/stages/070-advanced-app-platform/rhdh/rhdh-operator/` | [Compare Helm and Operator][compare] |
| One backend replica with the Operator-managed local PostgreSQL (Deviation, justified for a single-cluster demo) | `gitops/stages/070-advanced-app-platform/rhdh/rhdh-instance/backstage.yaml` | [Database high availability][db-ha], [Sizing][sizing] |
| External dependencies are in-cluster: Keycloak `platform` realm, private GitLab mirror, Argo CD, Kubernetes API | `gitops/stages/070-advanced-app-platform/rhdh/README.md` (Depends on) | [External data dependencies][deps] |
| Catalog and templates pinned to one reviewed platform commit in the GitLab mirror | `gitops/stages/070-advanced-app-platform/rhdh/jobs/catalog/` | — (repo design) |

## Procedure

1. For any behavior question start at the component README "Why/What/How"
   and its "Alignment with official guidance" table; it lists every Gap and
   Deviation.
2. Read-only state after the safety guard in `AGENTS.md`:

   ```bash
   oc get backstage developer-hub -n rhdh
   oc get deployment,statefulset,route -n rhdh
   ```

## Pitfalls

- Sizing guidance recommends two or more application replicas and an
  external database for production; the demo knowingly runs one replica on
  the local database ([Sizing][sizing]). Do not scale the Deployment by hand;
  it is Operator-owned and `maxSurge: 0` is set for migration safety.
- Supported OpenShift versions come from the lifecycle page linked from
  [Supported platforms][platforms], not from this skill.

## Official documentation (Developer Hub 1.10)

| Topic | Section |
|---|---|
| Concepts | [Internal developer platforms][idp], [Key features][features] |
| Architecture | [System architecture][arch], [External data dependencies][deps] |
| Deployment method | [Compare Helm and Operator][compare] |
| HA and sizing | [High availability][ha], [Database high availability][db-ha], [Sizing][sizing] |
| Integrations | [Integrations][integrations], [OpenShift integration][ocp] |
| Platforms and support | [Supported platforms][platforms], [Support][support] |

## Related skills

`rhdh-install-ocp`, `rhdh-configure`, `rhdh-release-notes`,
`rhdh-getting-started-setup`, `rhdh-dynamic-plugins-configure`.

[idp]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/about_red_hat_developer_hub/index#understanding-internal-developer-platforms_about-rhdh
[features]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/about_red_hat_developer_hub/index#key-features
[arch]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/about_red_hat_developer_hub/index#system-architecture-for-deployment-planning_about-rhdh
[deps]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/about_red_hat_developer_hub/index#external-data-dependencies
[compare]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/about_red_hat_developer_hub/index#compare-the-helm-chart-and-operator-to-choose-the-optimal-deployment-method_about-rhdh
[ha]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/about_red_hat_developer_hub/index#high-availability-with-database-and-cache-layers_about-rhdh
[db-ha]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/about_red_hat_developer_hub/index#database-high-availability
[sizing]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/about_red_hat_developer_hub/index#sizing-requirements-for-rhdh_about-rhdh
[integrations]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/about_red_hat_developer_hub/index#integrations-in-rhdh_about-rhdh
[ocp]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/about_red_hat_developer_hub/index#integration-with-red-hat-openshift-container-platform
[platforms]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/about_red_hat_developer_hub/index#supported-platforms_about-rhdh
[support]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/about_red_hat_developer_hub/index#rhdh-support_about-rhdh
