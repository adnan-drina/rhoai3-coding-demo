# Official Doc Extraction

This extraction is derived from the official RHOAI 3.4 chapter captured in
`source-capture.md`.

## Default Behavior

After OpenShift AI installation, the OpenShift AI Operator creates an empty
`odh-trusted-ca-bundle` ConfigMap. The Cluster Network Operator injects the
cluster-wide CA bundle into it when the ConfigMap has the
`config.openshift.io/inject-trusted-cabundle` label.

The DSCI field `spec.trustedCABundle.managementState` controls how OpenShift AI
manages this ConfigMap:

| State | Behavior |
|-------|----------|
| `Managed` | Operator manages `odh-trusted-ca-bundle` in non-reserved namespaces and updates it from `customCABundle`. |
| `Unmanaged` | ConfigMap is not removed, but the Operator stops updating it from `customCABundle`. |
| `Removed` | Operator removes `odh-trusted-ca-bundle` from existing non-reserved namespaces and stops creating it in new ones. |

Reserved/system namespaces such as `default`, `openshift-*`, and `kube-*` are
not targets for the Operator-managed ConfigMap.

## Adding Certificates

Use one of two top-level patterns:

- Cluster-wide CA bundle: use when many services need the certificate or
  policy requires cluster-wide trust.
- RHOAI custom CA bundle: use when the certificate should stay scoped to
  OpenShift AI components and avoid global cluster impact.

Cluster-wide pattern:

- Create a ConfigMap in `openshift-config` with `ca-bundle.crt`.
- Patch `proxy/cluster` so `spec.trustedCA.name` points at that ConfigMap.
- Verify `odh-trusted-ca-bundle` exists in non-reserved namespaces.

RHOAI custom bundle pattern:

- Set DSCI `spec.trustedCABundle.managementState: Managed`.
- Add PEM-encoded CA certificates to `spec.trustedCABundle.customCABundle`.
- The Operator updates `odh-trusted-ca-bundle` with `odh-ca-bundle.crt`.

## S3-Compatible Object Storage And In-Cluster Databases

For OpenShift-hosted object storage or databases that use self-signed
certificates, include the relevant CA in the OpenShift AI trusted CA
configuration. Each namespace includes `kube-root-ca.crt`, which contains the
internal API server CA certificate.

Use this pattern when AI pipelines or other OpenShift AI components need to
connect to an in-cluster service that presents a certificate signed by the
cluster CA.

## AI Pipelines

AI pipelines can trust self-signed or custom certificates through:

- cluster-wide CA bundle
- RHOAI custom CA bundle
- pipeline-specific CA bundle

For a pipeline-specific bundle:

- Create a ConfigMap in the same project as the target pipeline.
- Configure the underlying `DataSciencePipelinesApplication` to reference that
  ConfigMap from its API server CA bundle field.
- The pipeline server pod redeploys and mounts the bundle at
  `/dsp-custom-certs/dsp-ca.crt`.

Verify exact field casing against the active DSPA CRD before writing GitOps.

## Workbenches

Cluster-wide self-signed certificates apply automatically to workbenches created
after the certificate configuration exists. Existing workbenches must be stopped
and restarted to pick up the configured certificates.

Workbench certificate path:

```text
/etc/pki/tls/custom-certs/ca-bundle.crt
```

Use this path explicitly for libraries that do not automatically use the
preconfigured certificate environment.

## Model Serving

The model serving platform uses a self-signed certificate generated at
installation for model server endpoints by default. If cluster-wide OpenShift
certificates are configured, they can be used for other endpoint types such as
routes.

The official procedure copies a TLS secret reference from `openshift-ingress`
into `istio-system` and configures the KServe serving ingress gateway
certificate in the `DataScienceCluster`.

Verify the active `DataScienceCluster` schema before GitOps promotion. The
official example uses a provided certificate secret for the KServe ingress
gateway.

## Llama Stack

By default, Llama Stack server images trust public CAs only. For external
inference, embedding, or vector-store providers that use self-signed or private
CA certificates, configure `spec.server.tlsConfig.caBundle` on the
`LlamaStackDistribution` CR.

Preferred pattern:

- Add the CA to the cluster-wide or RHOAI custom CA bundle.
- Reference `odh-trusted-ca-bundle` from `LlamaStackDistribution`.
- Include both keys when using the OpenShift AI managed ConfigMap:
  - `ca-bundle.crt`
  - `odh-ca-bundle.crt`

Operator behavior:

- validates certificate PEM blocks from the source ConfigMap
- creates a managed `<instance-name>-ca-bundle` ConfigMap
- mounts the bundle at `/etc/ssl/certs/ca-bundle/ca-bundle.crt`
- sets `SSL_CERT_FILE` to that path
- restarts the server pod when the CA bundle configuration changes

Llama Stack CA bundle subfields:

| Field | Meaning |
|-------|---------|
| `configMapName` | Required source ConfigMap name |
| `configMapNamespace` | Optional source namespace; cross-namespace access requires RBAC |
| `configMapKeys` | Optional keys to concatenate; default is `ca-bundle.crt` |

Validation rules and limits:

- Only PEM blocks of type `CERTIFICATE` are processed.
- Bundle must contain at least one valid X.509 certificate.
- Kubernetes source ConfigMap size limit still applies.
- Llama Stack generated bundle limit is 10 MB.
- Maximum valid certificate count is 1000.
- Validation errors surface in `LlamaStackDistribution.status.conditions`.

## Unmanaged And Removed Modes

Use `Unmanaged` when another automation system owns trusted CA bundle updates.
Changing from `Managed` to `Unmanaged` does not delete existing
`odh-trusted-ca-bundle` ConfigMaps.

Use `Removed` only when the demo or environment intentionally uses a different
authentication approach and should not receive the OpenShift AI trusted CA
bundle.

Namespace-only opt-out uses this annotation:

```text
security.opendatahub.io/inject-trusted-ca-bundle=false
```

Apply it only to non-reserved namespaces that must not receive the ConfigMap.

## Unresolved Items

This chapter does not define:

- enterprise certificate issuance or rotation policy
- cert-manager issuer configuration
- private key storage policy
- exact GitOps secret material handling for environment-specific certificates

Use official OpenShift, RHOAI, and organization security policy before
implementing those areas.
