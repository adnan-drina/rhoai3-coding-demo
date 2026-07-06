# Validation Checklist

Use this checklist when reviewing OCP GitOps documentation, GitOps manifests,
or live operations.

## Source And Baseline

- The task references the active OCP baseline in `docs/PLATFORM_BASELINE.md`.
- OCP-level GitOps claims are traced to the official OCP GitOps overview.
- Detailed Red Hat OpenShift GitOps behavior is not claimed unless the separate
  Red Hat OpenShift GitOps documentation and active cluster schema were
  checked.
- Repo-specific Argo CD Application and Kustomize conventions are handled by
  `project-gitops-authoring`.

## Manifest Review

- OpenShift GitOps Operator installation, channel, namespace, subscription, and
  install mode are verified from separate Red Hat OpenShift GitOps docs or the
  active cluster catalog.
- Argo CD instance fields are verified against the installed `ArgoCD` CRD.
- `Application`, `ApplicationSet`, `AppProject`, and related `argoproj.io`
  resources use verified API versions and fields.
- Repository credentials, cluster credentials, tokens, SSO secrets, and webhook
  secrets are not committed.
- RBAC, cluster roles, and service accounts are reviewed as platform-sensitive
  resources.
- Resource tracking behavior is verified before changing
  `resourceTrackingMethod`.
- Project-specific Application layout, sync waves, `targetRevision`,
  Kustomize paths, and ignore-differences rules are reviewed with
  `project-gitops-authoring`.

## Read-Only Cluster Checks

Run only after the repo environment guard confirms the target cluster:

```bash
oc get subscription -A | grep -i gitops
oc get csv -A | grep -i gitops
oc api-resources | grep -Ei 'argo|gitops'
oc get crd | grep -Ei 'argo|gitops'
oc get argocd -A
oc get applications.argoproj.io -A
oc get appprojects.argoproj.io -A
oc get pods -A | grep -Ei 'argocd|gitops'
```

For schema verification:

```bash
oc explain argocd.spec
oc explain applications.argoproj.io.spec
oc explain appprojects.argoproj.io.spec
```

For resource tracking discovery:

```bash
oc get cm -A | grep -i argocd
oc get cm <argocd-configmap-name> -n <argocd-namespace> -o yaml
```

## Live Operation Review

- The repo-local OpenShift safety guard is used before any `oc` or `kubectl`
  command that touches the cluster.
- Operator installation, Argo CD instance changes, RBAC changes, repository
  credential changes, SSO changes, cluster credential changes, and resource
  tracking changes have explicit user approval.
- Argo CD-managed resources are not also managed with direct `oc apply -k`
  unless the exception is documented.
- Bootstrap operations are sequenced so the GitOps Operator and Argo CD
  instance exist before demo Applications are applied.

## Fail Conditions

Stop and ask for verification if:

- the documentation version does not match `docs/PLATFORM_BASELINE.md`
- a detailed GitOps claim is based only on the OCP overview page
- a manifest includes unverified `argoproj.io` or Operator CR fields
- credentials would be committed to Git
- resource tracking would change away from the project-required annotation
  mode without explicit approval
- live Argo CD state and Git state would manage the same resource in
  conflicting ways
