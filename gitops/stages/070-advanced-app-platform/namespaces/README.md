# Stage 070 namespaces (`070-namespaces`)

This Application owns every namespace Stage 070 uses, and nothing else. It deploys first, so every later component can write into any Stage 070 namespace, including ones that belong to a component deployed after it.

| | |
|---|---|
| Argo CD Application | `070-namespaces` ([manifest](../../../argocd/app-of-apps/070-advanced-app-platform/namespaces.yaml)) |
| Deployed by | `stages/070-advanced-app-platform/deploy.sh` → `application.py deploy` (deploy-order 1) |
| Validated by | `stages/070-advanced-app-platform/validate.sh` (component Applications Synced and Healthy); `scripts/shared/stage_apps.py check-static 070` |
| Sync | Automated, `prune: true`, `selfHeal: true`; every Namespace carries `Prune=false`; `ignoreDifferences` on Namespace `/metadata/annotations` and `/metadata/labels` |
| Used by | Every other Stage 070 component |

## Why

Sync waves order resources only inside one Application. Several components place objects in namespaces that another component uses:
- `070-identity` writes provisioner Secrets into `gitlab-system`, `rhdh`, `openshift-mta` and `trusted-artifact-signer`.
- `070-devspaces` creates a service account in `app-platform-build`.
- `070-gitlab` binds its integration hub into `rhdh`.

When each component created its own namespace, a fresh install failed at the first component that wrote into a namespace created later. One namespace owner deployed first removes that ordering problem. It also keeps the boundary in one reviewable file.

`Prune=false` on every namespace means removing a namespace from Git never deletes it. GitLab repositories and databases, SonarQube data and developer workspaces live in these namespaces. Deleting a namespace is an explicit operator action ([OPERATIONS: Cleanup Guidance](../../../../docs/OPERATIONS.md#cleanup-guidance)).

## What

| Namespace | Used by | Notes |
|---|---|---|
| `openshift-devspaces` | `070-devspaces` | Dev Spaces operator and CheCluster |
| `wksp-ai-admin`, `wksp-ai-developer`, `wksp-kubeadmin` | `070-devspaces` | Persona workspace namespaces; labels `app.kubernetes.io/part-of: che.eclipse.org`, `app.kubernetes.io/component: workspaces-namespace`, annotation `che.eclipse.org/username` |
| `app-platform-build` | `070-pipelines` | Build namespace, project enrollment, webhook dispatcher |
| `trusted-artifact-signer` | `070-pipelines` | Trusted Artifact Signer instance |
| `sonarqube` | `070-sonarqube` | SonarQube and its database |
| `openshift-mta`, `openshift-vertical-pod-autoscaler` | `070-mta` | MTA operator and instance; VPA operator for the MTA controller sizing |
| `coolstore-dev` | Coolstore enrollment | Labels `app.kubernetes.io/part-of: coolstore`, `rhoai3.redhat.com/pipeline-project: "true"`; workload comes from the GitLab delivery repository |
| `gitlab-system` | `070-gitlab` | GitLab and its storage |
| `rhdh-operator`, `rhdh` | `070-rhdh` | Developer Hub operator and instance |

The `coolstore-dev` namespace is the only object the demo platform declares for Coolstore. GitLab project enrollment adds its pipeline, webhook listener and `project-coolstore-inventory-service` Application. `runtime-coolstore-inventory-service` reconciles its Deployment, Service and Route from delivery Git.

## How

- **Order.** `application.py` syncs this Application first and waits until it is Synced and Healthy before `070-identity` starts.
- **Ignored metadata.** Operators add labels and annotations after creation (pod security synchronization, SCC annotations, the Pipelines operator). The Application ignores Namespace labels and annotations, so it stays Synced without fighting them. With `RespectIgnoreDifferences=true`, ignored fields are also left out of later syncs. A label added in Git to an existing namespace therefore does not reach the cluster: see [TROUBLESHOOTING: a namespace label added in Git never reaches the cluster](../../../../docs/TROUBLESHOOTING.md#a-namespace-label-added-in-git-never-reaches-the-cluster).
- **Label contract.** The enrollment reconciler and the SonarQube ingress policy select namespaces by `rhoai3.redhat.com/pipeline-project=true`, which `coolstore-dev` carries from creation.

## Validation

- `validate.sh` checks every Stage 070 component Application is Synced and Healthy, this one included.
- `stage_apps.py check-static 070` checks that the components render disjoint object sets that add up to the stage aggregate.

```bash
oc get namespaces app-platform-build coolstore-dev gitlab-system openshift-devspaces openshift-mta openshift-vertical-pod-autoscaler \
  rhdh rhdh-operator sonarqube trusted-artifact-signer wksp-ai-admin wksp-ai-developer wksp-kubeadmin \
  -o custom-columns=NAME:.metadata.name,OWNER:.metadata.annotations.argocd\\.argoproj\\.io/tracking-id
```

## Alignment with official guidance

| Topic | Official guidance | This repository | Status |
|---|---|---|---|
| Namespaces from Git | Argo CD manages a declared Namespace like any resource; `CreateNamespace` creates only the destination namespace [1] | All namespaces declared explicitly in one Application, deployed first | Aligned |
| Protecting stateful namespaces | `Prune=false` keeps a resource when it leaves Git [1] | Every Stage 070 namespace | Aligned |
| Ordering across Applications | Waves order resources only inside one Application [2] | Cross-component order comes from `demo.rhoai.io/deploy-order` in `application.py` | Aligned |
| Ignored metadata | `RespectIgnoreDifferences` leaves ignored fields out of sync [1] | Labels and annotations ignored | Deviation (justified: controllers own most namespace metadata); drift in a contract label is not detected |
| Pod security | `warn`/`audit` labels are synchronized from service account SCC permissions [3] | Not set in Git | Aligned |

## References

1. Sync options (`CreateNamespace`, `Prune=false`, `RespectIgnoreDifferences`), Argo CD (upstream). https://argo-cd.readthedocs.io/en/stable/user-guide/sync-options/
2. Sync phases and waves, Argo CD (upstream). https://argo-cd.readthedocs.io/en/stable/user-guide/sync-waves/
3. Understanding and managing pod security admission, OpenShift Container Platform 4.22. https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html/authentication_and_authorization/understanding-and-managing-pod-security-admission

Repository: [Stage 070 README](../../../../stages/070-advanced-app-platform/README.md), [OPERATIONS: Stage 070 GitLab release](../../../../docs/OPERATIONS.md#stage-070-gitlab-release).
