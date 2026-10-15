# Stage 070 namespaces (`070-namespaces`)

This Application owns every namespace Stage 070 uses, and nothing else. It deploys first, so every later component can write into any Stage 070 namespace, including ones that belong to a component deployed after it.

| | |
|---|---|
| Argo CD Application | `070-namespaces` ([manifest](../../../argocd/app-of-apps/070-advanced-app-platform/namespaces.yaml)) |
| Deployed by | `stages/070-advanced-app-platform/deploy.sh` → `stage_apps.py deploy 070` (deploy-order 1) |
| Validated by | `stages/070-advanced-app-platform/validate.sh` (component Applications Synced and Healthy); `scripts/shared/stage_apps.py check-static 070` |
| Sync | Automated, `prune: true`, `selfHeal: true`; every Namespace carries `Prune=false`; compare-option `ServerSideDiff=true`; no `ignoreDifferences` |
| Used by | Every other Stage 070 component |

## Why

Sync waves order resources only inside one Application. Several components place objects in namespaces that another component uses:
- `070-identity` writes provisioner Secrets into `gitlab-system`, `rhdh`, `openshift-mta` and `trusted-artifact-signer`.
- `070-devspaces` creates a service account in `app-platform-build`.
- `070-gitlab` binds its integration hub into `rhdh`.

When each component created its own namespace, a fresh install failed at the first component that wrote into a namespace created later. One namespace owner deployed first removes that ordering problem. It also keeps the boundary in one reviewable file.

Every namespace carries `Prune=false,Delete=false`: removing it from Git never deletes it (`Prune=false`), and deleting the `070-namespaces` Application, even with cascade, leaves it in place (`Delete=false`) [1]. GitLab repositories and databases, SonarQube data and developer workspaces live in these namespaces. Deleting a namespace is an explicit operator action ([OPERATIONS: Cleanup Guidance](../../../../docs/OPERATIONS.md#cleanup-guidance)).

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

- **Order.** `stage_apps.py deploy 070` syncs this Application first and waits until it is Synced and Healthy before `070-identity` starts.
- **Metadata owned by controllers.** Controllers add their own labels and annotations after creation: pod security label synchronization, SCC range annotations, OLM and the Pipelines operator. Each writes keys Git does not declare, under its own field manager. With `ServerSideDiff=true` Argo CD compares only the fields it applies, so those keys are not drift and need no `ignoreDifferences`. A label or annotation declared here (for example the enrollment label) is enforced, and a change in Git reaches the cluster.
- **No ignored metadata.** Ignoring `/metadata/annotations` would also hide the `argocd.argoproj.io/tracking-id` annotation: with `RespectIgnoreDifferences` Argo CD then never rewrites it, so an Application could not take a namespace over from another.
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
| Ordering across Applications | Waves order resources only inside one Application [2] | Cross-component order comes from `demo.rhoai.io/deploy-order` in `stage_apps.py deploy 070` | Aligned |
| Diffing controller-owned metadata | Server-side diff compares only the fields Argo CD applies [4] | `ServerSideDiff=true`, no `ignoreDifferences`; declared labels and annotations are enforced | Aligned |
| Pod security | `warn`/`audit` labels are synchronized from service account SCC permissions [3] | Not set in Git | Aligned |

## References

1. Sync options (`CreateNamespace`, `Prune=false`, `Delete=false`, `RespectIgnoreDifferences`), Argo CD (upstream). https://argo-cd.readthedocs.io/en/stable/user-guide/sync-options/
2. Sync phases and waves, Argo CD (upstream). https://argo-cd.readthedocs.io/en/stable/user-guide/sync-waves/
3. Understanding and managing pod security admission, OpenShift Container Platform 4.22. https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html/authentication_and_authorization/understanding-and-managing-pod-security-admission

4. Diff strategies (server-side diff), Argo CD (upstream). https://argo-cd.readthedocs.io/en/stable/user-guide/diff-strategies/

Repository: [Stage 070 README](../../../../stages/070-advanced-app-platform/README.md), [OPERATIONS: Stage 070 GitLab release](../../../../docs/OPERATIONS.md#stage-070-gitlab-release).
