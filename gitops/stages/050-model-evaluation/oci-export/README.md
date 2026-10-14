# Evaluation result OCI export (`050-oci-export`)

This Application lets EvalHub jobs in the `evaluated-models` tenant push their result artifacts and evaluation cards as
immutable OCI artifacts to the cluster's internal image registry (repository `evaluated-models/evaluation-results`). It
creates a pusher ServiceAccount, exposes the registry's default route, and composes the registry credential Secret that
jobs reference. `submit-evaluation.sh` adds the export to every job it submits unless `--no-oci-export` is given.

| | |
|---|---|
| Argo CD Application | `050-oci-export` ([manifest](../../../argocd/app-of-apps/050-model-evaluation/oci-export.yaml)) |
| Deployed by | [`stages/050-model-evaluation/deploy.sh`](../../../../stages/050-model-evaluation/deploy.sh) (deploy-order 4, all Stage 050 components at one commit SHA) |
| Validated by | [`validate.sh`](../../../../stages/050-model-evaluation/validate.sh) (Synced and Healthy at the stage revision). No export-specific check. |
| Sync | Automated, `prune` and `selfHeal`. Server-Side Diff by annotation; `RespectIgnoreDifferences=true`. |
| Depends on | `050-model-qualification` (namespace `evaluated-models`); the OpenShift image registry with a publicly trusted default ingress certificate. |
| Used by | EvalHub jobs submitted by [`submit-evaluation.sh`](../../../../stages/050-model-evaluation/submit-evaluation.sh) (`exports.oci` with `k8s.connection: evalhub-oci-registry`). |

## Why

EvalHub can export evaluation results to an OCI registry: the job submission names the registry host and repository and a
`kubernetes.io/dockerconfigjson` Secret with the credentials, and the result's tag and reference appear in the job results
[1]. The internal registry avoids an external registry account. The 3.5.1 `EvalHub` CR has no CA field for this export and
the evaluation sidecar trusts only public roots, so the push goes through the registry's default route, which serves the
cluster's ingress certificate. The documented way to expose that route is `defaultRoute: true` on the image registry
configuration [2].

## What

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| ServiceAccount | `evalhub-oci-pusher` | `evaluated-models` | Wave 12. Registry identity. |
| Secret (`kubernetes.io/service-account-token`) | `evalhub-oci-pusher-token` | `evaluated-models` | Wave 12. Long-lived token for the pusher, filled by Kubernetes. |
| RoleBinding | `evalhub-oci-pusher-image-builder` | `evaluated-models` | Wave 12. `system:image-builder` (push to image streams in this namespace). |
| ServiceAccount | `evalhub-oci-export-provisioner` | `evaluated-models` | Wave 12. Hook identity. |
| ClusterRole / ClusterRoleBinding | `evalhub-oci-export-provisioner` | cluster | Wave 12. `get`/`patch` on `configs.imageregistry.operator.openshift.io/cluster`; `get` on Routes in every namespace. |
| Role / RoleBinding | `evalhub-oci-export-provisioner` | `evaluated-models` | Wave 12. get/patch/update on the pusher token and `evalhub-oci-registry`; create Secrets. |
| Job | `provision-evalhub-oci-export` | `evaluated-models` | `Sync` hook, wave 13, `BeforeHookCreation,HookSucceeded`, `backoffLimit: 3`, no deadline. Sets `defaultRoute: true`, waits for Route `default-route`, builds a docker config from the pusher token and writes Secret `evalhub-oci-registry`. |

### Objects not in Git

| Object | Created by |
|---|---|
| `configs.imageregistry.operator.openshift.io/cluster` field `spec.defaultRoute: true` | The hook (cluster-scoped object owned by the Image Registry Operator, not by any Application) |
| Route `openshift-image-registry/default-route` | Image Registry Operator |
| Secret `evaluated-models/evalhub-oci-registry` (`.dockerconfigjson`) | The hook |
| ImageStream `evaluated-models/evaluation-results` and its tags (`evalhub-<hash>`, `evaluation-card-<job id>`) | Registry, on first push by an EvalHub job |

## How

**Ordering.** RBAC and the token Secret at wave 12, then the hook at wave 13 [3].

**Registry exposure.** The hook patches the cluster image registry configuration rather than declaring it, because that
object is cluster-wide and not owned by this repository. Turning the route on exposes the internal registry outside the
cluster for every namespace; access still requires a token with registry rights [2].

**Credentials.** The pusher's long-lived token is the password in the docker config (`evalhub-oci-pusher:<token>`). Rotate
by deleting `evalhub-oci-pusher-token` and syncing; the hook rewrites `evalhub-oci-registry`. No credential is stored in
Git or printed.

**Cluster-specific values.** The registry route host is read at sync time and written only into the Secret.

## Validation

`validate.sh` requires the Application Synced and Healthy at the stage revision. The export itself is verified only by a
job: its `results.benchmarks[].artifacts` carry the digest and reference.

By hand:

```bash
oc get configs.imageregistry.operator.openshift.io cluster -o jsonpath='{.spec.defaultRoute}{"\n"}'
oc get secret evalhub-oci-registry -n evaluated-models -o jsonpath='{.type}{"\n"}'
```

## Alignment with official guidance

| Topic | Official guidance (link) | This repository | Status |
|---|---|---|---|
| Export mechanism | `exports.oci` with host, repository and a `kubernetes.io/dockerconfigjson` Secret [1] | Secret `evalhub-oci-registry`, repository `evaluated-models/evaluation-results` | Aligned |
| Registry exposure | `defaultRoute: true` creates `default-route` [2] | Set by a hook Job | Deviation (justified: cluster object not owned in Git; sidecar needs a publicly trusted certificate) |
| Least privilege | Narrow RBAC | Cluster-wide `get` on Routes and `patch` on the registry config for the hook | Gap (see findings) |
| Credential lifetime | Short-lived tokens preferred | Long-lived ServiceAccount token Secret | Deviation (justified: the export Secret must stay valid between syncs; rotation documented) |
| Hook bounds | Bounded Jobs | No `activeDeadlineSeconds` | Gap (see findings) |
| Labels | Repository rule: `app.kubernetes.io/name` and `component` on every object | Only the kustomization's `part-of`, `managed-by`, stage labels | Gap (see findings) |
| Argo CD | Server-Side Diff by annotation [4] | Annotation present | Aligned |

## References

1. Evaluating AI systems (2.19 Export evaluation results to an OCI registry), Red Hat OpenShift AI Self-Managed 3.5. https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/evaluating_ai_systems/index
2. Exposing the registry (Expose a default registry manually), OpenShift Container Platform 4.22. https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html/registry/securing-exposing-registry
3. Sync phases and waves, Argo CD (upstream). https://argo-cd.readthedocs.io/en/stable/user-guide/sync-waves/
4. Diff strategies (Server-Side Diff), Argo CD (upstream). https://argo-cd.readthedocs.io/en/stable/user-guide/diff-strategies/
