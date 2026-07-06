# Build Review Patterns

These examples are review patterns, not copy-paste manifests. Verify exact API
fields, image references, triggers, and secret names against the official docs
and active cluster schema before committing GitOps resources.

## BuildConfig Shape

```yaml
apiVersion: build.openshift.io/v1
kind: BuildConfig
metadata:
  name: sample-build
spec:
  runPolicy: Serial
  source:
    git:
      uri: https://github.com/example/repository
  strategy:
    sourceStrategy:
      from:
        kind: ImageStreamTag
        name: builder-image:latest
  output:
    to:
      kind: ImageStreamTag
      name: sample-app:latest
```

Review points:

- `runPolicy: Serial` is the documented default posture for sequential builds.
- Replace example source and image references with approved project sources.
- Verify the builder image exists and is supported for the build strategy.
- Do not include webhook secrets, registry credentials, or entitlement data in
  the manifest.

## BuildConfig Trigger Review

```yaml
spec:
  triggers:
    - type: GitHub
      github:
        secretReference:
          name: sample-github-webhook
    - type: Generic
      generic:
        secretReference:
          name: sample-generic-webhook
    - type: ImageChange
```

Review points:

- Use secret references rather than literal secrets.
- Confirm whether webhook triggers are appropriate for a GitOps-managed demo.
- Ensure image-change triggers do not create uncontrolled rebuild loops.

## Build Log And Status Checks

Read-only checks:

```bash
oc get buildconfigs -n <namespace>
oc get builds -n <namespace>
oc describe build <build-name> -n <namespace>
oc logs -f bc/<buildconfig-name> -n <namespace>
oc logs --version=<number> bc/<buildconfig-name> -n <namespace>
```

Review points:

- Use `oc describe build` for source, strategy, output, created-by, digest, and
  source revision information.
- Use build logs to diagnose assemble, Dockerfile, push, and registry issues.
- Do not copy logs containing credentials into committed docs.

## Strategy RBAC Review

Read-only checks:

```bash
oc get clusterrole system:build-strategy-docker -o yaml
oc get clusterrole system:build-strategy-source -o yaml
oc get clusterrole system:build-strategy-custom -o yaml
oc get clusterrolebinding | grep build-strategy
```

Review points:

- Docker and S2I strategy access is commonly available to users who can create
  builds.
- Custom strategy access is more sensitive and should be explicitly justified.
- Global strategy restriction changes affect many projects and require
  platform approval.

## Shipwright Boundary Review

Before writing Shipwright manifests:

```bash
oc api-resources | grep -i shipwright
oc get crd | grep -i shipwright
```

Review points:

- The OCP page confirms Shipwright-based Builds exist and lists capabilities,
  but detailed API fields must come from the separate Builds documentation or
  active CRDs.
- Keep Shipwright build outputs aligned with the same image provenance and
  GitOps deployment rules as BuildConfig outputs.
