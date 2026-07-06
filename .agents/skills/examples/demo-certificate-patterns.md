# Demo Certificate Patterns

These snippets are implementation patterns, not complete environment manifests.
Verify active CRDs and avoid committing private keys or environment-specific
certificate material.

## Preferred Demo DSCI State

```yaml
spec:
  trustedCABundle:
    managementState: Managed
    customCABundle: |
      -----BEGIN CERTIFICATE-----
      <public-demo-ca-certificate>
      -----END CERTIFICATE-----
```

Use this when demo components need to trust a private or self-signed CA without
changing OpenShift cluster-wide trust.

## Llama Stack Trust From OpenShift AI Managed Bundle

```yaml
spec:
  server:
    tlsConfig:
      caBundle:
        configMapName: odh-trusted-ca-bundle
        configMapKeys:
          - ca-bundle.crt
          - odh-ca-bundle.crt
```

Use this when Llama Stack must trust external inference, embedding, or vector
store providers that use certificates already present in the OpenShift AI
trusted CA bundle.

## Namespace Opt-Out

```text
security.opendatahub.io/inject-trusted-ca-bundle=false
```

Use this annotation only when a specific non-reserved namespace should not
receive `odh-trusted-ca-bundle`.

## Workbench Client Path

```text
/etc/pki/tls/custom-certs/ca-bundle.crt
```

Use this path in client code only when the library does not automatically honor
the workbench certificate environment.

## Pipeline-Specific Bundle Contract

When a pipeline needs its own CA bundle:

- create a ConfigMap in the same namespace as the pipeline server
- store the CA bundle under `ca-bundle.crt`
- configure the target `DataSciencePipelinesApplication` to reference that
  ConfigMap after verifying the active CRD
- verify the pipeline server pod has `/dsp-custom-certs/dsp-ca.crt`

Do not infer DSPA field casing from memory.
