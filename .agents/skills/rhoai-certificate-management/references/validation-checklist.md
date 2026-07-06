# Validation Checklist

Use this checklist before approving RHOAI certificate GitOps, docs, or demo
instructions.

## Source Review

- Product links use the active baseline in `docs/PLATFORM_BASELINE.md`.
- Certificate decisions are tied to official RHOAI docs or verified CRDs.
- Private keys are not committed.
- Environment-specific CA PEM content is not committed unless explicitly
  approved as public demo material.
- README claims match implemented manifests and validation commands.

## DSCI Trusted CA Review

Run only after following the OpenShift safety guard in `AGENTS.md`:

```bash
oc get dscinitialization default-dsci -o yaml
oc explain dscinitialization.spec.trustedCABundle
oc get configmaps --all-namespaces -l app.kubernetes.io/part-of=opendatahub-operator | rg odh-trusted-ca-bundle
```

Check:

- `managementState` is `Managed` unless `Unmanaged` or `Removed` is explicitly
  justified.
- `customCABundle` contains only intended public CA certificates.
- `odh-trusted-ca-bundle` appears only where expected.
- ConfigMap data includes `ca-bundle.crt` and/or `odh-ca-bundle.crt` as
  intended.

## Component Review

AI pipelines:

```bash
oc explain datasciencepipelinesapplication.spec
oc get datasciencepipelinesapplication -A -o yaml
```

- DSPA CA bundle fields are verified against the active CRD.
- Pipeline-specific ConfigMaps live in the same namespace as the target
  pipeline unless official docs and RBAC support another pattern.
- Pipeline server pods redeploy after CA changes.

Workbenches:

- Existing workbenches are stopped and restarted after CA bundle changes.
- Client code uses `/etc/pki/tls/custom-certs/ca-bundle.crt` when a library
  does not honor default certificate environment settings.

Model serving:

```bash
oc explain datasciencecluster.spec.components.kserve
oc get datasciencecluster default-dsc -o yaml
```

- KServe ingress gateway certificate fields are verified before GitOps
  promotion.
- TLS secret references do not expose private key material in repo content.

Llama Stack:

```bash
oc explain llamastackdistribution.spec.server.tlsConfig
oc get llamastackdistribution -A -o yaml
oc get configmap <instance-name>-ca-bundle -n <namespace>
oc get pods -n <namespace> -l app.kubernetes.io/instance=<instance-name>
```

- `configMapName`, optional `configMapNamespace`, and optional `configMapKeys`
  match official docs and active schema.
- Referenced ConfigMaps and keys exist.
- Cross-namespace references have required read access.
- `DeploymentReady` is `True` and no condition reports CA validation failure.
- Server pod exposes `/etc/ssl/certs/ca-bundle/ca-bundle.crt` and
  `SSL_CERT_FILE` points to it.

## Removal Review

- `Removed` is used only when the environment intentionally disables the
  OpenShift AI CA bundle.
- Namespace opt-out annotation is applied only to specific non-reserved
  namespaces.
- Removal commands are treated as live-cluster changes and require the
  OpenShift safety guard.

## Fail Conditions

- `customCABundle` changes are made while `managementState` is `Unmanaged` and
  the docs claim the Operator will propagate them.
- A component-specific CA field is written without CRD verification.
- Llama Stack CA bundles contain no valid `CERTIFICATE` PEM blocks.
- A bundle exceeds documented Llama Stack limits.
- Private keys or kubeconfig credentials appear in committed certificate
  examples.
