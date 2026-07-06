# Validation Checklist

Use this checklist when reviewing OCP build documentation, GitOps manifests, or
live operations.

## Source And Baseline

- The task references the active OCP baseline in `docs/PLATFORM_BASELINE.md`.
- CI/CD routing is traced to the official OCP CI/CD overview.
- Shipwright build behavior is limited to what the OCP page states unless the
  separate Builds for Red Hat OpenShift documentation and active CRDs are
  verified.
- BuildConfig behavior is traced to the official Builds using BuildConfig
  guide.

## Manifest Review

- `BuildConfig`, `Build`, `BuildRequest`, and `BuildLog` resources use verified
  `build.openshift.io/v1` schemas.
- Shipwright resources use only API versions and fields verified from official
  Builds documentation or active CRDs.
- Build strategy choice is explicit: Docker, S2I, custom, pipeline, or
  Shipwright strategy.
- Build inputs and precedence are documented when multiple input types are
  used.
- Git, Dockerfile, binary input, image source, secrets, config maps, and
  external artifacts are intentionally selected.
- Output image references, ImageStreams, registries, labels, and environment
  variables are reviewed for provenance and promotion flow.
- Secret references do not expose registry credentials, entitlement material,
  tokens, or private source credentials in Git.
- Triggers are intentional and use approved webhook secret handling.
- Build hooks are documented and do not hide deployment or validation behavior.
- Resource requests, limits, maximum duration, run policy, and pruning behavior
  are explicit for recurring builds.
- Node assignment is reviewed with `ocp-nodes` before selectors or tolerations
  are added.
- Build strategy RBAC changes are justified and scoped.
- Build controller configuration changes are treated as platform operations.

## Read-Only Cluster Checks

Run only after the repo environment guard confirms the target cluster:

```bash
oc get buildconfigs -A
oc get builds -A
oc get imagestreams -A
oc get clusterrole | grep build-strategy
oc get clusterrolebinding | grep build-strategy
oc get pods -A | grep -Ei 'build|shipwright'
```

For schema verification:

```bash
oc explain buildconfig.spec
oc explain build.spec
oc get crd | grep -Ei 'shipwright|build'
oc api-resources | grep -Ei 'build|shipwright'
```

For diagnostics:

```bash
oc describe build <build-name>
oc logs -f bc/<buildconfig-name>
oc logs --version=<number> bc/<buildconfig-name>
```

## Live Operation Review

- The repo-local OpenShift safety guard is used before any `oc` or `kubectl`
  command that touches the cluster.
- Creating, starting, canceling, deleting, or pruning builds has explicit user
  approval when run against a live environment.
- Build strategy RBAC changes have explicit approval and security review.
- Build-controller configuration, cluster CA, subscription entitlement, and
  registry credential changes have explicit approval.
- Build outputs are not treated as deployed state unless ArgoCD/GitOps consumes
  the approved image reference.

## Fail Conditions

Stop and ask for verification if:

- the documentation version does not match `docs/PLATFORM_BASELINE.md`
- a manifest includes unverified BuildConfig or Shipwright fields
- build secrets or subscription entitlements would be committed
- a build strategy is enabled broadly without a documented reason
- a build workflow bypasses the project GitOps deployment model
- Shipwright API details are needed but the separate Builds documentation or
  active CRDs have not been checked
