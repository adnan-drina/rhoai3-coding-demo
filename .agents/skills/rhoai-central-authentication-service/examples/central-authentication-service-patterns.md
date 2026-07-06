# Central Authentication Service Patterns

These examples show the intended shape for future GitOps manifests and
runbooks. Replace placeholders with verified provider values before using them
in active manifests.

## OIDC Client Secret Placeholder

Do not commit a real client secret. This manifest shape is only a placeholder:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: oidc-client-secret
  namespace: openshift-ingress
type: Opaque
stringData:
  clientSecret: <do-not-commit-real-secret>
```

Active GitOps should use the project-approved secret mechanism once it exists.

## GatewayConfig OIDC Patch Shape

Verify the live `GatewayConfig` name before using this shape:

```yaml
apiVersion: opendatahub.io/v1alpha1
kind: GatewayConfig
metadata:
  name: <verified-gatewayconfig-name>
spec:
  oidc:
    issuerURL: <https://provider.example.com/realms/rhoai>
    clientID: <client-id>
    clientSecretRef:
      name: oidc-client-secret
      key: clientSecret
```

Schema and object checks:

```bash
oc get gatewayconfigs
oc explain gatewayconfig.spec
```

## Custom Provider CA Shape

Use only when the external OIDC provider requires a custom or private CA:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: external-oidc-ca
  namespace: openshift-ingress
type: Opaque
stringData:
  ca.crt: |
    -----BEGIN CERTIFICATE-----
    <provider-ca-certificate>
    -----END CERTIFICATE-----
---
apiVersion: opendatahub.io/v1alpha1
kind: GatewayConfig
metadata:
  name: <verified-gatewayconfig-name>
spec:
  providerCASecretName: external-oidc-ca
```

The official chapter also shows `insecureSkipVerify: true` as development and
test only; do not use it for this demo unless the user explicitly approves a
temporary exception.

## Service Account Token API Access Runbook Shape

Use generated tokens as credentials and never commit them:

```bash
oc create serviceaccount <service_account_name> -n <target_namespace>
oc apply -n <target_namespace> -f <least_privilege_role.yaml>
oc create rolebinding <binding_name> \
  --role=<role_name> \
  --serviceaccount=<target_namespace>:<service_account_name> \
  -n <target_namespace>
TOKEN="$(oc create token <service_account_name> -n <target_namespace> --duration=1h)"
GATEWAY_URL="$(oc get route data-science-gateway -n openshift-ingress -o jsonpath='{.spec.host}')"
curl -k -H "Authorization: Bearer ${TOKEN}" "https://${GATEWAY_URL}/<service-path>"
```

For failures, check gateway and proxy resources:

```bash
oc logs -l app=kube-auth-proxy -n openshift-ingress
oc get gateway data-science-gateway -n openshift-ingress
oc get httproute -n openshift-ingress
```
